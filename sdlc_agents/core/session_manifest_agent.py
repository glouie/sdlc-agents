"""
session_manifest_agent.py — The key to context-efficient multi-session work.

The manifest is a small JSON file (~2-5kb) stored at .sdlc/manifest.json
in the GitHub repo. Every session starts by reading ONLY this file.

The manifest tells the agent:
  - What the project is (summary, not full spec)
  - What files exist and what each does (index only, not content)
  - Which files are relevant to common task types
  - What was done last session
  - What's next / current focus

The agent then selectively fetches only the files it needs for today's task.
This prevents the entire repo from being loaded into context.

Design principle: The manifest is an INDEX, not a dump.
  ✅ "auth.py — handles JWT login and token refresh (127 lines)"
  ❌ (the actual content of auth.py)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# ── Manifest schema ───────────────────────────────────────────────────────────

def create_manifest(
    spec: dict,
    arch: dict,
    generated_files: dict[str, str],
    repo_url: str,
    session_note: str = "Initial project generation",
) -> dict:
    """
    Build the initial manifest from a completed build pipeline run.
    Called once when a project is first pushed to GitHub.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Build file index — path + purpose + line count, NOT content
    file_index = []
    for path, content in generated_files.items():
        line_count = len(content.splitlines())
        # Find the matching entry in the file manifest for its purpose
        purpose = next(
            (f["purpose"] for f in arch.get("file_manifest", []) if f["path"] == path),
            "Project file"
        )
        file_type = next(
            (f["type"] for f in arch.get("file_manifest", []) if f["path"] == path),
            "module"
        )
        file_index.append({
            "path": path,
            "type": file_type,
            "purpose": purpose,
            "lines": line_count,
            "status": "generated",      # generated | reviewed | modified | wip
            "last_modified": now,
        })

    # Add deployment configs to index
    deploy_configs = [
        "Dockerfile", "docker-compose.yml",
        ".github/workflows/ci.yml", "Makefile",
        ".env.example", ".dockerignore"
    ]
    for cfg in deploy_configs:
        file_index.append({
            "path": cfg,
            "type": "config",
            "purpose": f"Deployment / infrastructure configuration",
            "lines": None,
            "status": "generated",
            "last_modified": now,
        })

    # Identify which files are relevant for common task types
    source_files = [f["path"] for f in file_index if f["type"] in ("entrypoint", "module", "util")]
    test_files   = [f["path"] for f in file_index if f["type"] == "test"]
    config_files = [f["path"] for f in file_index if f["type"] in ("config", "ci", "docker")]

    return {
        "version": "1.0",
        "project": {
            "name":        spec.get("project_name", "unknown"),
            "description": spec.get("description", ""),
            "language":    spec.get("language", "unknown"),
            "runtime":     spec.get("runtime", ""),
            "run_command": arch.get("run_command", ""),
            "test_command": arch.get("test_command", ""),
            "repo_url":    repo_url,
        },
        "architecture_summary": {
            "argument_parser": arch.get("architecture_decisions", {}).get("argument_parser", ""),
            "test_framework":  arch.get("architecture_decisions", {}).get("test_framework", ""),
            "key_patterns":    arch.get("architecture_decisions", {}).get("key_patterns", []),
        },
        "file_index": file_index,
        "task_file_map": {
            "add_feature":    source_files + ["README.md"],
            "fix_bug":        source_files,
            "add_tests":      source_files + test_files,
            "update_ci":      config_files,
            "review_code":    source_files,
            "update_docs":    ["README.md"],
            "full_review":    source_files + test_files,
        },
        "sessions": [
            {
                "date": now,
                "note": session_note,
                "files_changed": list(generated_files.keys()),
                "status": "complete",
            }
        ],
        "current_focus": None,   # set by session_agent when starting work
        "next_steps": [],        # populated by session agent at end of session
    }


def update_manifest_session(
    manifest: dict,
    files_changed: list[str],
    session_note: str,
    next_steps: list[str] | None = None,
    file_statuses: dict[str, str] | None = None,
) -> dict:
    """
    Update the manifest at the end of a session.
    Call this before writing back to GitHub.
    """
    import copy
    m = copy.deepcopy(manifest)
    now = datetime.now(timezone.utc).isoformat()

    # Add session log entry
    m["sessions"].append({
        "date": now,
        "note": session_note,
        "files_changed": files_changed,
        "status": "complete",
    })

    # Keep only last 10 sessions to prevent manifest growth
    m["sessions"] = m["sessions"][-10:]

    # Update file statuses and timestamps
    if file_statuses:
        for f in m["file_index"]:
            if f["path"] in file_statuses:
                f["status"] = file_statuses[f["path"]]
                f["last_modified"] = now

    # Update file line counts for changed files (caller should provide updated content)
    m["current_focus"] = None
    if next_steps:
        m["next_steps"] = next_steps

    return m


def get_files_for_task(manifest: dict, task_type: str) -> list[str]:
    """
    Returns the minimal list of file paths to fetch for a given task type.
    This is how we keep context small — only load what the task needs.
    """
    task_map = manifest.get("task_file_map", {})
    files = task_map.get(task_type, [])

    # Always include manifest itself (already loaded)
    # Return only files that actually exist in the index
    indexed = {f["path"] for f in manifest.get("file_index", [])}
    return [f for f in files if f in indexed]


def print_manifest_summary(manifest: dict):
    """Print a human-readable summary of the manifest."""
    project = manifest.get("project", {})
    sessions = manifest.get("sessions", [])
    file_index = manifest.get("file_index", [])
    next_steps = manifest.get("next_steps", [])

    print(f"\n📋 PROJECT: {project.get('name', '?')}")
    print(f"   {project.get('description', '')}")
    print(f"   Language: {project.get('language', '?')} | Runtime: {project.get('runtime', '?')}")
    print(f"   Repo: {project.get('repo_url', '?')}")
    print(f"   Run:  {project.get('run_command', '?')}")

    if sessions:
        last = sessions[-1]
        print(f"\n⏱  LAST SESSION: {last['date'][:10]}")
        print(f"   {last['note']}")
        print(f"   Files changed: {len(last.get('files_changed', []))}")

    if next_steps:
        print(f"\n📌 NEXT STEPS:")
        for step in next_steps:
            print(f"   • {step}")

    print(f"\n📁 FILES ({len(file_index)}):")
    type_icons = {
        "entrypoint": "🚀", "module": "📦", "config": "⚙️",
        "test": "🧪", "docs": "📝", "ci": "🔄", "docker": "🐳", "util": "🔧"
    }
    status_icons = {"generated": "✨", "reviewed": "✅", "modified": "📝", "wip": "🔄"}
    for f in file_index:
        icon = type_icons.get(f["type"], "📄")
        status = status_icons.get(f["status"], "❓")
        lines = f" ({f['lines']}L)" if f.get("lines") else ""
        print(f"   {icon} {status} {f['path']}{lines}")
        print(f"        {f['purpose']}")
