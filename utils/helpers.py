"""
General-purpose helper functions.

All functions here are pure (no side effects, no Qt dependency) so they
can be unit-tested without a QApplication instance.
"""


def ms_to_mmss(milliseconds: int) -> str:
    """
    Convert a duration in milliseconds to a "MM:SS" string.

    >>> ms_to_mmss(0)
    '00:00'
    >>> ms_to_mmss(3661000)
    '61:01'
    """
    total_seconds = max(0, milliseconds) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def bytes_to_human(num_bytes: int) -> str:
    """Return a human-readable file size string (e.g. '4.2 MB')."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def clamp(value: float, low: float, high: float) -> float:
    """Return *value* clamped to [low, high]."""
    return max(low, min(high, value))
