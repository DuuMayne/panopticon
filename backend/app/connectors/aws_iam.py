from __future__ import annotations

import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.connectors.base import ConnectorBase, register_connector

logger = logging.getLogger("oculus.connectors.aws_iam")


@register_connector
class AWSIAMConnector(ConnectorBase):
    """Fetches IAM data: root account MFA status, access key metadata.

    Uses the same AWS credentials as the CloudTrail connector.
    """

    connector_type = "aws_iam"
    required_env = ["aws_access_key_id"]
    mock_data = {
        "root_account": {
            "account_id": "123456789012",
            "mfa_enabled": True,
        },
        "access_keys": [
            {"user_name": "deploy-bot", "access_key_id": "AKIA1111", "status": "Active", "created_days_ago": 45},
            {"user_name": "ci-runner", "access_key_id": "AKIA2222", "status": "Active", "created_days_ago": 200},
            {"user_name": "legacy-svc", "access_key_id": "AKIA3333", "status": "Active", "created_days_ago": 400},
            {"user_name": "rotated-svc", "access_key_id": "AKIA4444", "status": "Active", "created_days_ago": 30},
        ],
    }

    def test_connection(self) -> bool:
        try:
            iam = boto3.client("iam", region_name=settings.aws_default_region)
            iam.get_account_summary()
            return True
        except Exception as e:
            logger.error(f"AWS IAM connection test failed: {e}")
            return False

    def fetch(self, config: dict) -> dict:
        iam = boto3.client("iam", region_name=settings.aws_default_region)
        sts = boto3.client("sts", region_name=settings.aws_default_region)

        result = {}

        # Root MFA
        try:
            account_id = sts.get_caller_identity()["Account"]
            summary = iam.get_account_summary()["SummaryMap"]
            result["root_account"] = {
                "account_id": account_id,
                "mfa_enabled": summary.get("AccountMFAEnabled", 0) == 1,
            }
        except Exception as e:
            logger.error(f"Failed to check root MFA: {e}")
            result["root_account"] = {"account_id": "unknown", "mfa_enabled": False, "error": str(e)}

        # Access keys for all IAM users
        try:
            access_keys = []
            paginator = iam.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page["Users"]:
                    keys_resp = iam.list_access_keys(UserName=user["UserName"])
                    for key in keys_resp["AccessKeyMetadata"]:
                        age_days = (datetime.now(timezone.utc) - key["CreateDate"].replace(tzinfo=timezone.utc)).days
                        access_keys.append({
                            "user_name": user["UserName"],
                            "access_key_id": key["AccessKeyId"],
                            "status": key["Status"],
                            "created_days_ago": age_days,
                        })
            result["access_keys"] = access_keys
            logger.info(f"Fetched {len(access_keys)} access keys from IAM")
        except Exception as e:
            logger.error(f"Failed to fetch access keys: {e}")
            result["access_keys"] = []

        return result
