"""
prompt_generator_agent.py — Generates specialized subagent system prompts on
demand for any language or domain. Enables the system to handle languages that
don't have handcrafted agents yet.

Cache persists to .agent_prompt_cache.json so generation only happens once
per language/domain combination.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, load_cache, save_cache, FAST_MODEL

GENERATOR_PROMPT = """You are an expert at writing system prompts for focused AI code review agents.

Given a programming language and a review domain, generate a precise system prompt for that agent.

The generated system prompt must:
- Name 8-15 SPECIFIC things to look for in that language and domain (not generic advice)
- Instruct the agent to output ONLY this exact JSON:
  {"issues": [{"severity": "critical|high|medium|low", "line": <int or null>, "issue": "<description>", "fix": "<suggestion>"}]}
- Be under 400 tokens total
- Contain no preamble, explanation, or markdown — just the raw system prompt text

Output ONLY the raw system prompt text."""

FIXER_GENERATOR_PROMPT = """You are an expert at writing system prompts for focused AI code fixer agents.

Given a programming language and a fix domain, generate a precise system prompt for that fixer agent.

The generated system prompt must:
- Clearly state which domain of issues this fixer handles
- Include explicit constraints on what it must NOT change (other domains)
- Instruct the agent to output ONLY this exact JSON:
  {"fixed_code": "<complete fixed code>", "changes": [{"line": <int or null>, "description": "<what changed>"}]}
- Be under 350 tokens total
- Contain no preamble, explanation, or markdown — just the raw system prompt text

Output ONLY the raw system prompt text."""

REFINER_PROMPT = """You are a system prompt optimizer for AI code review agents.

Given an existing system prompt and a description of an issue it missed or got wrong,
improve the prompt to handle that case correctly.

Output ONLY the improved system prompt text — no preamble, no explanation."""


def get_reviewer_prompt(language: str, domain: str, cache: dict | None = None) -> str:
    if cache is None:
        cache = load_cache()

    key = f"{language}:{domain}:reviewer"
    if key in cache:
        return cache[key]

    print(f"  ⚡ Generating {domain} reviewer prompt for {language}...")
    prompt = run_agent(
        GENERATOR_PROMPT,
        f"Generate a {domain} code review system prompt for: {language}",
        max_tokens=600,
        expect_json=False,
    )
    cache[key] = prompt
    save_cache(cache)
    return prompt


def get_fixer_prompt(language: str, domain: str, cache: dict | None = None) -> str:
    if cache is None:
        cache = load_cache()

    key = f"{language}:{domain}:fixer"
    if key in cache:
        return cache[key]

    print(f"  ⚡ Generating {domain} fixer prompt for {language}...")
    prompt = run_agent(
        FIXER_GENERATOR_PROMPT,
        f"Generate a {domain} code fixer system prompt for: {language}",
        max_tokens=500,
        expect_json=False,
    )
    cache[key] = prompt
    save_cache(cache)
    return prompt


def refine_prompt(language: str, domain: str, role: str, missed_issue: str, cache: dict | None = None) -> str:
    """Improve an existing prompt based on a case it got wrong."""
    if cache is None:
        cache = load_cache()

    key = f"{language}:{domain}:{role}"
    existing = cache.get(key, "")

    improved = run_agent(
        REFINER_PROMPT,
        f"Existing prompt:\n{existing}\n\nMissed/wrong case:\n{missed_issue}",
        max_tokens=600,
        expect_json=False,
    )
    cache[key] = improved
    save_cache(cache)
    print(f"  ✅ Refined {language}:{domain}:{role} prompt")
    return improved


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Usage:
      python prompt_generator_agent.py reviewer ruby security
      python prompt_generator_agent.py fixer python style
      python prompt_generator_agent.py refine bash security reviewer "missed eval usage"
    """
    if len(sys.argv) < 4:
        print("Usage: prompt_generator_agent.py <reviewer|fixer|refine> <language> <domain> [missed_case]")
        sys.exit(1)

    role, lang, domain = sys.argv[1], sys.argv[2], sys.argv[3]
    cache = load_cache()

    if role == "reviewer":
        print(get_reviewer_prompt(lang, domain, cache))
    elif role == "fixer":
        print(get_fixer_prompt(lang, domain, cache))
    elif role == "refine":
        missed = sys.argv[4] if len(sys.argv) > 4 else input("Describe the missed/wrong case: ")
        print(refine_prompt(lang, domain, "reviewer", missed, cache))
