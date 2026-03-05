"""
setup.py — Run this once when you first set up the SDLC agent system.

Does three things:
  1. Installs the only required Python dependency (anthropic)
  2. Collects and saves your API tokens (Anthropic + GitHub)
  3. Verifies everything works with a quick connectivity test

After this, you never need to set environment variables or paste tokens again.
Tokens are saved to ~/.sdlc_tokens (in your home directory).

Usage:
  python setup.py
"""

import subprocess
import sys
from pathlib import Path

def run(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║       SDLC Agent System — First Run Setup    ║")
    print("╚══════════════════════════════════════════════╝\n")

    # ── Step 1: Install dependencies ─────────────────────────────────────────
    print("📦 STEP 1: Installing dependencies...")
    print("   Installing anthropic SDK...")

    if run([sys.executable, "-m", "pip", "install", "anthropic", "--quiet"]):
        print("   ✅ anthropic installed")
    else:
        print("   ⚠️  pip install failed — trying with --user flag...")
        if run([sys.executable, "-m", "pip", "install", "anthropic", "--user", "--quiet"]):
            print("   ✅ anthropic installed (user mode)")
        else:
            print("   ❌ Could not install anthropic.")
            print("   Please run: pip install anthropic")
            print("   Then re-run: python setup.py")
            sys.exit(1)

    # ── Step 2: Collect tokens ────────────────────────────────────────────────
    print("\n🔑 STEP 2: Setting up API credentials")
    print("   Tokens are saved to ~/.sdlc_tokens (your home directory).")
    print("   They are never committed to any git repo.\n")

    sys.path.insert(0, str(Path(__file__).parent))
    from core.token_manager import get_token, TOKEN_FILE

    print("── Anthropic API Key ───────────────────────────────────────")
    print("   Powers all AI agents in the system.")
    print("   Get yours at: https://console.anthropic.com → API Keys\n")
    anthropic_key = get_token("ANTHROPIC_API_KEY", required=True)

    print("\n── GitHub Personal Access Token ────────────────────────────")
    print("   Used to create repos, push code, and read files.")
    print("   Get yours at: github.com/settings/tokens")
    print("   → Click 'New classic token'")
    print("   → Give it a name like 'sdlc-agents'")
    print("   → Check the 'repo' scope checkbox")
    print("   → Click 'Generate token' and copy it\n")
    github_token = get_token("GITHUB_TOKEN", required=True)

    # ── Step 3: Verify connectivity ────────────────────────────────────────────
    print("\n🔬 STEP 3: Verifying connectivity...")

    # Test Anthropic
    import os
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}]
        )
        print("   ✅ Anthropic API: connected")
    except Exception as e:
        print(f"   ❌ Anthropic API error: {e}")
        print("   Check your API key and try again.")
        sys.exit(1)

    # Test GitHub
    os.environ["GITHUB_TOKEN"] = github_token
    try:
        from core.github_client import GitHubClient
        gh = GitHubClient(token=github_token)
        username = gh.username
        print(f"   ✅ GitHub API: connected as {username}")
    except Exception as e:
        print(f"   ❌ GitHub API error: {e}")
        print("   Check your token has 'repo' scope and try again.")
        sys.exit(1)

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════════╗
║              Setup Complete! ✅               ║
╚══════════════════════════════════════════════╝

Tokens saved to: {TOKEN_FILE}
You won't need to enter them again.

─────────────────────────────────────────────────
WHAT TO DO NEXT

Build a new project from scratch:
  python build_orchestrator.py "describe what you want to build"

Resume an existing project:
  python session_agent.py https://github.com/{username}/your-repo
  (or just: python session_agent.py  after first session)

Review existing code:
  python sdlc_orchestrator.py yourfile.py --fix

Manage tokens later:
  python core/token_manager.py list       # see saved tokens
  python core/token_manager.py clear      # remove all tokens
  python core/token_manager.py setup      # re-run token setup
─────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
