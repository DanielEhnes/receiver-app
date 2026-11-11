"""Settings read from environment variables (or a local .env file)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Real environment variables (e.g. from an OpenShift ConfigMap/Secret) win over .env.
load_dotenv(override=False)

REQUIRED = [
    "S3_ENDPOINT_URL",
    "S3_BUCKET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "APP_USERNAME",
    "APP_PASSWORD",
]


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    s3_endpoint_url: str
    s3_bucket: str
    s3_region: str
    s3_root_prefix: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_ca_bundle: str | None
    s3_verify_ssl: bool
    s3_create_bucket: bool
    max_unzipped_bytes: int
    app_username: str
    app_password: str


def load_settings() -> Settings:
    missing = [name for name in REQUIRED if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"Missing required settings: {', '.join(missing)}")

    root = os.getenv("S3_ROOT_PREFIX", "upload/").strip().strip("/")
    return Settings(
        s3_endpoint_url=os.environ["S3_ENDPOINT_URL"].strip(),
        s3_bucket=os.environ["S3_BUCKET"].strip(),
        s3_region=os.getenv("S3_REGION", "us-east-1").strip() or "us-east-1",
        s3_root_prefix=f"{root}/" if root else "",
        s3_access_key_id=os.environ["S3_ACCESS_KEY_ID"].strip(),
        s3_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"].strip(),
        s3_ca_bundle=os.getenv("S3_CA_BUNDLE", "").strip() or None,
        s3_verify_ssl=_bool("S3_VERIFY_SSL", True),
        s3_create_bucket=_bool("S3_CREATE_BUCKET", False),
        max_unzipped_bytes=int(os.getenv("MAX_UNZIPPED_BYTES", "1073741824")),
        app_username=os.environ["APP_USERNAME"],
        app_password=os.environ["APP_PASSWORD"],
    )


settings = load_settings()
