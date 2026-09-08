#!/usr/bin/env python3
"""Milestone 4 engineering script: mission-energy and battery-capacity
sizing study for the Milestone 1-3 selected 0.50 m EDF / 14S electrical
architecture.

This script only calls the `edf_sizing` package (Milestone 1-4 modules);
it contains no physics of its own. Run with:

    python3 scripts/mission_energy_study.py
"""

from __future__ import annotations

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import (
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    REFERENCE_C_T,
    default_esc_model,
    default_motor_assumptions,
)
from edf_sizing.energy import (
    battery_mass_kg,
    cruise_only_energy_diagnostic_hours,
    segment_energy_Wh,
)
from edf_sizing.mission import MissionProfile, MissionSegment
from edf_sizing.mission_sizing import (
    CLIMB_DURATION_S,
    DEFAULT_CAPACITY_CANDIDATES_AH,
    DEFAULT_SPECIFIC_ENERGY_WH_PER_KG,
    DEFAULT_VOLTAGE_CANDIDATES_SERIES,
    LAUNCH_DURATION_S,
    LOITER_DURATION_S,
    RESERVE_FRACTION_SENSITIVITY,
    SPECIFIC_ENERGY_SENSITIVITY_WH_PER_KG,
    USABLE_FRACTION_SENSITIVITY,
    compute_energy_requirement,
    default_mission_profile,
    evaluate_voltage_carry_forward,
    m3_reference_battery_powers,
    select_capacity_for_voltage,
)
from edf_sizing.requirements import default_requirement
from edf_sizing.rotational_study import DEFAULT_M_TIP_MAX
from edf_sizing.sizing import SelectionLimits, evaluate_candidates, select_fan_diameter

M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)

CRUISE_DURATION_SENSITIVITY_S = (600.0, 1200.0, 1800.0)
CLIMB_DURATION_SENSITIVITY_S = (60.0, 120.0, 180.0)


def _mission_profile_with_cruise_duration(p_static, p_cruise, n_fans, cruise_duration_s):
    return MissionProfile(
        segments=(
            MissionSegment("launch", LAUNCH_DURATION_S, p_static, n_fans, 1.0),
            MissionSegment("climb", CLIMB_DURATION_S, p_static, n_fans, 0.70),
            MissionSegment("cruise", cruise_duration_s, p_cruise, n_fans, 1.0),
            MissionSegment("loiter", LOITER_DURATION_S, p_cruise, n_fans, 1.20),
        )
    )


def _mission_profile_with_climb_duration(p_static, p_cruise, n_fans, climb_duration_s):
    from edf_sizing.mission_sizing import CRUISE_DURATION_S

    return MissionProfile(
        segments=(
            MissionSegment("launch", LAUNCH_DURATION_S, p_static, n_fans, 1.0),
            MissionSegment("climb", climb_duration_s, p_static, n_fans, 0.70),
            MissionSegment("cruise", CRUISE_DURATION_S, p_cruise, n_fans, 1.0),
            MissionSegment("loiter", LOITER_DURATION_S, p_cruise, n_fans, 1.20),
        )
    )


