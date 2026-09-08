# VERIFICATION.md — EDF Propulsion Sizing

Independent-verification record for the frozen Milestone 1–6 reduced-order
study. Every check below compares a **production route** (the actual
`edf_sizing` package output as it flows through the real pipeline) against
an **independent route** (a hand-derived formula, written separately,
never calling the same production function on both sides).

## 1. Subsystem verification table

| Subsystem | Quantity | Production route | Independent route | Residual | Tolerance | Status |
|---|---|---|---|---|---|---|
| M1 | Static thrust/fan | `requirements.static_thrust_per_fan_N` | `1.2·W/n_fans` | 0.00e+00 | 1e-6 | OK |
| M1 | Cruise thrust/fan | `requirements.cruise_thrust_per_fan_N` | `(W/8)/n_fans` | 0.00e+00 | 1e-6 | OK |
| M1 | Static induced velocity | `sizing.CandidateResult.vi_static_m_s` | `sqrt(T/(2ρA))` | 0.00e+00 | 1e-6 | OK |
| M1 | Static ideal power | `sizing.CandidateResult.pi_static_W` | `T^1.5/sqrt(2ρA)` | 0.00e+00 | 1e-6 | OK |
| M1 | Static disk loading | `sizing.CandidateResult.disk_loading_N_m2` | `T/A` | 0.00e+00 | 1e-6 | OK |
| M1 | Cruise induced velocity | `sizing.ThrustTableRow.vi_m_s` | quadratic root formula | 0.00e+00 | 1e-6 | OK |
| M1 | Cruise ideal power | `sizing.ThrustTableRow.pi_W` | `T(V+vi)` | 0.00e+00 | 1e-6 | OK |
| M1 | Selected diameter | `select_fan_diameter().selected.diameter_m` | 0.50 m (predeclared rule) | 0.00e+00 | 1e-6 | OK |
| M2 | Static RPM (C_T=0.08) | `RotationalOperatingRow.rpm` | `n=sqrt(T/(ρC_TD⁴))·60` | 0.00e+00 | 1e-6 | OK |
| M2 | Static tip Mach | `RotationalOperatingRow.tip_mach` | `πDn/60/a` | 0.00e+00 | 1e-6 | OK |
| M2 | Ambient speed of sound | `compressibility.speed_of_sound()` | `sqrt(1.4·287.05·288.15)` | 0.00e+00 | 1e-6 | OK |
| M2 | Pressure-jump identity | `fan_loading` / `sizing` disk loading | equal by construction | 0.00e+00 | 1e-6 | OK |
| M2 | C_T=0.05 static tip Mach | `RotationalOperatingRow.tip_mach` | hand formula | 2.22e-16 | 1e-6 | OK |
| M2 | Tip-Mach RPM ceiling | `compressibility.max_rpm_static()` | `60·M_max·a/(πD)` | 0.00e+00 | 1e-6 | OK |
| M3 | Static shaft power | `RotationalOperatingRow.p_shaft_est_W` | `Pi/eta_overall` | 0.00e+00 | 1e-6 | OK |
| M3 | Battery input power | `m3_reference_battery_powers()` | `P_shaft/eta_motor/eta_ESC` | 0.00e+00 | 1e-6 | OK |
| M3 | 14S static battery current | `ElectricalOperatingPoint.battery_current_A` | `P_batt/V_pack` | 0.00e+00 | 1e-6 | OK |
| M3 | 14S static C-rate | `.c_rate_required` | `I/Ah` | 0.00e+00 | 1e-6 | OK |
| M3 | No eta_overall double-count | `m3_reference_battery_powers()` | single-application chain | 0.00e+00 | 1e-6 | OK |
| M4 | Raw mission energy | `compute_energy_requirement().mission_energy_Wh` | segment-by-segment `Pt/3600` sum | 0.00e+00 | 1e-6 | OK |
| M4 | Required nominal energy | `.required_nominal_Wh` | `mission·1.2/0.8` | 0.00e+00 | 1e-6 | OK |
| M4 | Required Ah at 14S | derived | `required_nominal_Wh/51.8` | 0.00e+00 | 1e-6 | OK |
| M5 | Static available thrust | `PerformanceEnvelopeResult.static_margin` | `eta_T·T_static` | 0.00e+00 | 1e-6 | OK |
| M5 | Cruise available thrust | `.cruise_margin` | `T_static_avail·f_lapse(30)` | 0.00e+00 | 1e-6 | OK |
| M5 | Static shortfall | `.static_margin.margin_fraction` | `eta_T-1` | 0.00e+00 | 1e-6 | OK |
| M5 | RPM recovery | `.rpm_recovery.rpm_required` | `RPM_ref/sqrt(eta_T)` | 0.00e+00 | 1e-6 | OK |
| M5 | RPM²-thrust round-trip | — | `eta_T·(RPM_req/RPM_ref)²ᵃᵗ = 1.0` | 0.00e+00 | 1e-6 | OK |
| M5 | RPM³ power scaling | `.recovered_electrical.shaft_power_recovered_W` | `P_ref·(ratio)³` | 0.00e+00 | 1e-6 | OK |
| M5 | Recovered tip Mach | `.rpm_recovery.tip_mach_at_recovery` | `π·D·n_rec/a` | 0.00e+00 | 1e-6 | OK |
| M5 | Recovered battery current | `.recovered_electrical.battery_current_A` | full hand chain | 0.00e+00 | 1e-6 | OK |
| M5 | M5 updated mission energy | `.mission_energy_penalty.mission_energy_m5_Wh` | segment-by-segment hand sum | 1.14e-13 | 1e-6 | OK |
| M5 | 28 Ah capacity margin | `.mission_energy_penalty.capacity_margin.margin` | `usable/reserve_adj - 1` | 0.00e+00 | 1e-6 | OK |

