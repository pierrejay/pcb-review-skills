# Chassis ground: method in full, field solver, convergence, validation, reporting

## Contents
1. Method, step by step, with the defaults
2. Describing a geometry to `estatic2d`
3. Convergence of an edge field
4. Board table and algorithm
5. Validation cases
6. Reporting

## 1. Method, step by step, with the defaults
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers.

1. **Geometry from the PCB.** Chassis copper per layer (area, list of pads, tracks, zones) and its minimum
   distance to the copper of every other net, nearest first, with position. For each connector, distance from
   its pins to each protection part on a shared net (state in the label what is measured: e.g. pad centre to pad
   centre, or footprint centre to centre when no net is shared) and the side.
2. **Parasitic capacitance** chassis net ↔ ground and chassis net ↔ chassis net: for each pair of adjacent
   layers, overlap area S of the two coppers, C = ε0·εr·S/h. Capacitance between two nets across the dielectric
   between layers a and b: sum of the overlaps net1-on-a × net2-on-b and net2-on-a × net1-on-b. Edge effect
   neglected: for a thin dielectric under wide copper, the capacitance is typically 10–20 % under (estimate), hence
   voltages slightly overestimated.
3. **Contact discharge on the touchable parts** (generator of the ESD immunity standard, here
   `esd_iec61000-4-2.lib`, ngspice). One node per conductive part or chassis net that is not ground, board ground
   `bgnd`, earth 0; the parasitics of step 2. The values below are orders of magnitude for a first run, typical of
   a small board in a small enclosure, each replaced by the board's value when it is known; they are estimates and
   listed as such:
   - tie capacitor: the board's part with its mounting inductance (≈ 1 nH for a large surface-mount case) and ESR,
     a constant read on the curve of the part (`mlcc_bias.capacitance`), re-read at the voltage the first run
     reached if the margin is small (a class-2 ceramic near its rating can lose a third or more); bleed resistor as
     fitted; a closed link or a screw and spacer: a few nH and tens of mΩ;
   - board ↔ horizontal coupling plane of the test set-up: ε0·S/h over the insulating support (≈ 1.8 pF per cm² of
     board over 0.5 mm); touched copper ↔ plane: a few pF;
   - ground earthed through the supply cable (of the order of 1 µH and 0.1 Ω per metre) or floating (tens of pF);
   - metal enclosure ↔ plane: from its size (of the order of 100–200 pF for a small box), not earthed (worst case
     for the part–ground voltage) and earthed by its strap (of the order of 1 µH per metre of strap); a connector
     shell touching the panel cut-out: of the order of 2 nH;
   - magnetics or isolators: inter-winding capacitance from the datasheet (tens of pF for a signal transformer
     when unpublished, estimate); a termination that ends on a shell or shield net (e.g. the common-mode
     termination of a connector with integrated magnetics, such as an Ethernet jack: resistors and capacitor of its
     drawing) to the net the board gives its end, both nets run when the datasheet asks for one and the board
     uses the other;
   - other cables not connected first (fewer return paths, pessimistic); connected, when proposed: common mode of
     a cable of the order of 150 Ω to earth at discharge time scales (estimate).
   Peaks are read with `.meas`. Output: peak |V| of each part against ground, ground against earth, the voltage on
   each tie component, termination and isolation.
3b. **Surge on a shield or shell tied to ground through a capacitor** (combination-wave generator of the
   surge immunity standard, `cwg_iec61000-4-5.lib`, applied to the shield itself: the coupling commonly used for a
   shielded line, indicative). Mechanism: a surge lasts tens of microseconds, so the tie capacitor (a few nF)
   charges almost fully; when something else holds ground to earth (an earthed host, an earthed peer on another
   port, a supply whose 0 V is earthed), the whole surge appears between the shield copper and the ground planes.
   When nothing does, ground follows the shield and the voltage between them stays low. The netlist is the one of
   step 3 with the generator swapped and run over the whole surge (§ 4), ground first earthed through another
   path; floating when asked. Output: peak shield–ground voltage, current in the tie, voltage on the tie capacitor
   (against its rating), per installation.
