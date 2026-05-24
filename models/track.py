"""
Track data model.

A plain Python dataclass that carries every piece of information about a
single audio file.  It has no Qt or I/O dependencies so it can be used
safely across all layers of the application.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Track:
    """Represents one audio file together with all its metadata."""

    # ── Database identity ──────────────────────────────────────────────────
    id: Optional[int] = None

    # ── File system ────────────────────────────────────────────────────────
    file_path: str = ""

    # ── Human-readable tags ────────────────────────────────────────────────
    title: str = "Unknown Title"
    artist: str = "Unknown Artist"
    album: str = "Unknown Album"
    genre: str = "Unknown Genre"
    year: Optional[int] = None
    track_number: Optional[int] = None

    # ── Technical information ──────────────────────────────────────────────
    duration: float = 0.0          # seconds (float for sub-second precision)
    bitrate: Optional[int] = None  # bits per second, e.g. 320000
    sample_rate: Optional[int] = None  # Hz, e.g. 44100

    # ── Embedded artwork ──────────────────────────────────────────────────
    cover_art: Optional[bytes] = None  # raw image bytes from the audio tag

    # ── Library management ─────────────────────────────────────────────────
    date_added: Optional[str] = None  # ISO-8601 timestamp set by DatabaseManager

    # ── Helper methods ─────────────────────────────────────────────────────

    def formatted_duration(self) -> str:
        """Return duration as a human-readable MM:SS string."""
        total_seconds = int(self.duration)
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def display_name(self) -> str:
        """Return the best available display name (title or filename stem)."""
        if self.title and self.title != "Unknown Title":
            return self.title
        return os.path.splitext(os.path.basename(self.file_path))[0]

    def __str__(self) -> str:
        return f"{self.artist} — {self.title}"
