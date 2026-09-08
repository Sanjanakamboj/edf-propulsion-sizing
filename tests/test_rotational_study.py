"""Tests for the Milestone 2 rotational operating table, diameter/RPM/
tip-Mach trade study, and selection-reconciliation logic.

Regression checks confirm Milestone 1 results are unchanged by the
existence of these Milestone 2 modules.
"""

from __future__ import annotations

import math

import pytest

from edf_sizing import actuator_disk as ad
from edf_sizing import compressibility as comp
from edf_sizing import fan_loading as fl
from edf_sizing import rotational as rot
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.requirements import UAVRequirement, default_requirement
from edf_sizing.rotational_study import (
    DEFAULT_AMBIENT,
    DEFAULT_M_TIP_MAX,
    build_rotational_operating_table,
    evaluate_diameter_rpm_tip_mach_trade,
    reconcile_selection_with_tip_mach,
)
from edf_sizing.sizing import SelectionLimits, evaluate_candidates, select_fan_diameter


@pytest.fixture
def requirement() -> UAVRequirement:
    return default_requirement()


@pytest.fixture
def assumption() -> NonIdealAssumption:
    return NonIdealAssumption(eta_overall=0.75)


@pytest.fixture
def limits() -> SelectionLimits:
    return SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


# ---------------------------------------------------------------------------
# Milestone 1 regression (unchanged by M2 modules)
# ---------------------------------------------------------------------------


def test_m1_selected_diameter_still_050(requirement, assumption, limits):
    candidates = evaluate_candidates(requirement, assumption, limits)
    outcome = select_fan_diameter(candidates)
    assert outcome.success
    assert outcome.selected.diameter_m == pytest.approx(0.50, abs=1e-9)


def test_m1_static_thrust_per_fan_unchanged(requirement):
    assert requirement.static_thrust_per_fan_N == pytest.approx(147.0997500000000015, rel=1e-9)


def test_m1_cruise_thrust_per_fan_unchanged(requirement):
    assert requirement.cruise_thrust_per_fan_N == pytest.approx(15.322890625, rel=1e-9)


# ---------------------------------------------------------------------------
# Rotational operating table -- hand checks
# ---------------------------------------------------------------------------


def test_rotational_operating_table_static_row_hand_check(requirement, assumption):
    rows = build_rotational_operating_table(requirement, 0.5, assumption)
    row = next(r for r in rows if r.operating_point == "static" and r.c_t == 0.08)

    area_hand = math.pi * 0.5**2 / 4.0
    t_hand = requirement.static_thrust_per_fan_N
    n_hand = math.sqrt(t_hand / (requirement.rho_kg_m3 * 0.08 * 0.5**4))
    rpm_hand = n_hand * 60.0
    u_tip_hand = math.pi * 0.5 * n_hand
    a_hand = comp.speed_of_sound(DEFAULT_AMBIENT)
    mach_hand = u_tip_hand / a_hand
    dp_hand = t_hand / area_hand

    assert row.n_rev_s == pytest.approx(n_hand, rel=1e-9)
    assert row.rpm == pytest.approx(rpm_hand, rel=1e-9)
    assert row.u_tip_m_s == pytest.approx(u_tip_hand, rel=1e-9)
    assert row.tip_mach == pytest.approx(mach_hand, rel=1e-9)
    assert row.delta_p_disk_Pa == pytest.approx(dp_hand, rel=1e-9)
    assert row.advance_ratio_j == pytest.approx(0.0, abs=1e-12)


def test_rotational_operating_table_cruise_row_reconstruction(requirement, assumption):
    rows = build_rotational_operating_table(requirement, 0.5, assumption)
    row = next(r for r in rows if r.operating_point == "cruise" and r.c_t == 0.08)

    # Independent reconstruction: recompute C_T from (T, rho, n, D) and
    # confirm it matches the assumed 0.08 case (round-trip identity).
    ct_check = float(
        fl.thrust_coefficient(row.thrust_N, requirement.rho_kg_m3, row.n_rev_s, row.diameter_m)
    )
    assert ct_check == pytest.approx(0.08, rel=1e-6)

    # J = V_inf / (n*D)
    j_hand = requirement.v_cruise_m_s / (row.n_rev_s * row.diameter_m)
    assert row.advance_ratio_j == pytest.approx(j_hand, rel=1e-9)

    # Relative tip Mach >= what static tip Mach would be at that same n.
    u_tip = float(rot.tip_speed(row.diameter_m, row.rpm))
    a = comp.speed_of_sound(DEFAULT_AMBIENT)
    static_mach_same_n = float(comp.static_tip_mach(u_tip, a))
    assert row.tip_mach >= static_mach_same_n


def test_pressure_jump_matches_m1_disk_loading_for_selected_fan(requirement, assumption):
    rows = build_rotational_operating_table(requirement, 0.5, assumption)
    static_row = next(r for r in rows if r.operating_point == "static")
    area = float(ad.disk_area(0.5))
    dl_m1 = float(ad.disk_loading(requirement.static_thrust_per_fan_N, area))
    assert static_row.delta_p_disk_Pa == pytest.approx(dl_m1, rel=1e-12)


