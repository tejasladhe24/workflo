"""Build example plugin wheel and publish index.json + artifacts to MinIO."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "packages" / "example-nodes"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_env("S3_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=_env("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=_env("S3_SECRET_KEY", "minioadmin"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _wait_for_minio(bucket: str, retries: int = 30) -> None:
    client = _s3_client()
    for _ in range(retries):
        try:
            client.head_bucket(Bucket=bucket)
            return
        except ClientError:
            try:
                client.create_bucket(Bucket=bucket)
                return
            except ClientError:
                time.sleep(2)
    raise RuntimeError(f"MinIO bucket {bucket!r} not ready after {retries} attempts")


def _build_wheel() -> Path:
    dist = PLUGIN_DIR / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for wheel in dist.glob("*.whl"):
        wheel.unlink()
    subprocess.run(
        ["uv", "build", str(PLUGIN_DIR), "--out-dir", str(dist)],
        check=True,
    )
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        raise RuntimeError("No wheel produced for example-nodes")
    return wheels[0]


def main() -> None:
    bucket = _env("BUCKET_NAME", "plugins")
    plugin_name = "example-nodes"
    version = "0.1.0"

    _wait_for_minio(bucket)
    wheel_path = _build_wheel()
    s3_key = f"{plugin_name}/{version}/{wheel_path.name}"

    client = _s3_client()
    client.upload_file(str(wheel_path), bucket, s3_key)
    print(f"Uploaded s3://{bucket}/{s3_key}")

    index = {
        "plugins": [
            {
                "name": plugin_name,
                "version": version,
                "package": "example_nodes",
                "wheel_path": s3_key,
                "nodes": ["uppercase", "concat", "constant"],
            }
        ]
    }
    index_bytes = json.dumps(index, indent=2).encode()
    client.put_object(
        Bucket=bucket,
        Key="index.json",
        Body=index_bytes,
        ContentType="application/json",
    )
    print(f"Uploaded s3://{bucket}/index.json")


if __name__ == "__main__":
    main()
