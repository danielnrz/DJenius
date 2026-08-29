"""Tests for V5 natural language parser."""

import pytest
from djenius.core.nl_parser import (
    parse_deterministic, parse_request, _intent_has_substantial_info,
)
from djenius.core.intent import (
    SetIntent, TransitionStyle, VocalPreference,
    EnergyPreference, ALL_PRESETS,
)
from djenius.core.models import EnergyProfile


class TestDeterministicParser:
    """Test deterministic keyword parser."""

    def test_preset_detection_chill(self):
        intent = parse_deterministic("give me a chill mix")
        assert intent.preset == "chill"

    def test_preset_detection_smooth(self):
        intent = parse_deterministic("smooth set please")
        assert intent.preset == "smooth"

    def test_preset_detection_energetic(self):
        intent = parse_deterministic("energetic mix tonight")
        assert intent.preset == "energetic"

    def test_preset_detection_peak(self):
        intent = parse_deterministic("peak time bangers")
        assert intent.preset == "peak"

    def test_preset_detection_late_night(self):
        intent = parse_deterministic("late night vibes")
        assert intent.preset == "late_night"

    def test_preset_detection_vocal_safe(self):
        intent = parse_deterministic("vocal safe mix please")
        assert intent.preset == "vocal_safe"

    def test_preset_detection_experimental(self):
        intent = parse_deterministic("experimental set")
        assert intent.preset == "experimental"

    def test_energy_profile_chill(self):
        intent = parse_deterministic("chill mix")
        assert intent.energy_profile == EnergyProfile.STEADY

    def test_energy_profile_build(self):
        intent = parse_deterministic("building set")
        assert intent.energy_profile == EnergyProfile.SLOW_BUILD

    def test_energy_profile_wave(self):
        intent = parse_deterministic("wave pattern")
        assert intent.energy_profile == EnergyProfile.WAVE

    def test_transition_style_smooth(self):
        intent = parse_deterministic("smooth transitions")
        assert intent.transition_style == TransitionStyle.SMOOTH

    def test_transition_style_energetic(self):
        intent = parse_deterministic("high energy bangers")
        assert intent.transition_style == TransitionStyle.ENERGETIC

    def test_transition_style_minimal(self):
        intent = parse_deterministic("minimal transitions")
        assert intent.transition_style == TransitionStyle.MINIMAL

    def test_transition_style_safe(self):
        intent = parse_deterministic("safe transitions")
        assert intent.transition_style == TransitionStyle.SAFE

    def test_vocal_preference_vocal_safe(self):
        intent = parse_deterministic("no vocal clash")
        assert intent.vocal_preference == VocalPreference.VOCAL_SAFE

    def test_vocal_preference_instrumental(self):
        intent = parse_deterministic("instrumental only")
        assert intent.vocal_preference == VocalPreference.INSTRUMENTAL_ONLY

    def test_vocal_preference_vocals(self):
        intent = parse_deterministic("vocals preferred")
        assert intent.vocal_preference == VocalPreference.VOCALS_PREFERRED

    def test_vocal_preference_stems(self):
        intent = parse_deterministic("stem friendly")
        assert intent.vocal_preference == VocalPreference.STEM_FRIENDLY

    def test_bpm_single_value(self):
        intent = parse_deterministic("120 bpm")
        assert intent.bpm_min is not None
        assert intent.bpm_max is not None
        assert intent.bpm_min < 120 < intent.bpm_max

    def test_bpm_range(self):
        intent = parse_deterministic("120 to 130 bpm")
        assert intent.bpm_min == 120.0
        assert intent.bpm_max == 130.0

    def test_duration_minutes(self):
        intent = parse_deterministic("30 minute set")
        assert intent.target_duration_sec == 1800.0

    def test_duration_hours(self):
        intent = parse_deterministic("2 hour set")
        assert intent.target_duration_sec == 7200.0

    def test_transition_length_short(self):
        intent = parse_deterministic("short transitions")
        assert intent.transition_length == "short"

    def test_transition_length_long(self):
        intent = parse_deterministic("extended transitions")
        assert intent.transition_length == "long"

    def test_stem_preference(self):
        intent = parse_deterministic("stem separation preferred")
        assert intent.prefer_stems is True

    def test_harmonic_preference(self):
        intent = parse_deterministic("harmonic mixing")
        assert intent.prefer_harmonic is True

    def test_raw_text_preserved(self):
        text = "give me a chill 30 min set"
        intent = parse_deterministic(text)
        assert intent.raw_text == text

    def test_source_is_nl_parser(self):
        intent = parse_deterministic("test")
        assert intent.source == "nl_parser"

    def test_empty_input(self):
        intent = parse_deterministic("")
        assert intent.preset is None
        assert intent.energy_profile is None


class TestIntentHasSubstantialInfo:
    """Test intent completeness check."""

    def test_empty_intent(self):
        intent = SetIntent()
        assert not _intent_has_substantial_info(intent)

    def test_preset_only(self):
        intent = SetIntent(preset="chill")
        assert not _intent_has_substantial_info(intent)

    def test_energy_profile_only(self):
        intent = SetIntent(energy_profile=EnergyProfile.STEADY)
        assert not _intent_has_substantial_info(intent)

    def test_two_fields(self):
        intent = SetIntent(bpm_min=120.0, bpm_max=130.0)
        assert _intent_has_substantial_info(intent)


class TestParseRequest:
    """Test unified parse_request function."""

    def test_deterministic_first(self):
        intent = parse_request("chill mix 30 min")
        assert intent.preset == "chill"
        assert intent.target_duration_sec == 1800.0

    def test_fallback_to_llm_disabled(self):
        # Even if deterministic gives minimal results, without use_llm it returns that
        intent = parse_request("something vague", use_llm=False)
        assert isinstance(intent, SetIntent)

    def test_all_presets_parseable(self):
        for preset in ALL_PRESETS:
            intent = parse_deterministic(preset)
            assert intent.preset == preset, f"Failed for preset: {preset}"

    def test_complex_request(self):
        intent = parse_deterministic("smooth 30 min set, 120-130 bpm, no vocal clash")
        assert intent.transition_style == TransitionStyle.SMOOTH
        assert intent.target_duration_sec == 1800.0
        assert intent.bpm_min == 120.0
        assert intent.bpm_max == 130.0
        assert intent.vocal_preference == VocalPreference.VOCAL_SAFE
