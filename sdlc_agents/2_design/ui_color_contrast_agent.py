"""
ui_color_contrast_agent.py — SDLC Phase 2: Design
Reviews UI code for color, contrast, and color system issues.

Scope: contrast ratios, color blindness, dark mode, design tokens.
Does NOT review layout, typography, or accessibility structure.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, FAST_MODEL, SMART_MODEL

COLOR_REVIEWER_PROMPT = """You are a UI color and contrast specialist.

Review the given UI code for color issues ONLY. Look for:
- Text/background contrast below WCAG AA (4.5:1 normal, 3:1 large text)
- Color combinations problematic for color blindness (red/green, blue/yellow)
- Insufficient contrast on interactive states (hover, focus, active, disabled)
- Placeholder text contrast (often below 4.5:1)
- Color as the only differentiator between states or data series
- Missing or broken dark mode support
- Hardcoded hex/rgb values that should be CSS variables or design tokens
- Inconsistent color usage for the same semantic meaning across the UI
- Insufficient contrast for icon-only buttons

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "element": "<element>",
      "current_colors": {"foreground": "<hex or null>", "background": "<hex or null>", "ratio": "<x:1 or null>"},
      "issue": "<description>",
      "fix": "<specific fix with suggested accessible color values>"
    }
  ]
}
If no issues, output: {"issues": []}"""

COLOR_FIXER_PROMPT = """You are a UI color fixer.

Fix ONLY the color and contrast issues provided. Do NOT change:
- Layout, spacing, or structure
- Typography sizes or families
- Component logic or behavior
- Non-color visual properties

You MAY:
- Replace hex/rgb color values with accessible alternatives
- Add or fix CSS custom properties / design tokens
- Add dark mode variants where missing

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"line": <int or null>, "description": "<what changed and why>"}]
}"""

COLOR_SYSTEM_PROMPT = """You are a UI color system designer.

Given UI code with color issues, generate a complete, accessible color system.

Produce:
- Primary, secondary, and neutral palettes with 5-9 shades each
- Semantic tokens: error, warning, success, info (light + dark mode)
- All text/background combinations verified to meet WCAG AA contrast
- Ready-to-use CSS custom properties

Output ONLY valid JSON:
{
  "tokens": {
    "primary":   {"50": "#...", "100": "#...", "300": "#...", "500": "#...", "700": "#...", "900": "#..."},
    "neutral":   {"50": "#...", "100": "#...", "300": "#...", "500": "#...", "700": "#...", "900": "#..."},
    "semantic": {
      "error":   {"light": "#...", "dark": "#..."},
      "warning": {"light": "#...", "dark": "#..."},
      "success": {"light": "#...", "dark": "#..."},
      "info":    {"light": "#...", "dark": "#..."}
    }
  },
  "css_variables": "<:root { --primary-500: #...; } block ready to paste>",
  "replacements": [
    {"find": "<old color>", "replace_with": "var(--token-name)", "reason": "<why>"}
  ]
}"""


def review(ui_code: str) -> dict:
    return run_agent(COLOR_REVIEWER_PROMPT, f"Review this UI code:\n\n{ui_code}", max_tokens=2048)


def fix(ui_code: str, issues: list) -> dict:
    user_input = (
        f"Fix these color issues:\n{json.dumps(issues, indent=2)}\n\n"
        f"In this code:\n{ui_code}"
    )
    return run_agent(COLOR_FIXER_PROMPT, user_input, max_tokens=8192)


def generate_color_system(ui_code: str) -> dict:
    """Generate a complete design token color system for the given UI."""
    return run_agent(COLOR_SYSTEM_PROMPT, f"Generate a color system for:\n\n{ui_code}", max_tokens=3000, model=SMART_MODEL)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_color_contrast_agent.py <file> [--fix] [--generate-system]")
        sys.exit(1)

    code = Path(sys.argv[1]).read_text()

    if "--generate-system" in sys.argv:
        print("🎨 Generating color system...")
        system = generate_color_system(code)
        print("\n" + system.get("css_variables", ""))
        Path("color_system.json").write_text(json.dumps(system, indent=2))
        print("\n📄 Full system saved to color_system.json")
    else:
        result = review(code)
        issues = result.get("issues", [])
        print(f"\n🎨 Color Review: {len(issues)} issues found")
        for i in issues:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
            print(f"  {icon} {i['element']}: {i['issue']}")
            print(f"     Fix: {i['fix']}")

        if "--fix" in sys.argv and issues:
            print("\n🔧 Applying fixes...")
            fixed = fix(code, issues)
            out = Path(sys.argv[1]).with_stem(Path(sys.argv[1]).stem + "_color_fixed")
            out.write_text(fixed["fixed_code"])
            print(f"✅ Fixed file written to: {out}")
