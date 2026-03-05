"""
code_structure_agent.py — SDLC Phase 3: Development
Reviews code for structural organization and project conformance.

Two agents in one file — they're closely related and often used together:
  - Structural Agent: universal good organization (SRP, separation of concerns)
  - Conformance Agent: adherence to YOUR team's specific conventions

Separate fixer prompts for each — structural fixes reorganize,
conformance fixes apply your specific rules.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL, SMART_MODEL, load_cache
from core.prompt_generator_agent import get_reviewer_prompt, get_fixer_prompt

# ── Structural Agent ──────────────────────────────────────────────────────────

STRUCTURAL_REVIEWER = """You are a code structure and organization reviewer.

Review the given code for structural and organizational issues ONLY. Look for:
- Functions defined after they are first called
- Unrelated functionality grouped in the same function or block
- Functions doing more than one thing (violates Single Responsibility)
- Missing logical separation (e.g., setup, execution, teardown, helpers)
- Global state that should be scoped or encapsulated
- Dead code or unreachable blocks
- Deeply nested code that should be extracted into helper functions
- Entry point not clearly defined or placed at wrong location
- Circular dependencies between modules or sections
- Constants or configuration embedded inline rather than grouped at top

Do NOT flag style, security, or correctness issues.

Output ONLY valid JSON:
{
  "issues": [
    {"severity": "high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<specific fix>"}
  ]
}
If no issues, output: {"issues": []}"""

STRUCTURAL_FIXER = """You are a code structure fixer.

Reorganize ONLY based on the structural issues provided. Rules:
- The code must be FUNCTIONALLY IDENTICAL after your changes
- You may: move, reorder, rename for clarity, extract helpers, remove dead code
- Do NOT change logic, variable values, security patterns, or style
- Do NOT add new functionality

Output ONLY valid JSON:
{
  "fixed_code": "<complete reorganized code — never truncate>",
  "changes": [{"description": "<what you moved/extracted/reorganized and why>"}]
}"""

# ── Conformance Agent ─────────────────────────────────────────────────────────

CONFORMANCE_REVIEWER = """You are a code conformance reviewer.

Review the given code for violations of the provided team conventions ONLY.

Check strictly for:
- Naming convention violations specified in the conventions
- Missing required file headers, footers, or boilerplate
- Absent mandatory error handling patterns
- Missing required logging or tracing calls
- Forbidden patterns or constructs explicitly listed
- Required structural patterns not present (e.g., must have main(), must have usage())
- Any other rules explicitly stated in the conventions document

Do NOT apply general style rules not in the conventions.
Do NOT flag structural or security issues.

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "high|medium|low",
      "convention_rule": "<which rule was violated>",
      "line": <int or null>,
      "issue": "<description>",
      "fix": "<specific fix aligned to the convention>"
    }
  ]
}
If no issues, output: {"issues": []}"""

CONFORMANCE_FIXER = """You are a code conformance fixer.

Apply ONLY fixes for the convention violations provided. Rules:
- Apply the stated convention precisely as written — do not interpret or extend
- Do NOT fix style, structure, or security issues not covered by the conventions
- Do NOT change logic or behavior

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<which convention was applied and how>"}]
}"""


# ── Runner functions ──────────────────────────────────────────────────────────

def review_structure(code: str) -> dict:
    return run_agent(STRUCTURAL_REVIEWER, f"Review this code:\n\n{code}", max_tokens=2048)


def fix_structure(code: str, issues: list) -> dict:
    user_input = f"Fix these structural issues:\n{json.dumps(issues, indent=2)}\n\nIn this code:\n{code}"
    return run_agent(STRUCTURAL_FIXER, user_input, max_tokens=8192, model=SMART_MODEL)


def review_conformance(code: str, conventions: str) -> dict:
    user_input = f"Team conventions:\n{conventions}\n\nCode to review:\n{code}"
    return run_agent(CONFORMANCE_REVIEWER, user_input, max_tokens=2048)


def fix_conformance(code: str, issues: list, conventions: str) -> dict:
    user_input = (
        f"Team conventions for reference:\n{conventions}\n\n"
        f"Fix these conformance violations:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{code}"
    )
    return run_agent(CONFORMANCE_FIXER, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Usage:
      python code_structure_agent.py <file> --mode structure [--fix]
      python code_structure_agent.py <file> --mode conformance --conventions CONVENTIONS.md [--fix]
    """
    if len(sys.argv) < 2:
        print("Usage: python code_structure_agent.py <file> --mode <structure|conformance> [--fix] [--conventions <file>]")
        sys.exit(1)

    file_path = sys.argv[1]
    code = Path(file_path).read_text()
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "structure"

    if mode == "conformance":
        if "--conventions" not in sys.argv:
            print("Error: --conventions <file> required for conformance mode")
            sys.exit(1)
        conventions_path = sys.argv[sys.argv.index("--conventions") + 1]
        conventions = Path(conventions_path).read_text()

        result = review_conformance(code, conventions)
        issues = result.get("issues", [])
        print(f"\n📏 Conformance Review: {len(issues)} violations found")
        for i in issues:
            icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
            print(f"  {icon} [{i.get('convention_rule', '?')}] line {i.get('line', '?')}: {i['issue']}")
            print(f"     Fix: {i['fix']}")

        if "--fix" in sys.argv and issues:
            fixed = fix_conformance(code, issues, conventions)
            out = Path(file_path).with_stem(Path(file_path).stem + "_conform_fixed")
            out.write_text(fixed["fixed_code"])
            print(f"\n✅ Fixed file written to: {out}")

    else:  # structure
        result = review_structure(code)
        issues = result.get("issues", [])
        print(f"\n🏗️  Structure Review: {len(issues)} issues found")
        for i in issues:
            icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
            line = f" line {i['line']}" if i.get("line") else ""
            print(f"  {icon}{line}: {i['issue']}")
            print(f"     Fix: {i['fix']}")

        if "--fix" in sys.argv and issues:
            fixed = fix_structure(code, issues)
            out = Path(file_path).with_stem(Path(file_path).stem + "_struct_fixed")
            out.write_text(fixed["fixed_code"])
            print(f"\n✅ Fixed file written to: {out}")
