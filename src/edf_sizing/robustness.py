"""Milestone 6 -- robustness orchestration across the frozen Milestone 1-5
architecture.

Purely additive orchestration: every quantity here is produced by calling
existing Milestone 1-5 APIs (`edf_sizing.sizing`, `edf_sizing
.rotational_study`, `edf_sizing.electrical_sizing`, `edf_sizing
.mission_sizing`, `edf_sizing.performance_envelope`) -- no physics
equation is re-implemented in this module. Milestone 6 asks "how robust is
the already-built model across its own predeclared sensitivity ranges?",
not "what is a new physical relation?".
"""

from __future__ import annotations

from dataclasses import dataclass

from edf_sizing.battery import BatteryPack
from edf_sizing.efficiency import NonIdealAssumption
from edf_sizing.electrical import ESCModel, rating_margin
from edf_sizing.electrical_sizing import (
    DEFAULT_ESC_I_MAX_A,
    DEFAULT_ETA_ESC,
    DEFAULT_ETA_MOTOR,
    DEFAULT_MOTOR_RATED_ELECTRICAL_POWER_W,
    REFERENCE_C_T,
    reference_rotational_rows,
)
from edf_sizing.mission import MissionProfile, MissionSegment
from edf_sizing.mission_sizing import (
    CLIMB_DURATION_S,
    CLIMB_POWER_FRACTION_OF_STATIC,
    CRUISE_DURATION_S,
    DEFAULT_C_RATE_LIMIT,
    DEFAULT_RESERVE_FRACTION,
    DEFAULT_USABLE_FRACTION,
    LAUNCH_DURATION_S,
    LOITER_DURATION_S,
    LOITER_POWER_FRACTION_OF_CRUISE,
    m3_reference_battery_powers,
)
from edf_sizing.motor import MotorAssumptions
from edf_sizing.performance_envelope import (
    DEFAULT_ETA_T,
    DEFAULT_LAPSE_MODEL,
    PerformanceEnvelopeResult,
    ThrustLapseModel,
    evaluate_performance_envelope,
)
from edf_sizing.requirements import UAVRequirement, default_requirement
from edf_sizing.rotational_study import DEFAULT_AMBIENT, DEFAULT_M_TIP_MAX
from edf_sizing.sizing import SelectionLimits, evaluate_candidates

# ---------------------------------------------------------------------------
# Final inherited baseline architecture (Section 5 of the Milestone 6
# brief) -- every value here is copied verbatim from the frozen M1-M5
# defaults; none is retuned in Milestone 6.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinalArchitecture:
    diameter_m: float = 0.50
    reference_c_t: float = REFERENCE_C_T  # 0.08
    m_tip_max: float = DEFAULT_M_TIP_MAX  # 0.85
    n_series: int = 14
    capacity_Ah: float = 28.0
    eta_T: float = DEFAULT_ETA_T  # 0.90
    eta_overall: float = 0.75  # M1
    eta_motor: float = DEFAULT_ETA_MOTOR  # 0.90
    eta_esc: float = DEFAULT_ETA_ESC  # 0.97
    esc_i_max_A: float = DEFAULT_ESC_I_MAX_A  # 100.0
    c_rate_limit: float = DEFAULT_C_RATE_LIMIT  # 20.0
    reserve_fraction: float = DEFAULT_RESERVE_FRACTION  # 0.20
    usable_fraction: float = DEFAULT_USABLE_FRACTION  # 0.80
    cruise_duration_s: float = CRUISE_DURATION_S  # 1200.0
    lapse_model: ThrustLapseModel = DEFAULT_LAPSE_MODEL


BASELINE = FinalArchitecture()

M1_LIMITS = SelectionLimits(max_disk_loading_N_m2=900.0, max_static_ideal_power_W=3500.0)


