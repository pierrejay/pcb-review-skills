# PDN voltage drop: method in full, board table, algorithm, validation, reporting

## 1. Method, step by step
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers.

1. **A single track** from one pad to another: R = ρ × length / (width × thickness), plus the resistance of each
   via barrel (step 5).
2. **Copper of the rail, per layer**: union of everything on the net: filled zones, tracks (straight and arcs),
   via pads on the layers where they are flashed, solid fills drawn as graphic polygons carrying a net, pads.
3. **Inter-layer links**: vias and through-hole pads of the net, with their drill diameter (a slot: the round
   hole of the same wall length, perimeter / π; its length would overstate the barrel).
4. **Mesh**: each layer is cut into square cells of side d. Between two neighbouring copper cells the conductance
   is the sheet conductance G = t / ρ (independent of d for square cells). Sheet resistance ρ / t: e.g. 0.49 mΩ per
   square for 35 µm of copper, 1.13 mΩ per square for 15.2 µm.
5. **Vias**: a plated barrel of thickness p (the plating of the fabricator file; e.g. 20 µm), cross-section
   π × (drill + p) × p, links the consecutive layers on which the rail has copper at the via position; its length
   is the distance between those layers. E.g. a 0.3 mm drill through 1.53 mm with 20 µm plating is 1.31 mΩ.
6. **Boundary conditions**: the cells of the source pad are held at 0 V; each load draws its current, spread
   equally over the cells of its pad(s); an IC with several supply pins on the rail shares its current equally
   between them unless the datasheet says otherwise. The cells of a pad are those whose centre lies inside the
   outline of its copper, not inside its bounding box, which on a rotated pad covers neighbouring copper.
7. **Solve** Ohm's law on the network (sparse linear system) and read, for each load pad, the mean voltage of
   its cells: the drop. Equivalent resistance of the rail = worst drop / total current.
8. **Temperature**: ρ = 1.72 × 10⁻⁸ Ω·m at 20 °C, × (1 + 0.00393 × (T − 20 °C)); every resistance of the network
   scales together, so the drop is multiplied by the same factor (× 1.1965 at 70 °C).
9. **Convergence**: the same rail meshed at d and at d / 2, and the two worst drops compared.
10. **The return**: the solver does not know which net it meshes, so the ground is solved the same way, declared as
   a rail whose source is the regulator's ground pad and whose loads are the loads' ground pads, with the same
   currents. The bound over a continuous plane: a few resistances (the plane as squares of sheet resistance ρ / t,
   about 0.5 mΩ per square for 35 µm at 20 °C, the vias of the ground pads, the regulator and load pads) show
   whether the return can take the remaining margin.

Thickness of each copper layer, z position of the layers and via plating are read from the stackup and fabricator
files, never retyped. For orientation only, on a common four-layer build the outer copper is of the order of
35 µm and the inner copper of the order of 15 µm after processing, and via plating of the order of 20 µm; another
build gives other values and the resistances scale with them.

## 2. Board table and algorithm

Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table of the export**: `LAYERS` (name → layer id), and per rail the net name, the source
`(reference, pad)` and the loads `(reference, pad or None)`; `None` means "the only pad of that component on the
rail" and is an error if there are several.

**Board table of the solver**: copper thickness and z position per layer from the stackup file, via plating from
the fabricator file, cell size `D`, the loads `{(reference, pad): (label, current case 1, current case 2, …)}` with
the datasheet and table of each figure in a comment, the low margin of each rail read from the JSON of the
set-point check.

1. Export, per rail: the copper of each layer (`rail_copper`), the inter-layer links (`rail_links`), the source and
   load pads (`rail_pad`).
2. Solver, per rail: rasterise once per mesh size (`raster`), solve each current case (`solve_rail`), repeat with
   `d / 2` (computed from `D`, not typed).
3. Per rail and case: worst drop, worst drop × the temperature factor of the scope, equivalent resistance, low
   margin and remainder; then the map.

## 3. Validation cases

On a real rail: a hand estimate (strips in series and parallel, plus barrels) and the convergence test (d against
d / 2).

## 4. Reporting

- Table per rail: current, equivalent resistance, maximum drop at the copper temperature of the scope, regulated
  low margin, remainder; sorted horizontal bars of the drop per pad; the map.
- The equivalent resistance is given because the currents of an SoC are often envelope values: the designer
  recomputes the drop when a measurement arrives.
- If the remainder is thin: the cause (which margin term, which copper), the precise correction (which divider
  resistor, which value, resulting nominal and range; or which copper to add) and its gain in mV.
- Listed: the assumptions of `../SKILL.md`, "Limits"; the estimates (envelope currents, split of an IC's current
  between its pins); how the return was counted (bound or solve).
- Measurement to request: the rail at the load's decoupling capacitor under maximum load.
