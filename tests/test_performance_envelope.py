"""Independent verification of the Milestone 5 thrust-margin, RPM-recovery,
electrical-propagation, and mission-energy-penalty logic, plus regression
checks that Milestone 1-4 results are unchanged."""

from __future__ import annotations

import math

import pytest

from edf_sizing import compressibility as comp
from edf_sizing.battery import BatteryPack
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel
from edf_sizing.electrical_sizing import (
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    REFERENCE_C_T,
    default_esc_model,
    default_motor_assumptions,
)
from edf_sizing.mission_sizing import (
    CLIMB_DURATION_S,
    CLIMB_POWER_FRACTION_OF_STATIC,
    CRUISE_DURATION_S,
    DEFAULT_RESERVE_FRACTION,
    DEFAULT_USABLE_FRACTION,
    LAUNCH_DURATION_S,
    LOITER_DURATION_S,
    LOITER_POWER_FRACTION_OF_CRUISE,
    default_mission_profile,
    m3_reference_battery_powers,
    reference_rotational_rows,
)
from edf_sizing.motor import MotorAssumptions
from edf_sizing.performance_envelope import (
    DEFAULT_LAPSE_MODEL,
    ETA_T_SENSITIVITY,
    STRESS_ETA_T,
    build_m5_mission_profile,
    compute_recovered_electrical,
    compute_rpm_recovery,
    evaluate_mission_energy_penalty,
    evaluate_performance_envelope,
    evaluate_thrust_margin,
)
from edf_sizing.requirements import default_requirement
from edf_sizing.rotational_study import DEFAULT_AMBIENT, DEFAULT_M_TIP_MAX


@pytest.fixture
def requirement():
    return default_requirement()


@pytest.fixture
def m1_assumption():
    return NonIdealAssumption(eta_overall=0.75)


@pytest.fixture
def rows(requirement, m1_assumption):
    return reference_rotational_rows(requirement, 0.5, m1_assumption, REFERENCE_C_T)


@pytest.fixture
def m3_powers(requirement, m1_assumption):
    return m3_reference_battery_powers(requirement, 0.5, m1_assumption, REFERENCE_C_T)


@pytest.fixture
def motor():
    return default_motor_assumptions()


@pytest.fixture
def esc():
    return default_esc_model()


@pytest.fixture
def pack28():
    return BatteryPack(n_series=14, capacity_Ah=28.0, continuous_c_rate_limit=20.0)


@pytest.fixture
def m4_profile(requirement, m3_powers):
    p_static, p_cruise, _sr, _cr = m3_powers
    return default_mission_profile(p_static, p_cruise, requirement.n_fans)


def _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, eta_T):
    static_row = rows["static"]
    p_static, p_cruise, _sr, _cr = m3_powers
    return evaluate_performance_envelope(
        requirement,
        0.5,
        requirement.static_thrust_per_fan_N,
        requirement.v_cruise_m_s,
        static_row.p_shaft_est_W,
        p_cruise,
        static_row.rpm,
        DEFAULT_M_TIP_MAX,
        eta_T,
        DEFAULT_LAPSE_MODEL,
        motor,
        esc,
        pack28,
        m4_profile,
        DEFAULT_RESERVE_FRACTION,
        DEFAULT_USABLE_FRACTION,
        CLIMB_POWER_FRACTION_OF_STATIC,
        LOITER_POWER_FRACTION_OF_CRUISE,
        LAUNCH_DURATION_S,
        CLIMB_DURATION_S,
        CRUISE_DURATION_S,
        LOITER_DURATION_S,
    )


# ---------------------------------------------------------------------------
# M1-M4 regression -- exact preservation
# ---------------------------------------------------------------------------


def test_m1_static_thrust_requirement_unchanged(requirement):
    assert requirement.static_thrust_per_fan_N == pytest.approx(147.0997500000000015, rel=1e-9)


def test_m1_cruise_thrust_requirement_unchanged(requirement):
    assert requirement.cruise_thrust_per_fan_N == pytest.approx(15.322890625, rel=1e-9)


