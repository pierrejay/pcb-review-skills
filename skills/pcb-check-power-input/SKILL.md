---
name: pcb-check-power-input
description: "Power-input protection check of a PCB in ngspice, for any cable-fed input (e.g. 12/24/48 V, USB VBUS): hot-plug overshoot, surge of both polarities (IEC 61000-4-5 may apply), reverse polarity and series diode, TVS choice and placement, two-stage coordination, transient behaviour and damping of an LC input filter."
---

# Check: power input (hot-plug, surge, reverse polarity, input filter)

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `power_input_models.py`: two-point TVS fit, soft-saturation constant, damper sizing;
- `mlcc_bias.py`: effective capacitance;
- `cwg_fit.py`, `models/cwg_iec61000-4-5.lib`: combination-wave generator;
- `models/*_behav.lib`: TVS and Schottky examples;
- `spice.py`: `run`, the launcher of every netlist (results only from a run that reached its stop time).

## Purpose
Between the supply connector and the first converter sit a clamp, usually a series diode, capacitors and
sometimes an LC filter. At hot-plug, at a surge of either polarity and, when the connector allows it, at a reversed
connection, does the voltage **at the converter pin** stay within its ratings, does every protection part stay
inside its own ratings, and does an input filter behave in transient where it really sits relative to the clamp?

## When it applies
- A power input fed through a cable, whatever its voltage (e.g. 12, 24, 48 V, or USB VBUS, hot-plugged by
  design): hot-plug applies; surge according to the scope. A low voltage or a standard connector exempts none. A
  ceramic input capacitor and the inductance of the cable form an LC with little damping: after a voltage step it can
  ring up to about twice the step (less when losses or a clamp limit it), which at 5 V already exceeds the absolute
  maximum of a part rated for a 5 V rail (`references/examples.md`, "A 5 V USB input rings like a 24 V one").
- The test levels come from what the designer declares (`../pcb-verification/references/scoping.md`). Texts that
  may apply: surge immunity, IEC 61000-4-5 (generator and coupling networks); levels per port type, the generic
  immunity standard for the environment (IEC 61000-6-1 / -6-2) or the product-family standard, whose notes on DC
  power ports the reader reads in the edition that applies to the product. Indicative values commonly used in
  design:
  - **dedicated supply** (adapter, internal supply) with a cable of at most about 30 m: the generic standards
    typically ask no surge on this port; a robustness target may still be simulated, e.g. ± 1 kV behind 42 Ω as
    for a signal port;
  - **dedicated supply with a cable above about 30 m**: treated as a signal port, ± 1 kV behind 42 Ω (coupled
    line-to-earth by the standard);
  - **port connected to a DC distribution network** (shared cabinet supply): treated as a power port, of the
    order of ± 0.5 kV (line-to-line) behind 2 Ω. The source impedance is far lower, so the clamp sees far more
    current than at 42 Ω: hardware sized for the first scope may not hold in the third.
- Each level is simulated in its coupling mode: between the two wires, or a wire against earth, the board ground then
  a node of its own (`references/method.md` § 6, "Line-to-earth surge"): among the ground configurations of the scope,
  the one expected to be the worst first. Against earth the stress moves with the configuration: through the ground
  link and the input clamps when the board ground is earthed, across the barrier to earth when it is floating or tied
  through a capacitor.
- The restriction of the scope goes into the manual.

## Inputs to obtain
- **Schematic and PCB**: the chain in order, node by node, with what hangs on each node (connector, clamps, series
  diode, capacitors, inductor, converter), and on which side of each series element every clamp sits; values read
  from the PCB.
- **Converter datasheet**: maximum input voltage in operation, absolute maximum, any short-duration rating.
- **TVS datasheets**: stand-off, breakdown min / typ / max at 1 mA, clamping voltage **in 8/20 µs** with its
  current, dynamic resistance, 8/20 µs peak current, maximum continuous breakdown current.
