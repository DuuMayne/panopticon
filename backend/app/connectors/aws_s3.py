from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.connectors.base import ConnectorBase, register_connector

logger = logging.getLogger("oculus.connectors.aws_s3")


@register_connector
class AWSS3Connector(ConnectorBase):
    """Fetches S3 bucket encryption and public access settings.

    Checks all buckets in the account (or a configured subset).
    """

    connector_type = "aws_s3"
    required_env = ["aws_access_key_id"]
    mock_data = {
        "buckets": [
            {"name": "prod-data-lake", "encryption_enabled": True, "encryption_type": "aws:kms", "public_access_blocked": True, "region": "us-east-1"},
            {"name": "prod-logs", "encryption_enabled": True, "encryption_type": "AES256", "public_access_blocked": True, "region": "us-east-1"},
            {"name": "marketing-assets", "encryption_enabled": False, "encryption_type": None, "public_access_blocked": False, "region": "us-east-1"},
            {"name": "backup-archive", "encryption_enabled": True, "encryption_type": "aws:kms", "public_access_blocked": True, "region": "us-west-2"},
        ],
    }

    def test_connection(self) -> bool:
        try:
            s3 = boto3.client("s3", region_name=settings.aws_default_region)
            s3.list_buckets()
            return True
        except Exception as e:
            logger.error(f"AWS S3 connection test failed: {e}")
            return False

    def fetch(self, config: dict) -> dict:
        s3 = boto3.client("s3", region_name=settings.aws_default_region)
        scope_buckets = config.get("bucket_names")  # None = all buckets

        try:
            all_buckets = s3.list_buckets().get("Buckets", [])
        except Exception as e:
            logger.error(f"Failed to list S3 buckets: {e}")
            return {"buckets": []}

        buckets = []
        for b in all_buckets:
            name = b["Name"]
            if scope_buckets and name not in scope_buckets:
                continue

            bucket_info = {"name": name, "encryption_enabled": False, "encryption_type": None, "public_access_blocked": True, "region": None}

            # Encryption
            try:
                enc = s3.get_bucket_encryption(Bucket=name)
                rules = enc.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
                if rules:
                    bucket_info["encryption_enabled"] = True
                    bucket_info["encryption_type"] = rules[0].get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                    bucket_info["encryption_enabled"] = False
                else:
                    logger.warning(f"Failed to check encryption for {name}: {e}")

            # Public access block
            try:
                pab = s3.get_public_access_block(Bucket=name)
                cfg = pab.get("PublicAccessBlockConfiguration", {})
                bucket_info["public_access_blocked"] = all([
                    cfg.get("BlockPublicAcls", False),
                    cfg.get("IgnorePublicAcls", False),
                    cfg.get("BlockPublicPolicy", False),
                    cfg.get("RestrictPublicBuckets", False),
                ])
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
                    bucket_info["public_access_blocked"] = False
                else:
                    logger.warning(f"Failed to check public access for {name}: {e}")

            # Region
            try:
                loc = s3.get_bucket_location(Bucket=name)
                bucket_info["region"] = loc.get("LocationConstraint") or "us-east-1"
            except Exception:
                pass

            buckets.append(bucket_info)

        logger.info(f"Fetched settings for {len(buckets)} S3 buckets")
        return {"buckets": buckets}
