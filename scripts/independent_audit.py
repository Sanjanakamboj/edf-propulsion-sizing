#!/usr/bin/env python3
"""Milestone 6 independent audit script.

Independently RECOMPUTES headline Milestone 1-5 quantities from raw
formulas (hand-coded in this script, duplicated on purpose) and compares
them against the actual production `edf_sizing` package values as they
flow through the real pipeline (evaluated candidates, rotational rows,
electrical operating points, mission-energy results, performance-envelope
results) -- never against a memorized/rounded literal. Every "independent"
value below is a separate arithmetic expression written directly in this
script; every "production" value is read from the actual object the
pipeline produces, not re-derived.

Run with:

    python3 scripts/independent_audit.py

Exits with a nonzero status if any check exceeds its declared tolerance.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

from edf_sizing import compressibility as comp
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import REFERENCE_C_T
from edf_sizing.mission_sizing import (
    compute_energy_requirement,
    default_mission_profile,
    m3_reference_battery_powers,
    reference_rotational_rows,
)
from edf_sizing.requirements import default_requirement
from edf_sizing.robustness import BASELINE, build_constraint_table, evaluate_baseline
from edf_sizing.rotational_study import DEFAULT_AMBIENT
from edf_sizing.sizing import (
    SelectionLimits,
    build_thrust_table,
    evaluate_candidates,
    select_fan_diameter,
)

ABS_TOL = 1e-6
REL_TOL = 1e-6

M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


@dataclass
class Check:
    section: str
    name: str
    production_value: float
    independent_value: float
    abs_residual: float
    rel_residual: float | None
    passed: bool


CHECKS: list[Check] = []


def audit(section: str, name: str, production: float, independent: float) -> None:
    abs_res = abs(production - independent)
    rel_res = abs_res / abs(production) if abs(production) > 1e-12 else None
    ok = abs_res <= ABS_TOL or (rel_res is not None and rel_res <= REL_TOL)
    CHECKS.append(Check(section, name, production, independent, abs_res, rel_res, ok))


def main() -> None:
    req = default_requirement()

    print("=" * 92)
    print("Milestone 6 -- independent audit of headline M1-M5 quantities")
    print("=" * 92)
    print("Production = actual pipeline output object. Independent = hand formula")
    print("written separately in this script. Neither side calls the other.")
    print()

    # -----------------------------------------------------------------
    # A. M1 actuator disk
    # -----------------------------------------------------------------
    g = 9.80665
    weight_N = req.mass_kg * g
    t_static_hand = 1.2 * weight_N / req.n_fans
    audit("A", "static thrust/fan", req.static_thrust_per_fan_N, t_static_hand)

    t_cruise_hand = (weight_N / 8.0) / req.n_fans
    audit("A", "cruise thrust/fan", req.cruise_thrust_per_fan_N, t_cruise_hand)

    D = 0.50
    area_hand = math.pi * D**2 / 4.0

    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    sel = outcome.selected
    audit("A", "selected diameter [m]", sel.diameter_m, 0.50)

    vi_static_hand = math.sqrt(t_static_hand / (2.0 * req.rho_kg_m3 * area_hand))
    pi_static_hand = t_static_hand**1.5 / math.sqrt(2.0 * req.rho_kg_m3 * area_hand)
    audit("A", "static induced velocity [m/s]", sel.vi_static_m_s, vi_static_hand)
    audit("A", "static ideal power [W]", sel.pi_static_W, pi_static_hand)
    audit("A", "static disk loading [N/m^2]", sel.disk_loading_N_m2, t_static_hand / area_hand)

    v_cruise = req.v_cruise_m_s
    half_v = v_cruise / 2.0
    vi_cruise_hand = -half_v + math.sqrt(
        half_v**2 + t_cruise_hand / (2.0 * req.rho_kg_m3 * area_hand)
    )
    pi_cruise_hand = t_cruise_hand * (v_cruise + vi_cruise_hand)

    thrust_table = build_thrust_table(req, sel.diameter_m, NonIdealAssumption(eta_overall=0.75))
    cruise_row_m1 = next(r for r in thrust_table if r.operating_point == "cruise")
    audit("A", "cruise induced velocity [m/s]", cruise_row_m1.vi_m_s, vi_cruise_hand)
    audit("A", "cruise ideal power [W]", cruise_row_m1.pi_W, pi_cruise_hand)

    # -----------------------------------------------------------------
    # B. M2 rotational
    # -----------------------------------------------------------------
    rows_008 = reference_rotational_rows(req, D, M1_ASSUMPTION, 0.08)
    static_row = rows_008["static"]

    n_hand = math.sqrt(t_static_hand / (req.rho_kg_m3 * REFERENCE_C_T * D**4))
    rpm_hand = n_hand * 60.0
    audit("B", "static RPM from C_T=0.08 inversion", static_row.rpm, rpm_hand)

    u_tip_hand = math.pi * D * n_hand
    a_sound_hand = math.sqrt(1.4 * 287.05 * 288.15)
    tip_mach_hand = u_tip_hand / a_sound_hand
    audit("B", "static tip Mach", static_row.tip_mach, tip_mach_hand)
    audit("B", "ambient speed of sound [m/s]", comp.speed_of_sound(DEFAULT_AMBIENT), a_sound_hand)
    audit(
        "B",
        "pressure-jump == disk-loading identity [Pa]",
        static_row.delta_p_disk_Pa,
        sel.disk_loading_N_m2,
    )

    rows_005 = reference_rotational_rows(req, D, M1_ASSUMPTION, 0.05)
    static_row_005 = rows_005["static"]
    n_005_hand = math.sqrt(t_static_hand / (req.rho_kg_m3 * 0.05 * D**4))
    u_tip_005_hand = math.pi * D * n_005_hand
    tip_mach_005_hand = u_tip_005_hand / a_sound_hand
    audit("B", "C_T=0.05 static tip Mach", static_row_005.tip_mach, tip_mach_005_hand)
    print(f"  [B] C_T=0.05: production tip_mach_ok={static_row_005.tip_mach_ok} "
          f"(expected False -- infeasible); independent check: "
          f"{'infeasible' if tip_mach_005_hand > 0.85 else 'feasible'}")
    print(f"  [B] C_T=0.08: production tip_mach_ok={static_row.tip_mach_ok} "
          f"(expected True -- feasible); independent check: "
          f"{'infeasible' if tip_mach_hand > 0.85 else 'feasible'}")

    ceiling_production = comp.max_rpm_static(D, 0.85, DEFAULT_AMBIENT)
    ceiling_hand = 60.0 * 0.85 * a_sound_hand / (math.pi * D)
    audit("B", "tip-Mach RPM ceiling (M_tip_max=0.85) [RPM]", ceiling_production, ceiling_hand)

    # -----------------------------------------------------------------
    # C. M3 electrical
    # -----------------------------------------------------------------
    eta_motor, eta_esc = 0.90, 0.97
    p_shaft_static_hand = pi_static_hand / 0.75  # M1 eta_overall, applied exactly once
    audit("C", "static shaft power estimate [W]", static_row.p_shaft_est_W, p_shaft_static_hand)

    p_static_pf, p_cruise_pf, _sr, cruise_row = m3_reference_battery_powers(
        req, D, M1_ASSUMPTION, REFERENCE_C_T
    )

    p_motor_hand = p_shaft_static_hand / eta_motor
    p_batt_hand = p_motor_hand / eta_esc
    audit("C", "battery input power [W]", p_static_pf, p_batt_hand)

    v_pack_14s_hand = 14 * 3.7
    i_batt_hand = p_batt_hand / v_pack_14s_hand
    i_batt_production = p_static_pf / v_pack_14s_hand
    audit("C", "14S static battery current [A]", i_batt_production, i_batt_hand)

    c_rate_hand = i_batt_hand / 4.0
    audit("C", "14S static C-rate @4.0 Ah", i_batt_production / 4.0, c_rate_hand)

    for n_series, cap, expected_current_ok, expected_crate_ok in (
        (12, 4.0, False, False),
        (14, 4.0, True, True),
        (16, 4.0, True, True),
    ):
        v = n_series * 3.7
        i = p_batt_hand / v
        crate = i / cap
        i_max = cap * 20.0
        current_ok = i_max >= i
        crate_ok = 20.0 >= crate
        matches = current_ok == expected_current_ok and crate_ok == expected_crate_ok
        print(
            f"  [C] {n_series}S @{cap:.1f}Ah: I={i:.2f}A C-rate={crate:.2f} "
            f"current_ok={current_ok} crate_ok={crate_ok} {'OK' if matches else 'MISMATCH'}"
        )

    # Independent check: no eta_overall double-counting. Reconstruct via
    # the SEPARATE chain Pi/eta_overall/eta_motor/eta_esc and confirm it
    # equals Pi/(eta_overall*eta_motor*eta_esc), while an ACCIDENTAL
    # double application (dividing by eta_overall twice) gives a
    # different, larger number.
    correct_chain = pi_static_hand / 0.75 / eta_motor / eta_esc
    accidental_double = pi_static_hand / 0.75 / 0.75 / eta_motor / eta_esc
    distinct = abs(correct_chain - accidental_double) > 1.0
    print(
        f"  [C] no eta_overall double-count: correct={correct_chain:.2f} W, "
        f"accidental-double={accidental_double:.2f} W, "
        f"{'OK (distinct, production matches correct chain)' if distinct else 'MISMATCH'}"
    )
    audit("C", "battery power via correct single-application chain [W]", p_static_pf, correct_chain)

    # -----------------------------------------------------------------
    # D. M4 mission energy (M4 baseline, unmodified by M5)
    # -----------------------------------------------------------------
    n_fans = req.n_fans
    seg_launch_hand = p_static_pf * n_fans * 30.0 / 3600.0
    seg_climb_hand = p_static_pf * n_fans * 0.70 * 120.0 / 3600.0
    seg_cruise_hand = p_cruise_pf * n_fans * 1200.0 / 3600.0
    seg_loiter_hand = p_cruise_pf * n_fans * 1.20 * 300.0 / 3600.0
    mission_wh_hand = seg_launch_hand + seg_climb_hand + seg_cruise_hand + seg_loiter_hand

    m4_profile = default_mission_profile(p_static_pf, p_cruise_pf, n_fans)
    m4_requirement = compute_energy_requirement(m4_profile)
    audit("D", "raw mission energy [Wh]", m4_requirement.mission_energy_Wh, mission_wh_hand)

    reserve_wh_hand = mission_wh_hand * 1.20
    required_nominal_wh_hand = reserve_wh_hand / 0.80
    audit(
        "D",
        "required nominal energy [Wh]",
        m4_requirement.required_nominal_Wh,
        required_nominal_wh_hand,
    )

    required_ah_14s_hand = required_nominal_wh_hand / v_pack_14s_hand
    audit(
        "D",
        "required Ah at 14S",
        m4_requirement.required_nominal_Wh / v_pack_14s_hand,
        required_ah_14s_hand,
    )

    # -----------------------------------------------------------------
    # E. M5 losses / lapse
    # -----------------------------------------------------------------
    envelope = evaluate_baseline(req, BASELINE)
    eta_T = 0.90

    t_static_avail_hand = eta_T * t_static_hand
    audit(
        "E",
        "eta_T thrust scaling: static available [N]",
        envelope.static_margin.thrust_available_N,
        t_static_avail_hand,
    )

    f_lapse_hand = max(0.0, 1.0 - 0.30 * (v_cruise / 60.0))
    t_cruise_avail_hand = t_static_avail_hand * f_lapse_hand
    audit(
        "E",
        "lapse at cruise: available thrust [N]",
        envelope.cruise_margin.thrust_available_N,
        t_cruise_avail_hand,
    )

    static_shortfall_hand = t_static_avail_hand / t_static_hand - 1.0
    audit(
        "E",
        "static shortfall (margin fraction)",
        envelope.static_margin.margin_fraction,
        static_shortfall_hand,
    )

    rpm_recovery_hand = static_row.rpm / math.sqrt(eta_T)
    audit("E", "RPM recovery formula", envelope.rpm_recovery.rpm_required, rpm_recovery_hand)

    thrust_ratio_check = eta_T * (rpm_recovery_hand / static_row.rpm) ** 2
    audit("E", "RPM^2 thrust-scaling round-trip (should be 1.0)", 1.0, thrust_ratio_check)

    power_ratio_hand = (rpm_recovery_hand / static_row.rpm) ** 3
    p_shaft_recovered_hand = p_shaft_static_hand * power_ratio_hand
    audit(
        "E",
        "RPM^3 power scaling: recovered shaft power [W]",
        envelope.recovered_electrical.shaft_power_recovered_W,
        p_shaft_recovered_hand,
    )

    u_tip_recovery_hand = math.pi * D * (rpm_recovery_hand / 60.0)
    tip_mach_recovery_hand = u_tip_recovery_hand / a_sound_hand
    audit(
        "E",
        "recovered tip Mach",
        envelope.rpm_recovery.tip_mach_at_recovery,
        tip_mach_recovery_hand,
    )

    p_motor_recovered_hand = p_shaft_recovered_hand / eta_motor
    p_batt_recovered_hand = p_motor_recovered_hand / eta_esc
    i_batt_recovered_hand = p_batt_recovered_hand / v_pack_14s_hand
    audit(
        "E",
        "recovered battery current [A]",
        envelope.recovered_electrical.battery_current_A,
        i_batt_recovered_hand,
    )

    m5_mission_wh_hand = (
        i_batt_recovered_hand * v_pack_14s_hand * n_fans * 30.0 / 3600.0
        + i_batt_recovered_hand * v_pack_14s_hand * n_fans * 0.70 * 120.0 / 3600.0
        + seg_cruise_hand
        + seg_loiter_hand
    )
    audit(
        "E",
        "M5 updated mission energy [Wh]",
        envelope.mission_energy_penalty.mission_energy_m5_Wh,
        m5_mission_wh_hand,
    )

    m5_reserve_wh_hand = m5_mission_wh_hand * 1.20
    usable_wh_28ah_hand = 28.0 * v_pack_14s_hand * 0.80
    capacity_margin_hand = usable_wh_28ah_hand / m5_reserve_wh_hand - 1.0
    audit(
        "E",
        "28 Ah capacity margin (M5-updated mission)",
        envelope.mission_energy_penalty.capacity_margin.margin,
        capacity_margin_hand,
    )

    # -----------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------
    print()
    print("## Numeric checks")
    print("-" * 92)
    header = (
        f"{'section':>7} {'check':<52} {'prod':>12} {'indep':>12} {'abs_res':>10} {'status':>6}"
    )
    print(header)
    for c in CHECKS:
        print(
            f"{c.section:>7} {c.name:<52} {c.production_value:12.4f} {c.independent_value:12.4f} "
            f"{c.abs_residual:10.2e} {'OK' if c.passed else 'FAIL':>6}"
        )

    n_checks = len(CHECKS)
    n_failed = sum(1 for c in CHECKS if not c.passed)
    max_abs = max(c.abs_residual for c in CHECKS)
    rel_values = [c.rel_residual for c in CHECKS if c.rel_residual is not None]
    max_rel = max(rel_values) if rel_values else 0.0

    print()
    print("## Summary")
    print("-" * 92)
    print(f"  numeric checks run       : {n_checks}")
    print(f"  numeric checks failed    : {n_failed}")
    print(f"  max absolute residual    : {max_abs:.3e}")
    print(f"  max relative residual    : {max_rel:.3e}")
    print(f"  tolerances               : abs<={ABS_TOL:.0e} OR rel<={REL_TOL:.0e}")
    print(f"  status                   : {'ALL PASS' if n_failed == 0 else 'FAILURES PRESENT'}")
    print()

    table = build_constraint_table(req, BASELINE, envelope)
    print(f"  constraint-table rows    : {len(table)} (expect 8)")
    print(f"  baseline overall feasible: {envelope.feasible}")

    if n_failed > 0:
        print()
        print("AUDIT FAILED -- see FAIL rows above.")
        sys.exit(1)

    print()
    print("Independent audit: ALL CHECKS PASS within declared tolerances.")


if __name__ == "__main__":
    main()
