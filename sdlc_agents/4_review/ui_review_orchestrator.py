"""
ui_review_orchestrator.py — SDLC Phase 4: Review
Orchestrates all UI/UX review subagents for a given UI file.
Auto-detects platform (mobile/desktop/web) and runs appropriate agents.

Usage:
  python ui_review_orchestrator.py <file> [--fix] [--auto] [--platform mobile|desktop|web]
"""

import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL
from core.merger_agent import merge

sys.path.insert(0, str(Path(__file__).parent.parent / "2_design"))
from ui_accessibility_agent  import review as review_a11y,    fix as fix_a11y
from ui_color_contrast_agent import review as review_color,   fix as fix_color
from ui_typography_agent     import review as review_typo,    fix as fix_typo
from ui_mobile_touch_agent   import review as review_mobile,  fix as fix_mobile
from ui_keyboard_desktop_agent import review as review_kbd,   fix as fix_kbd
from ui_visual_feedback_agent  import review as review_ux,    fix as fix_ux
from ui_layout_structure_agent import review as review_layout, fix as fix_layout

PLATFORM_DETECTOR_PROMPT = """You are a UI platform detector.
Given UI code, identify the target platform and framework.
Output ONLY valid JSON:
{
  "platform": "mobile|desktop|web",
  "framework": "react|vue|angular|html|swiftui|flutter|android|wpf|unknown",
  "confidence": "high|medium|low"
}"""

AGGREGATOR_PROMPT = """You are a UI/UX review report writer.

Given JSON findings from multiple specialized UI reviewers, write a concise,
actionable report in markdown.

Format:
1. One-line summary
2. Issues by severity: Critical → High → Medium → Low
   Each: severity | domain | element | problem | fix
3. "Quick Wins" — low-effort, high-impact fixes
4. "Top Accessibility Concerns" if any critical/high a11y issues

Be specific and actionable."""

# Agents per platform
PLATFORM_AGENTS = {
    "mobile": ["accessibility", "color", "typography", "mobile", "visual_feedback", "layout"],
    "desktop": ["accessibility", "color", "typography", "keyboard", "visual_feedback", "layout"],
    "web": ["accessibility", "color", "typography", "mobile", "keyboard", "visual_feedback", "layout"],
}

REVIEWERS = {
    "accessibility":  review_a11y,
    "color":          review_color,
    "typography":     review_typo,
    "mobile":         review_mobile,
    "keyboard":       review_kbd,
    "visual_feedback": review_ux,
    "layout":         review_layout,
}

FIXERS = {
    "color":          fix_color,
    "typography":     fix_typo,
    "layout":         fix_layout,
    "mobile":         fix_mobile,
    "keyboard":       fix_kbd,
    "visual_feedback": fix_ux,
    "accessibility":  fix_a11y,  # last — touches DOM structure
}

# Fix order: colors first, accessibility last
FIX_ORDER = ["color", "typography", "layout", "mobile", "keyboard", "visual_feedback", "accessibility"]


def detect_platform(code: str) -> dict:
    sample = "\n".join(code.splitlines()[:80])
    return run_agent(PLATFORM_DETECTOR_PROMPT, sample, max_tokens=128)


def aggregate_report(findings: dict) -> str:
    return run_agent(
        AGGREGATOR_PROMPT,
        f"UI Review Findings:\n{json.dumps(findings, indent=2)}",
        max_tokens=3000,
        model=SMART_MODEL,
        expect_json=False,
    )


def review_ui_file(file_path: str, platform: str | None = None) -> tuple[dict, str, str]:
    code = Path(file_path).read_text()

    if not platform:
        print("🔎 Detecting platform...")
        detection = detect_platform(code)
        platform = detection.get("platform", "web")
        framework = detection.get("framework", "unknown")
        print(f"   → {platform} / {framework}")
    else:
        print(f"   → Platform: {platform} (specified)")

    agent_names = PLATFORM_AGENTS.get(platform, PLATFORM_AGENTS["web"])
    print(f"🔍 Running {len(agent_names)} reviewers in parallel...")

    def run_reviewer(name):
        return name, REVIEWERS[name](code)

    with ThreadPoolExecutor(max_workers=len(agent_names)) as ex:
        results = dict(ex.map(run_reviewer, agent_names))

    findings = {name: data.get("issues", []) for name, data in results.items()}
    total = sum(len(v) for v in findings.values())
    print(f"📊 Found {total} total issues.\n")

    return findings, platform, code


def fix_ui_file(code: str, findings: dict) -> str:
    fixed_versions = {}

    for domain in FIX_ORDER:
        if findings.get(domain):
            print(f"  🔧 Fixing {domain} issues...")
            result = FIXERS[domain](code, findings[domain])
            fixed_versions[domain] = result.get("fixed_code", code)

    if not fixed_versions:
        return code

    if len(fixed_versions) == 1:
        return list(fixed_versions.values())[0]

    print("  🔀 Merging all fixes...")
    merged = merge(code, fixed_versions)
    return merged.get("final_code", code)


def print_findings(findings: dict):
    severity_order = ["critical", "high", "medium", "low"]
    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    all_issues = []
    for domain, issues in findings.items():
        for issue in issues:
            all_issues.append({**issue, "domain": domain})

    all_issues.sort(key=lambda x: severity_order.index(x.get("severity", "low")))

    for i in all_issues:
        icon = icons.get(i.get("severity", "low"), "⚪")
        element = i.get("element", "?")
        print(f"  {icon} [{i['domain'].upper()}] {element}: {i['issue']}")
        print(f"     → {i['fix']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ui_review_orchestrator.py <file> [--fix] [--auto] [--platform mobile|desktop|web]")
        sys.exit(1)

    file_path = sys.argv[1]
    auto_fix = "--auto" in sys.argv
    do_fix = "--fix" in sys.argv or auto_fix
    platform = sys.argv[sys.argv.index("--platform") + 1] if "--platform" in sys.argv else None

    print(f"\n{'='*60}")
    print(f"UI/UX REVIEW: {file_path}")
    print(f"{'='*60}\n")

    findings, platform, code = review_ui_file(file_path, platform)

    total = sum(len(v) for v in findings.values())
    if total == 0:
        print("✅ No UI issues found!")
        sys.exit(0)

    print_findings(findings)
    print("\n" + "─" * 60)
    report = aggregate_report(findings)
    print(report)

    if do_fix:
        if not auto_fix:
            answer = input("\n⚡ Apply all fixes? (y/n): ").strip().lower()
            if answer != "y":
                sys.exit(0)

        print("\n── APPLYING FIXES ──────────────────────────────────────")
        fixed_code = fix_ui_file(code, findings)
        out_path = Path(file_path).with_stem(Path(file_path).stem + "_ui_reviewed")
        out_path.write_text(fixed_code)
        print(f"\n✅ Final fixed file: {out_path}")

    findings_path = Path(file_path).with_suffix(".ui_review.json")
    findings_path.write_text(json.dumps(findings, indent=2))
    print(f"📄 Findings saved to: {findings_path}")
