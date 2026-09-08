"""Milestone 5 -- combine the thrust-effectiveness and thrust-lapse models
with the frozen Milestone 1-4 architecture into thrust margins, an RPM
recovery analysis, its electrical consequence, and its mission-energy
consequence.

Purely additive: imports and reuses Milestone 1-4
(`edf_sizing.requirements`, `edf_sizing.rotational_study`,
`edf_sizing.compressibility`, `edf_sizing.rotational`,
`edf_sizing.electrical_sizing`, `edf_sizing.motor`, `edf_sizing.electrical`,
`edf_sizing.battery`, `edf_sizing.mission`, `edf_sizing.energy`,
`edf_sizing.mission_sizing`) without modifying any of them, and combines
them with the new Milestone 5 modules (`edf_sizing.duct_losses`,
`edf_sizing.thrust_lapse`).

Historical Milestone 1 required thrust values (`static_thrust_per_fan_N`,
`cruise_thrust_per_fan_N`) remain REQUIREMENTS throughout -- this module
computes AVAILABLE thrust and never rewrites them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from edf_sizing import compressibility as comp
from edf_sizing import rotational as rot
from edf_sizing.battery import BatteryPack
from edf_sizing.duct_losses import ThrustEffectivenessModel, static_available_thrust_N
from edf_sizing.electrical import ESCModel, battery_input_power, current_from_power, rating_margin
from edf_sizing.electrical_sizing import RatingMargin
from edf_sizing.energy import mission_energy_Wh, reserve_adjusted_energy_Wh, usable_energy_Wh
from edf_sizing.mission import MissionProfile, MissionSegment
from edf_sizing.motor import MotorAssumptions, motor_electrical_power, shaft_torque
from edf_sizing.requirements import UAVRequirement
from edf_sizing.rotational_study import DEFAULT_AMBIENT
from edf_sizing.thrust_lapse import ThrustLapseModel, available_thrust_N

# ---------------------------------------------------------------------------
# Predeclared Milestone 5 baseline case and sensitivity sets
# ---------------------------------------------------------------------------

DEFAULT_ETA_T = 0.90
ETA_T_SENSITIVITY: tuple[float, ...] = (0.80, 0.90, 1.00)
# Supplementary stress case (not part of the primary declared sensitivity
# set) used only to demonstrate the RPM-recovery infeasibility boundary --
# see DESIGN.md Milestone 5 Section on RPM recovery.
STRESS_ETA_T = 0.65

# ILLUSTRATIVE baseline lapse model: linear, k=0.30, referenced to twice
# the M1 cruise speed (60 m/s) -- see DESIGN.md for rationale. A quadratic
# form with the same coefficient is the declared alternative sensitivity.
DEFAULT_LAPSE_V_REF_M_S = 60.0
DEFAULT_LAPSE_K = 0.30
DEFAULT_LAPSE_MODEL = ThrustLapseModel(
    kind="linear", k=DEFAULT_LAPSE_K, v_ref_m_s=DEFAULT_LAPSE_V_REF_M_S
)
ALTERNATIVE_LAPSE_MODEL = ThrustLapseModel(
    kind="quadratic", k=DEFAULT_LAPSE_K, v_ref_m_s=DEFAULT_LAPSE_V_REF_M_S
)


def default_effectiveness_model(eta_T: float = DEFAULT_ETA_T) -> ThrustEffectivenessModel:
    return ThrustEffectivenessModel(eta_T=eta_T)


# ---------------------------------------------------------------------------
# Thrust margin
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThrustMarginResult:
    operating_point: str
    v_inf_m_s: float
    thrust_required_N: float
    thrust_available_N: float
    margin_N: float
    margin_fraction: float
    passes: bool


def evaluate_thrust_margin(
    operating_point: str, v_inf_m_s: float, thrust_required_N: float, thrust_available_N: float
) -> ThrustMarginResult:
    """DERIVED: margin_N = T_available - T_required;
    margin_fraction = T_available/T_required - 1 (T_required > 0 required).
    Never clipped -- a negative margin is reported honestly."""
    if thrust_required_N <= 0:
        raise ValueError(f"thrust_required_N must be > 0; got {thrust_required_N!r}")
    if thrust_available_N < 0:
        raise ValueError(f"thrust_available_N must be >= 0; got {thrust_available_N!r}")
    margin_n = thrust_available_N - thrust_required_N
    margin_fraction = float(rating_margin(thrust_available_N, thrust_required_N))
    return ThrustMarginResult(
        operating_point=operating_point,
        v_inf_m_s=v_inf_m_s,
        thrust_required_N=thrust_required_N,
        thrust_available_N=thrust_available_N,
        margin_N=margin_n,
        margin_fraction=margin_fraction,
        passes=margin_n >= 0.0,
    )


# ---------------------------------------------------------------------------
# RPM recovery (DERIVED, within the frozen M2 C_T convention: T ~ RPM^2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RpmRecoveryResult:
    rpm_reference: float
    eta_T: float
    rpm_required: float
    rpm_ceiling: float
    tip_mach_at_recovery: float
    feasible: bool
    power_ratio: float  # (rpm_required / rpm_reference)^3, DERIVED from C_P ~ RPM^3


def compute_rpm_recovery(
    rpm_reference: float,
    diameter_m: float,
    eta_T: float,
    m_tip_max: float,
    ambient: comp.AmbientCondition = DEFAULT_AMBIENT,
) -> RpmRecoveryResult:
    """DERIVED RPM required to restore the reference (eta_T=1) thrust,
    within the frozen Milestone 2 fixed-C_T convention T ~ n^2:

        RPM_required = RPM_reference / sqrt(eta_T)

    Compared against the Milestone 2 tip-Mach RPM ceiling
    (`compressibility.max_rpm_static`, unchanged). The corresponding
    power penalty follows the frozen Milestone 2 fixed-C_P convention
    P ~ n^3:

        power_ratio = (RPM_required / RPM_reference)^3
    """
    if rpm_reference <= 0:
        raise ValueError(f"rpm_reference must be > 0; got {rpm_reference!r}")
    if not (0.0 < eta_T <= 1.0):
        raise ValueError(f"eta_T must be in (0, 1]; got {eta_T!r}")

    rpm_required = rpm_reference / math.sqrt(eta_T)
    rpm_ceiling = comp.max_rpm_static(diameter_m, m_tip_max, ambient)
    u_tip = float(rot.tip_speed(diameter_m, rpm_required))
    a_sound = comp.speed_of_sound(ambient)
    tip_mach = float(comp.static_tip_mach(u_tip, a_sound))
    power_ratio = (rpm_required / rpm_reference) ** 3

    return RpmRecoveryResult(
        rpm_reference=rpm_reference,
        eta_T=eta_T,
        rpm_required=rpm_required,
        rpm_ceiling=rpm_ceiling,
        tip_mach_at_recovery=tip_mach,
        feasible=rpm_required <= rpm_ceiling,
        power_ratio=power_ratio,
    )


# ---------------------------------------------------------------------------
# Electrical consequence of RPM recovery (reuses M3 primitives directly)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveredElectricalResult:
    shaft_power_reference_W: float
    shaft_power_recovered_W: float
    motor_electrical_power_W: float
    battery_power_W: float
    battery_current_A: float
    c_rate_required: float
    esc_current_margin: RatingMargin
    battery_current_margin: RatingMargin

    @property
    def current_ok(self) -> bool:
        return self.esc_current_margin.ok and self.battery_current_margin.ok


def compute_recovered_electrical(
    shaft_power_reference_W: float,
    power_ratio: float,
    motor: MotorAssumptions,
    esc: ESCModel,
    pack: BatteryPack,
) -> RecoveredElectricalResult:
    """Propagate an M5 recovered shaft power through the frozen M3 chain:

        P_motor_elec = P_shaft / eta_motor
        P_battery    = P_motor_elec / eta_ESC
        I_battery    = P_battery / V_pack

    using `edf_sizing.motor`/`edf_sizing.electrical` primitives directly
    (never re-deriving M3's equations).
    """
    if shaft_power_reference_W < 0:
        raise ValueError(
            f"shaft_power_reference_W must be >= 0; got {shaft_power_reference_W!r}"
        )
    if power_ratio < 0:
        raise ValueError(f"power_ratio must be >= 0; got {power_ratio!r}")

    p_shaft_recovered = shaft_power_reference_W * power_ratio
    p_motor = float(motor_electrical_power(p_shaft_recovered, motor))
    p_batt = float(battery_input_power(p_motor, esc))
    i_batt = float(current_from_power(p_batt, pack.v_pack_nom_V))
    c_rate_req = float(pack.c_rate_required(i_batt))

    esc_margin = RatingMargin(
        name="ESC continuous current [A]",
        rated_value=esc.i_esc_max_A,
        required_value=i_batt,
        margin=float(rating_margin(esc.i_esc_max_A, i_batt)),
        ok=esc.i_esc_max_A >= i_batt,
    )
    batt_margin = RatingMargin(
        name="battery continuous current [A]",
        rated_value=pack.i_continuous_max_A,
        required_value=i_batt,
        margin=float(rating_margin(pack.i_continuous_max_A, i_batt)),
        ok=pack.i_continuous_max_A >= i_batt,
    )

    return RecoveredElectricalResult(
        shaft_power_reference_W=shaft_power_reference_W,
        shaft_power_recovered_W=p_shaft_recovered,
        motor_electrical_power_W=p_motor,
        battery_power_W=p_batt,
        battery_current_A=i_batt,
        c_rate_required=c_rate_req,
        esc_current_margin=esc_margin,
        battery_current_margin=batt_margin,
    )


def shaft_torque_at_recovery(shaft_power_recovered_W: float, rpm_recovered: float) -> float:
    """Convenience re-export of the frozen M3 torque relation at the
    recovered operating point: Q = P_shaft / omega."""
    return float(shaft_torque(shaft_power_recovered_W, rpm_recovered))


# ---------------------------------------------------------------------------
# Mission-energy consequence (new M5 off-design profile; M4 baseline
# untouched)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionEnergyPenaltyResult:
    mission_energy_m4_baseline_Wh: float
    mission_energy_m5_Wh: float
    delta_Wh: float
    reserve_adjusted_m5_Wh: float
    required_nominal_m5_Wh: float
    pack_nominal_Wh: float
    pack_usable_Wh: float
    capacity_margin: RatingMargin


def build_m5_mission_profile(
    static_battery_power_recovered_per_fan_W: float,
    cruise_battery_power_per_fan_W: float,
    n_fans: int,
    climb_power_fraction_of_static: float,
    loiter_power_fraction_of_cruise: float,
    launch_duration_s: float,
    climb_duration_s: float,
    cruise_duration_s: float,
    loiter_duration_s: float,
) -> MissionProfile:
    """M5 off-design mission profile: static/climb segments use the
    RPM-recovered battery power; cruise/loiter are unaffected (cruise
    passes the thrust-lapse screen without needing recovery at the
    baseline eta_T). Uses the same M4 segment structure and duration
    convention -- never overwrites the M4 baseline profile."""
    return MissionProfile(
        segments=(
            MissionSegment(
                "launch",
                launch_duration_s,
                static_battery_power_recovered_per_fan_W,
                n_fans,
                1.0,
                "M5 RPM-recovered static battery power",
            ),
            MissionSegment(
                "climb",
                climb_duration_s,
                static_battery_power_recovered_per_fan_W,
                n_fans,
                climb_power_fraction_of_static,
                "illustrative fraction of M5 recovered static battery power",
            ),
            MissionSegment(
                "cruise",
                cruise_duration_s,
                cruise_battery_power_per_fan_W,
                n_fans,
                1.0,
                "M4/M3 cruise battery power, unmodified (lapse screen passes)",
            ),
            MissionSegment(
                "loiter",
                loiter_duration_s,
                cruise_battery_power_per_fan_W,
                n_fans,
                loiter_power_fraction_of_cruise,
                "illustrative fraction of M4/M3 cruise battery power",
            ),
        )
    )


def evaluate_mission_energy_penalty(
    m4_baseline_profile: MissionProfile,
    m5_profile: MissionProfile,
    reserve_fraction: float,
    usable_fraction: float,
    pack: BatteryPack,
) -> MissionEnergyPenaltyResult:
    e_m4 = mission_energy_Wh(m4_baseline_profile)
    e_m5 = mission_energy_Wh(m5_profile)
    reserve_wh = reserve_adjusted_energy_Wh(e_m5, reserve_fraction)
    required_nominal_wh = reserve_wh / usable_fraction
    nominal_wh = pack.energy_Wh_nom
    usable_wh = usable_energy_Wh(nominal_wh, usable_fraction)

    capacity_margin = RatingMargin(
        name="battery usable energy [Wh]",
        rated_value=usable_wh,
        required_value=reserve_wh,
        margin=float(rating_margin(usable_wh, reserve_wh)),
        ok=usable_wh >= reserve_wh,
    )

    return MissionEnergyPenaltyResult(
        mission_energy_m4_baseline_Wh=e_m4,
        mission_energy_m5_Wh=e_m5,
        delta_Wh=e_m5 - e_m4,
        reserve_adjusted_m5_Wh=reserve_wh,
        required_nominal_m5_Wh=required_nominal_wh,
        pack_nominal_Wh=nominal_wh,
        pack_usable_Wh=usable_wh,
        capacity_margin=capacity_margin,
    )


# ---------------------------------------------------------------------------
# Predeclared Milestone 5 feasibility rule
# ---------------------------------------------------------------------------

FEASIBILITY_RULE_DESCRIPTION = (
    "An M5 operating case is feasible only if ALL of: (1) static required "
    "thrust is met (after eta_T and RPM recovery); (2) cruise required "
    "thrust is met (after eta_T and thrust lapse); (3) the RPM required for "
    "thrust recovery does not exceed the M2 tip-Mach RPM ceiling; (4) the "
    "M3 ESC and battery continuous-current margins at the recovered power "
    "are both >= 0; (5) the M4 selected battery capacity's usable-energy "
    "margin for the updated (M5) mission is >= 0. Any failing criterion is "
    "reported explicitly, never dropped."
)


@dataclass(frozen=True)
class PerformanceEnvelopeResult:
    """`static_margin` is the BASELINE (pre-recovery, reference-RPM) static
    thrust margin -- reported honestly per Section 11 of the Milestone 5
    brief, and MAY be negative even when the overall case is feasible,
    because static thrust feasibility criterion (1) of the predeclared
    rule is satisfied via RPM recovery (`rpm_recovery.feasible`), not by
    the unmodified baseline margin. `static_thrust_met_via_recovery` makes
    this explicit."""

    eta_T: float
    static_margin: ThrustMarginResult
    cruise_margin: ThrustMarginResult
    rpm_recovery: RpmRecoveryResult
    recovered_electrical: RecoveredElectricalResult
    mission_energy_penalty: MissionEnergyPenaltyResult
    rule_description: str

    @property
    def static_thrust_met_via_recovery(self) -> bool:
        """Criterion (1) of the predeclared rule: static thrust is met
        after RPM recovery. By construction, recovering to `rpm_required`
        restores available static thrust to exactly the requirement
        whenever that RPM is within the M2 tip-Mach ceiling."""
        return self.rpm_recovery.feasible

    @property
    def feasible(self) -> bool:
        return (
            self.static_thrust_met_via_recovery
            and self.cruise_margin.passes
            and self.recovered_electrical.current_ok
            and self.mission_energy_penalty.capacity_margin.ok
        )


def evaluate_performance_envelope(
    requirement: UAVRequirement,
    diameter_m: float,
    static_thrust_ideal_reference_N: float,
    v_cruise_m_s: float,
    static_shaft_power_reference_W: float,
    cruise_battery_power_per_fan_W: float,
    rpm_reference: float,
    m_tip_max: float,
    eta_T: float,
    lapse_model: ThrustLapseModel,
    motor: MotorAssumptions,
    esc: ESCModel,
    pack: BatteryPack,
    m4_baseline_profile: MissionProfile,
    reserve_fraction: float,
    usable_fraction: float,
    climb_power_fraction_of_static: float,
    loiter_power_fraction_of_cruise: float,
    launch_duration_s: float,
    climb_duration_s: float,
    cruise_duration_s: float,
    loiter_duration_s: float,
    ambient: comp.AmbientCondition = DEFAULT_AMBIENT,
) -> PerformanceEnvelopeResult:
    """Evaluate one complete Milestone 5 performance-envelope case: static
    and cruise thrust margins (baseline, pre-recovery), RPM recovery
    against the M2 tip-Mach ceiling, its M3 electrical consequence, and its
    M4-style mission-energy consequence -- combined per the predeclared
    feasibility rule (`FEASIBILITY_RULE_DESCRIPTION`)."""
    model = default_effectiveness_model(eta_T)

    static_available = float(static_available_thrust_N(static_thrust_ideal_reference_N, model))
    static_margin = evaluate_thrust_margin(
        "static", 0.0, requirement.static_thrust_per_fan_N, static_available
    )

    # Per the Milestone 5 brief (Section 7): T_available(V) = T_static_available
    # * f_lapse(V) -- the SAME static-available thrust is lapsed with speed;
    # M1's cruise "ideal" thrust is a REQUIRED value only, never re-scaled here.
    cruise_available = float(available_thrust_N(static_available, v_cruise_m_s, lapse_model))
    cruise_margin = evaluate_thrust_margin(
        "cruise", v_cruise_m_s, requirement.cruise_thrust_per_fan_N, cruise_available
    )

    rpm_recovery = compute_rpm_recovery(rpm_reference, diameter_m, eta_T, m_tip_max, ambient)
    recovered_electrical = compute_recovered_electrical(
        static_shaft_power_reference_W, rpm_recovery.power_ratio, motor, esc, pack
    )

    m5_profile = build_m5_mission_profile(
        recovered_electrical.battery_power_W,
        cruise_battery_power_per_fan_W,
        requirement.n_fans,
        climb_power_fraction_of_static,
        loiter_power_fraction_of_cruise,
        launch_duration_s,
        climb_duration_s,
        cruise_duration_s,
        loiter_duration_s,
    )
    mission_energy_penalty = evaluate_mission_energy_penalty(
        m4_baseline_profile, m5_profile, reserve_fraction, usable_fraction, pack
    )

    return PerformanceEnvelopeResult(
        eta_T=eta_T,
        static_margin=static_margin,
        cruise_margin=cruise_margin,
        rpm_recovery=rpm_recovery,
        recovered_electrical=recovered_electrical,
        mission_energy_penalty=mission_energy_penalty,
        rule_description=FEASIBILITY_RULE_DESCRIPTION,
    )
