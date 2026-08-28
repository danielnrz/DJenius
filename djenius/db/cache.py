"""File fingerprinting and SQLite cache for analysis results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

import xxhash

from djenius.core.models import TrackMetadata, TrackAnalysis, TrackProfile


DB_NAME = "djenius_cache.db"


def compute_file_hash(filepath: str, sample_bytes: int = 1024 * 1024) -> str:
    """Compute a fast fingerprint of a file using xxhash.

    Reads the first `sample_bytes` plus the file size for a quick fingerprint.
    This is fast and good enough to detect if a file has been re-saved or replaced.
    """
    path = Path(filepath)
    if not path.exists():
        return ""

    file_size = path.stat().st_size

    h = xxhash.xxh128()
    h.update(str(file_size).encode())

    with open(path, "rb") as f:
        data = f.read(sample_bytes)
        h.update(data)

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
        """Create tables if they don't exist."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                file_hash TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_filepath ON tracks(filepath)
        """)
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
            "SELECT metadata_json, analysis_json FROM tracks WHERE file_hash = ?",
            (file_hash,)
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
            (file_hash, filepath, metadata_json, analysis_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            profile.id,
            profile.metadata.filepath,
            meta_json,
            analysis_json,
            now,
            now,
        ))
        self._conn.commit()

    def has(self, filepath: str) -> bool:
        """Check if a file is already cached."""
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            return False

        cursor = self._conn.execute(
            "SELECT 1 FROM tracks WHERE file_hash = ?",
            (file_hash,)
        )
        return cursor.fetchone() is not None

    def get_all_profiles(self) -> list[TrackProfile]:
        """Get all cached profiles."""
        cursor = self._conn.execute(
            "SELECT file_hash, metadata_json, analysis_json FROM tracks"
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
        """Number of cached tracks."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM tracks")
        return cursor.fetchone()[0]
