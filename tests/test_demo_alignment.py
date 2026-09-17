"""Focused safety/evidence tests for shadow DJ-original alignment."""

from pathlib import Path

import numpy as np
import pytest

from djenius.research.demo_alignment import (
    RATE,
    chroma24_from_samples,
    classify_alignment,
    nearest_ordered_sketches,
    sketches,
    verify_segment,
)
from djenius.research import demo_alignment


def test_ordered_chroma_alignment_needs_two_coherent_regions() -> None:
    rng = np.random.default_rng(12)
    # Each second has a distinct two-note combination; similarity needs its
    # temporal order, not merely the same average harmonic territory.
    seconds = 90
    times = np.arange(RATE, dtype=np.float32) / RATE
    notes = rng.integers(0, 12, size=(seconds, 2))
    audio = np.concatenate([
        .15 * np.sin(2 * np.pi * (220 * 2 ** (int(a) / 12)) * times)
        + .11 * np.sin(2 * np.pi * (330 * 2 ** (int(b) / 12)) * times)
        for a, b in notes
    ]).astype(np.float32)
    chroma = chroma24_from_samples(audio)
    starts, vectors = sketches(chroma, 12)
    assert len(starts) and vectors.shape[1] == 144
    first = verify_segment(chroma, chroma, 0, 0)
    second = verify_segment(chroma, chroma, 36, 36)
    assert first["mean_frame_cosine"] > .95
    assert second["mean_frame_cosine"] > .95
    assert classify_alignment([first])["status"] == "SINGLE_STRONG_REGION_UNCONFIRMED"
    assert classify_alignment([first, second])["status"] == "HIGH_CONFIDENCE_AUDIO_ALIGNMENT"
    wrong = verify_segment(chroma, chroma[::-1], 0, 0)
    assert wrong["mean_frame_cosine"] < first["mean_frame_cosine"] - .15


def test_alignment_rejects_incoherent_pair_of_strong_hits() -> None:
    hits = [
        {"source_start_sec": 0, "reference_start_sec": 10,
         "tempo_ratio": 1.0, "mean_frame_cosine": .95,
         "minimum_six_second_block_cosine": .9},
        {"source_start_sec": 40, "reference_start_sec": 110,
         "tempo_ratio": 1.0, "mean_frame_cosine": .95,
         "minimum_six_second_block_cosine": .9},
    ]
    assert classify_alignment(hits)["status"] == "SINGLE_STRONG_REGION_UNCONFIRMED"


def test_nearest_ordered_sketches_uses_existing_numpy_only() -> None:
    references = np.eye(3, dtype=np.float32)
    queries = np.asarray([[1, 0, 0], [0, 0, 1]], dtype=np.float32)
    distances, indices = nearest_ordered_sketches(queries, references, k=2)
    assert indices[:, 0].tolist() == [0, 2]
    assert np.allclose(distances[:, 0], 0)


def test_alignment_cli_requires_reference_root_and_private_output(tmp_path, monkeypatch) -> None:
    reference = tmp_path / "not_reference"
    reference.mkdir()
    monkeypatch.setattr("sys.argv", ["demo_alignment", "--normal-root", str(tmp_path),
                                    "--reference-root", str(reference),
                                    "--output", str(tmp_path / "out.json")])
    with pytest.raises(ValueError, match="fromDJ"):
        demo_alignment.main()
    reference = tmp_path / "fromDJ"
    reference.mkdir()
    in_repo = Path(__file__).resolve().parents[1] / "should_not_write_private_alignment.json"
    monkeypatch.setattr("sys.argv", ["demo_alignment", "--normal-root", str(tmp_path),
                                    "--reference-root", str(reference),
                                    "--output", str(in_repo)])
    with pytest.raises(ValueError, match="outside the repository"):
        demo_alignment.main()
