"""
test_generator_agent.py — SDLC Phase 5: Testing
Analyzes code and generates appropriate unit tests.

Scope: test case identification, test code generation, edge case coverage.
Supports: bash (bats), python (pytest), javascript (jest). Others on demand.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL, load_cache
from core.prompt_generator_agent import get_reviewer_prompt

TEST_ANALYZER_PROMPT = """You are a test coverage analyzer.

Given source code, identify what needs to be tested. Look for:
- Public functions and their expected behaviors
- Edge cases: empty input, null/None, zero, negative numbers, max values
- Error conditions that should be handled
- Happy path scenarios for each function
- Boundary conditions in loops and conditionals
- Async operations that need proper test handling

Do NOT generate test code yet — only identify what to test.

Output ONLY valid JSON:
{
  "test_cases": [
    {
      "target": "<function or behavior name>",
      "scenario": "<what is being tested>",
      "type": "happy_path|edge_case|error_condition|boundary",
      "inputs": "<description of test input>",
      "expected": "<description of expected outcome>"
    }
  ]
}"""

PYTEST_GENERATOR_PROMPT = """You are a pytest test writer.

Given source code and a list of test cases to implement, write complete pytest tests.

Rules:
- Use pytest fixtures where appropriate
- Use parametrize for data-driven tests
- Include descriptive test names (test_function_when_condition_then_result)
- Mock external dependencies (file system, network, databases)
- Include both positive and negative assertions
- Add docstrings explaining what each test verifies
- Import the module under test correctly

Output ONLY the complete Python test file content (no JSON wrapper)."""

JEST_GENERATOR_PROMPT = """You are a Jest test writer.

Given source code and a list of test cases to implement, write complete Jest tests.

Rules:
- Use describe blocks to group related tests
- Use clear test names that describe behavior
- Mock modules with jest.mock() where needed
- Use beforeEach/afterEach for setup/teardown
- Test both resolved and rejected promises for async code
- Include expect assertions with specific matchers

Output ONLY the complete JavaScript test file content (no JSON wrapper)."""

BATS_GENERATOR_PROMPT = """You are a BATS (Bash Automated Testing System) test writer.

Given a bash script and test cases, write complete BATS tests.

Rules:
- Use @test for each test case
- Use setup() and teardown() functions for temp file handling
- Test exit codes with [ "$status" -eq 0 ]
- Test output with [[ "$output" == *"expected"* ]]
- Mock external commands with function overrides in setup
- Clean up any side effects in teardown

Output ONLY the complete .bats test file content (no JSON wrapper)."""

GENERATORS = {
    "python": ("pytest", PYTEST_GENERATOR_PROMPT, "_test.py"),
    "py":     ("pytest", PYTEST_GENERATOR_PROMPT, "_test.py"),
    "javascript": ("jest", JEST_GENERATOR_PROMPT, ".test.js"),
    "js":         ("jest", JEST_GENERATOR_PROMPT, ".test.js"),
    "typescript": ("jest", JEST_GENERATOR_PROMPT, ".test.ts"),
    "ts":         ("jest", JEST_GENERATOR_PROMPT, ".test.ts"),
    "bash": ("bats", BATS_GENERATOR_PROMPT, ".bats"),
    "sh":   ("bats", BATS_GENERATOR_PROMPT, ".bats"),
}


def _get_language(file_path: str) -> str:
    return Path(file_path).suffix.lstrip(".").lower()


def analyze_test_cases(code: str) -> dict:
    return run_agent(TEST_ANALYZER_PROMPT, f"Analyze this code:\n\n{code}", max_tokens=3000, model=SMART_MODEL)


def generate_tests(code: str, language: str, test_cases: list) -> str:
    lang = language.lower()

    if lang in GENERATORS:
        framework, prompt, _ = GENERATORS[lang]
    else:
        # On-the-fly for unknown languages
        cache = load_cache()
        prompt = get_reviewer_prompt(lang, "test_generation", cache)
        framework = f"{lang}_test"

    user_input = (
        f"Source code:\n```{lang}\n{code}\n```\n\n"
        f"Test cases to implement:\n{json.dumps(test_cases, indent=2)}\n\n"
        f"Generate complete {framework} tests for all of these cases."
    )
    return run_agent(prompt, user_input, max_tokens=6000, model=SMART_MODEL, expect_json=False)


def get_test_extension(language: str) -> str:
    lang = language.lower()
    if lang in GENERATORS:
        return GENERATORS[lang][2]
    return f".{lang}_test"


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_generator_agent.py <file> [--language <lang>]")
        sys.exit(1)

    file_path = sys.argv[1]
    code = Path(file_path).read_text()
    language = sys.argv[sys.argv.index("--language") + 1] if "--language" in sys.argv else _get_language(file_path)

    print(f"\n🧪 Analyzing test cases for {file_path}...")
    analysis = analyze_test_cases(code)
    test_cases = analysis.get("test_cases", [])
    print(f"   → Identified {len(test_cases)} test cases")

    for tc in test_cases:
        icon = {"happy_path": "✅", "edge_case": "⚠️", "error_condition": "❌", "boundary": "📏"}.get(tc["type"], "🔹")
        print(f"  {icon} {tc['target']}: {tc['scenario']}")

    print(f"\n📝 Generating tests...")
    test_code = generate_tests(code, language, test_cases)

    ext = get_test_extension(language)
    stem = Path(file_path).stem
    out_path = Path(file_path).parent / f"test_{stem}{ext}"
    out_path.write_text(test_code)
    print(f"✅ Tests written to: {out_path}")
