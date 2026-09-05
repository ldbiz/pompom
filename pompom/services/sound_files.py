"""Managed per-user custom sound files."""

from __future__ import annotations

import os
import shutil
import uuid
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from ..constants import _DING_PATH, _TICKTOCK_PATH


class SoundKind(Enum):
    """Identifies a pompom sound slot."""

    TICK = "tick"
    BELL = "bell"


_MANAGED_NAMES: dict[SoundKind, str] = {
    SoundKind.TICK: "ticktock.wav",
    SoundKind.BELL: "ding.wav",
}

_FACTORY_PATHS: dict[SoundKind, Path] = {
    SoundKind.TICK: _TICKTOCK_PATH,
    SoundKind.BELL: _DING_PATH,
}


def custom_sounds_dir(custom_dir: Path | None = None) -> Path:
    """Return the managed custom-sounds directory."""
    if custom_dir is not None:
        return custom_dir
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "sounds"


def managed_path(kind: SoundKind, custom_dir: Path | None = None) -> Path:
    """Path to the managed custom copy for *kind*, which may not exist."""
    return custom_sounds_dir(custom_dir) / _MANAGED_NAMES[kind]


def has_custom(kind: SoundKind, custom_dir: Path | None = None) -> bool:
    """Return whether a managed custom copy exists for *kind*."""
    return managed_path(kind, custom_dir).is_file()


def resolve_sound_path(kind: SoundKind, custom_dir: Path | None = None) -> Path:
    """Return the managed custom copy if present, otherwise the factory path."""
    custom = managed_path(kind, custom_dir)
    if custom.is_file():
        return custom
    return _FACTORY_PATHS[kind]


def _remove_temp_silently(path: Path) -> None:
    """Remove a temporary file without masking an earlier operation error."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def install_custom(
    kind: SoundKind,
    source: Path | str,
    *,
    custom_dir: Path | None = None,
) -> None:
    """Copy *source* into the managed location for *kind*."""
    src = Path(source)
    if src.suffix.lower() != ".wav":
        raise ValueError("Please choose a WAV file.")
    if not src.is_file():
        raise ValueError("The selected file could not be read.")

    dest_dir = custom_sounds_dir(custom_dir)
    managed = managed_path(kind, custom_dir)
    temp = dest_dir / f".{managed.name}.{uuid.uuid4().hex}.tmp"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, temp)
        os.replace(temp, managed)
    except OSError as exc:
        _remove_temp_silently(temp)
        raise ValueError("Could not save the custom sound.") from exc


def reset_custom(kind: SoundKind, *, custom_dir: Path | None = None) -> None:
    """Remove the managed custom copy for *kind*."""
    managed = managed_path(kind, custom_dir)
    if not managed.is_file():
        return
    try:
        managed.unlink()
    except OSError as exc:
        raise ValueError("Could not reset the custom sound.") from exc


def reset_all_custom(*, custom_dir: Path | None = None) -> None:
    """Remove all managed custom copies."""
    for kind in SoundKind:
        reset_custom(kind, custom_dir=custom_dir)
