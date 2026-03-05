"""
code_logic_agent.py — SDLC Phase 3: Development
Reviews code for logic errors, edge cases, and correctness issues.

Scope: control flow, edge cases, exit codes, race conditions, scoping.
Does NOT review security, style, or code organization.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL, load_cache
from core.prompt_generator_agent import get_reviewer_prompt, get_fixer_prompt

BASH_LOGIC_REVIEWER = """You are a bash logic and correctness reviewer.

Review the given bash script for logic errors ONLY. Look for:
- Missing exit code checks after critical commands
- Race conditions (parallel operations sharing state without locking)
- Infinite loops with no guaranteed exit condition
- Incorrect conditional syntax or operator misuse (&& vs || vs ;)
- Variable scoping bugs (subshell variables not propagating to parent)
- Missing edge case handling: empty string input, missing files, zero-length arrays
- Incorrect use of arithmetic expressions (integer vs string context)
- Dependency on commands that may not exist (no which/command -v check)
- Scripts that proceed after a failed critical step
- Off-by-one errors in loop ranges or array indexing

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

BASH_LOGIC_FIXER = """You are a bash logic fixer.

Fix ONLY the logic issues provided. Rules:
- You are ALLOWED to change behavior — that is the purpose of logic fixes
- Reason carefully about what the code should do before changing it
- Do NOT change style, security patterns, or code structure/organization

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed bash script — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

PYTHON_LOGIC_REVIEWER = """You are a Python logic and correctness reviewer.

Review the given Python code for logic errors ONLY. Look for:
- Missing None checks before attribute access or method calls
- Off-by-one errors in slice or range operations
- Mutable default argument mutation (the classic Python gotcha)
- Catching exceptions too broadly and swallowing real errors
- Missing return value used by caller (function returns None implicitly)
- Incorrect handling of empty collections (iterating an empty list is fine; indexing is not)
- Floating point comparison with == instead of math.isclose()
- Missing close() or context manager for file/network/DB resources
- Modifying a list/dict while iterating over it
- Incorrect boolean logic (and/or precedence mistakes, double negations)

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

PYTHON_LOGIC_FIXER = """You are a Python logic fixer.

Fix ONLY the logic issues provided. You may change behavior. Do NOT touch style or security.

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed Python code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

JAVASCRIPT_LOGIC_REVIEWER = """You are a JavaScript/TypeScript logic reviewer.

Review the given code for logic errors ONLY. Look for:
- Async functions called without await (forgotten await)
- Promise rejections not caught (.catch() or try/catch missing)
- Off-by-one errors in array index or loop boundary
- Truthy/falsy pitfalls (0, "", null all falsy — may be valid values)
- Mutation of function arguments (objects passed by reference)
- Missing null/undefined checks before property access
- setState called in render or before component mounts (React)
- Race conditions in async operations sharing state
- Memory leaks (event listeners added but never removed)
- Incorrect this binding in callbacks

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

JAVASCRIPT_LOGIC_FIXER = """You are a JavaScript logic fixer.

Fix ONLY the logic issues provided. You may change behavior. Do NOT change style or security.

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

BUILT_IN_REVIEWERS = {
    "bash": BASH_LOGIC_REVIEWER, "sh": BASH_LOGIC_REVIEWER,
    "python": PYTHON_LOGIC_REVIEWER, "py": PYTHON_LOGIC_REVIEWER,
    "javascript": JAVASCRIPT_LOGIC_REVIEWER, "js": JAVASCRIPT_LOGIC_REVIEWER,
    "typescript": JAVASCRIPT_LOGIC_REVIEWER, "ts": JAVASCRIPT_LOGIC_REVIEWER,
}

BUILT_IN_FIXERS = {
    "bash": BASH_LOGIC_FIXER, "sh": BASH_LOGIC_FIXER,
    "python": PYTHON_LOGIC_FIXER, "py": PYTHON_LOGIC_FIXER,
    "javascript": JAVASCRIPT_LOGIC_FIXER, "js": JAVASCRIPT_LOGIC_FIXER,
    "typescript": JAVASCRIPT_LOGIC_FIXER, "ts": JAVASCRIPT_LOGIC_FIXER,
}


def _get_language(file_path: str) -> str:
    return Path(file_path).suffix.lstrip(".").lower()


def review(code: str, language: str) -> dict:
    lang = language.lower()
    prompt = BUILT_IN_REVIEWERS.get(lang)
    if not prompt:
        cache = load_cache()
        prompt = get_reviewer_prompt(lang, "logic", cache)
    return run_agent(prompt, f"Review this {language} code:\n\n{code}", max_tokens=2048)


def fix(code: str, language: str, issues: list) -> dict:
    lang = language.lower()
    prompt = BUILT_IN_FIXERS.get(lang)
    if not prompt:
        cache = load_cache()
        prompt = get_fixer_prompt(lang, "logic", cache)
    user_input = f"Fix these logic issues:\n{json.dumps(issues, indent=2)}\n\nIn this {language} code:\n{code}"
    return run_agent(prompt, user_input, max_tokens=8192)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python code_logic_agent.py <file> [--fix] [--language <lang>]")
        sys.exit(1)

    file_path = sys.argv[1]
    code = Path(file_path).read_text()
    language = sys.argv[sys.argv.index("--language") + 1] if "--language" in sys.argv else _get_language(file_path)

    result = review(code, language)
    issues = result.get("issues", [])

    print(f"\n🧠 Logic Review ({language}): {len(issues)} issues found")
    for i in issues:
        icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        line = f" line {i['line']}" if i.get("line") else ""
        print(f"  {icon}{line}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        fixed = fix(code, language, issues)
        out = Path(file_path).with_stem(Path(file_path).stem + "_logic_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"\n✅ Fixed file written to: {out}")
