"""
Audio player engine.

Wraps QMediaPlayer and QAudioOutput behind a clean, signal-based API so the
UI layer never touches Qt multimedia classes directly.  All state changes are
broadcast as signals, which lets multiple widgets (controls bar, playlist,
info panel) stay in sync without knowing about each other.
"""

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from models.track import Track


class AudioPlayer(QObject):
    """
    Playlist-aware audio player.

    Maintains an ordered list of Track objects as the current queue.
    Advancing past the last track wraps around (unless repeat is on).
    """

    # ── Outgoing signals ────────────────────────────────────────────────────
    # These let UI widgets react to state changes without polling.

    track_changed = pyqtSignal(object)           # emits Track
    playback_state_changed = pyqtSignal(object)  # emits QMediaPlayer.PlaybackState
    position_changed = pyqtSignal(int)           # milliseconds
    duration_changed = pyqtSignal(int)           # milliseconds
    volume_changed = pyqtSignal(float)           # 0.0 – 1.0
    error_occurred = pyqtSignal(str)             # human-readable message

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

        # Qt multimedia objects
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)

        # Internal playlist state
        self._playlist: list[Track] = []
        self._current_index: int = -1
        self._shuffle: bool = False
        self._repeat: bool = False

        # Volume memory for the mute/unmute toggle (owned here, used by UI)
        self.last_volume: float = 0.7

        self._audio_output.setVolume(self.last_volume)
        self._wire_qt_signals()

    # ── Playback controls ──────────────────────────────────────────────────

    def play(self) -> None:
        self._media_player.play()

    def pause(self) -> None:
        self._media_player.pause()

    def stop(self) -> None:
        self._media_player.stop()

    def toggle_play_pause(self) -> None:
        """Toggle between playing and paused."""
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
        else:
            self._media_player.play()

    def seek(self, position_ms: int) -> None:
        """Seek to an absolute position in milliseconds."""
        self._media_player.setPosition(position_ms)

    def set_volume(self, volume: float) -> None:
        """Set playback volume; *volume* must be in [0.0, 1.0]."""
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    def get_volume(self) -> float:
        return self._audio_output.volume()

    def get_position(self) -> int:
        """Current playback position in milliseconds."""
        return self._media_player.position()

    def get_duration(self) -> int:
        """Duration of the current media in milliseconds (0 if unknown)."""
        return self._media_player.duration()

    def get_state(self) -> QMediaPlayer.PlaybackState:
        return self._media_player.playbackState()

    # ── Playlist management ────────────────────────────────────────────────

    def set_playlist(self, tracks: list[Track], start_index: int = 0) -> None:
        """
        Replace the current queue with *tracks* and load *start_index*.

        Does not auto-play — the caller (or user) must call play().
        """
        self._playlist = list(tracks)
        if self._playlist:
            self._load_index(start_index)

    def play_track(self, index: int) -> None:
        """Immediately load and play the track at *index* in the queue."""
        if 0 <= index < len(self._playlist):
            self._load_index(index)
            self._media_player.play()

    def next_track(self) -> None:
        """Advance to the next track; wraps around at end of queue."""
        if not self._playlist:
            return
        next_index = (self._current_index + 1) % len(self._playlist)
        self._load_index(next_index)
        self._media_player.play()

    def previous_track(self) -> None:
        """
        Go to previous track.

        If more than 3 seconds have elapsed, restart the current track
        instead (standard behaviour in most players).
        """
        if not self._playlist:
            return
        if self._media_player.position() > 3000:
            self._media_player.setPosition(0)
            return
        prev_index = (self._current_index - 1) % len(self._playlist)
        self._load_index(prev_index)
        self._media_player.play()

    def get_current_track(self) -> Track | None:
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index]
        return None

    def get_current_index(self) -> int:
        return self._current_index

    def get_playlist(self) -> list[Track]:
        return list(self._playlist)

    # ── Shuffle / repeat properties ────────────────────────────────────────

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @shuffle.setter
    def shuffle(self, enabled: bool) -> None:
        self._shuffle = enabled

    @property
    def repeat(self) -> bool:
        return self._repeat

    @repeat.setter
    def repeat(self, enabled: bool) -> None:
        self._repeat = enabled

    # ── Internal helpers ───────────────────────────────────────────────────

    def _load_index(self, index: int) -> None:
        """Set the media source to the track at *index* and emit track_changed."""
        self._current_index = index
        track = self._playlist[index]
        self._media_player.setSource(QUrl.fromLocalFile(track.file_path))
        self.track_changed.emit(track)

    def _wire_qt_signals(self) -> None:
        """
        Forward relevant Qt signals to our own signals.

        PyQt6 refuses a direct signal-to-signal connection when the source
        carries a C++ enum type (e.g. QMediaPlayer::PlaybackState) and the
        destination is declared as pyqtSignal(object).  A lambda bridge
        routes the value through a Python callable first, which satisfies
        the type system.
        """
        # Lambda bridges are required for every connection from a C++ Qt signal
        # to a Python pyqtSignal.  PyQt6 rejects direct connections when the
        # C++ type (qint64, QMediaPlayer::PlaybackState, …) doesn't exactly
        # match the Python signal's declared type.  Routing through a lambda
        # passes the value as a plain Python object, which always succeeds.
        self._media_player.playbackStateChanged.connect(
            lambda state: self.playback_state_changed.emit(state)
        )
        self._media_player.positionChanged.connect(
            lambda pos: self.position_changed.emit(int(pos))
        )
        self._media_player.durationChanged.connect(
            lambda dur: self.duration_changed.emit(int(dur))
        )
        self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._media_player.errorOccurred.connect(self._on_error)
        self._audio_output.volumeChanged.connect(
            lambda vol: self.volume_changed.emit(float(vol))
        )

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Auto-advance or repeat when the current track ends."""
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if self._repeat:
            self._media_player.setPosition(0)
            self._media_player.play()
        else:
            self.next_track()

    def _on_error(self, _error, error_string: str) -> None:
        self.error_occurred.emit(f"Playback error: {error_string}")
