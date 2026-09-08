"""Milestone 3 -- series-cell battery pack model (electrical bookkeeping
only; no electrochemical or mission-endurance model).

SOURCED cell-voltage convention (typical LiPo cell, restated from
reputable hobbyist/technical battery references -- see DESIGN.md
Milestone 3 source audit):

    nominal cell voltage     ~= 3.7 V   (rated / mid-discharge voltage,
                                          used for all capacity/power
                                          labeling and bookkeeping)
    full-charge cell voltage ~= 4.2 V   (maximum safe charge voltage)
    minimum/cutoff cell voltage ~= 3.0 V (lowest safe discharge voltage)

These three are clearly distinct and must never be interchanged.

SOURCED pack conventions:

    V_pack_nom  = N_s * V_cell_nom      (e.g. 2S = 7.4 V, 3S = 11.1 V)
    V_pack_full = N_s * V_cell_full
    E_Wh        = V_pack_nom * Capacity_Ah
    C_rate      = I / Capacity_Ah

`capacity_Ah` and `i_continuous_max_A` are pack-level totals (already
reflecting any parallel cell groups); `n_parallel` is retained only as
descriptive metadata, not multiplied into any computed quantity, to keep
the model's inputs unambiguous. No mission-endurance (flight time) claim
is made anywhere -- energy (Wh) exists here only for electrical
bookkeeping (Ah/Wh/C-rate), per the Milestone 3 brief.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

# SOURCED typical LiPo cell voltage convention (see module docstring).
DEFAULT_V_CELL_NOM_V = 3.7
DEFAULT_V_CELL_FULL_V = 4.2
DEFAULT_V_CELL_MIN_V = 3.0


@dataclass(frozen=True)
class BatteryPack:
    """A series (xS) battery pack, generic illustrative LiPo-style chemistry.

    Attributes
    ----------
    n_series:
        Number of series cell groups (the "S" in e.g. "14S"), >= 1.
    capacity_Ah:
        Pack-level total capacity, Ah (already reflecting any parallel
        strings).
    continuous_c_rate_limit:
        Illustrative declared continuous discharge C-rate (e.g. 20.0 for a
        "20C" pack) -- the conventional way continuous current capability
        is specified on battery datasheets/marketing. The pack's continuous
        current limit is DERIVED from this: `i_continuous_max_A =
        capacity_Ah * continuous_c_rate_limit`. A conceptual illustrative
        value, not a manufacturer datasheet rating for any specific cell.
    n_parallel:
        Descriptive metadata only (number of parallel cell groups); not
        used in any computed quantity here.
    v_cell_nom_V, v_cell_full_V, v_cell_min_V:
        SOURCED generic LiPo cell voltage convention (defaults above).
        Must satisfy v_cell_min_V < v_cell_nom_V < v_cell_full_V.
    """

    n_series: int
    capacity_Ah: float
    continuous_c_rate_limit: float
    n_parallel: int = 1
    v_cell_nom_V: float = DEFAULT_V_CELL_NOM_V
    v_cell_full_V: float = DEFAULT_V_CELL_FULL_V
    v_cell_min_V: float = DEFAULT_V_CELL_MIN_V

    def __post_init__(self) -> None:
        if self.n_series < 1:
            raise ValueError(f"n_series must be >= 1; got {self.n_series!r}")
        if self.n_parallel < 1:
            raise ValueError(f"n_parallel must be >= 1; got {self.n_parallel!r}")
        if self.capacity_Ah <= 0:
            raise ValueError(f"capacity_Ah must be > 0; got {self.capacity_Ah!r}")
        if self.continuous_c_rate_limit <= 0:
            raise ValueError(
                f"continuous_c_rate_limit must be > 0; got {self.continuous_c_rate_limit!r}"
            )
        if not (self.v_cell_min_V < self.v_cell_nom_V < self.v_cell_full_V):
            raise ValueError(
                "cell voltages must satisfy v_cell_min_V < v_cell_nom_V < "
                f"v_cell_full_V; got min={self.v_cell_min_V!r}, "
                f"nom={self.v_cell_nom_V!r}, full={self.v_cell_full_V!r}"
            )

    @property
    def v_pack_nom_V(self) -> float:
        """Nominal pack voltage: V_pack_nom = N_s * V_cell_nom."""
        return self.n_series * self.v_cell_nom_V

    @property
    def v_pack_full_V(self) -> float:
        """Full-charge pack voltage: V_pack_full = N_s * V_cell_full."""
        return self.n_series * self.v_cell_full_V

    @property
    def energy_Wh_nom(self) -> float:
        """Nominal pack energy: E_Wh = V_pack_nom * Capacity_Ah (bookkeeping
        only -- not a mission-endurance/flight-time claim)."""
        return self.v_pack_nom_V * self.capacity_Ah

    @property
    def i_continuous_max_A(self) -> float:
        """DERIVED pack continuous current limit: Capacity_Ah *
        continuous_c_rate_limit."""
        return self.capacity_Ah * self.continuous_c_rate_limit

    def c_rate_required(self, current_A: ArrayLike) -> NDArray[np.float64]:
        """Required discharge C-rate = I / Capacity_Ah."""
        i = np.asarray(current_A, dtype=np.float64)
        if np.any(~np.isfinite(i)) or np.any(i < 0):
            raise ValueError(f"current_A must be finite and >= 0; got {current_A!r}")
        return i / self.capacity_Ah
