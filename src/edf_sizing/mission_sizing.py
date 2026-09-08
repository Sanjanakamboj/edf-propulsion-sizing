"""Milestone 4 -- combine the Milestone 1-3 aerodynamic/rotational/
electrical results with the mission/energy modules into a representative
mission definition, a battery energy requirement, a capacity candidate
sweep, and a pack-voltage carry-forward trade.

Purely additive: imports and reuses Milestone 1-3
(`edf_sizing.requirements`, `edf_sizing.efficiency`,
`edf_sizing.rotational_study`, `edf_sizing.electrical_sizing`) without
modifying any of them, and combines them with the new Milestone 4 modules
(`edf_sizing.mission`, `edf_sizing.energy`).

IMPORTANT modeling note (see DESIGN.md Section 21 for the full
discussion): Milestone 3's battery CURRENT/C-rate screening is evaluated
per-fan (one motor/ESC/battery circuit), frozen exactly as committed.
Milestone 4's mission ENERGY, per the Milestone 4 brief ("total battery
power uses both fans"), is evaluated at the whole-aircraft level
(per-fan power x n_fans). A single candidate pack is therefore screened
against two conventions that are not perfectly architecturally unified
(per-fan current vs. whole-aircraft energy) -- this is deliberate,
matches the Milestone 4 brief's explicit instructions, and is documented
as a named limitation rather than silently reconciled.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel, rating_margin
from edf_sizing.electrical_sizing import (
    DEFAULT_C_RATE_LIMIT,
    RatingMargin,
    build_electrical_operating_point,
    default_esc_model,
    default_motor_assumptions,
    make_pack,
    reference_rotational_rows,
)
from edf_sizing.energy import (
    mission_energy_Wh,
    required_capacity_Ah,
    required_nominal_energy_Wh,
    reserve_adjusted_energy_Wh,
    usable_energy_Wh,
)
from edf_sizing.mission import MissionProfile, MissionSegment
from edf_sizing.motor import MotorAssumptions
from edf_sizing.requirements import UAVRequirement
from edf_sizing.rotational_study import RotationalOperatingRow

# ---------------------------------------------------------------------------
# Predeclared mission profile (Section 6 of the Milestone 4 brief)
# ---------------------------------------------------------------------------

LAUNCH_DURATION_S = 30.0
CLIMB_DURATION_S = 120.0
CRUISE_DURATION_S = 1200.0  # 20 min
LOITER_DURATION_S = 300.0  # 5 min

# ILLUSTRATIVE declared fractions of inherited M3 static/cruise battery
# power -- no new aerodynamic power level is invented.
CLIMB_POWER_FRACTION_OF_STATIC = 0.70
LOITER_POWER_FRACTION_OF_CRUISE = 1.20

# ILLUSTRATIVE reserve / usable-energy baseline (Section 9 of the brief).
DEFAULT_RESERVE_FRACTION = 0.20
RESERVE_FRACTION_SENSITIVITY: tuple[float, ...] = (0.10, 0.20, 0.30)

DEFAULT_USABLE_FRACTION = 0.80
USABLE_FRACTION_SENSITIVITY: tuple[float, ...] = (0.70, 0.80, 0.90)

DEFAULT_CAPACITY_CANDIDATES_AH: tuple[float, ...] = (
    4.0,
    8.0,
    12.0,
    16.0,
    20.0,
    24.0,
    28.0,
    32.0,
)

DEFAULT_VOLTAGE_CANDIDATES_SERIES: tuple[int, ...] = (12, 14, 16)

# ILLUSTRATIVE specific-energy sensitivity, bracketing the pack-level value
# reported for NASA X-57 Maxwell (~149 Wh/kg) -- see DESIGN.md Section 19.
DEFAULT_SPECIFIC_ENERGY_WH_PER_KG = 200.0
SPECIFIC_ENERGY_SENSITIVITY_WH_PER_KG: tuple[float, ...] = (150.0, 200.0, 250.0)


def default_mission_profile(
    static_battery_power_per_fan_W: float,
    cruise_battery_power_per_fan_W: float,
    n_fans: int,
) -> MissionProfile:
    """Predeclared, generic, illustrative 4-segment mission profile.

    Every segment power is an inherited Milestone 3 static/cruise
    per-fan battery power, optionally scaled by an explicit illustrative
    multiplier. Reserve is handled separately as an energy margin, not as
    a fake flight segment (Section 6 of the Milestone 4 brief).
    """
    segments = (
        MissionSegment(
            name="launch",
            duration_s=LAUNCH_DURATION_S,
            power_per_fan_W=static_battery_power_per_fan_W,
            n_fans=n_fans,
            power_multiplier=1.0,
            label="M3 static battery power, unmodified",
        ),
        MissionSegment(
            name="climb",
            duration_s=CLIMB_DURATION_S,
            power_per_fan_W=static_battery_power_per_fan_W,
            n_fans=n_fans,
            power_multiplier=CLIMB_POWER_FRACTION_OF_STATIC,
            label="illustrative fraction of M3 static battery power",
        ),
        MissionSegment(
            name="cruise",
            duration_s=CRUISE_DURATION_S,
            power_per_fan_W=cruise_battery_power_per_fan_W,
            n_fans=n_fans,
            power_multiplier=1.0,
            label="M3 cruise battery power, unmodified",
        ),
        MissionSegment(
            name="loiter",
            duration_s=LOITER_DURATION_S,
            power_per_fan_W=cruise_battery_power_per_fan_W,
            n_fans=n_fans,
            power_multiplier=LOITER_POWER_FRACTION_OF_CRUISE,
            label="illustrative fraction of M3 cruise battery power",
        ),
    )
    return MissionProfile(segments=segments)


# ---------------------------------------------------------------------------
# Battery energy requirement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatteryEnergyRequirement:
    mission_energy_Wh: float
    reserve_fraction: float
    reserve_adjusted_Wh: float
    usable_fraction: float
    required_nominal_Wh: float


def compute_energy_requirement(
    profile: MissionProfile,
    reserve_fraction: float = DEFAULT_RESERVE_FRACTION,
    usable_fraction: float = DEFAULT_USABLE_FRACTION,
) -> BatteryEnergyRequirement:
    """DERIVED chain: mission Wh -> reserve-adjusted Wh -> required nominal Wh."""
    mission_wh = mission_energy_Wh(profile)
    reserve_wh = reserve_adjusted_energy_Wh(mission_wh, reserve_fraction)
    nominal_required_wh = required_nominal_energy_Wh(reserve_wh, usable_fraction)
    return BatteryEnergyRequirement(
        mission_energy_Wh=mission_wh,
        reserve_fraction=reserve_fraction,
        reserve_adjusted_Wh=reserve_wh,
        usable_fraction=usable_fraction,
        required_nominal_Wh=nominal_required_wh,
    )


# ---------------------------------------------------------------------------
# Battery capacity candidate evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatteryCapacityResult:
    n_series: int
    v_pack_nom_V: float
    capacity_Ah: float
    nominal_Wh: float
    usable_Wh: float
    required_Ah: float
    capacity_margin: RatingMargin
    static_current_A: float
    static_c_rate: float
    current_margin: RatingMargin
    current_ok: bool
    energy_ok: bool

    @property
    def overall_ok(self) -> bool:
        return self.current_ok and self.energy_ok


def evaluate_capacity_candidate(
    n_series: int,
    capacity_Ah: float,
    static_row: RotationalOperatingRow,
    motor: MotorAssumptions,
    esc: ESCModel,
    energy_requirement: BatteryEnergyRequirement,
    c_rate_limit: float = DEFAULT_C_RATE_LIMIT,
) -> BatteryCapacityResult:
    """Evaluate one (voltage, capacity) candidate against BOTH the
    Milestone 3 per-fan current/C-rate screen (frozen convention) and the
    Milestone 4 whole-aircraft mission-energy requirement."""
    pack = make_pack(n_series, capacity_Ah=capacity_Ah, c_rate_limit=c_rate_limit)
    pt = build_electrical_operating_point(static_row, motor, esc, pack)

    nominal_wh = pack.energy_Wh_nom
    usable_wh = usable_energy_Wh(nominal_wh, energy_requirement.usable_fraction)
    required_ah = required_capacity_Ah(energy_requirement.required_nominal_Wh, pack.v_pack_nom_V)
    capacity_margin = RatingMargin(
        name="pack capacity [Ah]",
        rated_value=capacity_Ah,
        required_value=required_ah,
        margin=float(rating_margin(capacity_Ah, required_ah)),
        ok=capacity_Ah >= required_ah,
    )
    energy_ok = usable_wh >= energy_requirement.reserve_adjusted_Wh

    return BatteryCapacityResult(
        n_series=n_series,
        v_pack_nom_V=pack.v_pack_nom_V,
        capacity_Ah=capacity_Ah,
        nominal_Wh=nominal_wh,
        usable_Wh=usable_wh,
        required_Ah=required_ah,
        capacity_margin=capacity_margin,
        static_current_A=pt.battery_current_A,
        static_c_rate=pt.c_rate_required,
        current_margin=pt.battery_current_margin,
        current_ok=pt.battery_current_margin.ok,
        energy_ok=energy_ok,
    )


CAPACITY_SELECTION_RULE_DESCRIPTION = (
    "At the carried-forward pack voltage, select the smallest candidate capacity "
    "(from the predeclared sweep) that satisfies BOTH: (1) the Milestone 3 "
    "per-fan battery continuous-current / C-rate screen (frozen convention), "
    "AND (2) the Milestone 4 whole-aircraft mission-energy requirement "
    "(usable energy at least equal to the reserve-adjusted mission energy). "
    "If no candidate qualifies, report failure honestly rather than forcing "
    "a selection."
)


@dataclass(frozen=True)
class CapacitySelectionOutcome:
    n_series: int
    selected: BatteryCapacityResult | None
    rule_description: str
    all_candidates: list[BatteryCapacityResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.selected is not None


def select_capacity_for_voltage(
    n_series: int,
    capacities_Ah: tuple[float, ...],
    static_row: RotationalOperatingRow,
    motor: MotorAssumptions,
    esc: ESCModel,
    energy_requirement: BatteryEnergyRequirement,
) -> CapacitySelectionOutcome:
    """Apply the predeclared capacity-selection rule at one pack voltage.

    `capacities_Ah` is assumed sorted ascending; the first candidate
    satisfying both current and energy gates is selected.
    """
    candidates = [
        evaluate_capacity_candidate(n_series, cap, static_row, motor, esc, energy_requirement)
        for cap in capacities_Ah
    ]
    for c in candidates:
        if c.overall_ok:
            return CapacitySelectionOutcome(
                n_series=n_series,
                selected=c,
                rule_description=CAPACITY_SELECTION_RULE_DESCRIPTION,
                all_candidates=candidates,
            )
    return CapacitySelectionOutcome(
        n_series=n_series,
        selected=None,
        rule_description=CAPACITY_SELECTION_RULE_DESCRIPTION,
        all_candidates=candidates,
    )


VOLTAGE_CARRY_FORWARD_RULE_DESCRIPTION = (
    "Carry forward the Milestone 3 lowest-voltage selection rule: among "
    "pack voltages whose smallest feasible capacity yields the lowest "
    "required nominal energy (equivalently, the lowest conceptual battery "
    "mass at a fixed specific energy), select the lowest-voltage candidate. "
    "Since required nominal Wh is voltage-invariant in this model (only "
    "required Ah scales with voltage), ties on nominal energy are broken "
    "in favor of the lowest voltage, consistent with Milestone 3's own rule."
)


@dataclass(frozen=True)
class VoltageCarryForwardOutcome:
    outcomes_by_voltage: dict[int, CapacitySelectionOutcome]
    selected_n_series: int | None
    matches_m3_selection: bool
    rule_description: str


def evaluate_voltage_carry_forward(
    voltages_series: tuple[int, ...],
    capacities_Ah: tuple[float, ...],
    static_row: RotationalOperatingRow,
    motor: MotorAssumptions,
    esc: ESCModel,
    energy_requirement: BatteryEnergyRequirement,
    m3_selected_n_series: int,
) -> VoltageCarryForwardOutcome:
    """Evaluate the capacity-selection rule at every candidate voltage and
    apply the predeclared voltage carry-forward rule."""
    outcomes: dict[int, CapacitySelectionOutcome] = {}
    for n_series in voltages_series:
        outcomes[n_series] = select_capacity_for_voltage(
            n_series, capacities_Ah, static_row, motor, esc, energy_requirement
        )

    feasible = {n: o for n, o in outcomes.items() if o.success}
    if not feasible:
        return VoltageCarryForwardOutcome(
            outcomes_by_voltage=outcomes,
            selected_n_series=None,
            matches_m3_selection=False,
            rule_description=VOLTAGE_CARRY_FORWARD_RULE_DESCRIPTION,
        )

    min_wh = min(o.selected.nominal_Wh for o in feasible.values())
    tied = [n for n, o in feasible.items() if abs(o.selected.nominal_Wh - min_wh) < 1e-6]
    selected_n_series = min(tied)

    return VoltageCarryForwardOutcome(
        outcomes_by_voltage=outcomes,
        selected_n_series=selected_n_series,
        matches_m3_selection=selected_n_series == m3_selected_n_series,
        rule_description=VOLTAGE_CARRY_FORWARD_RULE_DESCRIPTION,
    )


# ---------------------------------------------------------------------------
# Convenience: build the M3-inherited reference rows/points used above
# ---------------------------------------------------------------------------


def m3_reference_battery_powers(
    requirement: UAVRequirement,
    diameter_m: float,
    m1_assumption: NonIdealAssumption,
    c_t: float,
    motor: MotorAssumptions | None = None,
    esc: ESCModel | None = None,
) -> tuple[float, float, RotationalOperatingRow, RotationalOperatingRow]:
    """Return (static_battery_power_per_fan_W, cruise_battery_power_per_fan_W,
    static_row, cruise_row) at the M2 reference rotational case, using the
    M3 default motor/ESC assumptions unless overridden."""
    motor = motor if motor is not None else default_motor_assumptions()
    esc = esc if esc is not None else default_esc_model()
    rows = reference_rotational_rows(requirement, diameter_m, m1_assumption, c_t=c_t)
    static_row = rows["static"]
    cruise_row = rows["cruise"]
    pack_dummy = make_pack(14)  # voltage cancels out of *_power_W; used only to run the chain
    pt_static = build_electrical_operating_point(static_row, motor, esc, pack_dummy)
    pt_cruise = build_electrical_operating_point(cruise_row, motor, esc, pack_dummy)
    return pt_static.battery_power_W, pt_cruise.battery_power_W, static_row, cruise_row
