"""
sdlc_orchestrator.py — Master Orchestrator
Runs the full SDLC agent pipeline for a given file or goal.

Coordinates:
  1. Planning   → PM agent defines requirements
  2. Design     → UI review (if applicable)
  3. Development → Code review (security, style, logic, structure)
  4. Testing    → Test generation
  5. Deployment → Deployment readiness check

Usage:
  python sdlc_orchestrator.py <file> [options]

Options:
  --goal "<text>"          High-level goal for PM agent (optional)
  --fix                    Apply fixes interactively
  --auto                   Apply all fixes without prompting
  --ui                     Also run UI/UX review
  --tests                  Also generate tests
  --deploy                 Also run deployment readiness check
  --conventions <file>     Conventions file for conformance checks
  --platform <p>           Force UI platform: mobile|desktop|web
  --all                    Run everything (ui + tests + deploy)
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.base_agent import run_agent

# Planning
sys.path.insert(0, str(Path(__file__).parent / "1_planning"))
from product_manager_agent import analyze_goal, print_requirements
from project_manager_agent import build_plan, print_plan

# Review orchestrators
sys.path.insert(0, str(Path(__file__).parent / "4_review"))
from code_review_orchestrator import review_file as review_code, fix_file as fix_code, aggregate_report as code_report, print_findings as print_code_findings
from ui_review_orchestrator   import review_ui_file, fix_ui_file, aggregate_report as ui_report, print_findings as print_ui_findings

# Testing
sys.path.insert(0, str(Path(__file__).parent / "5_testing"))
from test_generator_agent import analyze_test_cases, generate_tests, get_test_extension, _get_language

# Deployment
sys.path.insert(0, str(Path(__file__).parent / "6_deployment"))
from deployment_checklist_agent import review as review_deploy, fix as fix_deploy, generate_report as deploy_report


def section(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}\n")


def ask_proceed(prompt: str, auto: bool) -> bool:
    if auto:
        return True
    answer = input(f"\n{prompt} (y/n): ").strip().lower()
    return answer == "y"


def run_pipeline(args):
    file_path = args.file
    code = Path(file_path).read_text()
    language = _get_language(file_path)
    conventions = Path(args.conventions).read_text() if args.conventions else None
    results = {}

    # ── Phase 1: Planning (optional) ──────────────────────────────────────────
    if args.goal:
        section("PHASE 1: PLANNING")
        print("🎯 Running Product Manager agent...")
        requirements = analyze_goal(args.goal, f"Target file: {file_path}\nLanguage: {language}")
        print_requirements(requirements)
        results["requirements"] = requirements

        print("\n📋 Running Project Manager agent...")
        plan = build_plan(requirements)
        print_plan(plan)
        results["plan"] = plan

        Path("requirements.json").write_text(json.dumps(requirements, indent=2))
        Path("plan.json").write_text(json.dumps(plan, indent=2))

    # ── Phase 2: UI/UX Review (optional) ─────────────────────────────────────
    if args.ui or args.all:
        section("PHASE 2: UI/UX DESIGN REVIEW")
        ui_findings, platform, _ = review_ui_file(file_path, args.platform)
        total = sum(len(v) for v in ui_findings.values())
        results["ui_findings"] = ui_findings

        if total > 0:
            print_ui_findings(ui_findings)
            print("\n" + "─" * 60)
            print(ui_report(ui_findings))

            if (args.fix or args.all) and ask_proceed("⚡ Apply UI fixes?", args.auto):
                fixed = fix_ui_file(code, ui_findings)
                out = Path(file_path).with_stem(Path(file_path).stem + "_ui_fixed")
                out.write_text(fixed)
                code = fixed
                file_path = str(out)
                print(f"✅ UI fixes applied → {out}")
        else:
            print("✅ No UI issues found.")

    # ── Phase 3/4: Code Review ────────────────────────────────────────────────
    section("PHASES 3-4: CODE REVIEW")
    code_findings, lang, current_code = review_code(file_path, conventions)
    total = sum(len(v) for v in code_findings.values())
    results["code_findings"] = code_findings

    if total > 0:
        print_code_findings(code_findings)
        print("\n" + "─" * 60)
        print(code_report(code_findings))

        if (args.fix or args.all) and ask_proceed("⚡ Apply code fixes?", args.auto):
            fixed = fix_code(current_code, lang, code_findings, conventions)
            out = Path(file_path).with_stem(Path(file_path).stem + "_fixed")
            Path(out).write_text(fixed)
            file_path = str(out)
            print(f"✅ Code fixes applied → {out}")
    else:
        print("✅ No code issues found.")

    # ── Phase 5: Test Generation (optional) ──────────────────────────────────
    if args.tests or args.all:
        section("PHASE 5: TEST GENERATION")
        final_code = Path(file_path).read_text()

        print("🧪 Analyzing test cases...")
        analysis = analyze_test_cases(final_code)
        test_cases = analysis.get("test_cases", [])
        print(f"   → {len(test_cases)} test cases identified")

        if test_cases:
            print("📝 Generating tests...")
            test_code = generate_tests(final_code, language, test_cases)
            ext = get_test_extension(language)
            stem = Path(file_path).stem.replace("_fixed", "")
            test_out = Path(file_path).parent / f"test_{stem}{ext}"
            test_out.write_text(test_code)
            print(f"✅ Tests written to: {test_out}")
            results["test_cases_count"] = len(test_cases)

    # ── Phase 6: Deployment Readiness (optional) ──────────────────────────────
    if args.deploy or args.all:
        section("PHASE 6: DEPLOYMENT READINESS")
        final_code = Path(file_path).read_text()

        deploy_result = review_deploy(final_code)
        ready = deploy_result.get("deployment_ready", False)
        blockers = deploy_result.get("blockers", [])
        results["deployment_ready"] = ready
        results["deployment_blockers"] = blockers

        status = "✅ GO" if ready else "🛑 NO-GO"
        print(f"Deployment Status: {status}")
        print(deploy_report(deploy_result))

        if not ready and blockers and (args.fix or args.all):
            if ask_proceed("⚡ Apply deployment fixes?", args.auto):
                fixed = fix_deploy(final_code, deploy_result.get("issues", []))
                out = Path(file_path).with_stem(Path(file_path).stem + "_deploy_ready")
                Path(out).write_text(fixed["fixed_code"])
                print(f"✅ Deploy-ready file: {out}")

    # ── Summary ───────────────────────────────────────────────────────────────
    section("PIPELINE COMPLETE")
    print(f"📁 Input file:   {args.file}")
    print(f"📁 Output file:  {file_path}")

    code_total = sum(len(v) for v in results.get("code_findings", {}).values())
    ui_total   = sum(len(v) for v in results.get("ui_findings", {}).values())
    print(f"🔒 Code issues:  {code_total}")
    if args.ui or args.all:
        print(f"🎨 UI issues:    {ui_total}")
    if args.tests or args.all:
        print(f"🧪 Tests gen'd:  {results.get('test_cases_count', 0)} cases")
    if args.deploy or args.all:
        deploy_status = "✅ GO" if results.get("deployment_ready") else "🛑 NO-GO"
        print(f"🚀 Deploy:       {deploy_status}")

    Path("pipeline_results.json").write_text(json.dumps(results, indent=2))
    print("\n📄 Full results saved to: pipeline_results.json")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SDLC Agent Pipeline")
    parser.add_argument("file", help="Source file to process")
    parser.add_argument("--goal", help="High-level goal for PM agent")
    parser.add_argument("--fix", action="store_true", help="Apply fixes interactively")
    parser.add_argument("--auto", action="store_true", help="Apply all fixes without prompting")
    parser.add_argument("--ui", action="store_true", help="Run UI/UX review")
    parser.add_argument("--tests", action="store_true", help="Generate tests")
    parser.add_argument("--deploy", action="store_true", help="Run deployment readiness check")
    parser.add_argument("--all", action="store_true", help="Run all phases")
    parser.add_argument("--conventions", help="Conventions file for conformance checks")
    parser.add_argument("--platform", choices=["mobile", "desktop", "web"], help="Force UI platform")

    args = parser.parse_args()
    run_pipeline(args)
