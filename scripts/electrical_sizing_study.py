#!/usr/bin/env python3
"""Milestone 3 engineering script: motor/ESC/battery electrical sizing for
the Milestone 1/2 selected 0.50 m EDF at its M2 reference rotational case.

This script only calls the `edf_sizing` package (Milestone 1 + 2 + 3
modules); it contains no physics of its own. Run with:

    python3 scripts/electrical_sizing_study.py
"""

from __future__ import annotations

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel
from edf_sizing.electrical_sizing import (
    CAPACITY_SENSITIVITY_AH,
    DEFAULT_C_RATE_LIMIT,
    DEFAULT_CAPACITY_AH,
    DEFAULT_ESC_I_MAX_A,
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    DEFAULT_MOTOR_RATED_ELECTRICAL_POWER_W,
    DEFAULT_PACK_SERIES_CANDIDATES,
    ESC_I_MAX_SENSITIVITY_A,
    ETA_ESC_SENSITIVITY,
    ETA_MOTOR_SENSITIVITY,
    HISTORICAL_INFEASIBLE_C_T,
    REFERENCE_C_T,
    SENSITIVITY_C_T_CASES,
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
from edf_sizing.sizing import SelectionLimits, evaluate_candidates, select_fan_diameter

M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


def _print_point_row(label: str, pt) -> None:
    ok = "ok" if pt.tip_mach_ok else "FAIL"
    print(
        f"  {label:<8} T={pt.thrust_N:7.2f} N  RPM={pt.rpm:7.0f}  "
        f"Q={pt.shaft_torque_Nm:6.3f} N*m  Mtip={pt.tip_mach:5.3f} ({ok})"
    )
    print(
        f"           P_shaft={pt.shaft_power_W:7.1f} W  "
        f"P_motor={pt.motor_electrical_power_W:7.1f} W  "
        f"P_batt={pt.battery_power_W:7.1f} W"
    )
    print(
        f"           V_pack={pt.pack_v_nom_V:5.1f} V ({pt.pack_n_series}S)  "
        f"I_batt={pt.battery_current_A:6.2f} A  C-rate={pt.c_rate_required:5.2f}"
    )
    esc_ok = "ok" if pt.esc_current_margin.ok else "FAIL"
    batt_ok = "ok" if pt.battery_current_margin.ok else "FAIL"
    crate_ok = "ok" if pt.c_rate_margin.ok else "FAIL"
    print(
        f"           margins: ESC_I={pt.esc_current_margin.margin:+.3f} ({esc_ok})  "
        f"batt_I={pt.battery_current_margin.margin:+.3f} ({batt_ok})  "
        f"C-rate={pt.c_rate_margin.margin:+.3f} ({crate_ok})"
    )


def main() -> None:
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot run Milestone 3 study.")
    sel_d = outcome.selected.diameter_m

    print("=" * 92)
    print("Milestone 3 -- motor / ESC / battery electrical sizing study")
    print("=" * 92)
    print("This is a reduced-order electrical sizing study, not a validated")
    print("motor/ESC/battery selection.")
    print()

    print("## Inherited EDF design")
    print("-" * 92)
    rows_ref = reference_rotational_rows(req, sel_d, M1_ASSUMPTION, c_t=REFERENCE_C_T)
    static_ref = rows_ref["static"]
    cruise_ref = rows_ref["cruise"]
    print(f"  Selected diameter D = {sel_d:.2f} m")
    print(f"  Static thrust/fan   = {req.static_thrust_per_fan_N:.2f} N")
    print(f"  Cruise thrust/fan   = {req.cruise_thrust_per_fan_N:.2f} N")
    print(f"  Static shaft power  = {static_ref.p_shaft_est_W:.1f} W (M1 P_shaft_est)")
    print(f"  Cruise shaft power  = {cruise_ref.p_shaft_est_W:.1f} W (M1 P_shaft_est)")
    print(
        f"  M2 reference C_T = {REFERENCE_C_T:.2f} (middle sensitivity case, "
        "passes M2 tip-Mach screen)"
    )
    print(f"    static RPM={static_ref.rpm:.0f}  tip Mach={static_ref.tip_mach:.3f}")
    print(f"    cruise RPM={cruise_ref.rpm:.0f}  tip Mach={cruise_ref.tip_mach:.3f}")
    rows_005 = reference_rotational_rows(
        req, sel_d, M1_ASSUMPTION, c_t=HISTORICAL_INFEASIBLE_C_T
    )
    print(
        f"  (historical: C_T={HISTORICAL_INFEASIBLE_C_T:.2f} static tip Mach="
        f"{rows_005['static'].tip_mach:.3f} -- still M2-infeasible under "
        f"M_tip,max={DEFAULT_M_TIP_MAX:.2f}, not erased)"
    )
    print()

    print("## Electrical assumptions (ILLUSTRATIVE unless noted)")
    print("-" * 92)
    print(f"  eta_motor (baseline)  = {DEFAULT_ETA_MOTOR:.2f}  sensitivity {ETA_MOTOR_SENSITIVITY}")
    print(f"  eta_ESC (baseline)    = {DEFAULT_ETA_ESC:.2f}  sensitivity {ETA_ESC_SENSITIVITY}")
    motor_pwr = DEFAULT_MOTOR_RATED_ELECTRICAL_POWER_W
    print(f"  motor rated elec pwr  = {motor_pwr:.0f} W (illustrative)")
    print(f"  ESC continuous I max  = {DEFAULT_ESC_I_MAX_A:.0f} A  sens {ESC_I_MAX_SENSITIVITY_A}")
    print("  Battery chemistry (SOURCED generic LiPo convention):")
    print("    3.7 V nominal/cell, 4.2 V full-charge/cell, 3.0 V minimum/cell")
    print("    (see DESIGN.md for the source audit).")
    print(f"  Candidate series counts  = {DEFAULT_PACK_SERIES_CANDIDATES}")
    print(
        f"  Pack capacity (baseline) = {DEFAULT_CAPACITY_AH:.1f} Ah  "
        f"sens {CAPACITY_SENSITIVITY_AH}"
    )
    print(f"  Pack continuous C-rate limit (illustrative) = {DEFAULT_C_RATE_LIMIT:.0f}C")
    print()

    motor = default_motor_assumptions()
    esc = default_esc_model()
    baseline_pack = make_pack(14)

    print("## Static electrical chain (governing operating point, 14S baseline)")
    print("-" * 92)
    pt_static = build_electrical_operating_point(static_ref, motor, esc, baseline_pack)
    _print_point_row("static", pt_static)
    print()

    print("## Cruise electrical chain (14S baseline)")
    print("-" * 92)
    pt_cruise = build_electrical_operating_point(cruise_ref, motor, esc, baseline_pack)
    _print_point_row("cruise", pt_cruise)
    print()

    print("## Pack-voltage trade (static operating point, governing case)")
    print("-" * 92)
    header = (
        f"{'S':>3} {'Vnom':>6} {'Vfull':>6} {'I_batt':>7} {'C-rate':>7} "
        f"{'ESCmgn':>7} {'battmgn':>8} {'Cratemgn':>9} {'allok?':>7}"
    )
    print(header)
    packs = [make_pack(n) for n in DEFAULT_PACK_SERIES_CANDIDATES]
    for pack in packs:
        pt = build_electrical_operating_point(static_ref, motor, esc, pack)
        ok = "yes" if pt.all_gates_ok else "NO"
        print(
            f"{pt.pack_n_series:>3} {pt.pack_v_nom_V:6.1f} {pt.pack_v_full_V:6.1f} "
            f"{pt.battery_current_A:7.2f} {pt.c_rate_required:7.2f} "
            f"{pt.esc_current_margin.margin:+7.3f} {pt.battery_current_margin.margin:+8.3f} "
            f"{pt.c_rate_margin.margin:+9.3f} {ok:>7}"
        )
    print()

    print("## Predeclared pack-selection rule")
    print("-" * 92)
    outcome_elec = select_pack(static_ref, motor, esc, packs)
    print(f"  {outcome_elec.rule_description}")
    if outcome_elec.success:
        sel_pack = outcome_elec.selected
        print(
            f"  -> SELECTED: {sel_pack.pack_n_series}S "
            f"({sel_pack.pack_v_nom_V:.1f} V nominal)"
        )
    else:
        print("  -> NO candidate pack satisfies all gates -- reporting honestly.")
    print()

    print("## Sensitivities")
    print("-" * 92)
    print("  A. eta_motor sensitivity (14S, cap=4.0 Ah, static):")
    for e in ETA_MOTOR_SENSITIVITY:
        m = MotorAssumptions(eta_motor=e, rated_electrical_power_W=4500.0)
        pt = build_electrical_operating_point(static_ref, m, esc, baseline_pack)
        print(f"    eta_motor={e:.2f}  I_batt={pt.battery_current_A:6.2f} A  ok={pt.all_gates_ok}")

    print("  B. eta_ESC sensitivity (14S, cap=4.0 Ah, static):")
    for e in ETA_ESC_SENSITIVITY:
        esc_e = ESCModel(eta_esc=e, i_esc_max_A=DEFAULT_ESC_I_MAX_A)
        pt = build_electrical_operating_point(static_ref, motor, esc_e, baseline_pack)
        print(f"    eta_ESC={e:.2f}  I_batt={pt.battery_current_A:6.2f} A  ok={pt.all_gates_ok}")

    print("  C. pack series-count (already shown above in Pack-voltage trade)")

    print("  D. capacity sensitivity (14S, static):")
    for cap in CAPACITY_SENSITIVITY_AH:
        pack_cap = make_pack(14, capacity_Ah=cap)
        pt = build_electrical_operating_point(static_ref, motor, esc, pack_cap)
        print(f"    capacity={cap:.1f} Ah  C-rate={pt.c_rate_required:5.2f}  ok={pt.all_gates_ok}")

    print(f"  E. M2 C_T/RPM case sensitivity {SENSITIVITY_C_T_CASES} (14S, static):")
    for c_t in SENSITIVITY_C_T_CASES:
        rows_ct = reference_rotational_rows(req, sel_d, M1_ASSUMPTION, c_t=c_t)
        pt = build_electrical_operating_point(rows_ct["static"], motor, esc, baseline_pack)
        mach_ok = "ok" if pt.tip_mach_ok else "FAIL"
        print(
            f"    C_T={c_t:.2f}  RPM={pt.rpm:7.0f}  Mtip={pt.tip_mach:.3f} ({mach_ok})  "
            f"I_batt={pt.battery_current_A:6.2f} A  ok={pt.all_gates_ok}"
        )
    print(
        f"    (C_T={HISTORICAL_INFEASIBLE_C_T:.2f} retained as M2-tip-Mach-infeasible, "
        "not evaluated electrically as a valid case)"
    )
    print(
        "    Note: battery current/power here depend only on required THRUST (via"
    )
    print(
        "    M1 P_shaft_est), not on the assumed C_T -- C_T only sets RPM/torque/tip"
    )
    print("    Mach for a given thrust, so I_batt is identical across C_T cases.")

    print("  F. ESC current-rating sensitivity (14S, cap=4.0 Ah, static):")
    for i_max in ESC_I_MAX_SENSITIVITY_A:
        esc_i = ESCModel(eta_esc=DEFAULT_ETA_ESC, i_esc_max_A=i_max)
        pt = build_electrical_operating_point(static_ref, motor, esc_i, baseline_pack)
        print(
            f"    I_ESC_max={i_max:.0f} A  margin={pt.esc_current_margin.margin:+.3f}  "
            f"ok={pt.esc_current_margin.ok}"
        )
    print()

    print("## Result")
    print("-" * 92)
    if outcome_elec.success:
        sel = outcome_elec.selected
        print(
            f"  Selected conceptual electrical architecture: {sel.pack_n_series}S "
            f"({sel.pack_v_nom_V:.1f} V nominal),"
        )
        print(
            f"  eta_motor={DEFAULT_ETA_MOTOR:.2f}, eta_ESC={DEFAULT_ETA_ESC:.2f}, "
            f"capacity={DEFAULT_CAPACITY_AH:.1f} Ah."
        )
        print("  Governing operating point: static (higher power/current than cruise).")
        governing_margin = min(
            sel.esc_current_margin.margin,
            sel.battery_current_margin.margin,
            sel.c_rate_margin.margin,
        )
        print(f"  Governing (smallest) margin: {governing_margin:+.3f}")
    print(
        "  Electrical sizing does NOT invalidate the M1/M2 0.50 m EDF fan choice or its"
    )
    print(
        "  M2-admissible RPM region -- it adds a downstream electrical architecture on"
    )
    print(
        "  top of the unchanged aerodynamic/rotational requirement. The 12S candidate"
    )
    print(
        "  fails the electrical gates at the baseline 4.0 Ah capacity; 14S is the"
    )
    print("  lowest-voltage candidate satisfying every predeclared gate.")
    print()
    print("Battery energy is used only for electrical bookkeeping in Milestone 3;")
    print("mission endurance is not modeled.")
    print()
    print("Reminder: generic reduced-order conceptual EDF study, not experimentally")
    print("validated and not a manufacturer product recommendation.")


if __name__ == "__main__":
    main()
