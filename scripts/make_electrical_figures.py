#!/usr/bin/env python3
"""Generate the four Milestone 3 portfolio figures (08-11) into figures/.

Purely additive: does not touch or regenerate the 7 Milestone 1/2 figures
(01-07), which remain the responsibility of scripts/make_figures.py and
scripts/make_rotational_figures.py and must stay byte-identical.

Deterministic: no randomness anywhere in this script, so re-running it
produces byte-identical PNGs (verified in the Milestone 3 quality gates).

Run with:

    python3 scripts/make_electrical_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt
import numpy as np

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel
from edf_sizing.electrical_sizing import (
    DEFAULT_C_RATE_LIMIT,
    DEFAULT_ESC_I_MAX_A,
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    DEFAULT_PACK_SERIES_CANDIDATES,
    ETA_ESC_SENSITIVITY,
    ETA_MOTOR_SENSITIVITY,
    REFERENCE_C_T,
    build_electrical_operating_point,
    default_esc_model,
    default_motor_assumptions,
    make_pack,
    reference_rotational_rows,
    select_pack,
)
from edf_sizing.motor import MotorAssumptions
from edf_sizing.requirements import default_requirement
from edf_sizing.sizing import SelectionLimits, evaluate_candidates, select_fan_diameter

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

CAVEAT = (
    "Generic reduced-order conceptual EDF study. Motor/ESC/battery efficiencies, ratings, "
    "and C_T are illustrative sensitivity assumptions, not manufacturer datasheet values. "
    "Not experimentally validated; not a hardware selection; no mission endurance modeled."
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
        0.5,
        0.01,
        CAVEAT,
        ha="center",
        va="bottom",
        fontsize=6.8,
        style="italic",
        color="0.35",
        wrap=True,
    )


def figure_8_power_flow(static_pt, cruise_pt) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 5.0))

    stages = ["Ideal\naero.\npower", "M1 shaft\nestimate", "Motor\nelectrical", "Battery\ninput"]

    def stage_values(pt):
        return [
            pt.shaft_power_W * 0.75,  # Pi = P_shaft_est * eta_overall (reconstruct Pi)
            pt.shaft_power_W,
            pt.motor_electrical_power_W,
            pt.battery_power_W,
        ]

    x = np.arange(len(stages))
    width = 0.6

    for ax, pt, title, color in (
        (ax1, static_pt, "Static", "tab:blue"),
        (ax2, cruise_pt, "Cruise", "tab:orange"),
    ):
        values = stage_values(pt)
        ax.bar(x, values, width, color=color)
        for xi, v in zip(x, values, strict=True):
            ax.text(xi, v * 1.02, f"{v:,.0f} W", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(stages, fontsize=8.5)
        ax.set_ylabel("Power [W]")
        ax.set_title(f"{title} power flow")
        ax.set_ylim(0, max(values) * 1.2)
        ax.grid(alpha=0.3, axis="y")

    fig.suptitle(
        "Electrical power flow: ideal aero. power $\\rightarrow$ battery input\n"
        "(each downstream stage adds an explicit illustrative efficiency loss)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.90))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "08_electrical_power_flow.png")
    plt.close(fig)


def figure_9_current_vs_voltage(static_row, cruise_row) -> None:
    motor = default_motor_assumptions()
    esc = default_esc_model()

    n_series_range = np.arange(8, 22)
    v_range = n_series_range * 3.7

    static_currents = []
    cruise_currents = []
    for n in n_series_range:
        pack = make_pack(int(n))
        pt_s = build_electrical_operating_point(static_row, motor, esc, pack)
        pt_c = build_electrical_operating_point(cruise_row, motor, esc, pack)
        static_currents.append(pt_s.battery_current_A)
        cruise_currents.append(pt_c.battery_current_A)

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(v_range, static_currents, color="tab:blue", marker="o", markersize=3, label="static")
    ax.plot(
        v_range, cruise_currents, color="tab:orange", marker="o", markersize=3, label="cruise"
    )
    ax.axhline(
        esc.i_esc_max_A,
        color="tab:red",
        linestyle="--",
        linewidth=1.4,
        label=f"ESC limit = {esc.i_esc_max_A:.0f} A (illustrative)",
    )
    pack_4ah_limit = make_pack(1, capacity_Ah=4.0, c_rate_limit=DEFAULT_C_RATE_LIMIT)
    ax.axhline(
        pack_4ah_limit.i_continuous_max_A,
        color="tab:green",
        linestyle=":",
        linewidth=1.6,
        label=(
            f"battery limit = {pack_4ah_limit.i_continuous_max_A:.0f} A "
            f"(4.0 Ah @ {DEFAULT_C_RATE_LIMIT:.0f}C, illustrative)"
        ),
    )

    for n in DEFAULT_PACK_SERIES_CANDIDATES:
        ax.axvline(n * 3.7, color="black", linestyle=":", linewidth=0.9, alpha=0.6)
        ax.annotate(
            f"{n}S", xy=(n * 3.7, ax.get_ylim()[1] * 0.02), fontsize=8, ha="center"
        )

    ax.set_xlabel("Pack nominal voltage, $V_{pack,nom}$ [V]")
    ax.set_ylabel("Battery current [A]")
    ax.set_title(
        "Battery current vs. pack voltage\n"
        "(static & cruise, $C_T$=0.08 reference case, 14S baseline highlighted)"
    )
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "09_battery_current_vs_pack_voltage.png")
    plt.close(fig)


def figure_10_efficiency_sensitivity(static_row) -> None:
    baseline_pack = make_pack(14)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 5.0))

    eta_motor_range = np.linspace(0.80, 0.98, 60)
    currents_vs_motor = []
    for e in eta_motor_range:
        m = MotorAssumptions(eta_motor=float(e), rated_electrical_power_W=4500.0)
        pt = build_electrical_operating_point(static_row, m, default_esc_model(), baseline_pack)
        currents_vs_motor.append(pt.battery_current_A)
    ax1.plot(eta_motor_range, currents_vs_motor, color="tab:blue")
    for e in ETA_MOTOR_SENSITIVITY:
        m = MotorAssumptions(eta_motor=e, rated_electrical_power_W=4500.0)
        pt = build_electrical_operating_point(static_row, m, default_esc_model(), baseline_pack)
        ax1.scatter([e], [pt.battery_current_A], color="tab:red", zorder=5)
        ax1.annotate(
            f"{e:.2f}",
            xy=(e, pt.battery_current_A),
            fontsize=8,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax1.axvline(DEFAULT_ETA_MOTOR, color="black", linestyle=":", linewidth=1.0)
    ax1.set_xlabel(r"$\eta_{motor}$")
    ax1.set_ylabel("Battery current [A]")
    ax1.set_title(r"Battery current vs. $\eta_{motor}$" "\n(14S, static, $\\eta_{ESC}$=0.97)")
    ax1.grid(alpha=0.3)

    default_motor = default_motor_assumptions()
    eta_esc_range = np.linspace(0.90, 0.995, 60)
    currents_vs_esc = []
    for e in eta_esc_range:
        esc = ESCModel(eta_esc=float(e), i_esc_max_A=DEFAULT_ESC_I_MAX_A)
        pt = build_electrical_operating_point(static_row, default_motor, esc, baseline_pack)
        currents_vs_esc.append(pt.battery_current_A)
    ax2.plot(eta_esc_range, currents_vs_esc, color="tab:orange")
    for e in ETA_ESC_SENSITIVITY:
        esc = ESCModel(eta_esc=e, i_esc_max_A=DEFAULT_ESC_I_MAX_A)
        pt = build_electrical_operating_point(static_row, default_motor, esc, baseline_pack)
        ax2.scatter([e], [pt.battery_current_A], color="tab:red", zorder=5)
        ax2.annotate(
            f"{e:.2f}",
            xy=(e, pt.battery_current_A),
            fontsize=8,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax2.axvline(DEFAULT_ETA_ESC, color="black", linestyle=":", linewidth=1.0)
    ax2.set_xlabel(r"$\eta_{ESC}$")
    ax2.set_ylabel("Battery current [A]")
    ax2.set_title(r"Battery current vs. $\eta_{ESC}$" "\n(14S, static, $\\eta_{motor}$=0.90)")
    ax2.grid(alpha=0.3)

    fig.suptitle(
        "Electrical efficiency sensitivity -- static battery current, 14S pack",
        fontsize=12,
    )
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.92))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "10_electrical_efficiency_sensitivity.png")
    plt.close(fig)


def figure_11_final_summary(sel_d, static_row, cruise_row, selection_outcome) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    ax.axis("off")

    sel = selection_outcome.selected
    assert sel is not None

    lines = [
        "Milestone 3 -- final electrical operating summary",
        "",
        f"Fan: D={sel_d:.2f} m (M1/M2 unchanged)   Reference rotational case: "
        f"$C_T$={REFERENCE_C_T:.2f}",
        "",
        f"Selected conceptual pack: {sel.pack_n_series}S "
        f"({sel.pack_v_nom_V:.1f} V nominal, {sel.pack_v_full_V:.1f} V full-charge)",
        f"eta_motor={DEFAULT_ETA_MOTOR:.2f}  eta_ESC={DEFAULT_ETA_ESC:.2f}  "
        f"ESC I_max={DEFAULT_ESC_I_MAX_A:.0f} A (all illustrative)",
        "",
    ]

    header = (
        f"{'Point':<8}{'RPM':>7}{'Mtip':>7}{'Q [Nm]':>8}{'P_sh [W]':>10}"
        f"{'I_bat [A]':>10}{'C-rate':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    static_pt = build_electrical_operating_point(
        static_row, default_motor_assumptions(), default_esc_model(), make_pack(sel.pack_n_series)
    )
    cruise_pt = build_electrical_operating_point(
        cruise_row, default_motor_assumptions(), default_esc_model(), make_pack(sel.pack_n_series)
    )
    for pt in (static_pt, cruise_pt):
        lines.append(
            f"{pt.operating_point:<8}{pt.rpm:>7.0f}{pt.tip_mach:>7.3f}{pt.shaft_torque_Nm:>8.3f}"
            f"{pt.shaft_power_W:>10.1f}{pt.battery_current_A:>10.2f}{pt.c_rate_required:>8.2f}"
        )

    lines.append("")
    lines.append(
        f"Governing margins (static): ESC_I={static_pt.esc_current_margin.margin:+.3f}  "
        f"batt_I={static_pt.battery_current_margin.margin:+.3f}  "
        f"C-rate={static_pt.c_rate_margin.margin:+.3f}"
    )
    lines.append("")
    lines.append("M3 does not invalidate the M1/M2 D=0.50 m fan choice or its")
    lines.append("M2-admissible RPM region -- it adds a downstream electrical")
    lines.append("architecture without changing the aero/rotational requirement.")

    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.3,
        family="monospace",
    )

    fig.tight_layout(rect=(0.0, 0.07, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "11_final_m3_operating_summary.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot generate M3 figures.")
    sel_d = outcome.selected.diameter_m

    rows_ref = reference_rotational_rows(req, sel_d, M1_ASSUMPTION, c_t=REFERENCE_C_T)
    static_row = rows_ref["static"]
    cruise_row = rows_ref["cruise"]

    motor = default_motor_assumptions()
    esc = default_esc_model()
    baseline_pack = make_pack(14)
    static_pt = build_electrical_operating_point(static_row, motor, esc, baseline_pack)
    cruise_pt = build_electrical_operating_point(cruise_row, motor, esc, baseline_pack)

    packs = [make_pack(n) for n in DEFAULT_PACK_SERIES_CANDIDATES]
    selection_outcome = select_pack(static_row, motor, esc, packs)
    if not selection_outcome.success:
        raise RuntimeError("No pack satisfies the M3 selection rule -- cannot summarize.")

    figure_8_power_flow(static_pt, cruise_pt)
    figure_9_current_vs_voltage(static_row, cruise_row)
    figure_10_efficiency_sensitivity(static_row)
    figure_11_final_summary(sel_d, static_row, cruise_row, selection_outcome)
    print(f"Wrote 4 Milestone 3 figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
