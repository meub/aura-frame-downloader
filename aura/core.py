"""Core download logic for Aura Frame Downloader."""

import json
import logging
import os
import time
from typing import Callable, Dict, List, Optional, Tuple

import requests

from .exceptions import (
    DownloadCancelledError,
    DownloadError,
    LoginError,
    NoAssetsError,
)
from .storage import LocalStorage, StorageBackend

LOGGER = logging.getLogger(__name__)

# API URLs
LOGIN_URL = "https://api.pushd.com/v5/login.json"
FRAME_URL_TEMPLATE = "https://api.pushd.com/v5/frames/{frame_id}/assets.json?side_load_users=false"
IMAGE_URL_TEMPLATE = "https://imgproxy.pushd.com/{user_id}/{file_name}"


def create_session(email: str, password: str) -> requests.Session:
    """
    Create an authenticated session with the Aura API.

    Args:
        email: User's email address
        password: User's password

    Returns:
        Authenticated requests.Session object

    Raises:
        LoginError: If authentication fails
    """
    login_payload = {
        "identifier_for_vendor": "does-not-matter",
        "client_device_id": "does-not-matter",
        "app_identifier": "com.pushd.Framelord",
        "locale": "en",
        "user": {
            "email": email,
            "password": password
        }
    }

    session = requests.Session()
    response = session.post(LOGIN_URL, json=login_payload)

    if response.status_code != 200:
        raise LoginError("Login failed: Check your credentials")

    json_data = response.json()
    session.headers.update({
        'X-User-Id': json_data['result']['current_user']['id'],
        'X-Token-Auth': json_data['result']['current_user']['auth_token']
    })

    LOGGER.info("Login successful")
    return session


def get_frame_assets(session: requests.Session, frame_id: str) -> List[Dict]:
    """
    Fetch assets from a frame.

    Args:
        session: Authenticated requests.Session
        frame_id: ID of the frame to fetch assets from

    Returns:
        List of asset dictionaries

    Raises:
        NoAssetsError: If no assets are found or API returns error
    """
    frame_url = FRAME_URL_TEMPLATE.format(frame_id=frame_id)
    response = session.get(frame_url)
    json_data = json.loads(response.text)

    if "assets" not in json_data:
        LOGGER.error("No images returned from this Aura Frame. API responded with:")
        LOGGER.error(json_data)
        raise NoAssetsError("No images found in this Aura Frame")

    return json_data["assets"]


def download_photos_from_aura(
    email: str,
    password: str,
    frame_id: str,
    file_path: str,
    organize_by_year: bool = False,
    count_only: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    storage: Optional[StorageBackend] = None,
) -> Tuple[int, int, int]:
    """
    Download photos from an Aura frame.

    Args:
        email: User's email address
        password: User's password
        frame_id: ID of the frame to download from
        file_path: Base directory to save photos to (used by LocalStorage;
                   ignored by S3Storage which derives its paths from the
                   StorageBackend prefix)
        organize_by_year: If True, organize photos into year subdirectories
        count_only: If True, return count without downloading
        progress_callback: Optional callback(current, total, filename)
        cancel_check: Optional callback() that returns True if download should
                      be cancelled
        storage: Storage backend to use.  Defaults to LocalStorage(file_path)
                 so all existing callers (CLI, GUI) continue to work unchanged.

    Returns:
        Tuple of (downloaded_count, skipped_count, total_count)

    Raises:
        LoginError: If authentication fails
        NoAssetsError: If no assets are found
        DownloadCancelledError: If download is cancelled via cancel_check
        DownloadError: If a critical download error occurs
    """
    # Default to local filesystem — preserves existing CLI / GUI behaviour.
    if storage is None:
        storage = LocalStorage(file_path)

    # Create authenticated session
    session = create_session(email, password)

    # Get frame assets
    assets = get_frame_assets(session, frame_id)
    total_count = len(assets)
    LOGGER.info("Found %s photos", total_count)

    if count_only:
        return (0, 0, total_count)

    # Ensure output directory exists (no-op for S3Storage)
    storage.makedirs(file_path)

    LOGGER.info("Starting download process")

    downloaded_count = 0
    skipped_count = 0
    current = 0

    for item in assets:
        current += 1

        # Check for cancellation
        if cancel_check and cancel_check():
            LOGGER.info("Download cancelled by user")
            raise DownloadCancelledError("Download cancelled by user")

        try:
            # Construct the raw photo URL
            url = IMAGE_URL_TEMPLATE.format(
                user_id=item['user_id'],
                file_name=item['file_name']
            )

            # Make a unique filename using timestamp + id + extension.
            # Clean the timestamp to be Windows-friendly (colons → dashes).
            clean_time = item['taken_at'].replace(':', '-')
            new_filename = clean_time + "_" + item['id'] + os.path.splitext(item['file_name'])[1]

            if organize_by_year:
                # Group by year: <year>/<filename>
                # For LocalStorage, also ensure the year subdirectory exists.
                year_dir = os.path.join(file_path, clean_time[:4])
                storage.makedirs(year_dir)
                key = os.path.join(clean_time[:4], new_filename)
            else:
                key = new_filename

            # Update progress
            if progress_callback:
                progress_callback(current, total_count, new_filename)

            # Check if already downloaded / uploaded and skip if so
            if storage.exists(key):
                LOGGER.info("%i: Skipping %s, already downloaded", current, new_filename)
                skipped_count += 1
                continue

            # Fetch the photo
            LOGGER.info("%i: Downloading %s", current, new_filename)
            response = requests.get(url, stream=True, timeout=90)

            # Write to storage (local file or S3 object)
            storage.write_stream(key, response)
            del response

            downloaded_count += 1

            # Wait a bit to avoid throttling
            time.sleep(2)

        except DownloadCancelledError:
            raise
        except Exception as e:
            LOGGER.error("Item %i failed to download: %s", current, str(e))
            time.sleep(10)

    return (downloaded_count, skipped_count, total_count)