4. **Field in the laminate: the bound first.** Computed for 1 kV, then scaled to the peak voltages of steps 3 and
   3b (the problem is linear). Bound: E ≈ k · V / h_min, h_min the shortest distance from the stressed copper to a
   reference copper (the antipad gap in a plane, or one prepreg), k ≈ 2.6 for copper edges rounded at half the
   thickness. Domain of k: fitted on six geometries of one four-layer build (through-hole pads and a via in their
   antipads, zone edges over a plane, h_min of 0.094 to 0.1 mm, copper rounded at half its thickness), where the
   fine calculation gave k from 1.8 to 2.4: the bound overestimates by up to about 50 %. Another build, another
   h_min or another copper thickness is outside that domain.
5. **Field in the laminate: fine calculation** (`estatic2d`, `edge_field`). Two geometries: (A) a through-hole
   chassis pad in its antipad of the inner ground planes, axisymmetric; (B) the edge of a chassis zone above a
   ground plane through one prepreg, plane section. Copper edges rounded at half the copper thickness (etch
   profile) so the field stays finite. The quantity judged is the field **at the copper surface**, obtained by a
   convergence study at fixed distance from the copper and an extrapolation to the surface (§ 3). It costs of the
   order of an hour and gigabytes of memory per geometry set.
6. **Common-mode paths** (ngspice), one node per zone: ground plane split in nodes at the cable entries, linked by
   its partial inductance (**estimated** from the plane dimensions: of the order of 10 nH between opposite edges
   of a plate a few centimetres on a side; a range, e.g. half and one and a half times, if it decides); ties,
   screws and spacers as in step 3 (a metal screw into an earthed enclosure makes the enclosure a second path in
   parallel with the plane); enclosure strap; board ↔ reference plane from step 3; magnetics or isolators with their
   inter-winding capacitance and terminations; each cable to what it meets at its far end (e.g. a supply whose 0 V
   is earthed: often the other exit of the current). Events: surge on a cable that leaves the enclosure, with
   the coupling network of its test (e.g. for an unshielded symmetrical line, combination wave + 40 Ω, i.e. 42 Ω
   line to earth, a coupling commonly used, indicative); fast transients (5/50 ns, `EXP` source behind 50 Ω,
   coupling clamp of the order of 100 pF) on a cable. Output: current through the plane, voltage between its
   ends (under the ICs it crosses), current in each screw and cable, voltage on each isolation and tie component;
   with and without a candidate HF tie (a capacitor of a few nF rated for the surge level, with its mounting
   inductance) near the far connector.
7. **Strategy × installation table**: per configuration computed (tie of each part, state of a jumper the manual
   offers, enclosure type × far ends × supply 0 V earthed or floating), peak voltage at discharge and at surge,
   and margin.
8. **Margin** = laminate strength / field, the field being the field per kV of the geometry × the peak voltage
   (`edge_field.scale_to_voltage`, `edge_field.margin`).

## 2. Describing a geometry to `estatic2d` (units mm and V; field returned in kV/mm)

The maximum field is read at least `guard` + 1 cells from any
conductor, so at a distance that moves with the mesh; `edge_field.fixed_distance_guard` holds it fixed (§ 3).

