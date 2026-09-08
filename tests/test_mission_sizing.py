"""Tests for the Milestone 4 mission profile, energy requirement, capacity
candidate sweep, and voltage carry-forward logic -- plus regression checks
that Milestone 1-3 results are unchanged."""

from __future__ import annotations

import math

import pytest

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import (
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    REFERENCE_C_T,
    default_esc_model,
    default_motor_assumptions,
)
from edf_sizing.energy import mission_energy_Wh
from edf_sizing.mission_sizing import (
    CLIMB_POWER_FRACTION_OF_STATIC,
    DEFAULT_CAPACITY_CANDIDATES_AH,
    DEFAULT_RESERVE_FRACTION,
    DEFAULT_USABLE_FRACTION,
    DEFAULT_VOLTAGE_CANDIDATES_SERIES,
    LOITER_POWER_FRACTION_OF_CRUISE,
    compute_energy_requirement,
    default_mission_profile,
    evaluate_capacity_candidate,
    evaluate_voltage_carry_forward,
    m3_reference_battery_powers,
    select_capacity_for_voltage,
)
from edf_sizing.requirements import default_requirement


@pytest.fixture
def requirement():
    return default_requirement()


@pytest.fixture
def m1_assumption():
    return NonIdealAssumption(eta_overall=0.75)


@pytest.fixture
def m3_powers(requirement, m1_assumption):
    return m3_reference_battery_powers(requirement, 0.5, m1_assumption, REFERENCE_C_T)


@pytest.fixture
def profile(requirement, m3_powers):
    p_static, p_cruise, _static_row, _cruise_row = m3_powers
    return default_mission_profile(p_static, p_cruise, requirement.n_fans)


@pytest.fixture
def energy_requirement(profile):
    return compute_energy_requirement(profile)


# ---------------------------------------------------------------------------
# M1/M2/M3 regression -- exact preservation
# ---------------------------------------------------------------------------


def test_m3_static_battery_power_preserved(m3_powers):
    p_static, _p_cruise, _sr, _cr = m3_powers
    assert p_static == pytest.approx(3928.6596614837263, rel=1e-9)


def test_m3_cruise_battery_power_preserved(m3_powers):
    _p_static, p_cruise, _sr, _cr = m3_powers
    assert p_cruise == pytest.approx(726.1054198562236, rel=1e-9)


def test_m2_reference_rpm_preserved(m3_powers):
    _p_static, _p_cruise, static_row, cruise_row = m3_powers
    assert static_row.rpm == pytest.approx(9298.313211084502, rel=1e-9)
    assert cruise_row.rpm == pytest.approx(3001.0176845292235, rel=1e-9)
    assert static_row.tip_mach == pytest.approx(0.715, abs=0.001)


def test_m3_14s_static_current_preserved(m3_powers):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    result = evaluate_capacity_candidate(
        14, 4.0, static_row, motor, esc, compute_energy_requirement(
            default_mission_profile(3928.6596614837263, 726.1054198562236, 2)
        )
    )
    assert result.static_current_A == pytest.approx(75.84285060779393, rel=1e-9)
    assert result.static_c_rate == pytest.approx(18.960712651948484, rel=1e-9)


def test_baseline_efficiencies_unchanged():
    assert DEFAULT_ETA_MOTOR == pytest.approx(0.90, abs=1e-9)
    assert DEFAULT_ETA_ESC == pytest.approx(0.97, abs=1e-9)


# ---------------------------------------------------------------------------
# Mission profile / energy requirement
# ---------------------------------------------------------------------------


def test_default_mission_profile_hand_check(profile, m3_powers):
    p_static, p_cruise, _sr, _cr = m3_powers
    names = [s.name for s in profile.segments]
    assert names == ["launch", "climb", "cruise", "loiter"]

    launch = profile.segments[0]
    climb = profile.segments[1]
    cruise = profile.segments[2]
    loiter = profile.segments[3]

    climb_hand = p_static * 2 * CLIMB_POWER_FRACTION_OF_STATIC
    loiter_hand = p_cruise * 2 * LOITER_POWER_FRACTION_OF_CRUISE
    assert launch.total_power_W == pytest.approx(p_static * 2, rel=1e-12)
    assert climb.total_power_W == pytest.approx(climb_hand, rel=1e-12)
    assert cruise.total_power_W == pytest.approx(p_cruise * 2, rel=1e-12)
    assert loiter.total_power_W == pytest.approx(loiter_hand, rel=1e-12)