def _mission_profile_for(
    p_static_per_fan_W: float,
    p_cruise_per_fan_W: float,
    n_fans: int,
    cruise_duration_s: float,
) -> MissionProfile:
    """Build the M4-style 4-segment profile with an overridable cruise
    duration -- same segment structure/fractions as
    `mission_sizing.default_mission_profile`, no new mission logic."""
    return MissionProfile(
        segments=(
            MissionSegment("launch", LAUNCH_DURATION_S, p_static_per_fan_W, n_fans, 1.0),
            MissionSegment(
                "climb",
                CLIMB_DURATION_S,
                p_static_per_fan_W,
                n_fans,
                CLIMB_POWER_FRACTION_OF_STATIC,
            ),
            MissionSegment("cruise", cruise_duration_s, p_cruise_per_fan_W, n_fans, 1.0),
            MissionSegment(
                "loiter",
                LOITER_DURATION_S,
                p_cruise_per_fan_W,
                n_fans,
                LOITER_POWER_FRACTION_OF_CRUISE,
            ),
        )
    )


# ---------------------------------------------------------------------------
# Constraint margin table (Section 6 of the Milestone 6 brief)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstraintMargin:
    name: str
    milestone: str
    value: float
    limit: float
    margin: float  # DERIVED: limit/value - 1 (or available/required - 1); positive = PASS
    status: str  # "PASS" or "FAIL"
    unit: str


def build_constraint_table(
    requirement: UAVRequirement,
    architecture: FinalArchitecture = BASELINE,
    envelope: PerformanceEnvelopeResult | None = None,
) -> list[ConstraintMargin]:
    """The 8 cross-milestone constraints (A-H), each as `rated/required - 1`
    (positive = PASS), reusing existing M1/M2/M3/M4/M5 quantities only."""
    m1_assumption = NonIdealAssumption(eta_overall=architecture.eta_overall)
    candidates = evaluate_candidates(
        requirement, m1_assumption, M1_LIMITS, diameters_m=(architecture.diameter_m,)
    )
    m1_candidate = candidates[0]

    if envelope is None:
        envelope = evaluate_baseline(requirement, architecture)

    _reference_tip_mach = _static_tip_mach(requirement, architecture, m1_assumption)

    rows = [
        ConstraintMargin(
            name="A. M1 disk loading",
            milestone="M1",
            value=m1_candidate.disk_loading_N_m2,
            limit=M1_LIMITS.max_disk_loading_N_m2,
            margin=float(
                rating_margin(M1_LIMITS.max_disk_loading_N_m2, m1_candidate.disk_loading_N_m2)
            ),
            status="PASS" if m1_candidate.meets_disk_loading_limit else "FAIL",
            unit="N/m^2",
        ),
        ConstraintMargin(
            name="B. M1 ideal power",
            milestone="M1",
            value=m1_candidate.pi_static_W,
            limit=M1_LIMITS.max_static_ideal_power_W,
            margin=float(
                rating_margin(M1_LIMITS.max_static_ideal_power_W, m1_candidate.pi_static_W)
            ),
            status="PASS" if m1_candidate.meets_power_limit else "FAIL",
            unit="W",
        ),
        ConstraintMargin(
            name="C. M2 tip Mach (reference RPM)",
            milestone="M2",
            value=_reference_tip_mach,
            limit=architecture.m_tip_max,
            margin=float(rating_margin(architecture.m_tip_max, _reference_tip_mach)),
            status="PASS" if _reference_tip_mach <= architecture.m_tip_max else "FAIL",
            unit="Mach",
        ),
        ConstraintMargin(
            name="D. M3 ESC current",
            milestone="M3",
            value=envelope.recovered_electrical.battery_current_A,
            limit=architecture.esc_i_max_A,
            margin=envelope.recovered_electrical.esc_current_margin.margin,
            status="PASS" if envelope.recovered_electrical.esc_current_margin.ok else "FAIL",
            unit="A",
        ),
        ConstraintMargin(
            name="E. M3 battery current/C-rate",
            milestone="M3",
            value=envelope.recovered_electrical.battery_current_A,
            limit=architecture.capacity_Ah * architecture.c_rate_limit,
            margin=envelope.recovered_electrical.battery_current_margin.margin,
            status="PASS" if envelope.recovered_electrical.battery_current_margin.ok else "FAIL",
            unit="A",
        ),
        ConstraintMargin(
            name="F. M4/M5 mission energy capacity",
            milestone="M4/M5",
            value=envelope.mission_energy_penalty.reserve_adjusted_m5_Wh,
            limit=envelope.mission_energy_penalty.pack_usable_Wh,
            margin=envelope.mission_energy_penalty.capacity_margin.margin,
            status="PASS" if envelope.mission_energy_penalty.capacity_margin.ok else "FAIL",
            unit="Wh",
        ),
        ConstraintMargin(
            name="G. M5 static thrust (baseline RPM, pre-recovery)",
            milestone="M5",
            value=envelope.static_margin.thrust_available_N,
            limit=envelope.static_margin.thrust_required_N,
            margin=envelope.static_margin.margin_fraction,
            status="PASS" if envelope.static_margin.passes else "FAIL",
            unit="N",
        ),
        ConstraintMargin(
            name="H. M5 cruise thrust",
            milestone="M5",
            value=envelope.cruise_margin.thrust_available_N,
            limit=envelope.cruise_margin.thrust_required_N,
            margin=envelope.cruise_margin.margin_fraction,
            status="PASS" if envelope.cruise_margin.passes else "FAIL",
            unit="N",
        ),
    ]
    return rows


