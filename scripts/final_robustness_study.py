#!/usr/bin/env python3
"""Milestone 6 engineering script: final robustness audit, boundary
analysis, sensitivity ranking, and diameter trade for the frozen
Milestone 1-5 architecture.

This is a reduced-order robustness study, not experimental validation or
flight qualification. This script only calls the `edf_sizing` package
(Milestone 1-6 modules); it contains no physics of its own. Run with:

    python3 scripts/final_robustness_study.py
"""

from __future__ import annotations

from collections import Counter

from edf_sizing import compressibility as comp
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import reference_rotational_rows
from edf_sizing.requirements import default_requirement
from edf_sizing.robustness import (
    BASELINE,
    CRUISE_DURATION_GRID_S,
    ETA_T_GRID,
    build_constraint_table,
    evaluate_baseline,
    find_max_cruise_duration_s,
    find_min_feasible_eta_esc,
    find_min_feasible_eta_motor,
    find_min_feasible_eta_t,
    find_min_required_capacity_Ah,
    max_recoverable_thrust_loss_fraction,
    rank_sensitivities,
    sweep_diameter,
    sweep_grid,
)
from edf_sizing.rotational_study import DEFAULT_AMBIENT


def main() -> None:
    req = default_requirement()

    print("=" * 96)
    print("Milestone 6 -- final robustness study")
    print("=" * 96)
    print("This is a reduced-order robustness study, not experimental validation or")
    print("flight qualification.")
    print("Sensitivity ranges are deterministic engineering cases, not probability")
    print("distributions.")
    print()

    print("## Final inherited architecture")
    print("-" * 96)
    print(f"  D = {BASELINE.diameter_m:.2f} m   reference C_T = {BASELINE.reference_c_t:.2f}")
    ceiling = comp.max_rpm_static(BASELINE.diameter_m, BASELINE.m_tip_max, DEFAULT_AMBIENT)
    m1_assumption = NonIdealAssumption(eta_overall=BASELINE.eta_overall)
    rows = reference_rotational_rows(
        req, BASELINE.diameter_m, m1_assumption, BASELINE.reference_c_t
    )
    static_row = rows["static"]
    print(f"  static RPM (reference) = {static_row.rpm:.0f}   "
          f"tip Mach (reference RPM) = {static_row.tip_mach:.3f}")
    print(f"  M_tip,max = {BASELINE.m_tip_max:.2f}   tip-Mach RPM ceiling = {ceiling:.1f}")
    print(f"  14S = {14 * 3.7:.1f} V nominal   capacity = {BASELINE.capacity_Ah:.1f} Ah")
    print(f"  eta_T = {BASELINE.eta_T:.2f}   eta_motor = {BASELINE.eta_motor:.2f}   "
          f"eta_ESC = {BASELINE.eta_esc:.2f}")
    print()

    print("## Constraint table")
    print("-" * 96)
    envelope = evaluate_baseline(req, BASELINE)
    table = build_constraint_table(req, BASELINE, envelope)
    header = f"{'constraint':<48}{'MS':>6}{'value':>12}{'limit':>12}{'margin':>10}{'status':>8}"
    print(header)
    for row in table:
        print(
            f"{row.name:<48}{row.milestone:>6}{row.value:12.2f}{row.limit:12.2f}"
            f"{row.margin:10.3f}{row.status:>8}"
        )
    print(f"  -> overall feasible (via RPM recovery): {envelope.feasible}")
    print()

    print("## Key boundaries")
    print("-" * 96)
    eta_t_min = find_min_feasible_eta_t(req)
    max_cruise = find_max_cruise_duration_s(req)
    min_eta_motor = find_min_feasible_eta_motor(req)
    min_eta_esc = find_min_feasible_eta_esc(req)
    min_capacity = find_min_required_capacity_Ah(req)
    max_loss_fraction = max_recoverable_thrust_loss_fraction(req)
    print(f"  eta_T,min (fully feasible)          = {eta_t_min:.4f}  "
          f"(baseline {BASELINE.eta_T:.2f})")
    print(f"  max cruise duration (28 Ah margin>=0) = {max_cruise:.1f} s "
          f"({max_cruise / 60.0:.2f} min, baseline "
          f"{BASELINE.cruise_duration_s / 60.0:.0f} min)")
    print(f"  min eta_motor (current-feasible)    = {min_eta_motor:.4f}  "
          f"(baseline {BASELINE.eta_motor:.2f})")
    print(f"  min eta_ESC (current-feasible)      = {min_eta_esc:.4f}  "
          f"(baseline {BASELINE.eta_esc:.2f})")
    print(f"  min capacity @ baseline eta_T=0.90  = {min_capacity:.2f} Ah  "
          f"(selected {BASELINE.capacity_Ah:.1f} Ah)")
    print(f"  max static RPM (M_tip,max={BASELINE.m_tip_max:.2f})   = {ceiling:.1f} RPM")
    print(f"  max recoverable thrust-loss fraction (RPM-limited) = {max_loss_fraction:.4f} "
          f"(eta_T down to {1 - max_loss_fraction:.4f})")
    print()

    print("## Robustness grid (eta_T x cruise duration)")
    print("-" * 96)
    grid = sweep_grid(req, ETA_T_GRID, CRUISE_DURATION_GRID_S)
    n_feasible = sum(1 for r in grid if r.feasible)
    n_total = len(grid)
    n_infeasible = n_total - n_feasible
    print(f"  cases evaluated: {n_total}   feasible: {n_feasible}   infeasible: {n_infeasible}")
    failure_counts = Counter(r.governing_failure for r in grid if not r.feasible)
    for failure, count in failure_counts.most_common():
        print(f"    governing failure {failure}: {count} case(s)")
    print()

    print("## Diameter comparison")
    print("-" * 96)
    diam_results = sweep_diameter(req)
    header2 = (
        f"{'D [m]':>7}{'M1 ok':>8}{'RPM req':>10}{'tip Mach':>10}"
        f"{'I [A]':>9}{'E margin':>10}{'feasible':>10}"
    )
    print(header2)
    for r in diam_results:
        rr = r.envelope.rpm_recovery
        print(
            f"{r.case.diameter_m:7.2f}{'yes' if r.m1_ok else 'NO':>8}"
            f"{rr.rpm_required:10.0f}{rr.tip_mach_at_recovery:10.3f}"
            f"{r.envelope.recovered_electrical.battery_current_A:9.2f}"
            f"{r.envelope.mission_energy_penalty.capacity_margin.margin:10.3f}"
            f"{'yes' if r.feasible else 'NO':>10}"
        )
    smallest_viable = next((r for r in diam_results if r.feasible), None)
    print(
        f"  -> smallest viable diameter under baseline M5 losses: "
        f"{smallest_viable.case.diameter_m:.2f} m"
        if smallest_viable
        else "  -> NO diameter in the tested set is viable"
    )
    print(
        f"  -> matches M1 selection (0.50 m): "
        f"{smallest_viable.case.diameter_m == 0.50 if smallest_viable else False}"
    )
    print()

    print("## Sensitivity ranking (computed, not asserted)")
    print("-" * 96)
    rankings = rank_sensitivities(req)
    header3 = f"{'rank':>4}{'parameter':<20}{'range':<28}{'swing':>10}{'flips?':>8}"
    print(header3)
    for rk in rankings:
        range_str = str(tuple(round(v, 2) for v in rk.tested_range))
        print(f"{rk.rank:>4}{rk.parameter:<20}{range_str:<28}{rk.max_fractional_swing:10.3f}{str(rk.feasibility_flips):>8}")
    print()

    print("## Final engineering conclusion")
    print("-" * 96)
    baseline_feasible = envelope.feasible
    status_word = "FEASIBLE" if baseline_feasible else "INFEASIBLE"
    print(
        f"  Baseline architecture (D={BASELINE.diameter_m:.2f} m, "
        f"C_T={BASELINE.reference_c_t:.2f}, 14S, {BASELINE.capacity_Ah:.0f} Ah, "
        f"eta_T={BASELINE.eta_T:.2f}) is {status_word} within the tested"
    )
    print("  reduced-order baseline.")
    print(
        "  This means the architecture is feasible within the tested reduced-order baseline --"
    )
    print("  it is NOT validated and NOT optimized.")
    # NOTE: constraint-table rows C and G are deliberately PRE-RECOVERY
    # diagnostics (reference-RPM tip Mach / raw static thrust) -- they are
    # always tight/negative whenever eta_T<1 by construction, and are
    # NOT part of the actual post-recovery feasibility gate set. The real
    # "governing" (tightest binding) constraint is the smallest margin
    # among the gates `RobustnessResult` actually evaluates: ESC current,
    # battery current, mission energy, cruise thrust, and RPM-recovery
    # headroom (not itself a table row).
    rr = envelope.rpm_recovery
    rpm_headroom_fraction = (rr.rpm_ceiling - rr.rpm_required) / rr.rpm_ceiling
    post_recovery_margins = {
        "D. M3 ESC current": envelope.recovered_electrical.esc_current_margin.margin,
        "E. M3 battery current/C-rate": envelope.recovered_electrical.battery_current_margin.margin,
        "F. M4/M5 mission energy capacity": envelope.mission_energy_penalty.capacity_margin.margin,
        "H. M5 cruise thrust": envelope.cruise_margin.margin_fraction,
        "RPM-recovery / tip-Mach headroom": rpm_headroom_fraction,
    }
    governing_name = min(post_recovery_margins, key=post_recovery_margins.get)
    print(f"  Governing (smallest post-recovery margin) constraint: {governing_name} "
          f"(margin {post_recovery_margins[governing_name]:+.3f})")
    print(
        "  (Row G above is the honest PRE-recovery diagnostic -- it is always negative"
    )
    print(
        "   whenever eta_T<1 by construction and is not itself a feasibility gate;"
    )
    print("   feasibility gate (3) is satisfied via RPM recovery instead, see DESIGN.md.)")
    top_rank = rankings[0]
    print(f"  Strongest assumption (largest sensitivity swing): {top_rank.parameter} "
          f"(swing {top_rank.max_fractional_swing:.3f})")
    headroom_frac = (max_cruise - BASELINE.cruise_duration_s) / BASELINE.cruise_duration_s
    print(
        f"  Strongest failure boundary (closest to baseline): max cruise duration "
        f"at {max_cruise:.0f} s"
    )
    print(
        f"  (baseline {BASELINE.cruise_duration_s:.0f} s, only {headroom_frac:+.1%} headroom)"
    )
    print()
    print("Reminder: generic reduced-order conceptual EDF study, not experimentally")
    print("validated and not a real product or flight-qualified architecture.")


if __name__ == "__main__":
    main()
