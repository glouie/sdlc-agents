"""
code_review_orchestrator.py — SDLC Phase 4: Review
Orchestrates all code review subagents for a single file.
Runs reviewers in parallel, optionally runs fixers in sequence, merges results.

Usage:
  python code_review_orchestrator.py <file> [--fix] [--auto] [--conventions <file>]
"""

import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL
from core.merger_agent import merge

# Import review and fix functions from each subagent
sys.path.insert(0, str(Path(__file__).parent.parent / "3_development"))
from code_security_agent  import review as review_security,  fix as fix_security
from code_style_agent     import review as review_style,     fix as fix_style
from code_logic_agent     import review as review_logic,     fix as fix_logic
from code_structure_agent import review_structure, fix_structure

AGGREGATOR_PROMPT = """You are a code review report writer.

Given JSON findings from multiple specialized reviewers, write a concise, actionable code review report in markdown.

Format:
1. One-line summary at the top
2. Issues grouped by severity: Critical → High → Medium → Low
3. Each issue: severity badge | domain | what the problem is | suggested fix
4. Final "Top 3 Priorities" section — the most impactful things to fix first

Be direct, specific, and actionable. No padding."""

LANGUAGE_DETECTOR_PROMPT = """You are a programming language detector.
Given a code snippet (first 80 lines), identify the language.
Output ONLY valid JSON:
{"language": "bash|python|javascript|typescript|ruby|go|rust|java|kotlin|swift|unknown", "confidence": "high|medium|low"}"""


def detect_language(code: str) -> str:
    sample = "\n".join(code.splitlines()[:80])
    result = run_agent(LANGUAGE_DETECTOR_PROMPT, sample, max_tokens=64)
    return result.get("language", "unknown")


def aggregate_report(findings: dict) -> str:
    return run_agent(
        AGGREGATOR_PROMPT,
        f"Findings:\n{json.dumps(findings, indent=2)}",
        max_tokens=3000,
        model=SMART_MODEL,
        expect_json=False,
    )


def review_file(file_path: str, conventions: str | None = None) -> tuple[dict, str, str]:
    """Returns (findings, language, code)."""
    code = Path(file_path).read_text()

    print("🔎 Detecting language...")
    language = detect_language(code)
    print(f"   → {language}")

    print("🔍 Running reviewers in parallel...")

    def run_security():
        return "security", review_security(code, language)

    def run_style():
        return "style", review_style(code, language)

    def run_logic():
        return "logic", review_logic(code, language)

    def run_structure():
        return "structure", review_structure(code)

    jobs = [run_security, run_style, run_logic, run_structure]
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = dict(ex.map(lambda f: f(), jobs))

    findings = {domain: data.get("issues", []) for domain, data in results.items()}

    if conventions:
        from code_structure_agent import review_conformance
        conform_result = review_conformance(code, conventions)
        findings["conformance"] = conform_result.get("issues", [])

    total = sum(len(v) for v in findings.values())
    print(f"📊 Found {total} total issues.\n")

    return findings, language, code


def fix_file(
    code: str,
    language: str,
    findings: dict,
    conventions: str | None = None,
) -> str:
    """Run all fixers in order and merge results."""
    fixed_versions = {}

    # Fix order: security first, structural last
    fix_order = [
        ("security",  lambda: fix_security(code, language, findings.get("security", []))),
        ("logic",     lambda: fix_logic(code, language, findings.get("logic", []))),
        ("style",     lambda: fix_style(code, language, findings.get("style", []))),
        ("structure", lambda: fix_structure(code, findings.get("structure", []))),
    ]

    if conventions and findings.get("conformance"):
        from code_structure_agent import fix_conformance
        fix_order.append((
            "conformance",
            lambda: fix_conformance(code, findings["conformance"], conventions)
        ))

    for domain, fixer_fn in fix_order:
        if findings.get(domain):
            print(f"  🔧 Fixing {domain} issues...")
            result = fixer_fn()
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
        line = f" line {i['line']}" if i.get("line") else ""
        print(f"  {icon} [{i['domain'].upper()}{line}] {i['issue']}")
        print(f"     → {i['fix']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python code_review_orchestrator.py <file> [--fix] [--auto] [--conventions <file>]")
        sys.exit(1)

    file_path = sys.argv[1]
    auto_fix = "--auto" in sys.argv
    do_fix = "--fix" in sys.argv or auto_fix
    conventions = None

    if "--conventions" in sys.argv:
        conv_path = sys.argv[sys.argv.index("--conventions") + 1]
        conventions = Path(conv_path).read_text()

    print(f"\n{'='*60}")
    print(f"CODE REVIEW: {file_path}")
    print(f"{'='*60}\n")

    findings, language, code = review_file(file_path, conventions)

    total = sum(len(v) for v in findings.values())
    if total == 0:
        print("✅ No issues found!")
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
        fixed_code = fix_file(code, language, findings, conventions)
        out_path = Path(file_path).with_stem(Path(file_path).stem + "_reviewed")
        out_path.write_text(fixed_code)
        print(f"\n✅ Final fixed file: {out_path}")

    # Save findings JSON
    findings_path = Path(file_path).with_suffix(".review.json")
    findings_path.write_text(json.dumps(findings, indent=2))
    print(f"📄 Findings saved to: {findings_path}")
