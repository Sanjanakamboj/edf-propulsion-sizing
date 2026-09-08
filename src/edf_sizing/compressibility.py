"""Milestone 2 -- ambient speed of sound and blade-tip Mach relations.

Builds on `edf_sizing.rotational.tip_speed`. Nothing here is blade-element
or compressible-flow physics; it is a purely kinematic estimate of the
*helical* speed seen at the blade tip and its ratio to the ambient speed of
sound. See DESIGN.md, Milestone 2 source audit, for exact sourcing.

SOURCED:
    a = sqrt(gamma * R_specific * T)          (ideal-gas speed of sound)
    M_tip,static = U_tip / a
    M_tip,rel    = sqrt(U_tip^2 + V_inf^2) / a   (helical/total tip speed
                   over freestream + rotation, per the classical propeller
                   "helical tip Mach" construction)

The relative-tip-Mach formula is a kinematic vector sum of the tangential
(rotational) tip speed and the axial freestream speed. It is NOT a
blade-section local Mach solution, NOT a compressible blade-element
calculation, and NOT a shock/transonic prediction -- it ignores induced
(axial) velocity through the disk and any spanwise/sweep effects.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class AmbientCondition:
    """Ambient atmospheric assumption used only for the speed of sound.

    Attributes
    ----------
    temperature_K:
        Assumed static ambient temperature, K. Default 288.15 K = 15 degC
        is the ISA sea-level standard temperature, chosen for consistency
        with the Milestone 1 `rho = 1.225 kg/m^3` (ISA sea-level) air
        density assumption. This is a generic illustrative UAV operating
        assumption, not derived from a specific mission profile.
    gamma:
        Ratio of specific heats for air (SOURCED: ideal diatomic gas
        value, standard atmospheric physics).
    r_specific_J_per_kgK:
        Specific gas constant for dry air, J/(kg*K) (SOURCED: standard
        atmospheric physics constant).
    """

    temperature_K: float = 288.15
    gamma: float = 1.4
    r_specific_J_per_kgK: float = 287.05

    def __post_init__(self) -> None:
        if self.temperature_K <= 0:
            raise ValueError(f"temperature_K must be > 0; got {self.temperature_K!r}")
        if self.gamma <= 1.0:
            raise ValueError(f"gamma must be > 1.0; got {self.gamma!r}")
        if self.r_specific_J_per_kgK <= 0:
            raise ValueError(
                f"r_specific_J_per_kgK must be > 0; got {self.r_specific_J_per_kgK!r}"
            )


def speed_of_sound(ambient: AmbientCondition) -> float:
    """Ideal-gas speed of sound a = sqrt(gamma * R_specific * T), m/s."""
    return float(
        np.sqrt(ambient.gamma * ambient.r_specific_J_per_kgK * ambient.temperature_K)
    )


def _as_float_array(x: ArrayLike, name: str) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite; got {x!r}")
    return arr


def static_tip_mach(u_tip_m_s: ArrayLike, a_m_s: float) -> NDArray[np.float64]:
    """Static rotational tip Mach number M_tip,static = U_tip / a."""
    u = _as_float_array(u_tip_m_s, "u_tip_m_s")
    if np.any(u < 0):
        raise ValueError(f"u_tip_m_s must be >= 0; got {u_tip_m_s!r}")
    if a_m_s <= 0:
        raise ValueError(f"a_m_s must be > 0; got {a_m_s!r}")
    return u / a_m_s


def relative_tip_mach(
    u_tip_m_s: ArrayLike, v_inf_m_s: ArrayLike, a_m_s: float
) -> NDArray[np.float64]:
    """Forward-flight relative (helical) tip Mach number.

        M_tip,rel = sqrt(U_tip^2 + V_inf^2) / a

    Reduces exactly to `static_tip_mach` when V_inf = 0.
    """
    u = _as_float_array(u_tip_m_s, "u_tip_m_s")
    v = _as_float_array(v_inf_m_s, "v_inf_m_s")
    if np.any(u < 0):
        raise ValueError(f"u_tip_m_s must be >= 0; got {u_tip_m_s!r}")
    if np.any(v < 0):
        raise ValueError(f"v_inf_m_s must be >= 0; got {v_inf_m_s!r}")
    if a_m_s <= 0:
        raise ValueError(f"a_m_s must be > 0; got {a_m_s!r}")
    return np.sqrt(u**2 + v**2) / a_m_s


@dataclass(frozen=True)
class RpmCeilingResult:
    """Result of the tip-Mach-limited maximum-RPM derivation.

    Attributes
    ----------
    feasible:
        False when even RPM = 0 cannot satisfy the relative-tip-Mach
        constraint (i.e. M_tip_max*a <= V_inf) -- the freestream speed
        alone already meets or exceeds the allowed tip Mach.
    rpm_max:
        Maximum admissible RPM, or None if infeasible.
    u_tip_max_m_s:
        Corresponding maximum admissible tip speed, or None if infeasible.
    reason:
        Human-readable explanation, populated when infeasible.
    """

    feasible: bool
    rpm_max: float | None
    u_tip_max_m_s: float | None
    reason: str | None = None


def max_rpm_for_tip_mach(
    diameter_m: float,
    v_inf_m_s: float,
    m_tip_max: float,
    ambient: AmbientCondition,
) -> RpmCeilingResult:
    """Maximum RPM admissible under a relative-tip-Mach ceiling.

    DERIVED from `relative_tip_mach(U_tip, V_inf, a) <= m_tip_max`:

        sqrt(U_tip^2 + V_inf^2) <= m_tip_max * a
        U_tip <= sqrt((m_tip_max*a)^2 - V_inf^2)          [if m_tip_max*a >= V_inf]
        RPM_max = 60 * U_tip_max / (pi * D)

    With V_inf = 0 this reduces exactly to the static-case closed form
        RPM_max = 60 * m_tip_max * a / (pi * D).

    If `m_tip_max * a <= V_inf`, no RPM (not even RPM = 0) satisfies the
    constraint kinematically, and the case is reported infeasible rather
    than silently clamped.
    """
    if diameter_m <= 0:
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    if v_inf_m_s < 0:
        raise ValueError(f"v_inf_m_s must be >= 0; got {v_inf_m_s!r}")
    if not (0.0 < m_tip_max):
        raise ValueError(f"m_tip_max must be > 0; got {m_tip_max!r}")

    a = speed_of_sound(ambient)
    limit_speed = m_tip_max * a

    if limit_speed <= v_inf_m_s:
        return RpmCeilingResult(
            feasible=False,
            rpm_max=None,
            u_tip_max_m_s=None,
            reason=(
                f"m_tip_max*a = {limit_speed:.2f} m/s <= V_inf = {v_inf_m_s:.2f} m/s: "
                "freestream speed alone already meets/exceeds the allowed tip Mach; "
                "no rotational speed (not even 0 RPM) satisfies the constraint."
            ),
        )

    u_tip_max = float(np.sqrt(limit_speed**2 - v_inf_m_s**2))
    rpm_max = 60.0 * u_tip_max / (np.pi * diameter_m)
    return RpmCeilingResult(feasible=True, rpm_max=rpm_max, u_tip_max_m_s=u_tip_max)


def max_rpm_static(diameter_m: float, m_tip_max: float, ambient: AmbientCondition) -> float:
    """Static-case tip-Mach RPM ceiling: RPM_max = 60*m_tip_max*a/(pi*D).

    Thin, explicit closed-form wrapper -- equal to
    `max_rpm_for_tip_mach(diameter_m, 0.0, m_tip_max, ambient).rpm_max`.
    """
    if diameter_m <= 0:
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    if not (0.0 < m_tip_max):
        raise ValueError(f"m_tip_max must be > 0; got {m_tip_max!r}")
    a = speed_of_sound(ambient)
    return 60.0 * m_tip_max * a / (np.pi * diameter_m)
