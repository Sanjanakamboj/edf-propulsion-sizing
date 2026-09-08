"""Independent verification of the Milestone 4 mission segment model."""

from __future__ import annotations

import pytest

from edf_sizing.mission import MissionProfile, MissionSegment


def test_total_power_hand_case():
    seg = MissionSegment(
        name="cruise", duration_s=1200.0, power_per_fan_W=726.1, n_fans=2, power_multiplier=1.0
    )
    expected = 726.1 * 2 * 1.0
    assert seg.total_power_W == pytest.approx(expected, rel=1e-12)


def test_total_power_with_multiplier_hand_case():
    seg = MissionSegment(
        name="climb", duration_s=120.0, power_per_fan_W=3928.7, n_fans=2, power_multiplier=0.70
    )
    expected = 3928.7 * 2 * 0.70
    assert seg.total_power_W == pytest.approx(expected, rel=1e-12)


def test_zero_duration_segment_is_valid():
    seg = MissionSegment(name="x", duration_s=0.0, power_per_fan_W=100.0, n_fans=2)
    assert seg.duration_s == 0.0
    assert seg.total_power_W > 0.0  # power itself need not be zero


@pytest.mark.parametrize("bad_duration", [-1.0, -100.0])
def test_rejects_negative_duration(bad_duration):
    with pytest.raises(ValueError):
        MissionSegment(name="x", duration_s=bad_duration, power_per_fan_W=100.0, n_fans=2)


@pytest.mark.parametrize("bad_power", [-1.0, -50.0])
def test_rejects_negative_power(bad_power):
    with pytest.raises(ValueError):
        MissionSegment(name="x", duration_s=10.0, power_per_fan_W=bad_power, n_fans=2)


@pytest.mark.parametrize("bad_n_fans", [0, -1])
def test_rejects_invalid_fan_count(bad_n_fans):
    with pytest.raises(ValueError):
        MissionSegment(name="x", duration_s=10.0, power_per_fan_W=100.0, n_fans=bad_n_fans)


@pytest.mark.parametrize("bad_multiplier", [0.0, -0.5])
def test_rejects_invalid_power_multiplier(bad_multiplier):
    with pytest.raises(ValueError):
        MissionSegment(
            name="x",
            duration_s=10.0,
            power_per_fan_W=100.0,
            n_fans=2,
            power_multiplier=bad_multiplier,
        )


def test_mission_profile_rejects_empty_segments():
    with pytest.raises(ValueError):
        MissionProfile(segments=())


def test_mission_profile_holds_segments_in_order():
    s1 = MissionSegment(name="a", duration_s=10.0, power_per_fan_W=1.0, n_fans=1)
    s2 = MissionSegment(name="b", duration_s=20.0, power_per_fan_W=2.0, n_fans=1)
    profile = MissionProfile(segments=(s1, s2))
    assert profile.segments == (s1, s2)