def _static_tip_mach(
    requirement: UAVRequirement, architecture: FinalArchitecture, m1_assumption: NonIdealAssumption
) -> float:
    rows = reference_rotational_rows(
        requirement, architecture.diameter_m, m1_assumption, architecture.reference_c_t
    )
    return rows["static"].tip_mach


# ---------------------------------------------------------------------------
# Case evaluation and feasibility classification (Section 8)
# ---------------------------------------------------------------------------

FEASIBLE = "FEASIBLE"
FAIL_M1_LOADING = "FAIL_M1_LOADING"
FAIL_TIP_MACH = "FAIL_TIP_MACH"
FAIL_STATIC_THRUST = "FAIL_STATIC_THRUST"
FAIL_CRUISE_THRUST = "FAIL_CRUISE_THRUST"
FAIL_ESC_CURRENT = "FAIL_ESC_CURRENT"
FAIL_BATTERY_CURRENT = "FAIL_BATTERY_CURRENT"
FAIL_MISSION_ENERGY = "FAIL_MISSION_ENERGY"

# Declared BEFORE any grid is evaluated: governing failure is the first of
# these present in a case's failure set (upstream/most-fundamental first).
GOVERNING_FAILURE_PRIORITY: tuple[str, ...] = (
    FAIL_M1_LOADING,
    FAIL_TIP_MACH,
    FAIL_STATIC_THRUST,
    FAIL_CRUISE_THRUST,
    FAIL_ESC_CURRENT,
    FAIL_BATTERY_CURRENT,
    FAIL_MISSION_ENERGY,
)


@dataclass(frozen=True)
class RobustnessCase:
    diameter_m: float = BASELINE.diameter_m
    reference_c_t: float = BASELINE.reference_c_t
    m_tip_max: float = BASELINE.m_tip_max
    eta_T: float = BASELINE.eta_T
    eta_motor: float = BASELINE.eta_motor
    eta_esc: float = BASELINE.eta_esc
    n_series: int = BASELINE.n_series
    capacity_Ah: float = BASELINE.capacity_Ah
    cruise_duration_s: float = BASELINE.cruise_duration_s
    lapse_model: ThrustLapseModel = BASELINE.lapse_model


@dataclass(frozen=True)
class RobustnessResult:
    case: RobustnessCase
    m1_ok: bool
    tip_mach_ok: bool
    envelope: PerformanceEnvelopeResult
    failures: tuple[str, ...]
    governing_failure: str | None
    feasible: bool


