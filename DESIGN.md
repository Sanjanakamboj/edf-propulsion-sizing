# DESIGN.md -- EDF Propulsion Sizing

Portfolio engineering study. This document records the sources inspected,
the exact equations implemented, every explicit assumption, and the
Milestone 1 scope boundary.

## 1. Source audit (inspected before writing any physics code)

The following primary/high-quality references on actuator-disk momentum
theory and propeller/rotor ideal-power relations were inspected via web
search and page fetch before implementation:

1. **NASA Glenn Research Center -- Thrust Equation** (beginners guide to
   aeronautics, `www1.grc.nasa.gov/beginners-guide-to-aeronautics/thrust-force/`).
   Confirms the general momentum-based thrust equation
   `F = (ṁv)_e - (ṁv)_0 + A_e(p_e - p_0)` and its simplified forms. Does not
   itself carry propeller actuator-disk induced-velocity relations, but
   establishes the momentum-conservation basis used throughout.
2. **MIT OpenCourseWare 16.unified, Unified Propulsion 7 -- "Production of
   Thrust with a Propeller"**
   (`ocw.mit.edu/ans7870/16/16.unified/propulsionS04/UnifiedPropulsion7/UnifiedPropulsion7.htm`).
   Traceable derivation of: thrust `T = ṁ(V_e - V_0)`, disk velocity
   `V_disk = (V_0 + V_e)/2` (i.e. the induced velocity is half the total
   velocity change, split evenly upstream/downstream of the disk), ideal
   power `P_ideal = T·V_disk`, and disk loading `T/A_disk`. This is the
   primary traceable source for the forward-flight relations implemented
   here.