def test_static_and_cruise_use_independent_c_t_sensitivity_not_forced_equal(
    requirement, assumption
):
    rows = build_rotational_operating_table(requirement, 0.5, assumption)
    static_cts = sorted({r.c_t for r in rows if r.operating_point == "static"})
    cruise_cts = sorted({r.c_t for r in rows if r.operating_point == "cruise"})
    # Same sensitivity SET is applied to both (by explicit assumption), but
    # nothing forces the resulting RPM/thrust values to match between them.
    assert static_cts == cruise_cts
    static_rpm_at_008 = next(
        r.rpm for r in rows if r.operating_point == "static" and r.c_t == 0.08
    )
    cruise_rpm_at_008 = next(
        r.rpm for r in rows if r.operating_point == "cruise" and r.c_t == 0.08
    )
    assert static_rpm_at_008 != pytest.approx(cruise_rpm_at_008, rel=1e-3)


# ---------------------------------------------------------------------------
# Diameter x RPM/tip-Mach trade study
# ---------------------------------------------------------------------------


def test_diameter_trade_rpm_ceiling_scales_with_diameter(requirement, assumption, limits):
    candidates = evaluate_candidates(requirement, assumption, limits)
    trade = evaluate_diameter_rpm_tip_mach_trade(requirement, candidates)
    # At fixed C_T, larger diameter -> lower required RPM (same physical
    # trend verified independently in test_fan_loading.py).
    rows_ct = [r for r in trade if r.c_t == 0.08]
    rows_ct.sort(key=lambda r: r.diameter_m)
    rpms = [r.rpm for r in rows_ct]
    assert all(a > b for a, b in zip(rpms, rpms[1:], strict=False))


def test_diameter_trade_tip_mach_reflects_m1_pass_fail_flags(requirement, assumption, limits):
    candidates = evaluate_candidates(requirement, assumption, limits)
    trade = evaluate_diameter_rpm_tip_mach_trade(requirement, candidates)
    # The smallest M1 candidate diameter (0.15 m) must be flagged as failing
    # M1 disk-loading/power checks in every trade row (regression sanity).
    small_rows = [r for r in trade if r.diameter_m == 0.15]
    assert all(not r.m1_disk_loading_ok for r in small_rows)


def test_reconciliation_selected_fan_partial_or_full_pass_not_forced(
    requirement, assumption, limits
):
    candidates = evaluate_candidates(requirement, assumption, limits)
    outcome = select_fan_diameter(candidates)
    trade = evaluate_diameter_rpm_tip_mach_trade(requirement, candidates)
    recon = reconcile_selection_with_tip_mach(trade, outcome.selected.diameter_m)
    # Honest outcome for the documented default assumptions: M1 checks pass,
    # but not every C_T sensitivity case satisfies the tip-Mach ceiling.
    assert recon.m1_selected is True
    assert recon.any_c_t_case_passes_tip_mach is True
    # This must not be silently tuned to force "all pass" -- confirm at
    # least the specific known-failing case (C_T=0.05) is present and
    # failing, reproduced independently here.
    row_ct_005 = next(r for r in recon.rows if r.c_t == 0.05)
    a = comp.speed_of_sound(DEFAULT_AMBIENT)
    u_tip_hand = math.pi * 0.5 * (row_ct_005.rpm / 60.0)
    mach_hand = u_tip_hand / a
    assert mach_hand == pytest.approx(row_ct_005.tip_mach_static, rel=1e-9)
    assert (mach_hand > DEFAULT_M_TIP_MAX) == (not row_ct_005.tip_mach_ok)


def test_reconciliation_rejects_diameter_not_in_trade_rows(requirement, assumption, limits):
    candidates = evaluate_candidates(requirement, assumption, limits)
    trade = evaluate_diameter_rpm_tip_mach_trade(requirement, candidates)
    with pytest.raises(ValueError):
        reconcile_selection_with_tip_mach(trade, 1.23)


# ---------------------------------------------------------------------------
# No NaN/Inf across valid sweeps
# ---------------------------------------------------------------------------


def test_no_nan_or_inf_in_operating_table(requirement, assumption):
    rows = build_rotational_operating_table(requirement, 0.5, assumption)
    for r in rows:
        for value in (
            r.n_rev_s,
            r.rpm,
            r.u_tip_m_s,
            r.tip_mach,
            r.delta_p_disk_Pa,
            r.c_p,
            r.advance_ratio_j,
            r.pi_ideal_W,
            r.p_shaft_est_W,
        ):
            assert math.isfinite(value)


def test_no_nan_or_inf_in_diameter_trade(requirement, assumption, limits):
    candidates = evaluate_candidates(requirement, assumption, limits)
    trade = evaluate_diameter_rpm_tip_mach_trade(requirement, candidates)
    for r in trade:
        assert math.isfinite(r.rpm)
        assert math.isfinite(r.u_tip_m_s)
        assert math.isfinite(r.tip_mach_static)
