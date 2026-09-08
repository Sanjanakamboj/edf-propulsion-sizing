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

## 27. Milestone 3 status

Milestone 3 is complete and frozen as of commit `9719e44`. Milestone 4
(below) is purely additive: it imports and reuses Milestone 1-3
(`requirements.py`/`actuator_disk.py`/`efficiency.py`/`sizing.py`;
`rotational.py`/`compressibility.py`/`fan_loading.py`/`rotational_study.py`;
`motor.py`/`electrical.py`/`battery.py`/`electrical_sizing.py`) without
modifying any of them, and every Milestone 1-3 test, script, and figure
remains unchanged (see Section 33).

---

# Milestone 4 -- battery energy, mission-power integration, endurance screening

## 28. Source audit (inspected before writing any M4 energy physics)

1. **Elementary electrical energy** (standard physics, restated):
   `E = integral(P dt)`, which for a constant-power segment reduces to
   `E_J = P_W * t_s`; the exact conversion `1 Wh = 3600 J` (since
   1 W = 1 J/s and 1 hour = 3600 s). These are the two equations
   implemented in `src/edf_sizing/energy.py::segment_energy_J` and
   `joules_to_Wh`.
2. **Battery specific energy for electric aircraft** (NASA feasibility/
   scaling studies, search-corroborated): a NASA all-electric
   150-passenger-aircraft feasibility study assumes a **usable** battery
   energy density of ~300 Wh/kg (large, full-scale-aircraft pack, not
   representative of small UAV LiPo hardware); a NASA AIAA "Battery
   Cell-to-Pack Scaling Laws for Electric Aircraft" analysis (NTRS
   20210009584), corroborated via aggregated search summary, reports the
   NASA X-57 Maxwell lithium-ion cells at **225 Wh/kg** and the complete
   battery **pack** at **149 Wh/kg** (~66% of cell-level specific energy
   retained after packaging). Direct PDF text extraction of the primary
   NTRS/ICAS documents was inconclusive (heavily compressed/embedded-font
   PDFs); the 225/149 Wh/kg figures are reported via the search engine's
   synthesized summary of that document and are used here only as an
   order-of-magnitude anchor for a small-UAV pack-level specific-energy
   sensitivity range, NOT as a value directly measured from the source
   text by this project.
