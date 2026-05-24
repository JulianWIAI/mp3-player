"""
Library scanner.

Runs in a background QThread so scanning large folders never freezes the UI.
Emits one signal per track found, plus a finished signal with the total count.
"""

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.database import DatabaseManager
from core.metadata import MetadataReader
from models.track import Track

# All container/codec extensions we attempt to handle via mutagen + QMediaPlayer
AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav", ".wma", ".opus", ".ape"}
)


class LibraryScanWorker(QThread):
    """
    Background worker that reads metadata from a list of paths and persists
    each track to the database.

    Paths can be individual files or directories (which are scanned
    recursively).
    """

    track_found = pyqtSignal(object)  # emits Track after each successful insert
    finished = pyqtSignal(int)        # emits total number of tracks added/updated

    def __init__(
        self,
        paths: list[str],
        db: DatabaseManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._db = db

    def run(self) -> None:
        """Entry point for the worker thread."""
        count = 0

        for raw_path in self._paths:
            path = Path(raw_path)

            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                count += self._process_file(path)

            elif path.is_dir():
                for audio_file in sorted(path.rglob("*")):
                    if audio_file.suffix.lower() in AUDIO_EXTENSIONS:
                        count += self._process_file(audio_file)

        self.finished.emit(count)

    def _process_file(self, path: Path) -> int:
        """
        Read metadata, upsert into DB, emit track_found.

        Returns 1 on success, 0 if an exception was raised.
        """
        try:
            track = MetadataReader.read(str(path))
            track_id = self._db.upsert_track(track)
            track.id = track_id
            self.track_found.emit(track)
            return 1
        except Exception as exc:
            print(f"[LibraryScanWorker] Failed to process '{path}': {exc}")
            return 0
