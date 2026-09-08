# EDF Propulsion Sizing

A transparent, reduced-order electric ducted-fan (EDF) sizing model for a
**generic** UAV, built as a portfolio engineering study.

> **This is a conceptual, reduced-order study, not a manufacturer-calibrated
> propulsion model.** All aircraft/requirement numbers are illustrative and
> do not represent a real aircraft. No real commercial EDF unit is modeled
> or calibrated against.

## Status: Milestone 1

Milestone 1 implements only the actuator-disk / momentum-theory foundation:

- A generic representative UAV propulsion requirement (mass, fan count,
  cruise speed, air density, static/cruise thrust levels) with all
  assumptions explicit ([src/edf_sizing/requirements.py](src/edf_sizing/requirements.py)).
- Ideal 1-D actuator-disk (momentum theory) relations for static and axial
  forward-flight operation: thrust, induced velocity, ideal power, disk
  loading ([src/edf_sizing/actuator_disk.py](src/edf_sizing/actuator_disk.py)).
- A clearly separated, explicitly illustrative non-ideal efficiency
  bookkeeping layer to estimate shaft/electrical power
  ([src/edf_sizing/efficiency.py](src/edf_sizing/efficiency.py)).
- A candidate fan-diameter sweep, a predeclared conceptual selection rule,
  and a representative static/cruise thrust table for the selected fan
  ([src/edf_sizing/sizing.py](src/edf_sizing/sizing.py)).

See [DESIGN.md](DESIGN.md) for the full derivation, sources inspected, and
all explicit assumptions.

### Explicitly out of scope for Milestone 1

Blade-element theory, RPM selection, motor Kv selection, tip-Mach
constraints, duct pressure-recovery modeling, motor/controller sizing,
battery sizing, acoustic prediction, and any real commercial EDF
calibration. Ideal actuator-disk power is never called "motor power" --
see the efficiency layer for the one explicit, labeled conversion.

## Status: Milestone 2

Milestone 2 is additive on top of the frozen Milestone 1 baseline. It adds
rotational kinematics, blade-tip Mach constraints, and a reduced-order
nondimensional fan-loading framework:

- Pure rotational kinematics: RPM/rev-s, angular speed, blade-tip speed
  ([src/edf_sizing/rotational.py](src/edf_sizing/rotational.py)).
- Ambient speed of sound and static/relative (helical) blade-tip Mach
  number, plus an analytic tip-Mach-limited RPM ceiling (static and
  forward-flight) ([src/edf_sizing/compressibility.py](src/edf_sizing/compressibility.py)).
- A reduced-order actuator-disk pressure-jump estimate and the classical
  nondimensional thrust/power/advance-ratio coefficients (`C_T`, `C_P`,
  `J`), plus a derived RPM-from-`C_T` inversion
  ([src/edf_sizing/fan_loading.py](src/edf_sizing/fan_loading.py)).
- A combining module that builds static/cruise rotational operating
  tables and a full diameter x RPM x tip-Mach trade study for the
  Milestone 1 candidate sweep, reconciling whether Milestone 2 changes
  the Milestone 1 fan selection
  ([src/edf_sizing/rotational_study.py](src/edf_sizing/rotational_study.py)).

**Result:** the Milestone 1 selected D = 0.50 m fan is **not invalidated**
by Milestone 2 -- it passes the tip-Mach constraint under 2 of 3
illustrative thrust-coefficient (`C_T`) sensitivity cases (fails only the
most lightly-loaded case). Milestone 2 constrains the admissible RPM range
for the selected fan; it does not change the Milestone 1 diameter
selection. See [DESIGN.md](DESIGN.md), Milestone 2 sections, for the full
source audit, equations, sensitivity results, and limitations.

### Explicitly out of scope for Milestone 2

