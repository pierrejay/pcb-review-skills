# Clock integrity: method in full, the engine, board table, validation, measurement plan, reporting

## Simulation of the edge
- **Line**: lossless, cut into L-C cells of 0.5 mm: L_cell = Z0·tpd·d, C_cell = tpd·d / Z0 (`clockline.Net`
  computes them; `clock_compat.line_cells(z0, tpd, dseg)` returns the same values and the cell count for a script
  that only prints them). Z0 and the delay per mm come from the impedance results of each stackup built, for the
  track width as routed. A delay computed without solder mask is lower than the one with the mask (by several
  per cent for a microstrip): take Z0 and delay from the same solver run, with the mask as built. The delay of a
  microstrip on an FR-4-type laminate is of the order of 6 ps/mm (sqrt(eps_eff) / c), which catches an absurd
  value.
- **Driver** (rarely documented, to be fitted on a measurement): ideal ramp source behind R_out and a package
  inductance (e.g. 0.5 nH). R_out of the order of 25 Ω for a typical output stage and 10 Ω for a strong one are
  plausible starting values; internal edge (10–90 %) e.g. 0.5 ns and 1 ns as plausible values, plus the
  datasheet worst case.
- **Loads**: published input capacitance (e.g. 1 pF for the clock input of a PHY) + pad (e.g. 0.3 pF); unpublished
  input: an assumed value (e.g. 5 pF). Driver pad e.g. 0.3 pF; each series-resistor pad e.g. 0.2 pF;
  resistor body e.g. 0.3 nH. A strap of a few kΩ on the line is noted and neglected: it is far above Z0.
- **Stimulus**: one rising edge from 0 to the supply of the driver, observed in a window set from the period:
  the start of the ramp (1 ns) + tr / 0.8 + several round trips of the longest branch (2·tpd·length each);
  `simulate(..., vdd, t_end)`. Ringing that has not settled by about half a period is met by the next edge of the
  real clock, which a single-edge simulation does not show: report it rather than lengthen the window.
- **Sweep**: the cost of a series resistor on the edge is of the order of 2.2·R·C (10–90 %) for R in front of a
  total load C, combined roughly in quadrature with the driver's edge: the simulation gives the exact value, this
  one screens it.
- **Metrics at each receiver**: edge 10–90 %; overshoot in % of the supply; lowest voltage after the edge has
  reached 90 % (ringback, displayed).
- **Step back ignored** (`back_max` of `edges` and `metrics`): 10 mV by default, a tolerance for the numerical
  noise of a simulated waveform. A larger value only from a hysteresis the receiver's datasheet guarantees, written
  in the results next to the false-edge state.
- **False edge: the whole transition, at the thresholds of that receiver, on both edges.** Rising: no step back
  inside the VIL–VIH band, and no return below VIH once it is passed. Falling: the same on the mirrored waveform
  (supply − v; valid for a linear network with a symmetrical driver, which is an assumption): no step back
  inside the band, and no return above VIL once it is passed. Both polarities go through the same function: an
  edge that enters the band, goes back out the way it came, then completes, is "band" (receiver-dependent),
  never clean. The two edges do not have the same margin when the thresholds are not symmetrical about the
  middle of the swing: once the fall has passed VIL, a bounce of VIL / VDD of the swing re-enters the band,
  while once the rise has passed VIH it takes a dip of (VDD − VIH) / VDD to do so. With low thresholds such as
  0.6 / 1.2 V on a 3.3 V swing, that is 18 % for the fall against 64 % for the rise: the falling edge is the
  sensitive one.

## Compatibility on paper (`clock_compat.compare`)
A table source / receiver with the **guaranteed** values, line by line: rise and fall time, duty cycle, frequency
accuracy, jitter. A guaranteed value outside the required range fails the rule; the effect is unknown until
measured. Two jitter figures are compared only when they have the same definition (RMS, period to period,
cumulative over n periods, long term). For an SoC generating the clock from a PLL, write what the documentation
gives and what it does not (output jitter, rise time and drive impedance are usually missing), and what the
software must guarantee: the source configuration that the receiver's jitter and accuracy limits require (e.g.
PLL in integer mode, spread spectrum off on the PLL that feeds the clock output), read back in the registers under
the running operating system.

## Measurement plan (when the paper comparison does not conclude)
1. Same clock configuration and same output path as the product.
2. Edge, overshoot and duty cycle at each receiver for each drive strength: the edge and the overshoot fit the
   driver model, which is then used to simulate the product's line with and without the series resistor.
3. Cumulative jitter: trigger on an edge and observe, in persistence, the edge N periods later (e.g. N = 10 000,
   i.e. N / f: 200 µs at 50 MHz); the width of the trace gives the order of magnitude. Measure the oscilloscope's
   own floor first on a crystal oscillator.
4. A jitter limit near or below the floor of the oscilloscope can only be bounded from above: a general-purpose
   oscilloscope does not resolve an RMS jitter of a few tens of ps (e.g. 40 ps), and the measurement then gives
   an upper bound.
5. Final proof on the prototype: long-duration traffic, signal-quality indicator and error counters of the
   receiving device, where it has them.