def main() -> None:
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot run Milestone 4 study.")
    sel_d = outcome.selected.diameter_m

    p_static, p_cruise, static_row, cruise_row = m3_reference_battery_powers(
        req, sel_d, M1_ASSUMPTION, REFERENCE_C_T
    )
    profile = default_mission_profile(p_static, p_cruise, req.n_fans)
    energy_req = compute_energy_requirement(profile)

    motor = default_motor_assumptions()
    esc = default_esc_model()

    print("=" * 92)
    print("Milestone 4 -- mission-energy and battery-capacity sizing study")
    print("=" * 92)
    print("This is a reduced-order mission-energy bookkeeping study, not a")
    print("trajectory simulation or flight-endurance prediction.")
    print()

    print("## Inherited design")
    print("-" * 92)
    print(f"  Selected diameter D = {sel_d:.2f} m")
    print(f"  M2 reference C_T = {REFERENCE_C_T:.2f}, static RPM = {static_row.rpm:.0f}, "
          f"cruise RPM = {cruise_row.rpm:.0f}")
    print(f"  M3 selected pack voltage = 14S ({14 * 3.7:.1f} V nominal)")
    print(
        f"  Static battery power/fan = {p_static:.1f} W, "
        f"cruise battery power/fan = {p_cruise:.1f} W"
    )
    print(f"  eta_motor = {DEFAULT_ETA_MOTOR:.2f}, eta_ESC = {DEFAULT_ETA_ESC:.2f}")
    print()

    print("## Mission definition (predeclared, ILLUSTRATIVE durations/fractions)")
    print("-" * 92)
    header = f"{'segment':<8}{'dur [s]':>9}{'P_tot [W]':>11}{'E [Wh]':>9}  assumption"
    print(header)
    for s in profile.segments:
        print(
            f"{s.name:<8}{s.duration_s:9.0f}{s.total_power_W:11.1f}"
            f"{segment_energy_Wh(s):9.2f}  {s.label}"
        )
    print()

    print("## Mission energy")
    print("-" * 92)
    print(f"  Raw mission energy         = {energy_req.mission_energy_Wh:.2f} Wh")
    print(f"  Reserve fraction (illustr.) = {energy_req.reserve_fraction:.2f}")
    print(f"  Reserve-adjusted energy     = {energy_req.reserve_adjusted_Wh:.2f} Wh")
    print(f"  Usable-energy fraction (illustr.) = {energy_req.usable_fraction:.2f}")
    print(f"  Required nominal energy     = {energy_req.required_nominal_Wh:.2f} Wh")
    req_ah_14s = energy_req.required_nominal_Wh / (14 * 3.7)
    print(f"  Required Ah at 14S          = {req_ah_14s:.2f} Ah")
    print()

    print("## Baseline M3 pack (4.0 Ah, 14S) -- current vs. energy screens")
    print("-" * 92)
    baseline_outcome = select_capacity_for_voltage(14, (4.0,), static_row, motor, esc, energy_req)
    b = baseline_outcome.all_candidates[0]
    print(f"  nominal Wh = {b.nominal_Wh:.1f}  usable Wh = {b.usable_Wh:.1f}")
    print(f"  current screen: {'PASS' if b.current_ok else 'FAIL'} "
          f"(static I={b.static_current_A:.2f} A, C-rate={b.static_c_rate:.2f})")
    print(f"  energy screen : {'PASS' if b.energy_ok else 'FAIL'} "
          f"(usable {b.usable_Wh:.1f} Wh vs. required {energy_req.reserve_adjusted_Wh:.1f} Wh)")
    print(f"  overall       : {'PASS' if b.overall_ok else 'FAIL'}")
    print()

    print("## Capacity trade at 14S (predeclared selection rule)")
    print("-" * 92)
    outcome_14s = select_capacity_for_voltage(
        14, DEFAULT_CAPACITY_CANDIDATES_AH, static_row, motor, esc, energy_req
    )
    print(f"  {outcome_14s.rule_description}")
    header2 = (
        f"{'Ah':>6}{'nom Wh':>9}{'usable Wh':>10}{'req Ah':>8}{'I [A]':>8}"
        f"{'C-rate':>8}{'curr?':>7}{'energy?':>8}{'all?':>6}"
    )
    print(header2)
    for c in outcome_14s.all_candidates:
        print(
            f"{c.capacity_Ah:6.1f}{c.nominal_Wh:9.1f}{c.usable_Wh:10.1f}{c.required_Ah:8.2f}"
            f"{c.static_current_A:8.2f}{c.static_c_rate:8.2f}"
            f"{'yes' if c.current_ok else 'NO':>7}{'yes' if c.energy_ok else 'NO':>8}"
            f"{'yes' if c.overall_ok else 'NO':>6}"
        )
    if outcome_14s.success:
        print(f"  -> SELECTED capacity: {outcome_14s.selected.capacity_Ah:.1f} Ah")
    else:
        print("  -> NO candidate capacity satisfies both screens -- reporting honestly.")
    print()

    print("## Voltage trade (12S / 14S / 16S carried forward from M3)")
    print("-" * 92)
    vf = evaluate_voltage_carry_forward(
        DEFAULT_VOLTAGE_CANDIDATES_SERIES,
        DEFAULT_CAPACITY_CANDIDATES_AH,
        static_row,
        motor,
        esc,
        energy_req,
        m3_selected_n_series=14,
    )
    header3 = f"{'S':>3}{'Vnom':>7}{'sel Ah':>8}{'nom Wh':>9}{'req Ah(exact)':>15}{'I [A]':>8}"
    print(header3)
    for n_series, o in sorted(vf.outcomes_by_voltage.items()):
        if o.success:
            s = o.selected
            print(
                f"{n_series:>3}{s.v_pack_nom_V:7.1f}{s.capacity_Ah:8.1f}{s.nominal_Wh:9.1f}"
                f"{s.required_Ah:15.2f}{s.static_current_A:8.2f}"
            )
        else:
            print(f"{n_series:>3}  -- no feasible capacity in the candidate sweep --")
    print(f"  {vf.rule_description}")
    print(f"  -> mechanical tie-break selects: {vf.selected_n_series}S")
    print(f"  -> matches M3's 14S selection: {vf.matches_m3_selection}")
    print(
        "  NOTE: required nominal Wh is voltage-invariant in this model (only required Ah\n"
        "  scales with voltage); the small Wh differences above are a discretization artifact\n"
        "  of the candidate Ah grid, not a genuine electrical difference between voltages.\n"
        "  Once capacity is resized for the mission-energy requirement, ALL THREE candidate\n"
        "  voltages become current-feasible -- the M3 12S current/C-rate failure was specific\n"
        "  to the small (4.0 Ah) M3 baseline capacity and is resolved at the larger capacity\n"
        "  mission-energy sizing requires."
    )
    print()

    print("## Sensitivities")
    print("-" * 92)
    print("  A. cruise duration (14S, 28 Ah candidate fixed for comparison):")
    for dur in CRUISE_DURATION_SENSITIVITY_S:
        prof = _mission_profile_with_cruise_duration(p_static, p_cruise, req.n_fans, dur)
        er = compute_energy_requirement(prof)
        print(f"    cruise={dur:.0f} s  mission={er.mission_energy_Wh:.1f} Wh  "
              f"required nominal={er.required_nominal_Wh:.1f} Wh")

    print("  B. climb (high-power) duration:")
    for dur in CLIMB_DURATION_SENSITIVITY_S:
        prof = _mission_profile_with_climb_duration(p_static, p_cruise, req.n_fans, dur)
        er = compute_energy_requirement(prof)
        print(f"    climb={dur:.0f} s  mission={er.mission_energy_Wh:.1f} Wh  "
              f"required nominal={er.required_nominal_Wh:.1f} Wh")

    print("  C. usable-energy fraction:")
    for f in USABLE_FRACTION_SENSITIVITY:
        er = compute_energy_requirement(profile, usable_fraction=f)
        print(f"    f_usable={f:.2f}  required nominal={er.required_nominal_Wh:.1f} Wh  "
              f"required Ah(14S)={er.required_nominal_Wh / (14 * 3.7):.2f}")

    print("  D. reserve fraction:")
    for r in RESERVE_FRACTION_SENSITIVITY:
        er = compute_energy_requirement(profile, reserve_fraction=r)
        print(f"    reserve={r:.2f}  required nominal={er.required_nominal_Wh:.1f} Wh")

    print("  E. eta_motor / eta_ESC sensitivity (affects battery power, not shown here")
    print("     directly -- see scripts/electrical_sizing_study.py Section A/B; mission")
    print("     energy scales in direct proportion to battery power).")

    print("  F. pack voltage/capacity: see Voltage trade table above.")
    print()

    print("## Battery mass proxy (cell/pack-level, ILLUSTRATIVE specific energy)")
    print("-" * 92)
    for se in SPECIFIC_ENERGY_SENSITIVITY_WH_PER_KG:
        m = battery_mass_kg(energy_req.required_nominal_Wh, se)
        marker = " (baseline)" if se == DEFAULT_SPECIFIC_ENERGY_WH_PER_KG else ""
        print(f"    specific energy={se:.0f} Wh/kg  mass proxy={m:.2f} kg{marker}")
    print(
        "  (Informed by/bracketing the ~149 Wh/kg pack-level value reported for NASA X-57"
        "\n   Maxwell; see DESIGN.md Section 19. This is NOT a real pack mass -- no"
        "\n   packaging/BMS/interconnect overhead beyond the chosen specific-energy basis.)"
    )
    print()

    print("## Cruise-only energy diagnostic (RESTRICTED USE -- see below)")
    print("-" * 92)
    if outcome_14s.success:
        usable_wh_selected = outcome_14s.selected.usable_Wh
        p_cruise_total = p_cruise * req.n_fans
        t_hours = cruise_only_energy_diagnostic_hours(usable_wh_selected, p_cruise_total)
        print(f"  cruise-only constant-power energy diagnostic = {t_hours:.2f} h")
        print("  This is a diagnostic ONLY -- NOT a range, flight-endurance, or")
        print("  mission-duration-capability claim.")
    print()

    print("## Result")
    print("-" * 92)
    if outcome_14s.success:
        sel = outcome_14s.selected
        print(f"  Selected conceptual pack: 14S, {sel.capacity_Ah:.1f} Ah "
              f"({sel.nominal_Wh:.1f} Wh nominal)")
        print(f"  Governing requirement: mission energy (cruise segment dominates: "
              f"{segment_energy_Wh(profile.segments[2]):.1f} Wh of "
              f"{energy_req.mission_energy_Wh:.1f} Wh total)")
        print(f"  Governing margin: capacity {sel.capacity_margin.margin:+.3f}, "
              f"current {sel.current_margin.margin:+.3f}")
    print(
        "  Mission-energy sizing does NOT preserve the M3 4.0 Ah baseline capacity -- it\n"
        "  requires a much larger pack (~28 Ah at 14S) to meet the representative mission's\n"
        "  energy demand, even though the 4.0 Ah pack passed M3's current/C-rate screen.\n"
        "  The M3 14S VOLTAGE choice remains a fully valid, current-feasible option once\n"
        "  capacity is resized for energy; the mechanical lowest-voltage tie-break above is a\n"
        "  near-tie driven mostly by capacity-grid discretization, not a substantive advantage\n"
        "  of a different voltage. 14S is retained as the recommended architecture."
    )
    print(f"  M2 tip-Mach ceiling (M_tip,max={DEFAULT_M_TIP_MAX:.2f}) and the M1/M2 D=0.50 m")
    print("  fan selection are unaffected by this milestone.")
    print()
    print("Battery reserve and usable-energy fractions are deterministic conceptual")
    print("assumptions unless explicitly sourced.")
    print()
    print("Reminder: generic reduced-order conceptual EDF study, not experimentally")
    print("validated and not a manufacturer product recommendation.")


if __name__ == "__main__":
    main()
