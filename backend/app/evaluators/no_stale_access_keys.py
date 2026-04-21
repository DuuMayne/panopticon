from __future__ import annotations

from app.evaluators.base import EvaluatorBase, EvaluationResult, FailingResource


class NoStaleAccessKeysEvaluator(EvaluatorBase):
    """Check that no active IAM access keys exceed the rotation threshold.

    Maps to: SOC 2 CC6.1, ISO 27001 A.9.2.4, PCI DSS 8.2.4, NIST IA-5, CIS 1.4

    Config:
        max_key_age_days: Maximum allowed age for access keys (default 90)
    """

    def evaluate(self, data: dict, config: dict) -> EvaluationResult:
        keys = data.get("access_keys")
        if keys is None:
            return EvaluationResult(status="error", summary="No access key data returned from connector")

        max_age = config.get("max_key_age_days", 90)
        active_keys = [k for k in keys if k.get("status") == "Active"]
        stale = [k for k in active_keys if k.get("created_days_ago", 0) > max_age]

        failures = [
            FailingResource(
                resource_type="access_key",
                resource_identifier=f"{k['user_name']}/{k['access_key_id']}",
                details={
                    "user_name": k["user_name"],
                    "access_key_id": k["access_key_id"],
                    "age_days": k["created_days_ago"],
                    "max_allowed_days": max_age,
                },
            )
            for k in stale
        ]

        evidence = {
            "total_active_keys": len(active_keys),
            "stale_keys": len(stale),
            "compliant_keys": len(active_keys) - len(stale),
            "max_key_age_days": max_age,
            "stale_key_details": [
                {"user": k["user_name"], "key_id": k["access_key_id"], "age_days": k["created_days_ago"]}
                for k in stale
            ],
        }

        if stale:
            return EvaluationResult(
                status="fail",
                summary=f"{len(stale)} active access keys exceed {max_age}-day rotation threshold",
                evidence=evidence,
                failures=failures,
                metadata={"evaluator": "no_stale_access_keys"},
            )

        return EvaluationResult(
            status="pass",
            summary=f"All {len(active_keys)} active access keys are within {max_age}-day rotation threshold",
            evidence=evidence,
            metadata={"evaluator": "no_stale_access_keys"},
        )
