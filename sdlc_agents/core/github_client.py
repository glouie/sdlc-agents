"""
github_client.py — All GitHub API operations used by the SDLC agent system.

Handles: repo creation, file read/write, commits, branch management.
All operations are scoped to individual files — never bulk-loads a repo.

Required env var: GITHUB_TOKEN (personal access token with 'repo' scope)
Optional env var: GITHUB_USERNAME (inferred from token if not set)
"""

import os
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GitHub token required. Set GITHUB_TOKEN env var or pass token= argument.\n"
                "Create one at: https://github.com/settings/tokens (needs 'repo' scope)"
            )
        self._username: str | None = None

    # ── Auth + identity ───────────────────────────────────────────────────────

    @property
    def username(self) -> str:
        if not self._username:
            self._username = os.environ.get("GITHUB_USERNAME") or self._get_username()
        return self._username

    def _get_username(self) -> str:
        data = self._request("GET", "/user")
        return data["login"]

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | None:
        url = f"{self.BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise RuntimeError(f"GitHub API {method} {path} → {e.code}: {error_body}") from e

    # ── Repo management ───────────────────────────────────────────────────────

    def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
    ) -> dict:
        """Create a new repository. Returns repo info dict."""
        return self._request("POST", "/user/repos", {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,         # creates initial commit + main branch
            "default_branch": "main",
        })

    def repo_exists(self, owner: str, repo: str) -> bool:
        try:
            self._request("GET", f"/repos/{owner}/{repo}")
            return True
        except RuntimeError:
            return False

    def get_repo(self, owner: str, repo: str) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}")

    # ── File operations ───────────────────────────────────────────────────────

    def read_file(self, owner: str, repo: str, path: str, ref: str = "main") -> str | None:
        """Read a single file's content. Returns text or None if not found."""
        try:
            data = self._request("GET", f"/repos/{owner}/{repo}/contents/{path}?ref={ref}")
            if data and data.get("content"):
                return base64.b64decode(data["content"]).decode("utf-8")
            return None
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise

    def _get_file_sha(self, owner: str, repo: str, path: str, ref: str = "main") -> str | None:
        """Get current SHA of a file (needed to update it)."""
        try:
            data = self._request("GET", f"/repos/{owner}/{repo}/contents/{path}?ref={ref}")
            return data.get("sha") if data else None
        except RuntimeError:
            return None

    def write_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
    ) -> dict:
        """Create or update a single file. Handles SHA automatically."""
        sha = self._get_file_sha(owner, repo, path, branch)
        body = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        return self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", body)

    def write_files_batch(
        self,
        owner: str,
        repo: str,
        files: dict[str, str],
        commit_message: str,
        branch: str = "main",
    ) -> int:
        """
        Write multiple files using the Git Trees API (single commit for all files).
        Much faster than writing one file at a time.
        Returns number of files committed.
        """
        # Get current HEAD SHA
        ref_data = self._request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
        head_sha = ref_data["object"]["sha"]

        # Get current tree SHA
        commit_data = self._request("GET", f"/repos/{owner}/{repo}/git/commits/{head_sha}")
        base_tree_sha = commit_data["tree"]["sha"]

        # Build tree
        tree_items = [
            {
                "path": path,
                "mode": "100644",
                "type": "blob",
                "content": content,
            }
            for path, content in files.items()
        ]

        # Create tree
        tree_data = self._request("POST", f"/repos/{owner}/{repo}/git/trees", {
            "base_tree": base_tree_sha,
            "tree": tree_items,
        })

        # Create commit
        commit = self._request("POST", f"/repos/{owner}/{repo}/git/commits", {
            "message": commit_message,
            "tree": tree_data["sha"],
            "parents": [head_sha],
        })

        # Update branch ref
        self._request("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", {
            "sha": commit["sha"],
        })

        return len(files)

    def list_files(self, owner: str, repo: str, path: str = "", ref: str = "main") -> list[str]:
        """List files in a directory (non-recursive). Returns list of paths."""
        try:
            data = self._request("GET", f"/repos/{owner}/{repo}/contents/{path}?ref={ref}")
            if isinstance(data, list):
                return [item["path"] for item in data if item["type"] == "file"]
            return []
        except RuntimeError:
            return []

    def file_exists(self, owner: str, repo: str, path: str, ref: str = "main") -> bool:
        return self._get_file_sha(owner, repo, path, ref) is not None

    # ── Branch management ─────────────────────────────────────────────────────

    def create_branch(self, owner: str, repo: str, branch: str, from_branch: str = "main"):
        ref_data = self._request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}")
        sha = ref_data["object"]["sha"]
        self._request("POST", f"/repos/{owner}/{repo}/git/refs", {
            "ref": f"refs/heads/{branch}",
            "sha": sha,
        })

    # ── Convenience ───────────────────────────────────────────────────────────

    def repo_url(self, owner: str, repo: str) -> str:
        return f"https://github.com/{owner}/{repo}"

    def clone_url(self, owner: str, repo: str) -> str:
        return f"https://github.com/{owner}/{repo}.git"


# ── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """Quick connectivity test."""
    import sys
    token = sys.argv[1] if len(sys.argv) > 1 else None
    gh = GitHubClient(token)
    print(f"✅ Connected as: {gh.username}")
