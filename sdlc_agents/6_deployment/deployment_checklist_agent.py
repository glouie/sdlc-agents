"""
deployment_checklist_agent.py — SDLC Phase 6: Deployment
Reviews code/config for deployment readiness issues.

Scope: environment config, secrets management, logging, rollback, health checks.
Does NOT review code logic or UI — only deployment concerns.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.base_agent import run_agent, SMART_MODEL

DEPLOYMENT_REVIEWER_PROMPT = """You are a deployment readiness reviewer.

Review the given code or configuration for deployment concerns ONLY. Look for:
- Hardcoded environment-specific values (URLs, IPs, ports) that should be env vars
- Debug mode or verbose logging enabled in production code
- Missing or incomplete health check endpoints
- No graceful shutdown handling (SIGTERM not caught)
- Missing rollback strategy or feature flags for risky changes
- Database migrations without backward compatibility
- No rate limiting on public-facing endpoints
- Missing circuit breakers for external service calls
- Secrets or credentials not using a secrets manager (env vars are minimum)
- Missing request timeout configurations
- No retry logic on transient failures
- Logging that may expose PII or sensitive data

Output ONLY valid JSON:
{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "config|secrets|logging|reliability|security|observability",
      "issue": "<description>",
      "fix": "<specific fix>",
      "blocks_deployment": true
    }
  ],
  "deployment_ready": true,
  "blockers": ["<list of critical issues that must be fixed before deploying>"]
}"""

DEPLOYMENT_FIXER_PROMPT = """You are a deployment readiness fixer.

Fix ONLY the deployment issues provided. Do NOT change:
- Business logic
- UI or user-facing behavior
- Code style or structure

You MAY:
- Replace hardcoded values with os.environ / process.env lookups
- Add graceful shutdown handlers
- Add health check endpoints
- Remove debug flags
- Add request timeouts and retry logic

Output ONLY valid JSON:
{
  "fixed_code": "<complete fixed code — never truncate>",
  "changes": [{"description": "<what changed and why>"}],
  "remaining_manual_steps": ["<things that require infrastructure changes, not code changes>"]
}"""

DEPLOYMENT_SUMMARY_PROMPT = """You are a deployment readiness report writer.

Given review findings, produce a clear go/no-go deployment assessment.

Format:
## Deployment Readiness: GO / NO-GO

### Blockers (must fix before deploy)
...

### Warnings (should fix soon)
...

### Recommended Manual Steps
...

Be direct. A "NO-GO" recommendation must be unambiguous."""


def review(code: str) -> dict:
    return run_agent(DEPLOYMENT_REVIEWER_PROMPT, f"Review this for deployment:\n\n{code}", max_tokens=3000, model=SMART_MODEL)


def fix(code: str, issues: list) -> dict:
    fixable = [i for i in issues if not i.get("category") in ["secrets", "observability"]]
    user_input = f"Fix these deployment issues:\n{json.dumps(fixable, indent=2)}\n\nIn this code:\n{code}"
    return run_agent(DEPLOYMENT_FIXER_PROMPT, user_input, max_tokens=8192, model=SMART_MODEL)


def generate_report(findings: dict) -> str:
    return run_agent(
        DEPLOYMENT_SUMMARY_PROMPT,
        f"Findings:\n{json.dumps(findings, indent=2)}",
        max_tokens=2000,
        model=SMART_MODEL,
        expect_json=False,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deployment_checklist_agent.py <file> [--fix]")
        sys.exit(1)

    file_path = sys.argv[1]
    code = Path(file_path).read_text()

    print(f"\n🚀 Deployment Readiness Review: {file_path}\n")
    result = review(code)
    issues = result.get("issues", [])

    ready = result.get("deployment_ready", False)
    blockers = result.get("blockers", [])

    status = "✅ GO" if ready else "🛑 NO-GO"
    print(f"Status: {status}")

    if blockers:
        print(f"\nBlockers:")
        for b in blockers:
            print(f"  🔴 {b}")

    print(f"\nAll Issues ({len(issues)}):")
    for i in issues:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(i["severity"], "⚪")
        blocks = " [BLOCKS DEPLOY]" if i.get("blocks_deployment") else ""
        print(f"  {icon} [{i['category'].upper()}]{blocks} {i['issue']}")
        print(f"     Fix: {i['fix']}")

    print("\n" + "─" * 60)
    report = generate_report(result)
    print(report)

    if "--fix" in sys.argv and issues:
        print("\n🔧 Applying deployment fixes...")
        fixed = fix(code, issues)
        out = Path(file_path).with_stem(Path(file_path).stem + "_deploy_fixed")
        out.write_text(fixed["fixed_code"])
        print(f"✅ Fixed file written to: {out}")

        if fixed.get("remaining_manual_steps"):
            print("\n📋 Manual steps still required:")
            for step in fixed["remaining_manual_steps"]:
                print(f"  • {step}")
