"""
Player controls bar.

The bottom strip of the main window.  Contains:

  Left   — transport buttons (prev / play-pause / next / shuffle / repeat)
  Centre — track title label + waveform seek-bar + elapsed / total time
  Right  — mute toggle + volume slider

The bar subscribes to AudioPlayer's signals and translates user actions back
into AudioPlayer calls, so it has no business logic of its own.
"""

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.player import AudioPlayer
from ui.components.waveform_bar import WaveformBar
from utils.helpers import ms_to_mmss


class PlayerControls(QWidget):
    """
    Bottom transport bar.

    Design notes
    ------------
    * The volume slider and mute button share state via AudioPlayer.last_volume
      so the mute toggle remembers the pre-mute level.
    * We skip the @pyqtSlot decorator for signals carrying custom Python types
      (Track, PlaybackState) because PyQt6 resolves the connection at runtime
      and explicit C++ type strings are not required for pure-Python types.
    """

    def __init__(self, player: AudioPlayer, parent=None) -> None:
        super().__init__(parent)
        self._player = player
        self._is_seeking = False  # blocks position_changed feedback during drag

        self.setObjectName("playerControls")
        self.setFixedHeight(96)

        self._build_ui()
        self._connect_signals()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 8, 20, 8)
        root.setSpacing(20)

        root.addLayout(self._build_transport())
        root.addLayout(self._build_centre(), stretch=1)
        root.addLayout(self._build_volume())

    def _build_transport(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(4)

        self._btn_prev = _ControlButton("⏮", "Previous track")
        self._btn_play = _ControlButton("▶", "Play / Pause", accent=True)
        self._btn_next = _ControlButton("⏭", "Next track")
        self._btn_shuffle = _ControlButton("⇄", "Shuffle", checkable=True)
        self._btn_repeat = _ControlButton("↻", "Repeat", checkable=True)

        for btn in (
            self._btn_prev,
            self._btn_play,
            self._btn_next,
            self._btn_shuffle,
            self._btn_repeat,
        ):
            layout.addWidget(btn)

        return layout

    def _build_centre(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)

        # Track title
        self._lbl_title = QLabel("No track loaded")
        self._lbl_title.setObjectName("trackTitle")
        self._lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Seek row: elapsed | waveform | duration
        seek_row = QHBoxLayout()
        seek_row.setSpacing(10)

        self._lbl_elapsed = QLabel("00:00")
        self._lbl_elapsed.setObjectName("timeLabel")
        self._lbl_elapsed.setFixedWidth(38)
        self._lbl_elapsed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._waveform = WaveformBar(self)
        self._waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._lbl_duration = QLabel("00:00")
        self._lbl_duration.setObjectName("timeLabel")
        self._lbl_duration.setFixedWidth(38)
        self._lbl_duration.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        seek_row.addWidget(self._lbl_elapsed)
        seek_row.addWidget(self._waveform, stretch=1)
        seek_row.addWidget(self._lbl_duration)

        layout.addWidget(self._lbl_title)
        layout.addLayout(seek_row)

        return layout

    def _build_volume(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self._btn_mute = _ControlButton("🔊", "Mute / Unmute")

        self._slider_volume = QSlider(Qt.Orientation.Horizontal)
        self._slider_volume.setObjectName("volumeSlider")
        self._slider_volume.setRange(0, 100)
        self._slider_volume.setValue(70)
        self._slider_volume.setFixedWidth(96)
        self._slider_volume.setToolTip("Volume")

        layout.addWidget(self._btn_mute)
        layout.addWidget(self._slider_volume)

        return layout

    # ── Signal wiring ──────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Transport buttons → player
        self._btn_play.clicked.connect(self._player.toggle_play_pause)
        self._btn_prev.clicked.connect(self._player.previous_track)
        self._btn_next.clicked.connect(self._player.next_track)
        self._btn_shuffle.clicked.connect(self._on_shuffle_toggled)
        self._btn_repeat.clicked.connect(self._on_repeat_toggled)
        self._btn_mute.clicked.connect(self._on_mute_clicked)

        # Volume slider → player
        self._slider_volume.valueChanged.connect(
            lambda v: self._player.set_volume(v / 100.0)
        )

        # Waveform → player (seek on click / drag)
        self._waveform.seek_requested.connect(self._on_seek_requested)

        # Player → UI
        self._player.playback_state_changed.connect(self._on_playback_state_changed)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.duration_changed.connect(self._on_duration_changed)
        self._player.track_changed.connect(self._on_track_changed)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _on_playback_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._btn_play.setText("⏸" if playing else "▶")

    @pyqtSlot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        if self._is_seeking:
            return
        self._lbl_elapsed.setText(ms_to_mmss(position_ms))
        duration = self._player.get_duration()
        if duration > 0:
            self._waveform.set_progress(position_ms / duration)

    @pyqtSlot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        self._lbl_duration.setText(ms_to_mmss(duration_ms))

    def _on_track_changed(self, track) -> None:
        self._lbl_title.setText(f"{track.title}  ·  {track.artist}")
        self._waveform.regenerate()

    @pyqtSlot(float)
    def _on_seek_requested(self, fraction: float) -> None:
        duration = self._player.get_duration()
        if duration > 0:
            self._player.seek(int(fraction * duration))

    def _on_shuffle_toggled(self) -> None:
        self._player.shuffle = self._btn_shuffle.isChecked()

    def _on_repeat_toggled(self) -> None:
        self._player.repeat = self._btn_repeat.isChecked()

    def _on_mute_clicked(self) -> None:
        current = self._player.get_volume()
        if current > 0.0:
            # Mute: remember current level
            self._player.last_volume = current
            self._player.set_volume(0.0)
            self._btn_mute.setText("🔇")
            self._slider_volume.setValue(0)
        else:
            # Unmute: restore remembered level
            restore = self._player.last_volume
            self._player.set_volume(restore)
            self._btn_mute.setText("🔊")
            self._slider_volume.setValue(int(restore * 100))


# ── Helper widget ──────────────────────────────────────────────────────────────

class _ControlButton(QPushButton):
    """
    Styled transport button.

    *accent=True* applies the bright play/pause style.
    *checkable=True* lets the button act as a toggle (shuffle, repeat).
    """

    def __init__(
        self,
        text: str,
        tooltip: str,
        accent: bool = False,
        checkable: bool = False,
    ) -> None:
        super().__init__(text)
        self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self.setFixedSize(36, 36)
        self.setObjectName("playButton" if accent else "controlButton")
