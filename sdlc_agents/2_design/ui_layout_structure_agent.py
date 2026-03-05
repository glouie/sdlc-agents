"""
ui_layout_structure_agent.py — SDLC Phase 2: Design
Reviews UI code for layout, structure, and information architecture issues.

Scope: spacing scale, grid, visual hierarchy, Gestalt grouping, navigation.
Does NOT review colors, typography values, or accessibility attributes.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL

LAYOUT_REVIEWER_PROMPT = """You are a UI layout and information architecture specialist.

Review the given UI code for layout and structural issues ONLY. Look for:
- Inconsistent spacing (values not from a spacing scale like 4/8/16/24/32px)
- Elements not aligned to an underlying grid
- Visual hierarchy not matching content priority (primary action not dominant)
- Too many competing focal points on a single view
- Related items not visually grouped (violates Gestalt proximity principle)
- Navigation pattern inconsistent with platform conventions
- Content area too wide for comfortable reading (above ~800px without max-width)
- Z-index conflicts causing unintended layering
- Responsive breakpoints creating content reflow or overlap issues
- Sidebar or panel widths not adapting to content length
- Modals or overlays not centered or properly layered
- Inconsistent card or component border-radius within the same view

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "high|medium|low",
      "element": "<element or section>",
      "issue": "<description>",
      "fix": "<specific fix>"
    }
  ]
}
If no issues, output: {"issues": []}"""

LAYOUT_FIXER_PROMPT = """You are a UI layout fixer.

Fix ONLY the layout and structure issues provided. Do NOT change:
- Colors or typography values
- Accessibility structure (ARIA, labels, focus order)
- Component logic or event handlers
- Content/copy

You MAY:
- Adjust margin, padding, gap, grid-template values
- Add or fix max-width constraints
- Fix z-index values
- Add responsive breakpoint rules
- Reorder elements in the DOM to match visual hierarchy

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""


def review(ui_code: str) -> dict:
    return run_agent(LAYOUT_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    user_input = (
        f"Fix these layout issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(LAYOUT_FIXER_PROMPT, user_input, max_tokens=8192)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_layout_structure_agent.py <file> [--fix]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()
    result = review(code)
    issues = result.get("issues", [])

    print(f"\n📐 Layout/Structure Review: {len(issues)} issues found")
    for i in issues:
        icon = {"high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        print(f"  {icon} {i['element']}: {i['issue']}")
        print(f"     Fix: {i['fix']}")

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying fixes...")
        fixed = fix(code, issues)
        out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_layout_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")
