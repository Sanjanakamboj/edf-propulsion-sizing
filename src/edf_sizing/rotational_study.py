"""Milestone 2 -- combine the Milestone 1 actuator-disk results with
rotational kinematics, tip-Mach constraints, and reduced-order fan
coefficients to build operating tables and a diameter/RPM/tip-Mach trade
study.

This module is purely additive: it imports and reuses Milestone 1
(`edf_sizing.actuator_disk`, `edf_sizing.efficiency`, `edf_sizing.sizing`)
without modifying any of it, and combines it with the new Milestone 2
modules (`edf_sizing.rotational`, `edf_sizing.compressibility`,
`edf_sizing.fan_loading`).

IMPORTANT reduced-order caveat: for a given operating point, RPM is
inferred independently for each assumed thrust-coefficient (C_T)
sensitivity case (Section 8 of DESIGN.md); the Milestone 1 estimated
shaft power `P_shaft_est` is NOT a function of that RPM (it comes only
from the ideal actuator-disk power and the illustrative eta_overall). The
resulting C_P values are therefore a nondimensional bookkeeping exercise,
not a physically matched propeller/fan performance map. This is an
explicit, documented Milestone 2 limitation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from edf_sizing import actuator_disk as ad
from edf_sizing import compressibility as comp
from edf_sizing import fan_loading as fl
from edf_sizing import rotational as rot
from edf_sizing.efficiency import NonIdealAssumption, estimated_shaft_power
from edf_sizing.requirements import UAVRequirement
from edf_sizing.sizing import CandidateResult

# ---------------------------------------------------------------------------
# Milestone 2 assumptions (explicit, illustrative unless noted otherwise)
# ---------------------------------------------------------------------------

DEFAULT_AMBIENT = comp.AmbientCondition()  # ISA sea level, 288.15 K

# ILLUSTRATIVE tip-Mach design ceiling. Informed by a generally cited
# conventional-propeller tip-Mach design practice range of ~0.8-0.9 (see
# DESIGN.md source audit); not a sourced universal EDF-specific limit.
DEFAULT_M_TIP_MAX = 0.85
M_TIP_MAX_SENSITIVITY: tuple[float, ...] = (0.75, 0.85, 0.95)

# ILLUSTRATIVE thrust-coefficient sensitivity set. No sourced universal C_T
# exists for a generic reduced-order EDF unit at this design stage, so RPM
# is reported across this deterministic sensitivity set rather than forcing
# a single "design RPM" (see DESIGN.md Section 8).
C_T_SENSITIVITY_CASES: tuple[float, ...] = (0.05, 0.08, 0.12)


@dataclass(frozen=True)
class RotationalOperatingRow:
    operating_point: str
    c_t: float
    v_inf_m_s: float
    thrust_N: float
    diameter_m: float
    area_m2: float
    n_rev_s: float
    rpm: float
    u_tip_m_s: float
    tip_mach: float
    delta_p_disk_Pa: float
    c_p: float
    advance_ratio_j: float
    pi_ideal_W: float
    p_shaft_est_W: float
    m_tip_max: float
    tip_mach_ok: bool


def build_rotational_operating_table(
    requirement: UAVRequirement,
    diameter_m: float,
    m1_assumption: NonIdealAssumption,
    ambient: comp.AmbientCondition = DEFAULT_AMBIENT,
    m_tip_max: float = DEFAULT_M_TIP_MAX,
    c_t_cases: tuple[float, ...] = C_T_SENSITIVITY_CASES,
) -> list[RotationalOperatingRow]:
    """Static + cruise rotational operating table for one fan diameter,
    swept over the C_T sensitivity set (static and cruise are NOT forced
    to share a C_T -- each operating point is evaluated across the same
    explicit sensitivity set independently)."""
    area = float(ad.disk_area(diameter_m))
    a_sound = comp.speed_of_sound(ambient)
    rows: list[RotationalOperatingRow] = []

    operating_points = (
        ("static", 0.0, requirement.static_thrust_per_fan_N),
        ("cruise", requirement.v_cruise_m_s, requirement.cruise_thrust_per_fan_N),
    )

    for label, v_inf, thrust in operating_points:
        if label == "static":
            pi_ideal = float(ad.static_ideal_power(thrust, requirement.rho_kg_m3, area))
        else:
            vi = float(ad.forward_induced_velocity(thrust, requirement.rho_kg_m3, area, v_inf))
            pi_ideal = float(ad.forward_ideal_power(thrust, v_inf, vi))
        p_shaft_est = float(estimated_shaft_power(pi_ideal, m1_assumption))
        delta_p = float(fl.pressure_jump_disk(thrust, area))

        for c_t in c_t_cases:
            n = float(
                fl.rev_per_second_from_thrust_coefficient(
                    thrust, requirement.rho_kg_m3, diameter_m, c_t
                )
            )
            rpm = float(rot.rev_per_second_to_rpm(n))
            u_tip = float(rot.tip_speed(diameter_m, rpm))
            tip_mach = float(comp.relative_tip_mach(u_tip, v_inf, a_sound))
            c_p = float(fl.power_coefficient(p_shaft_est, requirement.rho_kg_m3, n, diameter_m))
            j = float(fl.advance_ratio(v_inf, n, diameter_m))

            rows.append(
                RotationalOperatingRow(
                    operating_point=label,
                    c_t=c_t,
                    v_inf_m_s=v_inf,
                    thrust_N=thrust,
                    diameter_m=diameter_m,
                    area_m2=area,
                    n_rev_s=n,
                    rpm=rpm,
                    u_tip_m_s=u_tip,
                    tip_mach=tip_mach,
                    delta_p_disk_Pa=delta_p,
                    c_p=c_p,
                    advance_ratio_j=j,
                    pi_ideal_W=pi_ideal,
                    p_shaft_est_W=p_shaft_est,
                    m_tip_max=m_tip_max,
                    tip_mach_ok=tip_mach <= m_tip_max,
                )
            )
    return rows


@dataclass(frozen=True)
class DiameterTradeRow:
    diameter_m: float
    m1_disk_loading_ok: bool
    m1_power_ok: bool
    c_t: float
    rpm: float
    u_tip_m_s: float
    tip_mach_static: float
    m_tip_max: float
    tip_mach_ok: bool

    @property
    def fully_admissible(self) -> bool:
        return self.m1_disk_loading_ok and self.m1_power_ok and self.tip_mach_ok


def evaluate_diameter_rpm_tip_mach_trade(
    requirement: UAVRequirement,
    m1_candidates: list[CandidateResult],
    ambient: comp.AmbientCondition = DEFAULT_AMBIENT,
    m_tip_max: float = DEFAULT_M_TIP_MAX,
    c_t_cases: tuple[float, ...] = C_T_SENSITIVITY_CASES,
) -> list[DiameterTradeRow]:
    """Static-operating-point diameter x RPM/tip-Mach trade study across the
    full Milestone 1 candidate diameter sweep, reusing the already-computed
    Milestone 1 disk-loading/power pass/fail flags for each candidate.
    """
    a_sound = comp.speed_of_sound(ambient)
    t_static = requirement.static_thrust_per_fan_N
    rows: list[DiameterTradeRow] = []
    for c in m1_candidates:
        for c_t in c_t_cases:
            n = float(
                fl.rev_per_second_from_thrust_coefficient(
                    t_static, requirement.rho_kg_m3, c.diameter_m, c_t
                )
            )
            rpm = float(rot.rev_per_second_to_rpm(n))
            u_tip = float(rot.tip_speed(c.diameter_m, rpm))
            tip_mach = float(comp.static_tip_mach(u_tip, a_sound))
            rows.append(
                DiameterTradeRow(
                    diameter_m=c.diameter_m,
                    m1_disk_loading_ok=c.meets_disk_loading_limit,
                    m1_power_ok=c.meets_power_limit,
                    c_t=c_t,
                    rpm=rpm,
                    u_tip_m_s=u_tip,
                    tip_mach_static=tip_mach,
                    m_tip_max=m_tip_max,
                    tip_mach_ok=tip_mach <= m_tip_max,
                )
            )
    return rows


@dataclass(frozen=True)
class SelectionReconciliation:
    diameter_m: float
    m1_selected: bool
    all_c_t_cases_pass_tip_mach: bool
    any_c_t_case_passes_tip_mach: bool
    verdict: str
    rows: list[DiameterTradeRow] = field(default_factory=list)


def reconcile_selection_with_tip_mach(
    trade_rows: list[DiameterTradeRow], selected_diameter_m: float
) -> SelectionReconciliation:
    """Determine whether the Milestone 1 selected diameter remains
    admissible once the Milestone 2 tip-Mach constraint is applied, and
    produce an honest, non-tuned verdict string.
    """
    rows_for_d = [r for r in trade_rows if r.diameter_m == selected_diameter_m]
    if not rows_for_d:
        raise ValueError(
            f"selected_diameter_m={selected_diameter_m!r} not present in trade_rows"
        )
    all_pass = all(r.tip_mach_ok for r in rows_for_d)
    any_pass = any(r.tip_mach_ok for r in rows_for_d)
    m1_ok = all(r.m1_disk_loading_ok and r.m1_power_ok for r in rows_for_d)

    if m1_ok and all_pass:
        verdict = (
            f"M2 does NOT invalidate the Milestone 1 D={selected_diameter_m:.2f} m "
            "selection: it passes the tip-Mach constraint under every C_T "
            "sensitivity case considered. M2 constrains admissible RPM but "
            "leaves the M1 diameter selection unchanged."
        )
    elif m1_ok and any_pass:
        verdict = (
            f"M2 partially constrains the Milestone 1 D={selected_diameter_m:.2f} m "
            "selection: it remains admissible (M1 checks pass) but only for a "
            "subset of the C_T sensitivity cases considered -- some assumed C_T "
            "cases violate the tip-Mach ceiling and are reported as such, not "
            "tuned away."
        )
    else:
        verdict = (
            f"M2 INVALIDATES the Milestone 1 D={selected_diameter_m:.2f} m selection "
            "under the stated rotational assumptions: it fails the M1 disk-loading/"
            "power checks and/or every C_T sensitivity case violates the tip-Mach "
            "ceiling."
        )

    return SelectionReconciliation(
        diameter_m=selected_diameter_m,
        m1_selected=m1_ok,
        all_c_t_cases_pass_tip_mach=all_pass,
        any_c_t_case_passes_tip_mach=any_pass,
        verdict=verdict,
        rows=rows_for_d,
    )
