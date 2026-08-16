# Repository analysis

> This analysis is AI-generated and should be treated as indicative, not
> authoritative. Verify important claims against the repository source before
> relying on them for design or implementation decisions.

## Product and scope

`pompom` 1.0.0 is a small Windows-first Pomodoro timer built with Python 3.10+
and PySide6. It provides a frameless floating timer, task and options panels,
and a system-tray icon. It has no backend, accounts, application networking,
analytics, or telemetry.

The default cycle is four 25-minute work sessions with 5-minute short breaks
and a 30-minute long break. Transitions start automatically; after the long
break the app returns to session 1, stopped. Breaks show suggestions from a
shuffled deck.

## Runtime

`pompom.py`, `python -m pompom`, and the installed `pompom` command all lead to
[`pompom/app.py`](pompom/app.py). Startup creates the Qt application, settings,
main widget, and tray icon, and repairs the Startup-folder shortcut when
**Start with Windows** is enabled.

[`pompom/ui/main_widget.py`](pompom/ui/main_widget.py) owns timer transitions,
painting, menus, input, and panel coordination. A one-second `QTimer` updates
the transient [`UIState`](pompom/state.py). On work-session completion, the
optional momentum prompt allows a five-minute extension or advances after a
skip or 12-second timeout. Break completion advances to the next work session.
Ticking audio is optional and separate from the overall mute setting.

The task panel supports add, edit, delete, complete, and sequential or shuffled
advancement. The card can be dragged and aspect-ratio resized. Space, M, and T
control start/pause, mute, and task visibility; Enter/Escape handle momentum.
These shortcuts are widget-local, not global hotkeys.

## Code map

- [`pompom/ui/`](pompom/ui/) — timer card, task/options/about panels, tray, and
  floating-window utilities.
- [`pompom/models/tasks.py`](pompom/models/tasks.py) — task queue and JSON
  serialization.
- [`pompom/settings.py`](pompom/settings.py) — typed `QSettings` access.
- [`pompom/services/audio.py`](pompom/services/audio.py) — best-effort tick and
  completion playback.
- [`pompom/platform/`](pompom/platform/) — Windows autostart, DWM chrome, and
  virtual-desktop integration.
- [`pompom/constants.py`](pompom/constants.py) — defaults, dimensions, timings,
  suggestions, and asset paths.

## Persistence

Settings are stored as plain-text INI at
`%APPDATA%\pompom\pompom.ini`, not in the registry.

Persisted data includes durations; mute, ticking, momentum, always-on-top, and
all-desktops preferences; tasks; main-window geometry; task-panel visibility;
and Start-with-Windows. Timer mode, remaining time, cycle index, running state,
momentum state, and manually positioned auxiliary-panel offsets are not
persisted. Every launch starts at a full session 1, stopped.

Options are written when changed. Tasks and current layout are captured on
task changes, cycle transitions, and clean application exit; moving or resizing
alone is therefore not crash-safe.

## Windows integration

The hidden owner window keeps the timer out of the taskbar. The app also
supports optional always-on-top behavior, DWM border cleanup, multi-monitor
clamping, and showing the window on all virtual desktops. Virtual-desktop
pinning uses undocumented Windows Immersive Shell COM interfaces and may fail
silently if Windows changes them.

Autostart uses `pompom.lnk` in the current user's Startup folder. The source
version creates it through non-interactive PowerShell and WScript.Shell; no
registry Run key or elevation is used. A source shortcut depends on that Python
environment remaining available.

## Build and distribution

[`pompom.spec`](pompom.spec) creates a one-folder, windowed PyInstaller build
with QtMultimedia and repository assets. [`scripts/build_installer.ps1`](scripts/build_installer.ps1)
then uses Inno Setup 7 to produce
`dist/installer/pompom-1.0.0-setup.exe`.

The Inno Setup installer is per-user by default, supports custom install and
Start Menu locations, and offers desktop and autostart shortcuts without
requesting administrator access. It is unsigned; there is no MSI/MSIX, winget
package, updater, or release CI. The Hatch wheel configuration includes only
the Python package, so it does not currently bundle the root `images/` and
`sounds/` assets; use the source tree or PyInstaller distribution.

## Validation and boundaries

There is no automated test suite, lint/type-check configuration, or CI
workflow. Important Windows smoke checks are:

1. Run a shortened complete cycle, including momentum and audio settings.
2. Exercise task editing/advancement and verify clean-restart persistence.
3. Check keyboard, tray, resize, multi-monitor, and virtual-desktop behavior.
4. Login-test the Startup-folder shortcut.
5. Build, install, launch, and uninstall the packaged application.

Current boundaries include no global hotkeys, statistics, sync, i18n,
comprehensive screen-reader support for the painted card, signing, or updates.

## Licensing

Application code is MIT licensed. 
