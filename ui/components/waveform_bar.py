"""
Waveform seek-bar widget.

Renders a pseudo-random waveform as a row of vertical bars.  Bars to the
left of the playhead are painted in the accent colour; bars to the right
are muted grey — giving a clear visual cue of playback progress.

Clicking or dragging emits seek_requested(fraction) where fraction is in
[0.0, 1.0].  The controller (PlayerControls) converts that to milliseconds
and calls AudioPlayer.seek().

Enhancement note
----------------
For a real waveform derived from audio samples you would decode the file
with e.g. soundfile or pydub, compute per-chunk RMS values, and pass the
resulting array to set_waveform_data().  The painting logic below already
supports an arbitrary float array — only _generate_bars() would change.
"""

import random

from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter
from PyQt6.QtWidgets import QWidget

# Accent and dim colours — kept in sync with the QSS variable names
_COLOUR_PLAYED = QColor("#00E5FF")
_COLOUR_UNPLAYED = QColor("#252525")
_COLOUR_HOVER = QColor("#00E5FFAA")


class WaveformBar(QWidget):
    """
    Custom seek-bar with a decorative waveform.

    Signals
    -------
    seek_requested(float) — emitted on click/drag; value is [0.0, 1.0]
    """

    seek_requested = pyqtSignal(float)

    _BAR_COUNT = 128
    _BAR_GAP = 2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bars: list[float] = []  # normalised heights [0.0, 1.0]
        self._progress: float = 0.0  # current playback fraction
        self._hover_fraction: float = -1.0  # mouse hover position (-1 = none)
        self._dragging: bool = False

        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._generate_bars()

    # ── Public interface ───────────────────────────────────────────────────

    def set_progress(self, fraction: float) -> None:
        """Update playback progress (0.0 = start, 1.0 = end)."""
        self._progress = max(0.0, min(1.0, fraction))
        self.update()

    def regenerate(self) -> None:
        """Generate a new waveform shape (call when a new track is loaded)."""
        self._generate_bars()
        self._progress = 0.0
        self.update()

    # ── Qt event overrides ─────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bar_w = max(
            1,
            (w - self._BAR_GAP * (self._BAR_COUNT - 1)) // self._BAR_COUNT,
        )
        total_w = bar_w * self._BAR_COUNT + self._BAR_GAP * (self._BAR_COUNT - 1)
        x_off = (w - total_w) // 2

        cutoff = int(self._progress * self._BAR_COUNT)
        hover_idx = (
            int(self._hover_fraction * self._BAR_COUNT)
            if self._hover_fraction >= 0
            else -1
        )

        for i, height_frac in enumerate(self._bars):
            bar_h = max(2, int(height_frac * h * 0.88))
            x = x_off + i * (bar_w + self._BAR_GAP)
            y = (h - bar_h) // 2

            if i < cutoff:
                color = _COLOUR_PLAYED
            elif i == hover_idx:
                color = _COLOUR_HOVER
            else:
                color = _COLOUR_UNPLAYED

            painter.fillRect(QRect(x, y, bar_w, bar_h), color)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._emit_seek(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._hover_fraction = max(0.0, min(1.0, event.position().x() / self.width()))
        if self._dragging:
            self._emit_seek(event.position().x())
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def leaveEvent(self, _event) -> None:
        self._hover_fraction = -1.0
        self.update()

    # ── Private helpers ────────────────────────────────────────────────────

    def _generate_bars(self) -> None:
        """
        Build a smoothed random-walk waveform.

        The random walk produces natural-looking variance while the
        smoothing pass removes jitter that would look like noise rather than
        music.
        """
        value = 0.5
        raw: list[float] = []
        for _ in range(self._BAR_COUNT):
            value += random.uniform(-0.18, 0.18)
            value = max(0.07, min(1.0, value))
            raw.append(value)

        # Simple 3-point moving average for smoother look
        smoothed: list[float] = []
        for i in range(len(raw)):
            neighbours = raw[max(0, i - 1) : i + 2]
            smoothed.append(sum(neighbours) / len(neighbours))

        self._bars = smoothed

    def _emit_seek(self, x: float) -> None:
        fraction = max(0.0, min(1.0, x / self.width()))
        self.seek_requested.emit(fraction)
