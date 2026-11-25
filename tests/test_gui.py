"""Tests for the desktop app, run offscreen against a throwaway settings file."""

import json
import os
import time

import pytest
from PyQt6.QtCore import QSettings, QStandardPaths
from PyQt6.QtWidgets import QDialog, QMessageBox

import aura.gui.download_worker as download_worker
import aura.gui.main_window as main_window
from aura.exceptions import NetworkError
from helpers import FRAME_1, FRAME_2, FRAME_3

ACCOUNT_FRAMES = [
    {"id": FRAME_1, "name": "Living Room", "num_assets": 4922},
    {"id": FRAME_3, "name": "Oma’s Frame: Upstairs", "num_assets": 1},
]


@pytest.fixture
def settings_path(tmp_path, monkeypatch):
    """Point the window's QSettings at an INI file in tmp_path instead of the real saved settings."""
    path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(main_window, "QSettings", lambda *args: QSettings(path, QSettings.Format.IniFormat))
    return path


def saved(settings_path):
    return QSettings(settings_path, QSettings.Format.IniFormat)


@pytest.fixture
def account(monkeypatch):
    """Fake sign-in: records credentials and returns ACCOUNT_FRAMES (or raises state['error'])."""
    state = {"frames": ACCOUNT_FRAMES, "error": None, "sign_ins": []}

    def create_session(email, password):
        state["sign_ins"].append((email, password))
        if state["error"]:
            raise state["error"]
        return "session"

    monkeypatch.setattr(download_worker, "create_session", create_session)
    monkeypatch.setattr(download_worker, "get_frames", lambda session: state["frames"])
    return state


@pytest.fixture
def dialogs(monkeypatch):
    """Record warning dialogs instead of showing them."""
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda parent, title, text, *a: shown.append((title, text))))
    return shown


def wait_for(qapp, condition, timeout=5.0):
    deadline = time.time() + timeout
    while not condition() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert condition(), "timed out waiting for the window"


def combo_items(window):
    return [(window.frame_combo.itemText(i), window.frame_combo.itemData(i)) for i in range(window.frame_combo.count())]


def pictures(*parts):
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    return os.path.join(root, "Aura", *parts)


def signed_in_window(qapp, settings_path, account):
    settings = saved(settings_path)
    settings.setValue("email", "someone@example.com")
    settings.setValue("password", " pw with spaces ")
    settings.sync()
    window = main_window.MainWindow()
    wait_for(qapp, lambda: window.sign_in_worker is None)
    return window


def test_first_launch_asks_to_sign_in(qapp, settings_path, account):
    window = main_window.MainWindow()
    assert window.sign_in_worker is None and account["sign_ins"] == []
    assert window.frame_combo.count() == 0
    assert "Sign In" in window.status_label.text()


def test_saved_details_sign_in_automatically_and_list_frames(qapp, settings_path, account):
    window = signed_in_window(qapp, settings_path, account)
    assert account["sign_ins"] == [("someone@example.com", " pw with spaces ")]
    assert combo_items(window) == [
        ("Living Room (4,922 photos)", FRAME_1),
        ("Oma’s Frame: Upstairs (1 photo)", FRAME_3),
    ]
    assert window.status_label.text().startswith("Signed in. Found 2 frames.")
    assert window.sign_in_btn.isEnabled()


def test_frames_from_2_1_are_migrated(qapp, settings_path, account):
    old = saved(settings_path)
    old.setValue("email", "someone@example.com")
    old.setValue("password", "pw")
    old.setValue("frames", json.dumps([
        {"name": "Living Room", "frame_id": f"https://app.auraframes.com/frame/{FRAME_1}", "path": "/photos/living"},
        {"name": "Kitchen", "frame_id": FRAME_2, "path": ""},
    ]))
    old.setValue("selected_frame", "Kitchen")
    old.sync()

    window = main_window.MainWindow()
    # Before sign-in finishes, the migrated frames are listed and Kitchen is still selected.
    assert combo_items(window) == [("Living Room (added by ID)", FRAME_1), ("Kitchen (added by ID)", FRAME_2)]
    assert window._selected_frame_id() == FRAME_2
    settings = saved(settings_path)
    assert not settings.contains("frames") and not settings.contains("selected_frame")
    assert json.loads(settings.value("folders")) == {FRAME_1: "/photos/living"}

    wait_for(qapp, lambda: window.sign_in_worker is None)
    # Living Room is on the account now, so its "added by ID" copy goes; its folder stays.
    assert window.manual_frames == [{"id": FRAME_2, "name": "Kitchen"}]
    assert [item[1] for item in combo_items(window)] == [FRAME_1, FRAME_3, FRAME_2]
    assert window._selected_frame_id() == FRAME_2
    window.frame_combo.setCurrentIndex(0)
    assert window.folder_input.text() == "/photos/living"


