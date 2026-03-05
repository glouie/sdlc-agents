"""
ui_visual_feedback_agent.py — SDLC Phase 2: Design
Reviews UI code for visual feedback, affordances, and user-friendly cues.

Scope: loading states, error feedback, affordances, empty states, confirmations.
Does NOT review colors, typography, keyboard, or accessibility structure.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL

VISUAL_FEEDBACK_REVIEWER_PROMPT = """You are a UI visual feedback and affordance specialist.

Review the given UI code for visual feedback and user-friendly cue issues ONLY. Look for:
- Buttons or links that don't look interactive (missing cursor, hover state, affordance)
- Missing loading/spinner states on async operations
- No visible success or error feedback after form submission
- Destructive actions (delete, reset) with no confirmation step
- Empty states showing nothing — no guidance on next action
- Multi-step flows with no progress indicator
- Error messages that describe the problem but not how to fix it
- No visual distinction between read and unread notification items
- Truncated text with no tooltip showing full content
- Missing skeleton screens or placeholders during data load
- Required vs optional fields not visually distinguished
- Disabled states that look identical to enabled states

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "high|medium|low",
      "element": "<element or flow>",
      "issue": "<description>",
      "fix": "<specific fix>"
    }
  ]
}
If no issues, output: {"issues": []}"""

VISUAL_FEEDBACK_FIXER_PROMPT = """You are a UI visual feedback fixer.

Fix ONLY the visual feedback and affordance issues provided. Do NOT change:
- Colors or typography values
- Layout or spacing
- Accessibility structure (ARIA, focus)
- Core business logic

You MAY:
- Add loading spinner components or CSS animations
- Add success/error message display logic
- Add confirmation dialogs before destructive actions
- Add empty state components with helpful copy
- Add tooltips on truncated or icon-only elements
- Add CSS cursor, hover, and disabled state styles

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""


def review(ui_code: str) -> dict:
    return run_agent(VISUAL_FEEDBACK_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    user_input = (
        f"Fix these visual feedback issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(VISUAL_FEEDBACK_FIXER_PROMPT, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_visual_feedback_agent.py <file> [--fix]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()
    result = review(code)
    issues = result.get("issues", [])

    print(f"\n💬 Visual Feedback Review: {len(issues)} issues found")
    for i in issues:
        icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        print(f"  {icon} {i['element']}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying fixes...")
        fixed = fix(code, issues)
        out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_ux_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
