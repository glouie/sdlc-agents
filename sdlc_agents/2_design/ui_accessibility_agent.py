"""
ui_accessibility_agent.py — SDLC Phase 2: Design
Reviews UI code for WCAG 2.1 accessibility compliance.

Scope: ARIA, keyboard, screen readers, focus, contrast semantics.
Does NOT review visual aesthetics, layout, or color values.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL

ACCESSIBILITY_REVIEWER_PROMPT = """You are a UI accessibility auditor specializing in WCAG 2.1 AA compliance.

Review the given UI code for accessibility issues ONLY. Look for:
- Missing or incorrect ARIA labels, roles, and landmarks
- Images missing alt text; decorative images not marked aria-hidden
- Form inputs missing associated <label> elements
- Focus indicators removed or visually insufficient
- Tab order that doesn't follow visual/logical reading flow
- Interactive elements unreachable by keyboard alone
- Error messages not announced to screen readers
- Color as the ONLY means of conveying information
- Missing skip-navigation links on pages with repeated nav
- Touch targets smaller than 44x44px
- Auto-playing media without user controls
- Flashing content faster than 3 Hz

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "wcag": "<criterion e.g. 1.4.3>",
      "element": "<element or component name>",
      "issue": "<clear description>",
      "fix": "<specific, actionable fix>"
    }
  ]
}
If no issues, output: {"issues": []}"""

ACCESSIBILITY_FIXER_PROMPT = """You are a UI accessibility fixer.

Fix ONLY the accessibility issues provided. Do NOT change:
- Visual styles or colors
- Layout or spacing
- Logic or behavior visible to sighted users

You MAY:
- Add/modify ARIA attributes
- Add <label> elements
- Fix tab index values
- Add skip links
- Add keyboard event handlers

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""


def review(ui_code: str) -> dict:
    return run_agent(ACCESSIBILITY_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    import json
    user_input = (
        f"Fix these accessibility issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(ACCESSIBILITY_FIXER_PROMPT, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("Usage: python ui_accessibility_agent.py <file> [--fix]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()
    result = review(code)
    issues = result.get("issues", [])

    print(f"\n♿ Accessibility Review: {len(issues)} issues found")
    for i in issues:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        print(f"  {icon} [{i.get('wcag', '?')}] {i['element']}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying fixes...")
        fixed = fix(code, issues)
        out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_a11y_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
