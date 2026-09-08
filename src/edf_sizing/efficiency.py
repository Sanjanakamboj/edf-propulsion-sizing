"""Non-ideal efficiency bookkeeping layer -- explicitly separated from the
ideal actuator-disk physics in `edf_sizing.actuator_disk`.

Ideal actuator-disk power (Pi) is a lower-bound, loss-free flow power. Real
EDF units incur profile drag, swirl, duct/inlet losses, motor and ESC
losses, etc. None of those mechanisms are modeled here. Instead we apply a
single illustrative *overall propulsive/fan efficiency* to convert ideal
power to an estimated shaft/electrical power:

    P_shaft_est = Pi / eta_overall

`eta_overall` is a placeholder assumption, NOT a sourced or calibrated
coefficient for any real EDF unit. It must be clearly labeled illustrative
wherever it is reported. See DESIGN.md, section "Non-ideal efficiency layer".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class NonIdealAssumption:
    """A single illustrative, unsourced efficiency assumption.

    Attributes
    ----------
    eta_overall:
        Assumed overall propulsive/fan efficiency (ideal power / shaft
        power), 0 < eta_overall <= 1. Illustrative only -- see DESIGN.md.
    label:
        Short human-readable description recorded alongside any reported
        result so the assumption's illustrative status is traceable.
    """

    eta_overall: float
    label: str = "illustrative, unsourced overall propulsive/fan efficiency"

    def __post_init__(self) -> None:
        if not (0.0 < self.eta_overall <= 1.0):
            raise ValueError(
                f"eta_overall must be in (0, 1]; got {self.eta_overall!r}"
            )


def estimated_shaft_power(
    ideal_power_W: ArrayLike, assumption: NonIdealAssumption
) -> NDArray[np.float64]:
    """Estimated non-ideal shaft/electrical power, W.

    P_shaft_est = Pi / eta_overall. This is a bookkeeping estimate built on
    top of the ideal actuator-disk power, not a re-derivation of it -- it
    must never be called "ideal power".
    """
    pi = np.asarray(ideal_power_W, dtype=np.float64)
    if np.any(~np.isfinite(pi)) or np.any(pi < 0):
        raise ValueError(f"ideal_power_W must be finite and >= 0; got {ideal_power_W!r}")
    return pi / assumption.eta_overall
