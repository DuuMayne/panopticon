from __future__ import annotations

from app.evaluators.base import EvaluatorBase, EvaluationResult, FailingResource


class NoPublicS3Evaluator(EvaluatorBase):
    """Check that no S3 buckets allow public access.

    Maps to: SOC 2 CC6.1/CC6.6, PCI DSS 1.2/7.1, NIST AC-3/SC-7, CIS 2.1.5, ISO 27001 A.13.1
    """

    def evaluate(self, data: dict, config: dict) -> EvaluationResult:
        buckets = data.get("buckets")
        if buckets is None:
            return EvaluationResult(status="error", summary="No S3 bucket data returned from connector")
        if not buckets:
            return EvaluationResult(status="pass", summary="No S3 buckets found to evaluate", evidence={"total_buckets": 0})

        public = [b for b in buckets if not b.get("public_access_blocked")]

        failures = [
            FailingResource(
                resource_type="s3_bucket",
                resource_identifier=b["name"],
                details={"public_access_blocked": False, "region": b.get("region")},
            )
            for b in public
        ]

        evidence = {
            "total_buckets": len(buckets),
            "private": len(buckets) - len(public),
            "publicly_accessible": len(public),
            "public_buckets": [b["name"] for b in public],
            "bucket_details": [
                {"name": b["name"], "public_access_blocked": b.get("public_access_blocked", False), "region": b.get("region")}
                for b in buckets
            ],
        }

        if public:
            return EvaluationResult(
                status="fail",
                summary=f"{len(public)} of {len(buckets)} S3 buckets do not have public access fully blocked",
                evidence=evidence,
                failures=failures,
                metadata={"evaluator": "no_public_s3"},
            )

        return EvaluationResult(
            status="pass",
            summary=f"All {len(buckets)} S3 buckets have public access blocked",
            evidence=evidence,
            metadata={"evaluator": "no_public_s3"},
        )
