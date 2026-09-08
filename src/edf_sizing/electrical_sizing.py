"""Milestone 3 -- combine the Milestone 1/2 aerodynamic/rotational results
with the motor/ESC/battery electrical models into operating points, a
predeclared battery-pack selection rule, and sensitivity studies.

Purely additive: imports and reuses Milestone 1
(`edf_sizing.actuator_disk`, `edf_sizing.efficiency`, `edf_sizing.sizing`)
and Milestone 2 (`edf_sizing.rotational`, `edf_sizing.compressibility`,
`edf_sizing.fan_loading`, `edf_sizing.rotational_study`) without modifying
any of them, and combines them with the new Milestone 3 modules
(`edf_sizing.motor`, `edf_sizing.electrical`, `edf_sizing.battery`).

Electrical power chain (Section 3 of the Milestone 3 brief -- no
double-counting of the Milestone 1 `eta_overall`):

    M1 ideal actuator-disk power (Pi)
      -> M1 estimated shaft power (P_shaft_est = Pi / eta_overall)   [inherited, unchanged]
      -> motor electrical input   (P_motor_elec = P_shaft_est / eta_motor)   [NEW]
      -> battery input power      (P_battery = P_motor_elec / eta_ESC)      [NEW]
      -> battery current          (I_battery = P_battery / V_pack)          [NEW]
"""

from __future__ import annotations

from dataclasses import dataclass, field

from edf_sizing.battery import BatteryPack
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel, battery_input_power, current_from_power, rating_margin
from edf_sizing.motor import MotorAssumptions, motor_electrical_power, shaft_torque
from edf_sizing.requirements import UAVRequirement
from edf_sizing.rotational_study import (
    DEFAULT_AMBIENT,
    RotationalOperatingRow,
    build_rotational_operating_table,
)

# ---------------------------------------------------------------------------
# Milestone 3 assumptions (explicit, illustrative unless noted otherwise)
# ---------------------------------------------------------------------------

# Predeclared M2 reference rotational case (Section 11 of the brief): the
# middle C_T sensitivity case, which passes the M2 tip-Mach screen.
REFERENCE_C_T = 0.08
SENSITIVITY_C_T_CASES: tuple[float, ...] = (0.08, 0.12)
HISTORICAL_INFEASIBLE_C_T = 0.05  # retained, not erased -- fails M2 tip-Mach at D=0.50 m

# ILLUSTRATIVE motor/ESC/battery assumptions -- see DESIGN.md Milestone 3.
DEFAULT_ETA_MOTOR = 0.90
ETA_MOTOR_SENSITIVITY: tuple[float, ...] = (0.85, 0.90, 0.95)

DEFAULT_ETA_ESC = 0.97
ETA_ESC_SENSITIVITY: tuple[float, ...] = (0.95, 0.97, 0.99)

DEFAULT_MOTOR_RATED_ELECTRICAL_POWER_W = 4500.0  # illustrative continuous rating

DEFAULT_ESC_I_MAX_A = 100.0
ESC_I_MAX_SENSITIVITY_A: tuple[float, ...] = (80.0, 100.0, 120.0)

DEFAULT_CAPACITY_AH = 4.0
CAPACITY_SENSITIVITY_AH: tuple[float, ...] = (4.0, 6.0, 8.0)

DEFAULT_C_RATE_LIMIT = 20.0  # illustrative continuous discharge C-rate

DEFAULT_PACK_SERIES_CANDIDATES: tuple[int, ...] = (12, 14, 16)


def default_motor_assumptions(eta_motor: float = DEFAULT_ETA_MOTOR) -> MotorAssumptions:
    return MotorAssumptions(
        eta_motor=eta_motor, rated_electrical_power_W=DEFAULT_MOTOR_RATED_ELECTRICAL_POWER_W
    )


def default_esc_model(
    eta_esc: float = DEFAULT_ETA_ESC, i_esc_max_A: float = DEFAULT_ESC_I_MAX_A
) -> ESCModel:
    return ESCModel(eta_esc=eta_esc, i_esc_max_A=i_esc_max_A)


def make_pack(
    n_series: int,
    capacity_Ah: float = DEFAULT_CAPACITY_AH,
    c_rate_limit: float = DEFAULT_C_RATE_LIMIT,
) -> BatteryPack:
    return BatteryPack(
        n_series=n_series, capacity_Ah=capacity_Ah, continuous_c_rate_limit=c_rate_limit
    )


def reference_rotational_rows(
    requirement: UAVRequirement,
    diameter_m: float,
    m1_assumption: NonIdealAssumption,
    c_t: float = REFERENCE_C_T,
) -> dict[str, RotationalOperatingRow]:
    """Static + cruise rotational operating rows at one C_T case, reusing
    the Milestone 2 `build_rotational_operating_table`."""
    rows = build_rotational_operating_table(
        requirement, diameter_m, m1_assumption, DEFAULT_AMBIENT, c_t_cases=(c_t,)
    )
    return {r.operating_point: r for r in rows}


# ---------------------------------------------------------------------------
# Electrical operating point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RatingMargin:
    name: str
    rated_value: float
    required_value: float
    margin: float
    ok: bool


