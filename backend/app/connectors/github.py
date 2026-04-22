from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.connectors.base import ConnectorBase, register_connector

logger = logging.getLogger("oculus.connectors.github")


@register_connector
class GitHubConnector(ConnectorBase):
    """Fetches branch protection settings from GitHub REST API.

    Requires GITHUB_TOKEN environment variable.
    Reads critical_repos list from control config_json.
    """

    connector_type = "github"
    required_env = ["github_token"]
    mock_data = {
        "repos": [
            {"full_name": "org/api-service", "default_branch": "main", "branch_protection": {"enabled": True, "required_reviews": 1, "enforce_admins": True, "restrict_pushes": True, "dismiss_stale_reviews": True, "required_status_checks": True, "require_linear_history": False}, "security_settings": {"secret_scanning": True, "secret_scanning_push_protection": True}},
            {"full_name": "org/web-app", "default_branch": "main", "branch_protection": {"enabled": True, "required_reviews": 2, "enforce_admins": False, "restrict_pushes": False, "dismiss_stale_reviews": False, "required_status_checks": True, "require_linear_history": False}, "security_settings": {"secret_scanning": True, "secret_scanning_push_protection": False}},
            {"full_name": "org/infra-config", "default_branch": "main", "branch_protection": None, "security_settings": {"secret_scanning": False, "secret_scanning_push_protection": False}},
        ]
    }

    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def test_connection(self) -> bool:
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/user",
                headers=self.headers,
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False

    def fetch(self, config: dict) -> dict:
        critical_repos = config.get("critical_repos", [])
        if not critical_repos:
            logger.warning("No critical_repos configured")
            return {"repos": []}

        repos = []
        for repo_full_name in critical_repos:
            repo_data = self._fetch_repo_protection(repo_full_name)
            repo_data["security_settings"] = self._fetch_security_settings(repo_full_name)
            repos.append(repo_data)

        logger.info(f"Fetched protection and security data for {len(repos)} repos")
        return {"repos": repos}

    def _fetch_repo_protection(self, repo_full_name: str) -> dict:
        """Fetch default branch and its protection settings for a repo."""
        # Get repo metadata for default branch
        try:
            repo_resp = httpx.get(
                f"{self.BASE_URL}/repos/{repo_full_name}",
                headers=self.headers,
                timeout=10,
            )
            repo_resp.raise_for_status()
            repo_info = repo_resp.json()
            default_branch = repo_info.get("default_branch", "main")
        except Exception as e:
            logger.error(f"Failed to fetch repo {repo_full_name}: {e}")
            return {
                "full_name": repo_full_name,
                "default_branch": "unknown",
                "branch_protection": None,
                "error": str(e),
            }

        # Get branch protection
        try:
            prot_resp = httpx.get(
                f"{self.BASE_URL}/repos/{repo_full_name}/branches/{default_branch}/protection",
                headers=self.headers,
                timeout=10,
            )

            if prot_resp.status_code == 404:
                return {
                    "full_name": repo_full_name,
                    "default_branch": default_branch,
                    "branch_protection": None,
                }

            prot_resp.raise_for_status()
            prot = prot_resp.json()

            # Normalize the protection data
            required_reviews = prot.get("required_pull_request_reviews")
            restrictions = prot.get("restrictions")

            return {
                "full_name": repo_full_name,
                "default_branch": default_branch,
                "branch_protection": {
                    "enabled": True,
                    "required_reviews": required_reviews.get("required_approving_review_count", 0) if required_reviews else 0,
                    "dismiss_stale_reviews": required_reviews.get("dismiss_stale_reviews", False) if required_reviews else False,
                    "enforce_admins": prot.get("enforce_admins", {}).get("enabled", False),
                    "required_status_checks": prot.get("required_status_checks") is not None,
                    "restrict_pushes": restrictions is not None,
                    "require_linear_history": prot.get("required_linear_history", {}).get("enabled", False),
                },
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "full_name": repo_full_name,
                    "default_branch": default_branch,
                    "branch_protection": None,
                }
            logger.error(f"Failed to fetch protection for {repo_full_name}/{default_branch}: {e}")
            return {
                "full_name": repo_full_name,
                "default_branch": default_branch,
                "branch_protection": None,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Failed to fetch protection for {repo_full_name}: {e}")
            return {
                "full_name": repo_full_name,
                "default_branch": default_branch,
                "branch_protection": None,
                "error": str(e),
            }

    def _fetch_security_settings(self, repo_full_name: str) -> dict:
        """Fetch secret scanning and push protection status for a repo."""
        try:
            resp = httpx.get(
                f"{self.BASE_URL}/repos/{repo_full_name}",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            repo = resp.json()
            security = repo.get("security_and_analysis", {}) or {}
            return {
                "secret_scanning": security.get("secret_scanning", {}).get("status") == "enabled",
                "secret_scanning_push_protection": security.get("secret_scanning_push_protection", {}).get("status") == "enabled",
            }
        except Exception as e:
            logger.warning(f"Failed to fetch security settings for {repo_full_name}: {e}")
            return {"secret_scanning": False, "secret_scanning_push_protection": False}
