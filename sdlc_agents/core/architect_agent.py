"""
architect_agent.py — Decides project structure, tech stack, patterns,
and produces a per-file generation plan.

This is the most critical generation agent. It runs ONCE before any code
is generated. Every code generator agent receives the architect's decisions
as context, ensuring the whole project is internally consistent.

Outputs a file manifest — one entry per file that needs to exist, with
enough spec that a focused generator agent can write it without needing
to see any other file.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

ARCHITECT_PROMPT = """You are a software architect specializing in CLI tools.

Given a project specification, design the complete project structure and
produce a generation plan — one entry per file that needs to be created.

Your decisions must be:
- Consistent across all files (one pattern, one style, not mixed)
- Appropriate for the project scale (no over-engineering small tools)
- Idiomatic for the chosen language and ecosystem
- Production-quality (not toy examples)

For CLI tools specifically, decide:
- Argument parsing library (argparse, click, typer for Python; commander, yargs for JS; cobra for Go)
- Configuration approach (env vars, config file, flags only)
- Error handling strategy (exit codes, stderr vs stdout, exception hierarchy)
- Logging approach (structured vs plain, verbosity levels)
- Project layout (flat script vs package with submodules)
- Testing framework and test structure

Output ONLY valid JSON:
{
  "architecture_decisions": {
    "argument_parser": "<library and why>",
    "config_approach": "<how config/settings are handled>",
    "error_handling": "<strategy for errors and exit codes>",
    "logging": "<logging approach>",
    "project_layout": "flat|package|monorepo",
    "test_framework": "<framework name>",
    "key_patterns": ["<pattern decisions that affect all files>"]
  },
  "folder_structure": [
    "<relative path>/"
  ],
  "file_manifest": [
    {
      "path": "<relative path to file>",
      "type": "entrypoint|module|config|test|docs|ci|docker|util",
      "purpose": "<one sentence: what this file does>",
      "depends_on": ["<other files in manifest this file imports>"],
      "exports": ["<function/class names this file exposes>"],
      "spec": "<3-5 sentence detailed spec for the generator agent — what to implement, edge cases to handle, patterns to follow>"
    }
  ],
  "install_steps": ["<how to install dependencies>"],
  "run_command": "<how to run the tool>",
  "test_command": "<how to run tests>"
}"""


def design_architecture(spec: dict) -> dict:
    user_input = f"Design the architecture for this CLI project:\n\n{json.dumps(spec, indent=2)}"
    return run_agent(ARCHITECT_PROMPT, user_input, max_tokens=6000, model=SMART_MODEL)


def print_architecture(arch: dict):
    decisions = arch.get("architecture_decisions", {})
    print(f"\n🏗️  ARCHITECTURE DECISIONS")
    print(f"   Parser:    {decisions.get('argument_parser', '?')}")
    print(f"   Config:    {decisions.get('config_approach', '?')}")
    print(f"   Errors:    {decisions.get('error_handling', '?')}")
    print(f"   Logging:   {decisions.get('logging', '?')}")
    print(f"   Layout:    {decisions.get('project_layout', '?')}")
    print(f"   Tests:     {decisions.get('test_framework', '?')}")

    if decisions.get("key_patterns"):
        print(f"\n   Key patterns:")
        for p in decisions["key_patterns"]:
            print(f"     • {p}")

    print(f"\n📁 FILES TO GENERATE ({len(arch.get('file_manifest', []))}):")
    type_icons = {
        "entrypoint": "🚀", "module": "📦", "config": "⚙️",
        "test": "🧪", "docs": "📝", "ci": "🔄", "docker": "🐳", "util": "🔧"
    }
    for f in arch.get("file_manifest", []):
        icon = type_icons.get(f["type"], "📄")
        print(f"   {icon} {f['path']}")
        print(f"      {f['purpose']}")

    print(f"\n▶  Run:   {arch.get('run_command', '?')}")
    print(f"🧪 Test:  {arch.get('test_command', '?')}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python architect_agent.py <project_spec.json>")
        sys.exit(1)

    spec = json.loads(Path(sys.argv[1]).read_text())
    arch = design_architecture(spec)
    print_architecture(arch)

    Path("architecture.json").write_text(json.dumps(arch, indent=2))
    print("\n📄 Architecture saved to: architecture.json")
