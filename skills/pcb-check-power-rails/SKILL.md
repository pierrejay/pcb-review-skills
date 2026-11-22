---
name: pcb-check-power-rails
description: "Power budget and regulator check of a PCB: rail set-points with tolerances against the load's range, ripple, inductor saturation, effective MLCC capacitance under DC bias, power-up sequence, rail dips at a source switchover or load hot-plug (ngspice), bulk capacitance."
---

# Check: power budget, converters, rail transients

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `mlcc_bias.py`: DC-bias fit, effective capacitance of a part and of a rail, typical fractions;
- `power_sequence.py`: set-point, ripple, enable instant, sequence corners, power-good chaining, downstream bounds;
- `spice.py`: `run`, the launcher of every netlist (results only from a run that reached its stop time).

## Purpose
Does every regulator deliver a voltage inside the range of its loads once reference and resistor tolerances are
stacked, with an inductor that does not saturate and the capacitance really there under bias? Do the rails come
up in the order the load requires at every tolerance corner? Does a rail stay in regulation when its source
switches over or a load is plugged in?

## When it applies
- Set-points, ripple, inductors, sequence: any board whose regulators feed ICs stating a supply range and a
  power-up order. Rail transients: a rail with two sources (power mux, OR-ing), a hot-pluggable downstream port,
  or little bulk capacitance for its load steps.
- The scope removes or adds cases: a port declared internal has no hot-plug case; a host port as source brings
  its own minimum (e.g. 4.75 V at the port of a USB host, indicative); two variants on the same rails need the
  designer to say which is fitted (the other kept "for the record" only).

## Inputs to obtain
- **PCB**, read at each run: Value of the feedback dividers and enable RC parts by reference; capacitors of each
  rail (value, case). **BOM**: exact part number and rating of every capacitor above 100 nF, of each inductor.
  **Schematic**: topology, feeds per pin, mux divider, load-switch limit resistor.
- **Datasheets**:
  - regulator: VREF and its tolerance, switching frequency min–max, current limit min / typ, enable threshold
    min–max as guaranteed (Pitfalls), soft-start min–max, maximum duty cycle, RDS(on), dropout at the load current
    (linear regulator), UVLO thresholds (rising min–max, typical, maximum falling, hysteresis), power-good low level
    at its test current, leakage, threshold (rising, falling), the input voltage from which the power good is valid;
  - inductor: tolerance, DCR, saturation current and its definition (inductance drop at Isat);
  - load: recommended operating range of each supply domain, power-up order, ripple limit if stated;
  - capacitors: DC-bias and ESR curves of the exact part number;
  - load switch: on-resistance, current limit, response time versus current; power mux: on-resistance,
    switchover time, threshold reference min–max, reverse-current blocking.
- **Reference design** of the load: power-up order, reset network. **Designer**: fitted variant, hot-pluggable
  ports, measured consumption when it exists.
- **Power budget** per scenario: one module, the same function for this check, `pcb-check-thermal`,
  `pcb-check-pdn-ir-drop` and the inductor derating of `pcb-check-derating-sourcing`.

## Method
1. **Budget**: consumptions from the datasheets at the real operating mode (speed, transmitting or idle, bus
   loaded or not), typ and max; LEDs and pulls computed. An unpublished consumption (an SoC) gets a "typical" and
   an "envelope" scenario, replaced by the designer's measurement as soon as it exists.
2. **Set-points** (`set_point`): each rail against the **intersection** of the ranges of all domains it feeds; the
   smallest of the two margins and, when it is thin, the resistor change that centres the rail (value, resulting
   nominal and range).
3. **Ripple and inductor** (`ripple`; `ripple_bank` for a bank of different parts) at the pessimistic corner: the peak
   against Isat, and the current limit against Isat too. The ripple includes ΔI × ESR of the output bank at the
   switching frequency: the ESR is a datum read on the parts' curves, not a zero. A limit above Isat has no effect in
   operation, but in a short the inductor may saturate before the limit acts: say so.