3. **Wikipedia -- Momentum theory** (`en.wikipedia.org/wiki/Momentum_theory`,
   itself citing Leishman, *Principles of Helicopter Aerodynamics*, and
   Glauert's classical actuator-disk analysis). Confirms the classical
   hover/static ideal power result `P = T^(3/2) / sqrt(2*rho*A)`, matching
   the closed-form static relation implemented here.
4. General web survey (search only, not fetched in full) of NASA Technical
   Reports Server actuator-disk material (e.g. NASA TM X-62,138) and
   AIAA/university course material, cross-confirming the same T/vi/Pi
   relations and terminology (disk loading, induced velocity, ideal power)
   used across the aerospace literature. These were used only to corroborate
   consistency of notation and did not introduce any additional equations
   beyond items 1-3.

**No empirical EDF-specific coefficient was found or used.** The only
non-ideal number in this codebase is a single illustrative overall
propulsive/fan efficiency (Section 4), explicitly labeled unsourced.

## 2. Ideal actuator-disk equations implemented

All implemented in `src/edf_sizing/actuator_disk.py`, matching the sources
above. `A = pi*D^2/4` is disk area, `rho` is air density, `V_inf` is
freestream speed, `vi` is induced velocity at the disk, `T` is thrust, `Pi`
is ideal flow/shaft power (loss-free), and disk loading is `T/A`.

### Static (hover, `V_inf = 0`)

```
T  = 2 * rho * A * vi^2
vi = sqrt(T / (2 * rho * A))
Pi = T * vi = T^(3/2) / sqrt(2 * rho * A)
```

### Axial forward flight (`V_inf > 0`)

```
T  = 2 * rho * A * vi * (V_inf + vi)
Pi = T * (V_inf + vi)
```

Solving the thrust relation for `vi` gives a quadratic
`2*rho*A*vi^2 + 2*rho*A*V_inf*vi - T = 0`. The single physically valid
(non-negative) root is

```
vi = -V_inf/2 + sqrt((V_inf/2)^2 + T/(2*rho*A))
```

which reduces exactly to the static formula as `V_inf -> 0` (verified in
`tests/test_actuator_disk.py::test_forward_flight_reduces_to_static_as_v_inf_vanishes`).

No blade-element, RPM, tip-speed, duct, or compressibility physics appear
in this module -- it is pure 1-D actuator-disk / momentum theory.

## 3. Representative generic UAV requirement

Implemented in `src/edf_sizing/requirements.py`. Every number below is an
illustrative, hand-picked choice for a *generic* small EDF-propelled UAV
concept -- **not** a real aircraft, and not derived from any specific
program.

| Quantity | Value | Rationale (illustrative) |
|---|---|---|
| Mass | 25.0 kg | Representative small tactical/portfolio-scale UAV |
| Number of fans | 2 | Simple twin-EDF layout |
| Air density | 1.225 kg/m^3 | ISA sea-level standard atmosphere |
| Cruise speed | 30.0 m/s | Plausible cruise speed for this weight class |
| Static thrust-to-weight | 1.2 | Illustrative margin for vertical/hover-equivalent maneuvering |
| Cruise lift-to-drag | 8.0 | Illustrative L/D stand-in; no wing/drag-polar model is implemented -- cruise thrust is simply `weight / (L/D)` |

From these: `static_thrust_per_fan = 1.2*weight/n_fans`,
`cruise_thrust_per_fan = (weight/8.0)/n_fans`. No aerodynamic drag-polar or
mission-profile model exists in this codebase; the L/D value is a single
scalar used only to produce a physically-motivated cruise thrust magnitude.

## 4. Non-ideal efficiency bookkeeping layer

Implemented in `src/edf_sizing/efficiency.py`, deliberately separated from
`actuator_disk.py`. Real EDF units incur profile drag, swirl, duct/inlet
losses, motor and ESC losses -- none of which are modeled here. Instead:

```
P_shaft_est = Pi / eta_overall
```

`eta_overall = 0.75` is used in the scripts as a single illustrative,
**unsourced** overall propulsive/fan efficiency placeholder. It is labeled
"illustrative" everywhere it is printed or plotted, and it must not be
confused with "motor power" -- it is a bookkeeping estimate of combined
non-ideal shaft/electrical power, not a motor efficiency map. If/when a
sourced coefficient becomes available, it will be substituted here without
touching the ideal actuator-disk math.

## 5. Fan diameter selection rule (predeclared before evaluating candidates)

> Select the smallest candidate diameter (from the predeclared sweep) that
> keeps static disk loading and static ideal power at or below explicitly
> chosen illustrative limits, for the required static thrust per fan. If no
> candidate qualifies, report failure honestly rather than forcing a
> selection.

Predeclared limits (`src/edf_sizing/sizing.py::SelectionLimits` defaults):

- Max static disk loading: **900 N/m^2** (illustrative, small-UAV EDF scale)
- Max static ideal power per fan: **3500 W** (illustrative)

Candidate sweep (`DEFAULT_CANDIDATE_DIAMETERS_M`): 0.15 m to 0.60 m in
0.05 m steps (10 candidates). These limits and the candidate sweep were
fixed before any candidate was evaluated, and are not tuned after the fact
to force a particular diameter.

### Milestone 1 result

For the default requirement, the selection rule picks **D = 0.50 m** (the
smallest candidate meeting both limits: disk loading 749.2 N/m^2, static
ideal power 2572.3 W). Smaller candidates (0.15-0.45 m) fail one or both
limits; see `scripts/run_sizing.py` output and Figure 1.

## 6. Milestone 1 output: representative static/cruise thrust table

For the selected D = 0.50 m fan:

| Operating point | V_inf [m/s] | T per fan [N] | Disk loading [N/m^2] | v_i [m/s] | P_i [W] | P_shaft,est [W] |
|---|---|---|---|---|---|---|
| Static | 0.00 | 147.10 | 749.2 | 17.49 | 2572.3 | 3429.7 |
| Cruise | 30.00 | 15.32 | 78.0 | 1.03 | 475.4 | 633.9 |

`P_shaft,est` uses the illustrative `eta_overall = 0.75` bookkeeping layer
(Section 4) and is clearly distinct from the ideal `P_i` column.

## 7. Verification approach

`tests/test_actuator_disk.py`, `tests/test_efficiency.py`,
`tests/test_requirements.py`, and `tests/test_sizing.py` implement
independent checks (see each file's docstring), including:

- Hand-derived numeric checks for static induced velocity and power
  (literal expected values, not re-derived from the production formula).
- Analytic verification that the forward-flight quadratic root satisfies
  `T = 2*rho*A*vi*(V_inf+vi)` when substituted back in, across several
  thrust/speed/diameter combinations.
- Limiting behavior as `V_inf -> 0` (forward-flight formulas reduce to the
  static formulas).
- Dimensional/monotonic sanity: increasing diameter at fixed thrust lowers
  disk loading and ideal power; increasing thrust at fixed diameter raises
  power monotonically (static and forward-flight).
- Scalar/vector (NumPy) consistency for every vectorized function.
- Invalid-input rejection (non-positive diameter/area/density, negative
  thrust/speed, out-of-range efficiency).
- An independent energy/power reconstruction using mass-flow and far-wake
  velocity (`Ve = 2*vi` static, `Ve = V_inf + 2*vi` forward flight) that
  never calls the closed-form `T^(3/2)/sqrt(2*rho*A)` or `T=2*rho*A*vi*(V+vi)`
  formulas directly, and is compared against the production implementation.

## 8. Explicit Milestone 1 limitations

- No blade-element theory, no RPM selection, no motor Kv selection.
- No tip-Mach or compressibility constraint on induced/tip velocity.
- No duct pressure-recovery or inlet/exit loss model.
- No motor controller (ESC) or battery sizing.
- No acoustic prediction.
- No real commercial EDF unit calibration; `eta_overall` is a placeholder.
- Cruise thrust requirement uses a single illustrative L/D scalar, not a
  drag-polar or mission-profile model.

## 9. Milestone 1 status

Milestone 1 is complete and frozen as of commit `782cc88`. Milestone 2
(below) is purely additive: it imports and reuses
`actuator_disk.py`/`efficiency.py`/`requirements.py`/`sizing.py` without
modifying them, and every Milestone 1 test, script, and figure remains
unchanged (see Section 17).

---

# Milestone 2 -- RPM, tip-Mach, and reduced-order fan-loading

## 10. Source audit (inspected before writing any M2 physics code)

1. **NACA/propeller-literature thrust and power coefficient conventions**
   (corroborated across `mh-aerotools.de/airfoils/propuls3.htm`, a
   propeller-performance reference restating the classical NACA-style
   nondimensional coefficients, and the NASA/AIAA search survey below).
   Confirms, verbatim:
   - `C_T = T / (rho * n^2 * D^4)`
   - `C_P = P / (rho * n^3 * D^5)`
   - Advance ratio `J = V / (n * D)`
   - Propeller efficiency `eta = J * C_T / C_P`
   with `T` in N, `P` in W, `n` in rev/s, `D` in m, `rho` in kg/m^3 --
   exactly the convention adopted in `src/edf_sizing/fan_loading.py`.
2. **Helical blade-tip speed / tip Mach number** (`kitplanes.com/wind-tunnel-52/`,
   a propeller-design reference restating the classical helical-tip-speed
   construction, corroborated by a broader NASA NTRS search on "helical tip
   Mach number" propeller noise/performance literature, e.g. NASA TM
   82891). Confirms the tangential (rotational) tip speed
   `V_r = pi*D*N/60` (N in rpm, D in the source's units) and the *total*
   (helical) tip speed as the vector sum of tangential and forward speed,
   `V_t = sqrt(V^2 + V_r^2)`, with tip Mach number `= V_t / a`. This is the
   exact kinematic construction implemented as `relative_tip_mach` in
   `src/edf_sizing/compressibility.py`. The same source states a
   conventional propeller design practice of keeping tip Mach below
   roughly 0.8-0.9 (metal/composite blades a bit higher, wooden blades a
   bit lower) -- used here only as the origin of the Section 12
   illustrative tip-Mach ceiling, not as a sourced EDF-specific limit.
3. **NASA NTRS actuator-disk / propeller general survey** (search only, not
   fetched in full; e.g. NASA TM X-62,138 and related NACA/NASA propeller
   reports) -- corroborates that the C_T/C_P/tip-speed terminology above is
   the standard propeller-literature convention, without introducing any
   additional equations beyond items 1-2.
4. **Ideal-gas speed of sound** (standard atmospheric physics, restated
   from general physics references): `a = sqrt(gamma * R_specific * T)`
   with `gamma = 1.4` (diatomic ideal gas) and `R_specific = 287.05
   J/(kg*K)` for dry air. At the ISA sea-level standard temperature
   `T = 288.15 K` (15 degC) this reproduces the well-known ISA sea-level
   speed of sound `a ~= 340.3 m/s`, which the implementation matches to
   0.1 m/s (see `tests/test_compressibility.py`).

**No credible universal EDF-specific C_T, C_P, or tip-Mach limit was
found.** Both are therefore treated as explicit, labeled sensitivity
parameters (Sections 11-12), never as sourced design values.

## 11. Rotational kinematics (SOURCED -- standard rigid-body kinematics)

Implemented in `src/edf_sizing/rotational.py`:

```
n     = RPM / 60                     [rev/s]
omega = 2*pi*n                       [rad/s]
R     = D / 2                        [m]
U_tip = omega * R = pi * D * n       [m/s]
```

No aerodynamics or atmosphere appears in this module -- it is pure
kinematics relating RPM, angular speed, and blade-tip speed.

## 12. Speed of sound and blade-tip Mach (SOURCED equations + DERIVED root; ILLUSTRATIVE ceiling)

Implemented in `src/edf_sizing/compressibility.py`.

**SOURCED:**

```
a = sqrt(gamma * R_specific * T)                     (Section 10.4)
M_tip,static = U_tip / a                             (Section 10.2)
M_tip,rel    = sqrt(U_tip^2 + V_inf^2) / a            (Section 10.2)
```

`T = 288.15 K` (ISA sea level) is used for consistency with the Milestone 1
`rho = 1.225 kg/m^3` assumption -- a generic illustrative UAV operating
condition, not a specific mission profile.

`M_tip,rel` is a purely kinematic helical-tip-speed estimate: the vector
sum of the rotational tip speed and the axial freestream speed. It is
**NOT** a blade-section local Mach solution, **NOT** a compressible
blade-element calculation, and **NOT** a shock/transonic prediction --
induced (axial) velocity through the disk and any spanwise/sweep effects
are ignored.

**DERIVED (RPM ceiling, inverting the tip-Mach constraint):**

Static: from `M_tip,static <= M_tip,max`,

```
RPM_max = 60 * M_tip_max * a / (pi * D)
```

Forward flight: from `M_tip,rel <= M_tip,max`, i.e.
`sqrt(U_tip^2 + V_inf^2) <= M_tip_max*a`,

```
U_tip_max = sqrt((M_tip_max*a)^2 - V_inf^2)      [if M_tip_max*a > V_inf]
RPM_max   = 60 * U_tip_max / (pi * D)
```

which reduces exactly to the static closed form as `V_inf -> 0`. Per the
Milestone 2 specification, cases with `M_tip_max*a <= V_inf` are rejected
as infeasible: the freestream speed alone already meets/exceeds the
allowed relative tip Mach, so no rotational speed (not even 0 RPM) can
satisfy the constraint as a usable operating ceiling. This is implemented
as `RpmCeilingResult(feasible=False, ...)` rather than raising, so sweeps
can report infeasibility honestly instead of crashing (see
`tests/test_compressibility.py::test_forward_flight_rpm_ceiling_exact_boundary_infeasible_case`
for the exact-boundary behavior).

**ILLUSTRATIVE tip-Mach ceiling:** `M_tip_max = 0.85` baseline, with a
sensitivity set `{0.75, 0.85, 0.95}` (`src/edf_sizing/rotational_study.py`).
Informed by the ~0.8-0.9 conventional-propeller design-practice range
noted in Section 10.2, but **not** a sourced universal EDF-specific limit
-- treated throughout as a configurable, labeled assumption.

## 13. Fan pressure-jump estimate (DERIVED identity with M1 disk loading)

Implemented in `src/edf_sizing/fan_loading.py::pressure_jump_disk`:

```
Delta_p_disk = T / A
```

This is numerically **identical** to the Milestone 1 disk-loading quantity
(`edf_sizing.actuator_disk.disk_loading`) -- the same actuator-disk
momentum-theory quantity, given a distinct name/interpretation ("idealized
static pressure jump across the disk") to make that reading explicit. It
is verified as an exact cross-model identity in
`tests/test_fan_loading.py::test_pressure_jump_disk_identity_with_m1_disk_loading`
and `tests/test_rotational_study.py::test_pressure_jump_matches_m1_disk_loading_for_selected_fan`.

This is **NOT** a fan-stage pressure ratio and does **NOT** model any real
internal static-pressure distribution through an EDF duct/rotor/stator
stage -- it is the same 1-D actuator-disk idealization as Milestone 1,
reinterpreted as a pressure jump rather than a force-per-area loading.

## 14. Nondimensional coefficients and RPM-from-C_T inversion

Implemented in `src/edf_sizing/fan_loading.py` (conventions per Section
10.1):

```
C_T = T / (rho * n^2 * D^4)
C_P = P / (rho * n^3 * D^5)
J   = V_inf / (n * D)
```

`n = 0` is explicitly rejected (`ValueError`) in all three -- rotational
coefficients are undefined at zero RPM, never silently evaluated. `P` in
`C_P` is always the Milestone 1 **illustrative estimated shaft power**
(`eta_overall = 0.75` bookkeeping estimate), never the ideal actuator-disk
power and never a measured/calibrated fan efficiency.

**DERIVED inversion** (RPM-from-C_T, Section 8 of the Milestone 2 brief):

```
n = sqrt(T / (rho * C_T * D^4))
RPM = 60*n
```

No defensible single universal C_T exists for a generic reduced-order EDF
unit at this design stage (Section 10 source audit), so RPM is reported
across an explicit, deterministic **ILLUSTRATIVE** sensitivity set
`C_T in {0.05, 0.08, 0.12}` (`src/edf_sizing/rotational_study.py`) rather
than asserting one "design RPM". Round-trip identity (recomputing C_T from
the inferred n recovers the assumed C_T) is verified in
`tests/test_fan_loading.py::test_rev_per_second_from_thrust_coefficient_round_trip`.

**Important limitation:** for a given operating point, RPM is inferred
independently per assumed C_T case, but the Milestone 1 `P_shaft_est` used
in `C_P` is *not* a function of that RPM (it comes only from the ideal
actuator-disk power and `eta_overall`). The resulting `C_P` values are
therefore a nondimensional bookkeeping exercise, not a physically matched
propeller/fan performance map (no sourced C_T-vs-C_P-vs-J curve is used or
implied).

## 15. Milestone 2 results

### 15.1 Static/cruise rotational operating table (selected D = 0.50 m fan)

Ambient: ISA sea level, `a = 340.29 m/s`. Tip-Mach ceiling baseline
`M_tip_max = 0.85` (illustrative).

| Point | C_T | V_inf [m/s] | T [N] | RPM | U_tip [m/s] | Tip Mach | Mach OK? | Δp_disk [Pa] | C_P | J |
|---|---|---|---|---|---|---|---|---|---|---|
| static | 0.05 | 0.0 | 147.10 | 11762 | 307.9 | 0.905 | **NO** | 749.2 | 0.0119 | 0.000 |
| static | 0.08 | 0.0 | 147.10 | 9298 | 243.4 | 0.715 | yes | 749.2 | 0.0241 | 0.000 |
| static | 0.12 | 0.0 | 147.10 | 7592 | 198.8 | 0.584 | yes | 749.2 | 0.0442 | 0.000 |
| cruise | 0.05 | 30.0 | 15.32 | 3796 | 99.4 | 0.305 | yes | 78.0 | 0.0654 | 0.948 |
| cruise | 0.08 | 30.0 | 15.32 | 3001 | 78.6 | 0.247 | yes | 78.0 | 0.1323 | 1.200 |
| cruise | 0.12 | 30.0 | 15.32 | 2450 | 64.1 | 0.208 | yes | 78.0 | 0.2431 | 1.469 |

Static and cruise are each swept over the *same* illustrative C_T set, but
are not forced to use matching values -- the RPM columns differ
substantially between them, as expected for very different thrust levels.

An honest, not-tuned-away result: the lowest-C_T static case (0.05)
requires enough RPM that the static tip Mach (0.905) exceeds the 0.85
illustrative ceiling; the two higher-C_T static cases and all cruise cases
pass.

### 15.2 Diameter x RPM/tip-Mach trade (full Milestone 1 candidate sweep)

Static thrust requirement fixed at 147.10 N/fan; RPM inferred per C_T case,
tip Mach checked against `M_tip_max = 0.85`.

| D [m] | M1 disk loading | M1 ideal power | tip-Mach @ C_T=0.05 | @ C_T=0.08 | @ C_T=0.12 | Fully admissible? |
|---|---|---|---|---|---|---|
| 0.15-0.30 | FAIL | FAIL | FAIL | FAIL | FAIL | no |
| 0.35 | FAIL | FAIL | FAIL | FAIL | OK | no |
| 0.40 | FAIL | OK | FAIL | FAIL | OK | no |
| 0.45 | FAIL | OK | FAIL | OK | OK | no |
| **0.50 (M1 selected)** | OK | OK | **FAIL** | OK | OK | **partial** |
| 0.55, 0.60 | OK | OK | OK | OK | OK | yes |

Full per-diameter, per-C_T table: `scripts/rotational_fan_study.py` output
and Figure 7.

### 15.3 Reconciliation: does Milestone 2 change the Milestone 1 selection?

**No.** The Milestone 1 D = 0.50 m selection is not invalidated: it still
passes both Milestone 1 checks (disk loading, ideal power), and it passes
the Milestone 2 tip-Mach constraint for 2 of the 3 illustrative C_T
sensitivity cases (0.08 and 0.12). It fails only the most lightly-loaded
C_T = 0.05 case, which is reported honestly rather than tuned away (per
the Milestone 2 brief, "some assumed C_T cases violate the tip-Mach
ceiling" is an acceptable, expected outcome).

**Conclusion: Milestone 2 constrains the admissible RPM range for the
Milestone 1-selected fan (and, for the lowest-loading C_T assumption,
rules out that specific operating point) -- it does not change the
Milestone 1 diameter selection.** See
`edf_sizing.rotational_study.reconcile_selection_with_tip_mach` and
`scripts/rotational_fan_study.py`.

## 16. Verification approach (Milestone 2)

`tests/test_rotational.py`, `tests/test_compressibility.py`,
`tests/test_fan_loading.py`, and `tests/test_rotational_study.py`
implement independent checks (hand-derived, not re-derived from the
production formula), including:

- RPM <-> rev/s, omega, and tip-speed hand cases, plus an independent
  `omega*R` cross-check of `tip_speed`.
- Speed-of-sound hand calculation matching the ~340.3 m/s ISA sea-level
  reference value.
- Static and relative tip-Mach hand cases; relative-tip-Mach reduction to
  the static formula at `V_inf = 0`; relative tip Mach always >= static
  tip Mach at the same RPM.
- RPM-ceiling analytic exact-boundary tests: mach exactly at the ceiling,
  just-below passes, just-above fails; forward-flight infeasibility at and
  above the `M_tip_max*a <= V_inf` boundary.
- Pressure-jump hand calculation and the cross-model identity with the
  Milestone 1 disk loading.
- C_T/C_P/J hand calculations; C_T scaling as RPM^-2, C_P as RPM^-3 at
  fixed T/P/D; zero-RPM rejection for all three.
- RPM-from-C_T hand-derived inversion and round-trip C_T recovery;
  required RPM scaling as C_T^-1/2 and as D^-2.
- Physical trends: U_tip linear in RPM; tip Mach monotonic in RPM; RPM
  ceiling scaling as D^-1; stricter M_tip_max giving lower allowable RPM.
- Regression: Milestone 1 static/cruise thrust-per-fan values and the
  D = 0.50 m selection are unchanged (`tests/test_rotational_study.py`
  regression tests).
- No NaN/Inf across the full operating table and diameter/C_T trade sweep.

**Final Milestone 2 test count: 65 new tests (123 total with Milestone 1's
58, all passing under `pytest -W error -q`).**

## 17. Explicit Milestone 2 limitations

- No blade-element theory: `C_T`/`C_P` are bulk nondimensional numbers, not
  derived from any blade planform, airfoil, or twist distribution.
- No motor Kv selection, no ESC or battery sizing.
- `C_P` is computed from the Milestone 1 illustrative `P_shaft_est`, which
  is independent of the RPM used in that same row -- this is a
  nondimensional bookkeeping exercise, not a matched propeller/fan
  performance map (no C_T-C_P-J curve is fit or assumed).
- The relative-tip-Mach construction is a kinematic helical-speed estimate
  only; it ignores induced/axial velocity through the disk, blade sweep,
  and any local compressibility/shock effects.
- `M_tip_max = 0.85` (and its `{0.75, 0.85, 0.95}` sensitivity set) is an
  illustrative ceiling informed by general conventional-propeller design
  practice, not a sourced universal EDF-specific limit.
- `C_T in {0.05, 0.08, 0.12}` is an illustrative sensitivity set, not a
  sourced design value for this or any specific EDF unit.
- No duct pressure-recovery, inlet/exit loss, or detailed compressor-map
  model; the pressure-jump estimate remains the same 1-D actuator-disk
  idealization as Milestone 1.
- No CFD, no acoustic prediction, no real commercial EDF calibration.
- Milestone 1's `eta_overall = 0.75` remains a placeholder (Section 4),
  unchanged and unrevisited in Milestone 2.

## 18. Milestone 2 status

Milestone 2 is complete and frozen as of commit `bdd924a`. Milestone 3
(below) is purely additive: it imports and reuses Milestone 1
(`actuator_disk.py`/`efficiency.py`/`requirements.py`/`sizing.py`) and
Milestone 2 (`rotational.py`/`compressibility.py`/`fan_loading.py`/
`rotational_study.py`) without modifying any of them, and every Milestone
1/2 test, script, and figure remains unchanged (see Section 25).

---

# Milestone 3 -- motor / ESC / battery electrical matching

## 19. Source audit (inspected before writing any M3 electrical physics)

1. **Electrical power and motor efficiency** (Tyto Robotics, "Brushless
   Motor Power and Efficiency Analysis" -- a widely used practical
   reference for RC/small-UAV brushless motor testing, restating standard
   electrical-machine bookkeeping). Confirms, verbatim: electrical power
   `P = V*I`; mechanical power `P_mech = Torque * RPM`; motor efficiency
   = mechanical power output / electrical power input. This is the
   standard `eta_motor = P_shaft / P_motor_elec` relation implemented in
   `src/edf_sizing/motor.py`. No electromagnetic (winding resistance,
   back-EMF, current-torque) model is taken from this or any other source
   -- motor behavior here is reduced to a single efficiency number.
2. **NASA CR-2506, "Brushless DC Motors"** (NASA Technical Reports Server,
   search-corroborated) -- general aerospace context confirming brushless
   DC motor terminology and that all motor mechanical power is delivered
   to the coupled load (here, the fan) with no separate transmission
   losses modeled.
3. **LiPo cell voltage and C-rate convention** (Roger's Hobby Center LiPo
   guide, a widely cited hobbyist/technical reference restating the
   standard convention; cross-checked against multiple similar sources
   found in the audit search). Confirms, verbatim: LiPo nominal cell
   voltage **3.7 V**; full-charge cell voltage **4.2 V**; minimum/cutoff
   cell voltage **3.0 V** (never to be confused with each other); series
   pack convention "2S = 7.4 V, 3S = 11.1 V" (i.e. `V_pack = N_s *
   V_cell`); C-rate as a multiplier on capacity (Ah) giving maximum
   continuous current. These are exactly the conventions implemented in
   `src/edf_sizing/battery.py`.
4. **Motor Kv (rpm/V) convention** (Endless Sphere DIY EV forum "The exact
   meaning of Kv", Brushless.com, and Tyto Robotics Kv/pole-count guides --
   search-corroborated, consistent across sources). Confirms Kv is a
   **no-load** speed-per-volt constant, and that using it to infer *loaded*
   RPM from a supply voltage alone is not rigorous (the relevant voltage
   is back-EMF, not applied terminal voltage, once current flows). **No
   sourced, independently verifiable loaded-RPM-from-Kv relation was
   found that could be implemented without either inventing an
   unsupported approximation or requiring winding-resistance/current data
   this project does not model.** Per the Milestone 3 brief's explicit
   fallback, **Kv is deliberately omitted entirely** -- Milestone 3 sizes
   power, current, and torque, but does not constrain or select a motor
   winding speed constant. This is a stated limitation (Section 24), not
   an oversight.

**No credible universal motor/ESC efficiency, current rating, or C_T-tied
electrical coefficient was found for a generic reduced-order EDF unit.**
`eta_motor`, `eta_ESC`, ESC current rating, motor rated power, and the
battery continuous C-rate limit are therefore all explicit, illustrative
sensitivity parameters (Section 21), never sourced design values.

## 20. Electrical power chain (no double-counting of `eta_overall`)

Implemented across `src/edf_sizing/motor.py`, `electrical.py`, and
`battery.py`, combined in `electrical_sizing.py`. The full chain, with
each stage's SOURCED equation and which module owns it:

```
M1 ideal actuator-disk power       Pi                                  [actuator_disk.py, UNCHANGED]
  -> M1 estimated shaft power      P_shaft_est = Pi / eta_overall       [efficiency.py, UNCHANGED, eta_overall=0.75]
  -> motor electrical input        P_motor_elec = P_shaft_est / eta_motor   [motor.py, NEW]
  -> battery input power           P_battery = P_motor_elec / eta_ESC       [electrical.py, NEW]
  -> battery current                I_battery = P_battery / V_pack          [electrical.py, NEW]
```

`P_shaft_est` (already divided by `eta_overall=0.75` exactly once,
upstream in Milestone 1) is treated as the **inherited, fixed** mechanical
shaft-power requirement for Milestone 3 -- it is read from
`RotationalOperatingRow.p_shaft_est_W` and passed directly into
`motor_electrical_power`, which divides it by `eta_motor` only. `eta_overall`
is never referenced, imported, or re-applied anywhere in `motor.py`,
`electrical.py`, `battery.py`, or `electrical_sizing.py` (a structural
import check enforces this in
`tests/test_electrical_sizing.py::test_no_double_counting_of_eta_overall`).

Also implemented: shaft torque `Q = P_shaft / omega` (`motor.py`, using
`omega` from Milestone 2's `rotational.angular_speed` -- an independent
cross-check via `omega*R` style reconstruction is in
`tests/test_motor.py`), and a generic `rating_margin(rated, required) =
rated/required - 1` (`electrical.py`) used for every ESC/battery/motor
margin, never clipped at zero.

## 21. Motor / ESC / battery assumptions (ILLUSTRATIVE unless noted)

| Assumption | Baseline | Sensitivity set | Status |
|---|---|---|---|
| `eta_motor` | 0.90 | {0.85, 0.90, 0.95} | ILLUSTRATIVE |
| `eta_ESC` | 0.97 | {0.95, 0.97, 0.99} | ILLUSTRATIVE |
| Motor rated electrical power | 4500 W | -- | ILLUSTRATIVE |
| ESC continuous current rating | 100 A | {80, 100, 120} A | ILLUSTRATIVE |
| Pack capacity | 4.0 Ah | {4.0, 6.0, 8.0} Ah | ILLUSTRATIVE |
| Pack continuous C-rate limit | 20C | -- | ILLUSTRATIVE |
| Candidate series counts | -- | {12S, 14S, 16S} | ILLUSTRATIVE |
| LiPo cell voltages (nom/full/min) | 3.7 / 4.2 / 3.0 V | -- | **SOURCED** (Section 19.3) |

None of these (other than the cell-voltage convention) are sourced from a
real motor/ESC/battery datasheet -- they are conceptual, generic values
chosen only to exercise the sizing model, per the Milestone 3 brief.

## 22. Predeclared M2 reference rotational case

Per the Milestone 3 brief: **`C_T = 0.08`** is adopted as the M3 reference
rotational case (`REFERENCE_C_T` in `electrical_sizing.py`), because it is
the middle Milestone 2 sensitivity case, it passes the Milestone 2
tip-Mach screen (static tip Mach 0.715 < `M_tip,max`=0.85), and gives
static RPM ~= 9298. `C_T = 0.12` is retained as an explicit sensitivity
case. **`C_T = 0.05` is retained, unerased, as the historically
tip-Mach-infeasible case** (static tip Mach 0.905 > 0.85) -- it is reported
in every script run but not used to build an electrical operating point,
since it never passed the Milestone 2 screen.

An emergent, notable property of this reduced-order model (not tuned, and
documented explicitly): required battery current/power at a fixed thrust
depend only on `P_shaft_est` (a function of thrust and disk area, from
Milestone 1) -- **not** on the assumed `C_T`. Changing `C_T` changes RPM,
torque, and tip Mach for the same thrust, but not the ideal/shaft power
or downstream electrical current. This is a direct consequence of RPM
being *inferred from* an assumed `C_T` rather than being a physically
independent input in this model (Section 14 of the Milestone 2
documentation).

## 23. Battery pack candidate rule and results

**Predeclared rule** (declared before evaluating any candidate;
`PACK_SELECTION_RULE_DESCRIPTION` in `electrical_sizing.py`): select the
lowest-voltage candidate pack, evaluated at the governing (static)
operating point, satisfying ALL of:

1. uses the Milestone 2 tip-Mach-feasible reference rotational case
   (`C_T = 0.08`);
2. motor rated electrical power exceeds required motor electrical power;
3. ESC continuous-current rating exceeds required battery current;
4. battery continuous-current capability exceeds required battery
   current;
5. required C-rate does not exceed the declared pack continuous C-rate;
6. all margins >= 0 (never clipped -- a negative margin is reported as a
   failing gate).

### Result (baseline assumptions: `eta_motor=0.90`, `eta_ESC=0.97`,
capacity=4.0 Ah, C-rate limit=20C, ESC I_max=100 A)

| Pack | V_nom [V] | V_full [V] | I_batt [A] (static) | C-rate | ESC margin | Battery-I margin | C-rate margin | All gates? |
|---|---|---|---|---|---|---|---|---|
| 12S | 44.4 | 50.4 | 88.48 | 22.12 | +0.130 | **-0.096** | **-0.096** | **NO** |
| 14S | 51.8 | 58.8 | 75.84 | 18.96 | +0.319 | +0.055 | +0.055 | yes (SELECTED) |
| 16S | 59.2 | 67.2 | 66.36 | 16.59 | +0.507 | +0.206 | +0.206 | yes |

**Selected conceptual electrical architecture: 14S** (the lowest-voltage
candidate satisfying every gate). 12S fails honestly (negative battery-
current and C-rate margins, not tuned away): at 4.0 Ah / 20C, its 80 A
continuous rating cannot support the required 88.48 A static current.

At a worst-case efficiency sensitivity (`eta_motor=0.85`, `eta_ESC=0.95`),
**only 16S remains feasible** -- 14S's margins turn negative (required
current rises to ~82.0 A against an 80 A battery limit at 4.0 Ah). This is
reported as a genuine finding illustrating margin fragility, not adjusted
away (see `scripts/electrical_sizing_study.py` output and
`tests/test_electrical_sizing.py::test_pack_selection_worst_case_sensitivity_only_16s_survives`).

Increasing pack capacity (e.g. to 6.0 or 8.0 Ah at fixed 20C) makes 12S
feasible too, since the derived continuous-current limit scales with
capacity -- demonstrating the basic capacity/C-rate trade without
changing the baseline-assumption selection.

## 24. Motor shaft-torque requirement (reference case, D = 0.50 m)

| Operating point | RPM | omega [rad/s] | Q = P_shaft/omega [N*m] |
|---|---|---|---|
| Static | 9298.3 | 973.7 | 3.522 |
| Cruise | 3001.0 | 314.3 | 2.017 |

Independently verified via `Q*omega` reconstruction
(`tests/test_motor.py::test_shaft_torque_reconstructs_power_independently`)
and cross-checked against `edf_sizing.rotational.angular_speed`
(`test_shaft_torque_matches_independent_omega_from_rotational_module`).
This torque requirement is useful context for future motor matching; no
winding current is derived from it (Section 19.4 -- Kv/Kt intentionally
omitted).

## 25. Verification approach (Milestone 3)

`tests/test_motor.py`, `tests/test_electrical.py`, `tests/test_battery.py`,
and `tests/test_electrical_sizing.py` implement independent checks
(hand-derived, not re-derived from the production formula), including:

- `P = V*I` hand calculations and its inverse (`I = P/V`); higher voltage
  gives lower current at fixed power.
- Motor/ESC power-chain hand calculations (`P_elec = P_shaft/eta_motor`,
  `P_batt = P_motor/eta_ESC`); lower efficiency increases downstream
  power/current (both stages).
- Shaft torque hand calculation and independent `omega` cross-check
  (`rotational.angular_speed`) and power reconstruction (`Q*omega =
  P_shaft`).
- Series-pack nominal and full-charge voltage hand calculations,
  cross-checked against the commonly cited "2S=7.4V, 3S=11.1V" reference;
  pack energy (Wh) hand calculation; C-rate hand calculation; higher
  capacity lowers required C-rate at fixed current.
- Rating-margin exact-boundary tests: margin exactly 0 at the rating
  boundary, positive just below, negative just above -- never clipped.
- Predeclared pack-selection-rule tests: 12S fails and is reported (not
  hidden), 14S is selected, a deliberately infeasible-ESC case is handled
  honestly (no forced selection), and the worst-case efficiency
  sensitivity correctly narrows the feasible set to 16S only.
- Regression: Milestone 1 static/cruise `P_shaft_est` values, the
  Milestone 2 `C_T=0.08` tip-Mach-feasible / `C_T=0.05`
  tip-Mach-infeasible classifications, and the Milestone 1 `D=0.50 m`
  selection are all unchanged.
- No double-counting of `eta_overall` (Section 20) -- both a numeric
  reconstruction check and a structural check that `motor.py` has no
  dependency on `efficiency.py`.
- No NaN/Inf across a full motor x ESC x pack sensitivity matrix (27
  combinations x 2 operating points).

**Final Milestone 3 test count: 79 new tests (202 total with Milestone
1/2's 123, all passing under `pytest -W error -q`).**

## 26. Explicit Milestone 3 limitations

- No electromagnetic motor model: winding resistance, back-EMF, and
  current-torque (Kt) relations are not modeled. `eta_motor` is a single
  bulk efficiency number.
- **Kv (motor speed constant) is deliberately omitted entirely** (Section
  19.4) -- no sourced, independently verifiable loaded-RPM-from-Kv
  relation could be built without inventing unsupported physics. This
  means Milestone 3 sizes power/current/torque but does NOT constrain or
  select a motor winding speed constant, and does not screen voltage/RPM
  compatibility via Kv.
- No motor or ESC thermal model.
- No battery electrochemical model (internal resistance, voltage sag
  under load, temperature effects, cycle life, aging) -- only Ah/Wh/V/
  C-rate bookkeeping per Section 19.3.
- No ESC switching-loss or PWM model -- `eta_ESC` is a single bulk
  efficiency number.
- No mission-energy or endurance model: `energy_Wh_nom` exists purely for
  electrical bookkeeping (Ah/Wh/C-rate), never for a flight-time claim.
- `eta_motor`, `eta_ESC`, motor/ESC current and power ratings, and the
  battery continuous C-rate limit are illustrative sensitivity
  assumptions, not sourced or manufacturer datasheet values.
- Because RPM (via the assumed `C_T`) does not feed back into
  `P_shaft_est`, required battery current/power is identical across the
  `C_T` sensitivity cases at a fixed thrust (Section 22) -- this is a
  property of the reduced-order model, not a physically matched
  propeller/motor/ESC performance map.
- No flight-qualified propulsion design, no manufacturer product
  recommendation, no real commercial motor/ESC/battery calibration.
- Milestone 1's `eta_overall = 0.75` remains an unrevisited placeholder
  (Section 4); Milestone 2's `M_tip_max`/`C_T` assumptions are unchanged.

## 27. Milestone 4 (recommended direction, not implemented here)

Not specified by this milestone's scope; to be defined based on portfolio
priorities (e.g. acoustic estimation, mission-energy/endurance modeling,
or a sourced reduced-order thermal check on the motor/ESC electrical
operating point established here).
