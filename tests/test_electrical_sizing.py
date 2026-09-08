"""Tests for the Milestone 3 electrical operating points, pack selection
rule, and regression checks that Milestone 1/2 results (and the
Milestone 1 eta_overall bookkeeping) are unchanged and not double-counted.
"""

from __future__ import annotations

import math

import pytest

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel
from edf_sizing.electrical_sizing import (
    DEFAULT_PACK_SERIES_CANDIDATES,
    HISTORICAL_INFEASIBLE_C_T,
    REFERENCE_C_T,
    build_electrical_operating_point,
    default_esc_model,
    default_motor_assumptions,
    make_pack,
    reference_rotational_rows,
    select_pack,
)
from edf_sizing.motor import MotorAssumptions
from edf_sizing.requirements import default_requirement
from edf_sizing.rotational_study import DEFAULT_M_TIP_MAX


@pytest.fixture
def requirement():
    return default_requirement()


@pytest.fixture
def m1_assumption():
    return NonIdealAssumption(eta_overall=0.75)


@pytest.fixture
def rows(requirement, m1_assumption):
    return reference_rotational_rows(requirement, 0.5, m1_assumption)


# ---------------------------------------------------------------------------
# M1/M2 regression -- unchanged, not double-counted
# ---------------------------------------------------------------------------


def test_m1_static_shaft_power_preserved_exactly(rows):
    assert rows["static"].p_shaft_est_W == pytest.approx(3429.719884475293, rel=1e-9)


def test_m1_cruise_shaft_power_preserved_exactly(rows):
    assert rows["cruise"].p_shaft_est_W == pytest.approx(633.8900315344832, rel=1e-9)


def test_m2_reference_c_t_008_remains_tip_mach_feasible(rows):
    assert rows["static"].c_t == pytest.approx(REFERENCE_C_T, rel=1e-12)
    assert rows["static"].tip_mach_ok is True
    assert rows["static"].tip_mach == pytest.approx(0.715, abs=0.001)


def test_m2_c_t_005_remains_tip_mach_infeasible(requirement, m1_assumption):
    rows_005 = reference_rotational_rows(
        requirement, 0.5, m1_assumption, c_t=HISTORICAL_INFEASIBLE_C_T
    )
    assert rows_005["static"].tip_mach_ok is False
    assert rows_005["static"].tip_mach == pytest.approx(0.905, abs=0.001)


def test_no_double_counting_of_eta_overall(requirement, rows):
    """P_shaft_est already includes M1's eta_overall=0.75 exactly once
    (Pi / eta_overall). Motor electrical power must divide the INHERITED
    P_shaft_est by eta_motor ONLY -- never re-divide by eta_overall again."""
    motor = default_motor_assumptions(eta_motor=0.90)
    static_row = rows["static"]
    from edf_sizing.motor import motor_electrical_power

    p_motor = float(motor_electrical_power(static_row.p_shaft_est_W, motor))

    # Correct single-application chain, reconstructed independently from
    # the ideal power: Pi / eta_overall / eta_motor.
    correct_chain = static_row.pi_ideal_W / 0.75 / 0.90
    assert p_motor == pytest.approx(correct_chain, rel=1e-9)

    # An accidental re-application of eta_overall inside the motor stage
    # would give Pi / eta_overall / eta_overall / eta_motor instead --
    # numerically different, and must NOT match what was actually computed.
    accidental_double_count = static_row.pi_ideal_W / 0.75 / 0.75 / 0.90
    assert p_motor != pytest.approx(accidental_double_count, rel=1e-6)

    # Structural check: the motor module must have no dependency at all on
    # M1's efficiency module, so eta_overall cannot be silently reapplied.
    import edf_sizing.motor as motor_module

    assert "efficiency" not in vars(motor_module).get("__dict__", vars(motor_module))
    assert not hasattr(motor_module, "NonIdealAssumption")
    assert not hasattr(motor_module, "estimated_shaft_power")


# ---------------------------------------------------------------------------
# Electrical operating point -- hand checks
# ---------------------------------------------------------------------------


def test_electrical_operating_point_static_hand_case(rows):
    motor = MotorAssumptions(eta_motor=0.90, rated_electrical_power_W=4500.0)
    esc = ESCModel(eta_esc=0.97, i_esc_max_A=100.0)
    pack = make_pack(14, capacity_Ah=4.0, c_rate_limit=20.0)

    pt = build_electrical_operating_point(rows["static"], motor, esc, pack)

    p_shaft = rows["static"].p_shaft_est_W
    p_motor_hand = p_shaft / 0.90
    p_batt_hand = p_motor_hand / 0.97
    v_pack_hand = 14 * 3.7
    i_batt_hand = p_batt_hand / v_pack_hand
    c_rate_hand = i_batt_hand / 4.0

    assert pt.motor_electrical_power_W == pytest.approx(p_motor_hand, rel=1e-9)
    assert pt.battery_power_W == pytest.approx(p_batt_hand, rel=1e-9)
    assert pt.battery_current_A == pytest.approx(i_batt_hand, rel=1e-9)
    assert pt.c_rate_required == pytest.approx(c_rate_hand, rel=1e-9)


