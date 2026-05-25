"""Environment-variable-based configuration for the container entry point.

All credentials and frame settings are read from environment variables so
nothing sensitive is ever written to disk or committed to the repository.

Required variables
------------------
AURA_EMAIL      Your Aura account e-mail address.
AURA_PASSWORD   Your Aura account password.
AURA_FRAMES     JSON array of frame objects, each with keys:
                  name      – human-readable label (used in log output)
                  frame_id  – UUID from the Aura API
                  s3_prefix – S3 key prefix / "folder" for this frame's photos
S3_BUCKET       Name of the destination S3 bucket.
                Not required when COUNT_ONLY=true.

Optional variables
------------------
AWS_DEFAULT_REGION   AWS region (default: us-east-1).
ORGANIZE_BY_YEAR     "true" to group photos in year sub-folders (default: false).
COUNT_ONLY           "true" to report photo counts only — no downloads, no S3
                     writes.  Useful as a local smoke test (no AWS credentials
                     needed).

Example AURA_FRAMES value
-------------------------
'[{"name":"Living Room","frame_id":"abc-123","s3_prefix":"living-room"}]'
"""

import json
import logging
import os
from typing import Dict, List

LOGGER = logging.getLogger(__name__)


def load_credentials_from_env() -> Dict[str, str]:
    """Read Aura login credentials from environment variables.

    Returns:
        dict with keys ``email`` and ``password``.

    Raises:
        EnvironmentError: If AURA_EMAIL or AURA_PASSWORD is not set.
    """
    missing = [v for v in ("AURA_EMAIL", "AURA_PASSWORD") if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(
            f"Required environment variable(s) not set: {', '.join(missing)}"
        )
    return {
        "email": os.environ["AURA_EMAIL"],
        "password": os.environ["AURA_PASSWORD"],
    }


def load_frames_from_env() -> List[Dict[str, str]]:
    """Parse the AURA_FRAMES JSON array from environment variables.

    Each frame dict must contain ``name``, ``frame_id``, and ``s3_prefix``.

    Returns:
        List of frame configuration dicts.

    Raises:
        EnvironmentError: If AURA_FRAMES is not set or is not valid JSON.
        ValueError: If any frame entry is missing required keys.
    """
    raw = os.environ.get("AURA_FRAMES")
    if not raw:
        raise EnvironmentError("Required environment variable AURA_FRAMES is not set")

    try:
        frames = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnvironmentError(f"AURA_FRAMES is not valid JSON: {exc}") from exc

    if not isinstance(frames, list) or len(frames) == 0:
        raise ValueError("AURA_FRAMES must be a non-empty JSON array")

    required_keys = {"name", "frame_id", "s3_prefix"}
    for i, frame in enumerate(frames):
        missing = required_keys - set(frame.keys())
        if missing:
            raise ValueError(
                f"Frame entry {i} is missing required key(s): {', '.join(sorted(missing))}"
            )

    LOGGER.info("Loaded %d frame(s) from AURA_FRAMES", len(frames))
    return frames


def load_s3_bucket_from_env() -> str:
    """Read the S3 bucket name from the S3_BUCKET environment variable.

    Raises:
        EnvironmentError: If S3_BUCKET is not set.
    """
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise EnvironmentError("Required environment variable S3_BUCKET is not set")
    return bucket


def is_organize_by_year() -> bool:
    """Return True if ORGANIZE_BY_YEAR is set to 'true' (case-insensitive)."""
    return os.environ.get("ORGANIZE_BY_YEAR", "false").lower() == "true"


def is_count_only() -> bool:
    """Return True if COUNT_ONLY is set to 'true' (case-insensitive).

    In count-only mode the container contacts the Aura API to report the
    number of photos in each frame but does not download anything or write
    to S3.  S3_BUCKET and AWS credentials are not required, making this
    ideal for local smoke-testing.
    """
    return os.environ.get("COUNT_ONLY", "false").lower() == "true"
