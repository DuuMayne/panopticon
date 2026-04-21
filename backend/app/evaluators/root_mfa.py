from __future__ import annotations

from app.evaluators.base import EvaluatorBase, EvaluationResult, FailingResource


class RootMfaEvaluator(EvaluatorBase):
    """Check that the AWS root account has MFA enabled.

    Maps to: SOC 2 CC6.1, PCI DSS 8.3, NIST AC-2, CIS 1.5
    """

    def evaluate(self, data: dict, config: dict) -> EvaluationResult:
        root = data.get("root_account")
        if not root:
            return EvaluationResult(status="error", summary="No root account data returned from connector")

        if root.get("error"):
            return EvaluationResult(status="error", summary=f"Failed to check root MFA: {root['error']}")

        evidence = {
            "account_id": root.get("account_id"),
            "mfa_enabled": root.get("mfa_enabled", False),
        }

        if not root.get("mfa_enabled"):
            return EvaluationResult(
                status="fail",
                summary=f"Root account {root.get('account_id')} does not have MFA enabled",
                evidence=evidence,
                failures=[FailingResource(
                    resource_type="account",
                    resource_identifier=root.get("account_id", "unknown"),
                    details={"mfa_enabled": False},
                )],
                metadata={"evaluator": "root_mfa_enabled"},
            )

        return EvaluationResult(
            status="pass",
            summary=f"Root account {root.get('account_id')} has MFA enabled",
            evidence=evidence,
            metadata={"evaluator": "root_mfa_enabled"},
        )
