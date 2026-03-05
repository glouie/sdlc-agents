"""
ui_keyboard_desktop_agent.py — SDLC Phase 2: Design
Reviews UI code for desktop keyboard and interaction issues.

Scope: keyboard shortcuts, focus management, hover states, menus.
Does NOT review mobile/touch, colors, or typography.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL

KEYBOARD_REVIEWER_PROMPT = """You are a desktop UI and keyboard interaction specialist.

Review the given UI code for desktop and keyboard interaction issues ONLY. Look for:
- Missing keyboard shortcuts for primary/frequent actions
- No visible focus indicator on focused interactive elements
- Modal dialogs that don't trap focus within the modal
- Dropdown menus not navigable with arrow keys
- Missing Escape key handler to dismiss overlays, modals, drawers
- Icon-only buttons with no tooltip or aria-label
- Right-click context menus absent where users would expect them
- Keyboard shortcut hints missing from tooltips and menus
- Drag-and-drop with no keyboard-accessible alternative
- Hover-only interactions with no keyboard equivalent
- Tab order inconsistent with visual left-to-right, top-to-bottom layout
- Lists or data grids missing Home/End key support
- Missing Ctrl+Z undo support in editable areas

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

KEYBOARD_FIXER_PROMPT = """You are a desktop keyboard interaction fixer.

Fix ONLY the keyboard/desktop interaction issues provided. Do NOT change:
- Visual appearance, colors, or layout
- Mobile/touch-specific code
- Accessibility structure beyond keyboard handling
- Business logic

You MAY:
- Add keyboard event listeners (keydown, keyup)
- Add/fix tabIndex values
- Add tooltip content for icon-only buttons
- Add focus trap logic inside modals
- Add aria-keyshortcuts attributes

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""


def review(ui_code: str) -> dict:
    return run_agent(KEYBOARD_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    user_input = (
        f"Fix these keyboard/desktop issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(KEYBOARD_FIXER_PROMPT, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_keyboard_desktop_agent.py <file> [--fix]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()
    result = review(code)
    issues = result.get("issues", [])

    print(f"\n⌨️  Keyboard/Desktop Review: {len(issues)} issues found")
    for i in issues:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        print(f"  {icon} {i['element']}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying fixes...")
        fixed = fix(code, issues)
        out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_kbd_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
