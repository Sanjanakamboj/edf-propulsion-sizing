"""Generic representative UAV propulsion requirement.

All numbers below are illustrative, hand-picked, generic values for a small
multirotor/fixed-wing-hybrid EDF-propelled UAV concept. They do NOT
represent any specific real aircraft, and are chosen only to exercise the
sizing model with physically plausible magnitudes. See DESIGN.md, section
"Representative UAV requirement" for the rationale behind each number.
"""

from __future__ import annotations

from dataclasses import dataclass

G_STANDARD = 9.80665  # m/s^2, standard gravity (exact, by definition)


@dataclass(frozen=True)
class UAVRequirement:
    """Generic illustrative UAV propulsion requirement.

    Attributes
    ----------
    mass_kg:
        Assumed total aircraft mass, kg.
    n_fans:
        Number of EDF units sharing the thrust load.
    rho_kg_m3:
        Assumed ambient air density, kg/m^3 (ISA sea level by default).
    v_cruise_m_s:
        Assumed representative cruise freestream speed, m/s.
    static_thrust_to_weight:
        Assumed illustrative static (vertical/hover-equivalent) thrust
        margin, expressed as total thrust / total weight. A value > 1
        leaves control/climb margin; this is a design choice, not a
        derived quantity.
    cruise_lift_to_drag:
        Assumed illustrative cruise lift-to-drag ratio, used only to turn
        aircraft weight into a representative cruise drag/thrust level.
        No aerodynamic (wing/drag-polar) model is implemented -- this is a
        single scalar stand-in so the cruise operating point has a
        physically motivated thrust requirement.
    """

    mass_kg: float = 25.0
    n_fans: int = 2
    rho_kg_m3: float = 1.225
    v_cruise_m_s: float = 30.0
    static_thrust_to_weight: float = 1.2
    cruise_lift_to_drag: float = 8.0

    def __post_init__(self) -> None:
        if self.mass_kg <= 0:
            raise ValueError(f"mass_kg must be > 0; got {self.mass_kg!r}")
        if self.n_fans < 1:
            raise ValueError(f"n_fans must be >= 1; got {self.n_fans!r}")
        if self.rho_kg_m3 <= 0:
            raise ValueError(f"rho_kg_m3 must be > 0; got {self.rho_kg_m3!r}")
        if self.v_cruise_m_s < 0:
            raise ValueError(f"v_cruise_m_s must be >= 0; got {self.v_cruise_m_s!r}")
        if self.static_thrust_to_weight <= 0:
            raise ValueError(
                f"static_thrust_to_weight must be > 0; got {self.static_thrust_to_weight!r}"
            )
        if self.cruise_lift_to_drag <= 0:
            raise ValueError(
                f"cruise_lift_to_drag must be > 0; got {self.cruise_lift_to_drag!r}"
            )

    @property
    def weight_N(self) -> float:
        return self.mass_kg * G_STANDARD

    @property
    def static_thrust_total_N(self) -> float:
        """Total static thrust requirement across all fans, N."""
        return self.static_thrust_to_weight * self.weight_N

    @property
    def static_thrust_per_fan_N(self) -> float:
        return self.static_thrust_total_N / self.n_fans

    @property
    def cruise_thrust_total_N(self) -> float:
        """Total cruise thrust requirement across all fans, N.

        Illustrative: level-flight thrust = weight / (L/D), i.e. drag is
        assumed equal to weight/(L/D) with no separate lift/drag-polar
        model.
        """
        return self.weight_N / self.cruise_lift_to_drag

    @property
    def cruise_thrust_per_fan_N(self) -> float:
        return self.cruise_thrust_total_N / self.n_fans


def default_requirement() -> UAVRequirement:
    """Return the Milestone 1 representative generic UAV requirement."""
    return UAVRequirement()
