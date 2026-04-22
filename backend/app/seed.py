"""Seed the database with initial control definitions.

Run directly: python -m app.seed
Idempotent: skips controls that already exist (matched by key).
"""
import logging

from app.database import SessionLocal
from app.models import Control, ControlCurrentState

logger = logging.getLogger("oculus.seed")

CONTROLS = [
    {
        "key": "mfa_enforced",
        "name": "MFA Enforced for All Active Users",
        "description": "Verifies that every active user in the identity provider has MFA enrolled. Flags users with active status but no MFA factors configured.",
        "owner": "Security Engineering",
        "connector_type": "okta",
        "evaluator_type": "mfa_enforced",
        "config_json": {},
    },
    {
        "key": "no_inactive_users",
        "name": "No Stale Inactive Users",
        "description": "Checks that no active users have been inactive beyond the configured threshold. Identifies accounts that should be deprovisioned or reviewed.",
        "owner": "IT Operations",
        "connector_type": "okta",
        "evaluator_type": "no_inactive_users",
        "config_json": {"inactivity_threshold_days": 90},
    },
    {
        "key": "branch_protection",
        "name": "Branch Protection on Critical Repos",
        "description": "Verifies that all configured critical repositories have branch protection enabled on their default branch, including required reviews.",
        "owner": "Platform Engineering",
        "connector_type": "github",
        "evaluator_type": "branch_protection",
        "config_json": {"critical_repos": ["org/api-service", "org/web-app", "org/infra-config"]},
    },
    {
        "key": "no_direct_push",
        "name": "No Direct Push to Main",
        "description": "Verifies that direct pushes to the default branch are blocked on all critical repositories. Ensures all changes go through pull requests.",
        "owner": "Platform Engineering",
        "connector_type": "github",
        "evaluator_type": "no_direct_push",
        "config_json": {"critical_repos": ["org/api-service", "org/web-app", "org/infra-config"]},
    },
    {
        "key": "audit_logging",
        "name": "Cloud Audit Logging Enabled",
        "description": "Verifies that CloudTrail is enabled and actively logging in all configured production AWS accounts.",
        "owner": "Cloud Security",
        "connector_type": "aws",
        "evaluator_type": "audit_logging",
        "config_json": {"production_accounts": ["123456789012", "234567890123"]},
    },
    {
        "key": "root_mfa_enabled",
        "name": "Root Account MFA Enabled",
        "description": "Verifies that the AWS root account has MFA enabled. Root accounts without MFA are a critical security gap across all compliance frameworks.",
        "owner": "Cloud Security",
        "connector_type": "aws_iam",
        "evaluator_type": "root_mfa_enabled",
        "config_json": {},
    },
    {
        "key": "no_stale_access_keys",
        "name": "No Stale IAM Access Keys",
        "description": "Verifies that no active IAM access keys exceed the rotation threshold. Stale keys increase the blast radius of credential compromise.",
        "owner": "Cloud Security",
        "connector_type": "aws_iam",
        "evaluator_type": "no_stale_access_keys",
        "config_json": {"max_key_age_days": 90},
    },
    {
        "key": "encryption_at_rest",
        "name": "S3 Encryption at Rest",
        "description": "Verifies that all S3 buckets have default server-side encryption enabled. Required by PCI DSS, HIPAA, and SOC 2 for data protection.",
        "owner": "Cloud Security",
        "connector_type": "aws_s3",
        "evaluator_type": "encryption_at_rest",
        "config_json": {},
    },
    {
        "key": "no_public_s3",
        "name": "No Public S3 Buckets",
        "description": "Verifies that no S3 buckets allow public access. Public buckets are the #1 cause of cloud data breaches and fail every compliance framework.",
        "owner": "Cloud Security",
        "connector_type": "aws_s3",
        "evaluator_type": "no_public_s3",
        "config_json": {},
    },
    {
        "key": "secret_scanning_enabled",
        "name": "Secret Scanning on Critical Repos",
        "description": "Verifies that GitHub secret scanning is enabled on all critical repositories. Detects accidentally committed credentials before they can be exploited.",
        "owner": "Platform Engineering",
        "connector_type": "github",
        "evaluator_type": "secret_scanning_enabled",
        "config_json": {"critical_repos": ["org/api-service", "org/web-app", "org/infra-config"]},
    },
]


def seed_controls() -> None:
    db = SessionLocal()
    try:
        for ctrl_data in CONTROLS:
            existing = db.query(Control).filter(Control.key == ctrl_data["key"]).first()
            if existing:
                logger.info(f"Control '{ctrl_data['key']}' already exists, skipping")
                continue

            control = Control(**ctrl_data)
            db.add(control)
            db.flush()

            state = ControlCurrentState(control_id=control.id, current_status="pending")
            db.add(state)

            logger.info(f"Seeded control: {ctrl_data['key']}")

        db.commit()
        logger.info("Seed complete")
    except Exception as e:
        logger.error(f"Seed failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_controls()
