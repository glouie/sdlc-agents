"""
merger_agent.py — Universal merger. Reconciles multiple patched versions of the
same file into one coherent result. Language and domain agnostic.

Used by: code review pipeline, UI review pipeline, any multi-fixer workflow.
"""

import sys
import json
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

MERGER_PROMPT = """You are a code merger agent. You receive an original file and
multiple patched versions of it, each fixing a different category of issues.

Your job: produce one final version that incorporates ALL fixes from ALL versions
without conflicts, duplications, or regressions.

Rules:
- Never drop code that exists in the original unless a fixer explicitly removed it
- When two fixers touch the same area, prefer the more conservative change
- Note any conflicts you had to resolve
- The result must be complete — never truncate

Output ONLY valid JSON:
{
  "final_code": "<complete merged code>",
  "conflicts_resolved": ["<description of any conflict you had to adjudicate>"]
}"""


def merge(original: str, patched_versions: dict[str, str]) -> dict:
    """
    original: the original source code string
    patched_versions: {"domain_name": "patched code string", ...}
    """
    sections = [f"ORIGINAL:\n```\n{original}\n```\n"]
    for domain, code in patched_versions.items():
        sections.append(f"{domain.upper()}-FIXED VERSION:\n```\n{code}\n```\n")

    user_input = "\n".join(sections) + "\nMerge all fixed versions into one final result."

    return run_agent(MERGER_PROMPT, user_input, max_tokens=8192, model=SMART_MODEL)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Usage: python merger_agent.py original.py security_fixed.py style_fixed.py logic_fixed.py
    Reads files, merges, prints result.
    """
    if len(sys.argv) < 3:
        print("Usage: merger_agent.py <original> <fixed1> [fixed2 ...]")
        sys.exit(1)

    original = Path(sys.argv[1]).read_text()
    versions = {}
    for f in sys.argv[2:]:
        p = Path(f)
        label = p.stem.replace("_fixed", "").replace("_", " ")
        versions[label] = p.read_text()

    result = merge(original, versions)
    print(result.get("final_code", ""))
    if result.get("conflicts_resolved"):
        print("\n# Conflicts resolved:", file=sys.stderr)
        for c in result["conflicts_resolved"]:
            print(f"  - {c}", file=sys.stderr)
