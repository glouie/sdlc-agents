"""
code_security_agent.py — SDLC Phase 3: Development
Reviews code for security vulnerabilities and fixes them.

Scope: injection, secrets, input validation, dangerous patterns.
Does NOT review style, logic correctness, or structure.

Supports: bash (built-in). Other languages generated on demand via prompt_generator_agent.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL, load_cache
from core.prompt_generator_agent import get_reviewer_prompt, get_fixer_prompt

# ── Built-in prompts for common languages ────────────────────────────────────

BASH_SECURITY_REVIEWER = """You are a bash security auditor.

Review the given bash script for security vulnerabilities ONLY. Look for:
- Unquoted variables in command positions (word splitting / glob injection)
- Use of eval with any non-literal input
- Missing ${VAR:?} or ${VAR:-default} guards on variables used in destructive commands
- Insecure temp file creation (using $$ PID instead of mktemp)
- Hardcoded credentials, tokens, or secrets in variable assignments
- curl | bash or wget | sh patterns
- rm -rf with unvalidated variable expansion
- Missing input validation on script arguments ($1, $2, etc.)
- World-writable files or directories created by the script
- Privilege escalation via sudo without explicit command restriction

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "critical|high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

BASH_SECURITY_FIXER = """You are a bash security fixer.

Fix ONLY the security issues provided. Rules:
- Be surgical — change the minimum code necessary to fix each issue
- Do NOT refactor, reorder, restyle, or fix non-security issues
- Do NOT add features or change logic
- After fixing, the script must behave identically for all valid inputs

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed bash script — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

PYTHON_SECURITY_REVIEWER = """You are a Python security auditor.

Review the given Python code for security vulnerabilities ONLY. Look for:
- SQL queries built with string formatting or concatenation
- Use of eval() or exec() with any non-literal input
- pickle.loads() on untrusted data
- subprocess calls with shell=True and variable input
- yaml.load() without Loader=yaml.SafeLoader
- Hardcoded secrets, API keys, or passwords
- Path traversal via unsanitized user input in file operations
- Missing authentication/authorization checks on sensitive functions
- use of assert for security checks (stripped in optimized mode)
- XML parsing without defusedxml (XXE vulnerability)
- Insecure random (random module) used for security purposes

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "critical|high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

PYTHON_SECURITY_FIXER = """You are a Python security fixer.

Fix ONLY the security issues provided. Rules:
- Use parameterized queries, not string formatting
- Replace dangerous functions with safe alternatives
- Do NOT change logic, style, or non-security code

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed Python code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

JAVASCRIPT_SECURITY_REVIEWER = """You are a JavaScript/Node.js security auditor.

Review the given code for security vulnerabilities ONLY. Look for:
- innerHTML, document.write, or insertAdjacentHTML with unsanitized input (XSS)
- eval() or new Function() with dynamic strings
- Prototype pollution (merging untrusted objects into base objects)
- Hardcoded secrets or API keys in client-side code
- Missing Content Security Policy meta tags in HTML
- Direct use of req.query/req.body in SQL or shell commands (injection)
- path.join with unvalidated user input (path traversal)
- JWT verification skipped or using 'none' algorithm
- Regex patterns vulnerable to ReDoS (catastrophic backtracking)
- Insecure deserialization of untrusted JSON with reviver functions

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "critical|high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

JAVASCRIPT_SECURITY_FIXER = """You are a JavaScript security fixer.

Fix ONLY the security issues provided. Do NOT change logic, style, or structure.
Use textContent instead of innerHTML where safe. Use parameterized queries.

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

BUILT_IN_REVIEWERS = {
    "bash":       BASH_SECURITY_REVIEWER,
    "sh":         BASH_SECURITY_REVIEWER,
    "python":     PYTHON_SECURITY_REVIEWER,
    "py":         PYTHON_SECURITY_REVIEWER,
    "javascript": JAVASCRIPT_SECURITY_REVIEWER,
    "js":         JAVASCRIPT_SECURITY_REVIEWER,
    "typescript": JAVASCRIPT_SECURITY_REVIEWER,
    "ts":         JAVASCRIPT_SECURITY_REVIEWER,
}

BUILT_IN_FIXERS = {
    "bash":       BASH_SECURITY_FIXER,
    "sh":         BASH_SECURITY_FIXER,
    "python":     PYTHON_SECURITY_FIXER,
    "py":         PYTHON_SECURITY_FIXER,
    "javascript": JAVASCRIPT_SECURITY_FIXER,
    "js":         JAVASCRIPT_SECURITY_FIXER,
    "typescript": JAVASCRIPT_SECURITY_FIXER,
    "ts":         JAVASCRIPT_SECURITY_FIXER,
}


def _get_language(file_path: str) -> str:
    return Path(file_path).suffix.lstrip(".").lower()


def review(code: str, language: str) -> dict:
    lang = language.lower()
    prompt = BUILT_IN_REVIEWERS.get(lang)
    if not prompt:
        cache = load_cache()
        prompt = get_reviewer_prompt(lang, "security", cache)
    return run_agent(prompt, f"Review this {language} code:\n\n{code}", max_tokens=2048)


def fix(code: str, language: str, issues: list) -> dict:
    lang = language.lower()
    prompt = BUILT_IN_FIXERS.get(lang)
    if not prompt:
        cache = load_cache()
        prompt = get_fixer_prompt(lang, "security", cache)
    user_input = (
        f"Fix these security issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this {language} code:\n{code}"
    )
    return run_agent(prompt, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python code_security_agent.py <file> [--fix] [--language <lang>]")
        sys.exit(1)

    file_path = sys.argv[1]
    code = Path(file_path).read_text()
    language = sys.argv[sys.argv.index("--language") + 1] if "--language" in sys.argv else _get_language(file_path)

    result = review(code, language)
    issues = result.get("issues", [])

    print(f"\n🔒 Security Review ({language}): {len(issues)} issues found")
    for i in issues:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        line = f" line {i['line']}" if i.get("line") else ""
        print(f"  {icon}{line}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying security fixes...")
        fixed = fix(code, language, issues)
        out = Path(file_path).with_stem(Path(file_path).stem + "_sec_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
