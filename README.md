# EDF Propulsion Sizing

A from-scratch, fully-verified reduced-order sizing chain that answers one
question for a generic small UAV: **starting from nothing but actuator-disk
momentum theory, what fan diameter, RPM, battery pack, and mission-energy
capacity does a twin electric-ducted-fan propulsion system need — and does
that architecture survive realistic thrust losses and forward-flight
lapse?**

> **This is a conceptual, reduced-order portfolio study, not a
> manufacturer-calibrated or flight-qualified propulsion model.** All
> aircraft/requirement numbers are illustrative and do not represent a real
> aircraft. No real commercial EDF, motor, ESC, or battery product is
> modeled or calibrated against.

## Final engineering conclusion

1. **M1** (actuator-disk momentum theory) selects a **D = 0.50 m** fan by a
   predeclared disk-loading/ideal-power rule.
2. **M2** (rotational kinematics + tip-Mach) constrains admissible RPM but
   leaves the M1 diameter unchanged — smaller diameters spin faster than
   the tip-Mach ceiling allows.
3. **M3** (motor/ESC/battery) selects a **14S** electrical architecture —
   the lowest-voltage candidate whose current/C-rate margins are positive.
4. **M4** (mission energy) drives battery capacity from M3's 4.0 Ah
   baseline up to **28.0 Ah** — the 4.0 Ah pack passes M3's instantaneous
   current screen but fails the mission-energy requirement outright.
5. **M5** (thrust-effectiveness + forward-flight lapse) shows that at an
   illustrative `eta_T=0.90`, the *unmodified* M1 static sizing does **not**
   close (-10.0% shortfall) — but RPM-based recovery, still within the M2
   tip-Mach ceiling, restores it exactly, and the resulting current/energy
   penalties both fit inside the M3/M4 architecture (with thinner margins).
6. **eta_T=0.80 breaks it** — RPM recovery itself is still fine, but the
   resulting current exceeds the ESC rating *and* the energy margin goes
   negative, simultaneously. A genuine, non-tuned failure mode.
7. **M6** (final robustness audit) independently re-derives every headline
   number from raw formulas (32/32 checks pass, max residual ~1e-13),
   quantifies exactly how much margin is left at baseline, and computes —
   not asserts — which assumption the whole chain is most sensitive to.

**Final robustness margin is sensitivity-dependent: the baseline
architecture is feasible with positive margins on every gate, but the
tightest of them (mission cruise duration) has only ~9.5% headroom.** See
[RESULTS.md](RESULTS.md) for the full numbers.

## Key numbers

| Quantity | Value |
|---|---|
| Selected fan diameter | 0.50 m |
| Static / cruise thrust requirement | 147.10 N / 15.32 N per fan |
| Reference RPM (C_T=0.08) / tip Mach | 9298 / 0.715 |
| Electrical architecture | 14S (51.8 V), 88.83 A static |
| Mission energy (raw / required nominal) | 878.1 Wh / 1317.2 Wh |
| Selected battery capacity | 28.0 Ah |
| Baseline thrust effectiveness, eta_T | 0.90 (illustrative) |
| RPM recovery / tip-Mach ceiling | 9801 / 11049 RPM |
| M5-updated mission energy | 920.7 Wh (+4.9%) |
| **Overall baseline feasibility** | **FEASIBLE**, governed by mission-energy margin (+0.050) |

## Final constraint table

| Constraint | Milestone | Margin | Status |
|---|---|---|---|
| Disk loading | M1 | +0.201 | PASS |
| Ideal power | M1 | +0.361 | PASS |
| Tip Mach (reference RPM) | M2 | +0.188 | PASS |
| ESC current | M3 | +0.126 | PASS |
| Battery current/C-rate | M3 | +5.304 | PASS |
| Mission-energy capacity | M4/M5 | **+0.050 (governing)** | PASS |
| Static thrust (pre-recovery, honest diagnostic) | M5 | -0.100 | FAIL* |
| Cruise thrust | M5 | +6.344 | PASS |

\* Not a feasibility gate on its own — static thrust is satisfied via RPM
recovery (see [RESULTS.md](RESULTS.md) §3).

## Robustness findings

- **Strongest sensitivity (computed, not asserted): battery capacity**
  (swing 1.88), followed by cruise duration (1.67), `eta_T` (1.33),
  tip-Mach ceiling (1.11), and motor efficiency (1.08) — all five flip
  feasibility somewhere in their tested range.
- **Tightest boundary: mission cruise duration** — only +9.5% headroom
  (1315 s vs. the 1200 s baseline) before the 28 Ah pack's energy margin
  reaches zero.
