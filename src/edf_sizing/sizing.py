"""Candidate fan-diameter sweep, predeclared selection rule, and the final
representative static/cruise thrust table.

This module only combines the ideal actuator-disk relations
(`edf_sizing.actuator_disk`) and the separate non-ideal efficiency layer
(`edf_sizing.efficiency`) with a requirement (`edf_sizing.requirements`).
It adds no new physics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from edf_sizing import actuator_disk as ad
from edf_sizing.efficiency import NonIdealAssumption, estimated_shaft_power
from edf_sizing.requirements import UAVRequirement


@dataclass(frozen=True)
class SelectionLimits:
    """Predeclared, illustrative selection-rule limits.

    These thresholds are chosen BEFORE evaluating any candidate and are not
    tuned to produce a particular answer. See DESIGN.md, section "Fan
    diameter selection rule".

    Attributes
    ----------
    max_disk_loading_N_m2:
        Illustrative upper limit on static disk loading T/A for a small EDF
        UAV concept, N/m^2.
    max_static_ideal_power_W:
        Illustrative upper limit on static ideal power per fan, W.
    """

    max_disk_loading_N_m2: float = 900.0
    max_static_ideal_power_W: float = 3500.0

    def __post_init__(self) -> None:
        if self.max_disk_loading_N_m2 <= 0:
            raise ValueError(
                f"max_disk_loading_N_m2 must be > 0; got {self.max_disk_loading_N_m2!r}"
            )
        if self.max_static_ideal_power_W <= 0:
            raise ValueError(
                f"max_static_ideal_power_W must be > 0; got {self.max_static_ideal_power_W!r}"
            )


DEFAULT_CANDIDATE_DIAMETERS_M: tuple[float, ...] = (
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
)


@dataclass(frozen=True)
class CandidateResult:
    diameter_m: float
    area_m2: float
    disk_loading_N_m2: float
    vi_static_m_s: float
    pi_static_W: float
    p_shaft_static_est_W: float
    meets_disk_loading_limit: bool
    meets_power_limit: bool

    @property
    def meets_selection_rule(self) -> bool:
        return self.meets_disk_loading_limit and self.meets_power_limit


def evaluate_candidates(
    requirement: UAVRequirement,
    assumption: NonIdealAssumption,
    limits: SelectionLimits,
    diameters_m: tuple[float, ...] = DEFAULT_CANDIDATE_DIAMETERS_M,
) -> list[CandidateResult]:
    """Evaluate the static operating point for each candidate fan diameter.

    Static thrust per fan is fixed by the requirement (not by diameter);
    what varies with diameter is disk loading, induced velocity, and power.
    """
    if len(diameters_m) == 0:
        raise ValueError("diameters_m must contain at least one candidate")
    t_static = requirement.static_thrust_per_fan_N
    results: list[CandidateResult] = []
    for d in diameters_m:
        area = float(ad.disk_area(d))
        dl = float(ad.disk_loading(t_static, area))
        vi = float(ad.static_induced_velocity(t_static, requirement.rho_kg_m3, area))
        pi = float(ad.static_ideal_power(t_static, requirement.rho_kg_m3, area))
        p_shaft = float(estimated_shaft_power(pi, assumption))
        results.append(
            CandidateResult(
                diameter_m=d,
                area_m2=area,
                disk_loading_N_m2=dl,
                vi_static_m_s=vi,
                pi_static_W=pi,
                p_shaft_static_est_W=p_shaft,
                meets_disk_loading_limit=dl <= limits.max_disk_loading_N_m2,
                meets_power_limit=pi <= limits.max_static_ideal_power_W,
            )
        )
    return results


@dataclass(frozen=True)
class SelectionOutcome:
    selected: CandidateResult | None
    rule_description: str
    all_candidates: list[CandidateResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.selected is not None


SELECTION_RULE_DESCRIPTION = (
    "Select the smallest candidate diameter (from the predeclared sweep) "
    "that meets the required static thrust per fan while keeping static "
    "disk loading and static ideal power at or below the predeclared "
    "illustrative limits. If no candidate qualifies, report failure "
    "honestly rather than forcing a selection."
)


def select_fan_diameter(candidates: list[CandidateResult]) -> SelectionOutcome:
    """Apply the predeclared selection rule to a list of evaluated candidates.

    Candidates are assumed sorted by ascending diameter (as produced by
    `evaluate_candidates` with the default/ordered sweep); the first one
    satisfying the rule is selected.
    """
    for c in candidates:
        if c.meets_selection_rule:
            return SelectionOutcome(
                selected=c, rule_description=SELECTION_RULE_DESCRIPTION, all_candidates=candidates
            )
    return SelectionOutcome(
        selected=None, rule_description=SELECTION_RULE_DESCRIPTION, all_candidates=candidates
    )


@dataclass(frozen=True)
class ThrustTableRow:
    operating_point: str
    v_inf_m_s: float
    thrust_per_fan_N: float
    disk_loading_N_m2: float
    vi_m_s: float
    pi_W: float
    p_shaft_est_W: float


def build_thrust_table(
    requirement: UAVRequirement,
    diameter_m: float,
    assumption: NonIdealAssumption,
) -> list[ThrustTableRow]:
    """Representative static + cruise thrust table for the selected fan.

    Two operating points, per Milestone 1 scope: static (V_inf = 0) at the
    static thrust requirement, and cruise (V_inf = v_cruise) at the cruise
    thrust requirement.
    """
    area = float(ad.disk_area(diameter_m))
    rows: list[ThrustTableRow] = []

    t_static = requirement.static_thrust_per_fan_N
    vi_static = float(ad.static_induced_velocity(t_static, requirement.rho_kg_m3, area))
    pi_static = float(ad.static_ideal_power(t_static, requirement.rho_kg_m3, area))
    rows.append(
        ThrustTableRow(
            operating_point="static",
            v_inf_m_s=0.0,
            thrust_per_fan_N=t_static,
            disk_loading_N_m2=float(ad.disk_loading(t_static, area)),
            vi_m_s=vi_static,
            pi_W=pi_static,
            p_shaft_est_W=float(estimated_shaft_power(pi_static, assumption)),
        )
    )

    t_cruise = requirement.cruise_thrust_per_fan_N
    v_cruise = requirement.v_cruise_m_s
    vi_cruise = float(
        ad.forward_induced_velocity(t_cruise, requirement.rho_kg_m3, area, v_cruise)
    )
    pi_cruise = float(ad.forward_ideal_power(t_cruise, v_cruise, vi_cruise))
    rows.append(
        ThrustTableRow(
            operating_point="cruise",
            v_inf_m_s=v_cruise,
            thrust_per_fan_N=t_cruise,
            disk_loading_N_m2=float(ad.disk_loading(t_cruise, area)),
            vi_m_s=vi_cruise,
            pi_W=pi_cruise,
            p_shaft_est_W=float(estimated_shaft_power(pi_cruise, assumption)),
        )
    )
    return rows