def _margin(name: str, rated_value: float, required_value: float) -> RatingMargin:
    m = float(rating_margin(rated_value, required_value))
    return RatingMargin(
        name=name, rated_value=rated_value, required_value=required_value, margin=m, ok=m >= 0.0
    )


@dataclass(frozen=True)
class ElectricalOperatingPoint:
    operating_point: str
    c_t: float
    v_inf_m_s: float
    thrust_N: float
    rpm: float
    tip_mach: float
    tip_mach_ok: bool
    shaft_power_W: float
    shaft_torque_Nm: float
    motor_electrical_power_W: float
    battery_power_W: float
    pack_n_series: int
    pack_v_nom_V: float
    pack_v_full_V: float
    battery_current_A: float
    c_rate_required: float
    esc_current_margin: RatingMargin
    battery_current_margin: RatingMargin
    c_rate_margin: RatingMargin
    motor_power_margin: RatingMargin | None

    @property
    def all_gates_ok(self) -> bool:
        margins = [self.esc_current_margin, self.battery_current_margin, self.c_rate_margin]
        if self.motor_power_margin is not None:
            margins.append(self.motor_power_margin)
        return self.tip_mach_ok and all(m.ok for m in margins)


def build_electrical_operating_point(
    row: RotationalOperatingRow,
    motor: MotorAssumptions,
    esc: ESCModel,
    pack: BatteryPack,
) -> ElectricalOperatingPoint:
    """Combine one Milestone 2 rotational operating row with the motor/ESC/
    battery models into a full electrical operating point."""
    q_shaft = float(shaft_torque(row.p_shaft_est_W, row.rpm))
    p_motor = float(motor_electrical_power(row.p_shaft_est_W, motor))
    p_batt = float(battery_input_power(p_motor, esc))
    i_batt = float(current_from_power(p_batt, pack.v_pack_nom_V))
    c_rate_req = float(pack.c_rate_required(i_batt))

    esc_margin = _margin("ESC continuous current [A]", esc.i_esc_max_A, i_batt)
    batt_margin = _margin("battery continuous current [A]", pack.i_continuous_max_A, i_batt)
    crate_margin = _margin("battery continuous C-rate", pack.continuous_c_rate_limit, c_rate_req)
    motor_margin = (
        _margin("motor rated electrical power [W]", motor.rated_electrical_power_W, p_motor)
        if motor.rated_electrical_power_W is not None
        else None
    )

    return ElectricalOperatingPoint(
        operating_point=row.operating_point,
        c_t=row.c_t,
        v_inf_m_s=row.v_inf_m_s,
        thrust_N=row.thrust_N,
        rpm=row.rpm,
        tip_mach=row.tip_mach,
        tip_mach_ok=row.tip_mach_ok,
        shaft_power_W=row.p_shaft_est_W,
        shaft_torque_Nm=q_shaft,
        motor_electrical_power_W=p_motor,
        battery_power_W=p_batt,
        pack_n_series=pack.n_series,
        pack_v_nom_V=pack.v_pack_nom_V,
        pack_v_full_V=pack.v_pack_full_V,
        battery_current_A=i_batt,
        c_rate_required=c_rate_req,
        esc_current_margin=esc_margin,
        battery_current_margin=batt_margin,
        c_rate_margin=crate_margin,
        motor_power_margin=motor_margin,
    )


# ---------------------------------------------------------------------------
# Predeclared pack-selection rule (Section 10 of the Milestone 3 brief)
# ---------------------------------------------------------------------------

PACK_SELECTION_RULE_DESCRIPTION = (
    "Select the lowest-voltage candidate pack (from the predeclared series-"
    "count sweep) at the governing (static) operating point that: (1) uses "
    "the M2 tip-Mach-feasible reference rotational case; (2) motor rated "
    "electrical power exceeds required motor electrical power; (3) ESC "
    "continuous-current rating exceeds required battery current; (4) "
    "battery continuous-current capability exceeds required battery "
    "current; (5) required C-rate does not exceed the declared pack "
    "continuous C-rate; (6) all margins are >= 0. If no candidate "
    "qualifies, report failure honestly rather than forcing a selection."
)


@dataclass(frozen=True)
class PackSelectionOutcome:
    selected: ElectricalOperatingPoint | None
    rule_description: str
    all_points: list[ElectricalOperatingPoint] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.selected is not None


def select_pack(
    governing_row: RotationalOperatingRow,
    motor: MotorAssumptions,
    esc: ESCModel,
    candidate_packs: list[BatteryPack],
) -> PackSelectionOutcome:
    """Apply the predeclared pack-selection rule at the governing operating
    point. `candidate_packs` is assumed sorted by ascending series count
    (ascending voltage); the first qualifying candidate is selected."""
    points = [
        build_electrical_operating_point(governing_row, motor, esc, pack)
        for pack in candidate_packs
    ]
    for pt in points:
        if pt.all_gates_ok:
            return PackSelectionOutcome(
                selected=pt, rule_description=PACK_SELECTION_RULE_DESCRIPTION, all_points=points
            )
    return PackSelectionOutcome(
        selected=None, rule_description=PACK_SELECTION_RULE_DESCRIPTION, all_points=points
    )
