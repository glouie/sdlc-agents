"""
build_orchestrator.py — Hybrid BUILD pipeline for new CLI projects.

This is the entry point when building from scratch (not reviewing existing code).

Pipeline:
  1. INTERVIEW    — asks focused questions upfront (hybrid: human input once)
  2. SPEC         — builds unambiguous project spec from answers
  3. ARCHITECTURE — decides structure, patterns, file manifest
  4. REVIEW PLAN  — shows user what will be built, asks for confirmation
  5. GENERATE     — creates all source files in dependency order
  6. REVIEW       — runs all reviewer agents on generated code
  7. FIX          — applies fixes automatically
  8. TESTS        — generates test files
  9. DEPLOY CFG   — generates Dockerfile, CI, Makefile, .env.example
 10. GITHUB PUSH  — creates repo, pushes all files, writes session manifest
 11. SUMMARY      — prints what was built + how to run it + how to resume

Usage:
  python build_orchestrator.py "<your project goal>"
  python build_orchestrator.py "Build a CLI tool that monitors log files and alerts on error patterns"

Options:
  --no-review      Skip code review step (faster, less polished)
  --no-tests       Skip test generation
  --no-deploy      Skip deployment config generation
  --no-github      Skip GitHub push (local files only)
  --private        Make the GitHub repo private
  --output <dir>   Output directory (default: project slug name)

Env vars:
  GITHUB_TOKEN     Personal access token with 'repo' scope (required for GitHub push)
  GITHUB_USERNAME  Your GitHub username (inferred from token if not set)
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.interview_agent     import conduct_interview, build_spec, print_spec
from core.architect_agent     import design_architecture, print_architecture
from core.base_agent          import SMART_MODEL
from core.github_push_agent   import push_project
from core.token_manager        import setup_tokens, get_token

sys.path.insert(0, str(Path(__file__).parent / "3_development"))
from code_generator_agent import generate_all_files

sys.path.insert(0, str(Path(__file__).parent / "6_deployment"))
from config_generator_agent import generate_all_configs

sys.path.insert(0, str(Path(__file__).parent / "4_review"))
from code_review_orchestrator import (
    review_file as review_code,
    fix_file    as fix_code,
    aggregate_report,
    print_findings,
)


def section(title: str):
    width = 60
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}\n")


def confirm(prompt: str) -> bool:
    answer = input(f"\n{prompt} (y/n) [y]: ").strip().lower()
    return answer in ("", "y", "yes")


def review_and_fix_generated(output_dir: Path, generated_files: dict, spec: dict) -> int:
    """Run reviewers on all generated source files. Returns total issues fixed."""
    language = spec.get("language", "python").lower()
    fixable_extensions = {".py", ".sh", ".bash", ".js", ".ts", ".rb", ".go"}

    source_files = [
        p for p in generated_files
        if Path(p).suffix in fixable_extensions
        and not Path(p).name.startswith("test_")
        and "test" not in Path(p).parts
    ]

    total_fixed = 0
    for rel_path in source_files:
        full_path = output_dir / rel_path
        if not full_path.exists():
            continue

        print(f"\n  🔍 Reviewing {rel_path}...")
        try:
            findings, lang, code = review_code(str(full_path))
            count = sum(len(v) for v in findings.values())

            if count == 0:
                print(f"     ✅ Clean")
                continue

            print(f"     ⚠️  {count} issues found — auto-fixing...")
            fixed_code = fix_code(code, lang, findings)
            full_path.write_text(fixed_code)
            total_fixed += count
            print(f"     ✅ Fixed {count} issues")
        except Exception as e:
            print(f"     ⚠️  Review skipped ({e})")

    return total_fixed


def print_summary(
    output_dir: Path,
    spec: dict,
    arch: dict,
    generated_files: dict,
    total_issues_fixed: int,
    github_result: dict | None = None,
):
    section("BUILD COMPLETE")
    project_name = spec.get("project_name", output_dir.name)

    print(f"✅ Project: {project_name}")
    print(f"📁 Output:  {output_dir.resolve()}/")
    print(f"📄 Files:   {len(generated_files)} generated")
    if total_issues_fixed:
        print(f"🔧 Fixed:   {total_issues_fixed} code issues auto-corrected")

    print(f"\n{'─' * 60}")
    print(f"GETTING STARTED\n")

    install_steps = arch.get("install_steps", [])
    if install_steps:
        print("Install:")
        for step in install_steps:
            print(f"  $ {step}")

    run_cmd = arch.get("run_command", "")
    test_cmd = arch.get("test_command", "")

    if run_cmd:
        print(f"\nRun:")
        print(f"  $ {run_cmd}")

    if test_cmd:
        print(f"\nTest:")
        print(f"  $ {test_cmd}")

    print(f"\nDocker:")
    print(f"  $ make docker-build")
    print(f"  $ make docker-run")

    print(f"\nAll available commands:")
    print(f"  $ make help")

    if github_result:
        print(f"\n{'─' * 60}")
        print(f"GITHUB REPO\n")
        print(f"  🔗 {github_result['repo_url']}")
        print(f"  Clone: git clone {github_result['clone_url']}")
        print(f"\n  Resume next session:")
        print(f"  $ python session_agent.py {github_result['repo_url']}")
        print(f"  (or just: python session_agent.py  — it remembers the last repo)")

    print(f"\n{'─' * 60}")
    print(f"PROJECT STRUCTURE\n")

    type_icons = {
        "entrypoint": "🚀", "module": "📦", "config": "⚙️",
        "test": "🧪", "docs": "📝", "ci": "🔄", "docker": "🐳", "util": "🔧"
    }
    for f in arch.get("file_manifest", []):
        icon = type_icons.get(f["type"], "📄")
        print(f"  {icon} {f['path']}")

    deploy_configs = [
        "Dockerfile", "docker-compose.yml",
        ".github/workflows/ci.yml", "Makefile"
    ]
    for cfg in deploy_configs:
        print(f"  🐳 {cfg}")


def run_build_pipeline(goal: str, args: argparse.Namespace):

    # ── Step 0: Credentials ───────────────────────────────────────────────────
    needed = ["ANTHROPIC_API_KEY"] if args.no_github else ["ANTHROPIC_API_KEY", "GITHUB_TOKEN"]
    setup_tokens(needed)

    # ── Step 1: Interview ─────────────────────────────────────────────────────
    section("STEP 1 OF 9: GATHERING REQUIREMENTS")
    print(f"Goal: {goal}\n")
    answers = conduct_interview(goal)

    # ── Step 2: Build spec ────────────────────────────────────────────────────
    section("STEP 2 OF 9: BUILDING PROJECT SPEC")
    print("🔨 Synthesizing your answers into a project spec...")
    spec = build_spec(goal, answers)
    print_spec(spec)

    # ── Step 3: Architecture ──────────────────────────────────────────────────
    section("STEP 3 OF 9: DESIGNING ARCHITECTURE")
    print("🏗️  Designing project structure and making tech decisions...")
    arch = design_architecture(spec)
    print_architecture(arch)

    # ── Step 4: Confirm plan ──────────────────────────────────────────────────
    section("STEP 4 OF 9: REVIEW PLAN")

    project_name = spec.get("project_name", "my-cli-tool")
    output_dir = Path(args.output) if args.output else Path(project_name)

    file_count = len(arch.get("file_manifest", []))
    print(f"Ready to generate {file_count} files into: {output_dir}/\n")
    print("This will create:")
    print(f"  • All source code ({spec.get('language', '?')})")
    print(f"  • Test suite ({arch.get('architecture_decisions', {}).get('test_framework', '?')})")
    print(f"  • Dockerfile + docker-compose")
    print(f"  • GitHub Actions CI workflow")
    print(f"  • Makefile")
    print(f"  • .env.example\n")

    if not confirm("⚡ Generate the project?"):
        print("Aborted.")
        sys.exit(0)

    # Save intermediates
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".sdlc" ).mkdir(exist_ok=True)
    (output_dir / ".sdlc/project_spec.json").write_text(json.dumps(spec, indent=2))
    (output_dir / ".sdlc/architecture.json").write_text(json.dumps(arch, indent=2))

    # ── Step 5: Generate source files ─────────────────────────────────────────
    section("STEP 5 OF 9: GENERATING SOURCE FILES")
    generated = generate_all_files(
        spec, arch, output_dir,
        generate_tests=not args.no_tests,
    )
    print(f"\n  ✅ {len(generated)} files generated")

    # ── Step 6+7: Review and fix ──────────────────────────────────────────────
    total_fixed = 0
    if not args.no_review:
        section("STEPS 6-7 OF 9: REVIEWING + AUTO-FIXING GENERATED CODE")
        total_fixed = review_and_fix_generated(output_dir, generated, spec)
        if total_fixed == 0:
            print("\n  ✅ All generated code is clean!")
        else:
            print(f"\n  ✅ Auto-fixed {total_fixed} issues across generated files")

    # ── Step 8: (Tests already generated in step 5) ───────────────────────────
    if not args.no_tests:
        section("STEP 8 OF 9: TESTS")
        test_files = [p for p in generated if "test" in Path(p).name or "test" in Path(p).parts]
        print(f"  ✅ {len(test_files)} test file(s) already generated in step 5")
        for t in test_files:
            print(f"     🧪 {t}")

    # ── Step 9: Deployment configs ────────────────────────────────────────────
    if not args.no_deploy:
        section("STEP 9 OF 9: GENERATING DEPLOYMENT CONFIGS")
        project_files = list(generated.keys())
        deploy_generated = generate_all_configs(spec, arch, output_dir, project_files)
        print(f"\n  ✅ {len(deploy_generated)} deployment config files generated")

    # ── Step 10: GitHub push ──────────────────────────────────────────────────
    github_result = None
    if not args.no_github:
        section("STEP 10 OF 10: PUSHING TO GITHUB")
        token = get_token("GITHUB_TOKEN")

        if token:
            try:
                deploy_files_for_push = deploy_generated if not args.no_deploy else {}
                github_result = push_project(
                    spec=spec,
                    arch=arch,
                    generated_files=generated,
                    deploy_files=deploy_files_for_push,
                    token=token,
                    private=args.private,
                )
                # Save repo ref locally for session_agent to pick up
                from pathlib import Path as _Path
                _Path(".sdlc").mkdir(exist_ok=True)
                _Path(".sdlc/last_repo.txt").write_text(
                    f"{github_result['owner']}/{github_result['repo']}"
                )
            except Exception as e:
                print(f"  ⚠️  GitHub push failed: {e}")
                print(f"  Files are still available locally in: {output_dir}/")
        else:
            print("  ⏭️  Skipping GitHub push (no token provided)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print_summary(output_dir, spec, arch, generated, total_fixed, github_result)




# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a new CLI tool project from a goal description.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_orchestrator.py "A CLI tool that monitors log files and alerts on error patterns"
  python build_orchestrator.py "A tool to sync files between S3 buckets" --output s3-sync
  python build_orchestrator.py "Parse and summarize nginx access logs" --no-review --no-github
        """,
    )
    parser.add_argument("goal", help="What you want to build (in plain English)")
    parser.add_argument("--output",    help="Output directory (default: project slug)")
    parser.add_argument("--no-review", action="store_true", help="Skip code review step")
    parser.add_argument("--no-tests",  action="store_true", help="Skip test generation")
    parser.add_argument("--no-deploy", action="store_true", help="Skip deployment config generation")
    parser.add_argument("--no-github", action="store_true", help="Skip GitHub push (local only)")
    parser.add_argument("--private",   action="store_true", help="Make the GitHub repo private")

    args = parser.parse_args()
    run_build_pipeline(args.goal, args)
