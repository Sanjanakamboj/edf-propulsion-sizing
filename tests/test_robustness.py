"""Independent verification of the Milestone 6 robustness orchestration
module: constraint extraction, feasibility classification, boundary
analysis, and sensitivity ranking -- plus regression checks that
Milestone 1-5 results are unchanged."""

from __future__ import annotations

import math

import pytest

from edf_sizing import compressibility as comp
from edf_sizing.requirements import default_requirement
from edf_sizing.robustness import (
    BASELINE,
    FAIL_BATTERY_CURRENT,
    FAIL_ESC_CURRENT,
    FAIL_M1_LOADING,
    FAIL_MISSION_ENERGY,
    FEASIBLE,
    GOVERNING_FAILURE_PRIORITY,
    FinalArchitecture,
    RobustnessCase,
    build_constraint_table,
    evaluate_baseline,
    evaluate_case,
    find_max_cruise_duration_s,
    find_min_feasible_eta_esc,
    find_min_feasible_eta_motor,
    find_min_feasible_eta_t,
    find_min_required_capacity_Ah,
    max_recoverable_thrust_loss_fraction,
    rank_sensitivities,
    sweep_diameter,
)
from edf_sizing.rotational_study import DEFAULT_AMBIENT


@pytest.fixture
def requirement():
    return default_requirement()


# ---------------------------------------------------------------------------
# M1-M5 regression -- exact preservation
# ---------------------------------------------------------------------------


def test_baseline_architecture_matches_committed_m1_m5_values():
    assert BASELINE.diameter_m == pytest.approx(0.50, abs=1e-9)
    assert BASELINE.reference_c_t == pytest.approx(0.08, abs=1e-9)
    assert BASELINE.m_tip_max == pytest.approx(0.85, abs=1e-9)
    assert BASELINE.n_series == 14
    assert BASELINE.capacity_Ah == pytest.approx(28.0, abs=1e-9)
    assert BASELINE.eta_T == pytest.approx(0.90, abs=1e-9)
    assert BASELINE.eta_motor == pytest.approx(0.90, abs=1e-9)
    assert BASELINE.eta_esc == pytest.approx(0.97, abs=1e-9)
    assert BASELINE.reserve_fraction == pytest.approx(0.20, abs=1e-9)
    assert BASELINE.usable_fraction == pytest.approx(0.80, abs=1e-9)


def test_baseline_envelope_reproduces_m5_committed_numbers(requirement):
    env = evaluate_baseline(requirement, BASELINE)
    assert env.static_margin.thrust_available_N == pytest.approx(132.39, abs=0.01)
    assert env.static_margin.margin_fraction == pytest.approx(-0.10, abs=1e-6)
    assert env.cruise_margin.margin_fraction == pytest.approx(6.344, abs=0.01)
    assert env.rpm_recovery.rpm_required == pytest.approx(9801.3, abs=0.5)
    assert env.rpm_recovery.tip_mach_at_recovery == pytest.approx(0.754, abs=0.001)
    assert env.recovered_electrical.battery_current_A == pytest.approx(88.83, abs=0.01)
    assert env.mission_energy_penalty.mission_energy_m5_Wh == pytest.approx(920.71, abs=0.01)
    assert env.mission_energy_penalty.capacity_margin.margin == pytest.approx(0.050, abs=0.001)


def test_m2_tip_mach_ceiling_unchanged():
    ceiling = comp.max_rpm_static(0.5, BASELINE.m_tip_max, DEFAULT_AMBIENT)
    assert ceiling == pytest.approx(11048.476708333434, rel=1e-6)


# ---------------------------------------------------------------------------
# Constraint table extraction
# ---------------------------------------------------------------------------


def test_constraint_table_has_eight_rows_and_positive_margin_convention(requirement):
    table = build_constraint_table(requirement, BASELINE)
    assert len(table) == 8
    for row in table:
        # margin > 0 must always correspond to status == PASS, and vice versa.
        assert (row.margin >= 0) == (row.status == "PASS")


def test_constraint_table_static_thrust_row_is_honest_baseline_shortfall(requirement):
    table = build_constraint_table(requirement, BASELINE)
    static_row = next(r for r in table if r.name.startswith("G."))
    assert static_row.status == "FAIL"
    assert static_row.margin == pytest.approx(-0.10, abs=1e-6)


