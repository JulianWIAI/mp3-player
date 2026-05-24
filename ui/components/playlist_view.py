"""
Playlist / queue view (centre panel).

Shows the current playback queue as a table with columns:
  #  |  Title  |  Artist  |  Album  |  Duration

The active (playing) row is highlighted in the accent colour.
Double-clicking a row emits track_activated(index) so MainWindow can call
AudioPlayer.play_track(index).

A right-click context menu allows removing a track from the queue.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.track import Track

_ACCENT = QColor("#00E5FF")
_DEFAULT_FG = QColor("#AAAAAA")
_ROW_HEIGHT = 36

_COLUMNS = ("#", "Title", "Artist", "Album", "Duration")
_COL_NUM = 0
_COL_TITLE = 1
_COL_ARTIST = 2
_COL_ALBUM = 3
_COL_DURATION = 4


class PlaylistView(QWidget):
    """
    Centre panel: editable playback queue.

    Signals
    -------
    track_activated(int) — emitted when the user double-clicks a row;
                           carries the row index in the current queue.
    """

    track_activated = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("playlistView")
        self._tracks: list[Track] = []
        self._active_index: int = -1
        self._build_ui()

    # ── Public interface ───────────────────────────────────────────────────

    def set_tracks(self, tracks: list[Track]) -> None:
        """Repopulate the table with a new track list."""
        self._tracks = list(tracks)
        self._active_index = -1

        self._table.setRowCount(0)
        self._table.setSortingEnabled(False)

        for i, track in enumerate(self._tracks):
            self._table.insertRow(i)
            self._set_row(i, track)

        self._table.setSortingEnabled(False)

    def set_active_track(self, index: int) -> None:
        """Highlight *index* as the currently playing row."""
        old = self._active_index
        self._active_index = index
        # Repaint only the two affected rows for performance
        for row in (old, index):
            if 0 <= row < self._table.rowCount():
                self._apply_row_style(row)
        # Scroll so the active row is visible
        if 0 <= index < self._table.rowCount():
            self._table.scrollToItem(
                self._table.item(index, _COL_TITLE),
                QAbstractItemView.ScrollHint.EnsureVisible,
            )

    def remove_track_at(self, index: int) -> None:
        """Remove a track from the queue by row index."""
        if 0 <= index < len(self._tracks):
            self._tracks.pop(index)
            self._table.removeRow(index)
            # Re-number all rows after the removed one
            for row in range(index, self._table.rowCount()):
                item = self._table.item(row, _COL_NUM)
                if item:
                    item.setText(str(row + 1))

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header strip
        header_bar = QWidget()
        header_bar.setObjectName("panelHeader")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 8, 16, 8)
        lbl = QLabel("QUEUE")
        lbl.setObjectName("panelTitle")
        header_layout.addWidget(lbl)
        header_layout.addStretch()
        self._lbl_count = QLabel("0 tracks")
        self._lbl_count.setObjectName("panelSubtitle")
        header_layout.addWidget(self._lbl_count)

        # Track table
        self._table = QTableWidget()
        self._table.setObjectName("trackTable")
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Column sizing
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(_COL_NUM,      QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(_COL_TITLE,    QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_ARTIST,   QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(_COL_ALBUM,    QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(_COL_DURATION, QHeaderView.ResizeMode.Fixed)

        self._table.setColumnWidth(_COL_NUM,      42)
        self._table.setColumnWidth(_COL_ARTIST,  160)
        self._table.setColumnWidth(_COL_ALBUM,   150)
        self._table.setColumnWidth(_COL_DURATION, 58)

        self._table.doubleClicked.connect(
            lambda idx: self.track_activated.emit(idx.row())
        )
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(header_bar)
        layout.addWidget(self._table, stretch=1)

    # ── Private helpers ────────────────────────────────────────────────────

    def _set_row(self, row: int, track: Track) -> None:
        """Populate all cells of *row* from *track*."""
        data = [
            str(row + 1),
            track.title,
            track.artist,
            track.album,
            track.formatted_duration(),
        ]
        for col, text in enumerate(data):
            item = QTableWidgetItem(text)
            item.setForeground(_DEFAULT_FG)
            if col == _COL_NUM:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            self._table.setItem(row, col, item)
        self._table.setRowHeight(row, _ROW_HEIGHT)

        # Update track count label
        total = self._table.rowCount()
        self._lbl_count.setText(f"{total} track{'s' if total != 1 else ''}")

    def _apply_row_style(self, row: int) -> None:
        """Paint the active row accent colour, or reset to default."""
        is_active = row == self._active_index
        color = _ACCENT if is_active else _DEFAULT_FG

        font = QFont()
        font.setBold(is_active)

        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item:
                item.setForeground(color)
                item.setFont(font)

    def _show_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return

        menu = QMenu(self)
        action_play = menu.addAction("▶  Play now")
        menu.addSeparator()
        action_remove = menu.addAction("Remove from queue")

        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen == action_play:
            self.track_activated.emit(row)
        elif chosen == action_remove:
            self.remove_track_at(row)
