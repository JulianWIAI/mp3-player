"""
Track info panel (right sidebar).

Displays:
  • Rounded album artwork (or a musical note placeholder)
  • Title, Artist, Album labels
  • A metadata grid: Genre · Year · Duration · Bitrate · Sample rate

Updated by connecting AudioPlayer.track_changed to update_track().
"""

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.track import Track

_COVER_SIZE = 220
_CORNER_RADIUS = 14
_PLACEHOLDER_BG = QColor("#1E1E1E")
_PLACEHOLDER_NOTE_COLOR = QColor("#333333")


class TrackInfoPanel(QWidget):
    """
    Right-hand panel: album art + full track metadata.

    Layout
    ------
    ┌─────────────────────┐
    │    [ cover art ]    │
    ├─────────────────────┤
    │  Title              │
    │  Artist             │
    │  Album              │
    ├─────────────────────┤
    │  Genre  │  value    │
    │  Year   │  value    │
    │  …      │  …        │
    └─────────────────────┘
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("trackInfoPanel")
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Cover art ──────────────────────────────────────────────────────
        self._cover = QLabel()
        self._cover.setObjectName("coverArt")
        self._cover.setFixedSize(_COVER_SIZE, _COVER_SIZE)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_placeholder()
        layout.addWidget(self._cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(16)
        layout.addWidget(_separator())
        layout.addSpacing(14)

        # ── Title / Artist / Album ─────────────────────────────────────────
        self._lbl_title = QLabel("—")
        self._lbl_title.setObjectName("infoTitle")
        self._lbl_title.setWordWrap(True)

        self._lbl_artist = QLabel("—")
        self._lbl_artist.setObjectName("infoArtist")
        self._lbl_artist.setWordWrap(True)

        self._lbl_album = QLabel("—")
        self._lbl_album.setObjectName("infoAlbum")
        self._lbl_album.setWordWrap(True)

        layout.addWidget(self._lbl_title)
        layout.addSpacing(2)
        layout.addWidget(self._lbl_artist)
        layout.addSpacing(2)
        layout.addWidget(self._lbl_album)

        layout.addSpacing(14)
        layout.addWidget(_separator())
        layout.addSpacing(12)

        # ── Metadata grid ──────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setHorizontalSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)

        self._rows: dict[str, QLabel] = {}
        meta_fields = ["Genre", "Year", "Duration", "Bitrate", "Sample rate"]
        for row_idx, field in enumerate(meta_fields):
            key_lbl = QLabel(field)
            key_lbl.setObjectName("metaKey")

            val_lbl = QLabel("—")
            val_lbl.setObjectName("metaValue")
            self._rows[field] = val_lbl

            grid.addWidget(key_lbl, row_idx, 0)
            grid.addWidget(val_lbl, row_idx, 1)

        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch()

    # ── Public slot ────────────────────────────────────────────────────────

    @pyqtSlot(object)
    def update_track(self, track: Track) -> None:
        """Refresh all labels for *track*.  Called on AudioPlayer.track_changed."""
        self._lbl_title.setText(track.title)
        self._lbl_artist.setText(track.artist)
        self._lbl_album.setText(track.album)

        self._rows["Genre"].setText(track.genre or "—")
        self._rows["Year"].setText(str(track.year) if track.year else "—")
        self._rows["Duration"].setText(track.formatted_duration())
        self._rows["Bitrate"].setText(
            f"{track.bitrate // 1000} kbps" if track.bitrate else "—"
        )
        self._rows["Sample rate"].setText(
            f"{track.sample_rate:,} Hz" if track.sample_rate else "—"
        )

        if track.cover_art:
            pixmap = QPixmap()
            pixmap.loadFromData(track.cover_art)
            self._show_cover(pixmap)
        else:
            self._show_placeholder()

    # ── Private helpers ────────────────────────────────────────────────────

    def _show_cover(self, pixmap: QPixmap) -> None:
        """Scale, crop to square, and round the corners of *pixmap*."""
        scaled = pixmap.scaled(
            _COVER_SIZE,
            _COVER_SIZE,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Centre-crop to exact square
        cx = (scaled.width() - _COVER_SIZE) // 2
        cy = (scaled.height() - _COVER_SIZE) // 2
        cropped = scaled.copy(cx, cy, _COVER_SIZE, _COVER_SIZE)
        self._cover.setPixmap(_rounded(cropped, _CORNER_RADIUS))

    def _show_placeholder(self) -> None:
        """Paint a dark rounded square with a musical note."""
        px = QPixmap(_COVER_SIZE, _COVER_SIZE)
        px.fill(Qt.GlobalColor.transparent)

        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        path = QPainterPath()
        path.addRoundedRect(0, 0, _COVER_SIZE, _COVER_SIZE, _CORNER_RADIUS, _CORNER_RADIUS)
        p.fillPath(path, _PLACEHOLDER_BG)

        # Musical note
        font = p.font()
        font.setPixelSize(80)
        p.setFont(font)
        p.setPen(_PLACEHOLDER_NOTE_COLOR)
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
        p.end()

        self._cover.setPixmap(px)


# ── Module-level helpers ───────────────────────────────────────────────────────

def _separator() -> QFrame:
    """Return a thin horizontal rule styled via the QSS #separator rule."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setObjectName("separator")
    return line


def _rounded(pixmap: QPixmap, radius: int) -> QPixmap:
    """Return a copy of *pixmap* with rounded corners."""
    result = QPixmap(pixmap.size())
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pixmap)
    p.end()
    return result
