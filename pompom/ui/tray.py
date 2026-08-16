"""System tray icon and menu setup."""

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .main_widget import PompomWidget


def _make_tray_icon(size: int = 64) -> QIcon:
    """Create a filled red-circle icon programmatically (no image files needed)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#8F3030"))
    painter.setPen(Qt.PenStyle.NoPen)
    m = 2
    painter.drawEllipse(m, m, size - 2 * m, size - 2 * m)
    painter.end()
    return QIcon(pix)


def _setup_tray(app: QApplication, widget: PompomWidget) -> QSystemTrayIcon:
    """Create and return the system-tray icon with its right-click menu."""
    tray = QSystemTrayIcon(_make_tray_icon(), app)
    tray.setToolTip("pompom — right-click for menu")

    menu = QMenu()

    def _rebuild_menu() -> None:
        menu.clear()
        widget.populate_action_menu(menu, include_timer_actions=False)

    menu.aboutToShow.connect(_rebuild_menu)

    tray.setContextMenu(menu)

    def _on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left or right click on the tray icon — bring pompom back when buried.
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Context,
        ):
            widget.bring_to_front()

    tray.activated.connect(_on_tray_activated)
    tray.show()
    return tray
