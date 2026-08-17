"""Database backup to Cloudflare R2 (S3-compatible).

Runs every 6 hours via Celery Beat. Performs pg_dump, compresses with gzip,
uploads to R2 with a timestamped key, then prunes old backups according to
retention policy (48 hourly + 7 daily).

Requires: pg_dump (from postgresql-client), boto3.

Env vars:
    S3_BUCKET          — R2 bucket name (required)
    S3_ENDPOINT_URL    — R2 endpoint: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    S3_ACCESS_KEY_ID   — R2 API token access key ID
    S3_SECRET_ACCESS_KEY — R2 API token secret key
    S3_REGION          — Always "auto" for R2
    S3_PREFIX          — Key prefix in bucket (default: llmplane/backups)
    DATABASE_URL       — PostgreSQL connection URL (used for pg_dump)
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from celery import shared_task

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Create an R2/S3 client from environment variables."""
    endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("S3_REGION", "auto"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def _parse_database_url() -> dict[str, str]:
    """Extract pg_dump connection params from DATABASE_URL."""
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://llmplane:llmplane_dev@postgres:5432/llmplane")
    # Strip the asyncpg driver prefix for pg_dump (which uses plain postgresql)
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    # Parse: postgresql://user:pass@host:port/dbname
    without_scheme = url.split("://", 1)[1]
    auth, host_part = without_scheme.split("@", 1)
    user, password = auth.split(":", 1)
    host_db = host_part.split("/", 1)
    host_port = host_db[0]
    dbname = host_db[1] if len(host_db) > 1 else "llmplane"

    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
    else:
        host, port = host_port, "5432"

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }


def _run_pg_dump(db_params: dict[str, str], dump_path: str) -> None:
    """Run pg_dump to create a custom-format dump file."""
    env = os.environ.copy()
    env["PGPASSWORD"] = db_params["password"]

    cmd = [
        "pg_dump",
        "--host", db_params["host"],
        "--port", db_params["port"],
        "--username", db_params["user"],
        "--dbname", db_params["dbname"],
        "--format=custom",
        "--compress=0",  # We handle compression ourselves with gzip
        "--no-owner",
        "--no-privileges",
        "--verbose",
        dump_path,
    ]

    logger.info("Running pg_dump for %s@%s:%s/%s",
                db_params["user"], db_params["host"], db_params["port"], db_params["dbname"])

    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}): {result.stderr}")

    dump_size = Path(dump_path).stat().st_size
    logger.info("pg_dump complete: %s bytes", dump_size)


def _compress_file(src_path: str, dst_path: str) -> None:
    """Gzip-compress a file."""
    import gzip
    import shutil

    with open(src_path, "rb") as f_in, gzip.open(dst_path, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)

    src_size = Path(src_path).stat().st_size
    dst_size = Path(dst_path).stat().st_size
    ratio = (1 - dst_size / src_size) * 100 if src_size > 0 else 0
    logger.info("Compressed %s -> %s (%.1f%% reduction)", src_size, dst_size, ratio)


def _upload_to_s3(client, bucket: str, key: str, file_path: str) -> None:
    """Upload a file to S3."""
    logger.info("Uploading to s3://%s/%s", bucket, key)
    client.upload_file(
        file_path,
        bucket,
        key,
        ExtraArgs={
            "ServerSideEncryption": "AES256",
            "Metadata": {
                "created-at": datetime.now(timezone.utc).isoformat(),
                "type": "llmplane-db-backup",
            },
        },
    )
    logger.info("Upload complete: s3://%s/%s", bucket, key)


def _prune_old_backups(client, bucket: str, prefix: str) -> dict[str, int]:
    """Delete old backups according to retention policy.

    Retention:
        - Hourly backups: keep last 48
        - Daily backups: keep last 7 (those taken at 00:00 UTC)
    """
    now = datetime.now(timezone.utc)
    cutoff_hourly = now - timedelta(hours=48)
    cutoff_daily = now - timedelta(days=7)

    paginator = client.get_paginator("list_objects_v2")
    to_delete: list[dict[str, str]] = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".sql.gz"):
                continue

            # Extract timestamp from key: .../llmplane_20260817_120000.sql.gz
            try:
                filename = key.rsplit("/", 1)[-1]
                ts_str = filename.replace("llmplane_", "").replace(".sql.gz", "")
                obj_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            except (ValueError, IndexError):
                continue

            is_daily = obj_time.hour == 0 and obj_time.minute == 0

            if is_daily and obj_time < cutoff_daily:
                to_delete.append({"Key": key})
            elif not is_daily and obj_time < cutoff_hourly:
                to_delete.append({"Key": key})

    if not to_delete:
        return {"hourly_deleted": 0, "daily_deleted": 0}

    # Delete in batches of 1000 (S3 max)
    hourly_count = 0
    daily_count = 0
    for i in range(0, len(to_delete), 1000):
        batch = to_delete[i:i + 1000]
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": batch, "Quiet": True},
        )

    # Count for logging
    for d in to_delete:
        try:
            filename = d["Key"].rsplit("/", 1)[-1]
            ts_str = filename.replace("llmplane_", "").replace(".sql.gz", "")
            obj_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            if obj_time.hour == 0 and obj_time.minute == 0:
                daily_count += 1
            else:
                hourly_count += 1
        except (ValueError, IndexError):
            hourly_count += 1

    logger.info("Pruned %d hourly, %d daily old backups", hourly_count, daily_count)
    return {"hourly_deleted": hourly_count, "daily_deleted": daily_count}


@shared_task(name="workers.tasks.backup.database_backup")
def database_backup() -> dict[str, Any]:
    """Full database backup: pg_dump -> gzip -> S3 upload -> prune old."""
    s3_bucket = os.getenv("S3_BUCKET")
    if not s3_bucket:
        return {"status": "skipped", "reason": "S3_BUCKET not set"}

    s3_prefix = os.getenv("S3_PREFIX", "llmplane/backups")
    start = time.monotonic()

    try:
        db_params = _parse_database_url()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dump_filename = f"llmplane_{ts}.sql"
        gz_filename = f"{dump_filename}.gz"

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = os.path.join(tmpdir, dump_filename)
            gz_path = os.path.join(tmpdir, gz_filename)

            # 1. pg_dump
            _run_pg_dump(db_params, dump_path)

            # 2. Compress
            _compress_file(dump_path, gz_path)

            # 3. Upload to S3
            s3_client = _get_s3_client()
            s3_key = f"{s3_prefix}/{gz_filename}"
            _upload_to_s3(s3_client, s3_bucket, s3_key, gz_path)

            # 4. Prune old backups
            pruned = _prune_old_backups(s3_client, s3_bucket, s3_prefix)

        elapsed = time.monotonic() - start
        dump_size_mb = Path(gz_path).stat().st_size / (1024 * 1024) if Path(gz_path).exists() else 0

        logger.info("Database backup complete in %.1fs (%.1f MB compressed)", elapsed, dump_size_mb)
        return {
            "status": "ok",
            "s3_key": s3_key,
            "size_mb": round(dump_size_mb, 2),
            "elapsed_s": round(elapsed, 1),
            "pruned": pruned,
        }

    except Exception as exc:
        logger.exception("Database backup failed")
        return {"status": "error", "error": str(exc)}
