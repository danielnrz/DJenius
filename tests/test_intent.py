"""Tests for V5 SetIntent model and presets."""

import pytest
from djenius.core.intent import (
    SetIntent, TransitionStyle, VocalPreference,
    EnergyPreference, make_intent, apply_preset, PRESETS,
    ALL_PRESETS,
)
from djenius.core.models import EnergyProfile, TransitionType


class TestTransitionStyle:
    """Test TransitionStyle enum."""

    def test_all_styles_defined(self):
        assert TransitionStyle.SMOOTH == "smooth"
        assert TransitionStyle.ENERGETIC == "energetic"
        assert TransitionStyle.MINIMAL == "minimal"
        assert TransitionStyle.VARIED == "varied"
        assert TransitionStyle.SAFE == "safe"

    def test_all_list(self):
        assert len(TransitionStyle.ALL) == 5

    def test_allowed_types_smooth(self):
        allowed = TransitionStyle.allowed_types(TransitionStyle.SMOOTH)
        assert TransitionType.CROSSFADE in allowed
        assert TransitionType.BEATMATCHED_BLEND in allowed
        assert TransitionType.BASS_SWAP not in allowed

    def test_allowed_types_energetic(self):
        allowed = TransitionStyle.allowed_types(TransitionStyle.ENERGETIC)
        assert TransitionType.BASS_SWAP in allowed
        assert TransitionType.FILTER_SWEEP not in allowed

    def test_allowed_types_minimal(self):
        allowed = TransitionStyle.allowed_types(TransitionStyle.MINIMAL)
        assert TransitionType.CROSSFADE in allowed
        assert len(allowed) == 3

    def test_allowed_types_safe(self):
        allowed = TransitionStyle.allowed_types(TransitionStyle.SAFE)
        assert TransitionType.CROSSFADE in allowed
        assert TransitionType.BEATMATCHED_BLEND in allowed
        assert TransitionType.FILTER_SWEEP in allowed
        assert len(allowed) == 4

    def test_allowed_types_varied(self):
        allowed = TransitionStyle.allowed_types(TransitionStyle.VARIED)
        assert len(allowed) == 8  # All TransitionType members


class TestVocalPreference:
    """Test VocalPreference enum."""

    def test_all_options(self):
        assert len(VocalPreference.ALL) == 5

    def test_values(self):
        assert VocalPreference.ANY == "any"
        assert VocalPreference.VOCAL_SAFE == "vocal_safe"
        assert VocalPreference.INSTRUMENTAL_ONLY == "instrumental"
        assert VocalPreference.VOCALS_PREFERRED == "vocals"
        assert VocalPreference.STEM_FRIENDLY == "stem_friendly"


class TestEnergyPreference:
    """Test EnergyPreference enum."""

    def test_to_range_low(self):
        min_e, max_e = EnergyPreference.to_range(EnergyPreference.LOW)
        assert min_e == 0.0
        assert max_e == 0.35

    def test_to_range_medium(self):
        min_e, max_e = EnergyPreference.to_range(EnergyPreference.MEDIUM)
        assert min_e == 0.3
        assert max_e == 0.65

    def test_to_range_high(self):
        min_e, max_e = EnergyPreference.to_range(EnergyPreference.HIGH)
        assert min_e == 0.6
        assert max_e == 1.0


class TestSetIntent:
    """Test SetIntent dataclass."""

    def test_default_intent(self):
        intent = SetIntent()
        assert intent.raw_text is None
        assert intent.preset is None
        assert intent.energy_profile is None
        assert intent.transition_style is None
        assert intent.vocal_preference is None

    def test_preset_intent(self):
        intent = make_intent("chill")
        assert intent.preset == "chill"
        assert intent.energy_profile == EnergyProfile.STEADY
        assert intent.transition_style == TransitionStyle.SMOOTH

    def test_make_intent_all_presets(self):
        for preset_name in ALL_PRESETS:
            intent = make_intent(preset_name)
            assert intent.preset == preset_name

    def test_make_intent_invalid(self):
        with pytest.raises(ValueError):
            make_intent("nonexistent_preset")

    def test_effective_energy_profile_default(self):
        intent = SetIntent()
        assert intent.effective_energy_profile() == EnergyProfile.STEADY

    def test_effective_energy_profile_explicit(self):
        intent = SetIntent(energy_profile=EnergyProfile.SLOW_BUILD)
        assert intent.effective_energy_profile() == EnergyProfile.SLOW_BUILD

    def test_effective_energy_profile_preset(self):
        intent = SetIntent(preset="chill")
        # Should use the preset's energy profile
        profile = intent.effective_energy_profile()
        assert profile is not None


class TestPresets:
    """Test preset definitions."""

    def test_all_presets_exist(self):
        for name in ALL_PRESETS:
            assert name in PRESETS

    def test_preset_count(self):
        assert len(PRESETS) == 8

    def test_chill_preset(self):
        preset = PRESETS["chill"]
        assert preset["energy_profile"] == EnergyProfile.STEADY
        assert preset["transition_style"] == TransitionStyle.SMOOTH
        assert preset["target_duration_sec"] == 2400.0

    def test_peak_preset(self):
        preset = PRESETS["peak"]
        assert preset["energy_profile"] == EnergyProfile.WARMUP_TO_PEAK
        assert preset["transition_style"] == TransitionStyle.ENERGETIC


class TestApplyPreset:
    """Test apply_preset function."""

    def test_apply_preset(self):
        intent = SetIntent()
        result = apply_preset(intent, "chill")
        assert result.preset == "chill"
        assert result.energy_profile == EnergyProfile.STEADY

    def test_apply_preset_returns_new_object(self):
        intent = SetIntent()
        result = apply_preset(intent, "chill")
        assert intent is not result
        assert intent.preset is None
        assert result.preset == "chill"

    def test_apply_preset_invalid(self):
        intent = SetIntent()
        with pytest.raises(ValueError):
            apply_preset(intent, "nonexistent")
