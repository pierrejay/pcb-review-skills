---
name: pcb-check-crystal
description: "Crystal oscillator check on a PCB: load capacitance actually seen, frequency deviation and ppm budget against the interface requirement, oscillation margin (critical gm), drive level; choice of the load capacitors."
---

# Check: crystals

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `crystal.py`: load seen, pulling, ppm budget, critical gm, drive level.

## Purpose
Does each crystal run at the frequency its consumers need, with enough loop gain to start, and without being
overdriven? The check computes the load capacitance the crystal really sees on the routed board, the frequency
shift it causes, the worst-case ppm budget against the requirement of the clocked interface, the critical
transconductance and the drive level.

## When it applies
- One pass per crystal connected to an oscillator stage (SoC, MCU, PHY, MAC-PHY).

## Inputs to obtain
- **Crystal datasheet**: load capacitance CL, maximum ESR, shunt capacitance C0 (maximum, and minimum when
  published), tolerance at 25 °C, stability and the temperature range it is given for, ageing, drive level (typical
  and maximum). Motional capacitance C1 is rarely published.
- **IC datasheet**: required frequency accuracy, recommended external capacitors and resistors, whether load
  capacitors are integrated, pin capacitance, transconductance of the oscillator and amplitude at the crystal
  (the last three rarely published).
- **Reference design** of the IC vendor: values fitted there (capacitors, series and feedback resistors) and the CL
  of the crystal it was validated with.
- **PCB**: the two nets of the crystal, the load capacitors (reference, value, tolerance and dielectric: their range
  over temperature), the series resistor if any, the routed length of each net.
- **Stackup**: propagation delay and impedance of each crystal track as routed (`pcb-check-impedance`), for C'.
- **Designer** (scope of use): the ambient temperature range (stability term), the service life (ageing term), and
  which interfaces the clock feeds — the most demanding one gives the requirement.

## Method
For each crystal (`crystal.py` does the arithmetic; the board script reads the board).
1. **Load capacitance seen** (`side_capacitance`, `load_seen`): each side is its capacitor, its track, its pad and
   the IC pin; the crystal sees the series of the two sides plus the capacitance between the pins. The length is
   the **whole net**, branches (e.g. to a test point) and arcs included. C' is computed from the board's stackup
   and track width: the default of `crystal.py` is one geometry. Integrated load capacitors declared "for a crystal
   of CL x" without their value are estimated from x.
2. **Frequency shift** (`pulling_sensitivity`, `frequency_shift`, `worst_shift`): the finite change between CL and
   the load seen, not the slope S, which understates a shift of several pF. The shift decreases as C0 grows: it is
   taken at the minimum C0, 0 when the datasheet publishes only a maximum.
3. **Budget** (`frequency_budget`): tolerance + stability + |load shift| + ageing, arithmetic worst case in ppm,
  against the requirement. The load shift is taken at the corners of the load: each load capacitor at its tolerance
  (and its drift over the temperature range), the pin and stray capacitances at the ends of their range; the largest
  |shift| at the minimum C0 enters the budget. Its `verdict`: "pass"; "unpublished_c0", a budget that fails only at
  the C0 of 0 taken for an unpublished minimum and passes at the maximum C0, a reservation on partial data
  (`verdict_threshold` on `budget_c0_max_ppm` with the mark of the C0 / C1 estimate, then "Unpublished C0 min and
  C1" below); "fail" otherwise. When the budget fails, `c0_needed_pf` is the smallest C0
  that would pass: report it as the minimum C0 to obtain from the crystal's manufacturer (or that even the maximum C0
  fails, `c0_max_passes` False). The drive level is taken at the largest load seen and the maximum C0. A nominal load
  is not a worst case: ±5 % on two 24 pF capacitors moves CL by ±0.6 pF, about ±5 ppm on a 12 pF crystal.
4. **Oscillation margin** (`worst_gm_crit`, `gm_margin5`): the critical transconductance with the two sides kept apart
   (asymmetric loads raise it) and the series resistor counted, at the maximum C0, the largest over the corners of
   the two sides (not at the largest load: a side without capacitor is worst at its smallest value), and the gm for a
   margin of 5.
5. **Drive level** (`drive_level`): current and power in the crystal at the load seen, bracketed at 1.8 and 3.3 V
   peak-to-peak when the amplitude at the crystal is not published.