- **Series diode**: VRRM, forward voltage at several currents, surge current, junction capacitance, avalanche
  rating when one exists (a Schottky usually has none). **Inductor**: inductance, DCR, Isat and its definition.
  **Capacitors**: DC-bias curve of the exact part (`mlcc_bias`), or of an equivalent part as an estimate, rated
  voltage.
- **Designer**: type of source, cable length (shortest and longest), permanent range, load current, test levels
  wanted, whether a reversed connection is possible (connector keying, terminal block) and the source's current
  limit. **Standard**: the IEC 61000-4-5 generator and coupling networks (the lumped generator of `lib/models`,
  indicative).

## Method
1. **Model the chain** node by node, in the order of the board, each clamp on its side of each series element:
   capacitors at their effective value on the curve (`references/method.md` § 1), load at its operating current,
   supply cable of the case, source at nominal + tolerance; surge from the combination-wave generator through the
   coupling network of the scope. Every node has a DC path and every loop its losses: a floating node behind a
   blocked diode, or a lossless LC, gives voltages that are artefacts of the model.
2. **Component models**: TVS fitted on its published 8/20 µs points, typical and maximum variants
   (`tvs_fit_exact`); series diode with its breakdown at VRRM, so that exceeding the rating shows; linear inductor,
   and near the limit the saturable one from one datasheet point (`saturation_ik`).
3. **Cases**, the one expected to be the worst first: hot-plug on the declared cable that damps least (usually the
   shortest) at the highest source voltage; surge at the declared level, both polarities when the chain is not
   symmetric (a series diode makes it asymmetric); the reversed hot-plug, run to its steady state, when the scope
   allows a reversed connection. The other cables, the level just above the scope, the other wires and ground
   configurations, capacitor corners and filter variants on the other cases are added when a result is near its
   limit or the designer asks; those not run are written with their reason. On each run the converter node and the
   clamp node are read apart, with the stress of each protection part.
4. **LC input filter in transient, in the full chain, with the clamp where it sits on the board.** A clamp before
   the inductor holds its own node only: the inductor and the converter-side capacitor ring above the clamped level
   on every step, whatever the stability criterion says. Simulate the filter as fitted, then the corrections
   (clamp moved to the converter side, series R–C damper `damper`, resistance in series in the supply path
   `series_damper`, resistor across the inductor), tabulated, the resistor that carries the pulse energy judged on its
   single-pulse curve (`references/method.md`, § 4). A filter proposal states on which side of the inductor the clamp
   goes, and comes with its damper or with the transient result that shows it is not needed.
5. **Coordination** when the clamp is not enough: two stages with a pulse resistor, or a converter with a higher
   input rating, each judged on its simulation. A higher input rating or an eFuse changes the limit to hold, not
   the energy to absorb: the input TVS stays.
6. **Verdict per quantity** on the cases run, saying which. Near the limit: the higher of the saturable and linear
   results; the capacitors at a tolerance corner, each group at its own, × (1 − tol) or × (1 + tol) (the I²t of a
   fuse and the forward peak of the series diode grow with C; a node voltage can peak on a mixed corner, one
   capacitor low and the next high).

