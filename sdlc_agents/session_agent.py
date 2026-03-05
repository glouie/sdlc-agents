"""
session_agent.py — Entry point for resuming work on an existing project.

Every new session on an existing project starts here, not at build_orchestrator.
This agent:
  1. Reads ONLY the manifest (small, ~2-5kb) from GitHub
  2. Shows you the project state and last session summary
  3. Asks what you want to do today
  4. Fetches ONLY the files relevant to today's task
  5. Does the work (review, generate, fix, etc.)
  6. Commits changes back to GitHub
  7. Updates the manifest with session log + next steps

Context stays small because:
  - We never load the full repo
  - We load files based on task type from task_file_map
  - Agent prompts are loaded from disk, not hardcoded here
  - Each subtask delegates to a focused subagent

Usage:
  python session_agent.py <github_repo_url>
  python session_agent.py https://github.com/yourname/my-cli-tool
  python session_agent.py yourname/my-cli-tool
  python session_agent.py  # looks for .sdlc/last_repo.txt
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.github_client          import GitHubClient
from core.base_agent             import run_agent, SMART_MODEL
from core.session_manifest_agent import (
    get_files_for_task,
    update_manifest_session,
    print_manifest_summary,
)
from core.token_manager import setup_tokens


# ── Task dispatcher ───────────────────────────────────────────────────────────

TASK_PROMPT = """You are a session planning agent for a CLI tool project.

Given:
- Project manifest (index of files, last session, next steps)
- User's task description for today

