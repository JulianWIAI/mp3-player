"""
Library panel (left sidebar).

Lets the user:
  • Search the library by title / artist / album
  • Add individual files via a file dialog
  • Add an entire folder (scanned recursively) via a folder dialog
  • Double-click a track to load it into the queue

Scanning runs in a LibraryScanWorker thread so the UI stays responsive
even when adding thousands of files.

The panel emits tracks_selected(list[Track]) when the user wants to play
something; MainWindow passes that list to AudioPlayer.set_playlist().
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.database import DatabaseManager
from core.library_scanner import AUDIO_EXTENSIONS, LibraryScanWorker
from models.track import Track


class LibraryPanel(QWidget):
    """
    Left sidebar: library browser.

    Signals
    -------
    tracks_selected(list) — emitted when the user wants to load a track or
                            a set of tracks into the main queue.
    """

    tracks_selected = pyqtSignal(list)  # list[Track]

    def __init__(self, db: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._all_tracks: list[Track] = []
        self._scan_worker: LibraryScanWorker | None = None

        # Debounce timer — refresh search 300 ms after the user stops typing
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

        self.setObjectName("libraryPanel")
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)

        self._build_ui()
        self._refresh()

    # ── Public interface ───────────────────────────────────────────────────

    def reload(self) -> None:
        """Re-read the database and repopulate the list (call after scanning)."""
        self._refresh()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("sidebarHeader")
        h_row = QHBoxLayout(header)
        h_row.setContentsMargins(14, 10, 14, 10)
        title_lbl = QLabel("LIBRARY")
        title_lbl.setObjectName("sidebarTitle")
        h_row.addWidget(title_lbl)
        h_row.addStretch()
        self._lbl_count = QLabel("")
        self._lbl_count.setObjectName("panelSubtitle")
        h_row.addWidget(self._lbl_count)

        # ── Search bar ─────────────────────────────────────────────────────
        search_wrap = QWidget()
        search_wrap.setObjectName("searchContainer")
        s_row = QHBoxLayout(search_wrap)
        s_row.setContentsMargins(10, 6, 10, 6)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchBar")
        self._search_input.setPlaceholderText("Search…")
        self._search_input.textChanged.connect(lambda: self._search_timer.start())
        s_row.addWidget(self._search_input)

        # ── Action buttons ─────────────────────────────────────────────────
        btn_wrap = QWidget()
        btn_wrap.setObjectName("btnContainer")
        btn_row = QHBoxLayout(btn_wrap)
        btn_row.setContentsMargins(10, 4, 10, 4)
        btn_row.setSpacing(6)

        self._btn_add_files = QPushButton("+ Files")
        self._btn_add_files.setObjectName("sidebarButton")
        self._btn_add_folder = QPushButton("+ Folder")
        self._btn_add_folder.setObjectName("sidebarButton")
        self._btn_add_files.setToolTip("Add audio files to the library")
        self._btn_add_folder.setToolTip("Scan a folder for audio files")

        self._btn_add_files.clicked.connect(self._on_add_files)
        self._btn_add_folder.clicked.connect(self._on_add_folder)

        btn_row.addWidget(self._btn_add_files)
        btn_row.addWidget(self._btn_add_folder)

        # ── Status label (shown during scanning) ───────────────────────────
        self._lbl_status = QLabel("")
        self._lbl_status.setObjectName("scanStatus")
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.setVisible(False)

        # ── Track list ─────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setObjectName("libraryList")
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(header)
        layout.addWidget(search_wrap)
        layout.addWidget(btn_wrap)
        layout.addWidget(self._lbl_status)
        layout.addWidget(self._list, stretch=1)

    # ── Data helpers ───────────────────────────────────────────────────────

    def _refresh(self) -> None:
        """Load all tracks from the database and repopulate the list."""
        self._all_tracks = self._db.get_all_tracks()
        self._populate_list(self._all_tracks)

    def _populate_list(self, tracks: list[Track]) -> None:
        """Replace list contents with *tracks*."""
        self._list.clear()
        for track in tracks:
            item = QListWidgetItem(f"{track.title}\n{track.artist}")
            item.setData(Qt.ItemDataRole.UserRole, track)
            item.setToolTip(f"{track.artist}  ·  {track.album}  ·  {track.formatted_duration()}")
            self._list.addItem(item)
        count = len(tracks)
        self._lbl_count.setText(f"{count}")

    # ── Slots ──────────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        query = self._search_input.text().strip()
        if query:
            results = self._db.search_tracks(query)
        else:
            results = self._all_tracks
        self._populate_list(results)

    def _on_add_files(self) -> None:
        extensions = " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Audio Files",
            "",
            f"Audio Files ({extensions});;All Files (*)",
        )
        if paths:
            self._start_scan(paths)

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if folder:
            self._start_scan([folder])

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Load all currently visible tracks into the queue and play the clicked one."""
        clicked_track: Track = item.data(Qt.ItemDataRole.UserRole)

        # Collect all tracks visible in the list (respects current search filter)
        visible_tracks = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]
        self.tracks_selected.emit(visible_tracks)

        # Find the index of the clicked track in the visible list so MainWindow
        # can tell AudioPlayer which track to start from.
        try:
            start_idx = visible_tracks.index(clicked_track)
        except ValueError:
            start_idx = 0

        # Re-emit with the start index embedded — MainWindow reads index 0 by
        # default but we need to pass the real index.  We use a two-signal
        # approach: first tracks_selected, then the main window plays start_idx.
        # For simplicity, we store start_idx in an attribute read by MainWindow.
        self._pending_start_index = start_idx

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        track: Track = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        action_play = menu.addAction("▶  Play now")
        action_queue = menu.addAction("+ Add to queue")
        menu.addSeparator()
        action_remove = menu.addAction("Remove from library")

        chosen = menu.exec(self._list.viewport().mapToGlobal(pos))
        if chosen == action_play:
            self.tracks_selected.emit([track])
        elif chosen == action_queue:
            # Notify MainWindow to append rather than replace — implement via
            # a dedicated signal if needed; for now we emit with current playlist.
            self.tracks_selected.emit([track])
        elif chosen == action_remove and track.id is not None:
            self._db.remove_track(track.id)
            self._list.takeItem(self._list.row(item))
            self._all_tracks = [t for t in self._all_tracks if t.id != track.id]
            count = self._list.count()
            self._lbl_count.setText(str(count))

    # ── Scanning ───────────────────────────────────────────────────────────

    def _start_scan(self, paths: list[str]) -> None:
        """Launch a background scan worker for *paths*."""
        if self._scan_worker and self._scan_worker.isRunning():
            return  # one scan at a time

        self._lbl_status.setText("Scanning…")
        self._lbl_status.setVisible(True)
        self._btn_add_files.setEnabled(False)
        self._btn_add_folder.setEnabled(False)

        self._scan_worker = LibraryScanWorker(paths, self._db, self)
        self._scan_worker.track_found.connect(self._on_track_found)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_track_found(self, track: Track) -> None:
        """Called from the worker thread for each discovered track."""
        # Update _all_tracks; avoid duplicates by file path
        paths = {t.file_path for t in self._all_tracks}
        if track.file_path not in paths:
            self._all_tracks.append(track)

        # Only add to the list widget if the search field is empty (or matches)
        query = self._search_input.text().strip().lower()
        if not query or query in track.title.lower() or query in track.artist.lower():
            item = QListWidgetItem(f"{track.title}\n{track.artist}")
            item.setData(Qt.ItemDataRole.UserRole, track)
            item.setToolTip(
                f"{track.artist}  ·  {track.album}  ·  {track.formatted_duration()}"
            )
            self._list.addItem(item)
            self._lbl_count.setText(str(self._list.count()))

    def _on_scan_finished(self, count: int) -> None:
        self._lbl_status.setText(f"Added {count} track{'s' if count != 1 else ''}")
        QTimer.singleShot(3000, lambda: self._lbl_status.setVisible(False))
        self._btn_add_files.setEnabled(True)
        self._btn_add_folder.setEnabled(True)
