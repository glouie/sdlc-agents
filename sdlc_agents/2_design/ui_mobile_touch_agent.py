"""
ui_mobile_touch_agent.py — SDLC Phase 2: Design
Reviews UI code for mobile and touch interaction issues.

Scope: touch targets, gestures, safe areas, mobile inputs, responsive.
Does NOT review desktop keyboard, colors, or typography.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL

MOBILE_REVIEWER_PROMPT = """You are a mobile and touch UI specialist.

Review the given UI code for mobile and touch interaction issues ONLY. Look for:
- Touch targets smaller than 44x44px (Apple HIG) or 48x48dp (Material)
- Interactive elements with less than 8px gap between them
- Missing touch/active state feedback (visual response on tap)
- Unintended horizontal scroll on main content
- Fixed-position elements obscuring critical content on small screens
- Missing safe area insets (env(safe-area-inset-*)) for notched devices
- Swipe gestures with no button-based alternative
- user-scalable=no or maximum-scale=1 blocking pinch-zoom
- Input fields missing type attribute (email, tel, number, search)
- Form fields missing autocomplete attributes
- Tap delay not eliminated (missing touch-action: manipulation)
- Content requiring two-handed interaction in primary flows
- Overflow content with no scrollable region (scroll trap)

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "element": "<element or component>",
      "issue": "<description>",
      "fix": "<specific fix>"
    }
  ]
}
If no issues, output: {"issues": []}"""

MOBILE_FIXER_PROMPT = """You are a mobile and touch UI fixer.

Fix ONLY the mobile/touch issues provided. Do NOT change:
- Desktop-specific layout or interactions
- Colors, typography, or visual design
- Accessibility structure (ARIA, labels)
- Business logic

You MAY:
- Increase touch target sizes (min-width/height, padding)
- Add touch-action CSS
- Add safe-area-inset CSS
- Add/fix input type and autocomplete attributes
- Add active/focus state CSS for touch feedback

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""


def review(ui_code: str) -> dict:
    return run_agent(MOBILE_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    user_input = (
        f"Fix these mobile/touch issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(MOBILE_FIXER_PROMPT, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_mobile_touch_agent.py <file> [--fix]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()
    result = review(code)
    issues = result.get("issues", [])

    print(f"\n📱 Mobile/Touch Review: {len(issues)} issues found")
    for i in issues:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        print(f"  {icon} {i['element']}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying fixes...")
        fixed = fix(code, issues)
        out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_mobile_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
