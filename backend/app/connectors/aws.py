from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings
from app.connectors.base import ConnectorBase, register_connector

logger = logging.getLogger("panopticon.connectors.aws")


@register_connector
class AWSConnector(ConnectorBase):
    """Fetches CloudTrail status from AWS accounts.

    Requires AWS credentials via environment variables or IAM role.
    For multi-account setups, uses STS AssumeRole if role_arn is provided
    in the account config. Otherwise uses default credentials for a single account.

    Expected config_json:
    {
        "production_accounts": [
            {"account_id": "123456789012", "role_arn": "arn:aws:iam::123456789012:role/PanopticonAudit"}
        ]
    }
    Or simple list of account IDs (uses default credentials):
    {
        "production_accounts": ["123456789012", "234567890123"]
    }
    """

    connector_type = "aws"
    required_env = ["aws_access_key_id"]
    mock_data = {
        "accounts": [
            {"account_id": "123456789012", "account_name": "prod-us", "cloudtrail_enabled": True, "is_logging": True, "trail_name": "org-trail"},
            {"account_id": "234567890123", "account_name": "prod-eu", "cloudtrail_enabled": True, "is_logging": True, "trail_name": "org-trail"},
        ]
    }

    def test_connection(self) -> bool:
        try:
            sts = boto3.client(
                "sts",
                region_name=settings.aws_default_region,
            )
            sts.get_caller_identity()
            return True
        except Exception as e:
            logger.error(f"AWS connection test failed: {e}")
            return False

    def fetch(self, config: dict) -> dict:
        raw_accounts = config.get("production_accounts", [])
        if not raw_accounts:
            logger.warning("No production_accounts configured")
            return {"accounts": []}

        accounts = []
        for entry in raw_accounts:
            if isinstance(entry, str):
                account_config = {"account_id": entry}
            else:
                account_config = entry

            account_data = self._check_account(account_config)
            accounts.append(account_data)

        logger.info(f"Checked CloudTrail status for {len(accounts)} accounts")
        return {"accounts": accounts}

    def _check_account(self, account_config: dict) -> dict:
        account_id = account_config["account_id"]
        role_arn = account_config.get("role_arn")

        try:
            session = self._get_session(role_arn)
            ct_client = session.client("cloudtrail", region_name=settings.aws_default_region)

            trails_resp = ct_client.describe_trails(includeShadowTrails=False)
            trails = trails_resp.get("trailList", [])

            if not trails:
                return {
                    "account_id": account_id,
                    "account_name": account_config.get("account_name", account_id),
                    "cloudtrail_enabled": False,
                    "is_logging": False,
                    "trail_name": None,
                    "trails_found": 0,
                }

            # Check if at least one trail is actively logging
            for trail in trails:
                trail_name = trail.get("Name", "")
                try:
                    status_resp = ct_client.get_trail_status(Name=trail["TrailARN"])
                    is_logging = status_resp.get("IsLogging", False)
                    if is_logging:
                        return {
                            "account_id": account_id,
                            "account_name": account_config.get("account_name", account_id),
                            "cloudtrail_enabled": True,
                            "is_logging": True,
                            "trail_name": trail_name,
                            "trails_found": len(trails),
                        }
                except ClientError as e:
                    logger.warning(f"Failed to get trail status for {trail_name} in {account_id}: {e}")

            # Trails exist but none are logging
            return {
                "account_id": account_id,
                "account_name": account_config.get("account_name", account_id),
                "cloudtrail_enabled": True,
                "is_logging": False,
                "trail_name": trails[0].get("Name"),
                "trails_found": len(trails),
            }

        except NoCredentialsError:
            logger.error(f"No AWS credentials available for account {account_id}")
            return {
                "account_id": account_id,
                "account_name": account_config.get("account_name", account_id),
                "cloudtrail_enabled": False,
                "is_logging": False,
                "trail_name": None,
                "error": "No credentials",
            }
        except Exception as e:
            logger.error(f"Failed to check CloudTrail for account {account_id}: {e}")
            return {
                "account_id": account_id,
                "account_name": account_config.get("account_name", account_id),
                "cloudtrail_enabled": False,
                "is_logging": False,
                "trail_name": None,
                "error": str(e),
            }

    def _get_session(self, role_arn: str | None) -> boto3.Session:
        if not role_arn:
            return boto3.Session(region_name=settings.aws_default_region)

        sts = boto3.client("sts", region_name=settings.aws_default_region)
        creds = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="panopticon-audit",
            DurationSeconds=900,
        )["Credentials"]

        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=settings.aws_default_region,
        )
