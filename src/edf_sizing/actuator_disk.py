"""Ideal 1-D actuator-disk (momentum theory) relations.

This module implements ONLY the ideal, inviscid, incompressible actuator-disk
(momentum theory) equations for an isolated fan/rotor disk. No empirical
losses, duct effects, blade count, RPM, or tip-speed physics are included
here -- see `edf_sizing.efficiency` for the explicitly separated non-ideal
bookkeeping layer.

Equations (see DESIGN.md for full derivation and sources):

Disk geometry / loading
    A = pi * D^2 / 4
    disk_loading = T / A

Static (hover, V_inf = 0)
    T  = 2 * rho * A * vi^2
    vi = sqrt(T / (2 * rho * A))
    Pi = T * vi = T^(3/2) / sqrt(2 * rho * A)

Axial forward flight (V_inf > 0)
    T  = 2 * rho * A * vi * (V_inf + vi)
    Pi = T * (V_inf + vi)

    Solving the thrust relation for vi gives a quadratic in vi:
        2*rho*A*vi^2 + 2*rho*A*V_inf*vi - T = 0
    with the single physically valid (non-negative) root
        vi = -V_inf/2 + sqrt((V_inf/2)^2 + T/(2*rho*A))
    which reduces exactly to the static formula as V_inf -> 0.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _as_float_array(x: ArrayLike, name: str) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite; got {x!r}")
    return arr


def disk_area(diameter_m: ArrayLike) -> NDArray[np.float64]:
    """Disk area A = pi * D^2 / 4 for diameter(s) in meters, returned in m^2."""
    d = _as_float_array(diameter_m, "diameter_m")
    if np.any(d <= 0):
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    return np.pi * d**2 / 4.0


def disk_loading(thrust_N: ArrayLike, area_m2: ArrayLike) -> NDArray[np.float64]:
    """Disk loading T/A in N/m^2."""
    t = _as_float_array(thrust_N, "thrust_N")
    a = _as_float_array(area_m2, "area_m2")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(a <= 0):
        raise ValueError(f"area_m2 must be > 0; got {area_m2!r}")
    return t / a


def static_induced_velocity(
    thrust_N: ArrayLike, rho_kg_m3: ArrayLike, area_m2: ArrayLike
) -> NDArray[np.float64]:
    """Static (hover) induced velocity vi = sqrt(T / (2*rho*A)), m/s."""
    t = _as_float_array(thrust_N, "thrust_N")
    rho = _as_float_array(rho_kg_m3, "rho_kg_m3")
    a = _as_float_array(area_m2, "area_m2")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(rho <= 0):
        raise ValueError(f"rho_kg_m3 must be > 0; got {rho_kg_m3!r}")
    if np.any(a <= 0):
        raise ValueError(f"area_m2 must be > 0; got {area_m2!r}")
    return np.sqrt(t / (2.0 * rho * a))


def static_ideal_power(
    thrust_N: ArrayLike, rho_kg_m3: ArrayLike, area_m2: ArrayLike
) -> NDArray[np.float64]:
    """Static ideal power Pi = T^(3/2) / sqrt(2*rho*A), W.

    Equal to T * vi with vi from `static_induced_velocity` (verified in tests
    by independent reconstruction).
    """
    t = _as_float_array(thrust_N, "thrust_N")
    rho = _as_float_array(rho_kg_m3, "rho_kg_m3")
    a = _as_float_array(area_m2, "area_m2")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(rho <= 0):
        raise ValueError(f"rho_kg_m3 must be > 0; got {rho_kg_m3!r}")
    if np.any(a <= 0):
        raise ValueError(f"area_m2 must be > 0; got {area_m2!r}")
    return t**1.5 / np.sqrt(2.0 * rho * a)


def forward_induced_velocity(
    thrust_N: ArrayLike,
    rho_kg_m3: ArrayLike,
    area_m2: ArrayLike,
    v_inf_m_s: ArrayLike,
) -> NDArray[np.float64]:
    """Axial forward-flight induced velocity, m/s.

    Positive physical root of T = 2*rho*A*vi*(V_inf + vi):
        vi = -V_inf/2 + sqrt((V_inf/2)^2 + T/(2*rho*A))

    Reduces exactly to `static_induced_velocity` as V_inf -> 0.
    """
    t = _as_float_array(thrust_N, "thrust_N")
    rho = _as_float_array(rho_kg_m3, "rho_kg_m3")
    a = _as_float_array(area_m2, "area_m2")
    v_inf = _as_float_array(v_inf_m_s, "v_inf_m_s")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(rho <= 0):
        raise ValueError(f"rho_kg_m3 must be > 0; got {rho_kg_m3!r}")
    if np.any(a <= 0):
        raise ValueError(f"area_m2 must be > 0; got {area_m2!r}")
    if np.any(v_inf < 0):
        raise ValueError(f"v_inf_m_s must be >= 0 (axial forward flight); got {v_inf_m_s!r}")
    half_v = v_inf / 2.0
    return -half_v + np.sqrt(half_v**2 + t / (2.0 * rho * a))


def forward_ideal_power(
    thrust_N: ArrayLike, v_inf_m_s: ArrayLike, vi_m_s: ArrayLike
) -> NDArray[np.float64]:
    """Ideal flow power Pi = T * (V_inf + vi), W."""
    t = _as_float_array(thrust_N, "thrust_N")
    v_inf = _as_float_array(v_inf_m_s, "v_inf_m_s")
    vi = _as_float_array(vi_m_s, "vi_m_s")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(v_inf < 0):
        raise ValueError(f"v_inf_m_s must be >= 0; got {v_inf_m_s!r}")
    if np.any(vi < 0):
        raise ValueError(f"vi_m_s must be >= 0; got {vi_m_s!r}")
    return t * (v_inf + vi)