def test_m2_reference_rpm_and_tip_mach_unchanged(rows):
    assert rows["static"].rpm == pytest.approx(9298.313211084502, rel=1e-9)
    assert rows["static"].tip_mach == pytest.approx(0.715, abs=0.001)


def test_m2_tip_mach_ceiling_unchanged():
    ceiling = comp.max_rpm_static(0.5, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    assert ceiling == pytest.approx(11048.476708333434, rel=1e-6)


def test_m3_baseline_efficiencies_unchanged():
    assert DEFAULT_ETA_MOTOR == pytest.approx(0.90, abs=1e-9)
    assert DEFAULT_ETA_ESC == pytest.approx(0.97, abs=1e-9)


def test_m4_baseline_mission_energy_unchanged(m4_profile):
    from edf_sizing.energy import mission_energy_Wh

    assert mission_energy_Wh(m4_profile) == pytest.approx(878.1064757693632, rel=1e-6)


# ---------------------------------------------------------------------------
# Thrust margin
# ---------------------------------------------------------------------------


def test_thrust_margin_hand_case():
    result = evaluate_thrust_margin("static", 0.0, 147.10, 132.39)
    expected_margin_n = 132.39 - 147.10
    expected_fraction = 132.39 / 147.10 - 1.0
    assert result.margin_N == pytest.approx(expected_margin_n, rel=1e-9)
    assert result.margin_fraction == pytest.approx(expected_fraction, rel=1e-9)
    assert result.passes is False


def test_thrust_margin_exact_zero_boundary():
    result = evaluate_thrust_margin("static", 0.0, 147.10, 147.10)
    assert result.margin_N == pytest.approx(0.0, abs=1e-9)
    assert result.passes is True


def test_thrust_margin_just_below_fails_just_above_passes():
    below = evaluate_thrust_margin("static", 0.0, 147.10, 147.10 * 0.999)
    above = evaluate_thrust_margin("static", 0.0, 147.10, 147.10 * 1.001)
    assert below.passes is False
    assert above.passes is True


def test_thrust_margin_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        evaluate_thrust_margin("static", 0.0, 0.0, 100.0)
    with pytest.raises(ValueError):
        evaluate_thrust_margin("static", 0.0, -1.0, 100.0)
    with pytest.raises(ValueError):
        evaluate_thrust_margin("static", 0.0, 100.0, -1.0)


# ---------------------------------------------------------------------------
# RPM recovery
# ---------------------------------------------------------------------------


def test_rpm_recovery_thrust_scaling_t_proportional_rpm_squared():
    # Independent hand check: T(RPM2)/T(RPM1) = (RPM2/RPM1)^2 at fixed C_T.
    rpm1, rpm2 = 9298.313211084502, 9801.3
    ratio_hand = (rpm2 / rpm1) ** 2
    # If eta_T * ratio_hand == 1, that RPM2 exactly recovers thrust.
    eta_T = 1.0 / ratio_hand
    result = compute_rpm_recovery(rpm1, 0.5, eta_T, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    assert result.rpm_required == pytest.approx(rpm2, rel=1e-3)


def test_rpm_recovery_exact_formula_hand_case():
    rpm_ref, eta_T = 9298.313211084502, 0.90
    expected = rpm_ref / math.sqrt(eta_T)
    result = compute_rpm_recovery(rpm_ref, 0.5, eta_T, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    assert result.rpm_required == pytest.approx(expected, rel=1e-12)


def test_rpm_recovery_round_trip_restores_thrust():
    """T_available(RPM_required) with eta_T applied must equal the
    reference (eta_T=1) thrust, verified via the independent T~RPM^2
    scaling relation."""
    rpm_ref, eta_T = 9298.313211084502, 0.80
    result = compute_rpm_recovery(rpm_ref, 0.5, eta_T, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    thrust_ratio_from_rpm = (result.rpm_required / rpm_ref) ** 2
    recovered_thrust_fraction = eta_T * thrust_ratio_from_rpm
    assert recovered_thrust_fraction == pytest.approx(1.0, rel=1e-9)


def test_power_scaling_p_proportional_rpm_cubed():
    rpm_ref, eta_T = 9298.313211084502, 0.90
    result = compute_rpm_recovery(rpm_ref, 0.5, eta_T, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    expected_power_ratio = (result.rpm_required / rpm_ref) ** 3
    assert result.power_ratio == pytest.approx(expected_power_ratio, rel=1e-12)


def test_tip_mach_increases_with_recovery_rpm():
    rpm_ref = 9298.313211084502
    r1 = compute_rpm_recovery(rpm_ref, 0.5, 1.00, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    r2 = compute_rpm_recovery(rpm_ref, 0.5, 0.80, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    assert r2.tip_mach_at_recovery > r1.tip_mach_at_recovery


def test_rpm_ceiling_enforcement_just_below_passes_just_above_fails():
    rpm_ref = 9298.313211084502
    ceiling = comp.max_rpm_static(0.5, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    # Choose eta_T so RPM_required lands exactly at the ceiling.
    eta_T_boundary = (rpm_ref / ceiling) ** 2
    result_at_boundary = compute_rpm_recovery(
        rpm_ref, 0.5, eta_T_boundary, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT
    )
    assert result_at_boundary.rpm_required == pytest.approx(ceiling, rel=1e-6)
    assert result_at_boundary.feasible is True  # boundary passes (>=)

    result_just_below = compute_rpm_recovery(
        rpm_ref, 0.5, eta_T_boundary * 1.001, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT
    )
    assert result_just_below.feasible is True

    result_just_above = compute_rpm_recovery(
        rpm_ref, 0.5, eta_T_boundary * 0.999, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT
    )
    assert result_just_above.feasible is False


def test_rpm_recovery_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        compute_rpm_recovery(0.0, 0.5, 0.9, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    with pytest.raises(ValueError):
        compute_rpm_recovery(9000.0, 0.5, 0.0, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    with pytest.raises(ValueError):
        compute_rpm_recovery(9000.0, 0.5, 1.5, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)


# ---------------------------------------------------------------------------
# Electrical propagation
# ---------------------------------------------------------------------------


def test_recovered_electrical_battery_power_hand_case(motor, esc, pack28):
    p_shaft_ref, power_ratio = 3429.719884475293, 1.1712139482105108
    p_shaft_recovered_hand = p_shaft_ref * power_ratio
    p_motor_hand = p_shaft_recovered_hand / motor.eta_motor
    p_batt_hand = p_motor_hand / esc.eta_esc
    i_batt_hand = p_batt_hand / pack28.v_pack_nom_V

    result = compute_recovered_electrical(p_shaft_ref, power_ratio, motor, esc, pack28)
    assert result.shaft_power_recovered_W == pytest.approx(p_shaft_recovered_hand, rel=1e-9)
    assert result.motor_electrical_power_W == pytest.approx(p_motor_hand, rel=1e-9)
    assert result.battery_power_W == pytest.approx(p_batt_hand, rel=1e-9)
    assert result.battery_current_A == pytest.approx(i_batt_hand, rel=1e-9)


def test_current_margin_exact_boundary(pack28, motor):
    p_shaft_ref, power_ratio = 3429.719884475293, 1.1712139482105108
    p_shaft_recovered = p_shaft_ref * power_ratio
    p_motor = p_shaft_recovered / motor.eta_motor
    p_batt = p_motor / 0.97
    i_batt = p_batt / pack28.v_pack_nom_V

    esc_exact = ESCModel(eta_esc=0.97, i_esc_max_A=i_batt)
    result = compute_recovered_electrical(p_shaft_ref, power_ratio, motor, esc_exact, pack28)
    assert result.esc_current_margin.margin == pytest.approx(0.0, abs=1e-9)
    assert result.esc_current_margin.ok is True


def test_recovered_electrical_rejects_invalid_inputs(motor, esc, pack28):
    with pytest.raises(ValueError):
        compute_recovered_electrical(-1.0, 1.0, motor, esc, pack28)
    with pytest.raises(ValueError):
        compute_recovered_electrical(1000.0, -0.5, motor, esc, pack28)


# ---------------------------------------------------------------------------
# Mission-energy penalty
# ---------------------------------------------------------------------------


def test_mission_energy_penalty_hand_case(requirement, m4_profile, pack28):
    p_static_recovered = 4601.300993301724
    p_cruise = 726.1054198562236
    m5_profile = build_m5_mission_profile(
        p_static_recovered,
        p_cruise,
        requirement.n_fans,
        CLIMB_POWER_FRACTION_OF_STATIC,
        LOITER_POWER_FRACTION_OF_CRUISE,
        LAUNCH_DURATION_S,
        CLIMB_DURATION_S,
        CRUISE_DURATION_S,
        LOITER_DURATION_S,
    )
    result = evaluate_mission_energy_penalty(
        m4_profile, m5_profile, DEFAULT_RESERVE_FRACTION, DEFAULT_USABLE_FRACTION, pack28
    )
    assert result.mission_energy_m4_baseline_Wh == pytest.approx(878.1064757693632, rel=1e-6)
    assert result.mission_energy_m5_Wh == pytest.approx(920.7070934511696, rel=1e-6)
    assert result.delta_Wh == pytest.approx(42.6006176818064, rel=1e-6)
    assert result.capacity_margin.margin == pytest.approx(0.05020732457799326, rel=1e-6)
    assert result.capacity_margin.ok is True


def test_m4_baseline_profile_unaffected_by_m5_evaluation(m4_profile, pack28, requirement):
    from edf_sizing.energy import mission_energy_Wh

    before = mission_energy_Wh(m4_profile)
    m5_profile = build_m5_mission_profile(
        5000.0,
        700.0,
        requirement.n_fans,
        CLIMB_POWER_FRACTION_OF_STATIC,
        LOITER_POWER_FRACTION_OF_CRUISE,
        LAUNCH_DURATION_S,
        CLIMB_DURATION_S,
        CRUISE_DURATION_S,
        LOITER_DURATION_S,
    )
    evaluate_mission_energy_penalty(
        m4_profile, m5_profile, DEFAULT_RESERVE_FRACTION, DEFAULT_USABLE_FRACTION, pack28
    )
    after = mission_energy_Wh(m4_profile)
    assert before == pytest.approx(after, rel=1e-15)


# ---------------------------------------------------------------------------
# Full performance-envelope integration and feasibility classification
# ---------------------------------------------------------------------------


def test_baseline_eta_t_090_is_feasible_via_recovery(
    requirement, rows, m3_powers, motor, esc, pack28, m4_profile
):
    result = _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, 0.90)
    # Baseline (pre-recovery) static margin is honestly negative.
    assert result.static_margin.passes is False
    assert result.static_margin.margin_fraction == pytest.approx(-0.10, abs=1e-6)
    # But RPM recovery closes it within the M2 tip-Mach ceiling.
    assert result.static_thrust_met_via_recovery is True
    assert result.cruise_margin.passes is True
    assert result.recovered_electrical.current_ok is True
    assert result.mission_energy_penalty.capacity_margin.ok is True
    assert result.feasible is True


def test_eta_t_100_fully_feasible_no_penalty(
    requirement, rows, m3_powers, motor, esc, pack28, m4_profile
):
    result = _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, 1.00)
    assert result.static_margin.passes is True
    assert result.rpm_recovery.power_ratio == pytest.approx(1.0, rel=1e-9)
    assert result.mission_energy_penalty.delta_Wh == pytest.approx(0.0, abs=1e-6)
    assert result.feasible is True


def test_eta_t_080_fails_electrical_and_energy(
    requirement, rows, m3_powers, motor, esc, pack28, m4_profile
):
    result = _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, 0.80)
    # RPM recovery itself is still within the tip-Mach ceiling.
    assert result.static_thrust_met_via_recovery is True
    # But the recovered current now exceeds the ESC rating,
    assert result.recovered_electrical.current_ok is False
    # and the mission-energy capacity margin goes negative.
    assert result.mission_energy_penalty.capacity_margin.ok is False
    assert result.feasible is False


def test_stress_eta_t_065_fails_rpm_ceiling(
    requirement, rows, m3_powers, motor, esc, pack28, m4_profile
):
    result = _full_envelope(
        requirement, rows, m3_powers, motor, esc, pack28, m4_profile, STRESS_ETA_T
    )
    assert result.rpm_recovery.feasible is False
    assert result.static_thrust_met_via_recovery is False
    assert result.feasible is False


def test_all_declared_sensitivity_eta_t_cases_deterministic(
    requirement, rows, m3_powers, motor, esc, pack28, m4_profile
):
    for eta_T in ETA_T_SENSITIVITY:
        r1 = _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, eta_T)
        r2 = _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, eta_T)
        assert r1.feasible == r2.feasible
        rpm1, rpm2 = r1.rpm_recovery.rpm_required, r2.rpm_recovery.rpm_required
        assert rpm1 == pytest.approx(rpm2, rel=1e-12)


def test_no_nan_or_inf_across_eta_t_sensitivity_grid(
    requirement, rows, m3_powers, motor, esc, pack28, m4_profile
):
    for eta_T in ETA_T_SENSITIVITY + (STRESS_ETA_T,):
        result = _full_envelope(requirement, rows, m3_powers, motor, esc, pack28, m4_profile, eta_T)
        values = (
            result.static_margin.margin_N,
            result.cruise_margin.margin_N,
            result.rpm_recovery.rpm_required,
            result.rpm_recovery.tip_mach_at_recovery,
            result.rpm_recovery.power_ratio,
            result.recovered_electrical.battery_current_A,
            result.mission_energy_penalty.delta_Wh,
            result.mission_energy_penalty.capacity_margin.margin,
        )
        for v in values:
            assert math.isfinite(v)


def test_16s_pack_also_evaluable_and_deterministic(
    requirement, rows, m3_powers, motor, esc, m4_profile
):
    pack16 = BatteryPack(n_series=16, capacity_Ah=24.0, continuous_c_rate_limit=20.0)
    result = _full_envelope(requirement, rows, m3_powers, motor, esc, pack16, m4_profile, 0.90)
    assert math.isfinite(result.recovered_electrical.battery_current_A)
    assert result.recovered_electrical.battery_current_A < 88.83  # lower current at higher voltage


def test_diameter_sensitivity_does_not_mutate_m1_selection(requirement, m1_assumption):
    """Evaluating the RPM ceiling at other diameters must not alter the
    frozen M1 requirement values."""
    for d in (0.45, 0.50, 0.55, 0.60):
        ceiling = comp.max_rpm_static(d, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
        assert math.isfinite(ceiling)
    assert requirement.static_thrust_per_fan_N == pytest.approx(147.0997500000000015, rel=1e-9)


def test_tip_mach_ceiling_sensitivity_changes_recovery_feasibility(
    requirement, rows, m3_powers
):
    rpm_ref = rows["static"].rpm
    for m_tip_max in (0.75, 0.85, 0.95):
        result = compute_rpm_recovery(rpm_ref, 0.5, 0.80, m_tip_max, DEFAULT_AMBIENT)
        assert math.isfinite(result.rpm_required)
    # A stricter ceiling must make recovery harder or equally hard, never easier.
    r_strict = compute_rpm_recovery(rpm_ref, 0.5, 0.80, 0.75, DEFAULT_AMBIENT)
    r_loose = compute_rpm_recovery(rpm_ref, 0.5, 0.80, 0.95, DEFAULT_AMBIENT)
    assert r_strict.rpm_ceiling < r_loose.rpm_ceiling


def test_motor_esc_efficiency_sensitivity_changes_current(
    requirement, rows, m3_powers, esc, pack28
):
    static_row = rows["static"]
    p_shaft_ref = static_row.p_shaft_est_W
    power_ratio = 1.1712139482105108
    r_hi = compute_recovered_electrical(
        p_shaft_ref, power_ratio, MotorAssumptions(eta_motor=0.95), esc, pack28
    )
    r_lo = compute_recovered_electrical(
        p_shaft_ref, power_ratio, MotorAssumptions(eta_motor=0.85), esc, pack28
    )
    assert r_lo.battery_current_A > r_hi.battery_current_A
