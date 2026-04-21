from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.connectors.base import ConnectorBase, register_connector

logger = logging.getLogger("panopticon.connectors.okta")


@register_connector
class OktaConnector(ConnectorBase):
    """Fetches user and MFA data from Okta Admin API.

    Requires OKTA_DOMAIN and OKTA_API_TOKEN environment variables.
    Returns normalized user list with MFA enrollment status.
    """

    connector_type = "okta"
    required_env = ["okta_domain", "okta_api_token"]
    mock_data = {
        "users": [
            {"id": "u1", "email": "alice@example.com", "status": "ACTIVE", "mfa_enrolled": True, "mfa_factors": ["okta_verify"], "last_login": "2026-04-18T10:00:00Z"},
            {"id": "u2", "email": "bob@example.com", "status": "ACTIVE", "mfa_enrolled": True, "mfa_factors": ["okta_verify", "sms"], "last_login": "2026-04-15T14:30:00Z"},
            {"id": "u3", "email": "charlie@example.com", "status": "ACTIVE", "mfa_enrolled": False, "mfa_factors": [], "last_login": "2026-03-01T09:00:00Z"},
            {"id": "u4", "email": "dana@example.com", "status": "ACTIVE", "mfa_enrolled": True, "mfa_factors": ["webauthn"], "last_login": "2026-04-19T16:00:00Z"},
            {"id": "u5", "email": "eve@example.com", "status": "DEPROVISIONED", "mfa_enrolled": False, "mfa_factors": [], "last_login": "2025-12-01T08:00:00Z"},
            {"id": "u6", "email": "frank@example.com", "status": "ACTIVE", "mfa_enrolled": False, "mfa_factors": [], "last_login": "2026-01-10T11:00:00Z"},
        ]
    }

    def __init__(self):
        self.base_url = f"https://{settings.okta_domain}"
        self.headers = {
            "Authorization": f"SSWS {settings.okta_api_token}",
            "Accept": "application/json",
        }

    def test_connection(self) -> bool:
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/users?limit=1",
                headers=self.headers,
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Okta connection test failed: {e}")
            return False

    def fetch(self, config: dict) -> dict:
        users = self._fetch_users()
        for user in users:
            if user["status"] == "ACTIVE":
                factors = self._fetch_factors(user["id"])
                user["mfa_enrolled"] = len(factors) > 0
                user["mfa_factors"] = [f["factorType"] for f in factors]
            else:
                user["mfa_enrolled"] = False
                user["mfa_factors"] = []
        return {"users": users}

    def _fetch_users(self) -> list[dict]:
        """Fetch all users with pagination."""
        users = []
        url = f"{self.base_url}/api/v1/users?limit=200"

        while url:
            logger.debug(f"Fetching users: {url}")
            resp = httpx.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()

            for u in resp.json():
                users.append({
                    "id": u["id"],
                    "email": u.get("profile", {}).get("email", ""),
                    "login": u.get("profile", {}).get("login", ""),
                    "status": u.get("status", "UNKNOWN"),
                    "last_login": u.get("lastLogin"),
                    "created": u.get("created"),
                })

            # Follow pagination via Link header
            url = self._next_link(resp.headers.get("link"))

        logger.info(f"Fetched {len(users)} users from Okta")
        return users

    def _fetch_factors(self, user_id: str) -> list[dict]:
        """Fetch enrolled MFA factors for a single user."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/users/{user_id}/factors",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            return [f for f in resp.json() if f.get("status") == "ACTIVE"]
        except Exception as e:
            logger.warning(f"Failed to fetch factors for user {user_id}: {e}")
            return []

    @staticmethod
    def _next_link(link_header: str | None) -> str | None:
        """Parse Okta's Link header for next page URL."""
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                return url
        return None
