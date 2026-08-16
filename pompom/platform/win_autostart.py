"""Per-user Windows login startup without registry access."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SHORTCUT_NAME = "pompom.lnk"


def _startup_parts() -> tuple[str, str, str]:
    """Return shortcut target, arguments, and working directory."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)
        return str(executable), "", str(executable.parent)

    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        executable = pythonw
    project_dir = Path(__file__).resolve().parents[2]
    return str(executable), "-m pompom", str(project_dir)


def _startup_shortcut() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / _SHORTCUT_NAME
    )


def set_start_with_windows(enabled: bool) -> bool:
    """Create or remove pompom's per-user Startup-folder shortcut.

    The shortcut is created through Windows' built-in WScript.Shell COM object,
    invoked by PowerShell without loading a profile or executing a script file.
    """
    if sys.platform != "win32":
        return not enabled

    shortcut = _startup_shortcut()
    if shortcut is None:
        return False

    try:
        if not enabled:
            shortcut.unlink(missing_ok=True)
            return True

        shortcut.parent.mkdir(parents=True, exist_ok=True)
        target, arguments, working_directory = _startup_parts()
        env = os.environ.copy()
        env.update(
            {
                "POMPOM_SHORTCUT": str(shortcut),
                "POMPOM_TARGET": target,
                "POMPOM_ARGUMENTS": arguments,
                "POMPOM_WORKING_DIR": working_directory,
            }
        )
        command = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut("
            "$env:POMPOM_SHORTCUT);"
            "$s.TargetPath=$env:POMPOM_TARGET;"
            "$s.Arguments=$env:POMPOM_ARGUMENTS;"
            "$s.WorkingDirectory=$env:POMPOM_WORKING_DIR;"
            "$s.Description='pompom Pomodoro timer';"
            "$s.Save()"
        )
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            env=env,
            capture_output=True,
            check=False,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return completed.returncode == 0 and shortcut.exists()
    except (OSError, subprocess.SubprocessError):
        return False
