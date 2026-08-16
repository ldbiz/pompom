"""Window flags, taskbar hiding and virtual-desktop behavior for floating windows.

pompom's floating windows must satisfy three constraints on Windows:

1. never show a taskbar button (the tray icon is the app's only presence),
2. optionally stay on top of other windows,
3. optionally appear on every virtual desktop.

``Qt.Tool`` (WS_EX_TOOLWINDOW) gives you 1 but *forces* 3: Windows shows tool
windows on every virtual desktop unconditionally, and the pinning API has no
view for them. So floating windows here are plain frameless windows, kept off
the taskbar by a hidden owner window (Qt transient parent), and constraint 3
is toggled with the virtual-desktop pinning API in ``platform.win_desktops``.
"""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QWidget

from ..platform.win_desktops import set_pinned_to_all_desktops
from ..platform.win_chrome import clear_dwm_border

_hidden_owner: QWindow | None = None


def _owner_window() -> QWindow:
    """Hidden native window used as Win32 owner; owned windows get no taskbar button.

    Deliberately NOT a tool window: owned windows follow their owner across
    virtual desktops, and tool windows live on all of them.
    """
    global _hidden_owner
    if _hidden_owner is None:
        owner = QWindow()
        owner.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        owner.setGeometry(-32000, -32000, 1, 1)
        owner.create()
        _hidden_owner = owner
    return _hidden_owner


def init_floating_window(widget: QWidget, *, always_on_top: bool) -> None:
    """One-time setup for a frameless floating window. Call before first show.

    Any attributes that must precede native window creation (e.g.
    WA_TranslucentBackground) must already be set on *widget*.
    """
    flags = (
        Qt.WindowType.Window
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    if always_on_top:
        flags |= Qt.WindowType.WindowStaysOnTopHint
    widget.setWindowFlags(flags)
    if sys.platform == "win32":
        widget.winId()  # force native window creation so windowHandle() exists
        handle = widget.windowHandle()
        if handle is not None:
            handle.setTransientParent(_owner_window())
        clear_dwm_border(int(widget.winId()))


def schedule_desktop_sync(widget: QWidget, *, show_on_all_desktops: bool) -> None:
    """Pin/unpin *widget* once the pending show has completed.

    Deferred one event-loop turn because the shell only creates a view for
    the window after it has actually been shown.
    """
    if sys.platform != "win32":
        return

    def _sync() -> None:
        try:
            if widget.isVisible():
                hwnd = int(widget.winId())
                clear_dwm_border(hwnd)
                set_pinned_to_all_desktops(hwnd, show_on_all_desktops)
        except RuntimeError:
            pass  # widget was deleted before the timer fired

    QTimer.singleShot(0, _sync)


def clamp_to_screen(widget: QWidget) -> None:
    """Keep *widget* fully within the current screen's available area."""
    screen = widget.screen()
    if screen is None:
        return
    avail = screen.availableGeometry()
    geo = widget.frameGeometry()
    x, y = geo.x(), geo.y()
    if geo.right() > avail.right():
        x = avail.right() - geo.width()
    if x < avail.left():
        x = avail.left()
    if geo.bottom() > avail.bottom():
        y = avail.bottom() - geo.height()
    if y < avail.top():
        y = avail.top()
    if (x, y) != (geo.x(), geo.y()):
        widget.move(x, y)


def focus_floating_window(widget: QWidget) -> None:
    """Raise *widget* and try to give it keyboard focus (e.g. after a tray click)."""
    widget.raise_()
    widget.activateWindow()
    if sys.platform == "win32" and widget.isVisible():
        hwnd = int(widget.winId())
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)  # type: ignore[attr-defined]


def apply_window_behavior(
    widget: QWidget, *, always_on_top: bool, show_on_all_desktops: bool
) -> None:
    """Apply both toggles to an already-initialized floating window."""
    was_visible = widget.isVisible()
    geo = widget.geometry()
    widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, always_on_top)
    # setWindowFlag recreates the HWND and can drop size/position.
    widget.setGeometry(geo)
    if was_visible and not widget.isVisible():
        widget.show()  # setWindowFlag hides the window when flags change
    if sys.platform == "win32":
        clear_dwm_border(int(widget.winId()))
    schedule_desktop_sync(widget, show_on_all_desktops=show_on_all_desktops)
