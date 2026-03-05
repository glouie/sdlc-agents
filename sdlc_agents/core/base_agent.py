"""
base_agent.py — Shared agent runner used by all subagents.
All subagents import from here. Keeps each agent file minimal.
"""

import anthropic
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def _get_client():
    import os
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        # Try loading from saved token file without prompting
        # (prompt happens at pipeline start via setup_tokens)
        try:
            from core.token_manager import _load_saved_tokens
            saved = _load_saved_tokens()
            key = saved.get("ANTHROPIC_API_KEY")
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
        except Exception:
            pass
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()

client = _get_client()

# Default model tiers
FAST_MODEL   = "claude-haiku-4-5-20251001"   # subagents — cheap, focused
SMART_MODEL  = "claude-sonnet-4-6"            # orchestrators, mergers, PM agents

CACHE_FILE = Path(".agent_prompt_cache.json")


# ── Core runner ──────────────────────────────────────────────────────────────

def run_agent(
    system_prompt: str,
    user_input: str,
    max_tokens: int = 1024,
    model: str = FAST_MODEL,
    expect_json: bool = True,
) -> dict | str:
    """Run a single agent call. Returns parsed dict if expect_json=True."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_input}],
    )
    text = response.content[0].text.strip()

    if not expect_json:
        return text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"raw": text, "parse_error": True}


def run_agents_parallel(jobs: list[tuple]) -> list:
    """
    Run multiple agents in parallel.
    jobs: list of (system_prompt, user_input, max_tokens, model) tuples
    """
    def _run(job):
        prompt, inp, max_tok, model = job
        return run_agent(prompt, inp, max_tok, model)

    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        return list(ex.map(_run, jobs))


# ── Prompt cache ─────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def get_or_generate_prompt(
    language: str, domain: str, cache: dict, generator_prompt: str
) -> str:
    key = f"{language}:{domain}"
    if key in cache:
        return cache[key]

    print(f"  ⚡ Generating {domain} prompt for {language}...")
    result = run_agent(generator_prompt, f"Generate a {domain} system prompt for: {language}", max_tokens=600)
    prompt = result if isinstance(result, str) else result.get("raw", "")
    cache[key] = prompt
    save_cache(cache)
    return prompt


# ── JSON output contract helper ───────────────────────────────────────────────

ISSUES_JSON_CONTRACT = """
Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "line": <int or null>,
      "issue": "<description>",
      "fix": "<specific, actionable suggestion>"
    }
  ]
}
If no issues found, output: {"issues": []}
"""

FIXER_JSON_CONTRACT = """
Output ONLY valid JSON:
{
  "fixed_code": "<the complete fixed code — never truncate>",
  "changes": [
    {"line": <int or null>, "description": "<what changed and why>"}
  ]
}
"""
