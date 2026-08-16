"""Typed application settings wrapper."""

from PySide6.QtCore import QSettings

from .constants import (
    _DEFAULT_BREAK_MINS,
    _DEFAULT_LONG_BREAK_MINS,
    _DEFAULT_POMODORO_MINS,
    _SETTINGS_APP,
    _SETTINGS_ORG,
)


class AppSettings:
    """Typed QSettings wrapper; all values are persisted between app runs."""

    def __init__(self) -> None:
        self._s = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            _SETTINGS_ORG,
            _SETTINGS_APP,
        )

    def pomodoro_minutes(self) -> int:
        return int(self._s.value("pomodoro_minutes", _DEFAULT_POMODORO_MINS))

    def set_pomodoro_minutes(self, v: int) -> None:
        self._s.setValue("pomodoro_minutes", v)

    def break_minutes(self) -> int:
        return int(self._s.value("break_minutes", _DEFAULT_BREAK_MINS))

    def set_break_minutes(self, v: int) -> None:
        self._s.setValue("break_minutes", v)

    def long_break_minutes(self) -> int:
        return int(self._s.value("long_break_minutes", _DEFAULT_LONG_BREAK_MINS))

    def set_long_break_minutes(self, v: int) -> None:
        self._s.setValue("long_break_minutes", v)

    def muted(self) -> bool:
        return self._s.value("muted", False, type=bool)

    def set_muted(self, v: bool) -> None:
        self._s.setValue("muted", v)

    def ticking_enabled(self) -> bool:
        return self._s.value("ticking_enabled", True, type=bool)

    def set_ticking_enabled(self, v: bool) -> None:
        self._s.setValue("ticking_enabled", v)

    def momentum_enabled(self) -> bool:
        return self._s.value("momentum_enabled", False, type=bool)

    def set_momentum_enabled(self, v: bool) -> None:
        self._s.setValue("momentum_enabled", v)

    def always_on_top(self) -> bool:
        return self._s.value("always_on_top", True, type=bool)

    def set_always_on_top(self, v: bool) -> None:
        self._s.setValue("always_on_top", v)

    def show_on_all_desktops(self) -> bool:
        return self._s.value("show_on_all_desktops", True, type=bool)

    def set_show_on_all_desktops(self, v: bool) -> None:
        self._s.setValue("show_on_all_desktops", v)

    def start_with_windows(self) -> bool:
        return self._s.value("start_with_windows", False, type=bool)

    def set_start_with_windows(self, v: bool) -> None:
        self._s.setValue("start_with_windows", v)

    # ── Task queue persistence ────────────────────────────────────────────────

    def tasks_json(self) -> str:
        return str(self._s.value("tasks_json", ""))

    def set_tasks_json(self, v: str) -> None:
        self._s.setValue("tasks_json", v)

    # ── Window geometry persistence ─────────────────────────────────────────

    def saved_window_x(self) -> int:
        return int(self._s.value("saved_window_x", -1))

    def set_saved_window_x(self, v: int) -> None:
        self._s.setValue("saved_window_x", v)

    def saved_window_y(self) -> int:
        return int(self._s.value("saved_window_y", -1))

    def set_saved_window_y(self, v: int) -> None:
        self._s.setValue("saved_window_y", v)

    def saved_window_width(self) -> int:
        return int(self._s.value("saved_window_width", -1))

    def set_saved_window_width(self, v: int) -> None:
        self._s.setValue("saved_window_width", v)

    def saved_window_height(self) -> int:
        return int(self._s.value("saved_window_height", -1))

    def set_saved_window_height(self, v: int) -> None:
        self._s.setValue("saved_window_height", v)

    def task_panel_visible(self) -> bool:
        return self._s.value("task_panel_visible", False, type=bool)

    def set_task_panel_visible(self, v: bool) -> None:
        self._s.setValue("task_panel_visible", v)

    def sync(self) -> None:
        """Flush pending writes to disk immediately."""
        self._s.sync()

