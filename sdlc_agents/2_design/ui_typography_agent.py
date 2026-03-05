"""
ui_typography_agent.py — SDLC Phase 2: Design
Reviews UI code for typography and readability issues.

Scope: font sizes, line height, line length, type scale, scaling.
Does NOT review colors, layout structure, or accessibility structure.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL

TYPOGRAPHY_REVIEWER_PROMPT = """You are a UI typography and readability specialist.

Review the given UI code for typography issues ONLY. Look for:
- Body font size below 16px (or 1rem) on mobile
- Line height below 1.4 or above 2.0 for body text
- Line length (measure) above 75ch or below 45ch for body text
- Using px instead of rem/em for font sizes (prevents user scaling)
- More than 2-3 distinct typefaces in one UI
- Missing font fallback stacks (web-safe or system font fallbacks)
- All-caps text used for body copy (impairs readability)
- Missing letter-spacing (tracking) on all-caps headings
- Justified text alignment causing rivers of whitespace
- Insufficient visual weight difference between heading levels
- Inconsistent type scale (not following a modular scale like 1.25x or 1.333x)
- Hardcoded font sizes that ignore user font size preferences

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "high|medium|low",
      "element": "<CSS selector or component>",
      "issue": "<description>",
      "fix": "<specific fix with values>"
    }
  ]
}
If no issues, output: {"issues": []}"""

TYPOGRAPHY_FIXER_PROMPT = """You are a UI typography fixer.

Fix ONLY the typography issues provided. Do NOT change:
- Colors or contrast
- Layout, spacing between components, or grid
- Component logic or interactivity
- Accessibility structure (ARIA, labels)

You MAY:
- Change font-size, line-height, letter-spacing, font-family values
- Replace px units with rem/em where appropriate
- Add or fix font fallback stacks
- Adjust text-align or text-transform

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""


def review(ui_code: str) -> dict:
    return run_agent(TYPOGRAPHY_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    user_input = (
        f"Fix these typography issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(TYPOGRAPHY_FIXER_PROMPT, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_typography_agent.py <file> [--fix]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()
    result = review(code)
    issues = result.get("issues", [])

    print(f"\n🔤 Typography Review: {len(issues)} issues found")
    for i in issues:
        icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        print(f"  {icon} {i['element']}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying fixes...")
        fixed = fix(code, issues)
        out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_type_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
