from __future__ import annotations

import json
import logging
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Callable

import boto3
from botocore.client import Config

from app.config import settings

logger = logging.getLogger(__name__)

HandlerFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def fetch_index() -> dict[str, Any]:
    client = _s3_client()
    response = client.get_object(Bucket=settings.bucket_name, Key="index.json")
    return json.loads(response["Body"].read())


def _install_wheel(wheel_file: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--target",
            str(target_dir),
            str(wheel_file),
        ],
        check=True,
    )


def _discover_handlers(target_dir: Path, package: str) -> dict[str, HandlerFn]:
    path_str = str(target_dir)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    handlers: dict[str, HandlerFn] = {}
    for ep in entry_points(group="starboard.nodes"):
        if ep.module and ep.module.split(".")[0] == package:
            handlers[ep.name] = ep.load()
    return handlers


def sync_plugins() -> dict[str, HandlerFn]:
    plugins_root = Path(settings.plugins_dir)
    plugins_root.mkdir(parents=True, exist_ok=True)

    if not settings.plugins_enabled:
        logger.info("Plugin sync disabled")
        return {}

    index = fetch_index()
    client = _s3_client()
    handlers: dict[str, HandlerFn] = {}

    for plugin in index.get("plugins", []):
        name = plugin["name"]
        version = plugin["version"]
        package = plugin.get("package", name.replace("-", "_"))
        wheel_path = plugin["wheel_path"]

        install_dir = plugins_root / name / version
        marker = install_dir / ".installed"

        if not marker.exists():
            logger.info("Installing plugin %s@%s", name, version)
            wheel_file = plugins_root / Path(wheel_path).name
            client.download_file(settings.bucket_name, wheel_path, str(wheel_file))
            _install_wheel(wheel_file, install_dir)
            marker.write_text(wheel_path)
        else:
            logger.info("Plugin %s@%s already installed", name, version)

        handlers.update(_discover_handlers(install_dir, package))

    logger.info("Loaded plugin handlers: %s", sorted(handlers.keys()))
    return handlers
