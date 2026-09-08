"""Milestone 4 -- energy integration, reserve/usable-energy bookkeeping,
required capacity, and an optional battery-mass proxy.

SOURCED (elementary physics, restated -- see DESIGN.md Milestone 4 source
audit):

    E_J  = P_W * t_s                      (constant-power segment energy)
    E_Wh = E_J / 3600                     (1 Wh = 3600 J, exact)

DERIVED (algebraic bookkeeping, explicit and separately declared -- never
conflated):

    E_required_Wh        = E_mission_Wh * (1 + reserve_fraction)
    E_nominal_required_Wh = E_required_Wh / usable_fraction
    Capacity_required_Ah  = E_nominal_required_Wh / V_pack_nom

ILLUSTRATIVE (Section 21 of DESIGN.md): `reserve_fraction`, `usable_fraction`,
and (if used) `specific_energy_Wh_per_kg` are explicit, labeled sensitivity
assumptions -- not sourced universal UAV battery requirements.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from edf_sizing.mission import MissionProfile, MissionSegment

SECONDS_PER_HOUR = 3600.0  # exact, by definition (1 Wh = 3600 J)


def segment_energy_J(segment: MissionSegment) -> float:
    """E_J = P_total * duration_s for one segment."""
    return segment.total_power_W * segment.duration_s


def segment_energy_Wh(segment: MissionSegment) -> float:
    """E_Wh = E_J / 3600 for one segment."""
    return segment_energy_J(segment) / SECONDS_PER_HOUR


def joules_to_Wh(energy_J: ArrayLike) -> NDArray[np.float64]:
    """Exact J -> Wh conversion: Wh = J / 3600."""
    j = np.asarray(energy_J, dtype=np.float64)
    if np.any(~np.isfinite(j)) or np.any(j < 0):
        raise ValueError(f"energy_J must be finite and >= 0; got {energy_J!r}")
    return j / SECONDS_PER_HOUR


def mission_energy_J(profile: MissionProfile) -> float:
    """Total mission energy, J: sum of each segment's E_J."""
    return sum(segment_energy_J(s) for s in profile.segments)


def mission_energy_Wh(profile: MissionProfile) -> float:
    """Total mission energy, Wh: sum of each segment's E_Wh."""
    return sum(segment_energy_Wh(s) for s in profile.segments)


def reserve_adjusted_energy_Wh(mission_energy_Wh_value: float, reserve_fraction: float) -> float:
    """DERIVED: E_required = E_mission * (1 + reserve_fraction)."""
    if not np.isfinite(mission_energy_Wh_value) or mission_energy_Wh_value < 0:
        raise ValueError(
            f"mission_energy_Wh_value must be finite and >= 0; got {mission_energy_Wh_value!r}"
        )
    if not np.isfinite(reserve_fraction) or reserve_fraction < 0:
        raise ValueError(f"reserve_fraction must be finite and >= 0; got {reserve_fraction!r}")
    return mission_energy_Wh_value * (1.0 + reserve_fraction)


def required_nominal_energy_Wh(required_energy_Wh: float, usable_fraction: float) -> float:
    """DERIVED: E_nominal_required = E_required / usable_fraction."""
    if not np.isfinite(required_energy_Wh) or required_energy_Wh < 0:
        raise ValueError(f"required_energy_Wh must be finite and >= 0; got {required_energy_Wh!r}")
    if not (0.0 < usable_fraction <= 1.0):
        raise ValueError(f"usable_fraction must be in (0, 1]; got {usable_fraction!r}")
    return required_energy_Wh / usable_fraction


def usable_energy_Wh(nominal_energy_Wh: float, usable_fraction: float) -> float:
    """DERIVED inverse: E_usable = usable_fraction * E_nominal (kept
    distinct from `required_nominal_energy_Wh`, its algebraic inverse)."""
    if not np.isfinite(nominal_energy_Wh) or nominal_energy_Wh < 0:
        raise ValueError(f"nominal_energy_Wh must be finite and >= 0; got {nominal_energy_Wh!r}")
    if not (0.0 < usable_fraction <= 1.0):
        raise ValueError(f"usable_fraction must be in (0, 1]; got {usable_fraction!r}")
    return nominal_energy_Wh * usable_fraction


def required_capacity_Ah(nominal_energy_required_Wh: float, v_pack_nom_V: float) -> float:
    """DERIVED: Capacity_required_Ah = E_nominal_required_Wh / V_pack_nom."""
    if not np.isfinite(nominal_energy_required_Wh) or nominal_energy_required_Wh < 0:
        raise ValueError(
            f"nominal_energy_required_Wh must be finite and >= 0; "
            f"got {nominal_energy_required_Wh!r}"
        )
    if not np.isfinite(v_pack_nom_V) or v_pack_nom_V <= 0:
        raise ValueError(f"v_pack_nom_V must be finite and > 0; got {v_pack_nom_V!r}")
    return nominal_energy_required_Wh / v_pack_nom_V


def battery_mass_kg(nominal_energy_required_Wh: float, specific_energy_Wh_per_kg: float) -> float:
    """DERIVED cell/pack-level battery mass PROXY:

        m_batt = E_nominal_required_Wh / specific_energy_Wh_per_kg

    `specific_energy_Wh_per_kg` is always an explicit, illustrative
    sensitivity value (see DESIGN.md Section 19 source audit) -- this is
    NOT a real pack mass estimate (no packaging/BMS/interconnect
    overhead beyond whatever is implicit in the chosen specific-energy
    basis).
    """
    if not np.isfinite(nominal_energy_required_Wh) or nominal_energy_required_Wh < 0:
        raise ValueError(
            f"nominal_energy_required_Wh must be finite and >= 0; "
            f"got {nominal_energy_required_Wh!r}"
        )
    if not np.isfinite(specific_energy_Wh_per_kg) or specific_energy_Wh_per_kg <= 0:
        raise ValueError(
            f"specific_energy_Wh_per_kg must be finite and > 0; "
            f"got {specific_energy_Wh_per_kg!r}"
        )
    return nominal_energy_required_Wh / specific_energy_Wh_per_kg


def cruise_only_energy_diagnostic_hours(
    usable_energy_Wh_value: float, p_cruise_total_W: float
) -> float:
    """RESTRICTED-USE diagnostic: t = E_usable / P_cruise_total.

    This is a "cruise-only constant-power energy diagnostic" ONLY -- it is
    NOT a range, flight-endurance, or mission-duration-capability claim,
    and must never be reported as such. See DESIGN.md Section 15.
    """
    if not np.isfinite(usable_energy_Wh_value) or usable_energy_Wh_value < 0:
        raise ValueError(
            f"usable_energy_Wh_value must be finite and >= 0; got {usable_energy_Wh_value!r}"
        )
    if not np.isfinite(p_cruise_total_W) or p_cruise_total_W <= 0:
        raise ValueError(f"p_cruise_total_W must be finite and > 0; got {p_cruise_total_W!r}")
    return usable_energy_Wh_value / p_cruise_total_W
