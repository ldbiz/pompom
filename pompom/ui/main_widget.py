"""Main frameless Pomodoro timer widget."""

import math
import random

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from ..constants import (
    _BODY_MARGIN,
    _BREAK_SUGGESTIONS,
    _CARD_ASSET_PATH,
    _CYCLE_H_FRAC,
    _DEFAULT_H,
    _DEFAULT_W,
    _MAX_H,
    _MAX_W,
    _MOMENTUM_EXTEND_MINS,
    _MOMENTUM_OFFER_SECS,
    _N_GAPS,
    _PLAY_H_FRAC,
    _RESIZE_MARGIN,
    _SHADOW_OFFSET,
    _TIMER_FONT_FAMILY,
    _TIMER_H_FRAC,
    _TITLE_H_FRAC,
)
from ..models.tasks import TaskQueue
from ..platform.win_autostart import set_start_with_windows
from ..services.audio import AudioService
from ..settings import AppSettings
from ..state import UIState
from .options_dialog import OptionsPanel
from .task_panel import TaskPanel
from .window_utils import (
    apply_window_behavior,
    focus_floating_window,
    init_floating_window,
    schedule_desktop_sync,
)


class PompomWidget(QWidget):
    """Frameless, always-on-top Pomodoro timer widget."""

    full_mode_changed = Signal(bool)

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()

        self._settings = settings
        self.state = UIState()
        self._break_suggestion_deck: list[str] = []

        # ── Restore task queue ─────────────────────────────────────────────
        raw = settings.tasks_json()
        self._task_queue: TaskQueue = TaskQueue.from_json(raw) if raw else TaskQueue()

        # Timer always starts fresh: session 1, full pomodoro duration, stopped.
        self.state.remaining_seconds = settings.pomodoro_minutes() * 60

        self.setWindowTitle("pompom")
        self.setMinimumSize(_DEFAULT_W, _DEFAULT_H)
        self.setMaximumSize(_MAX_W, _MAX_H)

        self._card_pixmap = QPixmap(str(_CARD_ASSET_PATH))
        self._has_card_asset = not self._card_pixmap.isNull()
        if self._has_card_asset:
            # Trim outer padding and remask to a clean round-rect so soft AA
            # cannot scale into a translucent frame, while keeping the original
            # corner radius.
            self._card_pixmap, self._card_radius_frac = self._prepare_card_pixmap(
                self._card_pixmap
            )
        else:
            self._card_radius_frac = 0.12

        # Task panel (created lazily when full mode is first enabled).
        # Must exist before init_floating_window: creating the native window
        # fires moveEvent, which reads it.
        self._task_panel: TaskPanel | None = None
        self._task_panel_user_placed = False
        self._options_panel: OptionsPanel | None = None
        self._options_user_placed = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        init_floating_window(self, always_on_top=settings.always_on_top())
        # setWindowFlags recreates the native window and drops geometry, so
        # restore size/position only after the floating-window setup above.
        self._wanted_geometry: QRect | None = None
        self._applying_geometry = False
        self._restore_window_geometry()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._dragging = False
        self._resizing = False
        self._drag_offset = QPoint()
        self._resize_start_global = QPoint()
        self._resize_start_size = self.size()

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(1000)

        # Momentum offer timer (fires every second during the offer window)
        self._momentum_timer = QTimer(self)
        self._momentum_timer.timeout.connect(self._on_momentum_tick)

        self._audio = AudioService(self)

        if settings.task_panel_visible():
            self.set_full_mode(True)

        self.setToolTip(
            "pompom — Space start/pause · M mute · T tasks · right-click for menu"
        )
        self._tray_icon: QSystemTrayIcon | None = None

    @staticmethod
    def _prepare_card_pixmap(pixmap: QPixmap) -> tuple[QPixmap, float]:
        """Trim outer halo and remask to the card's true rounded corners.

        The asset's soft anti-aliased fringe scales into a visible translucent
        frame. Rebuilding the edge as a round-rect at the measured radius keeps
        the original corner shape with only a thin, screen-stable AA rim.
        """
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        width, height = image.width(), image.height()
        if width <= 0 or height <= 0:
            return pixmap, 0.12

        bytes_per_line = image.bytesPerLine()
        pixels = bytes(image.constBits())

        threshold = 180
        left, top, right, bottom = width, height, -1, -1
        for y in range(height):
            row = y * bytes_per_line
            for x in range(width):
                if pixels[row + x * 4 + 3] >= threshold:
                    if x < left:
                        left = x
                    if y < top:
                        top = y
                    if x > right:
                        right = x
                    if y > bottom:
                        bottom = y

        if right < left or bottom < top:
            return pixmap, 0.12

        left = max(0, left - 1)
        top = max(0, top - 1)
        right = min(width - 1, right + 1)
        bottom = min(height - 1, bottom + 1)
        image = image.copy(QRect(left, top, right - left + 1, bottom - top + 1))
        width, height = image.width(), image.height()

        # Corner radius: first row whose left edge is already opaque.
        radius = 0.0
        bytes_per_line = image.bytesPerLine()
        pixels = memoryview(image.bits())
        for y in range(height):
            if pixels[y * bytes_per_line + 3] >= threshold:
                radius = float(y)
                break
        if radius < 1.0:
            radius = min(width, height) * 0.11
        radius_frac = radius / height

        # Flatten soft coverage so only the round-rect mask defines the edge.
        for y in range(height):
            row = y * bytes_per_line
            for x in range(width):
                i = row + x * 4 + 3
                if pixels[i] > 32:
                    pixels[i] = 255

        mask = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        mask.fill(Qt.GlobalColor.transparent)
        mp = QPainter(mask)
        mp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, width, height), radius, radius)
        mp.fillPath(path, QColor(255, 255, 255, 255))
        mp.end()

        p = QPainter(image)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.drawImage(0, 0, mask)
        p.end()

        return QPixmap.fromImage(image), radius_frac

    def _card_aspect_ratio(self) -> float:
        """Width-to-height ratio for the card (from asset or defaults)."""
        if self._has_card_asset and self._card_pixmap.height() > 0:
            return self._card_pixmap.width() / self._card_pixmap.height()
        return _DEFAULT_W / _DEFAULT_H

    def _normalize_size(self, width: int, height: int) -> tuple[int, int]:
        """Fit *width*×*height* within min/max while preserving card aspect ratio."""
        ratio = self._card_aspect_ratio()
        w = max(self.minimumWidth(), min(self.maximumWidth(), width))
        h = max(self.minimumHeight(), min(self.maximumHeight(), height))
        # Prefer width as the driver; adjust height, then clamp again if needed.
        h = round(w / ratio)
        if h < self.minimumHeight():
            h = self.minimumHeight()
            w = round(h * ratio)
        elif h > self.maximumHeight():
            h = self.maximumHeight()
            w = round(h * ratio)
        w = max(self.minimumWidth(), min(self.maximumWidth(), w))
        h = max(self.minimumHeight(), min(self.maximumHeight(), h))
        return w, h

    def _restore_window_geometry(self) -> None:
        """Restore saved size/position, or fall back to defaults.

        Geometry is stashed in ``_wanted_geometry`` and reasserted after show:
        Qt remaps size when the window first lands on a different-DPI screen.
        """
        saved_w = self._settings.saved_window_width()
        saved_h = self._settings.saved_window_height()
        if saved_w > 0 and saved_h > 0:
            w, h = self._normalize_size(saved_w, saved_h)
        else:
            w, h = _DEFAULT_W, _DEFAULT_H

        saved_x = self._settings.saved_window_x()
        saved_y = self._settings.saved_window_y()
        if saved_x >= 0 and saved_y >= 0:
            x, y = saved_x, saved_y
        else:
            x, y = self.x(), self.y()

        self._wanted_geometry = QRect(x, y, w, h)
        self._set_geometry_guarded(self._wanted_geometry)

    def _set_geometry_guarded(self, geo: QRect) -> None:
        """setGeometry without treating the resulting resize as user/DPI noise."""
        self._applying_geometry = True
        self.setGeometry(geo)
        self._applying_geometry = False

    def _apply_wanted_geometry(self) -> None:
        """Reapply stashed geometry and clamp to the screen it actually sits on."""
        geo = self._wanted_geometry
        if geo is None:
            return
        self._set_geometry_guarded(geo)
        self._ensure_on_screen()
        if self._wanted_geometry is not None:
            self._wanted_geometry = QRect(
                self.x(), self.y(), geo.width(), geo.height()
            )

    def _commit_wanted_geometry(self) -> None:
        """Final restore pass after Qt's cross-screen DPI remap, then stop."""
        geo = self._wanted_geometry
        self._wanted_geometry = None
        if geo is None:
            return
        if self.geometry() != geo:
            self._set_geometry_guarded(geo)
            self._ensure_on_screen()

    # ── Settings helpers ──────────────────────────────────────────────────────

    def apply_options(self, new_pom_mins: int, new_brk_mins: int, new_long_brk_mins: int) -> None:
        """Persist new durations from the Options dialog.

        If the timer is stopped *and* remaining_seconds still equals the old
        full duration for the current mode, reset the display to the new value.
        If the timer is running, the change takes effect on the next session reset.
        """
        old_pom_secs      = self._settings.pomodoro_minutes() * 60
        old_brk_secs      = self._settings.break_minutes() * 60
        old_long_brk_secs = self._settings.long_break_minutes() * 60

        self._settings.set_pomodoro_minutes(new_pom_mins)
        self._settings.set_break_minutes(new_brk_mins)
        self._settings.set_long_break_minutes(new_long_brk_mins)

        if not self.state.running:
            mode = self.state.mode
            if mode == "pomodoro" and self.state.remaining_seconds == old_pom_secs:
                self.state.remaining_seconds = new_pom_mins * 60
            elif mode == "short_break" and self.state.remaining_seconds == old_brk_secs:
                self.state.remaining_seconds = new_brk_mins * 60
            elif mode == "long_break" and self.state.remaining_seconds == old_long_brk_secs:
                self.state.remaining_seconds = new_long_brk_mins * 60
        self.update()

    def _toggle_mute(self, muted: bool) -> None:
        """Persist mute state and update audio accordingly."""
        self._settings.set_muted(muted)
        if self._options_panel is not None:
            self._options_panel.set_mute_checked(muted)
        self._update_audio_state()
        self._update_tray_tooltip()
        self.update()

    def apply_window_behavior(self) -> None:
        """Apply always-on-top / virtual-desktop settings to all floating windows."""
        apply_window_behavior(
            self,
            always_on_top=self._settings.always_on_top(),
            show_on_all_desktops=self._settings.show_on_all_desktops(),
        )
        if self._task_panel is not None:
            self._task_panel.apply_window_behavior()
        if self._options_panel is not None:
            self._options_panel.apply_window_behavior()

    def set_tray_icon(self, tray: QSystemTrayIcon) -> None:
        """Register the system tray icon for live status updates."""
        self._tray_icon = tray
        self._update_tray_tooltip()

    def _update_tray_tooltip(self) -> None:
        """Refresh the tray tooltip with current mode and remaining time."""
        if self._tray_icon is None:
            return
        mode_labels = {
            "pomodoro": "Session",
            "short_break": "Short break",
            "long_break": "Long break",
        }
        mode = mode_labels.get(self.state.mode, self.state.mode)
        status = "running" if self.state.running else "paused"
        muted = " · muted" if self._settings.muted() else ""
        self._tray_icon.setToolTip(
            f"pompom — {mode} {self.timer_text()} ({status}){muted}\nRight-click tray or card for menu"
        )

    def _notify_session_end_if_muted(self) -> None:
        """Brief tray balloon when a session ends while muted."""
        if self._tray_icon is None or not self._settings.muted():
            return
        if self.state.mode == "short_break":
            title = "Short break"
        elif self.state.mode == "long_break":
            title = "Long break"
        else:
            title = "Session complete"
        self._tray_icon.showMessage(
            "pompom",
            title,
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def bring_to_front(self) -> None:
        """Show and raise the timer (and visible task panel) above other windows."""
        if self.isMinimized():
            self.showNormal()
        if not self.isVisible():
            self.show()
        focus_floating_window(self)
        if self._task_panel is not None and self._task_panel.isVisible():
            focus_floating_window(self._task_panel)

    # ── Audio helpers ─────────────────────────────────────────────────────────

    def start_countdown_sound(self) -> None:
        """Start the looping ticktock sound if enabled, unmuted, and not already playing."""
        if self._settings.muted() or not self._settings.ticking_enabled():
            return
        self._audio.start_countdown_sound(muted=False)

    def stop_countdown_sound(self) -> None:
        """Stop the ticktock sound immediately."""
        self._audio.stop_countdown_sound()

    def play_timer_complete_sound(self) -> None:
        """Play the completion bell once, unless muted."""
        self._audio.play_timer_complete_sound(self._settings.muted())

    def _update_audio_state(self) -> None:
        """Start or stop ticktock based on running, mute, and ticking preference."""
        if (
            self.state.running
            and not self._settings.muted()
            and self._settings.ticking_enabled()
        ):
            self.start_countdown_sound()
        else:
            self.stop_countdown_sound()

    # ── Cycle helpers ─────────────────────────────────────────────────────────

    def _reset_timer_for_current_mode(self) -> None:
        """Reset remaining_seconds to the full duration of the current mode."""
        if self.state.mode == "pomodoro":
            self.state.remaining_seconds = self._settings.pomodoro_minutes() * 60
        elif self.state.mode == "short_break":
            self.state.remaining_seconds = self._settings.break_minutes() * 60
        else:  # long_break
            self.state.remaining_seconds = self._settings.long_break_minutes() * 60

    def _start_pomodoro_session(self) -> None:
        self.state.mode = "pomodoro"
        self._reset_timer_for_current_mode()
        self.state.running = True
        self.update()

    def _start_short_break(self) -> None:
        self.state.mode = "short_break"
        self._select_break_suggestion()
        self._reset_timer_for_current_mode()
        self.state.running = True
        self.update()

    def _start_long_break(self) -> None:
        self.state.mode = "long_break"
        self._select_break_suggestion()
        self._reset_timer_for_current_mode()
        self.state.running = True
        self.update()

    def restart_all(self) -> None:
        """Reset the full cycle to session 1, pomodoro mode, stopped."""
        self.stop_countdown_sound()
        if self.state.momentum_offer:
            self.state.momentum_offer = False
            self._momentum_timer.stop()
        self.state.cycle_index = 1
        self.state.mode = "pomodoro"
        self._reset_timer_for_current_mode()
        self.state.running = False
        self.update()

    def restart_current(self) -> None:
        """Restart the current session/break from its beginning and start it."""
        self.stop_countdown_sound()
        if self.state.momentum_offer:
            self.state.momentum_offer = False
            self._momentum_timer.stop()
        self._reset_timer_for_current_mode()
        self.state.running = True
        self._update_audio_state()
        self.update()

    def advance_current(self) -> None:
        """Skip to the end of the current session/break, triggering transition."""
        was_pomodoro = self.state.mode == "pomodoro"
        self.stop_countdown_sound()
        self.play_timer_complete_sound()
        if was_pomodoro:
            self._notify_session_end_if_muted()
        # Cancel any pending momentum offer
        if self.state.momentum_offer:
            self.state.momentum_offer = False
            self._momentum_timer.stop()
        self._advance_cycle()
        self._update_audio_state()

    # kept for backwards compatibility (tray used this name previously)
    def restart_cycle(self) -> None:
        self.restart_all()

    # ── Task queue helpers ────────────────────────────────────────────────────

    def _save_state(self) -> None:
        """Persist task queue and window layout to QSettings."""
        self._settings.set_tasks_json(self._task_queue.to_json())
        geo = self.frameGeometry()
        self._settings.set_saved_window_x(geo.x())
        self._settings.set_saved_window_y(geo.y())
        self._settings.set_saved_window_width(self.width())
        self._settings.set_saved_window_height(self.height())
        self._settings.set_task_panel_visible(self.full_mode)
        self._settings.sync()

    def _on_task_changed(self) -> None:
        """Called when the task panel mutates the queue."""
        self._task_queue.sync_current()
        self._save_state()
        self.update()

    def mark_current_task_done(self) -> None:
        """Mark the current task done and advance to the next undone task."""
        cur = self._task_queue.current
        if cur is None:
            return
        cur.done = True
        if not self._task_queue.advance():
            self._task_queue.current_index = -1
        self._save_state()
        if self._task_panel is not None:
            self._task_panel.refresh()
        self.update()

    # ── Full-mode / task panel ────────────────────────────────────────────────

    @property
    def full_mode(self) -> bool:
        return self._task_panel is not None and self._task_panel.isVisible()

    def set_full_mode(self, enabled: bool) -> None:
        """Show or hide the floating task panel."""
        if enabled == self.full_mode:
            return
        if enabled:
            if self._task_panel is None:
                self._task_panel = TaskPanel(self._task_queue, self._settings)
                self._task_panel.task_changed.connect(self._on_task_changed)
                self._task_panel.closed.connect(lambda: self.set_full_mode(False))
                self._task_panel.user_moved.connect(self._on_task_panel_user_moved)
            self._reposition_task_panel()
            self._task_panel.refresh()
            self._task_panel.show()
            self._reposition_options_panel()
        elif self._task_panel is not None:
            self._task_panel.hide()
            self._reposition_options_panel()
        self._task_panel_user_placed = False
        self.full_mode_changed.emit(self.full_mode)

    def _on_task_panel_user_moved(self) -> None:
        """Remember that the user positioned the task panel manually."""
        self._task_panel_user_placed = True

    def _reposition_task_panel(self) -> None:
        if self._task_panel is None:
            return
        gap = 8
        self._task_panel.move(self.x() + self.width() + gap, self.y())

    def _on_options_user_moved(self) -> None:
        """Remember that the user positioned the options panel manually."""
        self._options_user_placed = True

    def _options_anchor(self) -> QWidget:
        """Rightmost pompom window to chain the options panel from."""
        if self._task_panel is not None and self._task_panel.isVisible():
            return self._task_panel
        return self

    def _reposition_options_panel(self) -> None:
        if self._options_panel is None or self._options_user_placed:
            return
        anchor = self._options_anchor()
        gap = 8
        self._options_panel.move(anchor.x() + anchor.width() + gap, anchor.y())

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if (
            self._task_panel is not None
            and self._task_panel.isVisible()
            and not self._task_panel_user_placed
        ):
            self._reposition_task_panel()
        if self._options_panel is not None and self._options_panel.isVisible():
            self._reposition_options_panel()

    # ── Momentum mode ─────────────────────────────────────────────────────────

    def _offer_momentum(self) -> None:
        """Pause after a pomodoro and offer a 5-minute extension."""
        self.state.running = False
        self.state.momentum_offer = True
        self.state.momentum_remaining = _MOMENTUM_OFFER_SECS
        self._momentum_timer.start(1000)
        self.update()

    def _accept_momentum(self) -> None:
        self.state.momentum_offer = False
        self.state.momentum_zone_hover = ""
        self.state.momentum_zone_press = ""
        self._momentum_timer.stop()
        self.state.remaining_seconds = _MOMENTUM_EXTEND_MINS * 60
        self.state.running = True
        self._update_audio_state()
        self.update()

    def _decline_momentum(self) -> None:
        self.state.momentum_offer = False
        self.state.momentum_zone_hover = ""
        self.state.momentum_zone_press = ""
        self._momentum_timer.stop()
        self._advance_cycle()
        self._update_audio_state()

    def _on_momentum_tick(self) -> None:
        self.state.momentum_remaining -= 1
        self.update()
        if self.state.momentum_remaining <= 0:
            self._decline_momentum()

    # ── Break suggestions ─────────────────────────────────────────────────────

    def _select_break_suggestion(self) -> None:
        """Draw one suggestion from a shuffled, non-repeating deck."""
        if not self._break_suggestion_deck:
            self._break_suggestion_deck = list(_BREAK_SUGGESTIONS)
            random.shuffle(self._break_suggestion_deck)

            # Avoid showing the same title across a deck boundary as well.
            if (
                len(self._break_suggestion_deck) > 1
                and self._break_suggestion_deck[-1] == self.state.break_suggestion
            ):
                self._break_suggestion_deck[0], self._break_suggestion_deck[-1] = (
                    self._break_suggestion_deck[-1],
                    self._break_suggestion_deck[0],
                )

        self.state.break_suggestion = self._break_suggestion_deck.pop()

    # ── Options / menu / window recovery ──────────────────────────────────────

    def open_options(self) -> None:
        """Open the floating options panel and apply changes on OK."""
        if self._options_panel is not None and self._options_panel.isVisible():
            focus_floating_window(self._options_panel)
            return
        if self._options_panel is None:
            self._options_panel = OptionsPanel(self._settings)
            self._options_panel.accepted.connect(self._apply_options_panel)
            self._options_panel.ticking_changed.connect(self._on_ticking_changed)
            self._options_panel.mute_changed.connect(self._toggle_mute)
            self._options_panel.user_moved.connect(self._on_options_user_moved)
        self._options_user_placed = False
        self._options_panel.reload_settings()
        self._reposition_options_panel()
        self._options_panel.show()
        focus_floating_window(self._options_panel)

    def _apply_options_panel(self) -> None:
        panel = self._options_panel
        if panel is None:
            return
        self.apply_options(
            panel.pomodoro_minutes, panel.break_minutes, panel.long_break_minutes
        )
        self._settings.set_momentum_enabled(panel.momentum_enabled)
        self._settings.set_always_on_top(panel.always_on_top)
        self._settings.set_show_on_all_desktops(panel.show_on_all_desktops)
        if set_start_with_windows(panel.start_with_windows):
            self._settings.set_start_with_windows(panel.start_with_windows)
            self._settings.sync()
        else:
            QMessageBox.warning(
                self,
                "Start with Windows",
                "pompom could not update your Windows startup setting.",
            )
        self.apply_window_behavior()

    def _on_ticking_changed(self, enabled: bool) -> None:
        """Apply ticking preference immediately while Options is open."""
        self._settings.set_ticking_enabled(enabled)
        self._update_audio_state()

    def _ensure_on_screen(self, min_visible: int = 48) -> None:
        """Guarantee a graspable portion of the widget stays on screen.

        Uses the screen under the window (not primary) so a saved position on a
        secondary monitor is not pulled back onto the main display.
        """
        geo = self.frameGeometry()
        screen = QApplication.screenAt(geo.center())
        if screen is None:
            screen = QApplication.screenAt(geo.topLeft())
        if screen is None:
            screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x, y = geo.x(), geo.y()
        if x > avail.right() - min_visible:
            x = avail.right() - min_visible
        if x + geo.width() < avail.left() + min_visible:
            x = avail.left() + min_visible - geo.width()
        if y < avail.top():
            y = avail.top()
        if y > avail.bottom() - min_visible:
            y = avail.bottom() - min_visible
        if (x, y) != (geo.x(), geo.y()):
            self.move(x, y)

    def populate_action_menu(self, menu: QMenu, *, include_timer_actions: bool = True) -> None:
        """Fill *menu* with the standard pompom actions."""
        if include_timer_actions:
            if self.state.mode == "pomodoro":
                menu.addAction("Skip to Break").triggered.connect(self.advance_current)
                menu.addAction("Restart Session").triggered.connect(self.restart_current)
            else:
                menu.addAction("Skip to Session").triggered.connect(self.advance_current)
                menu.addAction("Restart Break").triggered.connect(self.restart_current)
            menu.addAction("Reset Cycle").triggered.connect(self.restart_all)
            menu.addSeparator()

        self._task_queue.sync_current()
        mark_act = menu.addAction("Mark Task as Done")
        mark_act.triggered.connect(self.mark_current_task_done)
        mark_act.setEnabled(self._task_queue.current is not None)

        menu.addAction(
            "Hide Tasks" if self.full_mode else "Show Tasks",
        ).triggered.connect(lambda: self.set_full_mode(not self.full_mode))

        menu.addSeparator()

        mute_act = menu.addAction("Mute")
        mute_act.setCheckable(True)
        mute_act.setChecked(self._settings.muted())
        mute_act.triggered.connect(lambda checked: self._toggle_mute(checked))

        menu.addAction("Options…").triggered.connect(self.open_options)
        menu.addAction("Quit").triggered.connect(QApplication.quit)

    def _advance_cycle(self) -> None:
        """Move to the next cycle state after the current timer reaches zero."""
        # When a pomodoro ends: if the current task is marked done, advance the queue.
        if self.state.mode == "pomodoro":
            cur = self._task_queue.current
            if cur is not None and cur.done:
                self._task_queue.advance()
                if self._task_panel is not None:
                    self._task_panel.refresh()

        if self.state.mode == "pomodoro":
            if self.state.cycle_index < self.state.cycle_total:
                self._start_short_break()
            else:
                self._start_long_break()
        elif self.state.mode == "short_break":
            self.state.cycle_index += 1
            self._start_pomodoro_session()
        else:  # long_break complete → restart from session 1, stopped
            self.state.cycle_index = 1
            self.state.mode = "pomodoro"
            self._reset_timer_for_current_mode()
            self.state.running = False
            self.update()
        self._save_state()

    # ── Geometry helpers ──────────────────────────────────────────────────────

    def corner_radius(self) -> float:
        """Rounded-corner radius matched to the remasked card asset."""
        return max(8.0, self.height() * self._card_radius_frac)

    def body_rect(self) -> QRectF:
        m = _BODY_MARGIN
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def shadow_rect(self) -> QRectF:
        m = _BODY_MARGIN + 1
        # Height is reduced by _SHADOW_OFFSET so the loop-shifted shadow rows
        # stay within the widget boundary without relying on clipping.
        return QRectF(m, m + _SHADOW_OFFSET,
                      self.width() - 2 * m, self.height() - 2 * m - _SHADOW_OFFSET)

    def resize_zone_rect(self) -> QRect:
        """Bottom-right resize grip, kept on opaque card pixels.

        Fully transparent pixels on a WA_TranslucentBackground window do not
        receive mouse events on Windows. After remasking the card to a round
        rect, the widget's true corner is transparent — so inset the grip by
        a fraction of the corner radius into the opaque card.
        """
        m = _RESIZE_MARGIN
        inset = max(0, int(self.corner_radius() * 0.45))
        return QRect(
            self.width() - m - inset,
            self.height() - m - inset,
            m,
            m,
        )

    def _momentum_zone_rects(self, play: QRectF) -> tuple[QRectF, QRectF]:
        """Split the play-button area into accept (left) and skip (right) zones."""
        gap = play.width() * 0.08
        w = (play.width() - gap) / 2
        accept = QRectF(play.left(), play.top(), w, play.height())
        skip = QRectF(play.right() - w, play.top(), w, play.height())
        return accept, skip

    def compute_layout(self, body: QRectF) -> dict[str, QRectF]:
        """Divide *body* proportionally into four non-overlapping element rects.

        Five equal spacing gaps are distributed: one above title, one between
        each pair of elements, and one below cycle.  Used for both painting
        and mouse hit-testing.

        Returned keys: "title", "timer", "play", "cycle".
        """
        h = body.height()
        w = body.width()

        title_h = h * _TITLE_H_FRAC
        timer_h = h * _TIMER_H_FRAC
        play_h  = h * _PLAY_H_FRAC
        cycle_h = h * _CYCLE_H_FRAC

        content_h = title_h + timer_h + play_h + cycle_h
        gap = max(0.0, (h - content_h) / _N_GAPS)

        y = body.top() + gap
        title_rect = QRectF(body.left(), y, w, title_h)
        y += title_h + gap

        timer_rect = QRectF(body.left() + 12, y, w - 24, timer_h)
        y += timer_h + gap

        play_w = min(w * 0.55, play_h * 2.4)
        play_rect = QRectF(body.center().x() - play_w / 2, y, play_w, play_h)
        y += play_h + gap

        cycle_rect = QRectF(body.left(), y, w, cycle_h)

        return {
            "title": title_rect,
            "timer": timer_rect,
            "play":  play_rect,
            "cycle": cycle_rect,
        }

    def timer_text(self) -> str:
        m = self.state.remaining_seconds // 60
        s = self.state.remaining_seconds % 60
        return f"{m:02d}:{s:02d}"

    # ── Timer tick ────────────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        if not self.state.running:
            return
        if self.state.remaining_seconds > 0:
            self.state.remaining_seconds -= 1
            self.update()
            self._update_tray_tooltip()
            if self.state.remaining_seconds == 0:
                self.stop_countdown_sound()
                self.play_timer_complete_sound()
                if self.state.mode == "pomodoro":
                    self._notify_session_end_if_muted()
                if self.state.mode == "pomodoro" and self._settings.momentum_enabled():
                    # Offer momentum extension before advancing to break
                    self._offer_momentum()
                else:
                    self._advance_cycle()
                    self._update_audio_state()
                self._update_tray_tooltip()

    # ── Mouse interaction ─────────────────────────────────────────────────────

    def _layout_now(self) -> dict[str, QRectF]:
        return self.compute_layout(self.body_rect())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos   = event.position()
        point = pos.toPoint()

        if self.resize_zone_rect().contains(point):
            self._resizing = True
            self._resize_start_global = event.globalPosition().toPoint()
            self._resize_start_size   = self.size()
            event.accept()
            return

        play = self._layout_now()["play"]
        if self.state.momentum_offer:
            accept, skip = self._momentum_zone_rects(play)
            if accept.contains(pos):
                self.state.momentum_zone_press = "accept"
                self.update()
                event.accept()
                return
            if skip.contains(pos):
                self.state.momentum_zone_press = "skip"
                self.update()
                event.accept()
                return
        elif play.contains(pos):
            self.state.pressed_play = True
            self.update()
            event.accept()
            return

        self._dragging    = True
        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos   = event.position()
        point = pos.toPoint()

        play = self._layout_now()["play"]
        if self.state.momentum_offer:
            accept, skip = self._momentum_zone_rects(play)
            if accept.contains(pos):
                self.state.momentum_zone_hover = "accept"
            elif skip.contains(pos):
                self.state.momentum_zone_hover = "skip"
            else:
                self.state.momentum_zone_hover = ""
            self.state.hovered_play = False
        else:
            self.state.hovered_play = play.contains(pos)

        if self._resizing:
            delta = event.globalPosition().toPoint() - self._resize_start_global
            raw_w = self._resize_start_size.width() + delta.x()
            new_w, new_h = self._normalize_size(raw_w, round(raw_w / self._card_aspect_ratio()))
            self.resize(new_w, new_h)
            self.update()
            return

        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            return

        interactive = (
            self.state.hovered_play
            or (self.state.momentum_offer and self.state.momentum_zone_hover)
        )
        if self.resize_zone_rect().contains(point):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif interactive:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        was_pressed = self.state.pressed_play
        self.state.pressed_play = False
        was_dragging = self._dragging

        if self._resizing:
            self._resizing = False
            self._ensure_on_screen()
            self.update()
            return

        play = self._layout_now()["play"]
        pos = event.position()

        if self.state.momentum_offer:
            zone = self.state.momentum_zone_press
            self.state.momentum_zone_press = ""
            if zone:
                accept, skip = self._momentum_zone_rects(play)
                if zone == "accept" and accept.contains(pos):
                    self._accept_momentum()
                elif zone == "skip" and skip.contains(pos):
                    self._decline_momentum()
        elif was_pressed and play.contains(pos):
            self.state.running = not self.state.running
            self._update_audio_state()

        self._dragging = False
        if was_dragging:
            self._ensure_on_screen()
        self.update()

    def _show_action_menu(self, global_pos: QPoint) -> None:
        """Open the card action menu at a screen position."""
        menu = QMenu(self)
        self.populate_action_menu(menu, include_timer_actions=True)
        menu.exec(global_pos)

    def contextMenuEvent(self, event) -> None:
        self._show_action_menu(event.globalPos())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()
        if self.state.momentum_offer:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._accept_momentum()
                return
            if key == Qt.Key.Key_Escape:
                self._decline_momentum()
                return
        elif key == Qt.Key.Key_Space:
            self.state.running = not self.state.running
            self._update_audio_state()
            self._update_tray_tooltip()
            self.update()
            return
        if key == Qt.Key.Key_Menu or (
            key == Qt.Key.Key_F10
            and modifiers & Qt.KeyboardModifier.ShiftModifier
        ):
            self._show_action_menu(self.mapToGlobal(self.rect().center()))
            return
        if key == Qt.Key.Key_M and not modifiers:
            self._toggle_mute(not self._settings.muted())
            return
        if key == Qt.Key.Key_T and not modifiers:
            self.set_full_mode(not self.full_mode)
            return
        super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_wanted_geometry()
        # Qt remaps size after the window associates with a high-DPI screen.
        # Two event-loop turns is enough for that remap to finish; then commit.
        if self._wanted_geometry is not None:
            QTimer.singleShot(0, self._finish_geometry_restore)
        self._update_tray_tooltip()
        schedule_desktop_sync(
            self, show_on_all_desktops=self._settings.show_on_all_desktops()
        )

    def _finish_geometry_restore(self) -> None:
        """Reassert saved geometry after DPI remap, then clear the stash."""
        if self._wanted_geometry is None:
            return
        self._apply_wanted_geometry()
        # One more turn: the DPI size remap often lands on this tick.
        QTimer.singleShot(0, self._commit_wanted_geometry)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        wanted = self._wanted_geometry
        if wanted is None or self._applying_geometry:
            return
        # Cross-screen DPI remap changes size while restore is still pending.
        if self.size() != wanted.size() or self.pos() != wanted.topLeft():
            self._set_geometry_guarded(wanted)

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing,     True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        body   = self.body_rect()
        shadow = self.shadow_rect()
        radius = self.corner_radius()
        layout = self.compute_layout(body)

        if self._has_card_asset:
            self._draw_card_background(p, body)
        else:
            # Development fallback: keep the old procedural card if the asset is
            # missing, so the app remains runnable from a bare source checkout.
            self._draw_shadow(p, shadow, radius)
            self._draw_shell(p, body, radius)
            self._draw_brushed_effect(p, body, radius)
            self._draw_sheen(p, body, radius)
            self._draw_highlight(p, body, radius)
            self._draw_edge(p, body, radius)

        self._draw_break_overlay(p, body, radius)
        self._draw_title(p, layout["title"], body)
        self._draw_timer(p, layout["timer"])
        if self.state.momentum_offer:
            self._draw_momentum_offer(p, layout["play"])
        else:
            self._draw_play_button(p, layout["play"])
        self._draw_cycle(p, layout["cycle"], body)
        if self._settings.muted():
            self._draw_muted_indicator(p)
        self._draw_resize_hint(p)


    def _draw_card_background(self, p: QPainter, rect: QRectF) -> None:
        """Draw the image-backed red card skin behind the timer overlay.

        The prepared pixmap is already masked to the card's rounded rect, so it
        draws edge-to-edge without a soft translucent frame.
        """
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        source = QRectF(self._card_pixmap.rect())
        p.drawPixmap(rect, self._card_pixmap, source)
        p.restore()

    def _draw_break_overlay(self, p: QPainter, body: QRectF, radius: float) -> None:
        """Draw a subtle cool tint over the card during break modes.

        Short breaks get a soft teal wash; long breaks a slightly deeper blue.
        Both are restrained enough to preserve the red-card identity while
        making the mode change immediately obvious at a glance.
        """
        if self.state.mode == "pomodoro":
            return
        if self.state.mode == "short_break":
            color = QColor(100, 185, 210, 32)
        else:  # long_break
            color = QColor(70, 130, 215, 50)
        p.save()
        p.setClipPath(self._rounded_path(body, radius))
        p.fillRect(body, color)
        p.restore()

    def _rounded_path(self, rect: QRectF, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path

    def _draw_shadow(self, p: QPainter, rect: QRectF, radius: float) -> None:
        for i, alpha in enumerate([30, 18, 10, 5]):
            r = QRectF(rect.left(), rect.top() + i, rect.width(), rect.height())
            p.fillPath(self._rounded_path(r, radius + i * 0.5), QColor(0, 0, 0, alpha))

    def _draw_shell(self, p: QPainter, rect: QRectF, radius: float) -> None:
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.00, QColor("#A04343"))
        grad.setColorAt(0.28, QColor("#8F3030"))
        grad.setColorAt(0.68, QColor("#7A2727"))
        grad.setColorAt(1.00, QColor("#5E1F1F"))
        p.fillPath(self._rounded_path(rect, radius), grad)

        # Bottom weight / depth
        dark = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        dark.setColorAt(0.0,  QColor(0, 0, 0,  0))
        dark.setColorAt(0.72, QColor(0, 0, 0,  0))
        dark.setColorAt(1.0,  QColor(0, 0, 0, 38))
        p.fillPath(self._rounded_path(rect, radius), dark)

    def _draw_brushed_effect(self, p: QPainter, rect: QRectF, radius: float) -> None:
        path = self._rounded_path(rect, radius)
        p.save()
        p.setClipPath(path)

        # Fine horizontal brushed texture.
        for y in range(int(rect.top()) + 2, int(rect.bottom()) - 2):
            t     = (y - rect.top()) / max(1.0, rect.height())
            wave1 = math.sin(t * math.pi * 10.0)
            wave2 = math.sin(t * math.pi * 27.0 + 0.8)
            alpha = 7 + int((wave1 + 1.0) * 1.8 + (wave2 + 1.0) * 1.3)
            p.setPen(QPen(QColor(255, 245, 245, alpha), 1))
            p.drawLine(int(rect.left()) + 4, y, int(rect.right()) - 4, y)

        # Very faint darker striations for a metallic feel.
        for y in range(int(rect.top()) + 3, int(rect.bottom()) - 3, 3):
            t     = (y - rect.top()) / max(1.0, rect.height())
            wave  = math.sin(t * math.pi * 16.0 + 0.5)
            alpha = 3 + int((wave + 1.0) * 1.8)
            p.setPen(QPen(QColor(40, 10, 10, alpha), 1))
            p.drawLine(int(rect.left()) + 5, y, int(rect.right()) - 5, y)

        p.restore()

    def _draw_sheen(self, p: QPainter, rect: QRectF, radius: float) -> None:
        sheen = QRectF(
            rect.left()   + rect.width()  * 0.05,
            rect.top()    + rect.height() * 0.08,
            rect.width()  * 0.75,
            rect.height() * 0.55,
        )
        grad = QLinearGradient(sheen.topLeft(), sheen.bottomRight())
        grad.setColorAt(0.0,  QColor(255, 255, 255, 24))
        grad.setColorAt(0.35, QColor(255, 255, 255, 10))
        grad.setColorAt(1.0,  QColor(255, 255, 255,  0))
        p.save()
        p.setClipPath(self._rounded_path(rect, radius))
        p.fillRect(sheen, grad)
        p.restore()

    def _draw_highlight(self, p: QPainter, rect: QRectF, radius: float) -> None:
        hl = QRectF(
            rect.left()   + rect.width()  * 0.02,
            rect.top()    + rect.height() * 0.02,
            rect.width()  * 0.62,
            rect.height() * 0.34,
        )
        grad = QLinearGradient(hl.topLeft(), hl.bottomRight())
        grad.setColorAt(0.0,  QColor(255, 255, 255, 56))
        grad.setColorAt(0.42, QColor(255, 255, 255, 16))
        grad.setColorAt(1.0,  QColor(255, 255, 255,  0))
        p.save()
        p.setClipPath(self._rounded_path(rect, radius))
        p.fillRect(hl, grad)
        p.restore()

    def _draw_edge(self, p: QPainter, rect: QRectF, radius: float) -> None:
        p.setPen(QPen(QColor(255, 210, 210, 52), 1.2))
        p.drawRoundedRect(rect, radius, radius)

        inset = rect.adjusted(1.5, 1.5, -1.5, -1.5)
        p.setPen(QPen(QColor(55, 12, 12, 78), 1.0))
        p.drawRoundedRect(inset, radius - 1.5, radius - 1.5)

    def _draw_title(self, p: QPainter, rect: QRectF, body: QRectF) -> None:
        size = max(9, int(body.height() * 0.09))
        font = QFont("Inter", size)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)

        if self.state.momentum_offer:
            text  = f"Keep going?  {self.state.momentum_remaining}s"
            color = QColor("#EED5A0")
        elif self.state.mode != "pomodoro":
            text  = self.state.break_suggestion
            color = QColor("#d87175")
        elif self._task_queue.current is not None:
            # Current task title (elided to fit)
            text  = self._task_queue.current.title
            color = QColor("#C89595")
        else:
            text  = "pompom"
            color = QColor("#C89595")

        fm     = QFontMetrics(font)
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()) - 4)
        p.setPen(color)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided)

    def _draw_timer(self, p: QPainter, rect: QRectF) -> None:
        # Sized to ~72 % of the timer rect height for elegance.
        size = max(14, int(rect.height() * 0.72))
        font = QFont(_TIMER_FONT_FAMILY, size)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(QColor("#E6D5D2"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.timer_text())

    def _draw_play_button(self, p: QPainter, rect: QRectF) -> None:
        if self.state.pressed_play:
            bg = QColor(185, 120, 120, 62)
        elif self.state.hovered_play:
            bg = QColor(195, 132, 132, 54)
        else:
            bg = QColor(188, 128, 128, 40)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 9, 9)

        p.setBrush(QColor("#EAD9D6"))
        cx, cy = rect.center().x(), rect.center().y()

        if self.state.running:
            bar_w = rect.width()  * 0.10
            bar_h = rect.height() * 0.44
            gap   = rect.width()  * 0.07
            y0    = cy - bar_h / 2
            p.drawRoundedRect(QRectF(cx - gap / 2 - bar_w, y0, bar_w, bar_h), 2, 2)
            p.drawRoundedRect(QRectF(cx + gap / 2,          y0, bar_w, bar_h), 2, 2)
        else:
            tri_w = rect.width()  * 0.24
            tri_h = rect.height() * 0.42
            path  = QPainterPath()
            path.moveTo(cx - tri_w * 0.38, cy - tri_h / 2)
            path.lineTo(cx - tri_w * 0.38, cy + tri_h / 2)
            path.lineTo(cx + tri_w * 0.52, cy)
            path.closeSubpath()
            p.drawPath(path)

    def _draw_cycle(self, p: QPainter, rect: QRectF, body: QRectF) -> None:
        body_h     = body.height()
        label_size = max(8, int(body_h * 0.08))
        count_size = max(9, int(body_h * 0.09))

        label_font = QFont("Inter", label_size)
        label_font.setWeight(QFont.Weight.Medium)

        # Current session/break number drawn bold; separator + total at normal weight.
        current_font = QFont("Inter", count_size)
        current_font.setWeight(QFont.Weight.Bold)

        total_font = QFont("Inter", count_size)
        total_font.setWeight(QFont.Weight.Normal)

        if self.state.mode == "pomodoro":
            label_text = "Session"
            label_color   = QColor("#8D3F3F")
            current_color = QColor("#A85F5F")
        else:
            label_text = "Break"
            label_color   = QColor("#d87175")
            current_color = QColor("#d87175")

        current_text = str(self.state.cycle_index)
        sep_text     = " / "
        total_text   = str(self.state.cycle_total)

        fm_label   = QFontMetrics(label_font)
        fm_current = QFontMetrics(current_font)
        fm_total   = QFontMetrics(total_font)

        lw   = fm_label.horizontalAdvance(label_text)
        curw = fm_current.horizontalAdvance(current_text)
        sepw = fm_total.horizontalAdvance(sep_text)
        totw = fm_total.horizontalAdvance(total_text)

        gap_px  = max(6, int(body_h * 0.05))
        total_w = lw + gap_px + curw + sepw + totw
        start_x = rect.center().x() - total_w / 2

        # Compute baseline for vertical centering within rect.
        ascent  = max(fm_label.ascent(),  fm_current.ascent(),  fm_total.ascent())
        descent = max(fm_label.descent(), fm_current.descent(), fm_total.descent())
        baseline = int(rect.top() + (rect.height() - ascent - descent) / 2 + ascent)

        x = int(start_x)

        p.setFont(label_font)
        p.setPen(label_color)
        p.drawText(QPoint(x, baseline), label_text)
        x += lw + gap_px

        p.setFont(current_font)
        p.setPen(current_color)
        p.drawText(QPoint(x, baseline), current_text)
        x += curw

        p.setFont(total_font)
        p.drawText(QPoint(x, baseline), sep_text)
        x += sepw

        p.drawText(QPoint(x, baseline), total_text)

    def _draw_momentum_offer(self, p: QPainter, rect: QRectF) -> None:
        """Draw explicit accept (+5m) and skip buttons in the play-button area."""
        accept, skip = self._momentum_zone_rects(rect)

        body_h = self.body_rect().height()
        size   = max(7, int(body_h * 0.08))
        font   = QFont("Inter", size)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)
        p.setPen(Qt.PenStyle.NoPen)

        def _zone_bg(zone: str, base: QColor, hover: QColor, press: QColor) -> QColor:
            if self.state.momentum_zone_press == zone:
                return press
            if self.state.momentum_zone_hover == zone:
                return hover
            return base

        # Accept (amber) — extend the session.
        p.setBrush(_zone_bg(
            "accept",
            QColor(185, 145, 75, 60),
            QColor(195, 160, 90, 78),
            QColor(185, 150, 80, 96),
        ))
        p.drawRoundedRect(accept, 9, 9)
        p.setPen(QColor("#EED5A0"))
        p.drawText(accept, Qt.AlignmentFlag.AlignCenter, f"+{_MOMENTUM_EXTEND_MINS}m")

        # Skip (neutral) — go to the break now.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_zone_bg(
            "skip",
            QColor(150, 120, 120, 46),
            QColor(165, 132, 132, 62),
            QColor(140, 108, 108, 80),
        ))
        p.drawRoundedRect(skip, 9, 9)
        p.setPen(QColor("#D8C4C1"))
        p.drawText(skip, Qt.AlignmentFlag.AlignCenter, "Skip")

    def _draw_muted_indicator(self, p: QPainter) -> None:
        """Draw a subtle speaker-off glyph in the top-left when muted."""
        body = self.body_rect()
        size = max(12.0, min(18.0, body.height() * 0.12))
        margin = max(6.0, body.height() * 0.05)
        rect = QRectF(body.left() + margin, body.top() + margin, size, size)
        p.save()
        col = QColor(230, 205, 205, 120)
        p.setPen(QPen(col, 1.3))
        p.setBrush(col)
        # Speaker cone
        cx, cy = rect.center().x(), rect.center().y()
        h = rect.height() * 0.5
        box = QRectF(rect.left(), cy - h * 0.28, rect.width() * 0.28, h * 0.56)
        p.drawRect(box)
        cone = QPainterPath()
        cone.moveTo(box.right(), cy - h * 0.28)
        cone.lineTo(box.right() + rect.width() * 0.26, cy - h * 0.5)
        cone.lineTo(box.right() + rect.width() * 0.26, cy + h * 0.5)
        cone.lineTo(box.right(), cy + h * 0.28)
        cone.closeSubpath()
        p.fillPath(cone, col)
        # Slash
        p.setPen(QPen(QColor(235, 150, 150, 200), 1.4))
        p.drawLine(rect.topRight().toPoint(), rect.bottomLeft().toPoint())
        p.restore()

    def _draw_resize_hint(self, p: QPainter) -> None:
        """Faint corner grip lines — visible on the red card, not loud."""
        z = self.resize_zone_rect()
        # Soft dark under-stroke so the marks read on both light sheen and red.
        p.setPen(QPen(QColor(40, 10, 10, 40), 1.6))
        for offset in (4, 8, 12):
            p.drawLine(
                z.right() - offset, z.bottom() - 2,
                z.right() - 2, z.bottom() - offset,
            )
        p.setPen(QPen(QColor(255, 230, 230, 70), 1.1))
        for offset in (4, 8, 12):
            p.drawLine(
                z.right() - offset, z.bottom() - 2,
                z.right() - 2, z.bottom() - offset,
            )


