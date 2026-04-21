from __future__ import annotations

from app.evaluators.base import EvaluatorBase, EvaluationResult, FailingResource


class EncryptionAtRestEvaluator(EvaluatorBase):
    """Check that all S3 buckets have default encryption enabled.

    Maps to: SOC 2 CC6.7, PCI DSS 3.4, HIPAA 164.312(a)(2)(iv), ISO 27001 A.10.1, NIST SC-28
    """

    def evaluate(self, data: dict, config: dict) -> EvaluationResult:
        buckets = data.get("buckets")
        if buckets is None:
            return EvaluationResult(status="error", summary="No S3 bucket data returned from connector")
        if not buckets:
            return EvaluationResult(status="pass", summary="No S3 buckets found to evaluate", evidence={"total_buckets": 0})

        unencrypted = [b for b in buckets if not b.get("encryption_enabled")]

        failures = [
            FailingResource(
                resource_type="s3_bucket",
                resource_identifier=b["name"],
                details={"encryption_enabled": False, "region": b.get("region")},
            )
            for b in unencrypted
        ]

        evidence = {
            "total_buckets": len(buckets),
            "encrypted": len(buckets) - len(unencrypted),
            "unencrypted": len(unencrypted),
            "unencrypted_buckets": [b["name"] for b in unencrypted],
            "bucket_details": [
                {"name": b["name"], "encrypted": b.get("encryption_enabled", False), "type": b.get("encryption_type"), "region": b.get("region")}
                for b in buckets
            ],
        }

        if unencrypted:
            return EvaluationResult(
                status="fail",
                summary=f"{len(unencrypted)} of {len(buckets)} S3 buckets lack default encryption",
                evidence=evidence,
                failures=failures,
                metadata={"evaluator": "encryption_at_rest"},
            )

        return EvaluationResult(
            status="pass",
            summary=f"All {len(buckets)} S3 buckets have default encryption enabled",
            evidence=evidence,
            metadata={"evaluator": "encryption_at_rest"},
        )
