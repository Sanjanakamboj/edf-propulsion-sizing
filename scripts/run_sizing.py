#!/usr/bin/env python3
"""Milestone 1 engineering script: run the candidate sweep, apply the
predeclared selection rule, and print the representative static/cruise
thrust table for the selected conceptual fan.

This script only calls the `edf_sizing` package; it contains no physics of
its own. Run with:

    python3 scripts/run_sizing.py
"""

from __future__ import annotations

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.requirements import default_requirement
from edf_sizing.sizing import (
    SELECTION_RULE_DESCRIPTION,
    SelectionLimits,
    build_thrust_table,
    evaluate_candidates,
    select_fan_diameter,
)

# Illustrative, unsourced overall propulsive/fan efficiency (ideal power ->
# estimated shaft/electrical power). See DESIGN.md.
ASSUMPTION = NonIdealAssumption(eta_overall=0.75)

# Predeclared selection-rule limits (chosen before evaluating candidates).
LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


def main() -> None:
    req = default_requirement()

    print("=" * 78)
    print("Milestone 1 -- Generic representative UAV EDF propulsion requirement")
    print("(illustrative, NOT a real aircraft)")
    print("=" * 78)
    print(f"  Aircraft mass                 : {req.mass_kg:.1f} kg")
    print(f"  Weight                        : {req.weight_N:.1f} N")
    print(f"  Number of fans                : {req.n_fans}")
    print(f"  Air density (assumed)         : {req.rho_kg_m3:.3f} kg/m^3")
    print(f"  Cruise freestream speed       : {req.v_cruise_m_s:.1f} m/s")
    print(f"  Static thrust-to-weight (asm) : {req.static_thrust_to_weight:.2f}")
    print(f"  Cruise L/D (assumed)          : {req.cruise_lift_to_drag:.1f}")
    print(f"  -> Static thrust per fan      : {req.static_thrust_per_fan_N:.2f} N")
    print(f"  -> Cruise thrust per fan      : {req.cruise_thrust_per_fan_N:.2f} N")
    print()
    print(f"Non-ideal efficiency assumption : eta_overall = {ASSUMPTION.eta_overall:.2f}")
    print(f"  ({ASSUMPTION.label})")
    print()
    print("Predeclared selection rule:")
    print(f"  {SELECTION_RULE_DESCRIPTION}")
    print(f"  max disk loading  <= {LIMITS.max_disk_loading_N_m2:.1f} N/m^2")
    print(f"  max static Pi     <= {LIMITS.max_static_ideal_power_W:.1f} W")
    print()

    candidates = evaluate_candidates(req, ASSUMPTION, LIMITS)

    print("-" * 78)
    print("Candidate fan-diameter sweep (static operating point)")
    print("-" * 78)
    header = (
        f"{'D [m]':>6} {'A [m^2]':>9} {'DL [N/m^2]':>11} {'vi [m/s]':>9} "
        f"{'Pi [W]':>9} {'P_shaft* [W]':>13} {'DL ok':>6} {'P ok':>6}"
    )
    print(header)
    for c in candidates:
        print(
            f"{c.diameter_m:6.2f} {c.area_m2:9.4f} {c.disk_loading_N_m2:11.1f} "
            f"{c.vi_static_m_s:9.2f} {c.pi_static_W:9.1f} {c.p_shaft_static_est_W:13.1f} "
            f"{'yes' if c.meets_disk_loading_limit else 'no':>6} "
            f"{'yes' if c.meets_power_limit else 'no':>6}"
        )
    print("(* estimated non-ideal shaft/electrical power, illustrative eta_overall)")
    print()

    outcome = select_fan_diameter(candidates)
    print("-" * 78)
    print("Selection outcome")
    print("-" * 78)
    if outcome.success:
        sel = outcome.selected
        assert sel is not None
        print(f"  SELECTED diameter: {sel.diameter_m:.2f} m")
        print(f"    disk loading (static) : {sel.disk_loading_N_m2:.1f} N/m^2")
        print(f"    induced velocity      : {sel.vi_static_m_s:.2f} m/s")
        print(f"    ideal power (static)  : {sel.pi_static_W:.1f} W")
        print(f"    est. shaft power      : {sel.p_shaft_static_est_W:.1f} W")
    else:
        print("  NO CANDIDATE satisfies the predeclared selection rule.")
        print("  Reporting honestly: widen the candidate sweep or relax the")
        print("  illustrative limits rather than forcing a selection.")
        return

    print()
    print("-" * 78)
    print("Representative static/cruise thrust table for the selected fan")
    print("-" * 78)
    rows = build_thrust_table(req, sel.diameter_m, ASSUMPTION)
    header2 = (
        f"{'point':>8} {'V_inf [m/s]':>11} {'T [N]':>9} {'DL [N/m^2]':>11} "
        f"{'vi [m/s]':>9} {'Pi [W]':>9} {'P_shaft* [W]':>13}"
    )
    print(header2)
    for r in rows:
        print(
            f"{r.operating_point:>8} {r.v_inf_m_s:11.2f} {r.thrust_per_fan_N:9.2f} "
            f"{r.disk_loading_N_m2:11.1f} {r.vi_m_s:9.2f} {r.pi_W:9.1f} {r.p_shaft_est_W:13.1f}"
        )
    print()
    print("Reminder: generic reduced-order conceptual EDF study, not")
    print("experimentally validated and not calibrated to any real aircraft.")


if __name__ == "__main__":
    main()
