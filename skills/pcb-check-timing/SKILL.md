---
name: pcb-check-timing
description: "Setup/hold timing budgets of synchronous interfaces on a PCB, line by line with routed pad-to-pad lengths: common-clock buses (e.g. RMII), controller-to-peripheral serial buses (e.g. SPI serial memory on an SoC). Use also for the relevance of length matching or the maximum clock frequency."
---

# Check: interface timing budgets

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `timing_budget.py`: the budget arithmetic;
- `kicad_routing.py`: `pad_path`, pad-to-pad paths.

## Purpose
Does each line of a synchronous interface meet setup and hold at its receiver, with the routed lengths, the real
clock path and the worst-case datasheet timings, at the frequency the firmware actually configures? This replaces
"the groups are length-matched", which is a means, by the quantity that matters, and gives the highest clock
frequency the board allows.

## When it applies
- Any interface where a clock edge launches data at one device and a clock edge captures it at another: a common
  clock shared by two devices (e.g. RMII between a MAC and a PHY or between two PHYs), a controller and a
  peripheral on a serial bus whose clock the controller drives (e.g. SPI), a serial memory (NOR, NAND, quad) on an
  SoC. Do it even when the expected answer is "not a topic": the budget is what shows it.
- A data rate lower than the clock rate does not remove the check when the clock keeps running at its full
  frequency: the receiver can still sample on the edge that follows a transition, so the budget at the clock
  frequency really applied remains the criterion, unless the interface specification defines otherwise.
- High-speed differential lanes with a forwarded clock (e.g. MIPI DSI): skew inside a pair and between a lane and the
  clock, as a share of the unit interval, against the interface specification, else a stated in-house threshold.
- A DDR3 / DDR3L memory bus: `pcb-check-memory-bus`.
- A link that trains its own sampling point has its training range as the criterion, when it is published.

## Inputs to obtain
- **PCB**: path of each line pad to pad, on both sides of its series resistor; vias crossed and, when a line reaches
  an inner layer, the layers each joins; value of each series resistor (read from the board, not typed).
- **Schematic**: the list of lines of each interface, the clock source and its fan-out, the pulls and branches
  that are not on the signal path.
- **Datasheets** (table and symbol for each value): output delay after the clock, minimum and maximum; input
  setup and hold; minimum clock period; minimum clock high and low times or duty cycle; input capacitances;
  the load and supply the values are given at. For the controller, the options that move its sampling point and
  their conditions.
- **Firmware**: the frequency and mode really configured (clock tree, prescaler, clock polarity and phase,
  sampling edge, delay line), read in the source of the builds in scope, with file and line.
- **Impedance check**: delay and capacitance per mm of the routed track. **Designer**: what was measured or run on
  a prototype, and under which conditions.

## Method
1. **General budget**: every line is a launch at the transmitter, a path, a capture at the receiver; its setup and
   hold come from the time between the launching and capturing edges, read on the waveform of the mode in use, the
   clock delays to both ends, the output delay and the delay of the line. The next steps apply it to three
   families.
2. **Delay of a line** (`line_delay`): flight on the routed path and its vias, plus the crossing of the series
   resistor's RC at the receiver's thresholds. RC is not a bound, and both polarities count. A via to an inner layer
   crosses less than the board: with a via count, the hold uses the flight without the vias (`flight_min`).
3. On a **clock** line the delay helps one margin and hurts the other: every margin is evaluated at both ends of the
   clock delay, and the worst is kept.
4. **Common-clock interface** (e.g. RMII; `rmii_margins`, `common_clock_margins`): clock delays to the two devices
   and their skew, then one row per line and direction.
5. **Unpublished controller**: complete budget on the published side, the interface specification's values as a
   stated estimate on the controller side, and the window its output delay must fall in
   (`output_delay_window`).
