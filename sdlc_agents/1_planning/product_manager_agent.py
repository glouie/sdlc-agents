"""
product_manager_agent.py — SDLC Phase 1: Planning
Translates high-level goals into prioritized, scoped requirements.

Answers: WHAT to build and WHY.
Does NOT plan tasks, assign work, or execute anything.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

PRODUCT_MANAGER_PROMPT = """You are a product manager agent. Translate high-level goals into
prioritized, scoped requirements with clear acceptance criteria.

Your responsibilities:
- Restate the goal clearly and measurably
- Break it into discrete, independently deliverable requirements
- Prioritize by user impact vs effort
- Define explicit acceptance criteria for each requirement
- Flag ambiguities that MUST be resolved before work starts
- Define what is explicitly OUT of scope

You do NOT plan tasks, sequence work, or execute anything.

Output ONLY valid JSON:
{
  "goal_summary": "<one sentence restatement>",
  "success_criteria": ["<measurable outcome>"],
  "requirements": [
    {
      "id": "REQ-001",
      "priority": "critical|high|medium|low",
      "title": "<short title>",
      "requirement": "<what must be true when done>",
      "acceptance_criteria": ["<specific, testable condition>"],
      "effort": "small|medium|large",
      "dependencies": ["REQ-xxx"]
    }
  ],
  "out_of_scope": ["<explicit exclusion>"],
  "ambiguities": ["<question that must be answered before work starts>"]
}"""


def analyze_goal(goal: str, context: str = "") -> dict:
    user_input = f"Goal: {goal}"
    if context:
        user_input += f"\n\nContext:\n{context}"
    return run_agent(PRODUCT_MANAGER_PROMPT, user_input, max_tokens=3000, model=SMART_MODEL)


def print_requirements(req: dict):
    print(f"\n🎯 Goal: {req.get('goal_summary', '')}")
    print(f"\n✅ Success Criteria:")
    for c in req.get("success_criteria", []):
        print(f"   • {c}")

    print(f"\n📋 Requirements ({len(req.get('requirements', []))}):")
    for r in req.get("requirements", []):
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(r["priority"], "⚪")
        print(f"   {icon} [{r['id']}] {r['title']} ({r['effort']})")
        print(f"      {r['requirement']}")

    if req.get("out_of_scope"):
        print(f"\n⛔ Out of Scope:")
        for o in req["out_of_scope"]:
            print(f"   • {o}")

    if req.get("ambiguities"):
        print(f"\n⚠️  Ambiguities (must resolve before starting):")
        for a in req["ambiguities"]:
            print(f"   • {a}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Usage: python product_manager_agent.py "Build a user authentication system"
    """
    if len(sys.argv) < 2:
        print('Usage: python product_manager_agent.py "<goal>" [context]')
        sys.exit(1)

    goal = sys.argv[1]
    context = sys.argv[2] if len(sys.argv) > 2 else ""
    result = analyze_goal(goal, context)
    print_requirements(result)
    print(f"\n📄 Full JSON saved to: requirements.json")
    Path("requirements.json").write_text(json.dumps(result, indent=2))
