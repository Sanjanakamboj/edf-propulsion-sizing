"""Milestone 4 -- mission segment model.

A `MissionSegment` is nothing more than a constant electrical battery
power sustained over a fixed duration -- no aircraft trajectory dynamics
(speed, altitude, acceleration) are modeled. Segment power is always
expressed as a per-fan battery-input power (inherited from Milestone 3)
times the number of active fans, optionally scaled by an explicit,
labeled illustrative multiplier for segments that are not literally the
Milestone 1/2/3 static or cruise operating point (e.g. climb, loiter).

No new aerodynamic power level is invented here -- every multiplier is a
declared fraction of an inherited M3 static/cruise battery power.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MissionSegment:
    """One constant-power mission segment.

    Attributes
    ----------
    name:
        Short segment label (e.g. "launch", "climb", "cruise", "loiter").
    duration_s:
        Segment duration, seconds, >= 0.
    power_per_fan_W:
        Per-fan battery-input electrical power for this segment, W (>= 0).
        Always inherited from a Milestone 3 `ElectricalOperatingPoint`
        (static or cruise), never a newly invented aerodynamic power.
    n_fans:
        Number of active fans drawing this power, >= 1.
    power_multiplier:
        Explicit, illustrative multiplier applied on top of
        `power_per_fan_W` (default 1.0 = use the inherited power
        unmodified). Must be > 0. Used only for segments that are a
        declared fraction of an inherited static/cruise power (e.g.
        climb = 0.70 x static, loiter = 1.20 x cruise) -- see
        DESIGN.md for the exact declared value and rationale.
    label:
        Human-readable note on the multiplier's provenance/illustrative
        status, carried through for reporting.
    """

    name: str
    duration_s: float
    power_per_fan_W: float
    n_fans: int
    power_multiplier: float = 1.0
    label: str = ""

    def __post_init__(self) -> None:
        if self.duration_s < 0:
            raise ValueError(f"duration_s must be >= 0; got {self.duration_s!r}")
        if self.power_per_fan_W < 0:
            raise ValueError(f"power_per_fan_W must be >= 0; got {self.power_per_fan_W!r}")
        if self.n_fans < 1:
            raise ValueError(f"n_fans must be >= 1; got {self.n_fans!r}")
        if self.power_multiplier <= 0:
            raise ValueError(f"power_multiplier must be > 0; got {self.power_multiplier!r}")

    @property
    def total_power_W(self) -> float:
        """Total (all-fans) electrical battery power for this segment, W."""
        return self.power_per_fan_W * self.n_fans * self.power_multiplier


@dataclass(frozen=True)
class MissionProfile:
    """An ordered, predeclared sequence of mission segments."""

    segments: tuple[MissionSegment, ...]

    def __post_init__(self) -> None:
        if len(self.segments) == 0:
            raise ValueError("MissionProfile must contain at least one segment")