6. **Centring value** (information; `centring_value`): the standard C0G value that brings `CL_seen` closest to CL.

## Criteria
| Criterion | Value | Source |
|---|---|---|
| Budget ≤ requirement of the most demanding consumer of the clock | the interface standard, or the tighter figure of the IC datasheet | the text of the interface standard that may apply (value indicative until confirmed in the applicable edition) or the IC datasheet, table quoted |
| Gain margin `gm / gm_crit` ≥ 5 | when the IC publishes gm | oscillator-design rule of thumb of crystal and MCU vendors (e.g. ST AN2867), used when the IC datasheet gives no other: the factor covers the spread of gm and ESR, temperature and ageing |
| Drive level ≤ crystal maximum | the crystal's figure (typically of the order of 100 to 500 µW; read the crystal's) | crystal datasheet |

The budget is judged against the requirement in every case. When gm is not published, its line reads "to measure"; so
does the drive level when the amplitude at the crystal is not published, whatever side of the maximum the bracket falls
on. The report then gives `gm_crit`, the gm needed for a margin of 5 and the bracket, and specifies the measurement.

**Unpublished C0 min and C1.** Almost no crystal publishes them, so the shift at C0 = 0 with an estimated C1 is a
bound the data cannot tighten, not a finding on the board. When the budget is tight or fails at that bound while it
passes at the maximum C0 (`c0_max_passes`), report it as unpublished data, without presenting it as a defect, and
propose to the designer the two ways to settle it:
- **the IC manufacturer's recommendation**: the board fits the load capacitors and a crystal of the CL that its
  datasheet or validated reference design recommends, with short tracks on the two nets. The manufacturer's
  validation covers the load shift; with the designer's acceptance (`accept_estimate`), the verdict is Pass *, the
  recommendation (document, table) given as its basis;
- **a measurement**: the frequency on a buffered clock output of the IC (e.g. CLKO), at the ambient of the scope;
  the measured offset replaces the computed shift in the budget. A probe on the crystal pins adds its capacitance to
  one side and shifts the very frequency it reads (1 pF can pull a 6 pF crystal back to its nominal load and show
  0 ppm where the board is 12 ppm off): it settles nothing unless the shift of the probe, computed with
  `frequency_shift` on the load with and without it, is corrected and its uncertainty counted in the budget.

The reservation stays when the board departs from that recommendation (other capacitors, another CL, long or
branched tracks), or when the requirement is tight and no reference design covers it.

## Self-checks
- Hand check of one case: `S` in ppm/pF and the budget sum (reference values in the validation cases of
  `references/method.md`).

## Tool contract
One script, `crystal_check.py`, KiCad's bundled Python (`pcbnew`, to read track lengths and capacitor values); writes
`results/crystal_check.json`; a second to run.
- **JSON**: crystal data, estimates, and per case each side term by term (net, external capacitance, track length,
  total), `CL_seen`, shift, budget terms and total, requirement with source, `gm_crit` and gm ×5, series
  resistance, drive level at both amplitudes, centring value with its `CL_seen`; the verdict lines of the criteria.
- **Refusals of the board script**: a declared net or capacitor absent from the board, a net with 0 mm of track, a
  capacitor value that does not parse in pF.

## Pitfalls
- **Do not recommend new capacitor values on the strength of an estimated pin capacitance.** The
  manufacturer's values already include its pins. When the budget is tight, compute the shift over the plausible
  range of pin capacitance (e.g. 2 to 6 pF) and recommend a change only if the budget fails across the whole range;
  "re-centring" against a guessed value can move the load the wrong way.
- **The margin hidden by a stability given over a wider range than the scope's is not counted.** Over −40 to
  85 °C in a product scoped for 0 to 40 °C, a margin is likely, but the datasheet neither quantifies nor guarantees
  it (the extreme of the curve can fall inside the scope's range): state both ranges and say so instead of alarming
  at a budget near the limit.

## Limits
- Small-signal budget only: the oscillator loop is not simulated, and the behaviour over temperature is the
  datasheet's stability figure.
- Pin capacitance, C1, internal capacitors and amplitude are estimates on most parts; the load shift and the
  drive level inherit them.
- Remains to be measured on the prototype: cold start-up and drive level.