Blade-element theory, motor Kv selection, ESC/battery sizing, detailed
compressor maps, CFD, and any real commercial EDF calibration. `C_P` uses
the Milestone 1 illustrative estimated shaft power and is not a physically
matched propeller/fan performance map. The tip-Mach ceiling and `C_T`
sensitivity set are explicit illustrative assumptions, not sourced
universal EDF values.

## Status: Milestone 3

Milestone 3 is additive on top of the frozen Milestone 1/2 baseline. It
extends the aerodynamic/rotational requirement into a reduced-order
electrical (motor/ESC/battery) sizing model:

- Motor electrical-input power (`P_motor_elec = P_shaft_est / eta_motor`)
  and required shaft torque (`Q = P_shaft/omega`), building on the
  inherited Milestone 1 shaft-power estimate and Milestone 2 rotational
  kinematics ([src/edf_sizing/motor.py](src/edf_sizing/motor.py)).
- Generic electrical primitives (`P=VI`), an ESC efficiency/rating model,
  and a never-clipped rating-margin helper
  ([src/edf_sizing/electrical.py](src/edf_sizing/electrical.py)).
- A series-cell (xS) battery pack model using a sourced generic LiPo cell-
  voltage convention (3.7 V nominal / 4.2 V full-charge / 3.0 V minimum),
  pack energy, and C-rate
  ([src/edf_sizing/battery.py](src/edf_sizing/battery.py)).
- A combining module building full static/cruise electrical operating
  points, a predeclared battery-pack selection rule, and deterministic
  sensitivity studies
  ([src/edf_sizing/electrical_sizing.py](src/edf_sizing/electrical_sizing.py)).

**Result:** at the Milestone 2 reference rotational case (`C_T=0.08`),
the predeclared rule selects a **14S** conceptual pack -- the lowest-
voltage candidate whose motor/ESC/battery current and C-rate margins are
all non-negative at the baseline illustrative efficiencies (`eta_motor
=0.90`, `eta_ESC=0.97`). The 12S candidate fails honestly (negative
battery-current/C-rate margin at the 4.0 Ah baseline capacity) rather than
being tuned away. Electrical sizing does **not** invalidate the Milestone
1/2 D = 0.50 m fan choice or its admissible RPM region -- it adds a
downstream electrical architecture on top of the unchanged aerodynamic/
rotational requirement. See [DESIGN.md](DESIGN.md), Milestone 3 sections,
for the full source audit, equations, sensitivity results, and
limitations.

### Explicitly out of scope for Milestone 3

Detailed electromagnetic motor modeling, motor/ESC thermal models, battery
electrochemical modeling, ESC switching-loss modeling, mission-energy/
endurance modeling, and any real commercial motor/ESC/battery calibration
or product recommendation. Motor Kv is deliberately omitted entirely (no
sourced, independently verifiable loaded-RPM-from-Kv relation could be
built without inventing unsupported physics) -- Milestone 3 sizes power,
current, and torque, but not a motor winding speed constant.

## Repository layout

```
src/edf_sizing/     # requirements, actuator_disk, efficiency, sizing (M1)
                     # rotational, compressibility, fan_loading, rotational_study (M2)
                     # motor, electrical, battery, electrical_sizing (M3)
tests/              # independent verification (pytest)
scripts/            # run_sizing.py, make_figures.py (M1)
                     # rotational_fan_study.py, make_rotational_figures.py (M2)
                     # electrical_sizing_study.py, make_electrical_figures.py (M3)
figures/            # generated portfolio figures (deterministic PNGs)
```

## Running it

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -W error -q
ruff check .
python3 scripts/run_sizing.py
python3 scripts/make_figures.py
python3 scripts/rotational_fan_study.py
python3 scripts/make_rotational_figures.py
python3 scripts/electrical_sizing_study.py
python3 scripts/make_electrical_figures.py
```

## Milestone 4 (not yet defined)

Not specified by the current milestone scope; a candidate direction is a
sourced reduced-order thermal check on the motor/ESC electrical operating
point established in Milestone 3, or mission-energy/endurance modeling,
without changing the Milestone 1-3 requirements.