def evaluate_case(requirement: UAVRequirement, case: RobustnessCase) -> RobustnessResult:
    """Evaluate one deterministic robustness case by orchestrating the
    frozen M1-M5 APIs -- no new physics."""
    m1_assumption = NonIdealAssumption(eta_overall=BASELINE.eta_overall)

    candidates = evaluate_candidates(
        requirement, m1_assumption, M1_LIMITS, diameters_m=(case.diameter_m,)
    )
    m1_candidate = candidates[0]
    m1_ok = m1_candidate.meets_disk_loading_limit and m1_candidate.meets_power_limit

    rows = reference_rotational_rows(
        requirement, case.diameter_m, m1_assumption, case.reference_c_t
    )
    static_row = rows["static"]
    tip_mach_ok = static_row.tip_mach <= case.m_tip_max

    motor = MotorAssumptions(
        eta_motor=case.eta_motor, rated_electrical_power_W=DEFAULT_MOTOR_RATED_ELECTRICAL_POWER_W
    )
    esc = ESCModel(eta_esc=case.eta_esc, i_esc_max_A=DEFAULT_ESC_I_MAX_A)
    pack = BatteryPack(
        n_series=case.n_series,
        capacity_Ah=case.capacity_Ah,
        continuous_c_rate_limit=DEFAULT_C_RATE_LIMIT,
    )

    p_static, p_cruise, _sr, _cr = m3_reference_battery_powers(
        requirement, case.diameter_m, m1_assumption, case.reference_c_t, motor, esc
    )
    m4_profile = _mission_profile_for(
        p_static, p_cruise, requirement.n_fans, case.cruise_duration_s
    )

    envelope = evaluate_performance_envelope(
        requirement,
        case.diameter_m,
        requirement.static_thrust_per_fan_N,
        requirement.v_cruise_m_s,
        static_row.p_shaft_est_W,
        p_cruise,
        static_row.rpm,
        case.m_tip_max,
        case.eta_T,
        case.lapse_model,
        motor,
        esc,
        pack,
        m4_profile,
        BASELINE.reserve_fraction,
        BASELINE.usable_fraction,
        CLIMB_POWER_FRACTION_OF_STATIC,
        LOITER_POWER_FRACTION_OF_CRUISE,
        LAUNCH_DURATION_S,
        CLIMB_DURATION_S,
        case.cruise_duration_s,
        LOITER_DURATION_S,
        DEFAULT_AMBIENT,
    )

    failures: list[str] = []
    if not m1_ok:
        failures.append(FAIL_M1_LOADING)
    if not tip_mach_ok:
        failures.append(FAIL_TIP_MACH)
    if not envelope.rpm_recovery.feasible:
        failures.append(FAIL_STATIC_THRUST)
    if not envelope.cruise_margin.passes:
        failures.append(FAIL_CRUISE_THRUST)
    if not envelope.recovered_electrical.esc_current_margin.ok:
        failures.append(FAIL_ESC_CURRENT)
    if not envelope.recovered_electrical.battery_current_margin.ok:
        failures.append(FAIL_BATTERY_CURRENT)
    if not envelope.mission_energy_penalty.capacity_margin.ok:
        failures.append(FAIL_MISSION_ENERGY)

    governing = None
    for candidate_failure in GOVERNING_FAILURE_PRIORITY:
        if candidate_failure in failures:
            governing = candidate_failure
            break

    return RobustnessResult(
        case=case,
        m1_ok=m1_ok,
        tip_mach_ok=tip_mach_ok,
        envelope=envelope,
        failures=tuple(failures),
        governing_failure=governing,
        feasible=len(failures) == 0,
    )


def evaluate_baseline(
    requirement: UAVRequirement | None = None, architecture: FinalArchitecture = BASELINE
) -> PerformanceEnvelopeResult:
    """Convenience: the single baseline case's PerformanceEnvelopeResult."""
    if requirement is None:
        requirement = default_requirement()
    case = RobustnessCase(
        diameter_m=architecture.diameter_m,
        reference_c_t=architecture.reference_c_t,
        m_tip_max=architecture.m_tip_max,
        eta_T=architecture.eta_T,
        eta_motor=architecture.eta_motor,
        eta_esc=architecture.eta_esc,
        n_series=architecture.n_series,
        capacity_Ah=architecture.capacity_Ah,
        cruise_duration_s=architecture.cruise_duration_s,
        lapse_model=architecture.lapse_model,
    )
    return evaluate_case(requirement, case).envelope


