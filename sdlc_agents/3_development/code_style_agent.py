"""
code_style_agent.py — SDLC Phase 3: Development
Reviews code for style, formatting, and best practice violations.

Scope: naming, formatting, idioms, documentation, code smell.
Does NOT review security, logic correctness, or structure/organization.

Supports: bash, python, javascript built-in. Others generated on demand.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL, load_cache
from core.prompt_generator_agent import get_reviewer_prompt, get_fixer_prompt

BASH_STYLE_REVIEWER = """You are a bash style and best-practices reviewer.

Review the given bash script for style and best-practice issues ONLY. Look for:
- Missing shebang (#!/usr/bin/env bash) or wrong shebang
- Missing set -euo pipefail at top of script
- Unquoted variable expansions (use "$var" not $var)
- Backtick command substitution instead of $()
- [ ] instead of [[ ]] for conditionals
- Functions missing local declarations for all local variables
- Variable names not in snake_case; constants not in UPPER_SNAKE_CASE
- Missing comments on non-obvious logic
- echo used for error messages instead of >&2 redirection
- Comparing numbers with string operators (-eq vs ==)
- Using cd without checking success or using pushd/popd

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

BASH_STYLE_FIXER = """You are a bash style fixer.

Fix ONLY the style issues provided. Rules:
- Do NOT change logic, behavior, or security-related code
- You may make broad changes across the whole file (style is safe to fix at scale)
- Maintain all existing functionality exactly

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed bash script — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

PYTHON_STYLE_REVIEWER = """You are a Python style reviewer (PEP 8 and Pythonic idioms).

Review the given Python code for style issues ONLY. Look for:
- Lines exceeding 88 characters (Black default)
- Missing or incomplete docstrings on public functions/classes/modules
- Non-Pythonic patterns (manual index loops instead of enumerate, range(len()))
- Mutable default arguments (def func(x=[]) is a bug waiting to happen)
- Bare except clauses (except: instead of except Exception:)
- f-strings not used where they would be clearer than % or .format()
- Type hints missing on public function signatures
- Inconsistent naming (not following snake_case / PascalCase / UPPER_SNAKE_CASE conventions)
- Import ordering violations (stdlib, third-party, local — separated by blank line)
- Unnecessary list comprehension where generator suffices

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

PYTHON_STYLE_FIXER = """You are a Python style fixer.

Fix ONLY the style issues provided. Do NOT change logic, security, or structure.
You may make broad changes across the whole file.

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed Python code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

JAVASCRIPT_STYLE_REVIEWER = """You are a JavaScript/TypeScript style reviewer.

Review the given code for style issues ONLY. Look for:
- var usage instead of const/let
- == instead of === for comparisons
- Callback-based async where async/await would be cleaner
- Missing semicolons (or inconsistent use)
- Arrow functions inconsistently used vs function declarations
- console.log statements left in non-debug code
- Deeply nested callbacks or promise chains (callback hell)
- Non-descriptive variable names (x, data, temp, obj)
- Magic numbers without named constants
- Missing JSDoc comments on exported functions

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

JAVASCRIPT_STYLE_FIXER = """You are a JavaScript style fixer.

Fix ONLY the style issues provided. Do NOT change logic or security code.

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

BUILT_IN_REVIEWERS = {
    "bash": BASH_STYLE_REVIEWER, "sh": BASH_STYLE_REVIEWER,
    "python": PYTHON_STYLE_REVIEWER, "py": PYTHON_STYLE_REVIEWER,
    "javascript": JAVASCRIPT_STYLE_REVIEWER, "js": JAVASCRIPT_STYLE_REVIEWER,
    "typescript": JAVASCRIPT_STYLE_REVIEWER, "ts": JAVASCRIPT_STYLE_REVIEWER,
}

BUILT_IN_FIXERS = {
    "bash": BASH_STYLE_FIXER, "sh": BASH_STYLE_FIXER,
    "python": PYTHON_STYLE_FIXER, "py": PYTHON_STYLE_FIXER,
    "javascript": JAVASCRIPT_STYLE_FIXER, "js": JAVASCRIPT_STYLE_FIXER,
    "typescript": JAVASCRIPT_STYLE_FIXER, "ts": JAVASCRIPT_STYLE_FIXER,
}


def _get_language(file_path: str) -> str:
    return Path(file_path).suffix.lstrip(".").lower()


def review(code: str, language: str) -> dict:
    lang = language.lower()
    prompt = BUILT_IN_REVIEWERS.get(lang)
    if not prompt:
        cache = load_cache()
        prompt = get_reviewer_prompt(lang, "style", cache)
    return run_agent(prompt, f"Review this {language} code:\n\n{code}", max_tokens=2048)


def fix(code: str, language: str, issues: list) -> dict:
    lang = language.lower()
    prompt = BUILT_IN_FIXERS.get(lang)
    if not prompt:
        cache = load_cache()
        prompt = get_fixer_prompt(lang, "style", cache)
    user_input = f"Fix these style issues:\n{json.dumps(issues, indent=2)}\n\nIn this {language} code:\n{code}"
    return run_agent(prompt, user_input, max_tokens=8192)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python code_style_agent.py <file> [--fix] [--language <lang>]")
        sys.exit(1)

    file_path = sys.argv[1]
    code = Path(file_path).read_text()
    language = sys.argv[sys.argv.index("--language") + 1] if "--language" in sys.argv else _get_language(file_path)

    result = review(code, language)
    issues = result.get("issues", [])

    print(f"\n🎨 Style Review ({language}): {len(issues)} issues found")
    for i in issues:
        icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        line = f" line {i['line']}" if i.get("line") else ""
        print(f"  {icon}{line}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        fixed = fix(code, language, issues)
        out = Path(file_path).with_stem(Path(file_path).stem + "_style_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"\n✅ Fixed file written to: {out}")