6. **Controller-driven serial bus, mode 0** (e.g. SPI; `spi_mode0_margins`): **t_w is the minimum high or low time
   of the clock, not T/2**. Read it in the controller's datasheet, give the margin at 50 % next to it, the lowest
   duty cycle that still holds and the limit frequency; a controller option that samples later enters with its
   conditions of use. The same t_w against the peripheral's minimum clock high and low times
   (`pulse_width_margins`).
7. **Serial memory, mode 0 single data rate** (`serial_memory_margins`): write margins at the memory, read window,
   margins per sampling edge given **before the SoC**, limit frequency.
8. **A layout guide's matching rule is an input, not the verdict.** Each manufacturer writes its own tolerances and its
   own definition of length (track only, or die to die with package and via). Copy the value, the source and that
   definition into the board table, then give three answers, never merged: the rule **as the guide writes it** ("not
   judgeable" when a term it counts is unknown, e.g. package lengths available on request); the **margin in time**; what
   **remains unknown** and has to share that margin.

## Criteria
| Criterion | Source |
|---|---|
| Setup and hold margins ≥ 0 on every line, worst case of the datasheets, at the configured frequency | datasheets of both ends |
| Clock period ≥ minimum period of the peripheral | its datasheet |
| Clock high and low times ≥ the receiver's minimum high and low times, on the shorter time the source guarantees (duty_min × T, `pulse_width_margins`) | datasheets of the source (duty cycle or minimum high / low time) and of the receiver |
| Rule of a layout guide, as it defines it | the guide, with section; judged apart from the margins, "not judgeable" when a counted term is unknown |
| Spread of line delays and clock skew inside the budget, not length matching as such | in-house: each line is judged against the clock; a matching rule of a layout guide is judged by what it costs in margin |

The constants are those of the datasheets of the parts on the board, each with document, table and symbol; a timing
missing from the electrical tables may sit in a section named after the interface. Where a part publishes none,
the interface specification may supply an estimate (e.g. the RMII specification for the input setup and hold;
values commonly used are of the order of 4 ns and 2 ns at 50 MHz, to be confirmed in the applicable edition),
labelled indicative. With a maximum output delay only, setup is computed and hold is "not demonstrable": give the
minimum delay the hold needs. A receiver setup or hold that neither the part nor the specification gives leaves the
line incomplete: it is not taken as 0.

## Self-checks
- Hold terms use the earliest arrival and setup terms the latest; check the sign of the skew on one line by
  hand in each direction (a positive Δ helps the setup of the line whose receiver sees the clock later and hurts
  the setup of the opposite direction).

## Tool contract
One script per interface family, KiCad's bundled Python (it reads the board): `timing_budget.py` →
`results/timing_budget.json`, `memory_timing.py` → `results/memory_timing.json`.
- **JSON**: per line length, flight, RC, latest, earliest; the clock delays and skew; one row per line and
  direction with setup, hold, window; per frequency the SPI margins, limit frequency, lowest duty cycle that
  holds, the MISO terms, the clock high and low margins; the serial memory margins per sampling mode; the assumptions
  block.
- **Refusals of the board script**: a pad or path not found, an unreadable resistor value, a line of the schematic
  missing from the table.

## Pitfalls
- **Budget each line against the clock; length matching is a means, not the criterion.** On a common-clock
  interface there is no relation between lines, only between each line and the clock. On a bus whose data are
  captured by a strobe or a clock sent with them, the data-to-data and data-to-strobe skew enter the budget
  through d_max − d_min and the clock path; a matching rule is judged by what it costs in margin.

## Limits
- Delays are flight times on uniform tracks plus a first-order RC: no edge shape, no reflection (see
  `pcb-check-clock-integrity` for the clock edge), no crosstalk.
- Clock jitter is not in the budget. The duty cycle is, where the controller publishes it; a clock high or low
  time carried in proportion from another frequency is an estimate.
- Datasheet values at other loads than the board's are used as published.
- With unpublished controller timings the verdict is on the routing only; the interface is proven on the
  prototype.
