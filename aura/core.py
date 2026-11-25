"""Core download logic for Aura Frame Downloader."""

import json
import logging
import os
import re
import shutil
import time
from typing import Callable, Dict, List, Optional, Tuple

import requests

from .exceptions import (
    AuraError,
    DownloadCancelledError,
    DownloadError,
    LoginError,
    NetworkError,
    NoAssetsError,
)

LOGGER = logging.getLogger(__name__)

# API URLs
LOGIN_URL = "https://api.pushd.com/v5/login.json"
FRAMES_URL = "https://api.pushd.com/v5/frames.json"
FRAME_URL_TEMPLATE = "https://api.pushd.com/v5/frames/{frame_id}/assets.json?side_load_users=false"
IMAGE_URL_TEMPLATE = "https://imgproxy.pushd.com/{user_id}/{file_name}"

# Without a timeout a stalled connection left the GUI stuck on "Logging in..." for good.
REQUEST_TIMEOUT_SECONDS = 90

# Stop after this many photos in a row fail to connect. Each failure waits 10 seconds, so
# without a limit a dropped connection kept "downloading" 5,000 photos for about 14 hours.
MAX_CONSECUTIVE_NETWORK_FAILURES = 5

# Frame IDs are UUIDs. Users often paste the whole app.auraframes.com/frame/<id> URL instead.
FRAME_ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def normalize_frame_id(raw: str) -> str:
    """Return the frame UUID found in raw (a bare ID or a pasted URL), else raw stripped."""
    match = FRAME_ID_PATTERN.search(raw)
    return match.group(0) if match else raw.strip()


def _api_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """Send an API request, turning connection failures into a NetworkError users can act on."""
    try:
        return session.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
    except (requests.ConnectionError, requests.Timeout) as exc:
        # Previously shown raw, e.g. "Unexpected error: HTTPSConnectionPool(host='api.pushd.com'...".
        raise NetworkError("Couldn't reach Aura. Check your internet connection and try again.") from exc


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
    response = _api_request(session, "POST", LOGIN_URL, json=login_payload)

    if response.status_code != 200:
        # A wrong email/password comes back as HTTP 475 with a JSON "message" (checked 2026-11-24).
        # A response without one (e.g. a 5xx page) points at an Aura outage, not bad credentials.
        try:
            message = response.json()["message"]
        except (ValueError, KeyError, TypeError):
            message = f"HTTP {response.status_code}. Aura may be having problems, try again later."
        raise LoginError(f"Login failed: {message}")

    json_data = response.json()
    session.headers.update({
        'X-User-Id': json_data['result']['current_user']['id'],
        'X-Token-Auth': json_data['result']['current_user']['auth_token']
    })

    LOGGER.info("Login successful")
    return session


def get_frames(session: requests.Session) -> List[Dict]:
    """
    List the frames this account can see, including frames shared with it.

    Args:
        session: Authenticated requests.Session

    Returns:
        List of dicts with 'id', 'name' and 'num_assets' (photo count, may be None)

    Raises:
        AuraError: If the API response isn't a frame list
    """
    response = _api_request(session, "GET", FRAMES_URL)
    try:
        frames = response.json()["frames"]
        return [
            {'id': f['id'], 'name': f.get('name') or "Unnamed frame", 'num_assets': f.get('num_assets')}
            for f in frames
        ]
    except (ValueError, KeyError, TypeError) as exc:
        LOGGER.error("Unexpected frame list response (HTTP %s): %.200s", response.status_code, response.text)
        raise AuraError(
            f"Aura returned an unexpected response (HTTP {response.status_code}) when listing frames."
        ) from exc


