"""Milestone 5 -- forward-flight thrust-lapse model.

SOURCED qualitative trend (see DESIGN.md Milestone 5 source audit,
NACA/propeller-literature and ducted-fan references): for a rotor/fan
operating at a fixed rotational speed, achievable thrust decreases as
forward speed (equivalently, advance ratio) increases, relative to the
static value -- "thrust lapse". No compact, universal, source-verified
EDF thrust-lapse curve was found, so this module implements a
transparent, explicitly ILLUSTRATIVE parametric reduced-order model
instead, per the Milestone 5 brief.

    T_available(V) = T_static_available * f_lapse(V)

with the required boundary conditions

    f_lapse(0) = 1
    0 <= f_lapse(V) <= 1   for V >= 0

Two parametric forms are implemented -- a baseline linear form and an
alternative quadratic sensitivity form -- both ILLUSTRATIVE, not fit to
any real EDF unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

LapseKind = Literal["linear", "quadratic"]


@dataclass(frozen=True)
class ThrustLapseModel:
    """An illustrative, unsourced forward-flight thrust-lapse parametrization.

    Attributes
    ----------
    kind:
        "linear": f_lapse(V) = max(0, 1 - k*(V/V_ref))
        "quadratic": f_lapse(V) = max(0, 1 - k*(V/V_ref)^2)
    k:
        Illustrative lapse coefficient, k >= 0. Larger k means faster
        thrust lapse with speed.
    v_ref_m_s:
        Illustrative reference speed used to nondimensionalize V, > 0.
    label:
        Short human-readable description for traceability.
    """

    kind: LapseKind
    k: float
    v_ref_m_s: float
    label: str = "illustrative forward-flight thrust-lapse parametrization"

    def __post_init__(self) -> None:
        if self.kind not in ("linear", "quadratic"):
            raise ValueError(f"kind must be 'linear' or 'quadratic'; got {self.kind!r}")
        if not np.isfinite(self.k) or self.k < 0:
            raise ValueError(f"k must be finite and >= 0; got {self.k!r}")
        if not np.isfinite(self.v_ref_m_s) or self.v_ref_m_s <= 0:
            raise ValueError(f"v_ref_m_s must be finite and > 0; got {self.v_ref_m_s!r}")


def lapse_factor(v_inf_m_s: ArrayLike, model: ThrustLapseModel) -> NDArray[np.float64]:
    """f_lapse(V), dimensionless, bounded to [0, 1], with f_lapse(0) = 1."""
    v = np.asarray(v_inf_m_s, dtype=np.float64)
    if np.any(~np.isfinite(v)) or np.any(v < 0):
        raise ValueError(f"v_inf_m_s must be finite and >= 0; got {v_inf_m_s!r}")
    x = v / model.v_ref_m_s
    if model.kind == "linear":
        raw = 1.0 - model.k * x
    else:
        raw = 1.0 - model.k * x**2
    return np.clip(raw, 0.0, 1.0)


def available_thrust_N(
    thrust_static_available_N: ArrayLike, v_inf_m_s: ArrayLike, model: ThrustLapseModel
) -> NDArray[np.float64]:
    """T_available(V) = T_static_available * f_lapse(V), N."""
    t = np.asarray(thrust_static_available_N, dtype=np.float64)
    if np.any(~np.isfinite(t)) or np.any(t < 0):
        raise ValueError(
            f"thrust_static_available_N must be finite and >= 0; "
            f"got {thrust_static_available_N!r}"
        )
    return t * lapse_factor(v_inf_m_s, model)