- **0.50 m remains the smallest viable diameter** under baseline M5 losses
  (0.45 m fails M1's disk-loading gate outright); 0.55/0.60 m trade a
  larger fan for more margin across every gate.
- Full grid: of 24 tested `eta_T` x cruise-duration combinations, 8 are
  feasible; the governing failure mode splits between ESC current (6
  cases), static-thrust/RPM-ceiling (6 cases), and mission energy (4
  cases) — no single failure mode dominates.

See [RESULTS.md](RESULTS.md) for the complete breakdown.

## Verification

Every headline number in this repository is independently reproducible
from raw formulas, not merely reprinted from production objects:

- **350 tests** (`pytest -W error -q`), each using hand-derived expected
  values or independent reconstruction — never a production function
  checked against itself.
- **`scripts/independent_audit.py`**: a standalone script that recomputes
  32 headline M1-M5 quantities from separately-written formulas and
  diffs them against the live pipeline output (max residual ~1e-13,
  floating-point noise only).
- **26 deterministic figures**, each regenerated and SHA-256-compared
  across this session — byte-identical every time.
- **Clean-environment reproduction**: the full suite, `ruff check .`, and
  every study script were re-run in a fresh virtual environment outside
  the repository, matching the development environment's output exactly.

Full detail: [VERIFICATION.md](VERIFICATION.md).

## Repository structure

```
src/edf_sizing/     # requirements, actuator_disk, efficiency, sizing (M1)
                     # rotational, compressibility, fan_loading, rotational_study (M2)
                     # motor, electrical, battery, electrical_sizing (M3)
                     # mission, energy, mission_sizing (M4)
                     # duct_losses, thrust_lapse, performance_envelope (M5)
                     # robustness (M6)
tests/              # independent verification (pytest), one file per module
scripts/            # one engineering-report script + one figure script per milestone,
                     # plus independent_audit.py and final_robustness_study.py (M6)
figures/            # 26 generated portfolio figures (deterministic PNGs)
DESIGN.md           # full derivations, source audits, equations, per-milestone results
RESULTS.md          # results-first summary (this is the fast read)
VERIFICATION.md     # independent-verification record and residual table
```

## How to run

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -W error -q
ruff check .

python3 scripts/run_sizing.py                    # M1
python3 scripts/make_figures.py
python3 scripts/rotational_fan_study.py           # M2
python3 scripts/make_rotational_figures.py
python3 scripts/electrical_sizing_study.py        # M3
python3 scripts/make_electrical_figures.py
python3 scripts/mission_energy_study.py           # M4
python3 scripts/make_mission_figures.py
python3 scripts/thrust_lapse_study.py             # M5
python3 scripts/make_thrust_lapse_figures.py
python3 scripts/independent_audit.py              # M6
python3 scripts/final_robustness_study.py
python3 scripts/make_final_figures.py
```

## Limitations

No blade-element theory, CFD, compressor maps, motor/ESC/battery thermal
models, battery electrochemistry, acoustic prediction, real-product
calibration, aircraft trajectory simulation, or continuous aircraft drag
polar anywhere in this project. Every non-first-principles coefficient
(`eta_overall`, `eta_T`, thrust-lapse parameters, `M_tip,max`, `eta_motor`,
`eta_ESC`, reserve/usable-energy fractions, specific energy, mission
durations) is an explicit, labeled illustrative assumption — see DESIGN.md
for which are informed by qualitative literature trends vs. purely
illustrative. Sensitivity ranges throughout are deterministic engineering
cases, never probability distributions. See [RESULTS.md](RESULTS.md) §8
and each milestone's DESIGN.md section for the complete limitations list.

## Milestone history

Each milestone is additive and frozen once complete — later milestones
never silently rewrite an earlier milestone's equations or results (every
regression is independently tested; see `tests/`).

- **Milestone 1 — Actuator-disk foundation.** Ideal 1-D momentum theory
  (`actuator_disk.py`), a generic UAV requirement (`requirements.py`), an
  illustrative non-ideal efficiency layer (`efficiency.py`), and a
  predeclared fan-diameter selection rule (`sizing.py`). Out of scope:
  blade-element theory, RPM, tip-Mach, duct/motor/battery sizing.
- **Milestone 2 — Rotational kinematics and tip Mach.** RPM, tip speed,
  and blade-tip Mach (`rotational.py`, `compressibility.py`), NACA-style
  `C_T`/`C_P`/`J` coefficients (`fan_loading.py`), and a diameter x RPM x
  tip-Mach trade study (`rotational_study.py`). Result: M1's D=0.50 m
  fan remains admissible; M2 constrains RPM, not diameter.
- **Milestone 3 — Motor/ESC/battery electrical matching.** Motor
  electrical power and torque (`motor.py`), generic electrical primitives
  and an ESC model (`electrical.py`), a series-cell battery pack using a
  sourced LiPo voltage convention (`battery.py`), and a predeclared
  pack-voltage selection rule (`electrical_sizing.py`). Result: 14S
  selected; 12S fails honestly at the 4.0 Ah baseline capacity.
- **Milestone 4 — Mission energy and battery capacity.** A constant-power
  mission-segment model and predeclared 4-segment mission
  (`mission.py`), energy integration and reserve/usable-energy bookkeeping
  (`energy.py`), and a capacity-selection rule requiring both current AND
  energy feasibility (`mission_sizing.py`). Result: capacity grows from
  4.0 Ah to 28.0 Ah; current and energy feasibility are independent
  questions.
- **Milestone 5 — Thrust-effectiveness and forward-flight lapse.** A
  lumped thrust-effectiveness factor (`duct_losses.py`), an illustrative
  forward-flight lapse model (`thrust_lapse.py`), and RPM-based thrust
  recovery with its electrical/energy consequences
  (`performance_envelope.py`). Result: baseline `eta_T=0.90` requires
  off-design RPM recovery to close static thrust; recovery fits the M2
  tip-Mach ceiling and the M3/M4 architecture, with reduced margins.
- **Milestone 6 — Final robustness audit and portfolio synthesis.**
  Independent re-derivation of every headline number
  (`scripts/independent_audit.py`), a cross-milestone constraint table,
  boundary/breakpoint analysis, and a computed sensitivity ranking
  (`robustness.py`). No new physics — pure verification and synthesis of
  the frozen M1-M5 chain. See [RESULTS.md](RESULTS.md) and
  [VERIFICATION.md](VERIFICATION.md).

Full per-milestone source audits, equations, and limitations:
[DESIGN.md](DESIGN.md).