def test_constraint_table_disk_loading_hand_check(requirement):
    import math as _m

    table = build_constraint_table(requirement, BASELINE)
    row = next(r for r in table if r.name.startswith("A."))
    area_hand = _m.pi * 0.5**2 / 4.0
    dl_hand = requirement.static_thrust_per_fan_N / area_hand
    assert row.value == pytest.approx(dl_hand, rel=1e-9)
    margin_hand = 900.0 / dl_hand - 1.0
    assert row.margin == pytest.approx(margin_hand, rel=1e-9)


# ---------------------------------------------------------------------------
# Feasibility classification
# ---------------------------------------------------------------------------


def test_baseline_case_is_feasible(requirement):
    result = evaluate_case(requirement, RobustnessCase())
    assert result.feasible is True
    assert result.failures == ()
    assert result.governing_failure is None


def test_eta_t_080_reproduces_known_infeasibility(requirement):
    result = evaluate_case(requirement, RobustnessCase(eta_T=0.80))
    assert result.feasible is False
    assert FAIL_ESC_CURRENT in result.failures
    assert FAIL_MISSION_ENERGY in result.failures
    assert result.envelope.rpm_recovery.feasible is True  # RPM ceiling itself still OK


def test_12s_preserves_known_m3_failure(requirement):
    """At the M3 baseline capacity (4.0 Ah) and no thrust loss (eta_T=1.0,
    isolating the electrical/energy screens), 12S fails on current/energy,
    exactly as established in Milestone 3/4."""
    result = evaluate_case(
        requirement, RobustnessCase(n_series=12, capacity_Ah=4.0, eta_T=1.0)
    )
    assert result.feasible is False
    assert FAIL_BATTERY_CURRENT in result.failures or FAIL_MISSION_ENERGY in result.failures


def test_16s_remains_feasible_at_baseline(requirement):
    result = evaluate_case(requirement, RobustnessCase(n_series=16, capacity_Ah=24.0))
    assert result.feasible is True


def test_simultaneous_failures_are_all_recorded(requirement):
    result = evaluate_case(requirement, RobustnessCase(eta_T=0.80))
    # Both electrical and energy gates fail simultaneously -- neither is hidden.
    assert len(result.failures) >= 2


def test_governing_failure_priority_is_deterministic(requirement):
    result = evaluate_case(requirement, RobustnessCase(eta_T=0.80))
    # ESC current precedes mission energy in the declared priority order.
    idx_esc = GOVERNING_FAILURE_PRIORITY.index(FAIL_ESC_CURRENT)
    idx_energy = GOVERNING_FAILURE_PRIORITY.index(FAIL_MISSION_ENERGY)
    assert idx_esc < idx_energy
    assert result.governing_failure == FAIL_ESC_CURRENT


def test_governing_failure_none_when_feasible(requirement):
    result = evaluate_case(requirement, RobustnessCase())
    assert result.governing_failure is None
    assert result.feasible


def test_m1_loading_failure_detected_for_undersized_diameter(requirement):
    result = evaluate_case(requirement, RobustnessCase(diameter_m=0.45))
    assert result.m1_ok is False
    assert FAIL_M1_LOADING in result.failures
    assert result.governing_failure == FAIL_M1_LOADING


# ---------------------------------------------------------------------------
# Boundary / breakpoint analysis
# ---------------------------------------------------------------------------


def test_min_feasible_eta_t_boundary_round_trip(requirement):
    boundary = find_min_feasible_eta_t(requirement)
    assert 0.70 < boundary < 0.90  # strictly between the known fail (0.80) and pass (0.90/1.00)
    just_above = evaluate_case(requirement, RobustnessCase(eta_T=boundary + 0.01))
    just_below = evaluate_case(requirement, RobustnessCase(eta_T=boundary - 0.01))
    assert just_above.feasible is True
    assert just_below.feasible is False


