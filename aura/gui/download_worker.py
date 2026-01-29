"""Background worker thread for downloading photos."""

from PyQt6.QtCore import QThread, pyqtSignal

from ..core import download_photos_from_aura
from ..exceptions import (
    AuraError,
    DownloadCancelledError,
    LoginError,
    NoAssetsError,
)


class DownloadWorker(QThread):
    """QThread worker for downloading photos in the background."""

    # Signals
    progress_updated = pyqtSignal(int, int, str)  # current, total, filename
    status_changed = pyqtSignal(str)  # status message
    download_complete = pyqtSignal(int, int, int)  # downloaded, skipped, total
    error_occurred = pyqtSignal(str)  # error message

    def __init__(
        self,
        email: str,
        password: str,
        frame_id: str,
        file_path: str,
        organize_by_year: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.email = email
        self.password = password
        self.frame_id = frame_id
        self.file_path = file_path
        self.organize_by_year = organize_by_year
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

    def run(self):
        """Execute the download in the background thread."""
        try:
            self.status_changed.emit("Logging in...")

            downloaded, skipped, total = download_photos_from_aura(
                email=self.email,
                password=self.password,
                frame_id=self.frame_id,
                file_path=self.file_path,
                organize_by_year=self.organize_by_year,
                count_only=False,
                progress_callback=self._progress_callback,
                cancel_check=self._check_cancelled,
            )

            self.status_changed.emit("Download complete")
            self.download_complete.emit(downloaded, skipped, total)

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
            self.status_changed.emit("Error")
            self.error_occurred.emit(f"Unexpected error: {str(e)}")
