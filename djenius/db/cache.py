"""File fingerprinting and SQLite cache for analysis results."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import xxhash

from djenius.core.models import TrackMetadata, TrackAnalysis, TrackProfile

logger = logging.getLogger(__name__)

DB_NAME = "djenius_cache.db"

# Bump this to invalidate all cached analysis results.
ANALYSIS_VERSION = 3

# Chunk size for reading files during hashing (64 KB).
_HASH_CHUNK_SIZE = 64 * 1024


def compute_file_hash(filepath: str) -> str:
    """Compute a fingerprint of an entire file using xxhash.

    Reads the file in chunks to avoid loading it entirely into memory.
    Returns a hex digest string, or empty string if the file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        return ""

    h = xxhash.xxh128()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


class AnalysisCache:
    """SQLite-backed cache for track analysis results."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.cwd() / DB_NAME)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist, and migrate if needed."""
        self._conn = sqlite3.connect(self.db_path, timeout=10.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                file_hash TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                analysis_version INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_filepath ON tracks(filepath)
        """)
        # Migrate existing databases that lack the analysis_version column.
        try:
            self._conn.execute(
                "ALTER TABLE tracks ADD COLUMN analysis_version INTEGER NOT NULL DEFAULT 0"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists.
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def get(self, filepath: str) -> Optional[TrackProfile]:
        """Retrieve a cached analysis for a file."""
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            return None

        cursor = self._conn.execute(
            "SELECT metadata_json, analysis_json FROM tracks "
            "WHERE file_hash = ? AND analysis_version = ?",
            (file_hash, ANALYSIS_VERSION),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        metadata = TrackMetadata(**json.loads(row[0]))
        analysis = TrackAnalysis.from_dict(json.loads(row[1]))

        profile = TrackProfile(
            id=file_hash,
            metadata=metadata,
            analysis=analysis,
        )
        return profile

    def put(self, profile: TrackProfile):
        """Store an analysis result in the cache."""
        now = time.time()
        meta_json = json.dumps(profile.metadata.__dict__)
        analysis_json = json.dumps(profile.analysis.to_dict())

        self._conn.execute("""
            INSERT OR REPLACE INTO tracks
            (file_hash, filepath, metadata_json, analysis_json, analysis_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.id,
            profile.metadata.filepath,
            meta_json,
            analysis_json,
            ANALYSIS_VERSION,
            now,
            now,
        ))
        self._conn.commit()

    def has(self, filepath: str) -> bool:
        """Check if a file is already cached with the current analysis version."""
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            return False

        cursor = self._conn.execute(
            "SELECT 1 FROM tracks WHERE file_hash = ? AND analysis_version = ?",
            (file_hash, ANALYSIS_VERSION),
        )
        return cursor.fetchone() is not None

    def get_all_profiles(self) -> list[TrackProfile]:
        """Get all cached profiles for the current analysis version."""
        cursor = self._conn.execute(
            "SELECT file_hash, metadata_json, analysis_json FROM tracks "
            "WHERE analysis_version = ?",
            (ANALYSIS_VERSION,),
        )
        profiles = []
        for row in cursor.fetchall():
            metadata = TrackMetadata(**json.loads(row[1]))
            analysis = TrackAnalysis.from_dict(json.loads(row[2]))
            profiles.append(TrackProfile(
                id=row[0],
                metadata=metadata,
                analysis=analysis,
            ))
        return profiles

    def remove(self, filepath: str) -> bool:
        """Remove a cached entry."""
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            return False
        cursor = self._conn.execute(
            "DELETE FROM tracks WHERE file_hash = ?", (file_hash,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def clear(self):
        """Clear all cached data."""
        self._conn.execute("DELETE FROM tracks")
        self._conn.commit()

    def count(self) -> int:
        """Number of cached tracks (current analysis version)."""
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE analysis_version = ?",
            (ANALYSIS_VERSION,),
        )
        return cursor.fetchone()[0]
