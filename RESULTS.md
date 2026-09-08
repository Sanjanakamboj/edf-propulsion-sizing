# RESULTS.md — EDF Propulsion Sizing

Results-first summary of the frozen Milestone 1–6 reduced-order study. See
[DESIGN.md](DESIGN.md) for full derivations and source audits, and
[VERIFICATION.md](VERIFICATION.md) for the independent-verification record.

> **Generic reduced-order conceptual EDF study — not experimentally
> validated, not a real product, and not a flight-qualified architecture.**

## 1. Final architecture

| Parameter | Value | Milestone |
|---|---|---|
| Fan diameter | 0.50 m | M1 |
| Reference thrust coefficient, C_T | 0.08 | M2 |
| Tip-Mach ceiling, M_tip,max | 0.85 (illustrative) | M2 |
| Battery pack | 14S (51.8 V nominal), 28.0 Ah | M3 / M4 |
| Thrust effectiveness, eta_T | 0.90 (illustrative baseline) | M5 |
| Motor / ESC efficiency | 0.90 / 0.97 (illustrative) | M3 |
| Reserve / usable-energy fraction | 0.20 / 0.80 (illustrative) | M4 |

## 2. Strongest quantified findings

1. **M1 sizing alone does not close under realistic thrust losses.** At the
   illustrative baseline `eta_T=0.90`, available static thrust at the
   unmodified reference RPM is 132.4 N against a 147.1 N requirement — a
   **-10.0% honest shortfall**.
2. **RPM-based recovery closes the gap with headroom.** Recovering to
   9801 RPM (vs. a tip-Mach-limited ceiling of 11049 RPM) restores static
   thrust exactly, at a tip Mach of 0.754 — safely under the 0.85 ceiling.
3. **The recovery's electrical and energy costs both fit within the
   already-upsized M3/M4 architecture, but with much tighter margins than
   the ideal case:** ESC current margin drops from a comfortable surplus to
   **+0.126**, and the 28 Ah pack's mission-energy margin drops from M4's
   +0.101 to **+0.050**.
4. **Mission energy, not thrust or current, is the tightest constraint at
   baseline.** The M3 4.0 Ah pack — which passed M3's instantaneous
   current screen — fails the mission-energy requirement by a wide margin;
   the pack had to grow to 28 Ah for energy alone.
5. **At a more pessimistic `eta_T=0.80`, the architecture fails** — not
   because RPM recovery is infeasible (it still fits the tip-Mach
   ceiling), but because the resulting current exceeds the ESC rating
   *and* the mission-energy margin goes negative, simultaneously.
6. **The maximum recoverable thrust-loss fraction (RPM-limited) is
   29.2%** — `eta_T` can fall to ~0.71 before RPM recovery itself is
   blocked by the tip-Mach ceiling, independent of the electrical/energy
   screens.

## 3. Constraint margins (baseline case)

| Constraint | Milestone | Value | Limit | Margin | Status |
|---|---|---|---|---|---|
| A. Disk loading | M1 | 749.2 N/m² | 900 N/m² | +0.201 | PASS |
| B. Ideal power | M1 | 2572.3 W | 3500 W | +0.361 | PASS |
| C. Tip Mach (reference RPM) | M2 | 0.715 | 0.85 | +0.188 | PASS |
| D. ESC current | M3 | 88.83 A | 100 A | +0.126 | PASS |
| E. Battery current/C-rate | M3 | 88.83 A | 560 A (20C) | +5.304 | PASS |
| F. Mission-energy capacity | M4/M5 | 1104.8 Wh | 1160.3 Wh | +0.050 | PASS |
| G. Static thrust (pre-recovery) | M5 | 132.4 N | 147.1 N | **-0.100** | **FAIL (honest)** |
| H. Cruise thrust | M5 | 112.5 N | 15.3 N | +6.344 | PASS |

Row G is a deliberate pre-recovery diagnostic, not a feasibility gate —
static thrust is satisfied via RPM recovery (governing gate 3), not by the
unmodified baseline value. **Governing post-recovery constraint: F,
mission-energy capacity (+0.050) — the tightest of the five gates that
actually determine feasibility.**

## 4. Robustness boundaries

