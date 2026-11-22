---
name: pcb-check-pdn-ir-drop
description: "DC voltage drop (IR drop) of power rails on the real copper of a KiCad PCB, from the regulator output to each load pin (SoC, memory, analogue supply), by a resistive mesh of zones, tracks, vias and pads."
---

# Check: DC voltage drop of the rails (PDN)

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `kicad_copper.py`: `rail_copper`, `rail_links`, `rail_pad`;
- `irdrop2d.py`: `raster`, `solve_rail`: the mesh solver;
- `copper_dc.py`: sheet resistance, via barrel, single-track hand formula, temperature factor.

## Purpose
The feedback of a regulator senses the voltage at its inductor or output pad, not at the load: the drop in the
copper between the two is not compensated. This check computes that drop on the real copper of each rail and
verifies that the worst-case regulated voltage minus the drop stays inside the range of the load.

## When it applies
- Low-voltage rails with a narrow range (SoC core, DDR), rails routed on few layers or through necks, loads of
  several hundred milliamperes: the drop can consume the whole set-point margin.
- A rail at a few volts carried by continuous planes to loads of the order of 100–200 mA typically drops well under
  a few millivolts: the check is then quick and closes the question with a number. Compute it, do not assume it.

## Inputs to obtain
- **PCB** with zone fills up to date and saved; KiCad closed, or a copy refilled in the scratchpad.
- **Stackup and fabricator files**: copper thickness and z position of each layer (barrel length), via plating
  (`../pcb-verification/assets/stackups/`, `assets/fabricators/`).
- **Scope**: the copper temperature (step 8).
- **Per rail**: net name; the source pad (output pad of the inductor of a buck, output pin of an LDO: the point
  the feedback regulates); the load pads (supply pins of each consumer; for a supply behind a ferrite or a
  resistor, the pad of that part on the rail).
- **Currents** per load: datasheets at the real mode, typical and maximum; envelope values when unpublished; the
  designer's measured total as a second case.
- **Regulated minimum** of each rail from `pcb-check-power-rails`, the range of the load (datasheet), the
  regulator's load regulation for comparison.

## Method
1. **A single track** from one pad to another needs no mesh (`copper_dc.track_resistance`,
   `via_barrel_resistance`). The mesh is for planes, pours and several loads sharing copper.
2. **Copper of the rail, per layer** (`rail_copper`): everything that carries the net, graphic polygons with the net
   included; a barrel with no pad on a layer does not connect it.
3. **Inter-layer links** (`rail_links`): vias and plated through-hole pads (a slot: the round hole of the same wall
   length).
4. **Mesh** (`raster`): square cells of side d, of the order of 50–80 µm.
5. **Vias**: a barrel of the fabricator's plating between the consecutive layers where the rail has copper at that
   point.
6. **Boundary conditions**: the source pad at 0 V; each load draws its current over the cells of its pad(s); an IC
   with several supply pins shares its current equally unless the datasheet says otherwise.
7. **Solve** (`solve_rail`): the drop at each load pad, and the equivalent resistance of the rail.
8. **Temperature**: the drop scales with the copper resistance at the copper temperature of the scope
   (`copper_dc.temperature_factor`).
9. **Convergence**: repeat at d / 2, derived in code from d.
10. **The return**: solved as a rail when the ground between regulator and load is not a continuous plane (a neck,
   a split, a connector, a return shared with a heavy load); over a continuous plane, a bound is enough. A rail
   whose margin is consumed by the return bound is solved, not passed.

## Criteria
| Criterion | Form | Number read in |
|---|---|---|
| Rail at the load | regulated minimum − (maximum supply drop + return drop) at the copper temperature of the scope ≥ minimum of the load's range; the load sees VDD_local − GND_local | load datasheet; regulated minimum from the set-point check of the current board |
| Comparison | drop against the regulator's load regulation | regulator datasheet |
| Convergence | halving the cell changes the worst drop by less than 10 % | in-house rule |

## Self-checks
- **No island**: a load on copper with no path to the source stops the solver; it means a link is missing from the
  model (via touching a pad with no track, through-hole pad, graphic fill not read): fix the export, do not move the
  load.
- **Inventory before filtering**: count the objects of each class on the rail (tracks, arcs, vias, zones, graphic
  shapes with a net, which an import can make of zone fills) and print it; a class at zero that the board uses is a
  reader bug.

## Tool contract
Two scripts, one JSON each in `results/`.
- **Export**, KiCad's bundled Python → `results/pdn_geometry.json`: per rail `layers` (per layer, polygons `{"outline",
  "holes"}`, mm), `vias` (x, y, drill), `source` and `pads` (reference, pad, `rail_pad`: centre, bounding box, layer and
  the outline of the pad's copper, by which the solver selects its cells).
- **Solver**, venv (numpy, scipy, matplotlib) → `results/pdn_ir.json`: per rail and case, total current, drop per load
  pad at both meshes, worst drop and worst drop × the temperature factor, equivalent resistance, vias linking at least
  two layers, nodes, low margin and remainder; and a map of the drop in mV on each outer layer, with the loads and the
  source annotated.
- **Refusals of the board script**: a load declared without its pad whose component has several pads on the rail.
- Cost: the export takes seconds; a rail of some 10⁴ mesh nodes typically solves in well under a second.

## Pitfalls
- **Do not assume the highest current gives the worst rail.** A low-voltage rail at a smaller current can have a
  higher equivalent resistance (fewer layers, necks) and a thinner margin: judge every rail by the remainder.

## Limits
Equal current per pad cell, and per pin where the datasheet gives no split. Nominal copper thickness without
plating over-thickness on the outer layers, the fabricator's plating and a uniform temperature are assumptions; the
DCR of a ferrite or inductor between the rail and a pin is not included (add it by hand).
