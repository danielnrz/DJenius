"""File fingerprinting and SQLite cache for analysis results."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

import xxhash

from djenius.core.models import TrackMetadata, TrackAnalysis, TrackProfile, SemanticProfile, LyricsProfile

logger = logging.getLogger(__name__)

DB_NAME = "djenius_cache.db"

# Bump this to invalidate all cached analysis results.
ANALYSIS_VERSION = 4
LYRICS_ANALYSIS_VERSION = "1"

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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_tracks (
                file_hash TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                semantic_json TEXT NOT NULL,
                semantic_version TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS lyrics_tracks (
                file_hash TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                lyrics_json TEXT NOT NULL,
                lyrics_version TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
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
        semantic = self._get_semantic_by_hash(file_hash)
        if semantic is not None:
            profile.semantic = semantic
        lyrics = self._get_lyrics_by_hash(file_hash)
        if lyrics is not None:
            profile.lyrics = lyrics
        return profile

    def _get_semantic_by_hash(self, file_hash: str) -> Optional[SemanticProfile]:
        cursor = self._conn.execute(
            "SELECT semantic_json FROM semantic_tracks WHERE file_hash = ?",
            (file_hash,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        try:
            return SemanticProfile.from_dict(json.loads(row[0]))
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring invalid semantic cache entry for %s", file_hash)
            return None

    def get_semantic(self, filepath: str, model_name: str, semantic_version: str) -> Optional[SemanticProfile]:
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            return None
        profile = self._get_semantic_by_hash(file_hash)
        if profile is None or profile.model_name != model_name or profile.model_version != semantic_version:
            return None
        if profile.source_file_hash and profile.source_file_hash != file_hash:
            return None
        return profile

    def put_semantic(self, filepath: str, profile: SemanticProfile) -> None:
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            raise FileNotFoundError(filepath)
        profile.source_file_hash = file_hash
        now = time.time()
        self._conn.execute(
            """INSERT OR REPLACE INTO semantic_tracks
            (file_hash, filepath, semantic_json, semantic_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (file_hash, filepath, json.dumps(profile.to_dict()), profile.model_version, now, now),
        )
        self._conn.commit()

    def _get_lyrics_by_hash(self, file_hash: str) -> Optional[LyricsProfile]:
        cursor = self._conn.execute(
            "SELECT lyrics_json FROM lyrics_tracks WHERE file_hash = ?",
            (file_hash,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        try:
            return LyricsProfile.from_dict(json.loads(row[0]))
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring invalid lyrics cache entry for %s", file_hash)
            return None

    def get_lyrics(self, filepath: str, lyrics_version: str = LYRICS_ANALYSIS_VERSION, transcription_model: str = "") -> Optional[LyricsProfile]:
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            return None
        profile = self._get_lyrics_by_hash(file_hash)
        if profile is None or profile.analysis_version != lyrics_version:
            return None
        if transcription_model and profile.transcription_model and profile.transcription_model != transcription_model:
            return None
        if profile.source_file_hash and profile.source_file_hash != file_hash:
            return None
        return profile

    def put_lyrics(self, filepath: str, profile: LyricsProfile) -> None:
        file_hash = compute_file_hash(filepath)
        if not file_hash:
            raise FileNotFoundError(filepath)
        profile.source_file_hash = file_hash
        now = time.time()
        self._conn.execute(
            """INSERT OR REPLACE INTO lyrics_tracks
            (file_hash, filepath, lyrics_json, lyrics_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (file_hash, filepath, json.dumps(profile.to_dict()), profile.analysis_version, now, now),
        )
        self._conn.commit()

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
                semantic=self._get_semantic_by_hash(row[0]),
                lyrics=self._get_lyrics_by_hash(row[0]),
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
        self._conn.execute("DELETE FROM semantic_tracks WHERE file_hash = ?", (file_hash,))
        self._conn.execute("DELETE FROM lyrics_tracks WHERE file_hash = ?", (file_hash,))
        self._conn.commit()
        return cursor.rowcount > 0

    def clear(self):
        """Clear all cached data."""
        self._conn.execute("DELETE FROM tracks")
        self._conn.execute("DELETE FROM semantic_tracks")
        self._conn.execute("DELETE FROM lyrics_tracks")
        self._conn.commit()

    def count(self) -> int:
        """Number of cached tracks (current analysis version)."""
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE analysis_version = ?",
            (ANALYSIS_VERSION,),
        )
        return cursor.fetchone()[0]
