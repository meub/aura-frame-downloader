#!/usr/bin/env python3
"""Container entry point: download Aura frame photos to S3.

This script is intended to run as a scheduled AWS ECS task (triggered by an
EventBridge rule).  All configuration is read from environment variables —
see aura/env_config.py for the full variable reference.

Smoke-test mode
---------------
Set COUNT_ONLY=true to verify Aura API connectivity without downloading
anything or touching S3.  S3_BUCKET and AWS credentials are not required:

    docker run --rm \\
      -e AURA_EMAIL=you@example.com \\
      -e AURA_PASSWORD=secret \\
      -e AURA_FRAMES='[{"name":"Living Room","frame_id":"...","s3_prefix":"living-room"}]' \\
      -e COUNT_ONLY=true \\
      aura-frame-downloader

Exit codes
----------
0   All frames processed successfully.
1   Configuration error or one or more frames failed.
"""

import logging
import sys

from aura.core import download_photos_from_aura
from aura.env_config import (
    is_count_only,
    is_organize_by_year,
    load_credentials_from_env,
    load_frames_from_env,
    load_s3_bucket_from_env,
)
from aura.storage import S3Storage

# Structured log format — CloudWatch Logs can parse and index these fields.
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Run the container job (download or count-only).

    Returns:
        Exit code: 0 on full success, 1 if any frame failed.
    """
    count_only = is_count_only()

    try:
        creds = load_credentials_from_env()
        frames = load_frames_from_env()
        bucket = None if count_only else load_s3_bucket_from_env()
        organize = is_organize_by_year()
    except (EnvironmentError, ValueError) as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 1

    if count_only:
        LOGGER.info(
            "COUNT_ONLY mode — reporting photo counts for %d frame(s), no downloads or S3 writes",
            len(frames),
        )
    else:
        LOGGER.info(
            "Starting Aura → S3 backup: %d frame(s), bucket=%s, organize_by_year=%s",
            len(frames),
            bucket,
            organize,
        )

    exit_code = 0
    for frame in frames:
        name = frame["name"]
        frame_id = frame["frame_id"]
        s3_prefix = frame["s3_prefix"]

        LOGGER.info("Processing frame '%s' (id=%s)", name, frame_id)

        # In count_only mode skip S3Storage entirely — no AWS credentials needed.
        storage = None if count_only else S3Storage(bucket=bucket, prefix=s3_prefix)

        try:
            downloaded, skipped, total = download_photos_from_aura(
                email=creds["email"],
                password=creds["password"],
                frame_id=frame_id,
                file_path=s3_prefix,
                organize_by_year=organize,
                count_only=count_only,
                storage=storage,
            )
            if count_only:
                LOGGER.info("Frame '%s': %d photo(s) found in frame", name, total)
            else:
                LOGGER.info(
                    "Frame '%s' complete: downloaded=%d skipped=%d total=%d",
                    name,
                    downloaded,
                    skipped,
                    total,
                )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("Frame '%s' failed: %s", name, exc, exc_info=True)
            exit_code = 1

    if exit_code == 0:
        if count_only:
            LOGGER.info("Smoke test passed — Aura API reachable for all frames")
        else:
            LOGGER.info("All frames completed successfully")
    else:
        LOGGER.warning("One or more frames encountered errors — see above")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
