"""Application startup for pompom."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .constants import _SETTINGS_ORG
from .platform.win_autostart import set_start_with_windows
from .settings import AppSettings
from .ui.main_widget import PompomWidget
from .ui.tray import _setup_tray


def main() -> int:
    """Start the pompom desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("pompom")
    app.setOrganizationName(_SETTINGS_ORG)
    # Keep the process alive even if the main window is hidden;
    # the tray icon provides Close / quit.
    app.setQuitOnLastWindowClosed(False)

    settings = AppSettings()
    if settings.start_with_windows():
        # Repair the Startup shortcut after an install path changes or reinstall.
        set_start_with_windows(True)
    widget = PompomWidget(settings)
    tray = _setup_tray(app, widget)
    widget.set_tray_icon(tray)

    # Keep a Python reference to the tray icon for the lifetime of the app.
    app._pompom_tray = tray  # type: ignore[attr-defined]

    # Persist state whenever the application quits (tray Close or OS shutdown).
    app.aboutToQuit.connect(widget._save_state)

    widget.show()
    return app.exec()
