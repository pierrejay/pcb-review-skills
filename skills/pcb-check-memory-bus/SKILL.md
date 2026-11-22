---
name: pcb-check-memory-bus
description: "First-order check of a parallel memory bus on a PCB with one DDR3/DDR3L chip point-to-point, up to 1066 MT/s: byte-lane wiring and the exchanges the layout guide allows, line delays in time per layer and via, setup/hold margins of each line against its clock or strobe. Use also to judge a layout guide's length-matching rule on such a bus."
---

# Check: parallel memory bus

Read `../pcb-verification/SKILL.md` first; the general budget and the judging of a layout guide's matching rule are
those of `../pcb-check-timing/SKILL.md` (Method, steps 1 and 8).

## Resources
In `../pcb-verification/lib/`:
- `timing_budget.py`: `byte_lane_wiring`, `via_transit`, `centred_window_margins`;
- `kicad_routing.py`: `pad_path`, with the layers each via joins (`via_layers=True`);
- `fieldsolver2d.py`, `stripline2d.py`: delay per millimetre of an outer and an inner layer.

## Purpose
Is each byte lane wired whole to one memory lane, and what share of its window does the routing take from each line,
against its clock or strobe? Necessary, not sufficient: the training run and the memory test decide.

## When it applies
One controller and one DDR3 or DDR3L chip, point-to-point (address and command lines unterminated or with series
resistors only), up to 1066 MT/s. Fly-by, several chips, ranks, DDR4 and later are not covered.

## Inputs to obtain
- **PCB**: path of each line pad to pad, per section and layer; the layers each via joins; the stackup.
- **Schematic and pins**: lanes of the controller (data bits, mask, strobe pair), address, bank, command and clock.
- **Datasheets**: the memory's setup, hold and read window at the speed grade and input level in use; what the
  controller corrects (leveling, per-byte or per-bit delays); the layout guide's exchanges, matching rule and its
  definition of length.
- **Firmware**: data rate and command timing mode.

## Method
1. **Wiring first** (`byte_lane_wiring`): each lane (data bits, mask, strobe pair) whole on one memory lane, read from
   the pins; address and command lines bit to bit; the exchanges allowed are the guide's, per memory type
   (`references/method.md`). Matching is judged inside a lane, against its own strobe.
2. **Lengths in time** (`via_transit`): delay of each line = sum over its sections of length × the delay per mm of
   that layer and mode, from the solvers (a pair's odd mode is not a single trace's delay), plus each via at the height
   it crosses.
3. **Margins** (`centred_window_margins`): for each line, its signed offset to the clock or strobe, setup, hold and
   the share of the free window. A share of the order of a percent closes the question, whatever the sign; one of the
   order of 10 % or more deserves the unpublished terms and, for a fast bus, a channel simulation.

## Criteria
| Criterion | Source |
|---|---|
| Each memory lane whole, its exchanges and the address lines as the guide allows for this memory type | layout guide, memory datasheet |
| Setup and hold margins ≥ 0 before the controller, against the clock or strobe | memory datasheet |
| Rule of a layout guide, as it defines it | the guide, with section; "not judgeable" when a counted term is unknown |

## Self-checks
- One line with no stub: its path equals the copper of its net, less the pad entries. A shorter path is a shortcut
  in the tool or a real branch: look at it before using it.

## Tool contract
One board script, KiCad's bundled Python → `results/memory_bus.json`: the lane mapping and its errors; per line the
sections per layer, vias, delay, offset, setup, hold, share; the assumptions block. Refusals: a net not found on the
memory, a pad or path not found.

## Pitfalls
- **"The clock arrives last" is a means, not a law.** The offset that balances setup and hold is (t_su − t_h) / 2: its
  sign follows the memory's requirements and input level. Compute the margins in both directions.
- **Compare lengths on one definition, in time.** An inner layer, an outer layer and a pair have different delays, and a
  via is crossed at its real height. A figure read in a CAD tool may or may not count vias and stubs: check it.

## Limits
- First order: flight times and a centred window; no reflection, crosstalk or channel effects.
- Unpublished controller uncertainties, package delays and derating with the edge rate share the margins computed;
  the training run and the memory test decide.
