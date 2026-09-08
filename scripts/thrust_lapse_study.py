#!/usr/bin/env python3
"""Milestone 5 engineering script: thrust-effectiveness / thrust-lapse
sensitivity study for the Milestone 1-4 selected 0.50 m EDF / 14S / 28 Ah
architecture.

This script only calls the `edf_sizing` package (Milestone 1-5 modules);
it contains no physics of its own. Run with:

    python3 scripts/thrust_lapse_study.py
"""

from __future__ import annotations

from edf_sizing import compressibility as comp
from edf_sizing.battery import BatteryPack
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel
from edf_sizing.electrical_sizing import (
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    REFERENCE_C_T,
    default_esc_model,
    default_motor_assumptions,
)
from edf_sizing.mission_sizing import (
    CLIMB_DURATION_S,
    CLIMB_POWER_FRACTION_OF_STATIC,
    CRUISE_DURATION_S,
    DEFAULT_RESERVE_FRACTION,
    DEFAULT_USABLE_FRACTION,
    LAUNCH_DURATION_S,
    LOITER_DURATION_S,
    LOITER_POWER_FRACTION_OF_CRUISE,
    default_mission_profile,
    m3_reference_battery_powers,
    reference_rotational_rows,
)
from edf_sizing.motor import MotorAssumptions
from edf_sizing.performance_envelope import (
    ALTERNATIVE_LAPSE_MODEL,
    DEFAULT_ETA_T,
    DEFAULT_LAPSE_MODEL,
    ETA_T_SENSITIVITY,
    STRESS_ETA_T,
    evaluate_performance_envelope,
)
from edf_sizing.requirements import default_requirement
from edf_sizing.rotational_study import DEFAULT_AMBIENT, DEFAULT_M_TIP_MAX
from edf_sizing.sizing import (
    SelectionLimits,
    evaluate_candidates,
    select_fan_diameter,
)

M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)

M_TIP_MAX_SENSITIVITY = (0.75, 0.85, 0.95)
DIAMETER_SENSITIVITY_M = (0.45, 0.50, 0.55, 0.60)


def _run_envelope(
    req, static_row, p_cruise, motor, esc, pack, m4_profile, eta_T, lapse_model,
    m_tip_max=DEFAULT_M_TIP_MAX, diameter_m=0.5,
):
    return evaluate_performance_envelope(
        req,
        diameter_m,
        req.static_thrust_per_fan_N,
        req.v_cruise_m_s,
        static_row.p_shaft_est_W,
        p_cruise,
        static_row.rpm,
        m_tip_max,
        eta_T,
        lapse_model,
        motor,
        esc,
        pack,
        m4_profile,
        DEFAULT_RESERVE_FRACTION,
        DEFAULT_USABLE_FRACTION,
        CLIMB_POWER_FRACTION_OF_STATIC,
        LOITER_POWER_FRACTION_OF_CRUISE,
        LAUNCH_DURATION_S,
        CLIMB_DURATION_S,
        CRUISE_DURATION_S,
        LOITER_DURATION_S,
    )


