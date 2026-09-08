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

## Repository layout

```
src/edf_sizing/     # requirements, actuator_disk, efficiency, sizing (M1)
                     # rotational, compressibility, fan_loading, rotational_study (M2)
tests/              # independent verification (pytest)
scripts/            # run_sizing.py, make_figures.py (M1)
                     # rotational_fan_study.py, make_rotational_figures.py (M2)
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
```

## Milestone 3 (planned, not yet implemented)

Motor/ESC/electrical operating-point matching and battery-power
implications, using the Milestone 1/2 aerodynamic and rotational
requirements without changing them.