Determine:
1. Which task type best fits the request
2. Which specific files need to be fetched (use the task_file_map as a guide,
   but also consider what the user's specific request needs)
3. A brief plan for completing the task

Task types: add_feature | fix_bug | add_tests | update_ci | review_code |
            update_docs | full_review | refactor | add_command

Output ONLY valid JSON:
{
  "task_type": "<type>",
  "files_needed": ["<paths to fetch from GitHub>"],
  "plan": ["<step 1>", "<step 2>", "<step 3>"],
  "estimated_changes": ["<file that will change and why>"]
}"""

WORK_AGENT_PROMPT = """You are an expert CLI tool developer working on an existing project.

You will be given:
- Project manifest (context about the whole project)
- The specific files needed for today's task (fetched from GitHub)
- The task to complete

Complete the task by producing updated file contents.
Follow the existing patterns and architecture decisions exactly.
Do not change files not relevant to the task.

Output ONLY valid JSON:
{
  "changes": [
    {
      "path": "<file path>",
      "content": "<complete new file content — never truncate>",
      "reason": "<why this file changed>"
    }
  ],
  "session_note": "<one sentence summary of what was done>",
  "next_steps": ["<suggested follow-up tasks>"]
}"""


# ── GitHub helpers ────────────────────────────────────────────────────────────

def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL or 'owner/repo' string."""
    url = url.strip().rstrip("/")
    if url.startswith("https://github.com/"):
        url = url.replace("https://github.com/", "")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse repo: {url}. Use 'owner/repo' or full GitHub URL.")
    return parts[0], parts[1]


def read_manifest(gh: GitHubClient, owner: str, repo: str) -> dict:
    content = gh.read_file(owner, repo, ".sdlc/manifest.json")
    if not content:
        raise RuntimeError(
            f"No manifest found at .sdlc/manifest.json in {owner}/{repo}.\n"
            f"This repo may not have been created with the SDLC agent system.\n"
            f"Run build_orchestrator.py to start a new project."
        )
    return json.loads(content)


def fetch_files(gh: GitHubClient, owner: str, repo: str, paths: list[str]) -> dict[str, str]:
    """Fetch specific files from GitHub. Returns {path: content}."""
    fetched = {}
    for path in paths:
        content = gh.read_file(owner, repo, path)
        if content:
            fetched[path] = content
        else:
            print(f"  ⚠️  Could not fetch {path} (may not exist yet)")
    return fetched


# ── Session flow ──────────────────────────────────────────────────────────────

def plan_task(manifest: dict, user_task: str) -> dict:
    user_input = (
        f"Project manifest:\n{json.dumps(manifest, indent=2)}\n\n"
        f"Today's task: {user_task}"
    )
    return run_agent(TASK_PROMPT, user_input, max_tokens=1500, model=SMART_MODEL)


def execute_task(manifest: dict, fetched_files: dict, user_task: str, plan: dict) -> dict:
    # Build minimal context — manifest summary + file contents
    file_sections = "\n\n".join(
        f"FILE: {path}\n```\n{content}\n```"
        for path, content in fetched_files.items()
    )
    user_input = (
        f"Project manifest:\n{json.dumps(manifest, indent=2)}\n\n"
        f"Task: {user_task}\n\n"
        f"Plan:\n{json.dumps(plan.get('plan', []), indent=2)}\n\n"
        f"Files to work with:\n{file_sections}"
    )
    return run_agent(WORK_AGENT_PROMPT, user_input, max_tokens=8192, model=SMART_MODEL)


def commit_changes(
    gh: GitHubClient,
    owner: str,
    repo: str,
    changes: list[dict],
    session_note: str,
) -> list[str]:
    """Commit all changed files in a single commit. Returns list of changed paths."""
    if not changes:
        return []

    files_to_commit = {c["path"]: c["content"] for c in changes}
    gh.write_files_batch(
        owner, repo, files_to_commit,
        commit_message=f"[sdlc-agent] {session_note}"
    )
    return list(files_to_commit.keys())


def run_session(repo_ref: str):
    section = lambda t: print(f"\n{'═'*60}\n  {t}\n{'═'*60}\n")

    # ── Credentials ───────────────────────────────────────────────────────────
    setup_tokens(["ANTHROPIC_API_KEY", "GITHUB_TOKEN"])

    # ── Connect ────────────────────────────────────────────────────────────────
    import os
    gh = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
    owner, repo_name = parse_repo_url(repo_ref)
    print(f"\n🔗 Connecting to: {gh.repo_url(owner, repo_name)}")
    print(f"   Authenticated as: {gh.username}")

    # ── Load manifest (small, always first) ────────────────────────────────────
    section("LOADING PROJECT STATE")
    print("📋 Reading manifest (.sdlc/manifest.json)...")
    manifest = read_manifest(gh, owner, repo_name)
    print_manifest_summary(manifest)

    # ── Get today's task from user ─────────────────────────────────────────────
    section("WHAT ARE WE WORKING ON TODAY?")

    if manifest.get("next_steps"):
        print("Suggested next steps from last session:")
        for i, step in enumerate(manifest["next_steps"], 1):
            print(f"  {i}. {step}")
        print()

    user_task = input("Describe what you want to do: ").strip()
    if not user_task:
        print("No task provided. Exiting.")
        return

    # ── Plan: decide which files to load ──────────────────────────────────────
    section("PLANNING SESSION")
    print("🧠 Analyzing task and determining which files to load...")
    plan = plan_task(manifest, user_task)

    files_needed = plan.get("files_needed", [])
    task_type = plan.get("task_type", "unknown")

    print(f"   Task type: {task_type}")
    print(f"   Files to fetch ({len(files_needed)}):")
    for f in files_needed:
        print(f"     • {f}")
    print(f"\n   Plan:")
    for step in plan.get("plan", []):
        print(f"     → {step}")

    if not files_needed:
        print("\n⚠️  No files identified as needed. Check your task description.")
        return

    # ── Fetch only needed files ────────────────────────────────────────────────
    section("FETCHING FILES FROM GITHUB")
    print(f"⬇️  Fetching {len(files_needed)} files (not the whole repo)...")
    fetched = fetch_files(gh, owner, repo_name, files_needed)
    total_lines = sum(len(c.splitlines()) for c in fetched.values())
    print(f"   ✅ {len(fetched)} files fetched ({total_lines} total lines in context)")

    # ── Do the work ────────────────────────────────────────────────────────────
    section("EXECUTING TASK")
    print(f"⚙️  Working on: {user_task}")
    result = execute_task(manifest, fetched, user_task, plan)

    changes = result.get("changes", [])
    session_note = result.get("session_note", user_task[:80])
    next_steps = result.get("next_steps", [])

    if not changes:
        print("ℹ️  No file changes produced.")
        return

    print(f"\n📝 Changes to commit ({len(changes)} files):")
    for c in changes:
        print(f"   • {c['path']}: {c['reason']}")

    # ── Review changes ─────────────────────────────────────────────────────────
    answer = input("\n⚡ Commit these changes to GitHub? (y/n) [y]: ").strip().lower()
    if answer not in ("", "y", "yes"):
        print("Changes discarded.")
        return

    # ── Commit to GitHub ───────────────────────────────────────────────────────
    section("COMMITTING TO GITHUB")
    print("⬆️  Pushing changes...")
    changed_paths = commit_changes(gh, owner, repo_name, changes, session_note)
    print(f"   ✅ Committed {len(changed_paths)} files")

    # ── Update manifest ────────────────────────────────────────────────────────
    print("📋 Updating session manifest...")
    updated_manifest = update_manifest_session(
        manifest,
        files_changed=changed_paths,
        session_note=session_note,
        next_steps=next_steps,
    )
    gh.write_file(
        owner, repo_name,
        ".sdlc/manifest.json",
        json.dumps(updated_manifest, indent=2),
        message="[sdlc-agent] Update session manifest",
    )

    # ── Summary ────────────────────────────────────────────────────────────────
    section("SESSION COMPLETE")
    print(f"✅ {session_note}")
    print(f"📁 {len(changed_paths)} files committed")
    print(f"🔗 {gh.repo_url(owner, repo_name)}")

    if next_steps:
        print(f"\n📌 Next steps for next session:")
        for step in next_steps:
            print(f"   • {step}")

    # Save repo ref for next time
    Path(".sdlc").mkdir(exist_ok=True)
    Path(".sdlc/last_repo.txt").write_text(f"{owner}/{repo_name}")
    print(f"\n💾 Repo saved to .sdlc/last_repo.txt for next session")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    repo_ref = None

    if len(sys.argv) > 1:
        repo_ref = sys.argv[1]
    elif Path(".sdlc/last_repo.txt").exists():
        repo_ref = Path(".sdlc/last_repo.txt").read_text().strip()
        print(f"📂 Resuming last repo: {repo_ref}")
    else:
        print("Usage: python session_agent.py <github_repo_url_or_owner/repo>")
        print("       python session_agent.py https://github.com/you/my-cli-tool")
        print("       python session_agent.py you/my-cli-tool")
        sys.exit(1)

    run_session(repo_ref)