# ---------------------------------------------------------------------------
# Robustness grid sweep (Section 7-8)
# ---------------------------------------------------------------------------

ETA_T_GRID: tuple[float, ...] = (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65)
C_T_GRID: tuple[float, ...] = (0.08, 0.12)
M_TIP_MAX_GRID: tuple[float, ...] = (0.75, 0.85, 0.95)
ETA_MOTOR_GRID: tuple[float, ...] = (0.85, 0.90, 0.95)
ETA_ESC_GRID: tuple[float, ...] = (0.95, 0.97, 0.99)
N_SERIES_GRID: tuple[int, ...] = (14, 16)
CAPACITY_GRID_AH: tuple[float, ...] = (24.0, 28.0, 32.0)
CRUISE_DURATION_GRID_S: tuple[float, ...] = (600.0, 1200.0, 1800.0)


def sweep_eta_t(requirement: UAVRequirement) -> list[RobustnessResult]:
    return [
        evaluate_case(requirement, RobustnessCase(eta_T=e)) for e in ETA_T_GRID
    ]


def sweep_grid(
    requirement: UAVRequirement,
    eta_t_values: tuple[float, ...] = ETA_T_GRID,
    cruise_duration_values: tuple[float, ...] = CRUISE_DURATION_GRID_S,
) -> list[RobustnessResult]:
    """The primary 2-D feasibility grid used for the feasibility map
    (eta_T x cruise duration), all other parameters held at baseline."""
    results = []
    for eta_t in eta_t_values:
        for dur in cruise_duration_values:
            case = RobustnessCase(eta_T=eta_t, cruise_duration_s=dur)
            results.append(evaluate_case(requirement, case))
    return results


# ---------------------------------------------------------------------------
# Boundary / breakpoint analysis (Section 9)
# ---------------------------------------------------------------------------


def _bisect_boundary(f, lo: float, hi: float, tol: float = 1e-6, max_iter: int = 100) -> float:
    """Bracketed bisection for a monotone boolean predicate `f(x)` that is
    True on one side of the boundary and False on the other. Requires
    f(lo) != f(hi). Returns the boundary value to within `tol`."""
    f_lo, f_hi = f(lo), f(hi)
    if f_lo == f_hi:
        raise ValueError(
            f"f(lo)={f_lo} and f(hi)={f_hi} must differ for a bracketed boundary search"
        )
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if f(mid) == f_lo:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < tol:
            break
    return 0.5 * (lo + hi)


def find_min_feasible_eta_t(
    requirement: UAVRequirement, lo: float = 0.50, hi: float = 1.00
) -> float:
    """Minimum eta_T (holding all else at baseline) for which the case
    remains fully FEASIBLE. Bisection on the feasibility boolean."""

    def feasible_at(eta_t: float) -> bool:
        return evaluate_case(requirement, RobustnessCase(eta_T=eta_t)).feasible

    if not feasible_at(hi):
        raise ValueError("baseline (eta_T=hi) must be feasible to search for a lower boundary")
    return _bisect_boundary(feasible_at, lo, hi)


def find_max_cruise_duration_s(
    requirement: UAVRequirement, lo: float = 60.0, hi: float = 6000.0
) -> float:
    """Maximum cruise duration (holding all else at baseline) for which
    the 28 Ah mission-energy capacity margin remains >= 0."""

    def energy_ok_at(duration_s: float) -> bool:
        return evaluate_case(
            requirement, RobustnessCase(cruise_duration_s=duration_s)
        ).envelope.mission_energy_penalty.capacity_margin.ok

    if not energy_ok_at(lo):
        raise ValueError(
            "baseline (lo duration) must be energy-feasible to search an upper boundary"
        )
    return _bisect_boundary(energy_ok_at, lo, hi)