## Series resistors: order of priority
Clocks before data. A clock runs permanently, is sampled on every edge, and, being periodic, concentrates its
emission at the harmonics of its frequency. A data line has a finite window to settle, judged by
`pcb-check-timing`, and its edges are not repeated at a fixed rate. A vendor reference design may put series
resistors on the clocks at the source and none on the data: it is a known-good starting point (judged as in
`pcb-verification/references/qualitative-rules.md`), not a criterion; the sweep decides for
the line at hand, from the overshoot, the false-edge state and the edge cost it gives.

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract". The board table below is what the board script
declares.

### Board table
| Declaration | Content |
|---|---|
| topology | segments in order, each with its length key in the timing JSON; series resistors with value read from the board; star point |
| line | (Z0, delay per mm) per stackup, from the impedance results |
| driver assumptions | list of (R_out, internal edge), each labelled plausible or datasheet worst case; package inductance |
| loads | input capacitance of each receiver with its source or "assumed"; pad capacitances |
| thresholds | supply, input thresholds of the receiver, required edge, with datasheet section |
| sweep | series values and positions to compare |
| paper rows | (name, required, guaranteed) per quantity, with the datasheet section of each figure |

### The engine (what `clockline.py` computes)
- **Network**: node capacitances to ground and series R-L branches between nodes; node −1 is the ideal source.
  `line(a, length, c_end)` chains max(1, round(length / 0.5 mm)) L-C cells and loads the last node: the length
  is rounded to a whole number of cells (error ≤ 0.25 mm).
- **Topology**: source —(R_out, L_pkg)→ driver pad → line → pad —(R_series, 0.3 nH)→ pad → line → receiver.
  A resistor at the source is a branch straight from the driver pad. A star: several branches from one node.
- **Solution**: state = node voltages then branch currents; `scipy.signal.lsim`, exact for the ramp input
  (starts at 1 ns, lasts tr / 0.8 so that its 10–90 % time is tr), 1 ps step, 12 ns by default.
- **Metrics**: 10 % and 90 % crossings by interpolation; overshoot = (max − supply) / supply; ringback = lowest
  sample once 90 % is reached (2.97 V at 3.3 V means "no dip"); false edges by `edges`, with the thresholds of
  each receiver read in its datasheet (e.g. 0.6 / 1.2 V for a low-threshold clock input, 0.8 / 2.0 V for an LVTTL
  input).
- **Rebuilding it another way** is legitimate (a SPICE deck with ideal lossless lines of the same Z0 and delay):
  the validation cases below then apply unchanged, and the false-edge detector is still needed on the waveform.

## Validation cases of the engine
Inputs are fully given so that a rebuilt engine can replay them: 3.3 V supply; line of Z0 51 Ω and 5.7 ps/mm
(plausible values for a microstrip); pads and inductances as above. Expected values are
those of the ladder with 0.5 mm cells.

| Topology | Case | Expected at the receiver |
|---|---|---|
| Point to point: 4.4 mm (0.3 pF) → R → 3.0 mm → 1.3 pF | R_out 25 Ω, edge 1 ns; R = 0 / 22 / 33 Ω | edge 0.98 / 0.99 / 1.00 ns; overshoot 2.3 / 0.8 / 0.2 % |
| same | R_out 10 Ω, edge 0.5 ns; R = 0 / 22 / 33 Ω | overshoot 10.6 / 5.4 / 3.5 % (same topology on a line of Z0 73 Ω and 5.6 ps/mm: 10.1 / 6.6 / 4.9 %) |
| same | R_out 25 Ω, edge 4 ns | edge 4.00 ns, overshoot ≤ 0.6 % |
| Star at the driver pad: 0.7 mm → R → 11.5 mm → 1.3 pF, and 5.4 mm → R → 8.3 mm → 5 pF | R_out 25 Ω, edge 1 ns, R = 0 | 1.18 ns, 3.1 % and 0.98 ns, 1.4 % |
| same | R = 33 Ω in each branch | 1.28 ns and 1.25 ns, no overshoot |
| same | edge 3.8 ns, R = 33 Ω | 3.84 ns on both |
| 13.8 mm → 5 pF, R at the source or after 11.8 mm | R_out 10 Ω, edge 0.5 ns, no R | 0.37 ns, overshoot 29.1 %, then 0.52 V under the supply |
| same | 22 Ω at the source / 22 Ω at the receiver / 33 Ω at the source | overshoot 4.2 / 8.7 / 0 % |

## Reporting
- A table of cases per receiver (edge, overshoot in volts and %, ringback) and the waveforms of the worst case
  with and without the series resistor, with the thresholds drawn.
- The paper comparison as a table source / receiver, each line with its verdict.
- The list of assumptions on the driver, as estimates, and the measurement that would replace each.
- For a deviation, the correction names the resistor, its value and its side, or the clock architecture.
- Fallback architectures when a source cannot be shown compatible, as a table with their side effects:
  - one oscillator feeding all the receivers (no strap, no register, clock present at power-up; the duty cycle
    and jitter are then those of the oscillator, chosen against the strictest receiver, and the fan-out is
    simulated as a star);
  - a receiver acting as clock master from its own crystal and feeding the other (the master / slave role is
    often selected by a strap or a register, and the strap pin may be shared with another function such as an LED,
    which changes its polarity, or needs a register write);
  - the same master fed by a clock output of the SoC: it brings back the SoC jitter that was the unknown, so it
    is discarded when that is the reason for the change.