def test_energy_requirement_chain_hand_check(profile, energy_requirement):
    mission_wh_hand = mission_energy_Wh(profile)
    reserve_wh_hand = mission_wh_hand * (1.0 + DEFAULT_RESERVE_FRACTION)
    nominal_wh_hand = reserve_wh_hand / DEFAULT_USABLE_FRACTION

    assert energy_requirement.mission_energy_Wh == pytest.approx(mission_wh_hand, rel=1e-12)
    assert energy_requirement.reserve_adjusted_Wh == pytest.approx(reserve_wh_hand, rel=1e-12)
    assert energy_requirement.required_nominal_Wh == pytest.approx(nominal_wh_hand, rel=1e-12)


def test_cruise_segment_dominates_mission_energy(profile):
    energies = {s.name: s.total_power_W * s.duration_s / 3600.0 for s in profile.segments}
    cruise_wh = energies["cruise"]
    assert cruise_wh == max(energies.values())


# ---------------------------------------------------------------------------
# Current vs. energy screening independence
# ---------------------------------------------------------------------------


def test_m3_baseline_pack_passes_current_but_fails_energy(m3_powers, energy_requirement):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    result = evaluate_capacity_candidate(14, 4.0, static_row, motor, esc, energy_requirement)
    assert result.current_ok is True
    assert result.energy_ok is False
    assert result.overall_ok is False


def test_large_capacity_passes_energy_but_could_fail_current_at_tiny_esc(
    m3_powers, energy_requirement
):
    """Demonstrate the reverse case: a pack can satisfy the energy
    requirement yet fail current, using a deliberately undersized ESC."""
    from edf_sizing.electrical import ESCModel

    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    tiny_esc = ESCModel(eta_esc=0.97, i_esc_max_A=1.0)
    result = evaluate_capacity_candidate(14, 32.0, static_row, motor, tiny_esc, energy_requirement)
    assert result.energy_ok is True
    # ESC margin fails, but our current_ok flag tracks the BATTERY current
    # margin (per Milestone 3 convention) -- verify the ESC margin
    # independently demonstrates the "current can fail while energy passes"
    # case using the underlying electrical operating point.
    from edf_sizing.battery import BatteryPack
    from edf_sizing.electrical_sizing import build_electrical_operating_point

    pack = BatteryPack(n_series=14, capacity_Ah=32.0, continuous_c_rate_limit=20.0)
    pt = build_electrical_operating_point(static_row, motor, tiny_esc, pack)
    assert pt.esc_current_margin.ok is False


def test_capacity_margin_exact_zero_boundary(m3_powers):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    # Build an energy requirement whose reserve-adjusted Wh exactly equals a
    # 28 Ah, 14S pack's usable energy at the default usable fraction --
    # i.e. the energy-margin boundary is exactly zero.
    v_pack = 14 * 3.7
    exact_usable_wh = 28.0 * v_pack * DEFAULT_USABLE_FRACTION
    from edf_sizing.mission_sizing import BatteryEnergyRequirement

    req = BatteryEnergyRequirement(
        mission_energy_Wh=exact_usable_wh / (1.0 + DEFAULT_RESERVE_FRACTION),
        reserve_fraction=DEFAULT_RESERVE_FRACTION,
        reserve_adjusted_Wh=exact_usable_wh,
        usable_fraction=DEFAULT_USABLE_FRACTION,
        required_nominal_Wh=exact_usable_wh / DEFAULT_USABLE_FRACTION,
    )
    result = evaluate_capacity_candidate(14, 28.0, static_row, motor, esc, req)
    assert result.usable_Wh == pytest.approx(exact_usable_wh, rel=1e-9)
    assert result.usable_Wh == pytest.approx(req.reserve_adjusted_Wh, rel=1e-9)
    assert result.energy_ok is True  # usable_Wh >= reserve_adjusted_Wh, boundary is >=