def find_min_feasible_eta_motor(
    requirement: UAVRequirement, lo: float = 0.50, hi: float = 0.99
) -> float:
    """Minimum eta_motor (holding all else at baseline) for which the
    recovered-current ESC and battery margins both remain >= 0."""

    def current_ok_at(eta_motor: float) -> bool:
        r = evaluate_case(requirement, RobustnessCase(eta_motor=eta_motor))
        return (
            r.envelope.recovered_electrical.esc_current_margin.ok
            and r.envelope.recovered_electrical.battery_current_margin.ok
        )

    if not current_ok_at(hi):
        raise ValueError("baseline (eta_motor=hi) must be current-feasible")
    return _bisect_boundary(current_ok_at, lo, hi)


def find_min_feasible_eta_esc(
    requirement: UAVRequirement, lo: float = 0.50, hi: float = 0.999
) -> float:
    """Minimum eta_ESC (holding all else at baseline) for which the
    recovered-current ESC and battery margins both remain >= 0."""

    def current_ok_at(eta_esc: float) -> bool:
        r = evaluate_case(requirement, RobustnessCase(eta_esc=eta_esc))
        return (
            r.envelope.recovered_electrical.esc_current_margin.ok
            and r.envelope.recovered_electrical.battery_current_margin.ok
        )

    if not current_ok_at(hi):
        raise ValueError("baseline (eta_ESC=hi) must be current-feasible")
    return _bisect_boundary(current_ok_at, lo, hi)


def find_min_required_capacity_Ah(
    requirement: UAVRequirement, lo: float = 1.0, hi: float = 60.0
) -> float:
    """Minimum battery capacity (holding all else, including eta_T, at
    baseline) for which the mission-energy margin remains >= 0."""

    def energy_ok_at(capacity_Ah: float) -> bool:
        return evaluate_case(
            requirement, RobustnessCase(capacity_Ah=capacity_Ah)
        ).envelope.mission_energy_penalty.capacity_margin.ok

    if not energy_ok_at(hi):
        raise ValueError("baseline (hi capacity) must be energy-feasible")
    return _bisect_boundary(energy_ok_at, lo, hi)


def max_recoverable_thrust_loss_fraction(requirement: UAVRequirement) -> float:
    """DERIVED: the maximum static thrust shortfall (1 - eta_T) whose RPM
    recovery still fits within the M2 tip-Mach RPM ceiling, i.e. the
    eta_T at which RPM_required == RPM_ceiling exactly (independently
    reconstructed, not merely read off `compute_rpm_recovery.feasible`)."""
    rows = reference_rotational_rows(
        requirement, BASELINE.diameter_m, NonIdealAssumption(eta_overall=BASELINE.eta_overall),
        BASELINE.reference_c_t,
    )
    rpm_ref = rows["static"].rpm
    from edf_sizing import compressibility as comp

    ceiling = comp.max_rpm_static(BASELINE.diameter_m, BASELINE.m_tip_max, DEFAULT_AMBIENT)
    eta_t_boundary = (rpm_ref / ceiling) ** 2
    return 1.0 - eta_t_boundary


# ---------------------------------------------------------------------------
# Sensitivity ranking (Section 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensitivityRanking:
    parameter: str
    tested_range: tuple[float, ...]
    governing_metric_values: tuple[float, ...]
    max_fractional_swing: float
    feasibility_flips: bool
    rank: int = 0