3. **Depth of discharge / usable-capacity convention** (search-corroborated
   across multiple battery-technical references, e.g. Wikipedia "Depth of
   discharge", solaxpower.com, lithiumbatterytech.com): manufacturers
   typically warrant 80-95% depth-of-discharge (DoD) for high-quality
   LiFePO4 cells; DoD/usable-capacity conventions are chemistry- and
   product-specific, and **no single universal usable-fraction value
   applies across all lithium battery chemistries or all UAV
   applications**. Electric-aircraft-specific reserve-energy concepts
   (a dedicated reserve energy system for diversion/loiter/go-around) are
   also noted in the NASA feasibility-study search results, corroborating
   that a separate reserve allowance (distinct from usable-fraction
   de-rating) is standard aviation practice, without prescribing a
   specific fraction for this generic reduced-order study.

**No credible universal usable-energy fraction, reserve fraction, or
UAV-specific battery specific-energy value was found.** All three are
therefore explicit, illustrative sensitivity parameters (Section 30),
matching the Milestone 4 brief's explicit instruction not to invent a
universal number.

## 29. Freeze of Milestone 1-3 and consumption convention

Milestone 4 does not modify `actuator_disk.py`, `rotational.py`/
`compressibility.py`, or `motor.py`/`electrical.py`/`battery.py`/
`electrical_sizing.py`. It consumes Milestone 3's `ElectricalOperatingPoint
.battery_power_W` (the per-fan battery-input power, itself already the end
of the M1-M3 chain `Pi -> P_shaft_est -> P_motor_elec -> P_battery`)
directly, via `m3_reference_battery_powers()` in
`src/edf_sizing/mission_sizing.py`, and never re-derives shaft, motor, or
battery power with a new convention.

**Important modeling note on current vs. energy scope** (see also Section
31): Milestone 3's battery CURRENT/C-rate screening is evaluated per-fan
(one motor/ESC/battery circuit) and is frozen exactly as committed.
Milestone 4's mission ENERGY, per the Milestone 4 brief's explicit
instruction ("total battery power uses both fans"), is evaluated at the
whole-aircraft level (per-fan power x `n_fans` = 2). A single candidate
pack is therefore screened against two conventions that are not perfectly
architecturally unified (per-fan current vs. whole-aircraft energy) --
this is a deliberate, documented modeling simplification, not a silently
introduced inconsistency (Section 34).

## 30. Mission profile, energy equations, reserve/usable-energy convention

Implemented in `src/edf_sizing/mission.py` (segment model),
`src/edf_sizing/energy.py` (equations), and
`src/edf_sizing/mission_sizing.py` (predeclared profile + combining logic).

**Predeclared, illustrative, generic mission profile** (declared before
any energy was computed):

| Segment | Duration | Power | Label |
|---|---|---|---|
| launch | 30 s | M3 static battery power, unmodified | -- |
| climb | 120 s | 0.70 x M3 static battery power | ILLUSTRATIVE fraction |
| cruise | 1200 s (20 min) | M3 cruise battery power, unmodified | -- |
| loiter | 300 s (5 min) | 1.20 x M3 cruise battery power | ILLUSTRATIVE fraction |

No new aerodynamic power level is invented -- every segment power is
either an unmodified M3 static/cruise battery power or an explicit,
labeled multiple of one. Reserve is handled as a separate energy margin
(Section on reserve below), not as a fake flight segment.

**SOURCED equations:**

```
E_segment,J = P_segment,total_W * duration_s
E_segment,Wh = E_segment,J / 3600
E_mission = sum(E_segment)
```

**DERIVED reserve/usable-energy chain** (kept distinct, never
double-counted):

```
E_required_Wh         = E_mission_Wh * (1 + reserve_fraction)
E_nominal_required_Wh = E_required_Wh / usable_fraction
Capacity_required_Ah  = E_nominal_required_Wh / V_pack_nom
```

**ILLUSTRATIVE baseline assumptions** (Section 28 -- no universal value
sourced): `reserve_fraction = 0.20` (sensitivity `{0.10, 0.20, 0.30}`),
`usable_fraction = 0.80` (sensitivity `{0.70, 0.80, 0.90}`).

## 31. Milestone 4 results

### 31.1 Mission energy

| Segment | Duration | Total power [W] | Energy [Wh] | % of mission |
|---|---|---|---|---|
| launch | 30 s | 7857.3 | 65.48 | 7% |
| climb | 120 s | 5500.1 | 183.34 | 21% |
| cruise | 1200 s | 1452.2 | 484.07 | **55%** |
| loiter | 300 s | 1742.7 | 145.22 | 17% |

**Raw mission energy = 878.11 Wh.** The cruise segment dominates mission
energy (55%) despite having the lowest instantaneous power of any powered
segment -- a direct consequence of its long duration, not high power.

Reserve-adjusted (x1.20): **1053.73 Wh**. Required nominal (÷0.80):
**1317.16 Wh**. Required Ah at 14S (51.8 V): **25.43 Ah**.

### 31.2 M3 4.0 Ah baseline pack: current vs. energy screens

| Screen | Result |
|---|---|
| Current/C-rate (M3 convention, frozen) | **PASS** (75.84 A, C-rate 18.96 <= 20C) |
| Mission energy (M4) | **FAIL** (165.8 Wh usable vs. 1053.7 Wh required) |
| Overall | **FAIL** |

This is the central Milestone 4 finding requested by the brief: the same
4.0 Ah/14S pack that satisfied Milestone 3's instantaneous current
screen is drastically undersized for the representative mission's energy
demand -- current feasibility and energy feasibility are independent
questions, and a pack can (and here does) pass one while failing the
other.

### 31.3 Capacity trade at 14S (predeclared rule, Section 30)

> Select the smallest candidate capacity (from `{4, 8, 12, 16, 20, 24, 28,
> 32} Ah`) that satisfies BOTH the M3 current/C-rate screen AND the M4
> mission-energy requirement.

| Capacity [Ah] | Usable Wh | Current OK? | Energy OK? | Overall |
|---|---|---|---|---|
| 4-24 | 165.8-994.6 | yes | **NO** | NO |
| **28** | 1160.3 | yes | **yes** | **SELECTED** |
| 32 | 1326.1 | yes | yes | yes |

**Selected conceptual pack: 14S, 28.0 Ah** (1450.4 Wh nominal). Capacity
margin +0.101, current margin +6.384 (governing constraint is energy, not
current).

### 31.4 Voltage trade (12S/14S/16S carried forward from Milestone 3)

| Pack | V_nom | Selected candidate Ah | Nominal Wh | Exact required Ah | Static I [A] |
|---|---|---|---|---|---|
| 12S | 44.4 V | 32.0 | 1420.8 | 29.67 | 88.48 |
| 14S | 51.8 V | 28.0 | 1450.4 | 25.43 | 75.84 |
| 16S | 59.2 V | 24.0 | 1420.8 | 22.25 | 66.36 |

**Does mission-energy sizing preserve the Milestone 3 14S selection?**
Answered honestly, with an important nuance:

- Required nominal energy (Wh) is **voltage-invariant** in this model --
  only required Ah scales inversely with voltage (energy content
  depends on Wh, not on the arbitrary choice of series count). The small
  differences in the "Nominal Wh" column above are a **discretization
  artifact** of the predeclared discrete capacity grid (12S and 16S both
  happen to round to 1420.8 Wh; 14S rounds to a slightly higher 1450.4 Wh
  purely because its exact requirement, 25.43 Ah, sits closer to the
  bottom of its candidate step), not a genuine electrical difference.
- Applying the M3-style "prefer lowest voltage among feasible candidates"
  tiebreak mechanically selects **12S** (`matches_m3_selection = False`
  in `evaluate_voltage_carry_forward`).
- **However**, this mechanical result is driven entirely by resizing
  capacity for the energy requirement: at the much larger capacity now
  required (~22-30 Ah, vs. Milestone 3's 4.0 Ah baseline), 12S's
  battery continuous-current/C-rate limitation -- the specific reason
  Milestone 3 rejected it -- disappears, because continuous-current
  capability scales with capacity while the underlying required current
  (88.48 A) does not change. **All three candidate voltages become fully
  current-feasible once capacity is sized for the mission.**
- Given the exact energy tie and the marginal, grid-driven nature of the
  mechanical 12S result, this project **retains 14S as the recommended
  conceptual architecture** (the mechanical tiebreak is reported
  transparently above, but is not treated as a decisive engineering
  reason to change the previously committed pack voltage). Either
  reading is defensible; both are reported rather than silently
  resolved in one direction.

### 31.5 Sensitivity summary (see `scripts/mission_energy_study.py` for
full numeric output)

| Factor | Effect on required nominal Wh |
|---|---|
| Cruise duration 600/1200/1800 s | 954.1 / 1317.2 / 1680.2 Wh (linear) |
| Climb duration 60/120/180 s | 1179.7 / 1317.2 / 1454.7 Wh |
| Usable fraction 0.70/0.80/0.90 | 1505.3 / 1317.2 / 1170.8 Wh |
| Reserve fraction 0.10/0.20/0.30 | 1207.4 / 1317.2 / 1426.9 Wh |

**Strongest sensitivity: cruise duration** -- it has both the largest
absolute range across its sensitivity set and, being multiplied through
the whole reserve/usable chain, the largest effect on required nominal
Wh per unit change in the underlying assumption (mission energy scales
exactly linearly with cruise duration, since cruise dominates total
mission energy at 55%).

### 31.6 Battery mass proxy (illustrative specific energy)

| Specific energy [Wh/kg] | Mass proxy [kg] |
|---|---|
| 150 | 8.78 |
| 200 (baseline) | 6.59 |
| 250 | 5.27 |

Labeled explicitly as a **"cell/pack-level battery mass proxy"** --
`m_batt = E_nominal_required_Wh / specific_energy_Wh_per_kg`, with no
packaging/BMS/interconnect overhead beyond whatever is implicit in the
chosen specific-energy basis (Section 28.2).

### 31.7 Cruise-only energy diagnostic (RESTRICTED USE)

`t_cruise_equiv = E_usable / P_battery,cruise,total` = **0.80 h** at the
selected 28 Ah/14S pack. This is a **cruise-only constant-power energy
diagnostic ONLY** -- it is explicitly NOT a range, flight-endurance, or
mission-duration-capability claim, and is never combined with the actual
segmented mission calculation.

## 32. Verification approach (Milestone 4)

`tests/test_mission.py`, `tests/test_energy.py`, and
`tests/test_mission_sizing.py` implement independent checks (hand-derived,
not re-derived from the production formula), including:

- `E = P*t` hand calculations; exact J->Wh conversion (`1 Wh = 3600 J`);
  multi-segment mission sum; fan-count multiplication; zero-duration
  segment gives exactly zero energy.
- Reserve-energy and usable-energy-inversion hand calculations, kept
  algebraically distinct (never double-counted); higher reserve fraction
  and lower usable fraction both increase required nominal energy.
- Required-Ah hand calculation; Ah x V reconstructs Wh; higher pack
  voltage lowers required Ah at fixed Wh.
- Capacity-margin exact-zero-boundary test, plus below/above-capacity
  pass/fail tests.
- Explicit demonstration that current and energy screens are
  independent: the M3 4.0 Ah/14S pack passes current but fails energy;
  a deliberately undersized ESC at a large (32 Ah) capacity passes energy
  but fails current.
- Regression: Milestone 1 static/cruise battery power, Milestone 2
  reference RPM/tip-Mach classification, and Milestone 3's 14S static
  current/C-rate values are all reproduced exactly.
- Battery-mass hand calculation and specific-energy monotonicity
  (higher specific energy -> lower mass).
- No NaN/Inf across the full voltage x capacity sensitivity matrix (3
  voltages x 8 capacities = 24 combinations).

**Final Milestone 4 test count: 58 new tests (260 total with Milestone
1-3's 202, all passing under `pytest -W error -q`).**

## 33. Milestone 1-3 preservation confirmation

All Milestone 1-3 source files (`requirements.py`, `actuator_disk.py`,
`efficiency.py`, `sizing.py`, `rotational.py`, `compressibility.py`,
`fan_loading.py`, `rotational_study.py`, `motor.py`, `electrical.py`,
`battery.py`, `electrical_sizing.py`), their tests, their scripts
(`run_sizing.py`, `make_figures.py`, `rotational_fan_study.py`,
`make_rotational_figures.py`, `electrical_sizing_study.py`,
`make_electrical_figures.py`), and all 11 previously committed figures
are byte-for-byte unchanged by Milestone 4 (verified via `git diff --stat`
showing zero changes to any of these paths, and figure-hash comparison
before/after the full 16-figure regeneration).

## 34. Explicit Milestone 4 limitations

- No trajectory/aircraft-performance simulation: a mission segment is
  exactly `constant electrical power x duration`, with no
  speed/altitude/acceleration dynamics.
- No detailed battery electrochemistry, no battery thermal model, no
  voltage-sag-under-load model, no battery aging/cycle-life model.
- No motor thermal model (unchanged from Milestone 3).
- No dispatch/reliability analysis.
- The cruise-only energy diagnostic (Section 31.7) is explicitly
  restricted to that single use -- it must never be read as range,
  endurance, or mission-duration capability.
- Mission segment durations (30 s / 120 s / 1200 s / 300 s), the climb
  and loiter power fractions (0.70x static, 1.20x cruise), the reserve
  fraction, the usable-energy fraction, and the specific-energy
  sensitivity values are all illustrative, generic assumptions -- not
  derived from or claimed to represent any real aircraft or mission.
- The per-fan current (Milestone 3) vs. whole-aircraft energy (Milestone
  4) scope mismatch (Section 29) is a deliberate modeling simplification
  per the Milestone 4 brief's own instructions, not a physically unified
  single-architecture model.
- The voltage carry-forward "preferred" result (Section 31.4) is
  reported both mechanically (12S, via a literal lowest-voltage tiebreak)
  and with the deeper engineering caveat that it is a near-exact tie
  driven by capacity-grid discretization -- neither reading should be
  treated as a strong, decisive result.
- Battery mass (Section 31.6) is a cell/pack-level proxy only; it
  includes no airframe integration, wiring, connector, or BMS mass beyond
  whatever the chosen specific-energy basis implicitly assumes.

## 35. Milestone 4 status

Milestone 4 is complete and frozen as of commit `806766f`. Milestone 5
(below) is purely additive: it imports and reuses Milestone 1-4
(`requirements.py`/`actuator_disk.py`/`efficiency.py`/`sizing.py`;
`rotational.py`/`compressibility.py`/`fan_loading.py`/`rotational_study.py`;
`motor.py`/`electrical.py`/`battery.py`/`electrical_sizing.py`;
`mission.py`/`energy.py`/`mission_sizing.py`) without modifying any of
them, and every Milestone 1-4 test, script, and figure remains unchanged
(see Section 41).

---

# Milestone 5 -- duct/fan efficiency sensitivity and thrust lapse

## 36. Source audit (inspected before writing any M5 aerodynamic-loss model)

1. **Ducted-fan performance and duct-loss context** (NASA NTRS "Performance
   Study of a Ducted Fan System", Abrego/Ames Research Center; NASA NTRS
   "Experimental Characterization of an Electric Ducted Fan", Weinstein
   et al., SciTech 2024; search-corroborated). Confirms that duct
   geometry has a significant effect on rotor velocity/pressure and hence
   propulsive efficiency, and that non-dimensional total-pressure/total-
   efficiency quantities are not strongly sensitive to specific inlet/
   outlet ducting geometry -- corroborating that a single lumped
   thrust-effectiveness number is a defensible reduced-order
   simplification for a conceptual study, without claiming any specific
   duct geometry's performance.
2. **Static vs. design-point efficiency** (mh-aerotools.de "Static Thrust
   of Propellers", a propeller-performance reference restating classical
   results). States that propellers/fans typically achieve only ~50% or
   less of theoretically predicted static thrust (due to flow separation/
   distortion) versus 80-90% efficiency at design-point (cruise-like)
   conditions -- corroborating that a lumped thrust-effectiveness factor
   below 1.0 is physically reasonable, and informing (not fixing) the
   Section 38 illustrative `eta_T` sensitivity range.
3. **Forward-flight thrust lapse with advance ratio** (search-corroborated
   across multiple propeller-literature sources, e.g. commons.erau.edu
   propeller-thrust-equation reference, mh-aerotools.de propeller
   aerodynamic-characteristics page): confirms the qualitative SOURCED
   trend that propeller/fan thrust decreases as advance ratio (forward
   speed relative to rotational speed) increases, for a fixed rotational
   operating point -- "thrust lapse". **No compact, universal,
   source-verified EDF thrust-lapse curve or coefficient was found**, so
   Milestone 5 implements a transparent, explicitly ILLUSTRATIVE
   parametric model (Section 39) rather than fitting to any specific
   published curve, per the Milestone 5 brief's explicit fallback
   instruction.
4. **Figure of merit / actual-vs-ideal actuator-disk thrust ratio**
   (search-corroborated, e.g. ScienceDirect "Ideal Actuator Disc"
   overview, academic figure-of-merit references): confirms the general
   concept that real rotors never achieve the actuator-disk theoretical
   maximum thrust/efficiency for a given power and diameter -- the
   conceptual basis for the Section 37 `eta_T` thrust-effectiveness
   factor, again without a single universal numeric value.

**No credible universal EDF thrust-lapse curve, duct-loss coefficient, or
fan-effectiveness value was found.** `eta_T` and the thrust-lapse
coefficient/reference speed are therefore explicit, illustrative,
deterministic sensitivity parameters (Section 38), never sourced design
values for any real EDF unit.

## 37. Non-ideal thrust-effectiveness model

Implemented in `src/edf_sizing/duct_losses.py`. The Milestone 1 ideal
actuator-disk relation is completely unchanged; this module adds a
separate, downstream, multiplicative factor:

```
T_static_available = eta_T * T_ideal_reference
```

`eta_T` lumps fan aerodynamic losses, duct/inlet losses, flow
nonuniformity, and other unmodeled installation effects into a single
number (ILLUSTRATIVE, Section 36.2/36.4). It is deliberately **not**
applied to power -- thrust effectiveness and power efficiency
(`eta_motor`/`eta_ESC`, Milestone 3, unchanged) are kept strictly
distinct.

## 38. Thrust-lapse model

Implemented in `src/edf_sizing/thrust_lapse.py`, per the Section 7
formula of the Milestone 5 brief:

```
T_available(V) = T_static_available * f_lapse(V)
f_lapse(0) = 1,  0 <= f_lapse(V) <= 1
```

Two ILLUSTRATIVE parametric forms are implemented (Section 36.3 -- no
sourced universal curve exists):

- **Baseline (linear)**: `f_lapse(V) = max(0, 1 - k*(V/V_ref))`,
  `k = 0.30`, `V_ref = 60.0 m/s` (chosen as 2x the Milestone 1 cruise
  speed, purely for a convenient normalization -- illustrative, not
  sourced).
- **Alternative (quadratic) sensitivity**: `f_lapse(V) = max(0, 1 -
  k*(V/V_ref)^2)`, same `k` and `V_ref` for comparability.

Crucially, per the brief's Section 7 formula, the SAME
`T_static_available` (from Section 37, at `V=0`) is lapsed with speed --
Milestone 1's separately-computed forward-flight "ideal" cruise thrust
(15.32 N) remains a REQUIRED value only, and is never re-scaled by
`eta_T` or the lapse factor on the available-thrust side. This
distinction matters: an earlier implementation draft mistakenly applied
`eta_T` to the M1 cruise-ideal-reference thrust and then lapsed *that*,
which silently reproduced a shortfall at the cruise point that the
brief's formula does not predict; the corrected implementation (matching
Section 7 literally) shows cruise passing with a very large margin, since
the available-thrust curve is anchored to the much larger static
reference. This is documented as a self-caught modeling correction, not
a historical-result change (no committed M1-M4 value was affected).

## 39. RPM recovery (DERIVED, within the frozen M2 fixed-C_T convention)

Implemented in `src/edf_sizing/performance_envelope.py`. Using the
Milestone 2 fixed-C_T convention `T ~ n^2` (unchanged):

```
RPM_required = RPM_reference / sqrt(eta_T)
```

compared against the Milestone 2 tip-Mach RPM ceiling
(`compressibility.max_rpm_static`, unchanged). Verified independently:
substituting `RPM_required` back into `eta_T * (RPM_required/
RPM_reference)^2` reconstructs exactly `1.0` (i.e. the thrust deficit is
exactly restored), for every `eta_T` tested.

The corresponding power penalty follows the frozen Milestone 2 fixed-C_P
convention `P ~ n^3` (unchanged):

```
power_ratio = (RPM_required / RPM_reference)^3
```

Note `power_ratio = eta_T^(-3/2)` while the thrust-recovery ratio is only
`eta_T^(-1)` at the RPM level and exactly `1` in delivered thrust --
i.e. the power penalty of RPM-based recovery grows faster than the
thrust shortfall it corrects (verified in the engineering sanity audit,
Section 42).

## 40. Milestone 5 results

### 40.1 Predeclared baseline case (declared before evaluating results)

`eta_T = 0.90` (ILLUSTRATIVE baseline; sensitivity `{0.80, 0.90, 1.00}`,
plus a supplementary stress case `eta_T = 0.65` used only to demonstrate
the RPM-ceiling infeasibility boundary). Baseline lapse model: linear,
`k=0.30`, `V_ref=60 m/s` (Section 38).

### 40.2 Static thrust (D = 0.50 m, reference static RPM = 9298.3)

| Quantity | Value |
|---|---|
| Required | 147.10 N |
| Available at baseline (reference) RPM | 132.39 N |
| Margin | -14.71 N (**-10.0%, FAILS honestly**) |
| RPM required for recovery | 9801.3 |
| M2 tip-Mach RPM ceiling (`M_tip,max=0.85`) | 11048.5 |
| Recovery feasible? | **Yes** (headroom: 1247 RPM) |
| Tip Mach at recovery | 0.754 (< 0.85 ceiling) |
| Power ratio at recovery | 1.1712 (+17.1% shaft power) |

**The unmodified Milestone 1 static sizing does NOT close under the
baseline `eta_T=0.90` assumption** -- reported honestly, not tuned away.
RPM recovery within the Milestone 2 tip-Mach ceiling closes the gap.

### 40.3 Cruise thrust (V_inf = 30 m/s)

| Quantity | Value |
|---|---|
| Required | 15.32 N |
| Available (baseline eta_T=0.90, lapsed from static-available) | 112.53 N |
| Margin | +97.21 N (**+634%, PASSES with large margin**) |

Cruise passes comfortably at every `eta_T` sensitivity case tested,
because the available-thrust curve is anchored to the much larger static
reference thrust (Section 38) -- the aircraft's cruise thrust requirement
is a small fraction of the fan's forward-flight thrust capability even
after lapse.

### 40.4 Electrical consequence of RPM-based recovery (14S/28Ah, baseline eta_T)

| Quantity | Value |
|---|---|
| Reference shaft power | 3429.7 W |
| Recovered shaft power | 4016.9 W (+17.1%) |
| Motor electrical power | 4463.3 W |
| Battery power | 4601.3 W |
| Battery current | 88.83 A |
| C-rate (28 Ah pack) | 3.17 |
| ESC margin (100 A rating) | +0.126 (**ok**) |
| Battery current margin (28 Ah @ 20C) | +5.304 (**ok**) |

### 40.5 Mission-energy consequence (new M5 off-design profile; M4 baseline untouched)

| Quantity | Value |
|---|---|
| M4 baseline mission energy | 878.11 Wh |
| M5 updated mission energy (static+climb use recovered power) | 920.71 Wh (+4.9%) |
| 28 Ah pack usable energy | 1160.32 Wh |
| Required (reserve-adjusted) | 1104.83 Wh |
| Capacity margin | +0.050 (**ok**, down from M4's +0.101) |

### 40.6 Overall feasibility (predeclared rule, Section on Milestone 5
performance envelope)

| eta_T | Static via recovery | Cruise | Current OK | Energy OK | **Overall** |
|---|---|---|---|---|---|
| 1.00 | yes (trivially) | yes | yes | yes | **FEASIBLE** |
| 0.90 (baseline) | yes | yes | yes | yes | **FEASIBLE** |
| 0.80 | yes (RPM ceiling OK) | yes | **NO** | **NO** | **INFEASIBLE** |
| 0.65 (stress) | **NO** (exceeds ceiling) | yes | NO | NO | **INFEASIBLE** |

**At the predeclared baseline (`eta_T=0.90`), the full M1-M5 chain
closes: the 0.50 m fan, the M2 tip-Mach constraint, the M3 14S electrical
architecture, and the M4 28 Ah battery capacity all remain viable**, but
only via off-design RPM recovery -- the raw (non-recovered) static margin
is honestly negative. **At the `eta_T=0.80` sensitivity extreme, the
architecture fails** -- not because RPM recovery itself is infeasible
(it stays within the tip-Mach ceiling), but because the resulting
electrical current exceeds the ESC rating and the resulting mission
energy exceeds the 28 Ah pack's margin, simultaneously. This is a
genuine, non-tuned finding: **electrical and energy margins, not the
rotational/tip-Mach constraint, are the binding failure mode as thrust
effectiveness degrades further from the baseline.**

### 40.7 Sensitivity summary

| Factor | Effect |
|---|---|
| `eta_T` {1.00, 0.90, 0.80, 0.65} | Governs feasibility outcome (Section 40.6) |
| Lapse model (linear vs. quadratic, same k) | Quadratic gives higher cruise-available thrust (122.5 N vs. 112.5 N) -- cruise passes either way with large margin |
| `M_tip,max` {0.75, 0.85, 0.95} (at stress `eta_T=0.80`) | Ceiling 9748.7 / 11048.5 / 12348.3 RPM; recovery infeasible only at the strictest 0.75 ceiling |
| `eta_motor` {0.85, 0.90, 0.95} | Recovered current 94.05 / 88.83 / 84.15 A -- all remain ESC/battery-feasible at baseline `eta_T` |
| `eta_ESC` {0.95, 0.97, 0.99} | Recovered current 90.70 / 88.83 / 87.03 A -- all feasible at baseline `eta_T` |
| Pack voltage (14S/28Ah vs. 16S/24Ah) | 16S draws less current (77.72 A vs. 88.83 A) and keeps a smaller but still positive energy margin (+0.029) |
| Diameter (0.45/0.50/0.55/0.60 m) | Tip-Mach RPM ceiling only reported (12276/11048/10044/9207 RPM) -- M1 diameter selection is NOT re-opened |

## 41. Milestone 1-4 preservation confirmation

All Milestone 1-4 source files, their tests, their scripts, and all 16
previously committed figures are byte-for-byte unchanged by Milestone 5
(verified via `git diff --stat` showing zero changes to any of these
paths, and figure-hash comparison before/after the full 21-figure
regeneration).

## 42. Verification approach and engineering sanity audit (Milestone 5)

`tests/test_duct_losses.py`, `tests/test_thrust_lapse.py`, and
`tests/test_performance_envelope.py` implement independent checks
(hand-derived, not re-derived from the production formula), including:

- Thrust-effectiveness hand calculation; `eta_T=1` exactly reproduces the
  ideal reference thrust; lower `eta_T` monotonically lowers available
  thrust.
- Lapse-function boundary (`f(0)=1` for both linear and quadratic forms),
  bounded-in-[0,1] checks over a wide speed range, and a hand-derived
  available-thrust calculation.
- RPM-recovery exact-formula hand check; independent `T~RPM^2`
  round-trip verification that the recovered RPM restores exactly 100%
  of the reference thrust; `P~RPM^3` power-scaling hand check;
  exact-boundary RPM-ceiling test (feasible at/just-below, infeasible
  just-above).
- Electrical propagation hand calculation (reusing Milestone 3
  primitives directly) and an exact-zero current-margin boundary test.
- Mission-energy-penalty hand calculation, and confirmation that
  evaluating an M5 case never mutates the M4 baseline `MissionProfile`
  object.
- Full-envelope integration tests reproducing the four feasibility rows
  of Section 40.6 exactly (`eta_T` = 1.00 fully feasible, 0.90 feasible
  via recovery, 0.80 fails electrical+energy, 0.65 fails the RPM
  ceiling).
- Regression: Milestone 1 static/cruise thrust requirements, Milestone 2
  reference RPM/tip-Mach and tip-Mach RPM ceiling, Milestone 3 baseline
  efficiencies, and Milestone 4 baseline mission energy are all
  reproduced exactly.
- No NaN/Inf across the full `eta_T` sensitivity grid (including the
  stress case).

Explicitly re-verified (engineering sanity audit): `eta_T=1` reproduces
historical thrust; available thrust falls monotonically as `eta_T`
falls; the baseline lapse gives `f(0)=1` and is non-increasing in `V`;
RPM recovery increases as `eta_T` decreases; the power penalty
(`eta_T^-1.5`) rises faster than the RPM-level recovery ratio
(`eta_T^-1`); tip Mach rises with recovery RPM; no recovery case silently
exceeds the tip-Mach ceiling (infeasible cases are flagged, not
clamped); battery current rises with recovered power; and evaluating any
M5 case leaves the M4 baseline mission profile, and all M1-M4 committed
values, byte-for-byte unchanged.

**Final Milestone 5 test count: 58 new tests (318 total with Milestone
1-4's 260, all passing under `pytest -W error -q`).**

## 43. Explicit Milestone 5 limitations

- Not blade-element momentum theory, not CFD, not a compressor-map
  simulation, not inlet-distortion modeling, not detailed duct
  aerodynamics, not a real fan-map calibration.
- `eta_T` is a single lumped thrust-effectiveness number; it does not
  separate fan aerodynamic loss from duct/inlet loss (Section 37) --
  no physically defensible basis for that decomposition was found in the
  source audit, so no `eta_fan * eta_duct` product is used.
- The thrust-lapse model (linear or quadratic) is an explicitly
  ILLUSTRATIVE parametric form, not fit to or validated against any real
  EDF or propeller thrust-lapse curve.
- No continuous aircraft drag polar is modeled -- only the static and
  cruise operating points are treated as thrust requirements; the
  available-thrust-vs-airspeed curve (Figure 17) is a bookkeeping
  envelope for the installed fan, not an aircraft performance curve.
- RPM recovery and its power/electrical/energy consequences use the
  frozen Milestone 2/3/4 fixed-coefficient conventions (`T~n^2`,
  `P~n^3`, `eta_motor`, `eta_ESC`) exactly as committed -- no new
  electromagnetic, thermal, or blade-element physics is introduced.
- The Milestone 5 off-design mission-energy profile (Section 40.5)
  applies the recovered static/climb battery power only to the
  static/climb segments; cruise/loiter are carried forward unmodified
  from Milestone 3/4 because they pass the thrust-lapse screen without
  needing recovery at the baseline `eta_T` -- this is a scope choice, not
  a claim that cruise/climb power is unaffected by `eta_T` in general.
- No motor/ESC thermal model, no battery electrochemistry, no aircraft
  trajectory simulation (unchanged from prior milestones).

## 44. Milestone 6 (recommended direction, not implemented here)

Final robustness audit and portfolio synthesis across Milestones 1-5,
including independent verification, a concise final operating-envelope
summary, and clean-environment reproducibility, without changing
historical physics.
