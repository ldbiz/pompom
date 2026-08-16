"""Windows DWM chrome tweaks for frameless translucent windows."""

from __future__ import annotations

import ctypes
import sys
from ctypes import byref, c_uint


# Windows 11 Build 22000+.
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWCP_DONOTROUND = 1
_DWMWA_COLOR_NONE = 0xFFFFFFFE


def clear_dwm_border(hwnd: int) -> None:
    """Remove the thin square DWM outline around a frameless translucent HWND.

    On Windows 11, DWM draws a 1px rectangular border around the window even
    when the content is a rounded alpha-masked card. Suppressing the border
    (and system corner rounding) leaves only the card's own rounded shape.
    No-ops on older Windows or on failure.
    """
    if sys.platform != "win32" or not hwnd:
        return
    try:
        dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
    except AttributeError:
        return

    corner = c_uint(_DWMWCP_DONOTROUND)
    dwmapi.DwmSetWindowAttribute(
        hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE, byref(corner), ctypes.sizeof(corner)
    )

    color = c_uint(_DWMWA_COLOR_NONE)
    dwmapi.DwmSetWindowAttribute(
        hwnd, _DWMWA_BORDER_COLOR, byref(color), ctypes.sizeof(color)
    )
