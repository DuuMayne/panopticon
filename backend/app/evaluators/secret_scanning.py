from __future__ import annotations

from app.evaluators.base import EvaluatorBase, EvaluationResult, FailingResource


class SecretScanningEvaluator(EvaluatorBase):
    """Check that secret scanning is enabled on all critical repositories.

    Uses the same GitHub connector data (repos), looking for the
    security_settings added by the connector. If the connector doesn't
    provide security_settings, falls back to checking if the field exists.

    Maps to: SOC 2 CC6.1/CC8.1, ISO 27001 A.14.2.5, NIST SA-11/SI-10

    Expected data from connector:
    {
        "repos": [
            {
                "full_name": "org/repo",
                "security_settings": {
                    "secret_scanning": true,
                    "secret_scanning_push_protection": true
                }
            }
        ]
    }
    """

    def evaluate(self, data: dict, config: dict) -> EvaluationResult:
        repos = data.get("repos", [])
        if not repos:
            return EvaluationResult(status="error", summary="No repository data returned from connector")

        non_compliant = []
        for repo in repos:
            sec = repo.get("security_settings", {})
            if not sec.get("secret_scanning"):
                non_compliant.append(repo)

        failures = [
            FailingResource(
                resource_type="repository",
                resource_identifier=r["full_name"],
                details={
                    "secret_scanning": r.get("security_settings", {}).get("secret_scanning", False),
                    "push_protection": r.get("security_settings", {}).get("secret_scanning_push_protection", False),
                },
            )
            for r in non_compliant
        ]

        evidence = {
            "total_repos": len(repos),
            "scanning_enabled": len(repos) - len(non_compliant),
            "scanning_disabled": len(non_compliant),
            "non_compliant_repos": [r["full_name"] for r in non_compliant],
            "repo_details": [
                {
                    "full_name": r["full_name"],
                    "secret_scanning": r.get("security_settings", {}).get("secret_scanning", False),
                    "push_protection": r.get("security_settings", {}).get("secret_scanning_push_protection", False),
                }
                for r in repos
            ],
        }

        if non_compliant:
            return EvaluationResult(
                status="fail",
                summary=f"{len(non_compliant)} of {len(repos)} critical repos do not have secret scanning enabled",
                evidence=evidence,
                failures=failures,
                metadata={"evaluator": "secret_scanning_enabled"},
            )

        return EvaluationResult(
            status="pass",
            summary=f"All {len(repos)} critical repos have secret scanning enabled",
            evidence=evidence,
            metadata={"evaluator": "secret_scanning_enabled"},
        )
