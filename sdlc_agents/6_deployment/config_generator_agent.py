"""
config_generator_agent.py — SDLC Phase 6: Deployment (Generation)
Generates all deployment and infrastructure configuration files.

Generates:
  - Dockerfile (multi-stage, non-root)
  - docker-compose.yml (for local dev)
  - .github/workflows/ci.yml (lint + test + build)
  - Makefile (developer convenience commands)
  - .env.example (documents all env vars)
  - .dockerignore

These are generated AFTER code generation so they can reference actual
project structure, dependencies, and commands.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

DOCKERFILE_PROMPT = """You are a Docker expert specializing in CLI tools.

Generate a production-quality multi-stage Dockerfile for this CLI project.

Requirements:
- Multi-stage: builder stage + minimal runtime stage
- Non-root user in runtime stage
- Layer caching optimized (dependencies before code)
- Appropriate base image for the language/runtime
- ENTRYPOINT set to the CLI tool
- Labels with metadata
- No unnecessary packages in runtime image

Output ONLY the raw Dockerfile content."""

DOCKER_COMPOSE_PROMPT = """You are a Docker Compose expert.

Generate a docker-compose.yml for local development of this CLI tool.

Include:
- Service for the CLI tool itself
- Volume mounts for local development (code + data dirs)
- Environment variable handling via .env file
- Any supporting services needed (databases, etc.) only if the spec requires them
- Appropriate restart policies

Output ONLY the raw docker-compose.yml content."""

GITHUB_ACTIONS_PROMPT = """You are a GitHub Actions CI/CD expert for CLI tools.

Generate a complete .github/workflows/ci.yml workflow.

Include jobs for:
1. lint — code style and static analysis
2. test — run the full test suite with coverage
3. build — verify the tool builds/installs correctly
4. (optional) release — if the project uses semantic versioning

Requirements:
- Matrix testing across relevant OS/runtime versions
- Dependency caching
- Test coverage reporting
- Fail fast on lint errors
- Artifact upload for built binaries if applicable

Output ONLY the raw YAML content."""

MAKEFILE_PROMPT = """You are an expert at writing Makefiles for CLI tool projects.

Generate a Makefile with developer convenience targets.

Include targets for:
- install: install dependencies
- dev: install with dev dependencies
- test: run tests
- lint: run linter/formatter check
- format: auto-format code
- build: build/package the tool
- docker-build: build Docker image
- docker-run: run via Docker
- clean: remove build artifacts
- help: print available targets (with descriptions)

Use .PHONY declarations. Include a help target that prints all targets.

Output ONLY the raw Makefile content."""

ENV_EXAMPLE_PROMPT = """You are a documentation specialist for CLI tools.

Generate a .env.example file that documents all environment variables
this project uses.

For each variable include:
- The variable name
- A comment explaining what it does
- An example value (never a real secret)
- Whether it is required or optional

Format:
# Description of what this var does
# Required | Optional
VAR_NAME=example_value

Output ONLY the raw .env.example content."""

DOCKERIGNORE_PROMPT = """Generate a .dockerignore file for this CLI project.

Exclude: test files, docs, .git, IDE files, local dev artifacts,
node_modules or venv equivalents, coverage reports, build artifacts.

Output ONLY the raw .dockerignore content."""


GENERATORS = {
    "Dockerfile":                    DOCKERFILE_PROMPT,
    "docker-compose.yml":            DOCKER_COMPOSE_PROMPT,
    ".github/workflows/ci.yml":      GITHUB_ACTIONS_PROMPT,
    "Makefile":                      MAKEFILE_PROMPT,
    ".env.example":                  ENV_EXAMPLE_PROMPT,
    ".dockerignore":                 DOCKERIGNORE_PROMPT,
}


def generate_config_file(filename: str, spec: dict, arch: dict, project_files: list) -> str:
    prompt = GENERATORS.get(filename)
    if not prompt:
        raise ValueError(f"No generator for: {filename}")

    context = (
        f"Project spec:\n{json.dumps(spec, indent=2)}\n\n"
        f"Architecture decisions:\n{json.dumps(arch.get('architecture_decisions', {}), indent=2)}\n\n"
        f"Files in project:\n{json.dumps(project_files, indent=2)}\n\n"
        f"Install steps: {arch.get('install_steps', [])}\n"
        f"Run command: {arch.get('run_command', '')}\n"
        f"Test command: {arch.get('test_command', '')}"
    )

    return run_agent(prompt, context, max_tokens=3000, model=SMART_MODEL, expect_json=False)


def generate_all_configs(
    spec: dict,
    arch: dict,
    output_dir: Path,
    project_files: list,
) -> dict[str, str]:
    """Generate all deployment config files."""
    generated = {}

    print(f"\n  🐳 Generating deployment configs...")
    for filename, _ in GENERATORS.items():
        print(f"     ⚙️  Generating {filename}...")
        content = generate_config_file(filename, spec, arch, project_files)
        generated[filename] = content

        full_path = output_dir / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    return generated


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python config_generator_agent.py <project_spec.json> <architecture.json> [output_dir]")
        sys.exit(1)

    spec = json.loads(Path(sys.argv[1]).read_text())
    arch = json.loads(Path(sys.argv[2]).read_text())
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(spec.get("project_name", "output"))

    project_files = [f["path"] for f in arch.get("file_manifest", [])]
    generated = generate_all_configs(spec, arch, output_dir, project_files)

    print(f"\n✅ Generated {len(generated)} config files in {output_dir}/")
