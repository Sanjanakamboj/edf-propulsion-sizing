"""Milestone 3 -- motor electrical-input power and shaft-torque estimate.

Builds on the Milestone 1 `P_shaft_est` (inherited mechanical shaft-power
requirement -- see `edf_sizing.efficiency`) and the Milestone 2 rotational
kinematics (`edf_sizing.rotational.angular_speed`). No electromagnetic,
winding-current, or thermal motor model is implemented here -- motor
behavior is reduced to a single explicit efficiency assumption.

SOURCED (restated from standard electrical-machine bookkeeping, e.g. Tyto
Robotics' brushless-motor power/efficiency reference -- see DESIGN.md
Milestone 3 source audit):

    P_elec = V * I                              (electrical power)
    eta_motor = P_shaft / P_motor_elec           (motor efficiency)
    => P_motor_elec = P_shaft / eta_motor
    P_mech = Q * omega  =>  Q = P_shaft / omega   (shaft torque)

`eta_motor` here is always an explicit, ILLUSTRATIVE assumption (see
`MotorAssumptions`), never a measured/sourced value for any real motor.
This module does not introduce or require any Kv/Kt (motor constant)
relation -- see DESIGN.md Milestone 3 Section on the Kv screen for why it
is deliberately omitted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from edf_sizing.rotational import angular_speed


@dataclass(frozen=True)
class MotorAssumptions:
    """A single illustrative, unsourced motor-efficiency assumption.

    Attributes
    ----------
    eta_motor:
        Assumed motor efficiency (shaft power / electrical input power),
        0 < eta_motor <= 1. Illustrative only.
    rated_electrical_power_W:
        Optional illustrative continuous electrical-power rating used only
        as a predeclared sizing-rule gate (Section 10 of the Milestone 3
        brief) -- NOT a manufacturer datasheet value.
    label:
        Short human-readable description recorded alongside any reported
        result so the assumption's illustrative status is traceable.
    """

    eta_motor: float
    rated_electrical_power_W: float | None = None
    label: str = "illustrative, unsourced motor efficiency"

    def __post_init__(self) -> None:
        if not (0.0 < self.eta_motor <= 1.0):
            raise ValueError(f"eta_motor must be in (0, 1]; got {self.eta_motor!r}")
        if self.rated_electrical_power_W is not None and self.rated_electrical_power_W <= 0:
            raise ValueError(
                f"rated_electrical_power_W must be > 0 if given; "
                f"got {self.rated_electrical_power_W!r}"
            )


def motor_electrical_power(
    shaft_power_W: ArrayLike, assumption: MotorAssumptions
) -> NDArray[np.float64]:
    """Motor electrical input power: P_motor_elec = P_shaft / eta_motor.

    `shaft_power_W` is the Milestone 1 `P_shaft_est` (or the ideal power,
    if a caller deliberately wants that variant) -- this function performs
    no re-derivation of Milestone 1 physics, only the new downstream
    electrical-efficiency division.
    """
    p = np.asarray(shaft_power_W, dtype=np.float64)
    if np.any(~np.isfinite(p)) or np.any(p < 0):
        raise ValueError(f"shaft_power_W must be finite and >= 0; got {shaft_power_W!r}")
    return p / assumption.eta_motor


def shaft_torque(shaft_power_W: ArrayLike, rpm: ArrayLike) -> NDArray[np.float64]:
    """Required shaft torque Q = P_shaft / omega, N*m.

    `omega` comes from `edf_sizing.rotational.angular_speed`. RPM must be
    strictly positive -- torque is undefined at zero rotational speed for
    nonzero power.
    """
    p = np.asarray(shaft_power_W, dtype=np.float64)
    r = np.asarray(rpm, dtype=np.float64)
    if np.any(~np.isfinite(p)) or np.any(p < 0):
        raise ValueError(f"shaft_power_W must be finite and >= 0; got {shaft_power_W!r}")
    if np.any(r <= 0):
        raise ValueError(f"rpm must be > 0 to define torque; got {rpm!r}")
    omega = angular_speed(r)
    return p / omega