```python
# excerpt — validated with numpy/scipy (pcb-verification/lib/estatic2d.py)
import estatic2d as es

# 4-layer stackup, z = 0 under the bottom copper (mm): bottom, inner 2, inner 1, top copper. The board script
# derives these from the stackup file (pcb-verification/assets/stackups/); the values below are those of one
# four-layer 1.6 mm build, for illustration (e.g.).
ZB, ZI2, ZI1, ZT = (0.0, 0.035), (0.1344, 0.1496), (1.4146, 1.4298), (1.5292, 1.5642)
DIEL = [(0.005, ZB[1], 3.8, "mask"), (ZB[1], ZI2[1], 4.1, "prepreg"), (ZI2[1], ZI1[0], 4.6, "core"),
        (ZI1[0], ZT[0], 4.1, "prepreg"), (ZT[0], ZT[0] + 0.030, 3.8, "mask")]
mid = lambda a: (a[0] + a[1]) / 2          # noqa: E731
thk = lambda a: a[1] - a[0]                # noqa: E731

def pad_in_antipad(r_pad, r_drill, gap, outer_gnd=1.2, d_fine=1e-3):
    """Through-hole pad at 1 kV inside the antipads of grounded planes; x is the radius."""
    hot, gnd = 1000.0, 0.0
    cond = [(es.rect(0, r_drill, ZB[0], ZT[1]), hot, "barrel")]
    for layer in (ZT, ZI1, ZI2, ZB):       # annular ring on every layer, outer edge rounded at t/2
        cond.append((es.strip(r_drill - 0.01, r_pad, mid(layer), thk(layer), round_hi=True), hot, "pad"))
    for layer in (ZI1, ZI2):               # inner planes start at r_pad + gap, inner edge rounded
        cond.append((es.strip(r_pad + gap, 9, mid(layer), thk(layer), round_lo=True), gnd, "plane"))
    for layer in (ZT, ZB):                 # nearest copper at 0 V on the outer layers (any net: 0 V in impulse)
        cond.append((es.strip(r_pad + outer_gnd, 9, mid(layer), thk(layer), round_lo=True), gnd, "outer"))
    focus = [(r_pad - 0.03, r_pad + gap + 0.03, layer[0] - 0.03, layer[1] + 0.03) for layer in (ZI1, ZI2, ZT)]
    pb = es.Problem((0, r_pad + 3.0), (-0.6, ZT[1] + 0.6), DIEL, cond, focus, axisymmetric=True)
    return es.solve(pb, d_fine=d_fine)     # result["by_material"]["prepreg"]["E_max_kV_mm"] is per kV here
```
Zone edge over a plane (geometry B): `strip(-3, 0, mid(ZT), thk(ZT), round_hi=True)` at 1 kV, full planes
`strip(-3, 3, …)` at 0 V on the inner layers, solder mask over the copper as `extra_eps`, one focus box of
±0.06 mm around the edge from the plane to above the mask, domain ±1.5 mm.

## 3. Convergence of an edge field

`edge_field.converged` applies these criteria and says whether they are met; `require_converged` and
`edge_field_study` raise when they are not. The reasons are:
1. Refining the mesh with a fixed `guard` is **not** a convergence test: each run reads the field closer to the
   copper, and near an edge the field rises as the surface is approached. A series that keeps rising by a
   similar step at each halving (ratio of successive differences near 1 instead of 0.5 or less) means the
   quantity read is changing, or that it has no limit; either way the last value is not the answer.
2. Hold the reading distance fixed in micrometres and halve the mesh. Converged means: the last step is small
   (≤ 2 %) and the successive differences shrink (ratio ≤ 0.6 in absolute value: a series may oscillate while
   damping), or the whole series already sits inside 1 % (it has reached the noise of the calculation). A
   monotonic series is completed by Richardson extrapolation with its observed ratio; an oscillating or flat one
   by its last value. If the series does not converge, the geometry has a real singularity (sharp corner) or the
   mesh does not resolve the rounding: fix the model, do not quote.
3. Repeat at three distances (3, 1.5, 0.75 µm) and extrapolate to the surface with `E(x) = A / (R + x)` (linear
   fit of 1/E against x). The extrapolation is valid if the fit reproduces the three converged readings within
   1 % and the surface value is within 15 % of the closest reading; otherwise the run fails. The fitted R is
   reported for information: it is of the order of the rounding radius for an edge facing an edge, larger for
   an edge above a plane, so it is not a validity test by itself.
4. **Plan the meshes within memory before running.** The system is solved directly and `estatic2d.solve` stops
   above its node cap rather than exhaust the memory; `estatic2d.node_count` gives the count of a mesh without
   solving it. The grid is a tensor product: a fine box
   widens a whole row and a whole column, so the count grows with the product of the fine spans in x and in z. A
   reading distance x held at 3, 6 and, if the series needs it, 12 cells (`guard` 2, 5 and 11) calls for cells of
   x/3, x/6 and x/12: the smallest reading distance sets the finest mesh. A series that needs one more halving is
   not forced by raising the cap: keep the fine box on the one edge that carries the maximum (located on a coarse
   run), shrink it to a few tens of reading distances, and re-count; if it still does not fit, the field of that
   geometry is "not converged", or is bounded by a more severe geometry already computed (a narrower antipad, the
   same pad); either is written as such.