def test_folders_default_per_frame_and_remember_changes(qapp, settings_path, account):
    window = signed_in_window(qapp, settings_path, account)
    window.frame_combo.setCurrentIndex(0)
    assert window.folder_input.text() == pictures("Living Room")
    window.frame_combo.setCurrentIndex(1)
    # Characters Windows rejects in folder names are replaced.
    assert window.folder_input.text() == pictures("Oma’s Frame_ Upstairs")

    window.folder_input.textEdited.emit("/photos/oma")
    window.frame_combo.setCurrentIndex(0)
    window.frame_combo.setCurrentIndex(1)
    assert window.folder_input.text() == "/photos/oma"

    window._save_settings()
    assert json.loads(saved(settings_path).value("folders")) == {FRAME_3: "/photos/oma"}
    assert saved(settings_path).value("selected_frame_id") == FRAME_3


def test_only_frames_added_by_id_can_be_removed(qapp, settings_path, account):
    window = signed_in_window(qapp, settings_path, account)
    assert not window.remove_frame_btn.isEnabled()
    window.manual_frames.append({"id": FRAME_2, "name": "Cabin"})
    window._refresh_frame_combo(select_id=FRAME_2)
    assert window.remove_frame_btn.isEnabled()


def test_add_by_id_rejects_text_without_a_frame_id(qapp, settings_path, dialogs):
    dialog = main_window.FrameDialog()
    dialog.name_input.setText("Cabin")
    dialog.frame_id_input.setText("cabin@send.auraframes.com")
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "doesn't look like a Frame ID" in dialogs[-1][1]


def test_add_by_id_accepts_a_pasted_address(qapp, settings_path, dialogs):
    dialog = main_window.FrameDialog()
    dialog.name_input.setText("Cabin")
    dialog.frame_id_input.setText(f"  https://app.auraframes.com/frame/{FRAME_2}?tab=photos ")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.get_data() == {"id": FRAME_2, "name": "Cabin"}


def test_sign_in_failure_at_launch_only_updates_the_status_line(qapp, settings_path, account, dialogs):
    account["error"] = NetworkError("Couldn't reach Aura. Check your internet connection and try again.")
    window = signed_in_window(qapp, settings_path, account)
    assert window.status_label.text().startswith("Couldn't reach Aura")
    assert dialogs == []


def test_sign_in_failure_after_a_click_shows_a_dialog(qapp, settings_path, account, dialogs):
    window = signed_in_window(qapp, settings_path, account)
    account["error"] = NetworkError("Couldn't reach Aura. Check your internet connection and try again.")
    window._sign_in(quiet=False)
    wait_for(qapp, lambda: window.sign_in_worker is None)
    assert dialogs == [("Sign In Failed", "Couldn't reach Aura. Check your internet connection and try again.")]
    # The frames from the earlier sign-in stay listed.
    assert [item[1] for item in combo_items(window)] == [FRAME_1, FRAME_3]


def test_completion_dialog_opens_the_download_folder(qapp, settings_path, account, monkeypatch):
    window = signed_in_window(qapp, settings_path, account)
    opened = []
    monkeypatch.setattr(main_window.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toLocalFile())))

    def click_open_folder(box):
        next(button for button in box.buttons() if button.text() == "Open Folder").click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", click_open_folder)

    class FinishedWorker:
        file_path = "/photos/living"

    window.worker = FinishedWorker()
    window._on_download_complete(10, 2, 0, 12)
    assert opened == ["/photos/living"]


def test_download_worker_writes_a_log_file(qapp, tmp_path, monkeypatch):
    def download(**kwargs):
        download_worker.LOGGER.error("Item 7 failed to download: boom")
        return (1, 0, 1, 2)

    monkeypatch.setattr(download_worker, "download_photos_from_aura", download)
    worker = download_worker.DownloadWorker("e", "p", FRAME_1, str(tmp_path))
    results = []
    worker.download_complete.connect(lambda *counts: results.append(counts))
    worker.run()
    assert results == [(1, 0, 1, 2)]
    assert "Item 7 failed" in (tmp_path / download_worker.LOG_FILE_NAME).read_text(encoding="utf-8")


def test_unexpected_errors_are_logged_with_a_traceback(qapp, tmp_path, monkeypatch):
    def crash(**kwargs):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(download_worker, "download_photos_from_aura", crash)
    worker = download_worker.DownloadWorker("e", "p", FRAME_1, str(tmp_path))
    errors = []
    worker.error_occurred.connect(errors.append)
    worker.run()
    assert errors == ["Unexpected error: Expecting value: line 1 column 1 (char 0)"]
    assert "Traceback" in (tmp_path / download_worker.LOG_FILE_NAME).read_text(encoding="utf-8")
    assert download_worker.logging.getLogger("aura").handlers == []