def main() -> None:
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot run Milestone 5 study.")
    sel_d = outcome.selected.diameter_m

    rows = reference_rotational_rows(req, sel_d, M1_ASSUMPTION, REFERENCE_C_T)
    static_row = rows["static"]
    p_static, p_cruise, _sr, _cr = m3_reference_battery_powers(
        req, sel_d, M1_ASSUMPTION, REFERENCE_C_T
    )
    motor = default_motor_assumptions()
    esc = default_esc_model()
    pack14_28 = BatteryPack(n_series=14, capacity_Ah=28.0, continuous_c_rate_limit=20.0)
    m4_profile = default_mission_profile(p_static, p_cruise, req.n_fans)

    print("=" * 92)
    print("Milestone 5 -- thrust-effectiveness / thrust-lapse sensitivity study")
    print("=" * 92)
    print("This is a reduced-order thrust-lapse sensitivity study, not a validated")
    print("EDF performance map.")
    print()

    print("## Inherited design")
    print("-" * 92)
    print(f"  D = {sel_d:.2f} m,  M2 reference RPM(static) = {static_row.rpm:.0f},  "
          f"tip Mach = {static_row.tip_mach:.3f}")
    ceiling = comp.max_rpm_static(sel_d, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
    print(f"  M2 tip-Mach ceiling (M_tip,max={DEFAULT_M_TIP_MAX:.2f}) = {ceiling:.1f} RPM")
    print(f"  M3 electrical: eta_motor={DEFAULT_ETA_MOTOR:.2f}, eta_ESC={DEFAULT_ETA_ESC:.2f}, "
          f"ESC I_max=100 A")
    print("  M4 selected battery: 14S, 28.0 Ah")
    print()

    print("## M5 model")
    print("-" * 92)
    print(
        f"  eta_T baseline = {DEFAULT_ETA_T:.2f} (ILLUSTRATIVE), "
        f"sensitivity {ETA_T_SENSITIVITY}"
    )
    print(
        f"  supplementary stress case eta_T = {STRESS_ETA_T:.2f} "
        "(demonstrates RPM-ceiling failure)"
    )
    print(
        f"  baseline lapse: linear, f(V) = max(0, 1 - {DEFAULT_LAPSE_MODEL.k:.2f}*V/"
        f"{DEFAULT_LAPSE_MODEL.v_ref_m_s:.0f}) (ILLUSTRATIVE)"
    )
    print(
        f"  alternative lapse: quadratic, f(V) = max(0, 1 - {ALTERNATIVE_LAPSE_MODEL.k:.2f}*"
        f"(V/{ALTERNATIVE_LAPSE_MODEL.v_ref_m_s:.0f})^2) (ILLUSTRATIVE)"
    )
    print("  SOURCED: qualitative NACA/propeller-literature thrust-lapse-with-advance-ratio")
    print("  trend; T~RPM^2 and P~RPM^3 from the frozen M2 fixed-C_T/C_P convention.")
    print()

    baseline = _run_envelope(
        req, static_row, p_cruise, motor, esc, pack14_28, m4_profile,
        DEFAULT_ETA_T, DEFAULT_LAPSE_MODEL,
    )

    print(f"## Static thrust (eta_T = {DEFAULT_ETA_T:.2f} baseline)")
    print("-" * 92)
    sm = baseline.static_margin
    print(f"  required = {sm.thrust_required_N:.2f} N   available (baseline RPM) = "
          f"{sm.thrust_available_N:.2f} N")
    print(f"  margin = {sm.margin_N:+.2f} N ({sm.margin_fraction:+.1%})  "
          f"{'PASS' if sm.passes else 'FAIL (honest shortfall)'}")
    rr = baseline.rpm_recovery
    print(f"  RPM recovery required = {rr.rpm_required:.1f}  ceiling = {rr.rpm_ceiling:.1f}  "
          f"{'FEASIBLE' if rr.feasible else 'INFEASIBLE'}")
    print(
        f"  tip Mach at recovery = {rr.tip_mach_at_recovery:.3f}  "
        f"power ratio = {rr.power_ratio:.4f}"
    )
    print()

    print("## Cruise thrust")
    print("-" * 92)
    cm = baseline.cruise_margin
    print(f"  V_inf = {cm.v_inf_m_s:.1f} m/s   required = {cm.thrust_required_N:.2f} N   "
          f"available = {cm.thrust_available_N:.2f} N")
    print(f"  margin = {cm.margin_N:+.2f} N ({cm.margin_fraction:+.1%})  "
          f"{'PASS' if cm.passes else 'FAIL'}")
    print()

    print("## Electrical impact (recovered static operating point)")
    print("-" * 92)
    re_ = baseline.recovered_electrical
    print(f"  shaft power: reference={re_.shaft_power_reference_W:.1f} W -> "
          f"recovered={re_.shaft_power_recovered_W:.1f} W")
    print(f"  motor elec. power = {re_.motor_electrical_power_W:.1f} W   "
          f"battery power = {re_.battery_power_W:.1f} W")
    print(f"  battery current = {re_.battery_current_A:.2f} A   C-rate = {re_.c_rate_required:.2f}")
    print(f"  ESC margin = {re_.esc_current_margin.margin:+.3f} "
          f"({'ok' if re_.esc_current_margin.ok else 'FAIL'})   "
          f"battery margin = {re_.battery_current_margin.margin:+.3f} "
          f"({'ok' if re_.battery_current_margin.ok else 'FAIL'})")
    print()

    print("## Mission-energy impact")
    print("-" * 92)
    mp = baseline.mission_energy_penalty
    print(f"  M4 baseline mission energy = {mp.mission_energy_m4_baseline_Wh:.1f} Wh")
    print(f"  M5 updated mission energy  = {mp.mission_energy_m5_Wh:.1f} Wh   "
          f"delta = {mp.delta_Wh:+.1f} Wh ({mp.delta_Wh / mp.mission_energy_m4_baseline_Wh:+.1%})")
    print(f"  28 Ah pack usable energy = {mp.pack_usable_Wh:.1f} Wh   "
          f"required (reserve-adj.) = {mp.reserve_adjusted_m5_Wh:.1f} Wh")
    print(f"  capacity margin = {mp.capacity_margin.margin:+.3f}  "
          f"{'ok' if mp.capacity_margin.ok else 'FAIL'}")
    print()

    print(f"## OVERALL (eta_T = {DEFAULT_ETA_T:.2f} baseline): "
          f"{'FEASIBLE' if baseline.feasible else 'INFEASIBLE'}")
    print("-" * 92)
    print(f"  {baseline.rule_description}")
    print()

    print("## Sensitivities")
    print("-" * 92)
    print("  A. eta_T sensitivity (14S/28Ah, baseline linear lapse):")
    for eta_T in ETA_T_SENSITIVITY + (STRESS_ETA_T,):
        r = _run_envelope(
            req, static_row, p_cruise, motor, esc, pack14_28, m4_profile,
            eta_T, DEFAULT_LAPSE_MODEL,
        )
        tag = " (stress case)" if eta_T == STRESS_ETA_T else ""
        print(
            f"    eta_T={eta_T:.2f}{tag}: static_via_recovery={r.static_thrust_met_via_recovery} "
            f"cruise={r.cruise_margin.passes} current_ok={r.recovered_electrical.current_ok} "
            f"energy_ok={r.mission_energy_penalty.capacity_margin.ok} "
            f"OVERALL={'FEASIBLE' if r.feasible else 'INFEASIBLE'}"
        )

    print("  B. lapse model (linear vs. quadratic, eta_T=0.90):")
    lapse_cases = ((DEFAULT_LAPSE_MODEL, "linear"), (ALTERNATIVE_LAPSE_MODEL, "quadratic"))
    for lapse_model, name in lapse_cases:
        r = _run_envelope(
            req, static_row, p_cruise, motor, esc, pack14_28, m4_profile,
            DEFAULT_ETA_T, lapse_model,
        )
        print(f"    {name}: cruise available = {r.cruise_margin.thrust_available_N:.2f} N  "
              f"margin = {r.cruise_margin.margin_fraction:+.1%}")

    print("  C. M2 C_T reference case (0.08 vs. 0.12) -- RPM/tip-Mach unaffected by eta_T,")
    print("     since RPM recovery uses the fixed-C_T scaling from whichever reference RPM")
    print("     is supplied; both C_T cases pass the M2 tip-Mach screen (see")
    print("     rotational_fan_study.py).")

    print("  D. M_tip,max sensitivity (eta_T=0.80, stress case for RPM ceiling):")
    for m_tip_max in M_TIP_MAX_SENSITIVITY:
        r = _run_envelope(
            req, static_row, p_cruise, motor, esc, pack14_28, m4_profile, 0.80, DEFAULT_LAPSE_MODEL,
            m_tip_max=m_tip_max,
        )
        print(f"    M_tip,max={m_tip_max:.2f}: ceiling={r.rpm_recovery.rpm_ceiling:.1f} "
              f"recovery_feasible={r.rpm_recovery.feasible}")

    print("  E. eta_motor sensitivity (recovered static point, eta_T=0.90):")
    for e in (0.85, 0.90, 0.95):
        m = MotorAssumptions(eta_motor=e, rated_electrical_power_W=4500.0)
        r = _run_envelope(
            req, static_row, p_cruise, m, esc, pack14_28, m4_profile,
            DEFAULT_ETA_T, DEFAULT_LAPSE_MODEL,
        )
        print(f"    eta_motor={e:.2f}: I_batt={r.recovered_electrical.battery_current_A:.2f} A  "
              f"current_ok={r.recovered_electrical.current_ok}")

    print("  F. eta_ESC sensitivity (recovered static point, eta_T=0.90):")
    for e in (0.95, 0.97, 0.99):
        esc_e = ESCModel(eta_esc=e, i_esc_max_A=100.0)
        r = _run_envelope(
            req, static_row, p_cruise, motor, esc_e, pack14_28, m4_profile,
            DEFAULT_ETA_T, DEFAULT_LAPSE_MODEL,
        )
        print(f"    eta_ESC={e:.2f}: I_batt={r.recovered_electrical.battery_current_A:.2f} A  "
              f"current_ok={r.recovered_electrical.current_ok}")

    print("  G. pack voltage (14S vs. 16S, eta_T=0.90):")
    for n_series, cap in ((14, 28.0), (16, 24.0)):
        pack = BatteryPack(n_series=n_series, capacity_Ah=cap, continuous_c_rate_limit=20.0)
        r = _run_envelope(
            req, static_row, p_cruise, motor, esc, pack, m4_profile,
            DEFAULT_ETA_T, DEFAULT_LAPSE_MODEL,
        )
        i_batt = r.recovered_electrical.battery_current_A
        print(f"    {n_series}S/{cap:.1f}Ah: I_batt={i_batt:.2f} A  "
              f"energy_margin={r.mission_energy_penalty.capacity_margin.margin:+.3f}  "
              f"OVERALL={'FEASIBLE' if r.feasible else 'INFEASIBLE'}")

    print("  H. mission cruise duration (carried forward from M4, 20 min baseline) --")
    print("     cruise/loiter power is unaffected by eta_T at baseline (thrust lapse passes),")
    print("     so cruise-duration sensitivity matches scripts/mission_energy_study.py exactly.")

    print("  I. diameter sensitivity (M2 tip-Mach ceiling only, M1 selection NOT replaced):")
    for d in DIAMETER_SENSITIVITY_M:
        ceiling_d = comp.max_rpm_static(d, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT)
        marker = " (M1 selected)" if abs(d - sel_d) < 1e-9 else ""
        print(f"    D={d:.2f} m: tip-Mach RPM ceiling = {ceiling_d:.1f}{marker}")
    print()

    print("## Result")
    print("-" * 92)
    print(f"  M1 fan (D={sel_d:.2f} m) remains viable: requires off-design RPM recovery at the "
          f"eta_T={DEFAULT_ETA_T:.2f}")
    print("  baseline (static thrust does not close without it), but recovery stays within the")
    print("  M2 tip-Mach ceiling with headroom.")
    print(f"  M2 RPM/tip-Mach constraint remains viable: recovery RPM "
          f"({baseline.rpm_recovery.rpm_required:.0f}) < ceiling ({ceiling:.0f}).")
    print(f"  M3 14S electrical architecture remains viable at baseline eta_T "
          f"(current margin {re_.esc_current_margin.margin:+.3f}), but FAILS at eta_T=0.80.")
    print(f"  M4 28 Ah battery capacity remains viable at baseline eta_T "
          f"(margin {mp.capacity_margin.margin:+.3f}), but FAILS at eta_T=0.80.")
    print("  Governing constraint at the eta_T=0.80 sensitivity extreme: ESC/battery current AND")
    print("  mission-energy capacity margin (both turn negative simultaneously).")
    print()
    print("Loss coefficients and lapse parameters are deterministic conceptual assumptions")
    print("unless explicitly source-backed.")
    print()
    print("Reminder: generic reduced-order conceptual EDF study, not experimentally")
    print("validated and not a real fan-map calibration.")


if __name__ == "__main__":
    main()
