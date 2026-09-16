"""The private DJ-reference discovery pass is shadow-only and conservative."""

import json
from pathlib import Path

import numpy as np
import pytest

from djenius.research import reference_regions as regions


def test_structured_change_is_only_an_unverified_candidate() -> None:
    rows = []
    for index in range(80):
        rows.append({
            "log_rms": -24.0 if index < 40 else -12.0,
            "low_fraction": 0.14 if index < 40 else 0.34,
            "high_fraction": 0.20,
            "centroid_hz": 1800.0,
            "transient_activity": 0.02 if index < 40 else 0.08,
            "spectral_flatness": 0.1,
        })

    found = regions.nominate_regions(rows, np.zeros(3200), 160.0)

    assert found
    assert all(item["classification"] == "CANDIDATE_REGION_NOT_CONFIRMED_DJ_TRANSITION"
               for item in found)
    assert all(0 <= item["review_range_sec"][0] < item["review_range_sec"][1] <= 160
               for item in found)
    assert any("log_rms" in item["independent_changed_axes"] for item in found)


def test_single_axis_change_is_not_called_a_reference_region() -> None:
    rows = [
        {"log_rms": -25.0 if index < 40 else -10.0,
         "low_fraction": 0.2, "high_fraction": 0.2,
         "centroid_hz": 1800.0, "transient_activity": 0.02,
         "spectral_flatness": 0.1}
        for index in range(80)
    ]

    assert regions.nominate_regions(rows, np.zeros(3200), 160.0) == []


def test_reference_discovery_requires_explicit_fromdj_and_private_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "fromDJ"
    root.mkdir()
    reference = root / "reference.wav"
    reference.touch()
    monkeypatch.setattr(regions, "probe_duration", lambda path: 120.0)
    monkeypatch.setattr(regions, "decode_coarse_features",
                        lambda path: ([], np.asarray([], dtype=float)))

    output = tmp_path / "derived.json"
    first = regions.discover_directory(root, output)
    first_bytes = output.read_bytes()
    second = regions.discover_directory(root, output)

    assert first == second
    assert output.read_bytes() == first_bytes
    assert json.loads(first_bytes)["all_regions_unverified"] is True
    assert json.loads(first_bytes)["complete"] is True
    assert first["rows"][0]["candidate_regions"] == []
    with pytest.raises(ValueError, match="fromDJ"):
        regions.discover_directory(tmp_path, output)
    with pytest.raises(ValueError, match="outside the repository"):
        regions.discover_directory(root, Path(regions.__file__).resolve().parents[2] / "leak.json")
