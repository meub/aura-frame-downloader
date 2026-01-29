#!/usr/bin/env python3
"""Aura Frame Downloader - GUI Entry Point."""

import sys

from PyQt6.QtWidgets import QApplication

from aura.gui.main_window import MainWindow


def main():
    """Launch the Aura Frame Downloader GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Aura Frame Downloader")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
