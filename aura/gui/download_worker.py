"""Background worker thread for downloading photos."""

import logging
import os
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ..core import create_session, download_photos_from_aura, get_frames
from ..exceptions import (
    AuraError,
    DownloadCancelledError,
    LoginError,
    NoAssetsError,
)

LOGGER = logging.getLogger(__name__)

# The packaged app has no console, so each run's log is written here in the download folder.
LOG_FILE_NAME = "aura-downloader.log"


class SignInWorker(QThread):
    """QThread worker that signs in and fetches the account's frames."""

    frames_loaded = pyqtSignal(list)  # list of {id, name, num_assets}
    failed = pyqtSignal(str)  # error message

    def __init__(self, email: str, password: str, parent=None):
        super().__init__(parent)
        self.email = email
        self.password = password

    def run(self):
        """Sign in and emit the frame list."""
        try:
            session = create_session(self.email, self.password)
            self.frames_loaded.emit(get_frames(session))
        except AuraError as e:
            self.failed.emit(str(e))
        except Exception as e:
            LOGGER.exception("Unexpected error while signing in")
            self.failed.emit(f"Unexpected error: {str(e)}")


class DownloadWorker(QThread):
    """QThread worker for downloading photos in the background."""

    # Signals
    progress_updated = pyqtSignal(int, int, str)  # current, total, filename
    status_changed = pyqtSignal(str)  # status message
    download_complete = pyqtSignal(int, int, int, int)  # downloaded, skipped, failed, total
    error_occurred = pyqtSignal(str)  # error message

    def __init__(
        self,
        email: str,
        password: str,
        frame_id: str,
        file_path: str,
        organize_by_year: bool = False,
        videos_only: bool = False,
        save_assets_path: str = None,
        parent=None
    ):
        super().__init__(parent)
        self.email = email
        self.password = password
        self.frame_id = frame_id
        self.file_path = file_path
        self.organize_by_year = organize_by_year
        self.videos_only = videos_only
        self.save_assets_path = save_assets_path
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the download."""
        self._cancelled = True

    def _check_cancelled(self) -> bool:
        """Check if download has been cancelled."""
        return self._cancelled

    def _progress_callback(self, current: int, total: int, filename: str):
        """Emit progress signal."""
        self.progress_updated.emit(current, total, filename)

    def _start_log_file(self) -> Optional[logging.FileHandler]:
        """Send this run's log to LOG_FILE_NAME in the download folder; None if it can't be written."""
        try:
            handler = logging.FileHandler(
                os.path.join(self.file_path, LOG_FILE_NAME), mode='w', encoding='utf-8'
            )
        except OSError:
            return None
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        aura_logger = logging.getLogger("aura")
        aura_logger.setLevel(logging.INFO)
        aura_logger.addHandler(handler)
        return handler

    def run(self):
        """Execute the download in the background thread."""
        log_handler = self._start_log_file()
        try:
            self.status_changed.emit("Logging in...")

            downloaded, skipped, failed, total = download_photos_from_aura(
                email=self.email,
                password=self.password,
                frame_id=self.frame_id,
                file_path=self.file_path,
                organize_by_year=self.organize_by_year,
                count_only=False,
                videos_only=self.videos_only,
                save_assets_path=self.save_assets_path,
                progress_callback=self._progress_callback,
                cancel_check=self._check_cancelled,
            )

            self.status_changed.emit("Download complete")
            self.download_complete.emit(downloaded, skipped, failed, total)

        except DownloadCancelledError:
            self.status_changed.emit("Download cancelled")
            self.error_occurred.emit("Download cancelled by user")

        except LoginError as e:
            self.status_changed.emit("Login failed")
            self.error_occurred.emit(str(e))

        except NoAssetsError as e:
            self.status_changed.emit("No photos found")
            self.error_occurred.emit(str(e))

        except AuraError as e:
            self.status_changed.emit("Error")
            self.error_occurred.emit(str(e))

        except Exception as e:
            LOGGER.exception("Unexpected error")
            self.status_changed.emit("Error")
            self.error_occurred.emit(f"Unexpected error: {str(e)}")

        finally:
            if log_handler:
                logging.getLogger("aura").removeHandler(log_handler)
                log_handler.close()