def test_electrical_operating_point_battery_power_chain_ordering(rows):
    """battery input power >= motor electrical power >= shaft power (each
    downstream stage adds loss, never recovers energy)."""
    motor = MotorAssumptions(eta_motor=0.90)
    esc = ESCModel(eta_esc=0.97, i_esc_max_A=100.0)
    pack = make_pack(14)
    pt = build_electrical_operating_point(rows["static"], motor, esc, pack)
    assert pt.battery_power_W >= pt.motor_electrical_power_W >= pt.shaft_power_W


def test_static_current_exceeds_cruise_current(rows):
    motor = default_motor_assumptions()
    esc = default_esc_model()
    pack = make_pack(14)
    pt_static = build_electrical_operating_point(rows["static"], motor, esc, pack)
    pt_cruise = build_electrical_operating_point(rows["cruise"], motor, esc, pack)
    assert pt_static.battery_current_A > pt_cruise.battery_current_A
    assert pt_static.battery_power_W > pt_cruise.battery_power_W


def test_shaft_torque_is_positive_for_both_operating_points(rows):
    motor = default_motor_assumptions()
    esc = default_esc_model()
    pack = make_pack(14)
    for point_name in ("static", "cruise"):
        pt = build_electrical_operating_point(rows[point_name], motor, esc, pack)
        assert pt.shaft_torque_Nm > 0.0


# ---------------------------------------------------------------------------
# Margins -- exact boundary and above/below
# ---------------------------------------------------------------------------


def test_esc_current_margin_hand_case(rows):
    esc = ESCModel(eta_esc=0.97, i_esc_max_A=100.0)
    motor = default_motor_assumptions()
    pack = make_pack(14)
    pt = build_electrical_operating_point(rows["static"], motor, esc, pack)
    expected = 100.0 / pt.battery_current_A - 1.0
    assert pt.esc_current_margin.margin == pytest.approx(expected, rel=1e-9)


def test_battery_current_margin_hand_case(rows):
    motor = default_motor_assumptions()
    esc = default_esc_model()
    pack = make_pack(14, capacity_Ah=4.0, c_rate_limit=20.0)
    pt = build_electrical_operating_point(rows["static"], motor, esc, pack)
    i_max = 4.0 * 20.0
    expected = i_max / pt.battery_current_A - 1.0
    assert pt.battery_current_margin.margin == pytest.approx(expected, rel=1e-9)


def test_exact_current_rating_boundary_gives_zero_margin(rows):
    motor = default_motor_assumptions()
    esc_base = default_esc_model()
    pack = make_pack(14)
    pt_ref = build_electrical_operating_point(rows["static"], motor, esc_base, pack)
    i_required = pt_ref.battery_current_A

    esc_exact = ESCModel(eta_esc=esc_base.eta_esc, i_esc_max_A=i_required)
    pt_exact = build_electrical_operating_point(rows["static"], motor, esc_exact, pack)
    assert pt_exact.esc_current_margin.margin == pytest.approx(0.0, abs=1e-9)
    assert pt_exact.esc_current_margin.ok is True  # margin >= 0 passes


def test_just_below_rating_fails_just_above_passes(rows):
    motor = default_motor_assumptions()
    pack = make_pack(14)
    pt_ref = build_electrical_operating_point(
        rows["static"], motor, default_esc_model(), pack
    )
    i_required = pt_ref.battery_current_A

    esc_below = ESCModel(eta_esc=0.97, i_esc_max_A=i_required * 0.999)
    esc_above = ESCModel(eta_esc=0.97, i_esc_max_A=i_required * 1.001)
    pt_below = build_electrical_operating_point(rows["static"], motor, esc_below, pack)
    pt_above = build_electrical_operating_point(rows["static"], motor, esc_above, pack)
    assert pt_below.esc_current_margin.ok is False
    assert pt_above.esc_current_margin.ok is True


# ---------------------------------------------------------------------------
# Pack selection rule
# ---------------------------------------------------------------------------


