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

## 9. Milestone 2 (recommended direction, not implemented here)

Add blade-tip / fan-face velocity constraints and RPM sizing, including tip
Mach number and a sourced reduced-order fan pressure-rise / power-coefficient
model, while preserving this Milestone 1 momentum-theory baseline unchanged.
