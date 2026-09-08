"""Milestone 2 -- reduced-order fan pressure-jump and nondimensional
thrust/power/advance-ratio coefficients.

Conventions (SOURCED -- see DESIGN.md Milestone 2 source audit, matching
the classical NACA/propeller-literature definitions with `n` in rev/s and
`D` in meters):

    C_T = T / (rho * n^2 * D^4)
    C_P = P / (rho * n^3 * D^5)
    J   = V_inf / (n * D)

`P` in `C_P` is whatever power is supplied to it by the caller; in this
project it is always the Milestone 1 *illustrative estimated shaft power*
(`edf_sizing.efficiency.estimated_shaft_power`), never the ideal
actuator-disk power and never a measured/calibrated fan efficiency. Callers
must not relabel `eta_overall = 0.75` as a measured fan efficiency.

The disk pressure-jump estimate

    Delta_p_disk = T / A

is numerically identical to the Milestone 1 disk-loading quantity
(`edf_sizing.actuator_disk.disk_loading`) -- it is the same actuator-disk
momentum-theory quantity, given a distinct name here only to make the
"static pressure rise across an idealized disk" interpretation explicit.
It is NOT a fan-stage pressure ratio and does NOT model any real internal
static-pressure distribution through an EDF duct/rotor/stator stage.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _as_float_array(x: ArrayLike, name: str) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite; got {x!r}")
    return arr


def pressure_jump_disk(thrust_N: ArrayLike, area_m2: ArrayLike) -> NDArray[np.float64]:
    """Idealized actuator-disk static pressure jump, Delta_p = T/A, Pa.

    Numerically identical to `edf_sizing.actuator_disk.disk_loading` --
    see module docstring for the distinct interpretation.
    """
    t = _as_float_array(thrust_N, "thrust_N")
    a = _as_float_array(area_m2, "area_m2")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(a <= 0):
        raise ValueError(f"area_m2 must be > 0; got {area_m2!r}")
    return t / a


def _validate_n(n: NDArray[np.float64]) -> None:
    if np.any(n <= 0):
        raise ValueError(
            f"n (rev/s) must be > 0 -- rotational coefficients are undefined at zero "
            f"RPM; got {n!r}"
        )


def thrust_coefficient(
    thrust_N: ArrayLike, rho_kg_m3: ArrayLike, n_rev_s: ArrayLike, diameter_m: ArrayLike
) -> NDArray[np.float64]:
    """C_T = T / (rho * n^2 * D^4). n is rev/s (n > 0 required)."""
    t = _as_float_array(thrust_N, "thrust_N")
    rho = _as_float_array(rho_kg_m3, "rho_kg_m3")
    n = _as_float_array(n_rev_s, "n_rev_s")
    d = _as_float_array(diameter_m, "diameter_m")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(rho <= 0):
        raise ValueError(f"rho_kg_m3 must be > 0; got {rho_kg_m3!r}")
    _validate_n(n)
    if np.any(d <= 0):
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    return t / (rho * n**2 * d**4)


def power_coefficient(
    power_W: ArrayLike, rho_kg_m3: ArrayLike, n_rev_s: ArrayLike, diameter_m: ArrayLike
) -> NDArray[np.float64]:
    """C_P = P / (rho * n^3 * D^5). n is rev/s (n > 0 required).

    `power_W` must be the Milestone 1 illustrative estimated shaft power
    (or the ideal power, if the caller explicitly wants that variant) --
    never silently relabeled as a measured/sourced fan efficiency.
    """
    p = _as_float_array(power_W, "power_W")
    rho = _as_float_array(rho_kg_m3, "rho_kg_m3")
    n = _as_float_array(n_rev_s, "n_rev_s")
    d = _as_float_array(diameter_m, "diameter_m")
    if np.any(p < 0):
        raise ValueError(f"power_W must be >= 0; got {power_W!r}")
    if np.any(rho <= 0):
        raise ValueError(f"rho_kg_m3 must be > 0; got {rho_kg_m3!r}")
    _validate_n(n)
    if np.any(d <= 0):
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    return p / (rho * n**3 * d**5)


def advance_ratio(
    v_inf_m_s: ArrayLike, n_rev_s: ArrayLike, diameter_m: ArrayLike
) -> NDArray[np.float64]:
    """J = V_inf / (n * D). n is rev/s (n > 0 required)."""
    v = _as_float_array(v_inf_m_s, "v_inf_m_s")
    n = _as_float_array(n_rev_s, "n_rev_s")
    d = _as_float_array(diameter_m, "diameter_m")
    if np.any(v < 0):
        raise ValueError(f"v_inf_m_s must be >= 0; got {v_inf_m_s!r}")
    _validate_n(n)
    if np.any(d <= 0):
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    return v / (n * d)


def rev_per_second_from_thrust_coefficient(
    thrust_N: ArrayLike,
    rho_kg_m3: ArrayLike,
    diameter_m: ArrayLike,
    c_t: ArrayLike,
) -> NDArray[np.float64]:
    """DERIVED inversion of C_T = T/(rho*n^2*D^4) for n (rev/s):

        n = sqrt(T / (rho * C_T * D^4))

    `c_t` is an explicit, caller-supplied sensitivity assumption (see
    DESIGN.md) -- this project does not assert a single sourced universal
    C_T for EDF units.
    """
    t = _as_float_array(thrust_N, "thrust_N")
    rho = _as_float_array(rho_kg_m3, "rho_kg_m3")
    d = _as_float_array(diameter_m, "diameter_m")
    ct = _as_float_array(c_t, "c_t")
    if np.any(t < 0):
        raise ValueError(f"thrust_N must be >= 0; got {thrust_N!r}")
    if np.any(rho <= 0):
        raise ValueError(f"rho_kg_m3 must be > 0; got {rho_kg_m3!r}")
    if np.any(d <= 0):
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")
    if np.any(ct <= 0):
        raise ValueError(f"c_t must be > 0; got {c_t!r}")
    return np.sqrt(t / (rho * ct * d**4))