## 4. Board table and algorithm

Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table**: `CHASSIS` (set of chassis net names); `PROTECT` (connector → protection references, from the
schematic); `PAIRS` (layer a, layer b, dielectric thickness, εr) and the z coordinates of every copper and
dielectric, from the stackup file; pad radius, drill radius and antipad gap of the through-hole pins, read from
the PCB; shield capacitor, bleed resistor and link values read from the PCB; `CASES` of the discharge (key,
label, discharge node, kV, options: capacitor value, link closed, ground earthed or floating, metal enclosure,
chassis–ground capacitor); `SURGE_CASES` (key, label, shield node, kV, what holds ground to earth); h_min of every
geometry (antipad gap, prepreg) with k and its domain; for the common-mode model, which connectors sit at which
end of the plane; laminate strength with its source.

1. Copper per net and per layer as polygon sets (`copper_by_net`; same collection and same distance function as
   `pcb-check-isolation`). Distances: chassis set against each other net, sorted.
2. Capacitances: for every pair of nets among chassis nets + ground and every pair of adjacent layers, the
   overlaps of step 2 both ways (`overlap_area_mm2`, `parallel_plate_pf`).
3. Discharge netlist built from a dictionary of options; 1 GΩ leaks on nodes without a DC path; `.options
   method=gear reltol=1e-4 abstol=1p vntol=1u`, `.tran 10p 300n 0 10p uic` (the generator's capacitors start
   charged: `uic` is mandatory). Peak of |V| per node over the run, as the `.meas` of the
   run: every netlist goes through `spice.run`, kind "fast" for a discharge or a fast transient, "slow" for a surge
   (`pcb-check-surge-esd`, method, step 2: the measure of a peak).
3b. Surge netlist: the same network with the combination-wave generator on the shield node of each case of
   `SURGE_CASES`, both polarities if the network is not linear, a time step resolving the 1.2 µs front and a run
   of the order of 100 µs. Peaks of the shield–ground voltage, of the tie current and of the voltage on the tie
   capacitor.
4. Field, bound: per geometry, the bound of step 4 per kV, × each peak voltage of steps 3 and 3b; margin of step 8.
   A margin at the bound that meets the criterion is the result, marked "bound: lower margin".
5. Field, fine calculation, only for the geometries whose bound misses the criterion or whose margin is asked:
   build the `Problem`s; for each, run the convergence study at fixed reading distance and extrapolate to the
   copper surface (`edge_field.edge_field_study`, or `require_converged` per series then `surface_field`); keep
   the largest surface field per kV found in a dielectric over the geometries, multiply by each peak voltage,
   margin of step 8.
6. Common-mode netlist at the nominal plane inductance; low and high when the result depends on it.

## 5. Validation cases

Run before the first real result that uses them.
- **Bound against the fine calculation** on one geometry of the build when it lies outside the domain of k (§ 1
  step 4): the observed k = fine field per kV × h_min stays below the k used; otherwise raise k for that build.
- **Combination-wave generator alone**: open-circuit and short-circuit peaks at a level against the nominal values
  of the standard (the effective source impedance of about 2 Ω between them).
- **Capacitance**: one overlap of the board by hand, C = ε0·εr·S/h (e.g. 100 mm² over 0.1 mm of εr 4.1 → about
  36 pF).
- **Generator alone in 2 Ω** at a level, against the nominal values of the standard scaled to the level: peak,
  rise, current at 30 ns and at 60 ns (at 4 kV of the order of 15 A peak, rise under 1 ns, about 8 A at 30 ns,
  about 4 A at 60 ns); expected values `tvs_fit.esd_expected`, nominals and tolerances `tvs_fit.ESD_STANDARD`,
  `tvs_fit.esd_check`.

## 6. Reporting

Table connector → protection (value, distance, side); table chassis pad → clearance to each plane → voltage at
stake and what holds it; table discharge case → peak voltage → edge field → margin against the specification
minimum (and against the measured value); the same table for the surge cases of step 3b, with the voltage on the
tie capacitor; each field marked "bound" (its margin a lower bound) or "fine calculation"; table event → current in
the plane, voltage across it (with its range for the inductance variants), voltage on the magnetics; the strategy
× installation table and the sentence for the manual. Figures: waveforms of the discharge, field map with
equipotentials around the pad and the zone edge. A deviation names the mechanism and the remedy with its computed
gain: "<tie> in <installation>: <coupling> divides against <enclosure capacitance>, <peak>, margin <m>; <remedy>:
<peak>, margin <m>". To request: an ESD pre-compliance shot on each touchable part in the retained strategy.
