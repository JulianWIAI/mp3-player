"""
Metadata reader.

Uses mutagen to extract ID3 tags, Vorbis comments, MP4 atoms, and embedded
artwork from audio files.  Returns a fully populated Track dataclass so the
rest of the application never has to touch mutagen directly.
"""

import os
from typing import Optional

from mutagen import File
from mutagen.id3 import APIC
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

from models.track import Track


class MetadataReader:
    """Static helper that converts a file path into a Track object."""

    # ── Public API ─────────────────────────────────────────────────────────

    @staticmethod
    def read(file_path: str) -> Track:
        """
        Read all available metadata from *file_path*.

        Falls back gracefully when a tag is absent or malformed — the track
        is always returned, even if only the file path is known.
        """
        track = Track(file_path=file_path)

        try:
            # easy=True gives us normalised, lower-case key names across
            # different container formats (MP3/FLAC/MP4/OGG …).
            audio_easy = File(file_path, easy=True)

            if audio_easy is None:
                track.title = MetadataReader._filename_stem(file_path)
                return track

            track.title = (
                MetadataReader._tag(audio_easy, ["title"])
                or MetadataReader._filename_stem(file_path)
            )
            track.artist = MetadataReader._tag(audio_easy, ["artist"]) or "Unknown Artist"
            track.album = MetadataReader._tag(audio_easy, ["album"]) or "Unknown Album"
            track.genre = MetadataReader._tag(audio_easy, ["genre"]) or "Unknown Genre"

            # Year is sometimes stored as a full ISO date ("2023-04-01")
            year_raw = MetadataReader._tag(audio_easy, ["date", "year"])
            if year_raw:
                try:
                    track.year = int(str(year_raw)[:4])
                except (ValueError, TypeError):
                    pass

            # Track number may be "5/12" (track / total)
            tracknumber_raw = MetadataReader._tag(audio_easy, ["tracknumber"])
            if tracknumber_raw:
                try:
                    track.track_number = int(str(tracknumber_raw).split("/")[0])
                except (ValueError, TypeError):
                    pass

            if hasattr(audio_easy, "info"):
                track.duration = getattr(audio_easy.info, "length", 0.0)
                track.bitrate = getattr(audio_easy.info, "bitrate", None)
                track.sample_rate = getattr(audio_easy.info, "sample_rate", None)

            track.cover_art = MetadataReader._extract_cover(file_path)

        except Exception as exc:
            # Never crash on a bad file — just return what we have
            print(f"[MetadataReader] Could not read '{file_path}': {exc}")
            track.title = MetadataReader._filename_stem(file_path)

        return track

    # ── Private helpers ────────────────────────────────────────────────────

    @staticmethod
    def _tag(audio, keys: list[str]) -> Optional[str]:
        """Return the first non-empty value found under any of the given keys."""
        for key in keys:
            if key in audio:
                value = audio[key]
                if isinstance(value, list) and value:
                    return str(value[0]).strip()
                if value:
                    return str(value).strip()
        return None

    @staticmethod
    def _extract_cover(file_path: str) -> Optional[bytes]:
        """Return raw bytes of the first embedded cover image, or None."""
        try:
            audio = File(file_path)
            if audio is None:
                return None

            # MP3: ID3 APIC frame
            if hasattr(audio, "tags") and audio.tags:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        return tag.data

            # MP4 / M4A
            if isinstance(audio, MP4) and "covr" in audio:
                cover_data = audio["covr"]
                if cover_data:
                    return bytes(cover_data[0])

            # FLAC
            if isinstance(audio, FLAC) and audio.pictures:
                return audio.pictures[0].data

        except Exception:
            pass

        return None

    @staticmethod
    def _filename_stem(file_path: str) -> str:
        return os.path.splitext(os.path.basename(file_path))[0]
