"""Milestone 5 -- non-ideal thrust-effectiveness (fan + duct/inlet loss)
model.

Keeps the Milestone 1 ideal actuator-disk relation (`edf_sizing
.actuator_disk`) completely intact. This module introduces a SEPARATE,
downstream, multiplicative thrust-effectiveness factor:

    T_static_available = eta_T * T_ideal_reference

`eta_T` lumps fan aerodynamic losses, duct/inlet losses, flow
nonuniformity, and other unmodeled installation effects into a single
number. It is ALWAYS an explicit, illustrative sensitivity assumption --
never a measured efficiency for any real EDF unit (see DESIGN.md
Milestone 5 source audit). `eta_T` is deliberately NOT applied to power --
thrust effectiveness and power efficiency are kept distinct; Milestone 3's
`eta_motor`/`eta_ESC` remain the only power-side efficiencies in this
project.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class ThrustEffectivenessModel:
    """A single illustrative, unsourced lumped thrust-effectiveness factor.

    Attributes
    ----------
    eta_T:
        Fraction of the ideal actuator-disk reference thrust the
        installed fan+duct actually delivers at a given (fixed) rotational
        operating point, 0 < eta_T <= 1. Illustrative only.
    label:
        Short human-readable description recorded alongside any reported
        result so the assumption's illustrative status is traceable.
    """

    eta_T: float
    label: str = (
        "illustrative lumped fan+duct thrust-effectiveness factor "
        "(fan aero losses + duct/inlet losses + nonuniformity + "
        "unmodeled installation effects) -- not a measured efficiency"
    )

    def __post_init__(self) -> None:
        if not (0.0 < self.eta_T <= 1.0):
            raise ValueError(f"eta_T must be in (0, 1]; got {self.eta_T!r}")


def static_available_thrust_N(
    thrust_ideal_reference_N: ArrayLike, model: ThrustEffectivenessModel
) -> NDArray[np.float64]:
    """T_static_available = eta_T * T_ideal_reference, N.

    `thrust_ideal_reference_N` is the Milestone 1 ideal actuator-disk
    thrust the fan was sized to produce at the reference (V_inf = 0)
    operating point -- never re-derived here.
    """
    t = np.asarray(thrust_ideal_reference_N, dtype=np.float64)
    if np.any(~np.isfinite(t)) or np.any(t < 0):
        raise ValueError(
            f"thrust_ideal_reference_N must be finite and >= 0; got {thrust_ideal_reference_N!r}"
        )
    return t * model.eta_T
