"""Options panel for Pomodoro durations."""

import sys

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..constants import _APP_VERSION
from ..services.sound_files import SoundKind, has_custom
from ..settings import AppSettings
from .theme import PANEL_STYLE, paint_floating_panel
from .window_utils import (
    apply_window_behavior,
    clamp_to_screen,
    focus_floating_window,
    init_floating_window,
    schedule_desktop_sync,
)


class _DragHeader(QWidget):
    """Title bar that drags the parent top-level window."""

    user_moved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dragging = False
        self._drag_offset = QPoint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            self._dragging = True
            self._drag_offset = (
                event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            )
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self.window().move(
                event.globalPosition().toPoint() - self._drag_offset
            )
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_dragging = self._dragging
        self._dragging = False
        if was_dragging:
            self.user_moved.emit()
        event.accept()


class AboutPanel(QWidget):
    """Frameless About panel matching pompom's other floating panels."""

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings = settings
        self.setObjectName("AboutPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        init_floating_window(self, always_on_top=settings.always_on_top())
        self.setFixedWidth(300)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        inner = QWidget(self)
        inner.setObjectName("AboutPanel")
        inner.setStyleSheet(
            "QWidget#AboutPanel { background: #1E1010; border-radius: 10px; }"
        )
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        outer.addWidget(inner)

        header = _DragHeader()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("About pompom")
        title.setObjectName("header")
        title.setStyleSheet(
            "QLabel { color: #9A7070; font-size: 12px; font-weight: 500; background: transparent; }"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { padding: 0; }")
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)
        layout.addWidget(header)

        body = QLabel(
            f"Version {_APP_VERSION}\n\n"
            "A small always-on-top Pomodoro timer.\n\n"
            "Space starts/pauses · M mutes · T toggles tasks.\n"
            "Menu or Shift+F10 opens the card menu.\n"
            "Enter/Esc accepts/skips a momentum offer.\n\n"
            "Built with Python and PySide6.\n"
            "MIT licensed."
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.adjustSize()

    def apply_window_behavior(self) -> None:
        apply_window_behavior(
            self,
            always_on_top=self._settings.always_on_top(),
            show_on_all_desktops=self._settings.show_on_all_desktops(),
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        schedule_desktop_sync(
            self, show_on_all_desktops=self._settings.show_on_all_desktops()
        )
        clamp_to_screen(self)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class SoundsPanel(QWidget):
    """Floating panel for choosing and resetting custom sounds."""

    install_requested = Signal(SoundKind, str)
    reset_requested = Signal(SoundKind)
    reset_all_requested = Signal()

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings = settings
        self.setObjectName("SoundsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        init_floating_window(self, always_on_top=settings.always_on_top())
        self.setFixedWidth(320)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        inner = QWidget(self)
        inner.setObjectName("SoundsPanel")
        inner.setStyleSheet(
            "QWidget#SoundsPanel { background: #1E1010; border-radius: 10px; }"
        )
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        outer.addWidget(inner)

        header = _DragHeader()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Sounds")
        title.setObjectName("header")
        title.setStyleSheet(
            "QLabel { color: #9A7070; font-size: 12px; font-weight: 500; background: transparent; }"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { padding: 0; }")
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)
        layout.addWidget(header)

        self._tick_state, self._tick_reset = self._add_sound_row(
            layout, "Ticking", SoundKind.TICK
        )
        self._bell_state, self._bell_reset = self._add_sound_row(
            layout, "Bell", SoundKind.BELL
        )

        reset_all_btn = QPushButton("Reset all to defaults")
        reset_all_btn.clicked.connect(self.reset_all_requested.emit)
        layout.addWidget(reset_all_btn)

        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh_state()
        self.adjustSize()

    def _add_sound_row(
        self,
        layout: QVBoxLayout,
        label: str,
        kind: SoundKind,
    ) -> tuple[QLabel, QPushButton]:
        row = QHBoxLayout()
        row.setSpacing(6)
        name = QLabel(label)
        name.setFixedWidth(52)
        row.addWidget(name)
        state = QLabel("Default")
        state.setFixedWidth(52)
        row.addWidget(state)
        choose_btn = QPushButton("Choose…")
        choose_btn.clicked.connect(lambda: self._choose_sound(kind))
        row.addWidget(choose_btn)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(
            lambda: self.reset_requested.emit(kind)
        )
        row.addWidget(reset_btn)
        layout.addLayout(row)
        return state, reset_btn

    def _choose_sound(self, kind: SoundKind) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Choose a WAV file",
            "",
            "WAV files (*.wav)",
        )
        if path:
            self.install_requested.emit(kind, path)

    def refresh_state(self) -> None:
        """Update Default/Custom labels and Reset enabled state."""
        self._set_row_state(self._tick_state, self._tick_reset, SoundKind.TICK)
        self._set_row_state(self._bell_state, self._bell_reset, SoundKind.BELL)

    def _set_row_state(
        self,
        state_label: QLabel,
        reset_btn: QPushButton,
        kind: SoundKind,
    ) -> None:
        custom = has_custom(kind)
        state_label.setText("Custom" if custom else "Default")
        reset_btn.setEnabled(custom)

    def apply_window_behavior(self) -> None:
        apply_window_behavior(
            self,
            always_on_top=self._settings.always_on_top(),
            show_on_all_desktops=self._settings.show_on_all_desktops(),
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        schedule_desktop_sync(
            self, show_on_all_desktops=self._settings.show_on_all_desktops()
        )
        clamp_to_screen(self)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class OptionsPanel(QWidget):
    """Floating options panel; chains alongside the timer and task panel."""

    accepted = Signal()
    rejected = Signal()
    user_moved = Signal()
    ticking_changed = Signal(bool)
    bell_changed = Signal(bool)
    mute_changed = Signal(bool)
    sound_install_requested = Signal(SoundKind, str)
    sound_reset_requested = Signal(SoundKind)
    sound_reset_all_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._about_panel: AboutPanel | None = None
        self._sounds_panel: SoundsPanel | None = None
        self.setObjectName("OptionsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        init_floating_window(self, always_on_top=settings.always_on_top())
        self.setFixedWidth(300)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        inner = QWidget(self)
        inner.setObjectName("OptionsPanel")
        inner.setStyleSheet(
            "QWidget#OptionsPanel { background: #1E1010; border-radius: 10px; }"
        )
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        outer.addWidget(inner)

        header = _DragHeader()
        header.user_moved.connect(self.user_moved.emit)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Options")
        title.setObjectName("header")
        title.setStyleSheet(
            "QLabel { color: #9A7070; font-size: 12px; font-weight: 500; background: transparent; }"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { padding: 0; }")
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        layout.addWidget(header)

        self._pom_spin = QSpinBox()
        self._pom_spin.setRange(1, 120)
        self._pom_spin.setSuffix(" min")
        layout.addLayout(self._duration_row("Pomodoro", self._pom_spin))

        self._brk_spin = QSpinBox()
        self._brk_spin.setRange(1, 60)
        self._brk_spin.setSuffix(" min")
        layout.addLayout(self._duration_row("Break", self._brk_spin))

        self._long_brk_spin = QSpinBox()
        self._long_brk_spin.setRange(1, 120)
        self._long_brk_spin.setSuffix(" min")
        layout.addLayout(self._duration_row("Long break", self._long_brk_spin))

        layout.addSpacing(2)

        self._momentum_chk = QCheckBox("Offer to extend a session when it ends")
        layout.addWidget(self._momentum_chk)

        self._ticking_chk = QCheckBox("Play ticking while the timer runs")
        self._ticking_chk.toggled.connect(self.ticking_changed.emit)
        layout.addWidget(self._ticking_chk)

        self._bell_chk = QCheckBox("Play bell when the timer ends")
        self._bell_chk.toggled.connect(self.bell_changed.emit)
        layout.addWidget(self._bell_chk)

        self._mute_chk = QCheckBox("Mute all sounds")
        self._mute_chk.toggled.connect(self._on_mute_toggled)
        layout.addWidget(self._mute_chk)

        self._on_top_chk = QCheckBox("Keep pompom above other windows")
        layout.addWidget(self._on_top_chk)

        self._all_desktops_chk = QCheckBox("Show on all virtual desktops")
        layout.addWidget(self._all_desktops_chk)

        self._autostart_chk = QCheckBox("Start pompom when Windows starts")
        self._autostart_chk.setVisible(sys.platform == "win32")
        layout.addWidget(self._autostart_chk)

        hint = QLabel(
            "Duration changes apply when the current session or break ends "
            "if the timer is running."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7A5A5A; font-size: 10px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        sounds_btn = QPushButton("Sounds…")
        sounds_btn.clicked.connect(self._show_sounds)
        btn_row.addWidget(sounds_btn)
        about_btn = QPushButton("About…")
        about_btn.clicked.connect(self._show_about)
        btn_row.addWidget(about_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self.reload_settings()
        self.adjustSize()

    def reload_settings(self) -> None:
        """Refresh controls from persisted settings."""
        settings = self._settings
        self._pom_spin.setValue(settings.pomodoro_minutes())
        self._brk_spin.setValue(settings.break_minutes())
        self._long_brk_spin.setValue(settings.long_break_minutes())
        self._momentum_chk.setChecked(settings.momentum_enabled())
        self._ticking_chk.blockSignals(True)
        self._ticking_chk.setChecked(settings.ticking_enabled())
        self._ticking_chk.blockSignals(False)
        self._bell_chk.blockSignals(True)
        self._bell_chk.setChecked(settings.bell_enabled())
        self._bell_chk.blockSignals(False)
        self._mute_chk.blockSignals(True)
        self._mute_chk.setChecked(settings.muted())
        self._mute_chk.blockSignals(False)
        self._sync_sound_checkboxes()
        self._on_top_chk.setChecked(settings.always_on_top())
        self._all_desktops_chk.setChecked(settings.show_on_all_desktops())
        self._autostart_chk.setChecked(settings.start_with_windows())

    def apply_window_behavior(self) -> None:
        """Apply always-on-top / virtual-desktop settings."""
        apply_window_behavior(
            self,
            always_on_top=self._settings.always_on_top(),
            show_on_all_desktops=self._settings.show_on_all_desktops(),
        )
        if self._about_panel is not None:
            self._about_panel.apply_window_behavior()
        if self._sounds_panel is not None:
            self._sounds_panel.apply_window_behavior()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        schedule_desktop_sync(
            self, show_on_all_desktops=self._settings.show_on_all_desktops()
        )
        clamp_to_screen(self)

    def accept(self) -> None:
        if self._about_panel is not None:
            self._about_panel.hide()
        if self._sounds_panel is not None:
            self._sounds_panel.hide()
        self.hide()
        self.accepted.emit()

    def reject(self) -> None:
        if self._about_panel is not None:
            self._about_panel.hide()
        if self._sounds_panel is not None:
            self._sounds_panel.hide()
        self.hide()
        self.rejected.emit()

    def _on_mute_toggled(self, muted: bool) -> None:
        self._sync_sound_checkboxes()
        self.mute_changed.emit(muted)

    def _sync_sound_checkboxes(self) -> None:
        """Mute greys out individual sound controls without clearing their selection."""
        enabled = not self._mute_chk.isChecked()
        self._ticking_chk.setEnabled(enabled)
        self._bell_chk.setEnabled(enabled)

    def set_mute_checked(self, muted: bool) -> None:
        """Update mute from outside (e.g. tray) without clearing ticking selection."""
        self._mute_chk.blockSignals(True)
        self._mute_chk.setChecked(muted)
        self._mute_chk.blockSignals(False)
        self._sync_sound_checkboxes()

    def sounds_panel_widget(self) -> SoundsPanel | None:
        """Return the Sounds panel if it has been opened."""
        return self._sounds_panel

    def _duration_row(self, label: str, spin: QSpinBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(72)
        row.addWidget(lbl)
        row.addWidget(spin, 1)
        return row

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        paint_floating_panel(painter, QRectF(self.rect()))

    def _show_about(self) -> None:
        if self._about_panel is None:
            self._about_panel = AboutPanel(self._settings)
        self._about_panel.move(self.x() + self.width() + 8, self.y())
        self._about_panel.show()
        focus_floating_window(self._about_panel)

    def _ensure_sounds_panel(self) -> SoundsPanel:
        if self._sounds_panel is None:
            self._sounds_panel = SoundsPanel(self._settings)
            self._sounds_panel.install_requested.connect(
                self.sound_install_requested.emit
            )
            self._sounds_panel.reset_requested.connect(
                self.sound_reset_requested.emit
            )
            self._sounds_panel.reset_all_requested.connect(
                self.sound_reset_all_requested.emit
            )
        return self._sounds_panel

    def _show_sounds(self) -> None:
        panel = self._ensure_sounds_panel()
        panel.refresh_state()
        panel.move(self.x() + self.width() + 8, self.y())
        panel.show()
        focus_floating_window(panel)

    @property
    def pomodoro_minutes(self) -> int:
        return self._pom_spin.value()

    @property
    def break_minutes(self) -> int:
        return self._brk_spin.value()

    @property
    def long_break_minutes(self) -> int:
        return self._long_brk_spin.value()

    @property
    def momentum_enabled(self) -> bool:
        return self._momentum_chk.isChecked()

    @property
    def ticking_enabled(self) -> bool:
        return self._ticking_chk.isChecked()

    @property
    def bell_enabled(self) -> bool:
        return self._bell_chk.isChecked()

    @property
    def muted(self) -> bool:
        return self._mute_chk.isChecked()

    @property
    def always_on_top(self) -> bool:
        return self._on_top_chk.isChecked()

    @property
    def show_on_all_desktops(self) -> bool:
        return self._all_desktops_chk.isChecked()

    @property
    def start_with_windows(self) -> bool:
        return self._autostart_chk.isChecked()