def test_below_capacity_fails_above_capacity_passes(m3_powers, energy_requirement):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    exact_required_ah = evaluate_capacity_candidate(
        14, 100.0, static_row, motor, esc, energy_requirement
    ).required_Ah

    just_below = evaluate_capacity_candidate(
        14, exact_required_ah * 0.999, static_row, motor, esc, energy_requirement
    )
    just_above = evaluate_capacity_candidate(
        14, exact_required_ah * 1.001, static_row, motor, esc, energy_requirement
    )
    assert just_below.energy_ok is False
    assert just_above.energy_ok is True


# ---------------------------------------------------------------------------
# Selection rule
# ---------------------------------------------------------------------------


def test_select_capacity_for_voltage_14s_picks_28ah(m3_powers, energy_requirement):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    outcome = select_capacity_for_voltage(
        14, DEFAULT_CAPACITY_CANDIDATES_AH, static_row, motor, esc, energy_requirement
    )
    assert outcome.success
    assert outcome.selected.capacity_Ah == pytest.approx(28.0, rel=1e-9)
    # Smaller candidates must all fail (not hidden).
    smaller = [c for c in outcome.all_candidates if c.capacity_Ah < 28.0]
    assert len(smaller) > 0
    assert all(not c.overall_ok for c in smaller)


def test_select_capacity_no_feasible_case_handled_honestly(m3_powers, energy_requirement):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    tiny_candidates = (1.0, 2.0, 3.0)
    outcome = select_capacity_for_voltage(
        14, tiny_candidates, static_row, motor, esc, energy_requirement
    )
    assert outcome.success is False
    assert outcome.selected is None
    assert len(outcome.all_candidates) == 3


def test_voltage_carry_forward_is_deterministic(m3_powers, energy_requirement):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    result_1 = evaluate_voltage_carry_forward(
        DEFAULT_VOLTAGE_CANDIDATES_SERIES,
        DEFAULT_CAPACITY_CANDIDATES_AH,
        static_row,
        motor,
        esc,
        energy_requirement,
        m3_selected_n_series=14,
    )
    result_2 = evaluate_voltage_carry_forward(
        DEFAULT_VOLTAGE_CANDIDATES_SERIES,
        DEFAULT_CAPACITY_CANDIDATES_AH,
        static_row,
        motor,
        esc,
        energy_requirement,
        m3_selected_n_series=14,
    )
    assert result_1.selected_n_series == result_2.selected_n_series


def test_all_three_voltages_become_current_feasible_at_energy_sized_capacity(
    m3_powers, energy_requirement
):
    """Once capacity is sized for the mission-energy requirement, 12S's
    original (small-capacity) current/C-rate failure from Milestone 3 is
    resolved -- an honest, non-tuned finding."""
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    for n_series in (12, 14, 16):
        outcome = select_capacity_for_voltage(
            n_series, DEFAULT_CAPACITY_CANDIDATES_AH, static_row, motor, esc, energy_requirement
        )
        assert outcome.success
        assert outcome.selected.current_ok is True


# ---------------------------------------------------------------------------
# No NaN/Inf
# ---------------------------------------------------------------------------


def test_no_nan_or_inf_across_full_sweep(m3_powers, energy_requirement):
    _p_static, _p_cruise, static_row, _cr = m3_powers
    motor = default_motor_assumptions()
    esc = default_esc_model()
    for n_series in DEFAULT_VOLTAGE_CANDIDATES_SERIES:
        for cap in DEFAULT_CAPACITY_CANDIDATES_AH:
            result = evaluate_capacity_candidate(
                n_series, cap, static_row, motor, esc, energy_requirement
            )
            for value in (
                result.nominal_Wh,
                result.usable_Wh,
                result.required_Ah,
                result.static_current_A,
                result.static_c_rate,
                result.capacity_margin.margin,
                result.current_margin.margin,
            ):
                assert math.isfinite(value)
