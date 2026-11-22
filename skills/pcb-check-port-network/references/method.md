# Port network: method, circuits and conventions, solver calls, board table, reporting

The two Ethernet families have their own files (`transformer-coupled.md`, `capacitor-coupled.md`); this file is
common to all.

## Contents
1. Other differential links
2. Method in full
3. The circuits and their conventions
4. Solver calls
5. Board table and algorithm
6. Reporting

## 1. Other differential links

E.g. CAN, RS-485, an isolated bus, USB: the IC datasheet's network (termination, split termination with a capacitor
to ground, choke, protections) against its ranges; symmetry, which sets the common-mode emission and immunity; the
capacitance the protections add, against what the transceiver tolerates. Their standards rarely give a return-loss
mask.

## 2. Method in full

The steps carry the numbers of `../SKILL.md`, "Method"; step 0 (the network as built) is entirely there.

1. **Components against the ranges.** A range the datasheet calls recommended is judged by what the circuit sees,
   the largest value it admits identified case by case from what the manufacturer allows. For capacitances in
   parallel on one line the line IC only sees the total: when the datasheet allows each part up to its own bound
   on the same node, the IC is shown working with the sum of those bounds, and the total of the parts fitted
   (maxima) is judged against it. This holds when the bounds are given for the same node, in one datasheet, for
   the application at hand; it is re-read for every IC (measurement conditions, bias, application the
   recommendation is given for), not carried as a rule. A TVS capacitance is usually given at 0 V and falls under
   bias: its maximum at 0 V is a pessimistic figure. Two TVS in series between the lines count for half their
   capacitance in differential.
2. **Return loss at the connector** (quantified effect of what the network adds). Half circuit of § 3, reference
   Zdiff / 2 (50 Ω for a 100 Ω pair), over the useful band of the link. First the protections at their maximum and
   the leakage at the datasheet ceiling, against the network without the protections; the typical values and the
   leakage estimate of the surge model when the margin is small. The receive branch is neglected unless the
   datasheet gives its input impedance: on a pair shared by both directions it is part of the termination, added as
   a shunt element.
3. **Symmetry.** A difference of capacitance to ground between the two lines converts differential signal into
   common mode, and injected common mode into differential noise. Two-line model and its solution: § 3. Case
   "mismatched" first (capacitors at their opposite tolerance limits, one TVS at its typical and the other at its
   maximum); "typical" (equal TVS) and "matched at 1 %" when the margin is small or to show what a tighter part
   buys. Transformer-coupled port: not computed (`transformer-coupled.md`); multidrop port: `capacitor-coupled.md`.
4. **Conducted common-mode emission of the port** (0.15–30 MHz): level = density + 20·log(envelope) + quasi-peak
   allowance − conversion (dB), and its margin to each class at each frequency. Density of the signal in 9 kHz at
   low frequency 10·log(2·V_rms²·T·9 kHz) for a random line code of symbol period T and RMS amplitude V_rms (from
   its levels and their probabilities), shaped by sinc² taken at the **envelope** of its lobes (sinc up to
   f·T = 0.5, then 1/(π·f·T)): an upper bound without transmit filter. A code whose spectrum is spread
   differently (e.g. DME, scrambled MLT-3) is estimated as a flat density over its band (`density_flat_dbuv`), an
   order of magnitude. Quasi-peak of a noise-like signal: of the order of +7 dB on the RMS value (estimate).
5. **Conducted immunity**: differential noise at the IC lines in the signal band, solved on the reverse
   excitation: an EMF at the cable's midpoint behind z_cm − 25 Ω (e.g. the 10 V RMS commonly used for a
   conducted-immunity test of an industrial port, to be confirmed in the applicable text), IC side terminated by its
   series resistors and line capacitances (`injection`, `differential_noise`). The DM → CM ratio does not apply:
   the terminations of the two directions differ. Compared with the signal received at the end of the longest
   cable.
6. **Multidrop node budget**: `capacitor-coupled.md`.
7. **Design study: plane or not under the pair, cable side.** Compare the variants at equal routing (no copper on
   any layer; plane on the adjacent layer; void on the track layer and the adjacent one with the plane farther
   down) on: differential capacitance added to the node; capacitance of each line to ground and its P/N
   difference (per-millimetre even-mode capacitance × length mismatch), from which the change of mode conversion
   20·log((e + ΔC variant) / (e + ΔC reference)) for a diode mismatch e swept over a fraction of a pF; impedance
   and its sensitivity to etching (±20 µm on the width, ∓20 µm on the gap) in both stackups; peak voltage of a
   contact discharge as a function of the ground-return inductance that each variant allows for the protection
   (`pcb-check-surge-esd`). A layout note that asks for a void is weighed by this study, not applied by default
   (`../../pcb-verification/references/qualitative-rules.md`).

