---
name: pcb-check-clock-integrity
description: "Clock lines of a PCB: simulated edges, overshoot, false edges, series resistor value and position, star topology; a source's guaranteed rise time, duty cycle and jitter against the receiver's. Use for a reference clock fed to one or several ICs (e.g. a 50 MHz Ethernet MAC-PHY reference), oscillator fan-out or selection."
---

# Check: clock integrity and clock compatibility

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `clockline.py`: the edge engine (`Net`, `simulate`, `edges`, `metrics`);
- `clock_compat.py`: the paper comparison and the lumped cell values;
- `spice.py`: `run`, kind "once", the launcher of an ngspice cross-check of the engine.

## Purpose
A clock is sampled on every edge: an edge that is not monotonic at the receiver is a false edge. The check
answers two questions and keeps them apart:
1. **Calculable**: for the routed topology, what are the edge, the overshoot and the ringback at each receiver,
   and what do the series resistors change (value, position)?
2. **Not calculable**: is the source good enough for the receiver (rise time, duty cycle, accuracy, jitter)? That
   is compared on paper from guaranteed values, then measured.

## When it applies
- Any clock distributed on the board to an input with stated requirements: a reference clock from an oscillator,
  a PHY output or an SoC output (e.g. a 50 MHz RMII reference); oscillator fan-out in a star to two ICs; the clock
  of a serial memory.
- A line much shorter than the edge (under about a tenth of the edge length: edge time divided by the delay per
  mm, about 17 mm for a 1 ns edge at 6 ps/mm) can still ring: the package and resistor inductances ring with the
  load (10.6 % of overshoot on the 7.4 mm validation case with a strong, fast driver). Only the position of the
  series resistor matters less there.

## Inputs to obtain
- **PCB**: topology of the clock net pad to pad: length of each branch, position and value of each series
  resistor, pulls hanging on the line (strap resistors).
- **Impedance check**: Z0 and delay per mm of the routed track on each stackup.
- **Receiver datasheet**: required edge (with its thresholds, 10–90 % or other), duty cycle, frequency accuracy,
  jitter with its definition, input thresholds, absolute maximum input voltage, input capacitance.
- **Source datasheet**: guaranteed edge and its load condition, duty cycle, accuracy (tolerance + temperature +
  ageing over the service life, `pcb-check-crystal` method, Reporting), the supply voltage the figures are given at (a
  "1.8–3.3 V" heading may list the versions sold, not one operating range: ask when it decides), jitter with its
  definition, output impedance or drive strength if given. For an SoC: which PLL feeds
  the output, integer or fractional mode, spread spectrum, drive-strength settings.
- **Vendor reference design**: series resistors on clocks and on data, and on which side.
- **Designer and firmware**: drive strength configured, reset sequencing of a receiver that takes its clock from
  outside (judged in `pcb-check-configuration`, method § "Around the straps"), oscilloscope available (bandwidth,
  jitter floor).

## Method
1. **Line** (`clockline.Net`; `clock_compat.line_cells` prints the cell values): Z0 and delay per mm of the routed
   track from the impedance results of each stackup, both from the same solver run, solder mask as built.
2. **Driver**: rarely documented, so every parameter is an estimate, between a strong, fast stage and the
   datasheet worst case.
3. **Loads**: the published input capacitance of each receiver, otherwise an assumed value bracketed like the
   driver; the pads and the series-resistor bodies; a strap of a few kΩ on the line is noted and neglected.
4. **Stimulus**: one rising edge from 0 to the supply of the driver (the logic swing the receiver sees), in a
   window long enough for the edge and several round trips of the longest branch; ringing that has not settled
   by about half a period is reported (the next edge of the real clock meets it, a single edge does not show it).
   **Cases**: the line as built, each metric at its worst driver (step 5); resistor values and positions, other
   stackups when a result is near its limit or the designer asks, the cases not run written with their reason.
5. **Metrics at each receiver** (`metrics`, `edges`): edge, overshoot, ringback, and the false-edge state **over
   the whole transition, at that receiver's thresholds, on both edges**. Each metric is judged at its own worst
   case: a fast, strong driver for overshoot and false edges, the slowest edge for the rise-time requirement.
6. **Compatibility on paper** (`clock_compat.compare`): source / receiver table of **guaranteed** values, line by
   line (rise and fall time, duty cycle, accuracy, jitter); jitter compared only at equal definition, otherwise
   replaced by a measurement. For an SoC source, the software configuration the receiver's limits require is
   read back in the registers.
7. **Oscillator choice**: table criterion / requirement / candidates (package, total accuracy, edge, duty cycle,
   jitter, current, availability at the assembler); a guaranteed maximum equal to the limit passes without
   margin: say so and put it in the measurements.
8. **Measurement plan** when the paper comparison does not conclude: edge and overshoot per drive strength to fit
   the driver, cumulative jitter in persistence, oscilloscope floor first, then long-duration traffic.

## Criteria
| Criterion | Source |
|---|---|
| Edge (with its thresholds), duty cycle, jitter (each figure with its definition) and frequency accuracy required at the clock input | receiver datasheet, "input clock" or "reference clock" section, table quoted; a requirement the datasheet does not state is written "nothing stated", not assumed |
| No false edge: no ringback through the input thresholds VIL / VIH of that receiver | receiver datasheet, DC characteristics |
| Overshoot within the absolute maximum of the inputs (supply + 0.3 V, usually) | receiver datasheet, absolute maximum ratings |
| Series resistors on clocks first | in-house, mechanism and the place of a reference design in `references/method.md` ("Series resistors: order of priority"); the benefit on a given line (overshoot, false edge, edge cost) is quantified by the sweep |

## Self-checks
- Halve the cell length on the fastest case: the edge must not move and the overshoot by 0.1 point at most.
- The verdict is taken at the worst assumed case, and the report names it.

## Tool contract
Per clock, one short board script, the venv's Python (numpy, scipy), builds the topology, sweeps the cases and writes
`results/<clock>_sim.json`: one row per case (stackup, R_out, internal edge, series resistor value and position) with
the metrics of each receiver and the driver assumption next to them. The lengths come from the JSON written by the
timing script of `pcb-check-timing` (pad-to-pad paths), never typed; resistor values are read from the board. 30 to 200
states, well under a second per case.
- **Paper comparison**: `clock_compat.compare([(name, required, guaranteed), …])`, written to the same JSON with
  its verdict strings.
- **Refusals of the board script**: a length key missing from the timing JSON (`clockline.Net` itself refuses a Z0 or
  delay that is not a finite number > 0).

## Pitfalls
- **Judge the guaranteed values, not the fact that it works.** A prototype that works is one sample of the parts;
  the guarantee covers all of them. A guaranteed maximum above the required maximum, or a guaranteed range wider
  than the required one, fails on paper even on a prototype that works.
- **A computed edge equal to the required one is a zero margin.** It passes only under an assumed driver: it goes
  in the measurements.
- **Choose the position of the series resistor by calculation.** When the line is not electrically short
  (beyond about a tenth of the edge length) the source side damps the reflection from the far end, and the same
  value placed at the receiver end can leave a much higher overshoot; on a short line the position matters less.
  Compute both.

## Limits
- Linear driver, lossless line, no input clamp, a single rising edge: no duty-cycle distortion, no
  steady-state ringing from one period into the next. The falling edge is the mirror of the rising one, which
  assumes a symmetrical output stage.
- The driver is assumed: results rank configurations; absolute edges need the fitted model.
- Jitter is not computed. Crosstalk onto the clock is not modelled.
