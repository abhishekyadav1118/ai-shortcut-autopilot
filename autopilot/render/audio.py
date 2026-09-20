"""Audio handling, music selection, ducking, and loudness normalization."""

import random
from pathlib import Path


def select_background_music(music_dir: Path | str = "assets/music") -> Path | None:
    """
    Select a random royalty-free background music track if available.
    Returns None if no music files exist (making music completely optional).
    """
    p = Path(music_dir)
    if not p.exists() or not p.is_dir():
        return None

    music_files = list(p.glob("*.mp3")) + list(p.glob("*.wav")) + list(p.glob("*.ogg"))
    if not music_files:
        return None

    return random.choice(music_files)