## 3. The circuits and their conventions

The calculations are a few lines of complex arithmetic (`mode_conversion.py`); what must be reproduced exactly is
the circuit and its conventions.
- **Return loss**, half circuit seen from the connector, one line against the symmetry plane, reference
  Zdiff / 2. `ladder_impedance` takes the circuit as a list of elements from the IC outwards, each "series" (in the
  line) or "shunt" (from the line to the symmetry plane, i.e. to ground for the differential mode). Conventions:
  an element **between the two lines** enters at half its value for R and L and twice its value for C (the
  symmetry plane splits it); an element from one line to ground enters as is; a series element of each line enters
  as is. Return loss = −20·log|(Z − Zref) / (Z + Zref)|. The ladder of each family is in its file.
- **Mode conversion** (not a transformer-coupled port), three nodes a, b (the two lines at the port) and m (cable
  midpoint). Sources + ½ V and − ½ V behind r·(1 + δ) and r·(1 − δ) (r the series resistor of each line, δ
  its tolerance), conductances g_a and g_b; admittances y_a = jωC_a and y_b = jωC_b from each line to ground; cable =
  50 Ω from each line to m (g_l), and m to ground through Z_cm − 25 Ω (g_m): 100 Ω differential, Z_cm in common
  mode (150 Ω: the measurement network commonly used for wired network ports). Solve

      [ g_a + y_a + g_l        0             −g_l      ] [v_a]   [ +½·g_a ]
      [       0          g_b + y_b + g_l     −g_l      ] [v_b] = [ −½·g_b ]
      [     −g_l              −g_l        2·g_l + g_m  ] [v_m]   [    0    ]

  and take conversion = |(v_a + v_b) / 2| / |v_a − v_b|. Any linear solver does.

## 4. Solver calls

The `Geometry` of each reference situation is built exactly as in `pcb-check-impedance` (table "key → Geometry":
adjacent plane; far plane with `h_top` / `er_core`; no plane with `plane=False`), a pad being a single track of the
pad's width (`s = 0`). `d_fine`: the step `impedance_keys.mesh_step` gives for the same situation, the solver's default
(`min(h, max(w, s, 0.05)) / 80`) over an adjacent plane, 0.004 mm over a far plane, at most 0.003 mm without plane. A
lateral ground on the track layer is added with `side_gap` (edge-to-edge distance); without plane only the odd mode is
well defined, the even mode depends on that surrounding ground. A coupled pair over a far plane at a fine mesh is the
slowest section (tens of seconds, hundreds of thousands of nodes).

## 5. Board table and algorithm

Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table**: references of the network by role (termination or series resistors, coupling capacitors or
magnetics, centre-tap parts, capacitors to ground, line TVS, array, choke, common-mode termination); values parsed
from the Value field (`"100pF"` → 1e-10); tolerances from the BOM; datasheet constants with their source:
protection capacitance typical / maximum, capacitance of one array channel, ESD diode maximum, choke (inductance,
tolerance, resistance, leakage or `None` + the estimate used), magnetics (ratio, inductance and its bias, leakage,
isolation); the manufacturer part numbers **asserted** for every part whose datasheet constants are typed;
`RULES`: (label, value, tolerance, low, high, unit, source, component maximum or `None`); the ladder of each
return-loss case; signal: levels and probabilities of the line code, symbol period, amplitude, the quasi-peak
estimate, list of frequencies, limit functions; node: the budget, (width, gap) and reference of each stretch as
routed, components typical / maximum, the estimate for through-hole pads.

**Algorithm**: read values and part numbers, assert the part numbers; for each rule `nominal_ok` = low ≤ value ≤
high, `guaranteed_ok` = same test on the component maximum when one is given (`in_range`); keep value, min, max,
tolerance, range, source; two output lists (out of range on the nominal; on the guaranteed value only); return loss
per case and frequency; conversion per case and frequency, level, margins, immunity noise.

## 6. Reporting

Table element → value, tolerance, component maximum, range, source, verdict (nominal / guaranteed); the network
as built against the reference network (wiring rows). Curves of return loss per case against the mask when one
applies; conversion and common-mode level against both classes, with the minimum margin; the immunity estimate
with its status. Design study: one row per variant. State the status of each number: envelope of the spectrum
(upper bound), order of magnitude of a spread spectrum, quasi-peak allowance (estimate), limits and masks
(indicative), immunity as an estimate, the cases not run and why.
