"""Independent verification of Milestone 4 energy integration, reserve/
usable-energy bookkeeping, capacity, and battery-mass-proxy relations."""

from __future__ import annotations

import pytest

from edf_sizing.energy import (
    battery_mass_kg,
    cruise_only_energy_diagnostic_hours,
    joules_to_Wh,
    mission_energy_J,
    mission_energy_Wh,
    required_capacity_Ah,
    required_nominal_energy_Wh,
    reserve_adjusted_energy_Wh,
    segment_energy_J,
    segment_energy_Wh,
    usable_energy_Wh,
)
from edf_sizing.mission import MissionProfile, MissionSegment


def _seg(name, duration_s, power_per_fan_W, n_fans=2, multiplier=1.0):
    return MissionSegment(
        name=name,
        duration_s=duration_s,
        power_per_fan_W=power_per_fan_W,
        n_fans=n_fans,
        power_multiplier=multiplier,
    )


# ---------------------------------------------------------------------------
# Segment energy: E = P*t, and J->Wh conversion
# ---------------------------------------------------------------------------


def test_segment_energy_J_hand_case():
    seg = _seg("cruise", 1200.0, 726.1054198562236, n_fans=2)
    p_total_hand = 726.1054198562236 * 2
    expected_J = p_total_hand * 1200.0
    assert segment_energy_J(seg) == pytest.approx(expected_J, rel=1e-12)


def test_segment_energy_Wh_hand_case():
    seg = _seg("cruise", 1200.0, 726.1054198562236, n_fans=2)
    expected_Wh = (726.1054198562236 * 2 * 1200.0) / 3600.0
    assert segment_energy_Wh(seg) == pytest.approx(expected_Wh, rel=1e-12)


def test_joules_to_Wh_hand_case():
    assert float(joules_to_Wh(18000.0)) == pytest.approx(5.0, rel=1e-12)  # 5 Wh = 18000 J


def test_joules_to_Wh_matches_segment_energy_Wh():
    seg = _seg("launch", 30.0, 3928.66, n_fans=2)
    wh_direct = segment_energy_Wh(seg)
    wh_via_joules = float(joules_to_Wh(segment_energy_J(seg)))
    assert wh_direct == pytest.approx(wh_via_joules, rel=1e-12)


def test_zero_duration_segment_gives_zero_energy():
    seg = _seg("x", 0.0, 1000.0, n_fans=2)
    assert segment_energy_J(seg) == pytest.approx(0.0, abs=1e-12)
    assert segment_energy_Wh(seg) == pytest.approx(0.0, abs=1e-12)


def test_joules_to_Wh_rejects_negative():
    with pytest.raises(ValueError):
        joules_to_Wh(-1.0)


# ---------------------------------------------------------------------------
# Multi-segment mission sum
# ---------------------------------------------------------------------------


def test_multi_segment_mission_sum_hand_case():
    segs = (
        _seg("launch", 30.0, 3928.66, n_fans=2),
        _seg("climb", 120.0, 3928.66, n_fans=2, multiplier=0.70),
        _seg("cruise", 1200.0, 726.11, n_fans=2),
        _seg("loiter", 300.0, 726.11, n_fans=2, multiplier=1.20),
    )
    profile = MissionProfile(segments=segs)
    expected_J = sum(segment_energy_J(s) for s in segs)
    expected_Wh = expected_J / 3600.0
    assert mission_energy_J(profile) == pytest.approx(expected_J, rel=1e-12)
    assert mission_energy_Wh(profile) == pytest.approx(expected_Wh, rel=1e-12)


def test_longer_duration_increases_mission_energy_monotonically():
    base_power = 1000.0
    durations = [100.0, 200.0, 400.0, 800.0]
    energies = []
    for d in durations:
        profile = MissionProfile(segments=(_seg("x", d, base_power, n_fans=2),))
        energies.append(mission_energy_Wh(profile))
    assert all(a < b for a, b in zip(energies, energies[1:], strict=False))


def test_mission_energy_scales_linearly_with_duration():
    profile1 = MissionProfile(segments=(_seg("x", 100.0, 500.0, n_fans=2),))
    profile2 = MissionProfile(segments=(_seg("x", 300.0, 500.0, n_fans=2),))
    assert mission_energy_Wh(profile2) / mission_energy_Wh(profile1) == pytest.approx(3.0, rel=1e-9)


# ---------------------------------------------------------------------------
# Reserve / usable-energy bookkeeping
# ---------------------------------------------------------------------------


def test_reserve_adjusted_energy_hand_case():
    mission_wh, reserve = 878.11, 0.20
    expected = 878.11 * 1.20
    assert reserve_adjusted_energy_Wh(mission_wh, reserve) == pytest.approx(expected, rel=1e-12)


def test_higher_reserve_fraction_increases_required_energy():
    mission_wh = 500.0
    e_low = reserve_adjusted_energy_Wh(mission_wh, 0.10)
    e_high = reserve_adjusted_energy_Wh(mission_wh, 0.30)
    assert e_high > e_low


