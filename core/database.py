"""
SQLite database manager.

Responsible exclusively for persisting and querying the music library.
All SQL is kept here so the rest of the app works with Track objects and
never writes raw queries.

Schema
------
  tracks          — one row per unique audio file
  playlists       — named user playlists
  playlist_tracks — ordered join between playlists and tracks
"""

import sqlite3
from datetime import datetime
from typing import Optional

from models.track import Track


class DatabaseManager:
    """
    Thin wrapper around a SQLite database file.

    Every public method opens and closes its own connection so the manager
    is safe to use from multiple widgets without connection sharing.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._initialise_schema()

    # ── Connection helper ──────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row      # access columns by name
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Schema bootstrap ───────────────────────────────────────────────────

    def _initialise_schema(self) -> None:
        """Create all tables and indexes on first run; is a no-op afterwards."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path    TEXT    UNIQUE NOT NULL,
                    title        TEXT,
                    artist       TEXT,
                    album        TEXT,
                    genre        TEXT,
                    year         INTEGER,
                    duration     REAL    DEFAULT 0.0,
                    bitrate      INTEGER,
                    sample_rate  INTEGER,
                    track_number INTEGER,
                    cover_art    BLOB,
                    date_added   TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks (artist);
                CREATE INDEX IF NOT EXISTS idx_tracks_album  ON tracks (album);
                CREATE INDEX IF NOT EXISTS idx_tracks_title  ON tracks (title);

                CREATE TABLE IF NOT EXISTS playlists (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    name    TEXT NOT NULL,
                    created TEXT
                );

                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    track_id    INTEGER NOT NULL REFERENCES tracks(id)    ON DELETE CASCADE,
                    position    INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (playlist_id, track_id)
                );
            """)

    # ── Track CRUD ─────────────────────────────────────────────────────────

    def upsert_track(self, track: Track) -> int:
        """
        Insert a new track or update the metadata of an existing one.

        The file path is the natural key.  Returns the track's database id.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tracks
                    (file_path, title, artist, album, genre, year,
                     duration, bitrate, sample_rate, track_number,
                     cover_art, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    title        = excluded.title,
                    artist       = excluded.artist,
                    album        = excluded.album,
                    genre        = excluded.genre,
                    year         = excluded.year,
                    duration     = excluded.duration,
                    bitrate      = excluded.bitrate,
                    sample_rate  = excluded.sample_rate,
                    track_number = excluded.track_number,
                    cover_art    = excluded.cover_art
                """,
                (
                    track.file_path,
                    track.title,
                    track.artist,
                    track.album,
                    track.genre,
                    track.year,
                    track.duration,
                    track.bitrate,
                    track.sample_rate,
                    track.track_number,
                    track.cover_art,
                    datetime.now().isoformat(),
                ),
            )
            # For an UPDATE the lastrowid is 0; fetch the real id instead.
            if cursor.lastrowid:
                return cursor.lastrowid
            row = conn.execute(
                "SELECT id FROM tracks WHERE file_path = ?", (track.file_path,)
            ).fetchone()
            return row["id"]

    def get_all_tracks(self) -> list[Track]:
        """Return every track ordered by artist → album → track number → title."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tracks
                ORDER BY artist COLLATE NOCASE,
                         album  COLLATE NOCASE,
                         track_number,
                         title  COLLATE NOCASE
                """
            ).fetchall()
        return [self._row_to_track(r) for r in rows]

    def search_tracks(self, query: str) -> list[Track]:
        """Return tracks whose title, artist, or album contains *query*."""
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tracks
                WHERE  title  LIKE ? COLLATE NOCASE
                   OR  artist LIKE ? COLLATE NOCASE
                   OR  album  LIKE ? COLLATE NOCASE
                ORDER BY artist COLLATE NOCASE,
                         album  COLLATE NOCASE,
                         track_number,
                         title  COLLATE NOCASE
                """,
                (like, like, like),
            ).fetchall()
        return [self._row_to_track(r) for r in rows]

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Fetch a single track by its primary key."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tracks WHERE id = ?", (track_id,)
            ).fetchone()
        return self._row_to_track(row) if row else None

    def remove_track(self, track_id: int) -> None:
        """Delete a track from the library (cascades to playlist_tracks)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))

    # ── Playlist helpers ───────────────────────────────────────────────────

    def create_playlist(self, name: str) -> int:
        """Create a new empty playlist and return its id."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO playlists (name, created) VALUES (?, ?)",
                (name, datetime.now().isoformat()),
            )
            return cursor.lastrowid

    def get_playlists(self) -> list[dict]:
        """Return all playlists as plain dicts."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM playlists ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_track_to_playlist(
        self, playlist_id: int, track_id: int, position: int
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO playlist_tracks (playlist_id, track_id, position)
                VALUES (?, ?, ?)
                """,
                (playlist_id, track_id, position),
            )

    def get_playlist_tracks(self, playlist_id: int) -> list[Track]:
        """Return tracks in a playlist ordered by position."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.* FROM tracks t
                JOIN   playlist_tracks pt ON pt.track_id = t.id
                WHERE  pt.playlist_id = ?
                ORDER  BY pt.position
                """,
                (playlist_id,),
            ).fetchall()
        return [self._row_to_track(r) for r in rows]

    # ── Row converter ──────────────────────────────────────────────────────

    @staticmethod
    def _row_to_track(row: sqlite3.Row) -> Track:
        return Track(
            id=row["id"],
            file_path=row["file_path"],
            title=row["title"] or "Unknown Title",
            artist=row["artist"] or "Unknown Artist",
            album=row["album"] or "Unknown Album",
            genre=row["genre"] or "Unknown Genre",
            year=row["year"],
            duration=row["duration"] or 0.0,
            bitrate=row["bitrate"],
            sample_rate=row["sample_rate"],
            track_number=row["track_number"],
            cover_art=row["cover_art"],
            date_added=row["date_added"],
        )