4. **Effective capacitance under DC bias** (`fit_bias`, `effective_capacitance`): the points of the exact part
   number in `verification/models/mlcc_dcbias.json`, one fit per part with its deviation stored, the sum per rail at
   its voltage, a constant in the netlists; without a curve, `typical_fraction`, an estimate; outside its table,
   the case at two bounds stated as estimates (e.g. 0.3 and 0.7 of the marked value for a class-2 part at half its
   rating or more), judged at the bound that hurts, the curve listed as a datum to obtain.
5. **Sequence by RC** (`enable_instant`, `sequence_corners`): the enable instant at two ramps (a fast plug-in ramp;
   the upstream soft-start otherwise); a regulator starts at the later of its enable crossing and its input crossing
   the rising UVLO, and is settled at the later of one soft-start after its start and its input reaching the level
   at which it holds its output (`vin_reg`: set-point maximum + maximum dropout at the load current for a linear
   regulator; (set-point maximum + I × (RDS(on) + DCR)) / the guaranteed minimum of the maximum duty cycle for a
   buck): on a slow ramp the output follows the input until then. The corners over threshold, UVLO, soft-start and
   each network's RC, every regulator and every network independently. A missing threshold, UVLO, soft-start,
   `vin_reg` or tolerance is a datum to obtain, not a zero. Channels of one IC track only on a datasheet clause
   (`tracking`); otherwise the correlated result is an estimate next to the independent one, which decides. A
   negative worst margin comes with the capacitor change that restores the order.
6. **Chained power goods** (`chain_matches`, `power_good_chain_conditions`): the chain read from the board against
   the order required, then each level computed and judged; the release threshold
   against the load's range under a declared requirement. A chained sequence is not judged with the time
   criterion of an RC one.
7. **Rail transients** (ngspice): capacitors at their effective value with ESR, converters as a constant-power load,
   the mux as two one-way channels with none conducting during the switchover, a load switch that trips on charge, a
   plugged device as a discharged capacitor; the scenario expected to be the worst first (method § 7).
8. **Capacitance corner**: nominal first (`ktol` = 1); where the margin is small, every capacitor at 1 − tol at once
   (plugged device excepted), the verdict then on that row, nominal row next to it.
9. **Downstream rail during a dip** (`downstream_bounds`): two independent bounds on the row that carries the
   verdict, the lower one kept, the in-house current and RDS(on) margins stated.