def test_pack_selection_rejects_low_voltage_selects_14s(rows):
    motor = default_motor_assumptions()
    esc = default_esc_model()
    packs = [make_pack(n) for n in DEFAULT_PACK_SERIES_CANDIDATES]
    outcome = select_pack(rows["static"], motor, esc, packs)
    assert outcome.success
    assert outcome.selected.pack_n_series == 14

    # 12S must fail (documented, not tuned away).
    pt_12s = next(p for p in outcome.all_points if p.pack_n_series == 12)
    assert pt_12s.all_gates_ok is False
    assert pt_12s.battery_current_margin.ok is False


def test_pack_selection_no_feasible_pack_handled_honestly(rows):
    motor = default_motor_assumptions()
    # Deliberately too-small ESC rating -> nothing should qualify.
    esc_tiny = ESCModel(eta_esc=0.97, i_esc_max_A=1.0)
    packs = [make_pack(n) for n in DEFAULT_PACK_SERIES_CANDIDATES]
    outcome = select_pack(rows["static"], motor, esc_tiny, packs)
    assert outcome.success is False
    assert outcome.selected is None
    assert len(outcome.all_points) == len(packs)


def test_pack_selection_worst_case_sensitivity_only_16s_survives(rows):
    """At worst-case efficiency sensitivity (low eta_motor, low eta_esc),
    only the highest-voltage candidate remains feasible -- an honest,
    non-tuned result."""
    motor_worst = MotorAssumptions(eta_motor=0.85, rated_electrical_power_W=4500.0)
    esc_worst = ESCModel(eta_esc=0.95, i_esc_max_A=100.0)
    packs = [make_pack(n, capacity_Ah=4.0, c_rate_limit=20.0) for n in (12, 14, 16)]
    outcome = select_pack(rows["static"], motor_worst, esc_worst, packs)
    assert outcome.success
    assert outcome.selected.pack_n_series == 16
    pt_14s = next(p for p in outcome.all_points if p.pack_n_series == 14)
    assert pt_14s.all_gates_ok is False


# ---------------------------------------------------------------------------
# Sensitivity trend checks
# ---------------------------------------------------------------------------


def test_higher_capacity_reduces_required_c_rate_and_can_flip_gate(rows):
    motor = default_motor_assumptions()
    esc = default_esc_model()
    pt_low_cap = build_electrical_operating_point(
        rows["static"], motor, esc, make_pack(12, capacity_Ah=4.0)
    )
    pt_high_cap = build_electrical_operating_point(
        rows["static"], motor, esc, make_pack(12, capacity_Ah=8.0)
    )
    assert pt_high_cap.c_rate_required < pt_low_cap.c_rate_required
    assert pt_low_cap.c_rate_margin.ok is False
    assert pt_high_cap.c_rate_margin.ok is True


def test_motor_power_margin_present_when_rating_given(rows):
    motor = MotorAssumptions(eta_motor=0.90, rated_electrical_power_W=4500.0)
    esc = default_esc_model()
    pt = build_electrical_operating_point(rows["static"], motor, esc, make_pack(14))
    assert pt.motor_power_margin is not None
    expected = 4500.0 / pt.motor_electrical_power_W - 1.0
    assert pt.motor_power_margin.margin == pytest.approx(expected, rel=1e-9)


def test_motor_power_margin_absent_when_no_rating_given(rows):
    motor = MotorAssumptions(eta_motor=0.90, rated_electrical_power_W=None)
    esc = default_esc_model()
    pt = build_electrical_operating_point(rows["static"], motor, esc, make_pack(14))
    assert pt.motor_power_margin is None


# ---------------------------------------------------------------------------
# No NaN/Inf
# ---------------------------------------------------------------------------


def test_no_nan_or_inf_across_full_operating_matrix(rows):
    motors = [
        MotorAssumptions(eta_motor=e, rated_electrical_power_W=4500.0) for e in (0.85, 0.9, 0.95)
    ]
    escs = [ESCModel(eta_esc=e, i_esc_max_A=100.0) for e in (0.95, 0.97, 0.99)]
    packs = [make_pack(n, capacity_Ah=cap) for n in (12, 14, 16) for cap in (4.0, 6.0, 8.0)]
    for motor in motors:
        for esc in escs:
            for pack in packs:
                for point_name in ("static", "cruise"):
                    pt = build_electrical_operating_point(rows[point_name], motor, esc, pack)
                    for value in (
                        pt.shaft_torque_Nm,
                        pt.motor_electrical_power_W,
                        pt.battery_power_W,
                        pt.battery_current_A,
                        pt.c_rate_required,
                        pt.esc_current_margin.margin,
                        pt.battery_current_margin.margin,
                        pt.c_rate_margin.margin,
                    ):
                        assert math.isfinite(value)


def test_default_m_tip_max_used_by_reference_case_is_085():
    assert DEFAULT_M_TIP_MAX == pytest.approx(0.85, abs=1e-9)
