"""Milestone 2 -- pure rotational kinematics for a fan/rotor disk.

Purely geometric/kinematic relations between rotational speed (RPM or
rev/s), angular speed, and blade-tip speed. No aerodynamics, atmosphere, or
compressibility appears in this module -- see `edf_sizing.compressibility`
for speed-of-sound and tip-Mach relations built on top of `tip_speed`.

SOURCED conventions (standard rigid-body rotational kinematics, restated
here for a fan/propeller disk; see DESIGN.md Milestone 2 source audit):

    n     = RPM / 60                     [rev/s]
    omega = 2*pi*n                       [rad/s]
    R     = D / 2                        [m]
    U_tip = omega * R = pi * D * n       [m/s]
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _as_float_array(x: ArrayLike, name: str) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite; got {x!r}")
    return arr


def _validate_rpm(rpm: NDArray[np.float64]) -> None:
    if np.any(rpm < 0):
        raise ValueError(f"rpm must be >= 0; got {rpm!r}")


def _validate_diameter(diameter_m: NDArray[np.float64]) -> None:
    if np.any(diameter_m <= 0):
        raise ValueError(f"diameter_m must be > 0; got {diameter_m!r}")


def rpm_to_rev_per_second(rpm: ArrayLike) -> NDArray[np.float64]:
    """Convert RPM to revolutions per second: n = RPM / 60."""
    r = _as_float_array(rpm, "rpm")
    _validate_rpm(r)
    return r / 60.0


def rev_per_second_to_rpm(n: ArrayLike) -> NDArray[np.float64]:
    """Convert revolutions per second to RPM: RPM = n * 60."""
    nn = _as_float_array(n, "n")
    if np.any(nn < 0):
        raise ValueError(f"n must be >= 0; got {n!r}")
    return nn * 60.0


def angular_speed(rpm: ArrayLike) -> NDArray[np.float64]:
    """Angular speed omega = 2*pi*n = 2*pi*RPM/60, rad/s."""
    r = _as_float_array(rpm, "rpm")
    _validate_rpm(r)
    n = r / 60.0
    return 2.0 * np.pi * n


def tip_speed(diameter_m: ArrayLike, rpm: ArrayLike) -> NDArray[np.float64]:
    """Blade-tip speed U_tip = omega*R = pi*D*n, m/s.

    Equivalent, independent forms (both used for cross-checking in tests):
        U_tip = angular_speed(rpm) * (diameter_m / 2)
        U_tip = pi * diameter_m * rpm_to_rev_per_second(rpm)
    """
    d = _as_float_array(diameter_m, "diameter_m")
    r = _as_float_array(rpm, "rpm")
    _validate_diameter(d)
    _validate_rpm(r)
    n = r / 60.0
    return np.pi * d * n
