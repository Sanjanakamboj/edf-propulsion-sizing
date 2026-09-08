#!/usr/bin/env python3
"""Generate the four Milestone 4 portfolio figures (12-15) into figures/.

Purely additive: does not touch or regenerate the 11 Milestone 1-3 figures
(01-11), which remain the responsibility of the earlier make_*_figures.py
scripts and must stay byte-identical.

Deterministic: no randomness anywhere in this script, so re-running it
produces byte-identical PNGs (verified in the Milestone 4 quality gates).

Run with:

    python3 scripts/make_mission_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt
import numpy as np

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical_sizing import REFERENCE_C_T, default_esc_model, default_motor_assumptions
from edf_sizing.energy import segment_energy_Wh
from edf_sizing.mission_sizing import (
    DEFAULT_CAPACITY_CANDIDATES_AH,
    DEFAULT_RESERVE_FRACTION,
    DEFAULT_USABLE_FRACTION,
    RESERVE_FRACTION_SENSITIVITY,
    USABLE_FRACTION_SENSITIVITY,
    compute_energy_requirement,
    default_mission_profile,
    m3_reference_battery_powers,
    select_capacity_for_voltage,
)
from edf_sizing.requirements import default_requirement
from edf_sizing.sizing import SelectionLimits, evaluate_candidates, select_fan_diameter

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

CAVEAT = (
    "Generic reduced-order conceptual EDF study. Mission durations, reserve/usable-energy "
    "fractions, and segment power fractions are illustrative conceptual assumptions. Not "
    "experimentally validated; not a trajectory simulation or flight-endurance prediction."
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


def figure_12_power_profile(profile) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.0))

    t = 0.0
    colors = {
        "launch": "tab:red",
        "climb": "tab:orange",
        "cruise": "tab:blue",
        "loiter": "tab:green",
    }
    for s in profile.segments:
        ax.fill_between(
            [t, t + s.duration_s],
            [0, 0],
            [s.total_power_W, s.total_power_W],
            step="post",
            color=colors.get(s.name, "tab:gray"),
            alpha=0.7,
            label=f"{s.name} ({s.total_power_W:,.0f} W)",
        )
        ax.plot(
            [t, t + s.duration_s], [s.total_power_W, s.total_power_W], color="black", linewidth=1.0
        )
        t += s.duration_s

    ax.set_xlabel("Mission time [s]")
    ax.set_ylabel("Total battery power, both fans [W]")
    ax.set_title(
        "Mission battery-power profile (piecewise-constant per segment)\n"
        "generic illustrative mission -- not a trajectory simulation"
    )
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, t)

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "12_mission_power_profile.png")
    plt.close(fig)


def figure_13_energy_by_segment(profile) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 5.2))

    names = [s.name for s in profile.segments]
    energies = [segment_energy_Wh(s) for s in profile.segments]
    colors = ["tab:red", "tab:orange", "tab:blue", "tab:green"]

    bars = ax.bar(names, energies, color=colors[: len(names)])
    total = sum(energies)
    for bar, e in zip(bars, energies, strict=True):
        pct = 100.0 * e / total
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + total * 0.01,
            f"{e:.1f} Wh\n({pct:.0f}%)",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

    ax.set_ylabel("Segment energy [Wh]")
    ax.set_title(
        f"Mission energy by segment (raw mission total = {total:.1f} Wh)\n"
        "cruise dominates due to long duration, not high instantaneous power"
    )
    ax.set_ylim(0, total * 0.65)
    ax.grid(alpha=0.3, axis="y")

    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.90))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "13_mission_energy_by_segment.png")
    plt.close(fig)


def figure_14_capacity_trade(capacity_outcome, energy_req) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 5.2))

    caps = np.array([c.capacity_Ah for c in capacity_outcome.all_candidates])
    usable = np.array([c.usable_Wh for c in capacity_outcome.all_candidates])
    current_ok = np.array([c.current_ok for c in capacity_outcome.all_candidates])
    energy_ok = np.array([c.energy_ok for c in capacity_outcome.all_candidates])

    ax1.plot(caps, usable, marker="o", color="tab:blue", label="usable energy")
    ax1.axhline(
        energy_req.reserve_adjusted_Wh,
        color="tab:red",
        linestyle="--",
        linewidth=1.4,
        label=f"required (reserve-adj.) = {energy_req.reserve_adjusted_Wh:.0f} Wh",
    )
    ax1.set_xlabel("Candidate capacity [Ah]")
    ax1.set_ylabel("Usable energy [Wh]")
    ax1.set_title("Usable energy vs. capacity (14S)")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.3)

    colors = [
        "#5cb85c" if (co and eo) else "#d9534f"
        for co, eo in zip(current_ok, energy_ok, strict=True)
    ]
    ax2.bar(caps.astype(str), np.ones_like(caps), color=colors)
    for i, (co, eo) in enumerate(zip(current_ok, energy_ok, strict=True)):
        label = f"I:{'OK' if co else 'F'}\nE:{'OK' if eo else 'F'}"
        ax2.text(i, 0.5, label, ha="center", va="center", fontsize=7.5)
    ax2.set_yticks([])
    ax2.set_xlabel("Candidate capacity [Ah]")
    ax2.set_title("Current (I) / Energy (E) screen pass-fail")

    fig.suptitle("Battery capacity trade at 14S", fontsize=12)
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.92))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "14_battery_capacity_trade.png")
    plt.close(fig)


def figure_15_sensitivity(p_static, p_cruise, n_fans) -> None:
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12.5, 5.0))

    base_profile = default_mission_profile(p_static, p_cruise, n_fans)

    cruise_durations = np.linspace(300.0, 2400.0, 40)
    required_wh_vs_cruise = []
    for dur in cruise_durations:
        from edf_sizing.mission import MissionProfile, MissionSegment
        from edf_sizing.mission_sizing import (
            CLIMB_DURATION_S,
            LAUNCH_DURATION_S,
            LOITER_DURATION_S,
        )

        prof = MissionProfile(
            segments=(
                MissionSegment("launch", LAUNCH_DURATION_S, p_static, n_fans, 1.0),
                MissionSegment("climb", CLIMB_DURATION_S, p_static, n_fans, 0.70),
                MissionSegment("cruise", float(dur), p_cruise, n_fans, 1.0),
                MissionSegment("loiter", LOITER_DURATION_S, p_cruise, n_fans, 1.20),
            )
        )
        required_wh_vs_cruise.append(compute_energy_requirement(prof).required_nominal_Wh)
    ax1.plot(cruise_durations / 60.0, required_wh_vs_cruise, color="tab:blue")
    ax1.axvline(1200.0 / 60.0, color="black", linestyle=":", linewidth=1.0)
    ax1.set_xlabel("Cruise duration [min]")
    ax1.set_ylabel("Required nominal energy [Wh]")
    ax1.set_title("vs. cruise duration")
    ax1.grid(alpha=0.3)

    usable_range = np.linspace(0.5, 0.95, 40)
    required_wh_vs_usable = [
        compute_energy_requirement(base_profile, usable_fraction=float(f)).required_nominal_Wh
        for f in usable_range
    ]
    ax2.plot(usable_range, required_wh_vs_usable, color="tab:orange")
    ax2.axvline(DEFAULT_USABLE_FRACTION, color="black", linestyle=":", linewidth=1.0)
    for f in USABLE_FRACTION_SENSITIVITY:
        val = compute_energy_requirement(base_profile, usable_fraction=f).required_nominal_Wh
        ax2.scatter([f], [val], color="tab:red", zorder=5)
    ax2.set_xlabel(r"Usable-energy fraction, $f_{usable}$")
    ax2.set_ylabel("Required nominal energy [Wh]")
    ax2.set_title(r"vs. $f_{usable}$")
    ax2.grid(alpha=0.3)

    reserve_range = np.linspace(0.0, 0.6, 40)
    required_wh_vs_reserve = [
        compute_energy_requirement(base_profile, reserve_fraction=float(r)).required_nominal_Wh
        for r in reserve_range
    ]
    ax3.plot(reserve_range, required_wh_vs_reserve, color="tab:green")
    ax3.axvline(DEFAULT_RESERVE_FRACTION, color="black", linestyle=":", linewidth=1.0)
    for r in RESERVE_FRACTION_SENSITIVITY:
        val = compute_energy_requirement(base_profile, reserve_fraction=r).required_nominal_Wh
        ax3.scatter([r], [val], color="tab:red", zorder=5)
    ax3.set_xlabel("Reserve fraction")
    ax3.set_ylabel("Required nominal energy [Wh]")
    ax3.set_title("vs. reserve fraction")
    ax3.grid(alpha=0.3)

    fig.suptitle("Mission-energy sensitivity (dashed line = baseline)", fontsize=12)
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.90))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "15_mission_energy_sensitivity.png")
    plt.close(fig)


def figure_16_final_summary(sel_d, static_row, capacity_outcome, energy_req) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.6))
    ax.axis("off")

    sel = capacity_outcome.selected
    assert sel is not None

    lines = [
        "Milestone 4 -- final mission-energy summary",
        "",
        f"Fan: D={sel_d:.2f} m   RPM(static)={static_row.rpm:.0f}   "
        f"Tip Mach={static_row.tip_mach:.3f}",
        "",
        f"Selected pack: 14S ({sel.v_pack_nom_V:.1f} V), {sel.capacity_Ah:.1f} Ah "
        f"({sel.nominal_Wh:.1f} Wh nominal)",
        "",
        f"Mission energy (raw)       = {energy_req.mission_energy_Wh:.1f} Wh",
        f"Reserve fraction           = {energy_req.reserve_fraction:.2f} (illustrative)",
        f"Usable-energy fraction     = {energy_req.usable_fraction:.2f} (illustrative)",
        f"Required nominal energy    = {energy_req.required_nominal_Wh:.1f} Wh",
        "",
        f"Static battery current     = {sel.static_current_A:.2f} A  "
        f"(C-rate {sel.static_c_rate:.2f})",
        f"Energy margin              = {sel.capacity_margin.margin:+.3f}",
        f"Current margin             = {sel.current_margin.margin:+.3f}",
        "",
        "M4 does not change the M1/M2 fan selection or M2 tip-Mach screen.",
        "It requires a much larger pack capacity than the M3 4.0 Ah baseline",
        "to meet the representative mission's energy demand.",
    ]

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

    fig.tight_layout(rect=(0.0, 0.07, 1.0, 1.0))
    _add_caveat(fig)
    fig.savefig(FIGURES_DIR / "16_final_m4_energy_summary.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    req = default_requirement()
    candidates = evaluate_candidates(req, M1_ASSUMPTION, M1_LIMITS)
    outcome = select_fan_diameter(candidates)
    if not outcome.success:
        raise RuntimeError("Milestone 1 selection failed -- cannot generate M4 figures.")
    sel_d = outcome.selected.diameter_m

    p_static, p_cruise, static_row, _cruise_row = m3_reference_battery_powers(
        req, sel_d, M1_ASSUMPTION, REFERENCE_C_T
    )
    profile = default_mission_profile(p_static, p_cruise, req.n_fans)
    energy_req = compute_energy_requirement(profile)

    motor = default_motor_assumptions()
    esc = default_esc_model()
    capacity_outcome = select_capacity_for_voltage(
        14, DEFAULT_CAPACITY_CANDIDATES_AH, static_row, motor, esc, energy_req
    )
    if not capacity_outcome.success:
        raise RuntimeError("No capacity satisfies the M4 selection rule -- cannot summarize.")

    figure_12_power_profile(profile)
    figure_13_energy_by_segment(profile)
    figure_14_capacity_trade(capacity_outcome, energy_req)
    figure_15_sensitivity(p_static, p_cruise, req.n_fans)
    figure_16_final_summary(sel_d, static_row, capacity_outcome, energy_req)
    print(f"Wrote 5 Milestone 4 figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