def get_frame_assets(
    session: requests.Session,
    frame_id: str,
    save_raw_response_path: Optional[str] = None,
) -> List[Dict]:
    """
    Fetch assets from a frame.

    Args:
        session: Authenticated requests.Session
        frame_id: ID of the frame to fetch assets from
        save_raw_response_path: If set, write the full JSON response to this path

    Returns:
        List of asset dictionaries

    Raises:
        NoAssetsError: If no assets are found or API returns error
    """
    frame_url = FRAME_URL_TEMPLATE.format(frame_id=normalize_frame_id(frame_id))
    response = _api_request(session, "GET", frame_url)
    try:
        json_data = response.json()
    except ValueError as exc:
        # A frame ID containing "/" misses the API's routes and gets an HTML 404 page back,
        # which surfaced as "Expecting value: line 1 column 1 (char 0)". Probed 2026-11-24.
        LOGGER.error("Non-JSON response (HTTP %s) from %s: %.200s",
                     response.status_code, frame_url, response.text)
        raise NoAssetsError(
            f"Aura returned an unexpected response (HTTP {response.status_code}). "
            "Check that the Frame ID is correct."
        ) from exc

    if save_raw_response_path:
        with open(save_raw_response_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        LOGGER.info("Saved raw asset JSON to %s", save_raw_response_path)

    if "assets" not in json_data:
        LOGGER.error("No images returned from this Aura Frame. API responded with:")
        LOGGER.error(json_data)
        if json_data.get("error"):
            # A wrong Frame ID answers {"error": true, "message": "Not found"}, which used to
            # be reported as an empty frame (issue #22).
            raise NoAssetsError(
                f"Aura could not load this frame: {json_data.get('message')} "
                f"(HTTP {response.status_code}). Check that the Frame ID is correct."
            )
        raise NoAssetsError("No images found in this Aura Frame")

    return json_data["assets"]


def download_photos_from_aura(
    email: str,
    password: str,
    frame_id: str,
    file_path: str,
    organize_by_year: bool = False,
    count_only: bool = False,
    videos_only: bool = False,
    save_assets_path: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Tuple[int, int, int, int]:
    """
    Download photos from an Aura frame.

    Args:
        email: User's email address
        password: User's password
        frame_id: ID of the frame to download from
        file_path: Directory to save photos to
        organize_by_year: If True, organize photos into year subdirectories
        count_only: If True, return count without downloading
        videos_only: If True, only download video clips, skip still photos
        save_assets_path: If set, write the raw assets JSON returned by the API to this path
        progress_callback: Optional callback(current, total, filename) for progress updates
        cancel_check: Optional callback() that returns True if download should be cancelled

    Returns:
        Tuple of (downloaded_count, skipped_count, failed_count, total_count).
        Downloaded and skipped count files; failed and total count assets.

    Raises:
        LoginError: If authentication fails
        NoAssetsError: If no assets are found
        DownloadCancelledError: If download is cancelled via cancel_check
        DownloadError: If a critical download error occurs
    """
    # Create authenticated session
    session = create_session(email, password)

    # Get frame assets
    assets = get_frame_assets(session, frame_id, save_raw_response_path=save_assets_path)
    total_count = len(assets)
    LOGGER.info("Found %s photos", total_count)

    if count_only:
        return (0, 0, 0, total_count)

    # Ensure output directory exists
    if not os.path.isdir(file_path):
        LOGGER.info("Creating new images directory: %s", file_path)
        os.makedirs(file_path)

    LOGGER.info("Starting download process")

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    consecutive_network_failures = 0
    current = 0

    for item in assets:
        current += 1

        # Check for cancellation
        if cancel_check and cancel_check():
            LOGGER.info("Download cancelled by user")
            raise DownloadCancelledError("Download cancelled by user")

        try:
            clean_time = item['taken_at'].replace(':', '-')

            if organize_by_year:
                out_dir = os.path.join(file_path, clean_time[:4])
                if not os.path.isdir(out_dir):
                    LOGGER.debug("Creating new year directory: %s", out_dir)
                    os.makedirs(out_dir)
            else:
                out_dir = file_path

            # Each asset may have a still image, a video (Live Photo / video clip), or both.
            # Build a list of (label, url, target_path) for whichever components are present.
            downloads = []

            still_name = item.get('file_name')
            if still_name and not videos_only:
                still_url = IMAGE_URL_TEMPLATE.format(
                    user_id=item['user_id'],
                    file_name=still_name,
                )
                still_filename = clean_time + "_" + item['id'] + os.path.splitext(still_name)[1]
                downloads.append(('photo', still_url, os.path.join(out_dir, still_filename)))

            video_url = item.get('video_url')
            video_name = item.get('video_file_name')
            if video_url and video_name:
                video_filename = clean_time + "_" + item['id'] + os.path.splitext(video_name)[1]
                downloads.append(('video', video_url, os.path.join(out_dir, video_filename)))

            for label, url, file_to_write in downloads:
                basename = os.path.basename(file_to_write)

                if progress_callback:
                    progress_callback(current, total_count, basename)

                if os.path.isfile(file_to_write):
                    LOGGER.info("%i: Skipping %s %s, already downloaded", current, label, basename)
                    skipped_count += 1
                    continue

                LOGGER.info("%i: Downloading %s %s", current, label, basename)
                response = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS)
                # Without this an error body (imgproxy sends a 27-byte text/plain 404) was saved
                # as the photo, and later runs skipped it as already downloaded.
                response.raise_for_status()

                # Write to .part and rename when complete, so an interrupted download never
                # leaves a truncated file that later runs would skip.
                part_file = file_to_write + ".part"
                with open(part_file, 'wb') as out_file:
                    shutil.copyfileobj(response.raw, out_file)
                os.replace(part_file, file_to_write)
                del response

                downloaded_count += 1
                consecutive_network_failures = 0

                time.sleep(2)

        except DownloadCancelledError:
            raise
        except Exception as e:
            LOGGER.error("Item %i failed to download: %s", current, str(e))
            failed_count += 1
            if isinstance(e, (requests.ConnectionError, requests.Timeout)):
                consecutive_network_failures += 1
                if consecutive_network_failures >= MAX_CONSECUTIVE_NETWORK_FAILURES:
                    raise NetworkError(
                        "Lost the connection to Aura. Check your internet connection, then start "
                        "the download again to continue where it stopped."
                    ) from e
            else:
                # Any other failure (e.g. a 404 for one photo) means the server answered.
                consecutive_network_failures = 0
            time.sleep(10)

    return (downloaded_count, skipped_count, failed_count, total_count)