def _governing_margin_metric(result: RobustnessResult) -> float:
    """The declared ranking metric (Section 10): the minimum margin across
    ALL mandatory numeric gates -- ESC current, battery current, mission
    energy, cruise thrust, AND the RPM-recovery/tip-Mach headroom
    (`(ceiling - required)/ceiling`) -- i.e. the single most-binding
    margin for that case. More negative = worse. Including the RPM-
    recovery headroom is required for consistency: a parameter (e.g.
    `m_tip_max`) can flip overall feasibility purely through this gate,
    and a ranking metric that ignored it would silently under-rank it."""
    e = result.envelope
    rr = e.rpm_recovery
    rpm_headroom_fraction = (rr.rpm_ceiling - rr.rpm_required) / rr.rpm_ceiling
    return min(
        e.recovered_electrical.esc_current_margin.margin,
        e.recovered_electrical.battery_current_margin.margin,
        e.mission_energy_penalty.capacity_margin.margin,
        e.cruise_margin.margin_fraction,
        rpm_headroom_fraction,
    )


def rank_sensitivities(requirement: UAVRequirement) -> list[SensitivityRanking]:
    """Rank predeclared sensitivity parameters by the maximum fractional
    swing they cause in the governing-margin metric (Section 10), computed
    -- not asserted."""
    sweeps: dict[str, tuple[tuple[float, ...], list[RobustnessResult]]] = {
        "eta_T": (
            ETA_T_GRID,
            [evaluate_case(requirement, RobustnessCase(eta_T=v)) for v in ETA_T_GRID],
        ),
        "cruise_duration_s": (
            CRUISE_DURATION_GRID_S,
            [
                evaluate_case(requirement, RobustnessCase(cruise_duration_s=v))
                for v in CRUISE_DURATION_GRID_S
            ],
        ),
        "eta_motor": (
            ETA_MOTOR_GRID,
            [evaluate_case(requirement, RobustnessCase(eta_motor=v)) for v in ETA_MOTOR_GRID],
        ),
        "eta_esc": (
            ETA_ESC_GRID,
            [evaluate_case(requirement, RobustnessCase(eta_esc=v)) for v in ETA_ESC_GRID],
        ),
        "n_series": (
            tuple(float(v) for v in N_SERIES_GRID),
            [evaluate_case(requirement, RobustnessCase(n_series=v)) for v in N_SERIES_GRID],
        ),
        "capacity_Ah": (
            CAPACITY_GRID_AH,
            [evaluate_case(requirement, RobustnessCase(capacity_Ah=v)) for v in CAPACITY_GRID_AH],
        ),
        "m_tip_max": (
            M_TIP_MAX_GRID,
            [evaluate_case(requirement, RobustnessCase(m_tip_max=v)) for v in M_TIP_MAX_GRID],
        ),
        "reference_c_t": (
            C_T_GRID,
            [evaluate_case(requirement, RobustnessCase(reference_c_t=v)) for v in C_T_GRID],
        ),
    }

    rankings: list[SensitivityRanking] = []
    for name, (values, results) in sweeps.items():
        metrics = tuple(_governing_margin_metric(r) for r in results)
        finite_metrics = [m for m in metrics if abs(m) > 1e-12]
        if finite_metrics:
            swing = (max(metrics) - min(metrics)) / max(abs(m) for m in finite_metrics)
        else:
            swing = 0.0
        flips = len({r.feasible for r in results}) > 1
        rankings.append(
            SensitivityRanking(
                parameter=name,
                tested_range=values,
                governing_metric_values=metrics,
                max_fractional_swing=swing,
                feasibility_flips=flips,
            )
        )

    rankings.sort(key=lambda r: r.max_fractional_swing, reverse=True)
    return [
        SensitivityRanking(
            parameter=r.parameter,
            tested_range=r.tested_range,
            governing_metric_values=r.governing_metric_values,
            max_fractional_swing=r.max_fractional_swing,
            feasibility_flips=r.feasibility_flips,
            rank=i + 1,
        )
        for i, r in enumerate(rankings)
    ]


# ---------------------------------------------------------------------------
# Diameter robustness (Section 11)
# ---------------------------------------------------------------------------

DIAMETER_GRID_M: tuple[float, ...] = (0.45, 0.50, 0.55, 0.60)


def sweep_diameter(requirement: UAVRequirement) -> list[RobustnessResult]:
    return [evaluate_case(requirement, RobustnessCase(diameter_m=d)) for d in DIAMETER_GRID_M]
