"""
interview_agent.py — Hybrid pipeline: upfront question gathering.

Analyzes a raw goal and generates the minimum set of clarifying questions
needed to fully spec the project. User answers once, then everything runs
automatically.

Design principle: ask the MINIMUM questions needed. Don't ask what can
be inferred or decided by the architect agent. Only ask what genuinely
requires human judgment.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

QUESTION_GENERATOR_PROMPT = """You are a technical project interviewer for CLI tools and scripts.

Given a project goal, generate the MINIMUM set of questions needed to fully
spec the project. Only ask what cannot be reasonably inferred or defaulted.

Rules:
- 3 questions minimum, 8 maximum
- Each question must be essential — if it can be defaulted, don't ask it
- Questions must be answerable in 1-3 sentences by a non-expert
- Cover: scope, language preference, inputs/outputs, key constraints
- Do NOT ask about: folder names, variable names, minor implementation details
- Do NOT ask things the architect agent should decide (library choices, patterns)

Output ONLY valid JSON:
{
  "questions": [
    {
      "id": "Q1",
      "question": "<the question>",
      "why": "<one sentence — why this matters for the build>",
      "default": "<sensible default if user skips it, or null if truly required>"
    }
  ]
}"""

SPEC_BUILDER_PROMPT = """You are a project specification writer for CLI tools.

Given a project goal and answers to clarifying questions, produce a complete,
unambiguous project specification that generation agents can act on.

The spec must define:
- What the CLI tool does (one clear paragraph)
- Primary language and runtime
- Commands / subcommands and their arguments
- Input sources (stdin, files, args, env vars)
- Output format (stdout, files, exit codes)
- Key constraints and non-goals
- Target OS / environment
- Any external dependencies explicitly mentioned by the user

Do NOT invent requirements not implied by the goal or answers.
Do NOT make architectural decisions (that is the architect's job).

Output ONLY valid JSON:
{
  "project_name": "<short-slug-name>",
  "description": "<2-3 sentence summary>",
  "language": "<primary language>",
  "runtime": "<e.g. python3.11+, node18+, bash5+>",
  "commands": [
    {
      "name": "<command or subcommand>",
      "description": "<what it does>",
      "args": ["<arg description>"],
      "flags": ["<--flag description>"],
      "output": "<what it outputs>",
      "exit_codes": {"0": "success", "1": "error"}
    }
  ],
  "inputs": ["<input source descriptions>"],
  "outputs": ["<output descriptions>"],
  "constraints": ["<hard requirements>"],
  "non_goals": ["<explicitly out of scope>"],
  "target_env": "<e.g. Linux/macOS, Docker, CI>",
  "dependencies": ["<external libs or tools mentioned by user>"]
}"""


def generate_questions(goal: str) -> list[dict]:
    result = run_agent(
        QUESTION_GENERATOR_PROMPT,
        f"Project goal: {goal}",
        max_tokens=1500,
        model=SMART_MODEL,
    )
    return result.get("questions", [])


def conduct_interview(goal: str) -> dict:
    """
    Runs the full interview: generates questions, prompts user, collects answers.
    Returns answers dict keyed by question ID.
    """
    print("\n" + "═" * 60)
    print("  PROJECT INTERVIEW")
    print("  Answer these questions, then everything runs automatically.")
    print("  Press Enter to accept the default where shown.")
    print("═" * 60 + "\n")

    questions = generate_questions(goal)
    answers = {}

    for i, q in enumerate(questions, 1):
        print(f"Q{i}: {q['question']}")
        print(f"     (why this matters: {q['why']})")
        if q.get("default"):
            prompt = f"     Your answer [default: {q['default']}]: "
        else:
            prompt = f"     Your answer (required): "

        answer = input(prompt).strip()

        if not answer and q.get("default"):
            answer = q["default"]
            print(f"     → Using default: {answer}")

        answers[q["id"]] = {
            "question": q["question"],
            "answer": answer or q.get("default", ""),
        }
        print()

    return answers


def build_spec(goal: str, answers: dict) -> dict:
    """Turns goal + interview answers into a complete project spec."""
    answers_text = "\n".join(
        f"Q: {v['question']}\nA: {v['answer']}" for v in answers.values()
    )
    user_input = f"Goal: {goal}\n\nInterview answers:\n{answers_text}"
    return run_agent(SPEC_BUILDER_PROMPT, user_input, max_tokens=3000, model=SMART_MODEL)


def print_spec(spec: dict):
    print(f"\n📋 PROJECT SPEC: {spec.get('project_name', '?')}")
    print(f"   {spec.get('description', '')}")
    print(f"   Language: {spec.get('language', '?')} | Runtime: {spec.get('runtime', '?')}")
    print(f"   Environment: {spec.get('target_env', '?')}")

    if spec.get("commands"):
        print(f"\n   Commands:")
        for cmd in spec["commands"]:
            print(f"     • {cmd['name']}: {cmd['description']}")

    if spec.get("constraints"):
        print(f"\n   Constraints:")
        for c in spec["constraints"]:
            print(f"     • {c}")

    if spec.get("non_goals"):
        print(f"\n   Out of scope:")
        for ng in spec["non_goals"]:
            print(f"     • {ng}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python interview_agent.py "<project goal>"')
        sys.exit(1)

    goal = sys.argv[1]
    answers = conduct_interview(goal)
    spec = build_spec(goal, answers)
    print_spec(spec)

    Path("project_spec.json").write_text(json.dumps(spec, indent=2))
    print("\n📄 Spec saved to: project_spec.json")
