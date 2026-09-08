#!/usr/bin/env python3
"""Generate the four Milestone 2 portfolio figures (04-07) into figures/.

Purely additive: does not touch or regenerate the three Milestone 1
figures (01-03), which remain the responsibility of scripts/make_figures.py
and must stay byte-identical.

Deterministic: no randomness anywhere in this script, so re-running it
produces byte-identical PNGs (verified in the Milestone 2 quality gates).

Run with:

    python3 scripts/make_rotational_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from edf_sizing import compressibility as comp
from edf_sizing import fan_loading as fl
from edf_sizing import rotational as rot
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
    DEFAULT_CANDIDATE_DIAMETERS_M,
    SelectionLimits,
    evaluate_candidates,
    select_fan_diameter,
)

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

CAVEAT = (
    "Generic reduced-order conceptual EDF study (ideal actuator-disk / momentum "
    "theory + kinematic tip-Mach / nondimensional fan-loading estimates). Not "
    "experimentally validated; not calibrated to any real aircraft or EDF unit. "
    "C_T and M_tip,max are illustrative sensitivity assumptions, not sourced values."
)

M1_ASSUMPTION = NonIdealAssumption(eta_overall=0.75)
M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)

CT_COLORS = {0.05: "tab:blue", 0.08: "tab:green", 0.12: "tab:purple"}

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
        fontsize=7,
        style="italic",
        color="0.35",
        wrap=True,
    )


def figure_4_rpm_vs_diameter(req, selected_diameter_m: float) -> None:
    diameters = np.array(DEFAULT_CANDIDATE_DIAMETERS_M)
    t_static = req.static_thrust_per_fan_N

    fig, ax = plt.subplots(figsize=(8.5, 5.2))

    for c_t in C_T_SENSITIVITY_CASES:
        n = fl.rev_per_second_from_thrust_coefficient(t_static, req.rho_kg_m3, diameters, c_t)
        rpm = rot.rev_per_second_to_rpm(n)
        ax.plot(
            diameters,
            rpm,
            marker="o",
            color=CT_COLORS.get(c_t, "tab:gray"),
            label=f"required RPM, $C_T$={c_t:.2f} (illustrative)",
        )

    rpm_ceiling = np.array(
        [comp.max_rpm_static(d, DEFAULT_M_TIP_MAX, DEFAULT_AMBIENT) for d in diameters]
    )
    ax.plot(
        diameters,
        rpm_ceiling,
        color="tab:red",
        linestyle="--",
        linewidth=1.6,
        label=f"tip-Mach RPM ceiling, $M_{{tip,max}}$={DEFAULT_M_TIP_MAX:.2f} (illustrative)",
    )

    ax.axvline(selected_diameter_m, color="black", linestyle=":", linewidth=1.2)
    ax.annotate(
        f"M1 selected\nD={selected_diameter_m:.2f} m",
        xy=(selected_diameter_m, rpm_ceiling.max() * 0.9),
        xytext=(selected_diameter_m + 0.03, rpm_ceiling.max() * 0.55),
        fontsize=8.5,
        ha="left",
    )

    ax.set_yscale("log")
    ax.set_xlabel("Candidate fan diameter, $D$ [m]")
    ax.set_ylabel("Rotational speed, RPM (log scale)")
    ax.set_title(
        "Required RPM vs. diameter (static thrust) with tip-Mach RPM ceiling\n"
        "(Milestone 1 candidate diameter sweep)"
    )
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3, which="both")

    fig.tight_layout(rect=(0.0, 0.07, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "04_rpm_vs_diameter_tip_mach_ceiling.png")
    plt.close(fig)


def figure_5_tip_mach_vs_rpm(req, diameter_m: float) -> None:
    a_sound = comp.speed_of_sound(DEFAULT_AMBIENT)
    rpm_range = np.linspace(1.0, 14000.0, 300)
    u_tip_range = rot.tip_speed(diameter_m, rpm_range)
    mach_static = comp.static_tip_mach(u_tip_range, a_sound)
    mach_cruise_rel = comp.relative_tip_mach(u_tip_range, req.v_cruise_m_s, a_sound)

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(rpm_range, mach_static, color="tab:blue", label="static, $M_{tip,static}$")
    ax.plot(
        rpm_range,
        mach_cruise_rel,
        color="tab:orange",
        label=f"cruise-relative, $M_{{tip,rel}}$ ($V_\\infty$={req.v_cruise_m_s:.0f} m/s)",
    )

    for m_max in M_TIP_MAX_SENSITIVITY:
        style = "--" if m_max == DEFAULT_M_TIP_MAX else ":"
        width = 1.6 if m_max == DEFAULT_M_TIP_MAX else 1.0
        ax.axhline(m_max, color="tab:red", linestyle=style, linewidth=width, alpha=0.8)
        rpm_ceiling_static = comp.max_rpm_static(diameter_m, m_max, DEFAULT_AMBIENT)
        ax.annotate(
            f"$M_{{tip,max}}$={m_max:.2f}\nRPM$_{{max}}$={rpm_ceiling_static:,.0f}",
            xy=(rpm_range[-1] * 0.99, m_max),
            xytext=(rpm_range[-1] * 0.62, m_max + 0.03),
            fontsize=7.5,
            color="tab:red",
        )

    ax.set_xlabel("Rotational speed, RPM")
    ax.set_ylabel("Blade-tip Mach number")
    ax.set_title(
        f"Tip Mach vs. RPM -- selected fan D={diameter_m:.2f} m\n"
        "(static rotational vs. cruise-relative helical tip Mach)"
    )
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "05_tip_mach_vs_rpm_selected_fan.png")
    plt.close(fig)


def figure_6_static_cruise_summary(req, diameter_m: float, rows) -> None:
    fig, (ax_table, ax_bar) = plt.subplots(
        1, 2, figsize=(11.5, 5.2), gridspec_kw={"width_ratios": [1.35, 1.0]}
    )
    ax_table.axis("off")

    lines = [
        f"Static & cruise rotational summary -- D={diameter_m:.2f} m",
        "",
        f"{'pt':<7}{'C_T':>6}{'T [N]':>9}{'RPM':>8}{'Mach':>7}{'dp [Pa]':>9}{'J':>6}",
        "-" * 52,
    ]
    for r in rows:
        lines.append(
            f"{r.operating_point:<7}{r.c_t:6.2f}{r.thrust_N:9.2f}{r.rpm:8.0f}"
            f"{r.tip_mach:7.3f}{r.delta_p_disk_Pa:9.1f}{r.advance_ratio_j:6.3f}"
        )
    lines.append("")
    lines.append("(C_T sensitivity cases are illustrative; RPM is inferred per case,")
    lines.append(" independently for static and cruise -- not forced equal.)")

    ax_table.text(
        0.0,
        0.98,
        "\n".join(lines),
        transform=ax_table.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        family="monospace",
    )

    c_ts = sorted({r.c_t for r in rows})
    x = np.arange(len(c_ts))
    width = 0.35
    static_mach = [
        next(r.tip_mach for r in rows if r.operating_point == "static" and r.c_t == c)
        for c in c_ts
    ]
    cruise_mach = [
        next(r.tip_mach for r in rows if r.operating_point == "cruise" and r.c_t == c)
        for c in c_ts
    ]

    ax_bar.bar(x - width / 2, static_mach, width, label="static", color="tab:blue")
    ax_bar.bar(x + width / 2, cruise_mach, width, label="cruise-relative", color="tab:orange")
    ax_bar.axhline(
        DEFAULT_M_TIP_MAX,
        color="tab:red",
        linestyle="--",
        linewidth=1.4,
        label=f"$M_{{tip,max}}$={DEFAULT_M_TIP_MAX:.2f} (illustrative)",
    )
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels([f"$C_T$={c:.2f}" for c in c_ts])
    ax_bar.set_ylabel("Blade-tip Mach number")
    ax_bar.set_title("Tip Mach by $C_T$ case")
    ax_bar.legend(loc="upper right", fontsize=7.5)
    ax_bar.grid(alpha=0.3, axis="y")

    fig.suptitle(
        f"Milestone 2 -- static/cruise rotational operating summary, D={diameter_m:.2f} m",
        fontsize=12,
    )
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.93))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "06_static_cruise_rotational_summary.png")
    plt.close(fig)


def figure_7_constraint_map(trade_rows, selected_diameter_m: float) -> None:
    diameters = sorted({r.diameter_m for r in trade_rows})
    c_ts = sorted({r.c_t for r in trade_rows})

    columns = ["M1 disk\nloading", "M1 ideal\npower"] + [f"tip-Mach\n$C_T$={c:.2f}" for c in c_ts]
    grid = np.zeros((len(diameters), len(columns)))

    for i, d in enumerate(diameters):
        rows_d = [r for r in trade_rows if r.diameter_m == d]
        grid[i, 0] = 1.0 if rows_d[0].m1_disk_loading_ok else 0.0
        grid[i, 1] = 1.0 if rows_d[0].m1_power_ok else 0.0
        for j, c_t in enumerate(c_ts):
            row = next(r for r in rows_d if r.c_t == c_t)
            grid[i, 2 + j] = 1.0 if row.tip_mach_ok else 0.0

    fig, ax = plt.subplots(figsize=(8.5, 6.0))
    cmap = ListedColormap(["#d9534f", "#5cb85c"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, fontsize=8.5)
    ax.set_yticks(range(len(diameters)))
    ax.set_yticklabels([f"{d:.2f} m" for d in diameters])
    ax.set_ylabel("Candidate fan diameter, $D$")
    ax.set_title(
        "M1 + M2 final constraint map\n"
        "(disk loading / ideal power / tip-Mach pass = green, fail = red)"
    )

    for i in range(len(diameters)):
        for j in range(len(columns)):
            label = "OK" if grid[i, j] == 1.0 else "FAIL"
            ax.text(j, i, label, ha="center", va="center", fontsize=8, color="black")

    sel_idx = diameters.index(selected_diameter_m)
    ax.add_patch(
        plt.Rectangle(
            (-0.5, sel_idx - 0.5),
            len(columns),
            1,
            fill=False,
            edgecolor="black",
            linewidth=2.5,
        )
    )
    ax.text(
        len(columns) - 0.5 + 0.15,
        sel_idx,
        "M1 selected",
        ha="left",
        va="center",
        fontsize=8.5,
        fontweight="bold",
    )
    ax.set_xlim(-0.5, len(columns) + 1.3)

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "07_m1_m2_constraint_map.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot generate M2 figures.")
    sel_d = outcome.selected.diameter_m

    rows = build_rotational_operating_table(req, sel_d, M1_ASSUMPTION)
    trade_rows = evaluate_diameter_rpm_tip_mach_trade(req, candidates)
    # Touch the reconciliation to fail loudly if it ever raises (keeps this
    # script's success meaningful as a quality gate, not just plotting).
    reconcile_selection_with_tip_mach(trade_rows, sel_d)

    figure_4_rpm_vs_diameter(req, sel_d)
    figure_5_tip_mach_vs_rpm(req, sel_d)
    figure_6_static_cruise_summary(req, sel_d, rows)
    figure_7_constraint_map(trade_rows, sel_d)
    print(f"Wrote 4 Milestone 2 figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