10. **Supplies of one IC and its reset**: list every IC with more than one supply pin or a stated order between
    its supplies, its clock and its reset (power-up timing table, its footnotes, the application chapter). Two
    supplies fed from one rail, one through a ferrite or a filter, rise together: an order "B after A is fully
    ramped" is **not** met by construction, and the datasheet's fallback applies (usually an external reset once
    both are up). A clock that starts after the supplies (an oscillator on the same rail: its start-up time; a
    clock output of another IC that starts after that IC's reset) needs the reset held until it is stable plus the
    stated delay. Then read who holds the reset at power-up: an RC, a supervisor, or a GPIO, which is an input at
    the MCU's own reset (floating: the pull-up releases the reset with the rail); a GPIO puts the requirement on the
    firmware, written as such with the pulse width and delays to respect.
11. **Reference design**: compare the order and the reset RC with the manufacturer's reference design.

## Criteria
| Criterion | Form | Number read in |
|---|---|---|
| Set-point | [min; max] inside the intersection of the domains' ranges | load datasheet, table quoted |
| Inductor | peak current < Isat | inductor datasheet, its definition of Isat |
| Sequence (RC) | margin ≥ 0 at every independent corner | load datasheet or reference design |
| Sequence (chained) | chain read = order required; every `power_good_chain_conditions` line met | regulator datasheets |
| Order inside one IC, clock at power-up | met by the circuit, or the datasheet's fallback (reset after both supplies / after the clock) provided by the hardware or written as a firmware requirement | load datasheet: timing table, footnotes, application chapter |
| Downstream input | ≥ output + dropout at the real current plus an in-house margin, or dip covered by its capacitors; no UVLO | regulator datasheet |
| Downstream rail | ≥ the highest minimum among its loads | load datasheets, most demanding quoted |
| Port | ≥ the minimum of its interface standard at the port (e.g. a USB device port: of the order of 4.4 V for a low-power device, indicative) | the interface specification |

Ripple is reported at the nominal effective capacitance, not judged, unless a load states a limit (then with C_eff
at its low corner, C_eff × (1 − tol)); the bank ESR at the switching frequency is in both. A hot-plug case that
the scope makes impossible is "not applicable".

## Self-checks
- Fit error of a DC-bias curve stored and compared with the margin of the verdict that uses it; an error that is
  not small against that margin means the law does not suit that curve over that range (read its points as a table).
- The time under a limit is integrated only after the event; the steady state before it must already be inside
  the limits (else the initial conditions are wrong). A hot-plugged capacitor starts discharged (`.ic`, not
  `.nodeset`) and receives a non-zero charge: both are checked, or the case is wrong, not passed.
- Each transient row carries its `ktol`.

## Tool contract
Three scripts, one JSON each in `results/`, plus the shared budget module.
- **Set-points, ripple, sequence**: venv (numpy) after a short export step in KiCad's Python. Writes
  `results/power_rails.json`: `dc` (nominal, min, max, range, smallest margin), `ripple` (ΔI, peak, nominal and
  effective capacitance, ΔV), `sequence` (worst margins per ramp case, nominal start and end of each rail; for a
  chained sequence the chain read and the condition list with `ok` per line), and a bar chart of the nominal
  sequence.
- **Rail transients**: venv (numpy, scipy), runs ngspice through `spice.run`. Writes `results/rail_transients.json`: the
  budget powers, one row per scenario and variant with `ktol`, minimum, time under each limit, port minimum, switch peak
  and whether it limited.
- **Downstream bound**: plain Python; reads both JSON and writes `results/rail_dropout.json`: the worst case and
  its margin over each load minimum.
- **Refusals of the board scripts**: a rail without capacitor; a divider, pull-up or chain that differs from the table.

## Pitfalls
- **Do not use the nominal capacitance of a class-2 MLCC under bias; take the curve of the exact part number.** A
  class-2 MLCC rated not far above the rail voltage typically keeps a third to a half of its marked value,
  sometimes less, at the DC bias of the rail; two parts of the same value and case but another rating or series
  can differ by tens of percent; a typical table is a screening estimate, off by a third or more for a given part.
  A part whose manufacturer publishes no curve takes the curve of an equivalent part (same dielectric, rating and
  value, same case or the nearest), listed as an estimate.
  Decoupling and bulk judged only against the IC manufacturer's recommendation compare at nominal when the part
  resembles the one it qualified (dielectric, rating, case), effective when it does not or when the manufacturer
  specifies an effective value (`pcb-verification`, failure modes).
- **Put the R and C of the enable networks in the corners; thresholds of separate chips are independent.** The
  order of two RC-delayed enables holds only if the ratio of their time constants exceeds the spread of delays that
  the thresholds alone can produce, plus the tolerances of R and C (two capacitors at ± 20 % move the ratio by a
  factor 1.5 = 1.2 / 0.8).
- **Take the enable thresholds the datasheet guarantees** (highest input-low, lowest input-high), not the span of a
  typical curve: the guaranteed span is usually wider, and at a low common threshold the delay between two RC
  networks shrinks.
- **Locate the minimum in time before adding bulk.** Capacitance behind a blocking element (reverse-blocking
  switch, mux channel, diode) does not hold the rail during the hole while that element does not conduct; only the
  rail's own capacitance counts then.

## Limits
Converters are a constant-power load without control loop; cable and converter output impedances are estimates;
ESL neglected (µs events, not ns edges); input-switch reaction delay ignored (pessimistic downstream). DC-bias
curves at 25 °C, without temperature or ageing. The sequence uses datasheet thresholds and soft-start times, not
measured ones: confirm with a start-up oscillogram of all rails.
