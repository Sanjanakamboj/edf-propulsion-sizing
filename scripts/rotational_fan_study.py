#!/usr/bin/env python3
"""Milestone 2 engineering script: RPM, blade-tip Mach, and reduced-order
fan-loading study for the Milestone 1 selected 0.50 m EDF.

This script only calls the `edf_sizing` package (Milestone 1 + Milestone 2
modules); it contains no physics of its own. Run with:

    python3 scripts/rotational_fan_study.py
"""

from __future__ import annotations

from edf_sizing import compressibility as comp
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.requirements import default_requirement
from edf_sizing.rotational_study import (
    C_T_SENSITIVITY_CASES,
    DEFAULT_AMBIENT,
    DEFAULT_M_TIP_MAX,
    M_TIP_MAX_SENSITIVITY,
    build_rotational_operating_table,
    evaluate_diameter_rpm_tip_mach_trade,
    reconcile_selection_with_tip_mach,
)
from edf_sizing.sizing import (
    SelectionLimits,
    evaluate_candidates,
    select_fan_diameter,
)

# Same illustrative M1 assumption/limits used in scripts/run_sizing.py.
M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


def main() -> None:
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot run Milestone 2 study.")
    sel = outcome.selected
    a_sound = comp.speed_of_sound(DEFAULT_AMBIENT)

    print("=" * 88)
    print("Milestone 2 -- RPM / tip-Mach / reduced-order fan-loading study")
    print("=" * 88)
    print("1. Inherited Milestone 1 selected fan and operating points")
    print("-" * 88)
    print(f"  Selected diameter          : {sel.diameter_m:.2f} m (A = {sel.area_m2:.4f} m^2)")
    print(f"  Static thrust/fan          : {req.static_thrust_per_fan_N:.2f} N")
    print(f"  Static disk loading        : {sel.disk_loading_N_m2:.1f} N/m^2")
    print(f"  Static ideal power         : {sel.pi_static_W:.1f} W")
    print(f"  Static est. shaft power    : {sel.p_shaft_static_est_W:.1f} W")
    print(f"  Cruise speed               : {req.v_cruise_m_s:.1f} m/s")
    print(f"  Cruise thrust/fan          : {req.cruise_thrust_per_fan_N:.2f} N")
    print()

    print("2. Source-audited coefficient convention (see DESIGN.md Milestone 2)")
    print("-" * 88)
    print("  C_T = T / (rho * n^2 * D^4)      n in rev/s, D in meters")
    print("  C_P = P / (rho * n^3 * D^5)      P = M1 estimated shaft power (bookkeeping)")
    print("  J   = V_inf / (n * D)")
    print("  U_tip = pi * D * n                (rotational tip speed)")
    print("  M_tip,static = U_tip / a ;  M_tip,rel = sqrt(U_tip^2 + V_inf^2) / a")
    print()

    print("3. Ambient speed of sound")
    print("-" * 88)
    print(
        f"  T = {DEFAULT_AMBIENT.temperature_K:.2f} K (ISA sea level, consistent with "
        f"M1 rho=1.225 kg/m^3), gamma = {DEFAULT_AMBIENT.gamma:.2f}, "
        f"R = {DEFAULT_AMBIENT.r_specific_J_per_kgK:.2f} J/(kg*K)"
    )
    print(f"  -> a = {a_sound:.2f} m/s")
    print()

    print("4. Tip-Mach limit assumption/sensitivity (ILLUSTRATIVE, not a sourced")
    print("   universal EDF limit -- informed by conventional-propeller design")
    print("   practice ~0.8-0.9; see DESIGN.md)")
    print("-" * 88)
    print(f"  Baseline M_tip,max = {DEFAULT_M_TIP_MAX:.2f}")
    print(f"  Sensitivity set    = {M_TIP_MAX_SENSITIVITY}")
    print()

    print("5-9. Static & cruise rotational operating table for the selected fan")
    print("     (C_T sensitivity cases, ILLUSTRATIVE/unsourced -- see DESIGN.md)")
    print("-" * 88)
    rows = build_rotational_operating_table(
        req,
        sel.diameter_m,
        M1_ASSUMPTION,
        DEFAULT_AMBIENT,
        DEFAULT_M_TIP_MAX,
        C_T_SENSITIVITY_CASES,
    )
    header = (
        f"{'point':>7} {'C_T':>6} {'V_inf':>6} {'T [N]':>8} {'RPM':>8} {'U_tip':>7} "
        f"{'Mach':>6} {'ok?':>4} {'dp [Pa]':>9} {'C_P':>9} {'J':>6} "
        f"{'Pi [W]':>8} {'Psh* [W]':>9}"
    )
    print(header)
    for r in rows:
        print(
            f"{r.operating_point:>7} {r.c_t:6.2f} {r.v_inf_m_s:6.1f} {r.thrust_N:8.2f} "
            f"{r.rpm:8.0f} {r.u_tip_m_s:7.1f} {r.tip_mach:6.3f} "
            f"{'yes' if r.tip_mach_ok else 'NO':>4} {r.delta_p_disk_Pa:9.1f} "
            f"{r.c_p:9.4f} {r.advance_ratio_j:6.3f} {r.pi_ideal_W:8.1f} {r.p_shaft_est_W:9.1f}"
        )
    print(
        "  (RPM inferred independently per C_T case from T,rho,D; C_P uses the M1\n"
        "   estimated shaft power at that RPM -- a nondimensional bookkeeping\n"
        "   exercise, NOT a physically matched propeller/fan performance map.)"
    )
    print()

    print("10. Diameter x RPM/tip-Mach trade across the full M1 candidate sweep")
    print("-" * 88)
    trade = evaluate_diameter_rpm_tip_mach_trade(
        req, candidates, DEFAULT_AMBIENT, DEFAULT_M_TIP_MAX, C_T_SENSITIVITY_CASES
    )
    header2 = (
        f"{'D [m]':>6} {'DL ok':>6} {'P ok':>5} {'C_T':>6} {'RPM':>8} {'U_tip':>7} "
        f"{'Mach':>6} {'Mtip ok':>8} {'fully ok':>9}"
    )
    print(header2)
    for r in trade:
        print(
            f"{r.diameter_m:6.2f} {'yes' if r.m1_disk_loading_ok else 'no':>6} "
            f"{'yes' if r.m1_power_ok else 'no':>5} {r.c_t:6.2f} {r.rpm:8.0f} "
            f"{r.u_tip_m_s:7.1f} {r.tip_mach_static:6.3f} "
            f"{'yes' if r.tip_mach_ok else 'NO':>8} {'yes' if r.fully_admissible else 'no':>9}"
        )
    print()

    print("Reconciliation: does M2 change the M1 diameter selection?")
    print("-" * 88)
    recon = reconcile_selection_with_tip_mach(trade, sel.diameter_m)
    print(f"  {recon.verdict}")
    print()
    print("Reminder: generic reduced-order conceptual EDF study, not")
    print("experimentally validated and not calibrated to any real aircraft or EDF unit.")


if __name__ == "__main__":
    main()