## Criteria
| Quantity | Limit | Source |
|---|---|---|
| Converter input | ≤ continuous maximum in steady state; ≤ short-duration or absolute maximum during the transient; negative excursion within its absolute minimum | converter datasheet |
| TVS | clamp current ≤ 8/20 µs peak rating; stand-off ≥ permanent maximum of the source; continuous breakdown current not reached at that maximum | TVS datasheet |
| Series diode | reverse voltage ≤ VRRM without relying on avalanche, or reverse energy within a published avalanche rating; forward peak ≤ IFSM at its pulse width | diode datasheet |
| Reversed connection (when the scope allows it) | converter node ≥ its absolute minimum, during the transient and in steady state; series element reverse voltage ≤ its rating without avalanche; steady current and dissipation of every conducting part ≤ its continuous rating, or a fuse that clears within what that part withstands at that current | datasheets of the converter, the series element, the protections and the fuse |
| Fuse on the path | I²t of the hot-plug and of the surge below its pre-arcing I²t | fuse datasheet |
| Capacitors | ≤ rated voltage | datasheets |
| Pulse resistor | peak voltage ≤ its 1.2/50 µs withstand; continuous dissipation ≤ rating | datasheet |
| Damping or limiting resistor carrying the pulse | pulse energy (transient) within the single-pulse curve at its equivalent duration E / P_peak; continuous dissipation ≤ rating | manufacturer's single-pulse curve; none published → reservation |
| Board ground against earth (line-to-earth, ground floating or through a capacitor) | voltage across each capacitor to earth ≤ its rating; distance from the board copper to earthed parts covering that peak; floating, the port whose cable brings earth back takes it, judged there (`pcb-check-surge-esd`, ground-return configurations) | capacitor datasheet; `pcb-check-isolation` (indicative tables) |
| Ground link to earth (line-to-earth, ground earthed) | the I²t of its current heats its thinnest copper by less than a stated rise (e.g. 100 K; `tvs_fit.adiabatic_heating`) | in-house |
| Saturable inductor | criteria judged at the higher of the saturable and linear results when both are run | in-house |

## Self-checks
- Each TVS and diode model checked in DC at its published points before use (voltage at 1 mA, at the 8/20 µs
  current); the comparison is printed (`tvs_model_voltage`).
- The generator checked alone: 1.2/50 µs into an open circuit, 8/20 µs into a short circuit, peak voltage / peak
  current = 2 Ω, undershoot of the short-circuit current ≤ 30 %.
- A simulated voltage equal to a component rating (diode reverse at VRRM, node at BV) is flagged: the model is
  clamping; rerun without breakdown and read current and energy.
- Each row stores the inductor model that produced it; a row with the linear inductor alone is **not** "the higher
  of the two".
- The power figure `tvs_peak_W` uses the voltage of the node the TVS is on: update it when the clamp moves.
- Values of inductors and capacitors compared with the PCB export after a component change.

## Tool contract
One script for the chain as fitted, plus one study per question (filter corrections, two stages, alternative clamp), all
in the venv (numpy, matplotlib), all running ngspice through `spice.run`; a run is short, and a study of several
variants by several cases stays within a few minutes at most.
- **Outputs**: one JSON per script (`results/input_sim.json`, `results/input_filter_study.json`, …): per case the
  quantities of `references/method.md` § 3 and the model that produced the row; per study the worst converter
  voltage per variant and the per-case detail. The main script also draws two figures, the converter node versus
  time at hot-plug and at the surges.
- **Refusals of the board script**: a model whose DC check misses its published points, a value that differs from
  the PCB export.

## Pitfalls
- **At the negative wave a series diode can take the whole wave alone, in avalanche.** Its reverse voltage then
  sits on VRRM whatever its rating: the model's breakdown is clamping, and the stress to judge is the current and
  the energy behind it.
- **A TVS fitted on 10/1000 µs data typically overstates its dynamic resistance at the surge current**, and can
  lead to a wrong architecture conclusion: fit it on the published 8/20 µs points at the current that matters;
  when the longer pulse is the only data, the figure is a pessimistic estimate, said so.
- **Size the clamp and the converter on the permanent range first** (nominal + tolerance; an adjustable supply at
  its upper setting), independently of the transient tests: a stand-off below the real maximum of the supply
  conducts continuously, whatever the transient results.

## Limits
Behavioural models: beyond the current they were fitted at, the figures only give the order of magnitude of the
stress. Saturation law, cable inductance and effective capacitances are estimates; the swing-back after a positive
wave depends on the coupling network of the test set-up. Stability of the converter with its input filter
(Middlebrook) is a separate criterion; neither replaces the other. Withstand of a
small TVS in 8/20 µs when only its 10/1000 µs power is published is an estimate from the power-duration curve.
