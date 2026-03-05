"""
code_generator_agent.py — SDLC Phase 3: Development (Generation)
Generates a single source file from its spec + architecture context.

Key design: each agent call gets:
  - The project spec (what the whole project does)
  - The architecture decisions (patterns to follow)
  - The specific file's spec (what THIS file must implement)
  - Signatures of files it depends on (for correct imports)

It does NOT get the content of other files — only their exported signatures.
This keeps context minimal while ensuring consistency.
"""

import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

CODE_GENERATOR_PROMPT = """You are an expert CLI tool developer.

Generate production-quality code for a single file based on:
1. The overall project spec (what the whole tool does)
2. Architecture decisions (patterns ALL files must follow)
3. This file's specific spec (what THIS file implements)
4. Dependency signatures (what you can import from other files)

Rules:
- Follow the architecture decisions exactly — do not deviate
- Implement everything in the file spec — no stubs, no TODOs
- Write idiomatic, production-quality code
- Include proper error handling per the architecture's error strategy
- Include docstrings / comments on non-obvious logic
- Use the exact function/class names listed in the file's exports
- Import only from files listed in depends_on

Output ONLY the raw file content — no JSON wrapper, no markdown fences,
no explanation. Just the code."""

TEST_GENERATOR_PROMPT = """You are an expert at writing thorough tests for CLI tools.

Generate a complete test file for the given source file based on:
1. The source file's content
2. The test framework specified in architecture decisions
3. The project spec (for understanding expected behavior)

Rules:
- Cover happy path, edge cases, and error conditions
- Mock external dependencies (filesystem, network, subprocess)
- Test CLI argument parsing end-to-end where relevant
- Use descriptive test names
- Include setup/teardown for any shared state
- Tests must be runnable with the specified test command

Output ONLY the raw test file content — no JSON wrapper, no fences."""

SCAFFOLD_PROMPT = """You are a project scaffolding expert.

Generate the content for a non-code project file based on its type and spec.
This may be: README, Dockerfile, docker-compose.yml, .github/workflows/*.yml,
.env.example, Makefile, pyproject.toml, package.json, requirements.txt, etc.

Rules:
- Follow best practices for the file type
- Make it production-ready, not a template with TODOs
- For CI files: include lint, test, and build steps
- For Docker: use multi-stage builds where appropriate, non-root user
- For README: include install, usage, examples, and development sections

Output ONLY the raw file content — no JSON wrapper."""


def _build_generator_input(
    file_entry: dict,
    spec: dict,
    arch: dict,
    dep_signatures: dict,
) -> str:
    """Build the minimal context input for a generator agent."""
    parts = [
        f"PROJECT SPEC:\n{json.dumps(spec, indent=2)}",
        f"\nARCHITECTURE DECISIONS:\n{json.dumps(arch.get('architecture_decisions', {}), indent=2)}",
        f"\nTHIS FILE:\n{json.dumps(file_entry, indent=2)}",
    ]
    if dep_signatures:
        parts.append(f"\nDEPENDENCY SIGNATURES (what you can import):\n{json.dumps(dep_signatures, indent=2)}")
    return "\n".join(parts)


def generate_source_file(
    file_entry: dict,
    spec: dict,
    arch: dict,
    dep_signatures: dict,
) -> str:
    """Generate a single source or config file."""
    file_type = file_entry.get("type", "module")

    if file_type in ("test",):
        prompt = TEST_GENERATOR_PROMPT
    elif file_type in ("config", "docs", "ci", "docker"):
        prompt = SCAFFOLD_PROMPT
    else:
        prompt = CODE_GENERATOR_PROMPT

    user_input = _build_generator_input(file_entry, spec, arch, dep_signatures)
    return run_agent(prompt, user_input, max_tokens=6000, model=SMART_MODEL, expect_json=False)


def generate_all_files(
    spec: dict,
    arch: dict,
    output_dir: Path,
    generate_tests: bool = True,
) -> dict[str, str]:
    """
    Generate all files in the manifest, respecting dependency order.
    Returns dict of {path: content}.
    """
    manifest = arch.get("file_manifest", [])
    generated: dict[str, str] = {}   # path → content
    signatures: dict[str, list] = {} # path → exports list

    # Separate test files so we generate them after their sources
    source_files = [f for f in manifest if f["type"] != "test"]
    test_files   = [f for f in manifest if f["type"] == "test"]

    def _topo_sort(files: list) -> list:
        """Simple topological sort by depends_on."""
        remaining = list(files)
        ordered = []
        visited = set()
        max_iters = len(remaining) * 2

        for _ in range(max_iters):
            if not remaining:
                break
            progress = False
            for f in list(remaining):
                deps = f.get("depends_on", [])
                if all(d in visited for d in deps):
                    ordered.append(f)
                    visited.add(f["path"])
                    remaining.remove(f)
                    progress = True
            if not progress:
                # Circular or missing deps — add remaining as-is
                ordered.extend(remaining)
                break

        return ordered

    ordered_sources = _topo_sort(source_files)

    # Generate source files in dependency order
    print(f"\n  📝 Generating {len(ordered_sources)} source files...")
    for file_entry in ordered_sources:
        path = file_entry["path"]
        file_type = file_entry.get("type", "module")
        icon = {"entrypoint": "🚀", "module": "📦", "config": "⚙️",
                "docs": "📝", "ci": "🔄", "docker": "🐳", "util": "🔧"}.get(file_type, "📄")

        print(f"     {icon} Generating {path}...")

        # Only pass signatures of direct dependencies
        dep_sigs = {
            dep: signatures.get(dep, [])
            for dep in file_entry.get("depends_on", [])
        }

        content = generate_source_file(file_entry, spec, arch, dep_sigs)
        generated[path] = content
        signatures[path] = file_entry.get("exports", [])

        # Write to disk immediately
        full_path = output_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    # Generate test files after sources (they reference source content)
    if generate_tests and test_files:
        print(f"\n  🧪 Generating {len(test_files)} test files...")
        for file_entry in test_files:
            path = file_entry["path"]
            print(f"     🧪 Generating {path}...")

            # Test files get the source file content they're testing
            dep_sigs = {}
            for dep in file_entry.get("depends_on", []):
                if dep in generated:
                    dep_sigs[dep] = generated[dep]  # full content for tests

            content = generate_source_file(file_entry, spec, arch, dep_sigs)
            generated[path] = content

            full_path = output_dir / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    return generated


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python code_generator_agent.py <project_spec.json> <architecture.json> [output_dir]")
        sys.exit(1)

    spec = json.loads(Path(sys.argv[1]).read_text())
    arch = json.loads(Path(sys.argv[2]).read_text())
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(spec.get("project_name", "output"))

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}")

    generated = generate_all_files(spec, arch, output_dir)
    print(f"\n✅ Generated {len(generated)} files in {output_dir}/")
