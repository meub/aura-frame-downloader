"""Storage backend abstraction for Aura Frame Downloader.

Provides a common interface for writing downloaded photos to either a local
filesystem (existing CLI/GUI behaviour) or an S3 bucket (container mode).
"""

import logging
import os
import shutil
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import requests

LOGGER = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def makedirs(self, path: str) -> None:
        """Ensure a directory (or logical prefix) exists."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if the object/file already exists at *key*."""

    @abstractmethod
    def write_stream(self, key: str, response: "requests.Response") -> None:
        """Write the streaming HTTP *response* body to *key*."""


class LocalStorage(StorageBackend):
    """Store downloaded photos on the local filesystem.

    This is the default backend — it replicates the original behaviour so the
    CLI and GUI continue to work without any changes to their call sites.
    """

    def __init__(self, base_path: str) -> None:
        self.base_path = base_path

    def _full_path(self, key: str) -> str:
        return os.path.join(self.base_path, key)

    def makedirs(self, path: str) -> None:
        if not os.path.isdir(path):
            LOGGER.debug("Creating directory: %s", path)
            os.makedirs(path)

    def exists(self, key: str) -> bool:
        return os.path.isfile(self._full_path(key))

    def write_stream(self, key: str, response: "requests.Response") -> None:
        dest = self._full_path(key)
        with open(dest, "wb") as out_file:
            shutil.copyfileobj(response.raw, out_file)


class S3Storage(StorageBackend):
    """Store downloaded photos directly in an S3 bucket.

    Authentication uses the standard boto3 credential chain — in production
    the ECS task IAM role is used automatically; for local testing set
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in your .env file.

    Args:
        bucket: Name of the S3 bucket.
        prefix: Optional key prefix (acts like a folder).  No trailing slash
                needed — one will be added automatically.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        import boto3  # imported lazily so boto3 is only required in containers
        from botocore.exceptions import ClientError

        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self._client = boto3.client("s3")
        self._ClientError = ClientError

    def _s3_key(self, key: str) -> str:
        """Build the full S3 key from the relative *key*."""
        if self.prefix:
            return f"{self.prefix}/{key}"
        return key

    def makedirs(self, path: str) -> None:
        """No-op: S3 does not use directories."""

    def exists(self, key: str) -> bool:
        """Return True if the S3 object already exists (head_object check)."""
        s3_key = self._s3_key(key)
        try:
            self._client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except self._ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def write_stream(self, key: str, response: "requests.Response") -> None:
        """Stream the HTTP response body directly into S3."""
        s3_key = self._s3_key(key)
        LOGGER.debug("Uploading to s3://%s/%s", self.bucket, s3_key)
        self._client.upload_fileobj(response.raw, self.bucket, s3_key)
