"""
Main application window.

Owns the two long-lived service objects (AudioPlayer, DatabaseManager) and
composes the four UI panels into a single window.  All inter-panel
communication flows through this class — panels only know their own signals
and call-back methods, never each other.

Layout
------
┌──────────────────────────────────────────────────────────────────┐
│  LibraryPanel  │         PlaylistView          │  TrackInfoPanel │
│  (left, ~220)  │         (centre, flex)        │  (right, ~280)  │
├────────────────┴───────────────────────────────┴─────────────────┤
│                     PlayerControls (bottom, 96 px)               │
└──────────────────────────────────────────────────────────────────┘
"""

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.database import DatabaseManager
from core.player import AudioPlayer
from ui.components.library_panel import LibraryPanel
from ui.components.player_controls import PlayerControls
from ui.components.playlist_view import PlaylistView
from ui.components.track_info_panel import TrackInfoPanel


class MainWindow(QMainWindow):
    """Top-level window.  Entry point for all UI interactions."""

    def __init__(self, data_dir: Path, parent=None) -> None:
        super().__init__(parent)

        # ── Service layer ──────────────────────────────────────────────────
        self._db = DatabaseManager(str(data_dir / "library.db"))
        self._player = AudioPlayer(self)

        # ── Build UI ───────────────────────────────────────────────────────
        self._init_window()
        self._build_panels()
        self._build_controls()
        self._build_status_bar()
        self._connect_signals()

        # ── Populate on startup ────────────────────────────────────────────
        self._load_library_into_queue()

    # ── Window setup ──────────────────────────────────────────────────────

    def _init_window(self) -> None:
        self.setWindowTitle("MP3 Player")
        self.setMinimumSize(QSize(1024, 680))
        self.resize(1280, 800)

        self._central = QWidget()
        self._root_layout = QVBoxLayout(self._central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        self.setCentralWidget(self._central)

    def _build_panels(self) -> None:
        """Create the three-column splitter layout."""
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.setHandleWidth(1)

        self._library_panel = LibraryPanel(self._db, self)
        self._playlist_view = PlaylistView(self)
        self._track_info = TrackInfoPanel(self)

        # Prevent the info panel from being squeezed out by the splitter
        self._track_info.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        self._splitter.addWidget(self._library_panel)
        self._splitter.addWidget(self._playlist_view)
        self._splitter.addWidget(self._track_info)

        # Starting widths: library | queue | info
        self._splitter.setSizes([230, 750, 300])
        self._splitter.setCollapsible(0, True)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, False)

        self._root_layout.addWidget(self._splitter, stretch=1)

    def _build_controls(self) -> None:
        self._controls = PlayerControls(self._player, self)
        self._root_layout.addWidget(self._controls)

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self._status_bar.setMaximumHeight(22)
        self.setStatusBar(self._status_bar)

    # ── Signal wiring ──────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        """
        Connect signals between panels and the service layer.

        Each connection is one-directional: a panel emits → MainWindow
        handles → calls into the service or another panel.  Panels never
        hold references to each other.
        """
        # Library → MainWindow: user picked tracks to load
        self._library_panel.tracks_selected.connect(self._on_library_selection)

        # Playlist → Player: user double-clicked a row
        self._playlist_view.track_activated.connect(self._player.play_track)

        # Player → TrackInfo: repaint metadata panel
        self._player.track_changed.connect(self._track_info.update_track)

        # Player → PlaylistView: highlight the active row
        self._player.track_changed.connect(self._on_player_track_changed)

        # Player errors → status bar
        self._player.error_occurred.connect(self._status_bar.showMessage)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _on_library_selection(self, tracks: list) -> None:
        """
        Replace the queue with *tracks* from the library panel.

        The library panel also stores the intended start index in
        _pending_start_index when the user double-clicks (vs. selecting via
        context menu where index 0 is fine).
        """
        start = getattr(self._library_panel, "_pending_start_index", 0)
        # Reset so the next single-file play defaults to 0
        self._library_panel._pending_start_index = 0

        self._playlist_view.set_tracks(tracks)
        self._player.set_playlist(tracks, start_index=start)
        self._player.play()

    def _on_player_track_changed(self, track) -> None:
        """Keep the playlist highlight in sync with what the player is doing."""
        idx = self._player.get_current_index()
        self._playlist_view.set_active_track(idx)

    # ── Startup ────────────────────────────────────────────────────────────

    def _load_library_into_queue(self) -> None:
        """
        Pre-populate the queue from the saved library on launch.

        Does not auto-play — the user presses Play when ready.
        """
        tracks = self._db.get_all_tracks()
        if tracks:
            self._playlist_view.set_tracks(tracks)
            self._player.set_playlist(tracks, start_index=0)

    # ── Window lifecycle ───────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        self._player.stop()
        event.accept()
