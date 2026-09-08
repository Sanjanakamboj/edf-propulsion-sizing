#!/usr/bin/env python3
"""Generate the three Milestone 1 portfolio figures into figures/.

Deterministic: no randomness anywhere in this script, so re-running it
produces byte-identical PNGs (verified in the Milestone 1 quality gates).

Run with:

    python3 scripts/make_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt
import numpy as np

from edf_sizing import actuator_disk as ad
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.requirements import default_requirement
from edf_sizing.sizing import (
    SelectionLimits,
    build_thrust_table,
    evaluate_candidates,
    select_fan_diameter,
)

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

CAVEAT = (
    "Generic reduced-order conceptual EDF study (ideal actuator-disk / "
    "momentum theory). Not experimentally validated; not calibrated to any "
    "real aircraft or EDF unit."
)

ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)

# Fixed, deterministic figure settings.
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
        fontsize=7.5,
        style="italic",
        color="0.35",
        wrap=True,
    )


def figure_1_candidate_sweep(req, candidates) -> None:
    diameters = np.array([c.diameter_m for c in candidates])
    disk_loading = np.array([c.disk_loading_N_m2 for c in candidates])
    ideal_power = np.array([c.pi_static_W for c in candidates])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.2))

    ax1.plot(diameters, disk_loading, marker="o", color="tab:blue")
    ax1.axhline(
        LIMITS.max_disk_loading_N_m2,
        color="tab:red",
        linestyle="--",
        linewidth=1.2,
        label=f"illustrative limit = {LIMITS.max_disk_loading_N_m2:.0f} N/m$^2$",
    )
    ax1.set_xlabel("Candidate fan diameter, $D$ [m]")
    ax1.set_ylabel(r"Static disk loading, $T/A$ [N/m$^2$]")
    ax1.set_title("Disk loading vs. diameter\n(fixed static thrust per fan)")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(alpha=0.3)

    ax2.plot(diameters, ideal_power, marker="o", color="tab:green")
    ax2.axhline(
        LIMITS.max_static_ideal_power_W,
        color="tab:red",
        linestyle="--",
        linewidth=1.2,
        label=f"illustrative limit = {LIMITS.max_static_ideal_power_W:.0f} W",
    )
    ax2.set_xlabel("Candidate fan diameter, $D$ [m]")
    ax2.set_ylabel(r"Static ideal power, $P_i$ [W]")
    ax2.set_title("Ideal actuator-disk power vs. diameter\n(fixed static thrust per fan)")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(alpha=0.3)

    fig.suptitle(
        "Candidate fan-diameter sweep -- static operating point (Milestone 1)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.94))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "01_candidate_sweep_disk_loading_power.png")
    plt.close(fig)


def figure_2_static_vs_cruise(req, diameter_m: float) -> None:
    area = float(ad.disk_area(diameter_m))
    rho = req.rho_kg_m3

    v_inf_range = np.linspace(0.0, req.v_cruise_m_s * 1.4, 200)
    # Illustrative fixed-thrust sweep across speed for the SELECTED fan at
    # its cruise thrust requirement, to show how vi and Pi vary with speed.
    t_cruise = req.cruise_thrust_per_fan_N
    vi_curve = ad.forward_induced_velocity(t_cruise, rho, area, v_inf_range)
    pi_curve = ad.forward_ideal_power(t_cruise, v_inf_range, vi_curve)

    t_static = req.static_thrust_per_fan_N
    vi_static = float(ad.static_induced_velocity(t_static, rho, area))
    pi_static = float(ad.static_ideal_power(t_static, rho, area))

    vi_cruise_pt = float(
        ad.forward_induced_velocity(t_cruise, rho, area, req.v_cruise_m_s)
    )
    pi_cruise_pt = float(ad.forward_ideal_power(t_cruise, req.v_cruise_m_s, vi_cruise_pt))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.2))

    ax1.plot(
        v_inf_range,
        vi_curve,
        color="tab:purple",
        label=f"cruise-thrust curve ($T$={t_cruise:.1f} N)",
    )
    ax1.scatter(
        [0.0], [vi_static], color="black", zorder=5, marker="s", label="static point"
    )
    ax1.scatter(
        [req.v_cruise_m_s],
        [vi_cruise_pt],
        color="tab:red",
        zorder=5,
        marker="o",
        label="cruise point",
    )
    ax1.set_xlabel(r"Freestream speed, $V_\infty$ [m/s]")
    ax1.set_ylabel(r"Induced velocity, $v_i$ [m/s]")
    ax1.set_title("Induced velocity vs. speed")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(alpha=0.3)

    ax2.plot(
        v_inf_range,
        pi_curve,
        color="tab:orange",
        label=f"cruise-thrust curve ($T$={t_cruise:.1f} N)",
    )
    ax2.scatter(
        [0.0],
        [pi_static],
        color="black",
        zorder=5,
        marker="s",
        label=f"static point ($T$={t_static:.1f} N)",
    )
    ax2.scatter(
        [req.v_cruise_m_s],
        [pi_cruise_pt],
        color="tab:red",
        zorder=5,
        marker="o",
        label="cruise point",
    )
    ax2.set_xlabel(r"Freestream speed, $V_\infty$ [m/s]")
    ax2.set_ylabel(r"Ideal power, $P_i$ [W]")
    ax2.set_title("Ideal power vs. speed")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(alpha=0.3)

    fig.suptitle(
        f"Static vs. cruise induced velocity & power -- selected fan D={diameter_m:.2f} m",
        fontsize=12,
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.92))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "02_static_vs_cruise_induced_velocity_power.png")
    plt.close(fig)


def figure_3_selection_summary(req, candidates, outcome, rows) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.axis("off")

    sel = outcome.selected
    assert sel is not None

    lines = [
        "Milestone 1 -- Representative fan sizing summary",
        "",
        f"Generic UAV: mass = {req.mass_kg:.1f} kg, weight = {req.weight_N:.1f} N, "
        f"n_fans = {req.n_fans}",
        f"Air density (assumed) = {req.rho_kg_m3:.3f} kg/m$^3$   "
        f"Cruise speed (assumed) = {req.v_cruise_m_s:.1f} m/s",
        "",
        "Predeclared selection rule: smallest candidate diameter with",
        f"  disk loading $\\leq$ {LIMITS.max_disk_loading_N_m2:.0f} N/m$^2$ "
        f"and static ideal power $\\leq$ {LIMITS.max_static_ideal_power_W:.0f} W.",
        "",
        f"SELECTED conceptual fan diameter: D = {sel.diameter_m:.2f} m "
        f"(A = {sel.area_m2:.4f} m$^2$)",
        "",
    ]

    table_header = (
        f"{'Point':<8}{'V_inf [m/s]':>13}{'T [N]':>10}{'DL [N/m^2]':>13}"
        f"{'v_i [m/s]':>11}{'P_i [W]':>10}{'P_shaft* [W]':>14}"
    )
    lines.append(table_header)
    lines.append("-" * len(table_header))
    for r in rows:
        lines.append(
            f"{r.operating_point:<8}{r.v_inf_m_s:>13.2f}{r.thrust_per_fan_N:>10.2f}"
            f"{r.disk_loading_N_m2:>13.1f}{r.vi_m_s:>11.2f}{r.pi_W:>10.1f}"
            f"{r.p_shaft_est_W:>14.1f}"
        )
    lines.append("")
    lines.append(
        f"(* estimated non-ideal shaft/electrical power assuming illustrative, "
        f"unsourced overall efficiency eta = {ASSUMPTION.eta_overall:.2f})"
    )

    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.5,
        family="monospace",
    )

    fig.tight_layout(rect=(0.0, 0.06, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "03_selected_fan_summary.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    req = default_requirement()
    candidates = evaluate_candidates(req, ASSUMPTION, LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError(
            "No candidate satisfies the selection rule; figures require a "
            "selected fan. Adjust the sweep or limits."
        )
    rows = build_thrust_table(req, outcome.selected.diameter_m, ASSUMPTION)

    figure_1_candidate_sweep(req, candidates)
    figure_2_static_vs_cruise(req, outcome.selected.diameter_m)
    figure_3_selection_summary(req, candidates, outcome, rows)
    print(f"Wrote 3 figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