def test_max_cruise_duration_boundary_round_trip(requirement):
    boundary = find_max_cruise_duration_s(requirement)
    assert boundary > 1200.0  # baseline (1200 s) passes with positive energy margin
    just_below = evaluate_case(requirement, RobustnessCase(cruise_duration_s=boundary - 5.0))
    just_above = evaluate_case(requirement, RobustnessCase(cruise_duration_s=boundary + 5.0))
    assert just_below.envelope.mission_energy_penalty.capacity_margin.ok is True
    assert just_above.envelope.mission_energy_penalty.capacity_margin.ok is False


def test_min_feasible_eta_motor_boundary_round_trip(requirement):
    boundary = find_min_feasible_eta_motor(requirement)
    assert 0.5 < boundary < 0.90
    r_above = evaluate_case(requirement, RobustnessCase(eta_motor=boundary + 0.01))
    r_below = evaluate_case(requirement, RobustnessCase(eta_motor=boundary - 0.01))
    assert r_above.envelope.recovered_electrical.current_ok is True
    assert r_below.envelope.recovered_electrical.current_ok is False


def test_min_feasible_eta_esc_boundary_round_trip(requirement):
    boundary = find_min_feasible_eta_esc(requirement)
    assert 0.5 < boundary < 0.97
    r_above = evaluate_case(requirement, RobustnessCase(eta_esc=boundary + 0.01))
    r_below = evaluate_case(requirement, RobustnessCase(eta_esc=boundary - 0.01))
    assert r_above.envelope.recovered_electrical.current_ok is True
    assert r_below.envelope.recovered_electrical.current_ok is False


def test_min_required_capacity_boundary_round_trip(requirement):
    boundary = find_min_required_capacity_Ah(requirement)
    assert 20.0 < boundary < 28.0
    r_above = evaluate_case(requirement, RobustnessCase(capacity_Ah=boundary + 0.5))
    r_below = evaluate_case(requirement, RobustnessCase(capacity_Ah=boundary - 0.5))
    assert r_above.envelope.mission_energy_penalty.capacity_margin.ok is True
    assert r_below.envelope.mission_energy_penalty.capacity_margin.ok is False


def test_boundary_search_rejects_non_bracketing_inputs(requirement):
    with pytest.raises(ValueError):
        find_min_feasible_eta_t(requirement, lo=0.99, hi=0.999)  # both feasible, no boundary


def test_max_recoverable_thrust_loss_fraction_hand_derivation(requirement):
    """DERIVED independently: the eta_T at which RPM_required exactly
    equals the tip-Mach RPM ceiling satisfies
    eta_T_boundary = (rpm_reference / rpm_ceiling)^2."""
    from edf_sizing.efficiency import NonIdealAssumption
    from edf_sizing.electrical_sizing import REFERENCE_C_T, reference_rotational_rows

    rows = reference_rotational_rows(
        requirement, 0.5, NonIdealAssumption(eta_overall=0.75), REFERENCE_C_T
    )
    rpm_ref = rows["static"].rpm
    ceiling = comp.max_rpm_static(0.5, 0.85, DEFAULT_AMBIENT)
    eta_t_boundary_hand = (rpm_ref / ceiling) ** 2
    expected_loss_fraction = 1.0 - eta_t_boundary_hand

    result = max_recoverable_thrust_loss_fraction(requirement)
    assert result == pytest.approx(expected_loss_fraction, rel=1e-9)
    assert result == pytest.approx(0.2917, abs=0.001)


def test_tip_mach_rpm_ceiling_preserved_across_module(requirement):
    ceiling_direct = comp.max_rpm_static(0.5, 0.85, DEFAULT_AMBIENT)
    result = evaluate_case(requirement, RobustnessCase())
    assert result.envelope.rpm_recovery.rpm_ceiling == pytest.approx(ceiling_direct, rel=1e-9)


# ---------------------------------------------------------------------------
# Diameter robustness
# ---------------------------------------------------------------------------


def test_diameter_045_fails_inherited_m1_constraints(requirement):
    results = sweep_diameter(requirement)
    r045 = next(r for r in results if r.case.diameter_m == pytest.approx(0.45))
    assert r045.m1_ok is False
    assert r045.feasible is False


def test_diameter_050_baseline_feasible(requirement):
    results = sweep_diameter(requirement)
    r050 = next(r for r in results if r.case.diameter_m == pytest.approx(0.50))
    assert r050.m1_ok is True
    assert r050.feasible is True


