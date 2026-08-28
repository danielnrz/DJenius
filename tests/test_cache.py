"""Tests for file fingerprinting and SQLite cache."""

from __future__ import annotations

import sqlite3
import pytest
from pathlib import Path

from djenius.db.cache import compute_file_hash, AnalysisCache, ANALYSIS_VERSION
from djenius.core.models import TrackMetadata, TrackAnalysis, TrackProfile


class TestComputeFileHash:
    def test_deterministic(self, tmp_path):
        p = tmp_path / "test.bin"
        p.write_bytes(b"hello world " * 100)
        h1 = compute_file_hash(str(p))
        h2 = compute_file_hash(str(p))
        assert h1 == h2
        assert len(h1) > 0

    def test_different_files_different_hashes(self, tmp_path):
        p1 = tmp_path / "a.bin"
        p2 = tmp_path / "b.bin"
        p1.write_bytes(b"content_a")
        p2.write_bytes(b"content_b")
        assert compute_file_hash(str(p1)) != compute_file_hash(str(p2))

    def test_nonexistent_file_returns_empty(self):
        assert compute_file_hash("/nonexistent/file/path.xyz") == ""

    def test_change_at_end_of_file_detected(self, tmp_path):
        """Full-file hashing must detect changes at end of file (ID3 tags, etc.)."""
        p = tmp_path / "track.bin"
        # Write a file with data at the beginning and end
        data = b"audio_data" * 1000 + b"METADATA_PADDING"
        p.write_bytes(data)
        h1 = compute_file_hash(str(p))

        # Append bytes (simulating ID3 tag addition)
        with open(p, "ab") as f:
            f.write(b"EXTRA_TAG_DATA")
        h2 = compute_file_hash(str(p))

        assert h1 != h2, "Hash must change when end of file is modified"

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.bin"
        p.write_bytes(b"")
        h = compute_file_hash(str(p))
        assert len(h) > 0  # Should still produce a hash


class TestAnalysisCache:
    @pytest.fixture
    def cache(self, tmp_path):
        """Create a fresh cache in a temp directory."""
        db_path = str(tmp_path / "test_cache.db")
        c = AnalysisCache(db_path)
        yield c
        c.close()

    def _make_profile(self, filepath: str, title: str = "Test") -> TrackProfile:
        from djenius.db.cache import compute_file_hash
        file_hash = compute_file_hash(filepath)
        return TrackProfile(
            id=file_hash,
            metadata=TrackMetadata(filepath=filepath, title=title),
            analysis=TrackAnalysis(bpm=120.0, camelot="8B"),
        )

    def test_put_and_get(self, cache, tmp_path):
        audio_path = str(tmp_path / "track.wav")
        Path(audio_path).write_bytes(b"fake_audio_data")
        profile = self._make_profile(audio_path, "My Track")
        cache.put(profile)

        retrieved = cache.get(audio_path)
        assert retrieved is not None
        assert retrieved.title == "My Track"
        assert retrieved.bpm == 120.0

    def test_get_uncached_returns_none(self, cache, tmp_path):
        path = str(tmp_path / "nonexistent.wav")
        Path(path).write_bytes(b"data")
        assert cache.get(path) is None

    def test_has(self, cache, tmp_path):
        path = str(tmp_path / "track.wav")
        Path(path).write_bytes(b"audio")
        assert not cache.has(path)
        cache.put(self._make_profile(path))
        assert cache.has(path)

    def test_remove(self, cache, tmp_path):
        path = str(tmp_path / "track.wav")
        Path(path).write_bytes(b"audio")
        cache.put(self._make_profile(path))
        assert cache.remove(path)
        assert not cache.has(path)
        assert not cache.remove(path)  # Already removed

    def test_clear(self, cache, tmp_path):
        for i in range(3):
            p = str(tmp_path / f"t{i}.wav")
            Path(p).write_bytes(f"unique_content_{i}".encode())
            cache.put(self._make_profile(p, f"Track {i}"))
        assert cache.count() == 3
        cache.clear()
        assert cache.count() == 0

    def test_count(self, cache, tmp_path):
        assert cache.count() == 0
        p = str(tmp_path / "a.wav")
        Path(p).write_bytes(b"audio")
        cache.put(self._make_profile(p))
        assert cache.count() == 1

    def test_get_all_profiles(self, cache, tmp_path):
        for i in range(2):
            p = str(tmp_path / f"t{i}.wav")
            Path(p).write_bytes(f"unique_content_{i}".encode())
            cache.put(self._make_profile(p, f"Track {i}"))
        profiles = cache.get_all_profiles()
        assert len(profiles) == 2

    def test_analysis_version_invalidation(self, cache, tmp_path):
        """Cache entries with old analysis_version are not returned."""
        path = str(tmp_path / "track.wav")
        Path(path).write_bytes(b"audio")
        cache.put(self._make_profile(path))

        # Directly insert a row with analysis_version = 0 (old)
        cache._conn.execute(
            "INSERT OR REPLACE INTO tracks "
            "(file_hash, filepath, metadata_json, analysis_json, analysis_version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("old_hash", path, "{}", "{}", 0, 0.0, 0.0),
        )
        cache._conn.commit()

        # The current version entry should still be found
        assert cache.has(path)

        # Count only current version
        assert cache.count() == 1  # Only the current-version entry

    def test_put_replaces_existing(self, cache, tmp_path):
        path = str(tmp_path / "track.wav")
        Path(path).write_bytes(b"audio")
        cache.put(self._make_profile(path, "Version 1"))
        cache.put(self._make_profile(path, "Version 2"))
        retrieved = cache.get(path)
        assert retrieved.title == "Version 2"

    def test_db_handles_old_schema_gracefully(self, tmp_path):
        """An existing DB without analysis_version column should be migrated."""
        db_path = str(tmp_path / "old_schema.db")
        # Create DB with old schema
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE tracks (
                file_hash TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        # Opening with AnalysisCache should add analysis_version column
        cache = AnalysisCache(db_path)
        # Should not raise
        assert cache.count() == 0
        cache.close()
