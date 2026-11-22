# Interface timing budgets: method in full, board table, algorithm, reporting

## General budget
A line is a launch at the transmitter, a path, a capture at the receiver. Let L be the launching device and C the
capturing one, t_cL and t_cC the clock delays to each, Δ = t_cC − t_cL, t_out (min, max) the output delay after the
launching edge, d (min, max) the delay of the line, t_su and t_h the setup and hold of the receiver. S is the time
from the launching edge to the capture edge that must catch the data; S_h is the time from the capture edge of the
previous data to the launching edge (0 when launch and capture are on the same edge). Then

- setup = S + Δ − t_out,max − d_max − t_su;
- hold = S_h − Δ + t_out,min + d_min − t_h.

S and S_h come from the waveform of the mode in use: T and 0 for a common clock; the clock high or low times for a
mode that launches and captures on opposite edges (they are not T/2 unless the datasheet says so); a whole period
for a capture a full cycle later. The three families below are this budget with their own S, S_h and what is
unknown. A device whose output delay is not published contributes t_out = 0 (the margin is then "before" that
device) or an estimate, and the window its output delay must fall in is given.

## Delay of a line (`timing_budget.line_delay`)
- Flight time = (track length of the path + height crossed by each via) × delay per mm. A via that leaves for an
  inner layer crosses less than the board: given a via count, the latest arrival takes the board thickness per via
  and the earliest none; given the heights each via crosses (the layers it joins, `pad_path(..., via_layers=True)`,
  in the stackup), both use them.
- Series resistor: RC = R × (input capacitance of the receiver + capacitance of the track after the resistor).
  A rising input is seen high after −ln(1 − VIH/V)·RC, a falling one low after −ln(VIL/V)·RC: 1.204·RC both ways
  at 0.7 / 0.3 of the swing (CMOS thresholds), but 0.931 rising and 1.417 falling at 2.0 / 0.8 V on 3.3 V. **RC is
  not a bound**, and both polarities count: the thresholds are input data (`vih`, `vil`, fractions of the swing).
  The driver's charge of its own test load is already in the datasheet's output delay; this term is the resistor
  added.
- **Data line**: latest arrival (setup terms) = flight + the larger of the two crossings; earliest arrival (hold
  terms) = the shortest flight alone (`flight_min`).
- **Clock** of a source-synchronous or common-clock link: its delay helps one of setup and hold and hurts the
  other (`clock=True`): its earliest arrival is the shortest flight plus the first crossing,
  min(−ln(1 − VIL/V), −ln(VIH/V))·RC, the RC taken with the track capacitance of the shortest path (`rc_min`: the
  vias of a count at their smallest crossing); evaluate
  every margin at both ends of the clock's delay (`rc_low`, `rc_high`), keeping the worst. A single value in
  between (the 50 % estimate) is optimistic on one side.
- **Delay and capacitance per mm** come from the solver result of `pcb-check-impedance`, with solder mask, for the
  stackup of the board: delay per mm of the order of 6 ps/mm for an outer-layer microstrip on FR-4 (√ε_eff / c),
  capacitance per mm = delay per mm / Z0. The value without mask is a few percent lower; on a flight time of a
  tenth of a nanosecond the difference is small, but take the one with mask.
- **Input capacitance not published**: an estimate, stated as such, given as a bracket (e.g. 2 to 10 pF for a
  digital input) with both ends run. The delay it moves is about 1.204 · R · ΔC at CMOS thresholds (22 Ω and a
  bracket of 8 pF: about 0.2 ns); the verdict is taken at the pessimistic end.

## Common-clock interface (e.g. RMII, 50 MHz, T = 20 ns) (`rmii_margins`, `common_clock_margins`)
Clock delays from the source to the PHY (t_cP) and to the MAC (t_cM), each with its series resistor; skew
Δ = t_cM − t_cP (positive: the MAC sees the clock after the PHY). When one IC generates the clock for the other,
its own delay is zero. With d_max and d_min the latest and earliest arrival of the line, S = T and S_h = 0:

| Direction | Setup margin | Hold margin |
|---|---|---|
| PHY → MAC | T + Δ − t_out,max(PHY) − d_max − t_su(MAC) | t_out,min(PHY) + d_min − Δ − t_h(MAC) |
| MAC → PHY | T − Δ − t_co,max(MAC) − d_max − t_su(PHY) | t_co,min(MAC) + d_min + Δ − t_h(PHY) |

A datasheet that gives a maximum output delay only (`t_out_min` None) gives `hold` None: the lower bound of the window
below is the minimum delay the hold needs. A controller whose timings are not published: complete budget on the
other side; on the controller side, the values of the interface specification as a stated estimate (indicative,
edition to confirm), **and the window its output delay must fall in** (`output_delay_window`): t_h(PHY) − d_min − Δ ≤ t_co ≤ T − Δ − d_max − t_su(PHY).

## Controller-driven serial bus, mode 0 (e.g. SPI) (`spi_mode0_margins`)
Launch on the falling edge, sampling on the rising edge. With t_c the SCLK delay to the peripheral and d the
delay of each data line:

| Line | Setup margin | Hold margin |
|---|---|---|
| MISO | t_w − t_c − t_dv(peripheral) − d_max − t_su(MI) | t_w + t_c + d_min − t_h(MI) |
| MOSI | t_w − t_v(MO) − (d_max − t_c,min) − t_su(peripheral) | t_w + (d_min − t_c) − t_h(peripheral) |

