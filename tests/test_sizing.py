"""Tests for the candidate sweep, selection rule, and thrust table.

These tests check the *sizing logic* (sweep ordering, rule application,
table assembly) independently of the underlying physics, which is already
covered by test_actuator_disk.py. Where numeric values are checked, they are
recomputed by hand rather than by re-calling the module under test.
"""

from __future__ import annotations

import math

import pytest

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.requirements import UAVRequirement
from edf_sizing.sizing import (
    DEFAULT_CANDIDATE_DIAMETERS_M,
    SelectionLimits,
    build_thrust_table,
    evaluate_candidates,
    select_fan_diameter,
)


@pytest.fixture
def requirement() -> UAVRequirement:
    return UAVRequirement()


@pytest.fixture
def assumption() -> NonIdealAssumption:
    return NonIdealAssumption(eta_overall=0.75)


@pytest.fixture
def limits() -> SelectionLimits:
    return SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


def test_candidate_sweep_diameters_are_ascending():
    diameters = list(DEFAULT_CANDIDATE_DIAMETERS_M)
    assert diameters == sorted(diameters)
    assert len(set(diameters)) == len(diameters)


def test_evaluate_candidates_disk_loading_hand_check(requirement, assumption, limits):
    results = evaluate_candidates(requirement, assumption, limits, diameters_m=(0.3,))
    r = results[0]
    A_hand = math.pi * 0.3**2 / 4.0
    dl_hand = requirement.static_thrust_per_fan_N / A_hand
    assert r.disk_loading_N_m2 == pytest.approx(dl_hand, rel=1e-9)


def test_evaluate_candidates_disk_loading_decreases_with_diameter(requirement, assumption, limits):
    results = evaluate_candidates(requirement, assumption, limits)
    dls = [r.disk_loading_N_m2 for r in results]
    powers = [r.pi_static_W for r in results]
    assert all(a > b for a, b in zip(dls, dls[1:], strict=False))
    assert all(a > b for a, b in zip(powers, powers[1:], strict=False))


def test_evaluate_candidates_rejects_empty_sweep(requirement, assumption, limits):
    with pytest.raises(ValueError):
        evaluate_candidates(requirement, assumption, limits, diameters_m=())


def test_selection_rule_picks_smallest_qualifying_candidate(requirement, assumption, limits):
    candidates = evaluate_candidates(requirement, assumption, limits)
    outcome = select_fan_diameter(candidates)
    assert outcome.success

    # Hand-verify: no smaller candidate than the selected one should satisfy
    # both limits.
    selected_index = candidates.index(outcome.selected)
    for c in candidates[:selected_index]:
        assert not c.meets_selection_rule


def test_selection_rule_honestly_reports_failure_when_no_candidate_qualifies(
    requirement, assumption
):
    # Deliberately impossible limits -> nothing should qualify, and the
    # function must report failure rather than force a pick.
    impossible_limits = SelectionLimits(
        max_disk_loading_N_m2=1.0, max_static_ideal_power_W=1.0
    )
    candidates = evaluate_candidates(requirement, assumption, impossible_limits)
    outcome = select_fan_diameter(candidates)
    assert not outcome.success
    assert outcome.selected is None


def test_selection_rule_always_succeeds_with_generous_limits(requirement, assumption):
    generous_limits = SelectionLimits(
        max_disk_loading_N_m2=1e6, max_static_ideal_power_W=1e6
    )
    candidates = evaluate_candidates(requirement, assumption, generous_limits)
    outcome = select_fan_diameter(candidates)
    assert outcome.success
    # Smallest candidate diameter should be chosen when limits never bind.
    assert outcome.selected.diameter_m == min(DEFAULT_CANDIDATE_DIAMETERS_M)


def test_build_thrust_table_static_row_hand_check(requirement, assumption):
    diameter = 0.5
    rows = build_thrust_table(requirement, diameter, assumption)
    static_row = next(r for r in rows if r.operating_point == "static")

    A_hand = math.pi * diameter**2 / 4.0
    T_hand = requirement.static_thrust_per_fan_N
    vi_hand = math.sqrt(T_hand / (2.0 * requirement.rho_kg_m3 * A_hand))
    Pi_hand = T_hand * vi_hand
    P_shaft_hand = Pi_hand / assumption.eta_overall

    assert static_row.v_inf_m_s == 0.0
    assert static_row.thrust_per_fan_N == pytest.approx(T_hand, rel=1e-12)
    assert static_row.vi_m_s == pytest.approx(vi_hand, rel=1e-9)
    assert static_row.pi_W == pytest.approx(Pi_hand, rel=1e-9)
    assert static_row.p_shaft_est_W == pytest.approx(P_shaft_hand, rel=1e-9)


def test_build_thrust_table_cruise_row_thrust_equation_reconstruction(requirement, assumption):
    diameter = 0.5
    rows = build_thrust_table(requirement, diameter, assumption)
    cruise_row = next(r for r in rows if r.operating_point == "cruise")

    A = math.pi * diameter**2 / 4.0
    rho = requirement.rho_kg_m3
    V = requirement.v_cruise_m_s
    vi = cruise_row.vi_m_s
    T_reconstructed = 2.0 * rho * A * vi * (V + vi)
    assert T_reconstructed == pytest.approx(cruise_row.thrust_per_fan_N, rel=1e-6)
    assert cruise_row.v_inf_m_s == pytest.approx(V, rel=1e-12)


def test_build_thrust_table_cruise_power_less_than_static_for_default_case(
    requirement, assumption
):
    # For the default representative UAV requirement, cruise thrust per fan
    # is much lower than static thrust per fan, so ideal cruise power should
    # be lower than static ideal power despite the nonzero freestream speed.
    rows = build_thrust_table(requirement, 0.5, assumption)
    static_row = next(r for r in rows if r.operating_point == "static")
    cruise_row = next(r for r in rows if r.operating_point == "cruise")
    assert cruise_row.pi_W < static_row.pi_W