| Boundary | Value | Baseline | Headroom |
|---|---|---|---|
| Minimum feasible eta_T | 0.832 | 0.90 | — |
| Maximum cruise duration (energy margin ≥ 0) | 1314.6 s (21.9 min) | 1200 s (20 min) | **+9.5%** |
| Minimum feasible eta_motor | 0.799 | 0.90 | — |
| Minimum feasible eta_ESC | 0.862 | 0.97 | — |
| Minimum required capacity @ baseline eta_T | 26.66 Ah | 28.0 Ah selected | +5.0% |
| Max recoverable thrust-loss fraction | 29.2% | eta_T down to 0.708 | — |

**The tightest margin in the whole study is mission cruise duration: only
~9.5% headroom before the 28 Ah pack's energy margin reaches zero.**

## 5. Sensitivity ranking (computed, not asserted)

| Rank | Parameter | Tested range | Swing | Flips feasibility? |
|---|---|---|---|---|
| 1 | Battery capacity | 24 / 28 / 32 Ah | 1.884 | Yes |
| 2 | Cruise duration | 600 / 1200 / 1800 s | 1.670 | Yes |
| 3 | Thrust effectiveness, eta_T | 1.00 → 0.65 | 1.327 | Yes |
| 4 | Tip-Mach ceiling | 0.75 / 0.85 / 0.95 | 1.108 | Yes |
| 5 | Motor efficiency | 0.85 / 0.90 / 0.95 | 1.075 | Yes |
| 6 | ESC efficiency | 0.95 / 0.97 / 0.99 | 0.603 | No |
| 7 | Pack voltage (14S/16S) | — | 0.555 | No |
| 8 | Reference C_T | 0.08 / 0.12 | 0.000 | No |

Metric: maximum fractional swing in the smallest margin among {ESC
current, battery current, mission energy, cruise thrust, RPM-recovery
headroom}. `reference_c_t` shows zero swing because it changes RPM/tip
Mach but not the currently-binding mission-energy constraint in this
reduced-order model — a real, not an omitted, finding.

## 6. Diameter trade

| D [m] | M1 gates | RPM required | Tip Mach | Current | Energy margin | Feasible |
|---|---|---|---|---|---|---|
| 0.45 | **FAIL** (disk loading) | 12100 | 0.838 | 98.70 A | +0.010 | **NO** |
| **0.50** | PASS | 9801 | 0.754 | 88.83 A | +0.050 | **YES** |
| 0.55 | PASS | 8100 | 0.685 | 80.75 A | +0.086 | YES |
| 0.60 | PASS | 6806 | 0.628 | 74.02 A | +0.117 | YES |

**0.50 m remains the smallest viable diameter** under baseline M5 losses,
confirming the original M1 selection. Larger diameters (0.55/0.60 m) trade
a smaller fan for more margin across every gate — a legitimate, honestly
reported alternative, not pursued further here since the milestone
brief's scope is verification of the existing selection, not
re-optimization.

## 7. Final conclusion

The baseline architecture — **D = 0.50 m, C_T = 0.08, 14S/28 Ah,
eta_T = 0.90** — is **feasible within the tested reduced-order baseline**.
This is not a validation or optimization claim: every gate closes with a
positive (if sometimes thin) margin, governed by mission-energy capacity
(+0.050), with mission cruise duration the tightest robustness boundary
(+9.5% headroom). The architecture degrades to infeasible at the
`eta_T=0.80` sensitivity case via simultaneous ESC-current and
mission-energy failure — a genuine, non-tuned finding, not a rare edge
case (it appears at the very next step of the predeclared `eta_T`
sensitivity grid).

## 8. Critical limitations

- No blade-element theory, CFD, compressor map, motor/battery
  electrochemistry, thermal model, acoustic prediction, or real-product
  calibration anywhere in M1–M6.
- `eta_T`, the thrust-lapse coefficients, `M_tip,max`, `eta_motor`,
  `eta_ESC`, reserve/usable-energy fractions, and mission durations are
  all explicit illustrative sensitivity assumptions — see DESIGN.md for
  which are sourced (qualitative trends only) vs. purely illustrative.
- No continuous aircraft drag polar; only the static and cruise operating
  points are true requirements.
- Sensitivity ranges are deterministic engineering cases, not probability
  distributions — no likelihood, confidence, or risk language is implied.
- This is a portfolio engineering study demonstrating a transparent,
  fully-verified reduced-order sizing chain — not a flight-qualified or
  commercially calibrated propulsion design.
