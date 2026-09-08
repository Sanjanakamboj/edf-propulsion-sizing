"""Milestone 3 -- generic electrical primitives and ESC model.

SOURCED (standard electrical bookkeeping):

    P = V * I                                    (electrical power)
    eta_ESC = P_ESC,out / P_battery,in
    => P_battery = P_ESC,out / eta_ESC = P_motor_elec / eta_ESC
    I_battery = P_battery / V_pack

`eta_ESC`, `i_esc_max_A`, and `p_esc_max_W` are always explicit,
ILLUSTRATIVE assumptions (see `ESCModel`) -- never sourced from a real ESC
datasheet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def electrical_power(voltage_V: ArrayLike, current_A: ArrayLike) -> NDArray[np.float64]:
    """P = V * I, W."""
    v = np.asarray(voltage_V, dtype=np.float64)
    i = np.asarray(current_A, dtype=np.float64)
    if np.any(~np.isfinite(v)) or np.any(v <= 0):
        raise ValueError(f"voltage_V must be finite and > 0; got {voltage_V!r}")
    if np.any(~np.isfinite(i)) or np.any(i < 0):
        raise ValueError(f"current_A must be finite and >= 0; got {current_A!r}")
    return v * i


def current_from_power(power_W: ArrayLike, voltage_V: ArrayLike) -> NDArray[np.float64]:
    """I = P / V, A."""
    p = np.asarray(power_W, dtype=np.float64)
    v = np.asarray(voltage_V, dtype=np.float64)
    if np.any(~np.isfinite(p)) or np.any(p < 0):
        raise ValueError(f"power_W must be finite and >= 0; got {power_W!r}")
    if np.any(~np.isfinite(v)) or np.any(v <= 0):
        raise ValueError(f"voltage_V must be finite and > 0; got {voltage_V!r}")
    return p / v


@dataclass(frozen=True)
class ESCModel:
    """A single illustrative, unsourced ESC efficiency/rating assumption.

    Attributes
    ----------
    eta_esc:
        Assumed ESC efficiency (ESC output power / battery input power),
        0 < eta_esc <= 1. Illustrative only.
    i_esc_max_A:
        Illustrative ESC continuous-current rating, A. A conceptual value,
        not a manufacturer datasheet rating.
    p_esc_max_W:
        Optional illustrative ESC continuous-power rating, W.
    label:
        Short human-readable description recorded alongside any reported
        result so the assumption's illustrative status is traceable.
    """

    eta_esc: float
    i_esc_max_A: float
    p_esc_max_W: float | None = None
    label: str = "illustrative, unsourced ESC efficiency/rating"

    def __post_init__(self) -> None:
        if not (0.0 < self.eta_esc <= 1.0):
            raise ValueError(f"eta_esc must be in (0, 1]; got {self.eta_esc!r}")
        if self.i_esc_max_A <= 0:
            raise ValueError(f"i_esc_max_A must be > 0; got {self.i_esc_max_A!r}")
        if self.p_esc_max_W is not None and self.p_esc_max_W <= 0:
            raise ValueError(f"p_esc_max_W must be > 0 if given; got {self.p_esc_max_W!r}")


def battery_input_power(motor_electrical_power_W: ArrayLike, esc: ESCModel) -> NDArray[np.float64]:
    """P_battery = P_motor_elec / eta_ESC, W."""
    p = np.asarray(motor_electrical_power_W, dtype=np.float64)
    if np.any(~np.isfinite(p)) or np.any(p < 0):
        raise ValueError(
            f"motor_electrical_power_W must be finite and >= 0; got {motor_electrical_power_W!r}"
        )
    return p / esc.eta_esc


def rating_margin(rated_value: float, required_value: ArrayLike) -> NDArray[np.float64]:
    """DERIVED rating margin: MS = rated/required - 1.

    Positive => rating exceeds requirement (margin as a fraction, e.g. 0.20
    means 20% headroom). Negative => rating is insufficient. Never clipped
    to zero -- a negative margin must be reported honestly, not hidden.
    """
    req = np.asarray(required_value, dtype=np.float64)
    if np.any(~np.isfinite(req)) or np.any(req <= 0):
        raise ValueError(f"required_value must be finite and > 0; got {required_value!r}")
    if not np.isfinite(rated_value) or rated_value <= 0:
        raise ValueError(f"rated_value must be finite and > 0; got {rated_value!r}")
    return rated_value / req - 1.0
