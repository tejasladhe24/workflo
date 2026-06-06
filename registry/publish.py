"""Build plugin wheels and publish index.json + artifacts to MinIO."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import TypedDict

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"


class PluginSpec(TypedDict):
    name: str
    version: str
    package: str
    directory: str
    nodes: list[str]


PLUGINS: list[PluginSpec] = [
    {
        "name": "example-nodes",
        "version": "0.1.0",
        "package": "example_nodes",
        "directory": "example-nodes",
        "nodes": ["uppercase", "concat", "constant"],
    },
    {
        "name": "web-search",
        "version": "0.1.0",
        "package": "web_search",
        "directory": "web-search",
        "nodes": ["web_search"],
    },
    {
        "name": "story-writer",
        "version": "0.1.0",
        "package": "story_writer",
        "directory": "story-writer",
        "nodes": ["story_writer"],
    },
]


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


def _build_wheel(plugin_dir: Path, plugin_name: str) -> Path:
    dist = plugin_dir / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for wheel in dist.glob("*.whl"):
        wheel.unlink()
    subprocess.run(
        ["uv", "build", str(plugin_dir), "--out-dir", str(dist)],
        check=True,
    )
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"No wheel produced for {plugin_name}")
    return wheels[0]


def _publish_plugin(client, bucket: str, spec: PluginSpec) -> dict:
    plugin_dir = PACKAGES_DIR / spec["directory"]
    wheel_path = _build_wheel(plugin_dir, spec["name"])
    s3_key = f"{spec['name']}/{spec['version']}/{wheel_path.name}"

    client.upload_file(str(wheel_path), bucket, s3_key)
    print(f"Uploaded s3://{bucket}/{s3_key}")

    return {
        "name": spec["name"],
        "version": spec["version"],
        "package": spec["package"],
        "wheel_path": s3_key,
        "nodes": spec["nodes"],
    }


def main() -> None:
    bucket = _env("BUCKET_NAME", "plugins")

    _wait_for_minio(bucket)
    client = _s3_client()

    index_plugins = [_publish_plugin(client, bucket, spec) for spec in PLUGINS]

    index = {"plugins": index_plugins}
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
