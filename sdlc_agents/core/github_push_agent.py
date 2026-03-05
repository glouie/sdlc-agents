"""
github_push_agent.py — Called at the end of build_orchestrator to:
  1. Create a new GitHub repo
  2. Push all generated files in a single commit
  3. Write the session manifest to .sdlc/manifest.json
  4. Write project spec and architecture to .sdlc/ for future reference
  5. Return the repo URL

This is intentionally a thin agent — it delegates storage decisions to
session_manifest_agent and API calls to github_client.
"""

import sys
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.github_client          import GitHubClient
from core.session_manifest_agent import create_manifest, print_manifest_summary


def push_project(
    spec: dict,
    arch: dict,
    generated_files: dict[str, str],
    deploy_files: dict[str, str],
    token: str | None = None,
    private: bool = False,
    repo_name: str | None = None,
) -> dict:
    """
    Push a complete generated project to a new GitHub repo.

    Returns:
      {
        "repo_url": "https://github.com/user/repo",
        "clone_url": "https://github.com/user/repo.git",
        "manifest_path": ".sdlc/manifest.json",
        "files_pushed": 42,
      }
    """
    gh = GitHubClient(token)
    owner = gh.username

    # Determine repo name
    name = repo_name or spec.get("project_name", "sdlc-project")
    # Ensure repo name is valid (GitHub slug rules)
    name = name.lower().replace("_", "-").replace(" ", "-")

    print(f"\n  🐙 Creating GitHub repo: {owner}/{name}")
    if gh.repo_exists(owner, name):
        print(f"  ⚠️  Repo {owner}/{name} already exists — pushing to it")
    else:
        gh.create_repo(
            name=name,
            description=spec.get("description", "")[:255],
            private=private,
            auto_init=True,
        )
        print(f"  ✅ Repo created: {gh.repo_url(owner, name)}")

    # Build the full manifest
    repo_url = gh.repo_url(owner, name)
    manifest = create_manifest(
        spec=spec,
        arch=arch,
        generated_files={**generated_files, **deploy_files},
        repo_url=repo_url,
        session_note="Initial project generation via build_orchestrator",
    )

    # Assemble everything to push in one commit
    all_files: dict[str, str] = {}

    # Source + test files
    all_files.update(generated_files)

    # Deployment configs
    all_files.update(deploy_files)

    # SDLC metadata (small, for future sessions)
    all_files[".sdlc/manifest.json"]     = json.dumps(manifest, indent=2)
    all_files[".sdlc/project_spec.json"] = json.dumps(spec, indent=2)
    all_files[".sdlc/architecture.json"] = json.dumps(arch, indent=2)

    # Add a .sdlc/README.md explaining the folder
    all_files[".sdlc/README.md"] = _sdlc_readme()

    print(f"\n  ⬆️  Pushing {len(all_files)} files in a single commit...")
    gh.write_files_batch(
        owner=owner,
        repo=name,
        files=all_files,
        commit_message="[sdlc-agent] Initial project generation",
    )

    print(f"  ✅ All files pushed successfully")
    print(f"  🔗 {repo_url}")

    return {
        "repo_url":      repo_url,
        "clone_url":     gh.clone_url(owner, name),
        "owner":         owner,
        "repo":          name,
        "manifest_path": ".sdlc/manifest.json",
        "files_pushed":  len(all_files),
    }


def _sdlc_readme() -> str:
    return """\
# .sdlc/

This directory is managed by the SDLC agent system.
Do not edit these files manually.

## Files

| File | Purpose |
|------|---------|
| `manifest.json` | Session index — loaded at the start of every agent session. Small by design. |
| `project_spec.json` | Full project specification from the initial interview. |
| `architecture.json` | Architecture decisions: tech stack, file manifest, patterns. |

## Resuming Work

To continue working on this project in a new session:

```bash
python session_agent.py https://github.com/{owner}/{repo}
```

The session agent reads only `manifest.json` first (~2-5kb), then fetches
only the specific files needed for today's task. The full repo is never
loaded into context at once.
"""


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Test push using existing spec/arch/output files.
    Usage: python github_push_agent.py <output_dir>
    """
    if len(sys.argv) < 2:
        print("Usage: python github_push_agent.py <output_dir>")
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    sdlc_dir   = output_dir / ".sdlc"

    spec = json.loads((sdlc_dir / "project_spec.json").read_text())
    arch = json.loads((sdlc_dir / "architecture.json").read_text())

    # Collect generated files
    generated = {}
    for path in output_dir.rglob("*"):
        if path.is_file() and ".sdlc" not in path.parts:
            rel = str(path.relative_to(output_dir))
            generated[rel] = path.read_text()

    result = push_project(spec, arch, generated, {})
    print(f"\n✅ Pushed to: {result['repo_url']}")
    print(f"   Clone: git clone {result['clone_url']}")
