"""Main window for Aura Frame Downloader GUI."""

import json
import os

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog,
    QDialogButtonBox,
)

from .download_worker import DownloadWorker


class FrameDialog(QDialog):
    """Dialog for adding/editing a frame."""

    def __init__(self, parent=None, frame_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add Frame" if frame_data is None else "Edit Frame")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Form layout for frame details
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Living Room Frame")
        form.addRow("Frame Name:", self.name_input)

        frame_id_layout = QHBoxLayout()
        self.frame_id_input = QLineEdit()
        self.frame_id_input.setPlaceholderText("Frame ID from Aura")
        frame_id_help = QLabel('<a href="https://github.com/meub/aura-frame-downloader?tab=readme-ov-file#getting-your-frame-id">Help</a>')
        frame_id_help.setOpenExternalLinks(True)
        frame_id_layout.addWidget(self.frame_id_input)
        frame_id_layout.addWidget(frame_id_help)
        form.addRow("Frame ID:", frame_id_layout)

        # Download path with browse button
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("/path/to/download/folder")
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        form.addRow("Download Path:", path_layout)

        layout.addLayout(form)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Populate if editing
        if frame_data:
            self.name_input.setText(frame_data.get('name', ''))
            self.frame_id_input.setText(frame_data.get('frame_id', ''))
            self.path_input.setText(frame_data.get('path', ''))

    def _browse_path(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder",
            self.path_input.text() or os.path.expanduser("~")
        )
        if folder:
            self.path_input.setText(folder)

    def get_data(self):
        return {
            'name': self.name_input.text().strip(),
            'frame_id': self.frame_id_input.text().strip(),
            'path': self.path_input.text().strip(),
        }

    def accept(self):
        data = self.get_data()
        if not data['name']:
            QMessageBox.warning(self, "Validation Error", "Frame name is required.")
            return
        if not data['frame_id']:
            QMessageBox.warning(self, "Validation Error", "Frame ID is required.")
            return
        if not data['path']:
            QMessageBox.warning(self, "Validation Error", "Download path is required.")
            return
        super().accept()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.frames = []  # List of frame dicts: {name, frame_id, path}
        self.settings = QSettings("AuraDownloader", "AuraFrameDownloader")
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Aura Frame Downloader")
        self.setMinimumWidth(550)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Login credentials group
        login_group = QGroupBox("Login Credentials")
        login_layout = QFormLayout(login_group)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        self.email_input.setMinimumWidth(300)
        login_layout.addRow("Email:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Your Aura password")
        self.password_input.setMinimumWidth(300)
        login_layout.addRow("Password:", self.password_input)

        layout.addWidget(login_group)

        # Frames group
        frames_group = QGroupBox("Frames")
        frames_layout = QVBoxLayout(frames_group)

        # Frame list
        self.frame_list = QListWidget()
        self.frame_list.setMaximumHeight(120)
        frames_layout.addWidget(self.frame_list)

        # Frame buttons
        frame_btn_layout = QHBoxLayout()
        self.add_frame_btn = QPushButton("Add Frame")
        self.add_frame_btn.clicked.connect(self._add_frame)
        self.edit_frame_btn = QPushButton("Edit")
        self.edit_frame_btn.clicked.connect(self._edit_frame)
        self.remove_frame_btn = QPushButton("Remove")
        self.remove_frame_btn.clicked.connect(self._remove_frame)
        frame_btn_layout.addWidget(self.add_frame_btn)
        frame_btn_layout.addWidget(self.edit_frame_btn)
        frame_btn_layout.addWidget(self.remove_frame_btn)
        frame_btn_layout.addStretch()
        frames_layout.addLayout(frame_btn_layout)

        layout.addWidget(frames_group)

        # Download options group
        options_group = QGroupBox("Download Options")
        options_layout = QVBoxLayout(options_group)

        # Frame selector
        frame_select_layout = QHBoxLayout()
        frame_select_layout.addWidget(QLabel("Download from:"))
        self.frame_combo = QComboBox()
        self.frame_combo.setMinimumWidth(200)
        frame_select_layout.addWidget(self.frame_combo)
        frame_select_layout.addStretch()
        options_layout.addLayout(frame_select_layout)

        # Organize by year
        self.year_checkbox = QCheckBox("Organize photos by year")
        options_layout.addWidget(self.year_checkbox)

        layout.addWidget(options_group)

        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Add your credentials and frames to begin")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def _load_settings(self):
        """Load saved settings."""
        self.email_input.setText(self.settings.value("email", ""))
        self.password_input.setText(self.settings.value("password", ""))
        self.year_checkbox.setChecked(self.settings.value("organize_by_year", False, type=bool))

        # Load frames
        frames_json = self.settings.value("frames", "[]")
        try:
            self.frames = json.loads(frames_json)
        except json.JSONDecodeError:
            self.frames = []

        self._refresh_frame_list()

        # Restore selected frame
        selected_frame = self.settings.value("selected_frame", "")
        if selected_frame:
            index = self.frame_combo.findText(selected_frame)
            if index >= 0:
                self.frame_combo.setCurrentIndex(index)

    def _save_settings(self):
        """Save current settings."""
        self.settings.setValue("email", self.email_input.text())
        self.settings.setValue("password", self.password_input.text())
        self.settings.setValue("organize_by_year", self.year_checkbox.isChecked())
        self.settings.setValue("frames", json.dumps(self.frames))
        self.settings.setValue("selected_frame", self.frame_combo.currentText())

    def closeEvent(self, event):
        """Save settings on close."""
        self._save_settings()
        super().closeEvent(event)

    def _refresh_frame_list(self):
        """Refresh the frame list and combo box."""
        self.frame_list.clear()
        self.frame_combo.clear()

        for frame in self.frames:
            # Add to list widget
            item = QListWidgetItem(f"{frame['name']} ({frame['frame_id']})")
            item.setData(Qt.ItemDataRole.UserRole, frame)
            self.frame_list.addItem(item)

            # Add to combo box
            self.frame_combo.addItem(frame['name'])

        # Update status
        if self.frames:
            self.status_label.setText("Ready to download")
        else:
            self.status_label.setText("Add your credentials and frames to begin")

    def _add_frame(self):
        """Open dialog to add a new frame."""
        dialog = FrameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.frames.append(dialog.get_data())
            self._refresh_frame_list()
            self._save_settings()

    def _edit_frame(self):
        """Edit the selected frame."""
        current_item = self.frame_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a frame to edit.")
            return

        index = self.frame_list.currentRow()
        frame_data = self.frames[index]

        dialog = FrameDialog(self, frame_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.frames[index] = dialog.get_data()
            self._refresh_frame_list()
            self._save_settings()

    def _remove_frame(self):
        """Remove the selected frame."""
        current_item = self.frame_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a frame to remove.")
            return

        index = self.frame_list.currentRow()
        frame_name = self.frames[index]['name']

        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Are you sure you want to remove '{frame_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.frames[index]
            self._refresh_frame_list()
            self._save_settings()

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
        password = self.password_input.text().strip()

        if not email or not password:
            QMessageBox.warning(self, "Missing Credentials", "Please enter your email and password.")
            return

        if not self.frames:
            QMessageBox.warning(self, "No Frames", "Please add at least one frame.")
            return

        selected_name = self.frame_combo.currentText()
        if not selected_name:
            QMessageBox.warning(self, "No Frame Selected", "Please select a frame to download from.")
            return

        # Find selected frame
        selected_frame = None
        for frame in self.frames:
            if frame['name'] == selected_name:
                selected_frame = frame
                break

        if not selected_frame:
            QMessageBox.warning(self, "Error", "Selected frame not found.")
            return

        # Ensure download directory exists
        download_path = selected_frame['path']
        if not os.path.isdir(download_path):
            try:
                os.makedirs(download_path)
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not create download directory: {e}")
                return

        # Save settings before starting
        self._save_settings()

        # Create and start worker
        self.worker = DownloadWorker(
            email=email,
            password=password,
            frame_id=selected_frame['frame_id'],
            file_path=download_path,
            organize_by_year=self.year_checkbox.isChecked(),
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
        self.frame_list.setEnabled(enabled)
        self.add_frame_btn.setEnabled(enabled)
        self.edit_frame_btn.setEnabled(enabled)
        self.remove_frame_btn.setEnabled(enabled)
        self.frame_combo.setEnabled(enabled)
        self.year_checkbox.setEnabled(enabled)

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

    def _on_download_complete(self, downloaded: int, skipped: int, total: int):
        """Handle download completion."""
        self.progress_bar.setValue(100)
        QMessageBox.information(
            self,
            "Download Complete",
            f"Downloaded: {downloaded}\nSkipped: {skipped}\nTotal: {total}"
        )

    def _on_error(self, error_msg: str):
        """Handle error from worker."""
        if "cancelled" not in error_msg.lower():
            QMessageBox.critical(self, "Error", error_msg)

    def _on_worker_finished(self):
        """Handle worker thread completion."""
        self.start_btn.setText("Start Download")
        self.start_btn.setEnabled(True)
        self._set_controls_enabled(True)
        self.worker = None
