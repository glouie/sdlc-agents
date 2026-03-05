"""
token_manager.py — API key management without environment variables.

Designed for use on mobile (iPhone app) or any environment where you
can't set env vars. Stores tokens in a local config file with clear
warnings about security.

Handles:
  - ANTHROPIC_API_KEY  (required for all agents)
  - GITHUB_TOKEN       (required for GitHub push/pull)

Token priority order:
  1. Environment variable (if set — desktop use)
  2. Local config file ~/.sdlc_tokens (saved from previous session)
  3. Interactive prompt (asks user, offers to save)

Usage:
  from core.token_manager import get_token, setup_tokens
  
  # At start of any script that needs tokens:
  setup_tokens()   # ensures all needed tokens are available
  
  # Or get a specific one:
  github_token = get_token("GITHUB_TOKEN")
"""

import os
import json
from pathlib import Path
from getpass import getpass

# Store tokens in home directory, not project directory
# so they persist across projects and don't get committed to git
TOKEN_FILE = Path.home() / ".sdlc_tokens"

TOKEN_DESCRIPTIONS = {
    "ANTHROPIC_API_KEY": {
        "description": "Anthropic API key (powers all AI agents)",
        "how_to_get": "https://console.anthropic.com → API Keys → Create Key",
        "prefix_hint": "sk-ant-",
    },
    "GITHUB_TOKEN": {
        "description": "GitHub Personal Access Token (for repo create/push/read)",
        "how_to_get": "github.com/settings/tokens → New classic token → check 'repo' scope",
        "prefix_hint": "ghp_",
    },
}


def _load_saved_tokens() -> dict:
    """Load tokens from the local config file."""
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_token(key: str, value: str):
    """Save a token to the local config file."""
    tokens = _load_saved_tokens()
    tokens[key] = value
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    # Restrict file permissions on Unix systems
    try:
        TOKEN_FILE.chmod(0o600)
    except Exception:
        pass


def get_token(key: str, required: bool = True) -> str | None:
    """
    Get a token by name. Tries env → saved file → interactive prompt.
    Returns the token value, or None if not required and not found.
    """
    # 1. Check environment variable
    value = os.environ.get(key)
    if value:
        return value

    # 2. Check saved file
    saved = _load_saved_tokens()
    if key in saved and saved[key]:
        return saved[key]

    # 3. Interactive prompt
    if not required:
        return None

    info = TOKEN_DESCRIPTIONS.get(key, {})
    print(f"\n🔑 {key} needed")
    if info.get("description"):
        print(f"   {info['description']}")
    if info.get("how_to_get"):
        print(f"   Get it at: {info['how_to_get']}")

    # Use getpass so token doesn't echo on screen
    try:
        value = getpass(f"   Paste your {key}: ").strip()
    except Exception:
        # getpass may not work in all environments
        value = input(f"   Paste your {key}: ").strip()

    if not value:
        if required:
            raise ValueError(f"{key} is required but was not provided.")
        return None

    # Offer to save
    hint = info.get("prefix_hint", "")
    if hint and not value.startswith(hint):
        print(f"   ⚠️  That doesn't look like a {key} (expected to start with {hint})")
        confirm = input("   Use it anyway? (y/n): ").strip().lower()
        if confirm != "y":
            return get_token(key, required)  # ask again

    save = input(f"   Save to {TOKEN_FILE} so you don't have to paste it again? (y/n) [y]: ").strip().lower()
    if save in ("", "y", "yes"):
        _save_token(key, value)
        print(f"   ✅ Saved to {TOKEN_FILE}")
        print(f"   (Delete this file to remove saved tokens)")
    else:
        print(f"   OK — you'll need to paste it again next session")

    # Also set in current process environment so subprocesses can use it
    os.environ[key] = value
    return value


def setup_tokens(needed: list[str] | None = None):
    """
    Ensure all needed tokens are available. Call at the start of a pipeline.
    Default: sets up both ANTHROPIC_API_KEY and GITHUB_TOKEN.
    """
    if needed is None:
        needed = ["ANTHROPIC_API_KEY", "GITHUB_TOKEN"]

    print("\n🔐 Checking API credentials...")
    all_good = True

    for key in needed:
        try:
            value = get_token(key, required=True)
            # Set in environment for the anthropic client and other libraries
            os.environ[key] = value
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"   ✅ {key}: {masked}")
        except ValueError as e:
            print(f"   ❌ {key}: {e}")
            all_good = False

    if not all_good:
        raise RuntimeError("Missing required credentials. Cannot continue.")

    print()


def clear_saved_token(key: str | None = None):
    """
    Remove a saved token. Pass a key to remove one, or None to remove all.
    """
    if key is None:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            print(f"✅ All saved tokens removed from {TOKEN_FILE}")
        return

    tokens = _load_saved_tokens()
    if key in tokens:
        del tokens[key]
        TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
        print(f"✅ {key} removed from {TOKEN_FILE}")
    else:
        print(f"ℹ️  {key} was not saved")


def list_saved_tokens():
    """Show which tokens are saved (masked values)."""
    tokens = _load_saved_tokens()
    env_tokens = {k for k in TOKEN_DESCRIPTIONS if os.environ.get(k)}

    print(f"\n🔑 Token Status:")
    for key in TOKEN_DESCRIPTIONS:
        if os.environ.get(key):
            val = os.environ[key]
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            print(f"   ✅ {key}: {masked} (from environment)")
        elif key in tokens:
            val = tokens[key]
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            print(f"   💾 {key}: {masked} (saved in {TOKEN_FILE})")
        else:
            print(f"   ❌ {key}: not set")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python token_manager.py setup          — set up all tokens")
        print("  python token_manager.py list           — show token status")
        print("  python token_manager.py clear          — remove all saved tokens")
        print("  python token_manager.py clear <KEY>    — remove one token")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "setup":
        setup_tokens()
        print("✅ All tokens configured.")

    elif cmd == "list":
        list_saved_tokens()

    elif cmd == "clear":
        key = sys.argv[2] if len(sys.argv) > 2 else None
        clear_saved_token(key)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
