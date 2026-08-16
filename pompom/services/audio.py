"""Audio playback service for countdown and completion sounds."""

from PySide6.QtCore import QObject, QUrl

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
    _MULTIMEDIA_AVAILABLE = True
except ImportError:
    _MULTIMEDIA_AVAILABLE = False

from ..constants import _DING_PATH, _TICKTOCK_PATH

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
        self._tick_player: QMediaPlayer | None = None
        self._ding_effect: QSoundEffect | None = None
        self._tick_requested = False
        self._ding_pending = False
        if not _MULTIMEDIA_AVAILABLE:
            return

        if _TICKTOCK_PATH.exists():
            try:
                tick_output = QAudioOutput(parent)
                self._tick_player = QMediaPlayer(parent)
                self._tick_player.setAudioOutput(tick_output)
                self._tick_player.setSource(QUrl.fromLocalFile(str(_TICKTOCK_PATH)))
                self._tick_player.setLoops(QMediaPlayer.Loops.Infinite)
                self._tick_player.mediaStatusChanged.connect(self._try_start_tick)
            except Exception:
                self._tick_player = None

        if _DING_PATH.exists():
            try:
                self._ding_effect = QSoundEffect(parent)
                self._ding_effect.setSource(QUrl.fromLocalFile(str(_DING_PATH)))
                self._ding_effect.statusChanged.connect(self._try_play_ding)
            except Exception:
                self._ding_effect = None

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
