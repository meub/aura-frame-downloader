"""Main window for Aura Frame Downloader GUI."""

import json
import os
import re

from PyQt6.QtCore import Qt, QSettings, QStandardPaths, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog,
    QDialogButtonBox,
)

from ..core import FRAME_ID_PATTERN, normalize_frame_id
from .download_worker import LOG_FILE_NAME, DownloadWorker, SignInWorker

FRAME_ID_HELP_URL = "https://github.com/meub/aura-frame-downloader?tab=readme-ov-file#getting-your-frame-id"
EXAMPLE_FRAME_ID = "476300c8-98fd-429a-9d33-72a39ca9f1c2"

# Frame names become default folder names; Windows rejects these characters in them.
INVALID_FOLDER_CHARS = re.compile(r'[<>:"/\\|?*]')


def default_folder_for(frame_name: str) -> str:
    """Suggested download folder for a frame: Pictures/Aura/<frame name>."""
    pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    safe_name = INVALID_FOLDER_CHARS.sub("_", frame_name).strip().rstrip(".") or "Frame"
    return os.path.join(pictures or os.path.expanduser("~"), "Aura", safe_name)


class FrameDialog(QDialog):
    """Dialog for adding a frame by ID, for frames that don't appear after signing in."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Frame by ID")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Living Room Frame")
        form.addRow("Frame Name:", self.name_input)

        frame_id_layout = QHBoxLayout()
        self.frame_id_input = QLineEdit()
        self.frame_id_input.setPlaceholderText("Frame ID or app.auraframes.com address")
        frame_id_help = QLabel(f'<a href="{FRAME_ID_HELP_URL}">Help</a>')
        frame_id_help.setOpenExternalLinks(True)
        frame_id_layout.addWidget(self.frame_id_input)
        frame_id_layout.addWidget(frame_id_help)
        form.addRow("Frame ID:", frame_id_layout)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            'id': normalize_frame_id(self.frame_id_input.text()),
            'name': self.name_input.text().strip(),
        }

    def accept(self):
        data = self.get_data()
        if not data['name']:
            QMessageBox.warning(self, "Validation Error", "Frame name is required.")
            return
        if not FRAME_ID_PATTERN.fullmatch(data['id']):
            QMessageBox.warning(
                self, "Validation Error",
                f"That doesn't look like a Frame ID. It should look like {EXAMPLE_FRAME_ID}.\n\n"
                "Click Help to see where to find it."
            )
            return
        super().accept()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.sign_in_worker = None
        self.account_frames = []  # From Aura after sign-in: {id, name, num_assets}. Not saved.
        self.manual_frames = []  # Added by ID: {id, name}. Saved.
        self.folders = {}  # Download folder the user chose, per frame id. Saved.
        self.settings = QSettings("AuraDownloader", "AuraFrameDownloader")
        self._init_ui()
        self._load_settings()

        if self.email_input.text().strip() and self.password_input.text():
            self._sign_in(quiet=True)

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Aura Frame Downloader")
        self.setMinimumWidth(550)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Account group
        login_group = QGroupBox("Aura Account")
        login_layout = QFormLayout(login_group)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        self.email_input.setMinimumWidth(300)
        login_layout.addRow("Email:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Your Aura password")
        self.password_input.setMinimumWidth(300)
        self.password_input.returnPressed.connect(lambda: self._sign_in(quiet=False))
        login_layout.addRow("Password:", self.password_input)

        sign_in_layout = QHBoxLayout()
        self.sign_in_btn = QPushButton("Sign In")
        self.sign_in_btn.clicked.connect(lambda: self._sign_in(quiet=False))
        sign_in_layout.addWidget(self.sign_in_btn)
        sign_in_layout.addStretch()
        login_layout.addRow("", sign_in_layout)

        layout.addWidget(login_group)

        # Frame group
        frame_group = QGroupBox("Frame")
        frame_layout = QFormLayout(frame_group)

        frame_select_layout = QHBoxLayout()
        self.frame_combo = QComboBox()
        self.frame_combo.setMinimumWidth(250)
        self.frame_combo.setPlaceholderText("Sign in to see your frames")
        self.frame_combo.currentIndexChanged.connect(self._on_frame_changed)
        self.add_frame_btn = QPushButton("Add by ID...")
        self.add_frame_btn.setToolTip("For a frame that doesn't appear in the list after signing in")
        self.add_frame_btn.clicked.connect(self._add_frame)
        self.remove_frame_btn = QPushButton("Remove")
        self.remove_frame_btn.clicked.connect(self._remove_frame)
        frame_select_layout.addWidget(self.frame_combo, 1)
        frame_select_layout.addWidget(self.add_frame_btn)
        frame_select_layout.addWidget(self.remove_frame_btn)
        frame_layout.addRow("Frame:", frame_select_layout)

        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.textEdited.connect(self._on_folder_edited)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.folder_input, 1)
        folder_layout.addWidget(self.browse_btn)
        frame_layout.addRow("Save to:", folder_layout)

        layout.addWidget(frame_group)

        # Download options group
        options_group = QGroupBox("Download Options")
        options_layout = QVBoxLayout(options_group)

        self.year_checkbox = QCheckBox("Organize photos by year")
        options_layout.addWidget(self.year_checkbox)

        self.videos_only_checkbox = QCheckBox("Only download video clips (skip still photos)")
        options_layout.addWidget(self.videos_only_checkbox)

        self.save_assets_checkbox = QCheckBox(
            "Save raw API response to download folder (debug)"
        )
        options_layout.addWidget(self.save_assets_checkbox)

        layout.addWidget(options_group)

        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Enter your Aura email and password, then click Sign In")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Start/Stop button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.start_btn = QPushButton("Start Download")
        self.start_btn.setMinimumWidth(150)
        self.start_btn.clicked.connect(self._toggle_download)
        button_layout.addWidget(self.start_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

    def _load_json_setting(self, key: str, default):
        """Read a JSON-encoded setting, falling back to default if missing or malformed."""
        try:
            value = json.loads(self.settings.value(key, ""))
        except (TypeError, json.JSONDecodeError):
            return default
        return value if isinstance(value, type(default)) else default

    def _load_settings(self):
        """Load saved settings."""
        self.email_input.setText(self.settings.value("email", ""))
        self.password_input.setText(self.settings.value("password", ""))
        self.year_checkbox.setChecked(self.settings.value("organize_by_year", False, type=bool))
        self.videos_only_checkbox.setChecked(self.settings.value("videos_only", False, type=bool))
        self.save_assets_checkbox.setChecked(self.settings.value("save_assets", False, type=bool))

        self.manual_frames = self._load_json_setting("manual_frames", [])
        self.folders = self._load_json_setting("folders", {})
        self._migrate_old_frames()

        self._refresh_frame_combo(select_id=self.settings.value("selected_frame_id", ""))

    def _migrate_old_frames(self):
        """Move frames saved by 2.1.x ({name, frame_id, path} under "frames") to the new settings, once."""
        if not self.settings.contains("frames"):
            return
        old_selected_name = self.settings.value("selected_frame", "")
        for frame in self._load_json_setting("frames", []):
            if not isinstance(frame, dict):
                continue
            frame_id = normalize_frame_id(frame.get('frame_id', ''))
            if not frame_id:
                continue
            if not any(f['id'] == frame_id for f in self.manual_frames):
                self.manual_frames.append({'id': frame_id, 'name': frame.get('name') or frame_id})
            if frame.get('path'):
                self.folders.setdefault(frame_id, frame['path'])
            if old_selected_name and frame.get('name') == old_selected_name:
                self.settings.setValue("selected_frame_id", frame_id)

        self.settings.setValue("manual_frames", json.dumps(self.manual_frames))
        self.settings.setValue("folders", json.dumps(self.folders))
        self.settings.remove("frames")
        self.settings.remove("selected_frame")

    def _save_settings(self):
        """Save current settings."""
        self.settings.setValue("email", self.email_input.text())
        self.settings.setValue("password", self.password_input.text())
        self.settings.setValue("organize_by_year", self.year_checkbox.isChecked())
        self.settings.setValue("videos_only", self.videos_only_checkbox.isChecked())
        self.settings.setValue("save_assets", self.save_assets_checkbox.isChecked())
        self.settings.setValue("manual_frames", json.dumps(self.manual_frames))
        self.settings.setValue("folders", json.dumps(self.folders))
        # Only overwrite with a real selection, so closing before sign-in finishes keeps the old one.
        if self._selected_frame_id():
            self.settings.setValue("selected_frame_id", self._selected_frame_id())

    def closeEvent(self, event):
        """Save settings on close."""
        self._save_settings()
        super().closeEvent(event)

    # Frames

    def _selected_frame_id(self) -> str:
        return self.frame_combo.currentData() or ""

    def _all_frames(self) -> list:
        """The account's frames, then frames added by ID that the account list doesn't include."""
        account_ids = {f['id'] for f in self.account_frames}
        return self.account_frames + [f for f in self.manual_frames if f['id'] not in account_ids]

    def _frame_name(self, frame_id: str) -> str:
        return next((f['name'] for f in self._all_frames() if f['id'] == frame_id), frame_id)

    def _folder_for(self, frame_id: str) -> str:
        return self.folders.get(frame_id) or default_folder_for(self._frame_name(frame_id))

    def _refresh_frame_combo(self, select_id: str = ""):
        """Rebuild the frame picker, keeping select_id (or the current frame) selected."""
        select_id = select_id or self._selected_frame_id()
        manual_ids = {f['id'] for f in self.manual_frames}

        self.frame_combo.blockSignals(True)
        self.frame_combo.clear()
        for frame in self._all_frames():
            count = frame.get('num_assets')
            if isinstance(count, int):
                label = f"{frame['name']} ({count:,} photo{'' if count == 1 else 's'})"
            elif frame['id'] in manual_ids:
                label = f"{frame['name']} (added by ID)"
            else:
                label = frame['name']
            self.frame_combo.addItem(label, frame['id'])
        index = self.frame_combo.findData(select_id) if select_id else -1
        self.frame_combo.setCurrentIndex(index if index >= 0 else 0)
        self.frame_combo.blockSignals(False)
        self._on_frame_changed()

    def _on_frame_changed(self):
        frame_id = self._selected_frame_id()
        self.folder_input.setText(self._folder_for(frame_id) if frame_id else "")
        self._update_remove_button()

    def _update_remove_button(self):
        """Only frames added by ID can be removed; the account's frames come from Aura."""
        is_manual = any(f['id'] == self._selected_frame_id() for f in self.manual_frames)
        self.remove_frame_btn.setEnabled(is_manual and self.worker is None)

    def _on_folder_edited(self, text: str):
        frame_id = self._selected_frame_id()
        if frame_id:
            self.folders[frame_id] = text.strip()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder",
            self.folder_input.text() or os.path.expanduser("~")
        )
        if folder:
            self.folder_input.setText(folder)
            self._on_folder_edited(folder)

    def _add_frame(self):
        """Add a frame by ID."""
        dialog = FrameDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        frame = dialog.get_data()
        if any(f['id'] == frame['id'] for f in self._all_frames()):
            QMessageBox.information(self, "Already Listed", "That frame is already in the list.")
        else:
            self.manual_frames.append(frame)
            self._save_settings()
        self._refresh_frame_combo(select_id=frame['id'])

    def _remove_frame(self):
        """Remove the selected frame that was added by ID."""
        frame_id = self._selected_frame_id()
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Remove '{self._frame_name(frame_id)}' from the list? Downloaded photos are not deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manual_frames = [f for f in self.manual_frames if f['id'] != frame_id]
            self.folders.pop(frame_id, None)
            self._refresh_frame_combo()
            self._save_settings()

    # Sign in

    def _sign_in(self, quiet: bool):
        """Sign in and load the account's frames. quiet: report problems in the status line only."""
        email = self.email_input.text().strip()
        password = self.password_input.text()  # not stripped: spaces can be part of a password
        if not email or not password:
            if not quiet:
                QMessageBox.warning(self, "Missing Credentials", "Please enter your email and password.")
            return
        if self.sign_in_worker is not None:
            return

        self.sign_in_btn.setEnabled(False)
        self.status_label.setText("Signing in...")
        self.sign_in_worker = SignInWorker(email, password, parent=self)
        self.sign_in_worker.frames_loaded.connect(self._on_frames_loaded)
        self.sign_in_worker.failed.connect(lambda message: self._on_sign_in_failed(message, quiet))
        self.sign_in_worker.finished.connect(self._on_sign_in_finished)
        self.sign_in_worker.start()

    def _on_frames_loaded(self, frames: list):
        self.account_frames = frames
        # Frames added by ID that the account now lists are redundant; their folder choice is kept.
        account_ids = {f['id'] for f in frames}
        self.manual_frames = [f for f in self.manual_frames if f['id'] not in account_ids]
        self._refresh_frame_combo()
        self._save_settings()

        if frames:
            plural = "" if len(frames) == 1 else "s"
            self.status_label.setText(
                f"Signed in. Found {len(frames)} frame{plural}. Pick one and click Start Download."
            )
        else:
            self.status_label.setText("Signed in, but no frames were found on this account.")

    def _on_sign_in_failed(self, message: str, quiet: bool):
        self.status_label.setText(message)
        if not quiet:
            QMessageBox.warning(self, "Sign In Failed", message)

    def _on_sign_in_finished(self):
        self.sign_in_worker = None
        self.sign_in_btn.setEnabled(self.worker is None)

    # Download

    def _toggle_download(self):
        """Start or stop the download."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.start_btn.setEnabled(False)
            self.status_label.setText("Stopping download...")
        else:
            self._start_download()

    def _start_download(self):
        """Start the download process."""
        email = self.email_input.text().strip()
        password = self.password_input.text()  # not stripped: spaces can be part of a password

        if not email or not password:
            QMessageBox.warning(self, "Missing Credentials", "Please enter your email and password.")
            return

        frame_id = self._selected_frame_id()
        if not frame_id:
            QMessageBox.warning(
                self, "No Frame Selected",
                "Click Sign In to load your frames, then pick one to download."
            )
            return

        download_path = self.folder_input.text().strip()
        if not download_path:
            QMessageBox.warning(self, "No Folder", "Choose a folder to save photos to.")
            return

        # Ensure download directory exists
        if not os.path.isdir(download_path):
            try:
                os.makedirs(download_path)
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not create download directory: {e}")
                return

        # Save settings before starting
        self._save_settings()

        save_assets_path = None
        if self.save_assets_checkbox.isChecked():
            save_assets_path = os.path.join(download_path, "aura-assets.json")

        # Create and start worker
        self.worker = DownloadWorker(
            email=email,
            password=password,
            frame_id=frame_id,
            file_path=download_path,
            organize_by_year=self.year_checkbox.isChecked(),
            videos_only=self.videos_only_checkbox.isChecked(),
            save_assets_path=save_assets_path,
            parent=self
        )

        # Connect signals
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.status_changed.connect(self._on_status_changed)
        self.worker.download_complete.connect(self._on_download_complete)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished.connect(self._on_worker_finished)

        # Update UI
        self.start_btn.setText("Stop Download")
        self._set_controls_enabled(False)
        self.progress_bar.setValue(0)

        self.worker.start()

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable input controls."""
        self.email_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.sign_in_btn.setEnabled(enabled and self.sign_in_worker is None)
        self.frame_combo.setEnabled(enabled)
        self.add_frame_btn.setEnabled(enabled)
        self.folder_input.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.year_checkbox.setEnabled(enabled)
        self.videos_only_checkbox.setEnabled(enabled)
        self.save_assets_checkbox.setEnabled(enabled)
        self._update_remove_button()

    def _truncate_filename(self, filename: str, max_length: int = 35) -> str:
        """Truncate filename with ellipsis in the middle if too long."""
        if len(filename) <= max_length:
            return filename
        # Keep some chars from start and end, put ellipsis in middle
        keep_chars = (max_length - 3) // 2  # 3 for "..."
        return filename[:keep_chars] + "..." + filename[-keep_chars:]

    def _on_progress_updated(self, current: int, total: int, filename: str):
        """Handle progress update from worker."""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
        display_name = self._truncate_filename(filename)
        self.status_label.setText(f"Downloading: {display_name} ({current}/{total})")

    def _on_status_changed(self, status: str):
        """Handle status change from worker."""
        self.status_label.setText(status)

    def _on_download_complete(self, downloaded: int, skipped: int, failed: int, total: int):
        """Handle download completion."""
        self.progress_bar.setValue(100)
        # Read before exec(): the dialog's event loop runs _on_worker_finished, which clears self.worker.
        folder = self.worker.file_path
        summary = f"Downloaded: {downloaded}\nSkipped: {skipped}\nFailed: {failed}\nTotal: {total}"
        if failed:
            box = QMessageBox(
                QMessageBox.Icon.Warning,
                "Download Finished With Errors",
                f"{summary}\n\nClick Start Download again to retry the failed items. "
                f"Details are in {LOG_FILE_NAME} in the download folder.",
                parent=self,
            )
        else:
            box = QMessageBox(QMessageBox.Icon.Information, "Download Complete", summary, parent=self)
        open_btn = box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_error(self, error_msg: str):
        """Handle error from worker."""
        if "cancelled" not in error_msg.lower():
            QMessageBox.critical(self, "Error", error_msg)

    def _on_worker_finished(self):
        """Handle worker thread completion."""
        self.start_btn.setText("Start Download")
        self.start_btn.setEnabled(True)
        self.worker = None
        self._set_controls_enabled(True)
