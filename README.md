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

## Repository layout

```
src/edf_sizing/     # the package: requirements, actuator_disk, efficiency, sizing
tests/              # independent verification (pytest)
scripts/            # engineering scripts: run_sizing.py, make_figures.py
figures/            # generated portfolio figures (deterministic PNGs)
```

## Running it

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -W error -q
ruff check .
python3 scripts/run_sizing.py
python3 scripts/make_figures.py
```

## Milestone 2 (planned, not yet implemented)

Add blade-tip / fan-face velocity constraints and RPM sizing, including tip
Mach number and a sourced reduced-order fan pressure-rise / power-coefficient
model, while preserving the Milestone 1 momentum-theory baseline unchanged.