def test_required_nominal_energy_hand_case():
    required_wh, usable = 1053.73, 0.80
    expected = 1053.73 / 0.80
    assert required_nominal_energy_Wh(required_wh, usable) == pytest.approx(expected, rel=1e-12)


def test_lower_usable_fraction_increases_required_nominal_energy():
    required_wh = 1000.0
    nom_high_usable = required_nominal_energy_Wh(required_wh, 0.90)
    nom_low_usable = required_nominal_energy_Wh(required_wh, 0.70)
    assert nom_low_usable > nom_high_usable


def test_usable_energy_is_inverse_of_required_nominal_energy():
    nominal_wh, usable_fraction = 1317.16, 0.80
    required_wh = nominal_wh * usable_fraction
    usable_computed = usable_energy_Wh(nominal_wh, usable_fraction)
    assert usable_computed == pytest.approx(required_wh, rel=1e-12)
    # Round-trip: required_nominal_energy_Wh(usable_computed, usable_fraction) recovers nominal_wh.
    recovered_nominal = required_nominal_energy_Wh(usable_computed, usable_fraction)
    assert recovered_nominal == pytest.approx(nominal_wh, rel=1e-9)


@pytest.mark.parametrize("bad_reserve", [-0.1, -1.0])
def test_reserve_rejects_negative_fraction(bad_reserve):
    with pytest.raises(ValueError):
        reserve_adjusted_energy_Wh(500.0, bad_reserve)


@pytest.mark.parametrize("bad_usable", [0.0, -0.1, 1.1])
def test_usable_fraction_rejects_invalid_values(bad_usable):
    with pytest.raises(ValueError):
        required_nominal_energy_Wh(500.0, bad_usable)
    with pytest.raises(ValueError):
        usable_energy_Wh(500.0, bad_usable)


# ---------------------------------------------------------------------------
# Required Ah / capacity
# ---------------------------------------------------------------------------


def test_required_capacity_Ah_hand_case():
    nominal_wh, v_pack = 1317.16, 51.8
    expected = 1317.16 / 51.8
    assert required_capacity_Ah(nominal_wh, v_pack) == pytest.approx(expected, rel=1e-12)


def test_ah_times_voltage_reconstructs_wh():
    nominal_wh, v_pack = 1450.4, 51.8
    ah = required_capacity_Ah(nominal_wh, v_pack)
    reconstructed_wh = ah * v_pack
    assert reconstructed_wh == pytest.approx(nominal_wh, rel=1e-9)


def test_higher_voltage_lowers_required_ah_for_fixed_wh():
    nominal_wh = 1317.16
    ah_12s = required_capacity_Ah(nominal_wh, 12 * 3.7)
    ah_16s = required_capacity_Ah(nominal_wh, 16 * 3.7)
    assert ah_16s < ah_12s
    assert ah_12s / ah_16s == pytest.approx((16 * 3.7) / (12 * 3.7), rel=1e-9)


def test_required_capacity_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        required_capacity_Ah(-1.0, 51.8)
    with pytest.raises(ValueError):
        required_capacity_Ah(500.0, 0.0)
    with pytest.raises(ValueError):
        required_capacity_Ah(500.0, -10.0)


# ---------------------------------------------------------------------------
# Battery mass proxy
# ---------------------------------------------------------------------------


def test_battery_mass_hand_case():
    nominal_wh, specific_energy = 1317.16, 200.0
    expected = 1317.16 / 200.0
    assert battery_mass_kg(nominal_wh, specific_energy) == pytest.approx(expected, rel=1e-12)


def test_battery_mass_decreases_with_higher_specific_energy():
    nominal_wh = 1317.16
    m_150 = battery_mass_kg(nominal_wh, 150.0)
    m_200 = battery_mass_kg(nominal_wh, 200.0)
    m_250 = battery_mass_kg(nominal_wh, 250.0)
    assert m_150 > m_200 > m_250


def test_battery_mass_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        battery_mass_kg(-1.0, 200.0)
    with pytest.raises(ValueError):
        battery_mass_kg(500.0, 0.0)
    with pytest.raises(ValueError):
        battery_mass_kg(500.0, -50.0)


# ---------------------------------------------------------------------------
# Cruise-only energy diagnostic (restricted use)
# ---------------------------------------------------------------------------


def test_cruise_only_diagnostic_hand_case():
    usable_wh, p_cruise_total = 1160.32, 1452.21
    expected = 1160.32 / 1452.21
    result = cruise_only_energy_diagnostic_hours(usable_wh, p_cruise_total)
    assert result == pytest.approx(expected, rel=1e-12)


def test_cruise_only_diagnostic_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        cruise_only_energy_diagnostic_hours(-1.0, 1000.0)
    with pytest.raises(ValueError):
        cruise_only_energy_diagnostic_hours(500.0, 0.0)
    with pytest.raises(ValueError):
        cruise_only_energy_diagnostic_hours(500.0, -10.0)
