"""Tests for Camelot key detection and compatibility scoring."""

from __future__ import annotations

import pytest

from djenius.utils.camelot import (
    key_to_camelot,
    camelot_to_key,
    parse_camelot,
    camelot_distance,
    score_key_compatibility,
    detect_key_from_chroma,
    KEY_TO_CAMELOT,
)


class TestKeyToCamelot:
    def test_known_keys(self):
        assert key_to_camelot("C Major") == "8B"
        assert key_to_camelot("A Minor") == "8A"
        assert key_to_camelot("F# Minor") == "11A"
        assert key_to_camelot("Eb Major") == "5B"

    def test_unknown_key_returns_empty(self):
        assert key_to_camelot("X# Zyzzy Minor") == ""

    def test_all_keys_have_camelot(self):
        for key, cam in KEY_TO_CAMELOT.items():
            assert cam[-1] in ("A", "B")


class TestCamelotToKey:
    def test_roundtrip(self):
        for key, cam in KEY_TO_CAMELOT.items():
            assert camelot_to_key(cam) == key

    def test_unknown_camelot(self):
        assert camelot_to_key("99Z") == ""


class TestParseCamelot:
    def test_valid(self):
        assert parse_camelot("5A") == (5, "A")
        assert parse_camelot("8B") == (8, "B")
        assert parse_camelot("12A") == (12, "A")

    def test_invalid(self):
        assert parse_camelot("") == (0, "")
        assert parse_camelot("A") == (0, "")


class TestCamelotDistance:
    def test_same_key(self):
        assert camelot_distance("8B", "8B") == 0

    def test_relative_major_minor(self):
        assert camelot_distance("8A", "8B") == 1

    def test_adjacent_same_mode(self):
        assert camelot_distance("8B", "9B") == 1

    def test_adjacent_different_mode(self):
        assert camelot_distance("8A", "9B") == 2

    def test_unknown_key_max_distance(self):
        assert camelot_distance("8B", "") == 6
        assert camelot_distance("", "8B") == 6

    def test_opposite_side(self):
        # 8 to 2 is 6 apart (max)
        d = camelot_distance("8B", "2B")
        assert d >= 4


class TestScoreKeyCompatibility:
    def test_identical_keys(self):
        assert score_key_compatibility("8B", "8B") == 1.0

    def test_adjacent_keys_high_score(self):
        score = score_key_compatibility("8B", "9B")
        assert score >= 0.7

    def test_distant_keys_low_score(self):
        score = score_key_compatibility("1A", "7A")
        assert score <= 0.3

    def test_relative_major_minor(self):
        score = score_key_compatibility("8A", "8B")
        assert score >= 0.8


class TestDetectKeyFromChroma:
    def test_c_major_chroma(self):
        """A C Major profile should detect C Major."""
        # C Major intervals: C D E F G A B -> bins 0,2,4,5,7,9,11
        chroma = [0.0] * 12
        for bin_idx in [0, 2, 4, 5, 7, 9, 11]:
            chroma[bin_idx] = 1.0
        key, camelot, conf = detect_key_from_chroma(chroma)
        assert key == "C Major"
        assert camelot == "8B"
        assert conf > 0.5

    def test_a_minor_chroma(self):
        """A Minor has the strongest profile on bins 9,11,0,2,4,5,7.
        Use weighted values matching the minor profile shape."""
        # A Minor K-S profile: root(A=9) is strongest, then D=2, E=4, G=7
        chroma = [0.0] * 12
        # Map minor scale intervals to chroma bins: A(9), B(11), C(0), D(2), E(4), F(5), G(7)
        weights = {
            9: 6.33,   # A - root
            11: 2.68,  # B
            0: 3.52,   # C
            2: 5.38,   # D
            4: 2.60,   # E
            5: 3.53,   # F
            7: 2.54,   # G
        }
        for bin_idx, w in weights.items():
            chroma[bin_idx] = w
        key, camelot, conf = detect_key_from_chroma(chroma)
        assert key == "A Minor"
        assert camelot == "8A"
        assert conf > 0.5

    def test_zero_chroma_returns_empty(self):
        key, camelot, conf = detect_key_from_chroma([0.0] * 12)
        assert key == ""
        assert conf == 0.0

    def test_confidence_in_range(self):
        chroma = [1.0] * 12  # All bins equal -> low confidence
        _, _, conf = detect_key_from_chroma(chroma)
        assert 0.0 <= conf <= 1.0
