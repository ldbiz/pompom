"""Virtual-desktop pinning via the Windows Immersive Shell COM API.

Windows has no documented API for the Task View "Show this window on all
desktops" toggle. This module uses the same undocumented shell interfaces
as VirtualDesktopAccessor / pyvda (stable across Windows 10 and 11).

Note: pinning only works for regular windows. The shell keeps no view for
WS_EX_TOOLWINDOW windows (GetViewForHwnd fails), which are instead forced
onto every desktop by the window manager.
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from ctypes import POINTER, byref, c_int, c_long, c_void_p

_CLSCTX_LOCAL_SERVER = 0x4


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _GUID:
    u = uuid.UUID(text)
    return _GUID(
        u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:])
    )


_CLSID_IMMERSIVE_SHELL = _guid("C2F03A33-21F5-47FA-B4BB-156362A2F239")
_IID_ISERVICE_PROVIDER = _guid("6D5140C1-7436-11CE-8034-00AA006009FA")
_IID_IAPPLICATION_VIEW_COLLECTION = _guid("1841C6D7-4F9D-42C0-AF41-8747538F10E5")
_CLSID_VIRTUAL_DESKTOP_PINNED_APPS = _guid("B5A399E7-1C87-46B8-88E9-FC5747B171BD")
_IID_IVIRTUAL_DESKTOP_PINNED_APPS = _guid("4CE81583-1E4C-4632-A621-07A53543148F")

# Vtable slots (IUnknown occupies slots 0-2).
_SLOT_RELEASE = 2            # IUnknown::Release
_SLOT_QUERY_SERVICE = 3      # IServiceProvider::QueryService
_SLOT_GET_VIEW_FOR_HWND = 6  # IApplicationViewCollection::GetViewForHwnd
_SLOT_IS_VIEW_PINNED = 6     # IVirtualDesktopPinnedApps::IsViewPinned
_SLOT_PIN_VIEW = 7           # IVirtualDesktopPinnedApps::PinView
_SLOT_UNPIN_VIEW = 8         # IVirtualDesktopPinnedApps::UnpinView


def _method(obj: c_void_p, slot: int, *argtypes):
    vtable = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    return ctypes.WINFUNCTYPE(c_long, c_void_p, *argtypes)(vtable[slot])


def _release(obj: c_void_p) -> None:
    if obj:
        _method(obj, _SLOT_RELEASE)(obj)


def set_pinned_to_all_desktops(hwnd: int, pinned: bool) -> bool:
    """Pin (show on every virtual desktop) or unpin *hwnd*.

    Returns True on success (including when the state already matched).
    The window must have been shown at least once, or the shell has no
    view for it yet and this fails.
    """
    if sys.platform != "win32" or not hwnd:
        return False

    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    shell = c_void_p()
    hr = ole32.CoCreateInstance(
        byref(_CLSID_IMMERSIVE_SHELL),
        None,
        _CLSCTX_LOCAL_SERVER,
        byref(_IID_ISERVICE_PROVIDER),
        byref(shell),
    )
    if hr:
        return False

    collection = c_void_p()
    pinned_apps = c_void_p()
    view = c_void_p()
    try:
        query = _method(
            shell, _SLOT_QUERY_SERVICE, POINTER(_GUID), POINTER(_GUID), POINTER(c_void_p)
        )
        if query(
            shell,
            byref(_IID_IAPPLICATION_VIEW_COLLECTION),
            byref(_IID_IAPPLICATION_VIEW_COLLECTION),
            byref(collection),
        ):
            return False
        if query(
            shell,
            byref(_CLSID_VIRTUAL_DESKTOP_PINNED_APPS),
            byref(_IID_IVIRTUAL_DESKTOP_PINNED_APPS),
            byref(pinned_apps),
        ):
            return False

        get_view = _method(
            collection, _SLOT_GET_VIEW_FOR_HWND, ctypes.c_ssize_t, POINTER(c_void_p)
        )
        if get_view(collection, hwnd, byref(view)):
            return False

        state = c_int()
        is_pinned = _method(
            pinned_apps, _SLOT_IS_VIEW_PINNED, c_void_p, POINTER(c_int)
        )
        if is_pinned(pinned_apps, view, byref(state)):
            return False
        if bool(state.value) == pinned:
            return True

        slot = _SLOT_PIN_VIEW if pinned else _SLOT_UNPIN_VIEW
        return _method(pinned_apps, slot, c_void_p)(pinned_apps, view) == 0
    finally:
        _release(view)
        _release(pinned_apps)
        _release(collection)
        _release(shell)
