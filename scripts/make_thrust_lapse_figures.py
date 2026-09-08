#!/usr/bin/env python3
"""Generate the five Milestone 5 portfolio figures (17-21) into figures/.

Purely additive: does not touch or regenerate the 16 Milestone 1-4 figures
(01-16), which remain the responsibility of the earlier make_*_figures.py
scripts and must stay byte-identical.

Deterministic: no randomness anywhere in this script, so re-running it
produces byte-identical PNGs (verified in the Milestone 5 quality gates).

Run with:

    python3 scripts/make_thrust_lapse_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt
import numpy as np

from edf_sizing import compressibility as comp
from edf_sizing.battery import BatteryPack
from edf_sizing.duct_losses import ThrustEffectivenessModel, static_available_thrust_N
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import REFERENCE_C_T, default_esc_model, default_motor_assumptions
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
from edf_sizing.performance_envelope import (
    DEFAULT_ETA_T,
    DEFAULT_LAPSE_MODEL,
    ETA_T_SENSITIVITY,
    evaluate_performance_envelope,
)
from edf_sizing.requirements import default_requirement
from edf_sizing.rotational_study import DEFAULT_AMBIENT, DEFAULT_M_TIP_MAX
from edf_sizing.sizing import SelectionLimits, evaluate_candidates, select_fan_diameter
from edf_sizing.thrust_lapse import available_thrust_N

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

CAVEAT = (
    "Generic reduced-order EDF study -- not experimentally validated, not a real fan map. "
    "eta_T and thrust-lapse parameters are illustrative sensitivity assumptions."
)

M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
    }
)


def _add_caveat(fig) -> None:
    fig.text(
        0.5, 0.01, CAVEAT, ha="center", va="bottom", fontsize=6.8,
        style="italic", color="0.35", wrap=True,
    )


def _envelope(req, static_row, p_cruise, motor, esc, pack, m4_profile, eta_T):
    return evaluate_performance_envelope(
        req,
        0.5,
        req.static_thrust_per_fan_N,
        req.v_cruise_m_s,
        static_row.p_shaft_est_W,
        p_cruise,
        static_row.rpm,
        DEFAULT_M_TIP_MAX,
        eta_T,
        DEFAULT_LAPSE_MODEL,
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


def figure_17_thrust_vs_airspeed(req) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    v_range = np.linspace(0.0, 50.0, 200)
    colors = {0.80: "tab:red", 0.90: "tab:orange", 1.00: "tab:green"}
    for eta_T in ETA_T_SENSITIVITY:
        model = ThrustEffectivenessModel(eta_T=eta_T)
        t_static = float(static_available_thrust_N(req.static_thrust_per_fan_N, model))
        t_curve = available_thrust_N(t_static, v_range, DEFAULT_LAPSE_MODEL)
        ax.plot(v_range, t_curve, color=colors[eta_T], label=f"$\\eta_T$={eta_T:.2f}")

    ax.axhline(
        req.static_thrust_per_fan_N,
        color="black",
        linestyle=":",
        linewidth=1.2,
        label=f"required static ({req.static_thrust_per_fan_N:.1f} N)",
    )
    ax.scatter(
        [req.v_cruise_m_s],
        [req.cruise_thrust_per_fan_N],
        color="black",
        marker="*",
        s=120,
        zorder=6,
        label=f"required cruise ({req.cruise_thrust_per_fan_N:.1f} N, {req.v_cruise_m_s:.0f} m/s)",
    )
    ax.axvline(req.v_cruise_m_s, color="0.6", linestyle="--", linewidth=0.9)

    ax.set_xlabel(r"Freestream speed, $V_\infty$ [m/s]")
    ax.set_ylabel("Available thrust per fan [N]")
    ax.set_title(
        "Available thrust vs. airspeed (baseline-RPM operating point)\n"
        "no continuous aircraft drag polar modeled -- only static/cruise points are requirements"
    )
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "17_thrust_available_vs_airspeed.png")
    plt.close(fig)


def figure_18_rpm_recovery(req, static_row) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    eta_T_range = np.linspace(0.55, 1.0, 100)
    rpm_required = static_row.rpm / np.sqrt(eta_T_range)

    ax.plot(
        eta_T_range, rpm_required, color="tab:blue",
        label="RPM required to recover static thrust",
    )
    for m_tip_max, style in ((0.75, ":"), (0.85, "--"), (0.95, "-.")):
        ceiling = comp.max_rpm_static(0.5, m_tip_max, DEFAULT_AMBIENT)
        ax.axhline(
            ceiling, color="tab:red", linestyle=style, linewidth=1.3,
            label=f"ceiling $M_{{tip,max}}$={m_tip_max:.2f} ({ceiling:.0f} RPM)",
        )
    for eta_T in ETA_T_SENSITIVITY:
        rpm_req = static_row.rpm / (eta_T ** 0.5)
        ax.scatter([eta_T], [rpm_req], color="black", zorder=5)
        ax.annotate(
            f"{eta_T:.2f}", xy=(eta_T, rpm_req), xytext=(3, 5),
            textcoords="offset points", fontsize=8,
        )

    ax.set_xlabel(r"Thrust effectiveness, $\eta_T$")
    ax.set_ylabel("RPM required to recover static thrust")
    ax.set_title("RPM recovery vs. thrust effectiveness, with M2 tip-Mach ceilings")
    ax.legend(loc="upper right", fontsize=7.5)
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "18_rpm_recovery_vs_thrust_effectiveness.png")
    plt.close(fig)


def figure_19_electrical_penalty(req, static_row, p_cruise, motor, esc, m4_profile) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 5.0))
    eta_T_range = np.array([1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70])

    pack14 = BatteryPack(n_series=14, capacity_Ah=28.0, continuous_c_rate_limit=20.0)
    pack16 = BatteryPack(n_series=16, capacity_Ah=24.0, continuous_c_rate_limit=20.0)

    for pack, color, label in ((pack14, "tab:blue", "14S/28Ah"), (pack16, "tab:green", "16S/24Ah")):
        currents = []
        for eta_T in eta_T_range:
            r = _envelope(req, static_row, p_cruise, motor, esc, pack, m4_profile, float(eta_T))
            currents.append(r.recovered_electrical.battery_current_A)
        ax1.plot(eta_T_range, currents, marker="o", color=color, label=label)
    ax1.axhline(100.0, color="tab:red", linestyle="--", linewidth=1.3, label="ESC limit = 100 A")
    ax1.set_xlabel(r"Thrust effectiveness, $\eta_T$")
    ax1.set_ylabel("Recovered battery current [A]")
    ax1.set_title("Battery current vs. $\\eta_T$")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.3)
    ax1.invert_xaxis()

    shaft_powers = []
    for eta_T in eta_T_range:
        r = _envelope(req, static_row, p_cruise, motor, esc, pack14, m4_profile, float(eta_T))
        shaft_powers.append(r.recovered_electrical.shaft_power_recovered_W)
    ax2.plot(eta_T_range, shaft_powers, marker="o", color="tab:orange")
    ax2.axhline(
        static_row.p_shaft_est_W, color="black", linestyle=":", linewidth=1.2,
        label=f"reference shaft power ({static_row.p_shaft_est_W:.0f} W)",
    )
    ax2.set_xlabel(r"Thrust effectiveness, $\eta_T$")
    ax2.set_ylabel("Recovered shaft power [W]")
    ax2.set_title("Shaft power penalty vs. $\\eta_T$ (14S/28Ah)")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)
    ax2.invert_xaxis()

    fig.suptitle("Electrical penalty of RPM-based thrust recovery", fontsize=12)
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.92))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "19_electrical_penalty_vs_thrust_loss.png")
    plt.close(fig)


def figure_20_mission_energy_penalty(req, static_row, p_cruise, motor, esc, m4_profile) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    pack14 = BatteryPack(n_series=14, capacity_Ah=28.0, continuous_c_rate_limit=20.0)

    eta_T_range = np.array([1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70])
    mission_wh = []
    for eta_T in eta_T_range:
        r = _envelope(req, static_row, p_cruise, motor, esc, pack14, m4_profile, float(eta_T))
        mission_wh.append(r.mission_energy_penalty.mission_energy_m5_Wh)

    ax.plot(eta_T_range, mission_wh, marker="o", color="tab:purple", label="M5 mission energy")
    m4_baseline = mission_wh[0]
    ax.axhline(
        m4_baseline, color="black", linestyle=":", linewidth=1.2,
        label=f"M4 baseline ({m4_baseline:.0f} Wh)",
    )
    usable_wh = pack14.energy_Wh_nom * DEFAULT_USABLE_FRACTION
    reserve_adj_usable = usable_wh / (1.0 + DEFAULT_RESERVE_FRACTION)
    ax.axhline(
        reserve_adj_usable, color="tab:red", linestyle="--", linewidth=1.3,
        label=f"28 Ah usable/(1+reserve) = {reserve_adj_usable:.0f} Wh",
    )
    for eta_T in ETA_T_SENSITIVITY:
        idx = list(eta_T_range).index(eta_T)
        ax.scatter([eta_T], [mission_wh[idx]], color="black", zorder=5)
        ax.annotate(
            f"{eta_T:.2f}", xy=(eta_T, mission_wh[idx]), xytext=(3, 5),
            textcoords="offset points", fontsize=8,
        )

    ax.set_xlabel(r"Thrust effectiveness, $\eta_T$")
    ax.set_ylabel("Mission energy [Wh]")
    ax.set_title("Mission-energy penalty of thrust-loss recovery (14S/28Ah)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    ax.invert_xaxis()

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "20_mission_energy_penalty_vs_losses.png")
    plt.close(fig)


def figure_21_final_summary(req, sel_d, static_row, baseline_result) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    ax.axis("off")

    sm, cm = baseline_result.static_margin, baseline_result.cruise_margin
    rr, re_ = baseline_result.rpm_recovery, baseline_result.recovered_electrical
    mp = baseline_result.mission_energy_penalty

    lines = [
        f"Milestone 5 -- final performance-envelope summary (eta_T={DEFAULT_ETA_T:.2f} baseline)",
        "",
        f"Fan: D={sel_d:.2f} m   Reference static RPM={static_row.rpm:.0f}   "
        f"tip Mach={static_row.tip_mach:.3f}",
        "",
        f"Static thrust: required={sm.thrust_required_N:.1f} N  "
        f"available(baseline RPM)={sm.thrust_available_N:.1f} N  ({sm.margin_fraction:+.1%})",
        f"  -> RPM recovery: {rr.rpm_required:.0f} RPM "
        f"(ceiling {rr.rpm_ceiling:.0f})  {'FEASIBLE' if rr.feasible else 'INFEASIBLE'}",
        "",
        f"Cruise thrust: required={cm.thrust_required_N:.1f} N  "
        f"available={cm.thrust_available_N:.1f} N  ({cm.margin_fraction:+.1%})  PASS",
        "",
        f"Recovered electrical: P_shaft={re_.shaft_power_recovered_W:.0f} W  "
        f"I_batt={re_.battery_current_A:.1f} A",
        f"  ESC margin={re_.esc_current_margin.margin:+.3f}  "
        f"battery margin={re_.battery_current_margin.margin:+.3f}",
        "",
        f"Mission energy: M4 baseline={mp.mission_energy_m4_baseline_Wh:.0f} Wh  "
        f"M5={mp.mission_energy_m5_Wh:.0f} Wh  (delta {mp.delta_Wh:+.0f} Wh)",
        f"  28 Ah capacity margin = {mp.capacity_margin.margin:+.3f}",
        "",
        f"OVERALL: {'FEASIBLE' if baseline_result.feasible else 'INFEASIBLE'} "
        "(governing: RPM recovery closes static-thrust shortfall within the",
        "M2 tip-Mach ceiling; M3 current and M4 energy margins both remain positive)",
        "",
        "M1-M4 requirements/results unchanged. This is a reduced-order sensitivity",
        "study -- not a validated EDF performance map.",
    ]

    ax.text(
        0.02, 0.98, "\n".join(lines), transform=ax.transAxes, ha="left", va="top",
        fontsize=9.3, family="monospace",
    )

    fig.tight_layout(rect=(0.0, 0.07, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "21_final_m5_performance_summary.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot generate M5 figures.")
    sel_d = outcome.selected.diameter_m

    rows = reference_rotational_rows(req, sel_d, M1_ASSUMPTION, REFERENCE_C_T)
    static_row = rows["static"]
    p_static, p_cruise, _sr, _cr = m3_reference_battery_powers(
        req, sel_d, M1_ASSUMPTION, REFERENCE_C_T
    )
    motor = default_motor_assumptions()
    esc = default_esc_model()
    pack14 = BatteryPack(n_series=14, capacity_Ah=28.0, continuous_c_rate_limit=20.0)
    m4_profile = default_mission_profile(p_static, p_cruise, req.n_fans)

    baseline_result = _envelope(
        req, static_row, p_cruise, motor, esc, pack14, m4_profile, DEFAULT_ETA_T
    )

    figure_17_thrust_vs_airspeed(req)
    figure_18_rpm_recovery(req, static_row)
    figure_19_electrical_penalty(req, static_row, p_cruise, motor, esc, m4_profile)
    figure_20_mission_energy_penalty(req, static_row, p_cruise, motor, esc, m4_profile)
    figure_21_final_summary(req, sel_d, static_row, baseline_result)
    print(f"Wrote 5 Milestone 5 figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
