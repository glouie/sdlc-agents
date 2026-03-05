"""
project_manager_agent.py — SDLC Phase 1: Planning
Turns requirements into an executable task plan and tracks progress.

Answers: WHEN things happen, in what order, and what's blocked.
Does NOT decide what to build or execute tasks.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

PROJECT_MANAGER_PROMPT = """You are a project manager agent. Turn requirements into a concrete,
sequenced task plan and track its current state.

Given requirements (and optionally previous execution results), you:
- Break each requirement into atomic, executable tasks
- Sequence tasks based on dependencies
- Assign each task to an appropriate agent type
- Identify the critical path
- Track status and surface blockers
- Compute what tasks are executable right now (all dependencies met)

You do NOT decide what to build. You do NOT execute tasks.

Output ONLY valid JSON:
{
  "plan": [
    {
      "task_id": "TASK-001",
      "requirement_id": "REQ-001",
      "title": "<short title>",
      "description": "<specific, actionable task>",
      "agent_type": "<which agent type executes this>",
      "depends_on": ["TASK-xxx"],
      "status": "pending|in_progress|done|blocked|skipped",
      "blocker": "<description if blocked, else null>",
      "result_summary": "<brief result if done, else null>"
    }
  ],
  "critical_path": ["TASK-001", "TASK-003"],
  "next_executable": ["TASK-001", "TASK-002"],
  "progress": {
    "total": 0, "done": 0, "in_progress": 0,
    "pending": 0, "blocked": 0
  },
  "blockers": ["<any current blockers>"],
  "estimated_remaining_tasks": 0
}"""


def build_plan(requirements: dict) -> dict:
    user_input = f"Build a task plan for these requirements:\n{json.dumps(requirements, indent=2)}"
    return run_agent(PROJECT_MANAGER_PROMPT, user_input, max_tokens=3000, model=SMART_MODEL)


def update_plan(current_plan: dict, execution_results: dict) -> dict:
    user_input = (
        f"Update this task plan based on execution results.\n\n"
        f"Current plan:\n{json.dumps(current_plan, indent=2)}\n\n"
        f"Execution results:\n{json.dumps(execution_results, indent=2)}"
    )
    return run_agent(PROJECT_MANAGER_PROMPT, user_input, max_tokens=3000, model=SMART_MODEL)


def print_plan(plan: dict):
    progress = plan.get("progress", {})
    total = progress.get("total", len(plan.get("plan", [])))
    done = progress.get("done", 0)

    print(f"\n📊 Progress: {done}/{total} tasks complete")
    print(f"🔑 Critical path: {' → '.join(plan.get('critical_path', []))}")
    print(f"⚡ Next executable: {plan.get('next_executable', [])}")

    if plan.get("blockers"):
        print(f"\n🚧 Blockers:")
        for b in plan["blockers"]:
            print(f"   • {b}")

    print(f"\n📋 All Tasks:")
    status_icons = {
        "done": "✅", "in_progress": "🔄", "pending": "⏳",
        "blocked": "🚧", "skipped": "⏭️"
    }
    for task in plan.get("plan", []):
        icon = status_icons.get(task["status"], "❓")
        deps = f" (needs: {', '.join(task['depends_on'])})" if task.get("depends_on") else ""
        print(f"   {icon} [{task['task_id']}] {task['title']}{deps}")
        print(f"      Agent: {task['agent_type']} | {task['description']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Usage:
      python project_manager_agent.py requirements.json           # build initial plan
      python project_manager_agent.py requirements.json plan.json results.json  # update plan
    """
    if len(sys.argv) < 2:
        print("Usage: project_manager_agent.py <requirements.json> [plan.json] [results.json]")
        sys.exit(1)

    requirements = json.loads(Path(sys.argv[1]).read_text())

    if len(sys.argv) >= 4:
        current_plan = json.loads(Path(sys.argv[2]).read_text())
        results = json.loads(Path(sys.argv[3]).read_text())
        plan = update_plan(current_plan, results)
        print("Updated plan:")
    else:
        plan = build_plan(requirements)
        print("Initial plan:")

    print_plan(plan)
    Path("plan.json").write_text(json.dumps(plan, indent=2))
    print(f"\n📄 Plan saved to plan.json")
