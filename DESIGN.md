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

## 18. Milestone 3 (recommended direction, not implemented here)

Motor/ESC/electrical operating-point matching and battery-power
implications, using the Milestone 1/2 aerodynamic and rotational
requirements without changing them.
