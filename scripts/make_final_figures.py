#!/usr/bin/env python3
"""Generate the five Milestone 6 portfolio figures (22-26) into figures/.

Purely additive: does not touch or regenerate the 21 Milestone 1-5 figures
(01-21), which remain the responsibility of the earlier make_*_figures.py
scripts and must stay byte-identical.

Deterministic: no randomness anywhere in this script, so re-running it
produces byte-identical PNGs (verified in the Milestone 6 quality gates).

Run with:

    python3 scripts/make_final_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt
import numpy as np

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import reference_rotational_rows
from edf_sizing.requirements import default_requirement
from edf_sizing.robustness import (
    BASELINE,
    ETA_MOTOR_GRID,
    ETA_T_GRID,
    RobustnessCase,
    build_constraint_table,
    evaluate_baseline,
    evaluate_case,
    rank_sensitivities,
    sweep_diameter,
)

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

CAVEAT = (
    "Generic reduced-order EDF study -- not experimentally validated, not a real product or "
    "flight-qualified architecture. Sensitivity ranges are deterministic engineering cases."
)

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


def figure_22_constraint_margins(table) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    names = [r.name.split(". ", 1)[-1] for r in table]
    margins = [r.margin for r in table]
    colors = ["#5cb85c" if m >= 0 else "#d9534f" for m in margins]

    y_pos = np.arange(len(names))
    ax.barh(y_pos, margins, color=colors)
    ax.axvline(0.0, color="black", linewidth=1.0)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Margin (rated/required - 1)")
    ax.set_title(
        "Final constraint margins (baseline: $\\eta_T$=0.90, 14S/28Ah, $C_T$=0.08)\n"
        "Row G is the honest pre-recovery static-thrust diagnostic (see DESIGN.md)"
    )
    for y, m in zip(y_pos, margins, strict=True):
        ax.text(m + (0.05 if m >= 0 else -0.05), y, f"{m:+.2f}", va="center",
                 ha="left" if m >= 0 else "right", fontsize=8)
    ax.grid(alpha=0.3, axis="x")

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "22_final_constraint_margins.png")
    plt.close(fig)


def figure_23_feasibility_map(req) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.5))

    eta_t_vals = ETA_T_GRID
    eta_motor_vals = ETA_MOTOR_GRID

    grid = np.zeros((len(eta_motor_vals), len(eta_t_vals)))
    for i, em in enumerate(eta_motor_vals):
        for j, et in enumerate(eta_t_vals):
            r = evaluate_case(req, RobustnessCase(eta_T=et, eta_motor=em))
            grid[i, j] = 1.0 if r.feasible else 0.0

    from matplotlib.colors import ListedColormap

    cmap = ListedColormap(["#d9534f", "#5cb85c"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto", origin="lower")
    ax.set_xticks(range(len(eta_t_vals)))
    ax.set_xticklabels([f"{v:.2f}" for v in eta_t_vals])
    ax.set_yticks(range(len(eta_motor_vals)))
    ax.set_yticklabels([f"{v:.2f}" for v in eta_motor_vals])
    ax.set_xlabel(r"Thrust effectiveness, $\eta_T$")
    ax.set_ylabel(r"Motor efficiency, $\eta_{motor}$")
    ax.set_title(
        "Final feasibility map: $\\eta_T$ x $\\eta_{motor}$ (14S/28Ah baseline)\n"
        "green = FEASIBLE, red = INFEASIBLE"
    )
    for i in range(len(eta_motor_vals)):
        for j in range(len(eta_t_vals)):
            label = "OK" if grid[i, j] == 1.0 else "FAIL"
            ax.text(j, i, label, ha="center", va="center", fontsize=8, color="black")

    baseline_i = eta_motor_vals.index(BASELINE.eta_motor)
    baseline_j = eta_t_vals.index(BASELINE.eta_T)
    ax.add_patch(
        plt.Rectangle(
            (baseline_j - 0.5, baseline_i - 0.5), 1, 1, fill=False, edgecolor="black", linewidth=3
        )
    )

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.92))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "23_final_feasibility_map.png")
    plt.close(fig)


def figure_24_diameter_robustness(diam_results) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 8.0))
    diameters = [r.case.diameter_m for r in diam_results]

    rpm_req = [r.envelope.rpm_recovery.rpm_required for r in diam_results]
    ceilings = [r.envelope.rpm_recovery.rpm_ceiling for r in diam_results]
    axes[0, 0].plot(diameters, rpm_req, marker="o", color="tab:blue", label="RPM required")
    axes[0, 0].plot(
        diameters, ceilings, marker="s", color="tab:red", linestyle="--",
        label="tip-Mach ceiling",
    )
    axes[0, 0].set_xlabel("Diameter [m]")
    axes[0, 0].set_ylabel("RPM")
    axes[0, 0].set_title("RPM recovery vs. ceiling")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(alpha=0.3)

    tip_mach = [r.envelope.rpm_recovery.tip_mach_at_recovery for r in diam_results]
    axes[0, 1].plot(diameters, tip_mach, marker="o", color="tab:purple")
    m_tip_label = f"$M_{{tip,max}}$={BASELINE.m_tip_max:.2f}"
    axes[0, 1].axhline(BASELINE.m_tip_max, color="tab:red", linestyle="--", label=m_tip_label)
    axes[0, 1].set_xlabel("Diameter [m]")
    axes[0, 1].set_ylabel("Tip Mach at recovery")
    axes[0, 1].set_title("Recovered tip Mach")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.3)

    currents = [r.envelope.recovered_electrical.battery_current_A for r in diam_results]
    axes[1, 0].plot(diameters, currents, marker="o", color="tab:orange")
    axes[1, 0].set_xlabel("Diameter [m]")
    axes[1, 0].set_ylabel("Battery current [A]")
    axes[1, 0].set_title("Recovered battery current")
    axes[1, 0].grid(alpha=0.3)

    margins = [r.envelope.mission_energy_penalty.capacity_margin.margin for r in diam_results]
    colors = ["#5cb85c" if r.feasible else "#d9534f" for r in diam_results]
    axes[1, 1].bar([f"{d:.2f}" for d in diameters], margins, color=colors)
    axes[1, 1].axhline(0.0, color="black", linewidth=1.0)
    axes[1, 1].set_xlabel("Diameter [m]")
    axes[1, 1].set_ylabel("Mission-energy margin")
    axes[1, 1].set_title("Energy margin (green=feasible, red=infeasible)")
    axes[1, 1].grid(alpha=0.3, axis="y")

    fig.suptitle("Diameter robustness (0.45-0.60 m, baseline $\\eta_T$=0.90)", fontsize=13)
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.95))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "24_final_diameter_robustness.png")
    plt.close(fig)


def figure_25_sensitivity_ranking(rankings) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    names = [r.parameter for r in rankings]
    swings = [r.max_fractional_swing for r in rankings]
    colors = ["#d9534f" if r.feasibility_flips else "#5b9bd5" for r in rankings]

    y_pos = np.arange(len(names))
    ax.barh(y_pos, swings, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Max fractional swing in governing-margin metric")
    ax.set_title(
        "Sensitivity ranking (computed, not asserted)\n"
        "red = flips feasibility across its tested range"
    )
    for y, s in zip(y_pos, swings, strict=True):
        ax.text(s + 0.02, y, f"{s:.2f}", va="center", fontsize=8)
    ax.grid(alpha=0.3, axis="x")

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.92))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "25_final_sensitivity_ranking.png")
    plt.close(fig)


def figure_26_flagship_summary(req, envelope, table) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 8.5))

    # Panel 1: fan / RPM
    ax = axes[0, 0]
    ax.axis("off")
    m1_assumption = NonIdealAssumption(eta_overall=BASELINE.eta_overall)
    static_row = reference_rotational_rows(
        req, BASELINE.diameter_m, m1_assumption, BASELINE.reference_c_t
    )["static"]
    lines1 = [
        "Fan / rotational",
        f"D = {BASELINE.diameter_m:.2f} m   $C_T$ = {BASELINE.reference_c_t:.2f}",
        f"static RPM = {static_row.rpm:.0f}",
        f"tip Mach (ref.) = {static_row.tip_mach:.3f}",
        f"recovery RPM = {envelope.rpm_recovery.rpm_required:.0f}",
        f"tip Mach (recovery) = {envelope.rpm_recovery.tip_mach_at_recovery:.3f}",
        f"ceiling = {envelope.rpm_recovery.rpm_ceiling:.0f} "
        f"($M_{{tip,max}}$={BASELINE.m_tip_max:.2f})",
    ]
    ax.text(
        0.02, 0.95, "\n".join(lines1), transform=ax.transAxes, va="top",
        fontsize=10, family="monospace",
    )

    # Panel 2: thrust
    ax = axes[0, 1]
    labels = ["static\nrequired", "static\navailable", "cruise\nrequired", "cruise\navailable"]
    values = [
        req.static_thrust_per_fan_N,
        envelope.static_margin.thrust_available_N,
        req.cruise_thrust_per_fan_N,
        envelope.cruise_margin.thrust_available_N,
    ]
    colors = ["0.5", "tab:red", "0.5", "tab:green"]
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("Thrust per fan [N]")
    ax.set_title("Static/cruise thrust (baseline RPM)")
    ax.grid(alpha=0.3, axis="y")

    # Panel 3: electrical chain
    ax = axes[1, 0]
    stages = ["shaft\n(ref.)", "shaft\n(recov.)", "motor\nelec.", "battery"]
    p_vals = [
        envelope.recovered_electrical.shaft_power_reference_W,
        envelope.recovered_electrical.shaft_power_recovered_W,
        envelope.recovered_electrical.motor_electrical_power_W,
        envelope.recovered_electrical.battery_power_W,
    ]
    ax.bar(stages, p_vals, color="tab:blue")
    ax.set_ylabel("Power [W]")
    ax.set_title(f"Electrical chain (I={envelope.recovered_electrical.battery_current_A:.1f} A)")
    ax.grid(alpha=0.3, axis="y")

    # Panel 4: mission energy / robustness
    ax = axes[1, 1]
    ax.axis("off")
    mp = envelope.mission_energy_penalty
    lines4 = [
        "Mission energy / robustness",
        f"M4 baseline = {mp.mission_energy_m4_baseline_Wh:.0f} Wh",
        f"M5 updated  = {mp.mission_energy_m5_Wh:.0f} Wh",
        f"28 Ah usable = {mp.pack_usable_Wh:.0f} Wh",
        f"capacity margin = {mp.capacity_margin.margin:+.3f}",
        "",
        f"OVERALL FEASIBLE: {envelope.feasible}",
        "governing (post-recovery): mission energy",
    ]
    ax.text(
        0.02, 0.95, "\n".join(lines4), transform=ax.transAxes, va="top",
        fontsize=10, family="monospace",
    )

    fig.suptitle(
        "EDF Propulsion Sizing -- flagship summary (D=0.50 m, 14S/28Ah, $\\eta_T$=0.90)",
        fontsize=13,
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.95))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "26_final_edf_sizing_summary.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    req = default_requirement()
    envelope = evaluate_baseline(req, BASELINE)
    table = build_constraint_table(req, BASELINE, envelope)
    diam_results = sweep_diameter(req)
    rankings = rank_sensitivities(req)

    figure_22_constraint_margins(table)
    figure_23_feasibility_map(req)
    figure_24_diameter_robustness(diam_results)
    figure_25_sensitivity_ranking(rankings)
    figure_26_flagship_summary(req, envelope, table)
    print(f"Wrote 5 Milestone 6 figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
