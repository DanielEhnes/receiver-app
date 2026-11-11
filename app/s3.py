"""S3 client for an S3-compatible endpoint (MinIO, Ceph, etc.)."""
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import settings

_client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key_id,
    aws_secret_access_key=settings.s3_secret_access_key,
    region_name=settings.s3_region,
    verify=settings.s3_ca_bundle or settings.s3_verify_ssl,
    config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
)


def upload_fileobj(fileobj: BinaryIO, key: str) -> None:
    _client.upload_fileobj(fileobj, settings.s3_bucket, key)


def ensure_bucket() -> None:
    """Create the bucket if it does not exist (only when S3_CREATE_BUCKET=true)."""
    if not settings.s3_create_bucket:
        return
    try:
        _client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        _client.create_bucket(Bucket=settings.s3_bucket)