**t_w is the minimum high or low time of the clock, not T/2.** A controller datasheet may publish it as a time at
a given frequency or as a duty-cycle range, and the high and low times can differ. Read it there, say how it is
carried to the frequency in use (in proportion: an estimate, to be listed; `duty_min`, the shorter of the two
times over the period, hence 0.5 at most: a 45–55 % range gives 0.45), give the margin at 50 %
next to it, and **the lowest duty cycle that still holds** (`duty_min_holding`). Measurement that settles it: the
clock low time on the oscilloscope.
**Clock high and low times at the peripheral** (`pulse_width_margins`): t_w against its minimum high and low times
(e.g. tCH, tCL, tWH); a negative margin fails whatever setup and hold give.
Limit frequency = min(k / (t_c + t_dv + d_max + t_su(MI)), 1 / minimum period of the peripheral), k being the
minimum duty cycle (0.5 only for an ideal clock). An option of the controller that samples half a period later
enters the budget as t_su(MI) − T/2 and a hold requirement raised by T/2, with its conditions of use (read them in
the controller's reference manual: it may exist only for some divider settings); launch and sampling are then on
two falling edges, the whole period counts and the duty cycle drops out (`sample_half_period_later=True`: setup =
T − t_c − t_dv − d_max − t_su(MI), hold = t_c + d_min − t_h(MI)).

## Serial memory on an SoC (mode 0, single data rate) (`serial_memory_margins`)
With t_c the clock delay to the memory (tracks + series resistor) and d_min, d_max over the data lines:
- Write: setup at the memory = T/2 − (d_max − t_c) − tDVCH; hold = T/2 + (d_min − t_c) − tCHDX (T/2 for want
  of a published duty cycle of the SoC clock: give the duty cycle at which the setup reaches zero, `duty_zero`).
- Read: the memory changes its outputs between tCLQX and tCLQV after the falling edge it receives. At the SoC,
  the data are valid from t_open = t_c + d_max + tCLQV to T + t_c + d_min + tCLQX after the falling edge sent: a
  window of T − (tCLQV − tCLQX) − (d_max − d_min).
- Sampling on the next rising edge: setup left for the SoC = T/2 − t_open; limit frequency 1 / (2·t_open).
  Sampling on the next falling edge: setup left = T − t_open, hold left = t_c + d_min + tCLQX.
- Clock high and low times at the memory: as for the serial bus (`pulse_width_margins`), with duty_min 0.5 for an
  unpublished SoC duty cycle, stated as an estimate, and the duty cycle at which the margin reaches zero (minimum
  high or low time / T).
- SoC timings are often not published: the margins are given **before the SoC** (what is left for its input
  setup and hold and its output dispersion), per sampling mode, with the limit frequency. The verdict then bears
  on what the routing consumes; the criterion states what the controller covers (delay line calibrated by
  software, sampling edge), and the missing SoC timings are listed as an estimate.

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

### Board table
| Declaration | Content |
|---|---|
| lines | per line, the list of (net, start pad, end pad) in the signal direction: one tuple per net, before and after the series resistor |
| series resistor | reference per line; the value is parsed from the footprint's Value field, and an unreadable value stops the script |
| end capacitance | per line, the input capacitance of its receiver, with source or "estimate" |
| datasheet constants | output delays, setup, hold, minimum period, minimum clock high and low times: each with document, table and symbol in a comment |
| assumed constants | timings taken from a specification for an IC that publishes none: flagged as estimates |
| frequencies | one entry per firmware build or clock setting, with the file it was read from |
| delay and capacitance per mm, board thickness | from the impedance results and the stackup |

### Algorithm
1. Load the board, group tracks (segments and arcs) per net.
2. For each line and each of its nets: legs of the path between the two pads, vias crossed; track length = sum of
   the leg lengths (the part of a segment actually travelled, not the whole track at a T-junction), the vias
   counted apart. Keep upstream and downstream lengths apart.
3. Delay of the line (`line_delay(track length, vias, board thickness, …)`, which adds the vias once: a count
   bounds each between 0 and the board thickness, the list of heights crossed gives both arrivals): flight and
   shortest flight; RC with the downstream length; store length (vias included, as returned), flight, RC and total.
4. Clock paths first, then the skew; then one budget row per data line with the formulas above, in both
   directions (`rmii_margins`).
5. For an unpublished controller: the admissible output-delay window per line (`output_delay_window`).
6. Serial bus (`spi_mode0_margins`): margins per configured frequency, the limit frequency, and the MISO setup
   budget **term by term** (half period or minimum low time, clock path, t_dv, return path, t_su) for each
   setting, including the candidate remedies (lower prescaler, sampling option); the clock high and low margins
   (`pulse_width_margins`).
7. Serial memory (`serial_memory_margins`): write, window, rising-edge and falling-edge sampling per frequency.
8. Write the JSON with the assumptions block (delay per mm, capacitances, estimated timings) next to the results.

## Reporting
- A table per interface: line, length, delay, setup margin, hold margin; a bar chart of the margins with the
  zero line; the limit frequency; the admissible window of an unpublished controller.
- A negative margin is written with its cause term by term, what it concerns (which build, which mode), the precise
  correction (file, line, value) and the gain.
- Say which case the budget covers (worst case of the datasheets) and which case a working prototype proves
  (typical parts, room temperature).
- Measurements to request: clock and data at the receiver on the prototype; long-duration traffic with error
  counters; for a calibrated delay line, the boot log showing that the calibration succeeded and did not fall
  back to a lower frequency.
