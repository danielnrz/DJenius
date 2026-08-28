"""Musical key to Camelot wheel conversion and key compatibility scoring."""

from __future__ import annotations


# Standard musical keys and their Camelot equivalents.
# The Camelot wheel has 12 major (B) and 12 minor (A) positions.
KEY_TO_CAMELOT: dict[str, str] = {
    "C Major": "8B",
    "G Major": "9B",
    "D Major": "10B",
    "A Major": "11B",
    "E Major": "12B",
    "B Major": "1B",
    "F# Major": "2B",
    "Db Major": "3B",
    "Ab Major": "4B",
    "Eb Major": "5B",
    "Bb Major": "6B",
    "F Major": "7B",
    "A Minor": "8A",
    "E Minor": "9A",
    "B Minor": "10A",
    "F# Minor": "11A",
    "C# Minor": "12A",
    "G# Minor": "1A",
    "Eb Minor": "2A",
    "Bb Minor": "3A",
    "F Minor": "4A",
    "C Minor": "5A",
    "G Minor": "6A",
    "D Minor": "7A",
}

CAMELOT_TO_KEY: dict[str, str] = {v: k for k, v in KEY_TO_CAMELOT.items()}

# Musical key notes in order (for chroma-based detection)
KEY_NAMES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
]

MAJOR_SCALE_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

# Krumhansl-Schmuckler key profiles for correlation
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def key_to_camelot(key_name: str) -> str:
    """Convert a standard key name to Camelot notation.

    Args:
        key_name: e.g. "C Minor", "A Major", "F# Minor"

    Returns:
        Camelot code like "5A", "8B", etc.
    """
    if key_name in KEY_TO_CAMELOT:
        return KEY_TO_CAMELOT[key_name]
    return ""


def camelot_to_key(camelot: str) -> str:
    """Convert Camelot notation to a standard key name."""
    return CAMELOT_TO_KEY.get(camelot, "")


def parse_camelot(camelot: str) -> tuple[int, str]:
    """Parse a Camelot code into (hour, mode).

    Args:
        camelot: e.g. "5A" -> (5, "A"), "8B" -> (8, "B")

    Returns:
        (hour, mode) where hour is 1-12 and mode is "A" (minor) or "B" (major).
    """
    if len(camelot) < 2:
        return (0, "")
    hour = int(camelot[:-1])
    mode = camelot[-1]
    return (hour, mode)


def camelot_distance(c1: str, c2: str) -> int:
    """Calculate the distance between two Camelot keys on the wheel.

    Returns a distance from 0 (identical) to 6 (maximum opposition).
    Accounts for both hour distance and mode relationship.
    """
    h1, m1 = parse_camelot(c1)
    h2, m2 = parse_camelot(c2)

    if h1 == 0 or h2 == 0:
        return 6  # Unknown keys are maximally distant

    # Hour distance on the wheel (wraps around)
    hour_diff = min(abs(h1 - h2), 12 - abs(h1 - h2))

    if hour_diff == 0 and m1 == m2:
        return 0  # Same key
    elif hour_diff == 0:
        return 1  # Same hour, different mode (relative major/minor)
    elif hour_diff == 1 and m1 == m2:
        return 1  # Adjacent on wheel, same mode
    elif hour_diff == 1:
        return 2  # Adjacent, different mode
    elif hour_diff == 2 and m1 == m2:
        return 3
    elif hour_diff <= 2:
        return 3
    elif hour_diff <= 3:
        return 4
    else:
        return min(hour_diff, 6)


def score_key_compatibility(camelot1: str, camelot2: str) -> float:
    """Score harmonic compatibility between two tracks.

    Returns a score from 0.0 (strong clash) to 1.0 (identical key).
    """
    dist = camelot_distance(camelot1, camelot2)

    # Map distance to score
    scores = {
        0: 1.0,    # Same key
        1: 0.9,    # Adjacent or relative major/minor
        2: 0.7,    # Compatible but not ideal
        3: 0.5,    # Neutral
        4: 0.3,    # Somewhat clashing
        5: 0.15,   # Clashing
        6: 0.05,   # Strong clash
    }
    return scores.get(dist, 0.05)


def detect_key_from_chroma(chroma: list[float]) -> tuple[str, str, float]:
    """Detect musical key from a 12-bin chroma vector using correlation.

    Args:
        chroma: 12-element list of chroma energies (C, C#, D, ..., B)

    Returns:
        (key_name, camelot, confidence)
    """
    import numpy as np

    chroma_arr = np.array(chroma, dtype=np.float64)
    if chroma_arr.sum() < 1e-10:
        return ("", "", 0.0)

    # Normalize
    chroma_arr = chroma_arr / chroma_arr.sum()

    best_key = ""
    best_camelot = ""
    best_corr = -1.0

    major_arr = np.array(MAJOR_PROFILE, dtype=np.float64)
    minor_arr = np.array(MINOR_PROFILE, dtype=np.float64)
    major_arr = major_arr / major_arr.sum()
    minor_arr = minor_arr / minor_arr.sum()

    for i in range(12):
        # Rotate chroma to test each root note
        rotated = np.roll(chroma_arr, -i)

        # Pearson correlation
        corr_major = np.corrcoef(rotated, major_arr)[0, 1]
        corr_minor = np.corrcoef(rotated, minor_arr)[0, 1]

        if corr_major > best_corr:
            best_corr = corr_major
            key_name = f"{KEY_NAMES[i]} Major"
            best_key = key_name
            best_camelot = KEY_TO_CAMELOT.get(key_name, "")

        if corr_minor > best_corr:
            best_corr = corr_minor
            key_name = f"{KEY_NAMES[i]} Minor"
            best_key = key_name
            best_camelot = KEY_TO_CAMELOT.get(key_name, "")

    # Normalize confidence to 0-1 range
    confidence = max(0.0, min(1.0, (best_corr + 0.5) / 1.5))

    return (best_key, best_camelot, confidence)