def test_diameter_sweep_does_not_alter_m1_selection_state(requirement):
    sweep_diameter(requirement)
    # Re-derive the M1 static thrust requirement independently to confirm
    # nothing in the sweep mutated global/module state.
    assert requirement.static_thrust_per_fan_N == pytest.approx(147.0997500000000015, rel=1e-9)


def test_larger_diameter_lowers_disk_loading_in_sweep(requirement):
    results = sweep_diameter(requirement)
    table_045 = build_constraint_table(requirement, FinalArchitecture(diameter_m=0.45))
    table_060 = build_constraint_table(requirement, FinalArchitecture(diameter_m=0.60))
    dl_045 = next(r for r in table_045 if r.name.startswith("A.")).value
    dl_060 = next(r for r in table_060 if r.name.startswith("A.")).value
    assert dl_060 < dl_045
    assert len(results) == 4


# ---------------------------------------------------------------------------
# Sensitivity ranking
# ---------------------------------------------------------------------------


def test_sensitivity_ranking_is_deterministic(requirement):
    r1 = rank_sensitivities(requirement)
    r2 = rank_sensitivities(requirement)
    assert [x.parameter for x in r1] == [x.parameter for x in r2]
    for a, b in zip(r1, r2, strict=True):
        assert a.max_fractional_swing == pytest.approx(b.max_fractional_swing, rel=1e-12)


def test_sensitivity_ranking_orders_by_swing_descending(requirement):
    rankings = rank_sensitivities(requirement)
    swings = [r.max_fractional_swing for r in rankings]
    assert swings == sorted(swings, reverse=True)
    ranks = [r.rank for r in rankings]
    assert ranks == list(range(1, len(rankings) + 1))


def test_sensitivity_ranking_flip_flags_are_consistent_with_metric(requirement):
    """A parameter whose grid includes a known feasibility-flipping case
    (eta_T spans the known 0.80-fail / 0.90-pass boundary) must be flagged
    as flipping."""
    rankings = rank_sensitivities(requirement)
    eta_t_ranking = next(r for r in rankings if r.parameter == "eta_T")
    assert eta_t_ranking.feasibility_flips is True
    assert eta_t_ranking.max_fractional_swing > 0.0


def test_m_tip_max_flip_is_reflected_in_nonzero_swing(requirement):
    """Regression for a self-caught metric gap: m_tip_max=0.75 flips
    feasibility purely via the RPM-recovery/tip-Mach gate, so the ranking
    metric must be nonzero for it (not just `feasibility_flips=True`)."""
    rankings = rank_sensitivities(requirement)
    m_tip_ranking = next(r for r in rankings if r.parameter == "m_tip_max")
    assert m_tip_ranking.feasibility_flips is True
    assert m_tip_ranking.max_fractional_swing > 0.0


# ---------------------------------------------------------------------------
# No NaN/Inf across the robustness grid
# ---------------------------------------------------------------------------


def test_no_nan_or_inf_across_eta_t_and_diameter_grids(requirement):
    from edf_sizing.robustness import DIAMETER_GRID_M, ETA_T_GRID

    for eta_t in ETA_T_GRID:
        r = evaluate_case(requirement, RobustnessCase(eta_T=eta_t))
        assert math.isfinite(r.envelope.static_margin.margin_N)
        assert math.isfinite(r.envelope.recovered_electrical.battery_current_A)
        assert math.isfinite(r.envelope.mission_energy_penalty.delta_Wh)

    for d in DIAMETER_GRID_M:
        r = evaluate_case(requirement, RobustnessCase(diameter_m=d))
        assert math.isfinite(r.envelope.rpm_recovery.rpm_required)


def test_status_constant_values_are_distinct_strings():
    from edf_sizing.robustness import (
        FAIL_CRUISE_THRUST,
        FAIL_M1_LOADING,
        FAIL_STATIC_THRUST,
        FAIL_TIP_MACH,
    )

    values = {
        FEASIBLE,
        FAIL_M1_LOADING,
        FAIL_TIP_MACH,
        FAIL_STATIC_THRUST,
        FAIL_CRUISE_THRUST,
        FAIL_ESC_CURRENT,
        FAIL_BATTERY_CURRENT,
        FAIL_MISSION_ENERGY,
    }
    assert len(values) == 8
