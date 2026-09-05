"""Audio playback service for countdown and completion sounds."""

from pathlib import Path

from PySide6.QtCore import QObject, QUrl

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
    _MULTIMEDIA_AVAILABLE = True
except ImportError:
    _MULTIMEDIA_AVAILABLE = False

from ..constants import _DING_PATH, _TICKTOCK_PATH
from .sound_files import SoundKind, resolve_sound_path

_TICK_PLAYER_READY = frozenset()
if _MULTIMEDIA_AVAILABLE:
    _TICK_PLAYER_READY = frozenset(
        {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }
    )


class AudioService:
    """Owns sound effect setup and playback for pompom sounds."""

    def __init__(self, parent: QObject | None = None) -> None:
        self._parent = parent
        self._tick_player: QMediaPlayer | None = None
        self._ding_effect: QSoundEffect | None = None
        self._tick_requested = False
        self._ding_pending = False
        self._tick_using_factory_fallback = False
        self._ding_using_factory_fallback = False
        if not _MULTIMEDIA_AVAILABLE:
            return

        self._set_tick_source(resolve_sound_path(SoundKind.TICK))
        self._set_ding_source(resolve_sound_path(SoundKind.BELL))

    def clear_tick_source(self) -> None:
        """Stop ticking and release the current tick media source."""
        self._tick_requested = False
        if self._tick_player is None:
            return
        self._tick_player.stop()
        self._tick_player.setSource(QUrl())

    def clear_ding_source(self) -> None:
        """Stop the bell and release the current ding media source."""
        self._ding_pending = False
        if self._ding_effect is None:
            return
        self._ding_effect.stop()
        self._ding_effect.setSource(QUrl())

    def reload_tick_source(self) -> None:
        """Reload the tick source from the current custom-or-factory path."""
        self._tick_using_factory_fallback = False
        self._set_tick_source(resolve_sound_path(SoundKind.TICK))

    def reload_ding_source(self) -> None:
        """Reload the ding source from the current custom-or-factory path."""
        self._ding_using_factory_fallback = False
        self._set_ding_source(resolve_sound_path(SoundKind.BELL))

    def start_countdown_sound(self, muted: bool = False) -> None:
        """Start the looping ticktock sound if not muted and not already playing."""
        if self._tick_player is None or muted:
            self._tick_requested = False
            return
        self._tick_requested = True
        self._try_start_tick()

    def stop_countdown_sound(self) -> None:
        """Stop the ticktock sound immediately."""
        self._tick_requested = False
        if self._tick_player is None:
            return
        self._tick_player.stop()

    def play_timer_complete_sound(self, muted: bool) -> None:
        """Play the completion bell once (not looped), unless muted."""
        if self._ding_effect is None or muted:
            self._ding_pending = False
            return
        self._ding_pending = True
        self._try_play_ding()

    def _ensure_tick_player(self) -> None:
        if self._tick_player is not None or not _MULTIMEDIA_AVAILABLE:
            return
        try:
            tick_output = QAudioOutput(self._parent)
            self._tick_player = QMediaPlayer(self._parent)
            self._tick_player.setAudioOutput(tick_output)
            self._tick_player.setLoops(QMediaPlayer.Loops.Infinite)
            self._tick_player.mediaStatusChanged.connect(self._on_tick_media_status)
            self._tick_player.mediaStatusChanged.connect(self._try_start_tick)
        except Exception:
            self._tick_player = None

    def _ensure_ding_effect(self) -> None:
        if self._ding_effect is not None or not _MULTIMEDIA_AVAILABLE:
            return
        try:
            self._ding_effect = QSoundEffect(self._parent)
            self._ding_effect.statusChanged.connect(self._on_ding_status)
            self._ding_effect.statusChanged.connect(self._try_play_ding)
        except Exception:
            self._ding_effect = None

    def _set_tick_source(self, path: Path) -> None:
        if not _MULTIMEDIA_AVAILABLE:
            return
        self._ensure_tick_player()
        if self._tick_player is None:
            return
        source = path if path.is_file() else _TICKTOCK_PATH
        try:
            self._tick_player.setSource(QUrl.fromLocalFile(str(source)))
            self._tick_player.setLoops(QMediaPlayer.Loops.Infinite)
        except Exception:
            if source != _TICKTOCK_PATH and _TICKTOCK_PATH.is_file():
                self._tick_using_factory_fallback = True
                self._tick_player.setSource(
                    QUrl.fromLocalFile(str(_TICKTOCK_PATH))
                )
                self._tick_player.setLoops(QMediaPlayer.Loops.Infinite)

    def _set_ding_source(self, path: Path) -> None:
        if not _MULTIMEDIA_AVAILABLE:
            return
        self._ensure_ding_effect()
        if self._ding_effect is None:
            return
        source = path if path.is_file() else _DING_PATH
        try:
            self._ding_effect.setSource(QUrl.fromLocalFile(str(source)))
        except Exception:
            if source != _DING_PATH and _DING_PATH.is_file():
                self._ding_using_factory_fallback = True
                self._ding_effect.setSource(QUrl.fromLocalFile(str(_DING_PATH)))

    def _on_tick_media_status(self, status: object) -> None:
        if (
            not _MULTIMEDIA_AVAILABLE
            or self._tick_player is None
            or self._tick_using_factory_fallback
        ):
            return
        if status != QMediaPlayer.MediaStatus.InvalidMedia:
            return
        if not _TICKTOCK_PATH.is_file():
            return
        self._tick_using_factory_fallback = True
        self._tick_player.setSource(QUrl.fromLocalFile(str(_TICKTOCK_PATH)))
        self._tick_player.setLoops(QMediaPlayer.Loops.Infinite)

    def _on_ding_status(self, status: object) -> None:
        if (
            not _MULTIMEDIA_AVAILABLE
            or self._ding_effect is None
            or self._ding_using_factory_fallback
        ):
            return
        if status != QSoundEffect.Status.Error:
            return
        if not _DING_PATH.is_file():
            return
        self._ding_using_factory_fallback = True
        self._ding_effect.setSource(QUrl.fromLocalFile(str(_DING_PATH)))

    def _try_start_tick(self, *_args: object) -> None:
        if not self._tick_requested or self._tick_player is None:
            return
        if (
            self._tick_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            return
        if self._tick_player.mediaStatus() not in _TICK_PLAYER_READY:
            return
        self._tick_player.play()

    def _try_play_ding(self, *_args: object) -> None:
        if (
            not self._ding_pending
            or self._ding_effect is None
            or self._ding_effect.status() != QSoundEffect.Status.Ready
        ):
            return
        self._ding_pending = False
        self._ding_effect.stop()
        self._ding_effect.play()