**32/32 numeric checks pass. Max absolute residual: 1.14e-13 (floating-point
noise only). Max relative residual: 2.45e-16.**

Run `python3 scripts/independent_audit.py` to reproduce this table; it
exits nonzero on any failure.

## 2. Test suite

| Metric | Value |
|---|---|
| Total tests | 350 |
| Milestone 1 | 58 |
| Milestone 2 | 65 |
| Milestone 3 | 79 |
| Milestone 4 | 58 |
| Milestone 5 | 58 |
| Milestone 6 | 32 |
| Independent-audit numeric checks | 32 (separate script, not part of pytest count) |
| Command | `pytest -W error -q` |
| Result | 350 passed, 0 failed, 0 warnings |

Every test file follows the project convention of hand-derived expected
values or independent reconstruction formulas — production functions are
never used to generate their own expected value (see each `tests/test_*.py`
module docstring).

## 3. Figure determinism

| Set | Count | Regenerated | Result |
|---|---|---|---|
| M1 (01–03) | 3 | Yes, 3x this session | Byte-identical |
| M2 (04–07) | 4 | Yes, 3x this session | Byte-identical |
| M3 (08–11) | 4 | Yes, 3x this session | Byte-identical |
| M4 (12–16) | 5 | Yes, 3x this session | Byte-identical |
| M5 (17–21) | 5 | Yes, 3x this session | Byte-identical |
| M6 (22–26) | 5 | Yes, 2x this session | Byte-identical |
| **Total** | **26** | | **All byte-identical (SHA-256)** |

Verified via `shasum -a 256` comparison before/after each regeneration
pass in this session; no figure hash changed across any milestone.

## 4. Clean-environment reproducibility

A temporary virtual environment was created outside the repository (via
`python3 -m venv`), `edf_sizing` installed via `pip install -e ".[dev]"`
with no `pyproject.toml` changes required, and the full test suite plus
`ruff check .` plus every M1–M6 study script (including
`independent_audit.py`) were re-run inside it.

| Check | Development environment | Clean environment |
|---|---|---|
| Python | 3.14 | 3.14.5 |
| matplotlib | (dev-installed) | 3.11.1 |
| `pytest -W error -q` | 350 passed | 350 passed |
| `ruff check .` | All checks passed | All checks passed |
| `independent_audit.py` | 32/32 checks pass | 32/32 checks pass |
| All study-script headline numbers | — | Identical |

One figure (`22_final_constraint_margins.png`) was regenerated to a
scratch location outside the repository in the clean environment; its
visual content is identical to the tracked figure, though its PNG bytes
differ (expected — different matplotlib versions produce different PNG
encodings even for pixel-identical renders, which is exactly why tracked
figures are always regenerated and hash-compared only within the same
development environment/session, never across matplotlib versions). The
temporary venv and scratch figure were removed after the check.

## 5. Source-audit caveats (see DESIGN.md for full detail)

- M1–M5 equations are matched against NASA/NACA/university/peer-reviewed
  propulsion literature for their *qualitative form and convention*
  (actuator-disk momentum theory, NACA C_T/C_P/J coefficients, ducted-fan
  loss trends, thrust-lapse-with-advance-ratio trends). No project
  equation is claimed to be independently peer-reviewed or experimentally
  validated for this specific generic airframe.
- All numeric coefficients not directly implied by first-principles
  physics (`eta_overall`, `eta_T`, thrust-lapse `k`/`V_ref`, `M_tip,max`,
  `eta_motor`, `eta_ESC`, reserve/usable-energy fractions, specific
  energy, mission durations) are explicitly labeled ILLUSTRATIVE
  throughout DESIGN.md and every generated figure/script — never presented
  as sourced or measured values for a real EDF unit.
- The NASA X-57 Maxwell battery specific-energy figures (225/149 Wh/kg)
  cited in DESIGN.md Milestone 4 were obtained via a search-engine
  summary of the source PDF (direct text extraction was inconclusive due
  to PDF compression); they are used only as an order-of-magnitude
  sensitivity anchor, not a literal reproduction of the source document.
