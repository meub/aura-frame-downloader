#!/usr/bin/env python3
"""Aura Frame Downloader - GUI Entry Point."""

import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from aura.gui.main_window import MainWindow


def main():
    """Launch the Aura Frame Downloader GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Aura Frame Downloader")

    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), 'aura', 'gui', 'resources', 'icon.svg')
    app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
