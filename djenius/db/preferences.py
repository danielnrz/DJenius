"""SQLite-backed user preference profile for DJenius.

Stores implicit and explicit feedback: transition ratings, track likes
and dislikes, preferred BPM ranges, and energy preferences. The scorer
reads this to bias compatibility scores toward the user's taste.

Schema is versioned so future migrations can invalidate stale data.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from djenius.core.models import TransitionType

logger = logging.getLogger(__name__)

DB_NAME = "djenius_preferences.db"
SCHEMA_VERSION = 1


class PreferenceProfile:
    """SQLite-backed user preference store.

    Each PreferenceProfile lives in its own SQLite database. The default
    path is ``<cwd>/djenius_preferences.db``.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.cwd() / DB_NAME)
        self.db_path = db_path
        self._conn = None
        self._init_db()

    # ---- lifecycle ----

    def _init_db(self):
        import sqlite3

        self._conn = sqlite3.connect(self.db_path, timeout=10.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        import sqlite3

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transition_ratings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source_track_id TEXT NOT NULL,
                target_track_id TEXT NOT NULL,
                transition_type TEXT NOT NULL,
                rating          REAL NOT NULL,   -- -1.0 (bad) to 1.0 (great)
                created_at      REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trans_src ON transition_ratings(source_track_id);
            CREATE INDEX IF NOT EXISTS idx_trans_tgt ON transition_ratings(target_track_id);

            CREATE TABLE IF NOT EXISTS track_feedback (
                track_id   TEXT PRIMARY KEY,
                liked      INTEGER NOT NULL DEFAULT 0,  -- 1 = liked, -1 = disliked
                play_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bpm_preference (
                id        INTEGER PRIMARY KEY CHECK (id = 1),
                preferred_min REAL,
                preferred_max REAL,
                updated_at    REAL
            );

            CREATE TABLE IF NOT EXISTS energy_preference (
                id        INTEGER PRIMARY KEY CHECK (id = 1),
                preferred_min REAL,
                preferred_max REAL,
                updated_at    REAL
            );
        """)

        # Schema version tracking
        cur = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        )
        row = cur.fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- transition ratings ----

    def rate_transition(
        self,
        source_track_id: str,
        target_track_id: str,
        transition_type: str,
        rating: float,
    ):
        """Record a rating for a specific transition.

        rating: -1.0 (bad) to 1.0 (great).
        """
        rating = max(-1.0, min(1.0, rating))
        now = time.time()
        self._conn.execute(
            """INSERT INTO transition_ratings
               (source_track_id, target_track_id, transition_type, rating, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (source_track_id, target_track_id, transition_type, rating, now),
        )
        self._conn.commit()

    def get_transition_avg(
        self,
        source_track_id: str,
        target_track_id: str,
        transition_type: Optional[str] = None,
    ) -> Optional[float]:
        """Get the average rating for a transition pair.

        If transition_type is given, filters to that type only.
        Returns None if no ratings exist.
        """
        if transition_type:
            cur = self._conn.execute(
                """SELECT AVG(rating), COUNT(*) FROM transition_ratings
                   WHERE source_track_id = ? AND target_track_id = ?
                   AND transition_type = ?""",
                (source_track_id, target_track_id, transition_type),
            )
        else:
            cur = self._conn.execute(
                """SELECT AVG(rating), COUNT(*) FROM transition_ratings
                   WHERE source_track_id = ? AND target_track_id = ?""",
                (source_track_id, target_track_id),
            )
        row = cur.fetchone()
        if row is None or row[1] == 0:
            return None
        return row[0]

    def get_preferred_transition_types(
        self, min_samples: int = 3
    ) -> dict[str, float]:
        """Return transition types ranked by average rating.

        Only includes types with at least ``min_samples`` ratings.
        Returns dict mapping type name -> average rating.
        """
        cur = self._conn.execute(
            """SELECT transition_type, AVG(rating), COUNT(*)
               FROM transition_ratings
               GROUP BY transition_type
               HAVING COUNT(*) >= ?
               ORDER BY AVG(rating) DESC""",
            (min_samples,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}

    # ---- track feedback ----

    def like_track(self, track_id: str):
        """Mark a track as liked."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO track_feedback (track_id, liked, play_count, created_at, updated_at)
               VALUES (?, 1, 1, ?, ?)
               ON CONFLICT(track_id) DO UPDATE SET
                   liked = 1,
                   play_count = play_count + 1,
                   updated_at = ?""",
            (track_id, now, now, now),
        )
        self._conn.commit()

    def dislike_track(self, track_id: str):
        """Mark a track as disliked."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO track_feedback (track_id, liked, play_count, created_at, updated_at)
               VALUES (?, -1, 1, ?, ?)
               ON CONFLICT(track_id) DO UPDATE SET
                   liked = -1,
                   play_count = play_count + 1,
                   updated_at = ?""",
            (track_id, now, now, now),
        )
        self._conn.commit()

    def increment_play_count(self, track_id: str):
        """Increment play count for a track (implicit feedback)."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO track_feedback (track_id, liked, play_count, created_at, updated_at)
               VALUES (?, 0, 1, ?, ?)
               ON CONFLICT(track_id) DO UPDATE SET
                   play_count = play_count + 1,
                   updated_at = ?""",
            (track_id, now, now, now),
        )
        self._conn.commit()

    def get_track_feedback(self, track_id: str) -> Optional[dict]:
        """Get feedback for a specific track.

        Returns dict with 'liked' (-1, 0, 1) and 'play_count', or None.
        """
        cur = self._conn.execute(
            "SELECT liked, play_count FROM track_feedback WHERE track_id = ?",
            (track_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"liked": row[0], "play_count": row[1]}

    def get_liked_tracks(self) -> list[str]:
        """Return track IDs that are marked as liked."""
        cur = self._conn.execute(
            "SELECT track_id FROM track_feedback WHERE liked = 1"
        )
        return [row[0] for row in cur.fetchall()]

    def get_disliked_tracks(self) -> list[str]:
        """Return track IDs that are marked as disliked."""
        cur = self._conn.execute(
            "SELECT track_id FROM track_feedback WHERE liked = -1"
        )
        return [row[0] for row in cur.fetchall()]

    def get_most_played(self, limit: int = 10) -> list[tuple[str, int]]:
        """Return the most played tracks as (track_id, play_count)."""
        cur = self._conn.execute(
            """SELECT track_id, play_count FROM track_feedback
               ORDER BY play_count DESC LIMIT ?""",
            (limit,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]

    # ---- BPM preference ----

    def set_bpm_preference(self, preferred_min: float, preferred_max: float):
        """Store preferred BPM range."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO bpm_preference (id, preferred_min, preferred_max, updated_at)
               VALUES (1, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   preferred_min = excluded.preferred_min,
                   preferred_max = excluded.preferred_max,
                   updated_at = excluded.updated_at""",
            (preferred_min, preferred_max, now),
        )
        self._conn.commit()

    def get_bpm_preference(self) -> Optional[tuple[float, float]]:
        """Get preferred BPM range. Returns None if not set."""
        cur = self._conn.execute(
            "SELECT preferred_min, preferred_max FROM bpm_preference WHERE id = 1"
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return (row[0], row[1])

    # ---- energy preference ----

    def set_energy_preference(self, preferred_min: float, preferred_max: float):
        """Store preferred energy range."""
        now = time.time()
        self._conn.execute(
            """INSERT INTO energy_preference (id, preferred_min, preferred_max, updated_at)
               VALUES (1, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   preferred_min = excluded.preferred_min,
                   preferred_max = excluded.preferred_max,
                   updated_at = excluded.updated_at""",
            (preferred_min, preferred_max, now),
        )
        self._conn.commit()

    def get_energy_preference(self) -> Optional[tuple[float, float]]:
        """Get preferred energy range. Returns None if not set."""
        cur = self._conn.execute(
            "SELECT preferred_min, preferred_max FROM energy_preference WHERE id = 1"
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return (row[0], row[1])

    # ---- aggregate helpers ----

    def get_scoring_bonuses(self, min_samples: int = 3) -> dict:
        """Compute scoring bonuses from accumulated feedback.

        Returns a dict with:
        - preferred_bpm_range: tuple or None
        - preferred_energy_range: tuple or None
        - liked_tracks: set of track IDs
        - disliked_tracks: set of track IDs
        - preferred_transition_types: dict of type -> avg rating
        - disliked_transition_types: dict of type -> avg rating
        """
        liked = set(self.get_liked_tracks())
        disliked = set(self.get_disliked_tracks())
        bpm_pref = self.get_bpm_preference()
        energy_pref = self.get_energy_preference()
        trans_prefs = self.get_preferred_transition_types(min_samples)

        # Split into liked vs disliked transition types
        preferred = {k: v for k, v in trans_prefs.items() if v > 0}
        disliked_trans = {k: v for k, v in trans_prefs.items() if v < 0}

        return {
            "preferred_bpm_range": bpm_pref,
            "preferred_energy_range": energy_pref,
            "liked_tracks": liked,
            "disliked_tracks": disliked,
            "preferred_transition_types": preferred,
            "disliked_transition_types": disliked_trans,
        }

    def summary(self) -> str:
        """Return a human-readable summary of stored preferences."""
        lines = ["Preference Profile:"]

        liked = self.get_liked_tracks()
        disliked = self.get_disliked_tracks()
        lines.append(f"  Liked tracks: {len(liked)}")
        lines.append(f"  Disliked tracks: {len(disliked)}")

        bpm = self.get_bpm_preference()
        if bpm:
            lines.append(f"  BPM preference: {bpm[0]:.0f} - {bpm[1]:.0f}")
        else:
            lines.append("  BPM preference: not set")

        energy = self.get_energy_preference()
        if energy:
            lines.append(f"  Energy preference: {energy[0]:.2f} - {energy[1]:.2f}")
        else:
            lines.append("  Energy preference: not set")

        trans = self.get_preferred_transition_types()
        if trans:
            lines.append("  Transition preferences:")
            for ttype, rating in trans.items():
                label = "liked" if rating > 0 else "disliked"
                lines.append(f"    {ttype}: {label} (avg {rating:.2f})")

        most_played = self.get_most_played(5)
        if most_played:
            lines.append("  Most played:")
            for tid, count in most_played:
                lines.append(f"    {tid}: {count} plays")

        return "\n".join(lines)
