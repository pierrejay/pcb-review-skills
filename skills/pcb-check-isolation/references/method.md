# Isolation barrier: method in full, the three tables, board table, algorithm, validation, reporting

## Method, step by step
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers.
1. **Isolated side.** Start from the seed nets and grow through every component (a component touching an
   isolated net puts all its nets on the isolated side), **except** the barrier component. A component that
   touches both an isolated net and a declared logic net is a bridge: reported, and not crossed.
2. **Copper of each side, per layer**: pads (only where they have copper on that layer; an unplated hole with a pad
   is copper minus the hole), the **barrel** of a plated hole or via on a layer where it has no pad (copper, not a
   connection), tracks, arcs, vias, filled zones of the board and of the footprints, graphic copper (shapes, text,
   fields drawn on a copper layer). Each is converted to polygons that cover the real copper (arc tolerance 2 µm):
   a distance is never optimistic. **Copper without a net is still copper**: nothing is dropped because its net name
   is empty. Copper with a net takes the side of its net: isolated if the net is on the isolated side, logic
   otherwise. Copper of a footprint without a connected net (an **unconnected pad**, net named `unconnected-…` or no
   net at all; a footprint graphic) takes the side of the nearest connected pad of the same footprint. What cannot be
   attached to a side is **floating**: copper of a footprint with no connected pad (mounting hole, fiducial), a
   track, via or zone with no net.
3. **Minimum per layer**, exact. For disjoint polygons the minimum is reached at a vertex of one of them, so every
   vertex of each side is measured against the outlines of the other. **Test the intersection first**: two outlines
   that cross have no vertex inside each other, and the vertex method then returns a positive distance (5.00 mm for
   two rectangles forming a cross). Overlap → 0. Result per layer: distance, position, and **the two objects**
   (reference.pad, track, via or zone, with their nets) that give it.
   Then the path isolated side → floating copper → logic side, the **sum of the gaps it crosses**, through one
   floating object or **several in a row**: a floating conductor holds no voltage and shortens the insulation by its
   own width. The nodes are **connected pieces of copper**, not KiCad objects: a zone fill may hold several separate
   islands. Following one object at a time misses a chain: with two islands between the sides and three gaps of
   0.1 mm the path is 0.3 mm, where a search through a single island returns the first gap plus the open gap behind
   that island (0.7 mm). The layer minimum is the smaller of the direct distance and the
   shortest floating path.
4. **Between layers**: the isolated side of each layer against the logic side of every other layer. In-plane
   distance (0 if the two coppers overlap in projection), thickness of insulation between those two layers in the
   fabricator's stackup file (`Slab.h_between`: a prepreg between two close layers, a core and more between distant
   ones; one prepreg thickness for every pair would put distant layers at the distance of close ones); of the builds
   the board may be ordered on, the thinnest for that pair. Straight distance = √(in-plane² + thickness²). Floating
   copper is not followed between layers: say so if a floating object lies near the barrier.
5. **Requirement**, read in the table that matches the **nature** of each targeted withstand (IEC 60664-1):
   - a **transient** overvoltage (surge, impulse) → table F.2; between two rows take the **upper** row; on an outer
     surface (pollution degree 2), never less than the 0.2 mm floor;
   - a **steady-state peak, temporary or recurring peak** voltage (a 60 s AC dielectric test, a DC withstand)
     → table F.8, case A, at the peak (× √2 for an RMS value), interpolated between its rows; outside the rows
     given in `iec60664.py`, no value and no verdict;
   - **creepage** along an outer surface → table F.5, at the **RMS working voltage** across the barrier, not at
     the test voltage, and never below the clearance of the targeted withstand; not judged while that working
     voltage is not declared.
   Which voltage sizes a **functional** insulation: the maximum stresses expected in service. A 60 s test that
   the designer sets for himself does not by itself make F.8 mandatory; if the product commits to that withstand,
   F.8 is the reference for the path in air. Judge the air path against the most demanding of the declared targets.
   **Reverse reading**: the highest row of the table that the measured distance covers, to tell the designer
   what the routed barrier is worth and what the next step of widening buys.
6. **Verdict**: the clearance in air of every target, the creepage, and, when the scope names a product-standard
   distance through insulation, the solid insulation on the inner layers and between layers (otherwise screened and
   flagged, step 8). `pass` only if all are judged and all hold, and only for functional insulation (basic or reinforced
   without the product standard's requirements for that kind: `incomplete`); `fail` if one judged criterion fails;
   `incomplete` if a criterion that applies could not be judged (creepage without a declared working voltage, no facing
   copper on the outer layers, a geometry refused by `kicad_copper`, a distance within the measurement uncertainty of
   its requirement, a slot whose path around was not measured), with what is lacking and what would complete it. A
   criterion is not applicable only by an explicit, dated statement of the designer.

## The three tables: what each one is, and what is not a table
The tables give clearances **in air**; they apply to the path in air. The path along a surface is creepage, a different
quantity sized from the working voltage (table F.5), which the standard keeps at least equal to the associated
clearance. The path between two layers, and the copper of an inner layer embedded in resin, run through solid
insulation: neither F.2 nor F.8 applies, and the standard sets no requirement for solid insulation used as functional
insulation. When the scope names a product standard that gives a distance through insulation, that distance is the
criterion. Otherwise the F.2 distance of the targeted peak, floor included, is a screening rule of this review, on the
cautious side: a distance below it is flagged, not a fail. Give the rule verdict (distance) and the effect separately
(field in kV/mm at the targeted peak voltage, against the electric strength of the laminate read in its datasheet).

**F.2** (`iec60664.F2`, transient). The solder mask is counted neither as insulation nor as the coating of quality
that would allow the pollution-degree-1 values of a note of F.2 (floor 0.04 mm; IEC 60664-3 deals with such
protections): `pollution_degree=1` only with that coating documented.

**F.8** (`iec60664.F8_A`, case A, held peak) is interpolated, as a note of the table allows: 1.414 kV peak gives
0.663 mm, where the upper row would give 0.76 mm. Over its rows it asks more air than F.2 at the same peak.

**F.5** (`iec60664.F5_PD2`, creepage, pollution degree 2) is read at the RMS working voltage. Often low on a
functional isolation, it can still size: between two successive rows the general column can more than double. The
reduced printed-board column needs the material group of the exact laminate, from its comparative tracking index
(`material_group`): look for the index in every sheet of the laminate (manufacturer, distributor), and in the
rendered pages of a PDF whose text layer is an image, where a text search returns nothing. With the reduced column
open, creepage is bounded only by the clearance of the targeted withstand; its use may require a protection against
pollution.

**Creepage across a slot.** The planar distance between the two coppers is the creepage when the straight segment
between them lies on the board surface. When a slot or cut-out of the board (an outline on Edge.Cuts) crosses that
segment, the planar distance is the clearance across the slot and only a lower bound of the creepage: it passes the
criterion when it meets it, and is never a fail by itself. A slot narrower than the width X of IEC 60664-1's creepage
examples (0.25 / 1.0 / 1.5 mm at pollution degree 1 / 2 / 3) is bridged: the planar distance is the creepage. A wider
slot is followed: the creepage is the shortest path on the surface between the two sides around the ends of the slot,
measured on the drawing. That path replaces only the distance of the pair of copper pieces whose segment the slot
crosses; every other pair, on the same outer layer or the other, keeps its own. The creepage is the smallest over all
of them, so after a minimum that crosses a wide slot the search goes on without that pair (algorithm, steps 3 and 7).

## Board table and algorithm
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table** (top of `isolation.py`): `BARRIER` (references of the barrier components), `SEED` (isolated-side nets),
`LOGIC_STOP` (ground and logic supplies), `LAYERS` (all copper layers of the board), the stackup, `MAXERR` (2 µm, from
`kicad_copper`), `SLOT_PAIRS` (outer layer → the `at_mm` of each minimum whose segment crosses a slot wider than X, read
on the board; empty at the first run). Top of the requirement script, written from the designer's answers: `SCENARIOS`
(label, kV peak computed unrounded with `rms_to_peak`, nature: "transient" → F.2, "steady" → F.8), e.g. "a 1.41 kV peak
transient", "1 kVrms held 60 s"; `TARGETS` (labels of the scenarios the product commits to); `WORKING_V` (RMS, across
the barrier; `None` until the designer declares it); `OUTER` (names of the two outer copper layers); `PCB_COLUMN`
(`True` only when the laminate's material group is documented other than IIIb and the designer accepts the condition of
the reduced column), with the group itself (`material_group(cti)`); `NOT_APPLICABLE` (criterion → the designer's dated
reason, e.g. `{"creepage": "reason"}`); `CREEPAGE_MM` (`{(layer, at_mm of a pair of slot_pairs or of a measured
beyond_slots): (mm, description)}`, the measured path around the slot between the two pieces of that pair, or of that
floating path; empty until measured).

**Algorithm**
1. Load the board; compute the isolated net set and the bridges (`isolated_nets`); print both.
2. For each layer, list every copper object (`copper_items`) with its side (`side_of`), by the rules of step 2.
3. Merge the polygons of each side; `min_distance`; convert from nanometres; on each side, the object nearest to
   the point of the minimum (the item with the smallest `poly.SquaredDistance(point)`) is stored with its
   description. Then the shortest floating path (`floating_path`, over the gaps between the two sides and every
   floating piece). The layer minimum is the smaller of the two; the JSON keeps both and counts the netless and the
   floating objects, with `gaps`, the number of gaps the minimum crosses (1 for the direct distance, the length of
   the `floating_path` list otherwise). Distances are written unrounded. A layer with copper on one side only gives
   `min_mm = null`, written as such in the JSON and in the report. On an outer layer, the pairs of `SLOT_PAIRS` are
   set aside: the two pieces of a pair are, on each side, the piece of the merged side (`pieces`) nearest to its
   `at_mm`. `slot_pairs` lists them with their planar distance, `at_mm` and objects; `beyond_slots` = the minimum
   over every other pair (each isolated piece of a pair against the logic side without the pieces it is paired with,
   the other isolated pieces against the whole logic side, by `min_distance`), or the floating path when it is
   shorter, with its `gaps`, `at_mm` and objects; `null` when no other pair faces.
4. Between layers (step 4): every pair (isolated side of one layer, logic side of another), sorted by straight
   distance.
5. Requirement script. `outer` = minimum of `min_mm` over the `OUTER` layers, ignoring a `null`; with no value at
   all, clearance and creepage are "not judged: no facing copper on the outer layers". `inner` = minimum over the
   other layers, `None` if there is none. `between` = smallest `distance_mm` of `between_layers` (the straight
   distance, not the insulation thickness), `None` when the list is empty. Each carries its uncertainty `u`: 0.004 mm
   (2 × `MAXERR`) per gap, `gaps` of the layer that gives it, one gap for `between`. Every comparison below is
   `distance_ok(distance, required_mm, uncertainty)` on unrounded values: `True`, `False`, or `None` when the
   requirement lies within the uncertainty, and then the criterion goes to `missing` with the two numbers ("widen by
   the uncertainty").
6. **Clearance in air**, per scenario, on `outer`: `clearance_f2` (transient) or `clearance_f8` (steady); `ok =
   distance_ok(outer, required_mm, u)`; `required_air` = largest `required_mm` among the `TARGETS`. Reverse reading
   of `outer`: `withstand_f2`, `withstand_f8` (`None` outside the rows, reported as "outside the rows given").
7. **Creepage**, over both outer layers. On each, open the board at the `at_mm` of its minimum: a segment that crosses a
   slot wider than X ("Creepage across a slot" above) puts that `at_mm` in `SLOT_PAIRS`, then rerun `isolation.py`.
   Candidates of a layer: its `min_mm` when it has no slot pair; otherwise each pair of `slot_pairs` at its path around
   (`CREEPAGE_MM`), and `beyond_slots` at its planar distance. When `beyond_slots` crosses a wide slot too and lies
   below the smallest other candidate, add its `at_mm` to `SLOT_PAIRS` and rerun; when it is a floating path one of
   whose gaps crosses a wide slot, setting it aside would return the same path: measure it instead, gap by gap, each gap
   that crosses a wide slot taken around it, and enter that length in `CREEPAGE_MM` under its `at_mm`. A rerun that
   returns the same `beyond_slots` is measured the same way. `creepage` = the smallest candidate of the two layers, with
   its `u`, path "planar" or the description of the path around. A candidate whose path is not measured counts at its
   planar distance as a lower bound. Judge the known candidates first: one that misses the requirement (`distance_ok`
   False) makes the creepage a fail, the unmeasured ones listed in `missing` beside it; otherwise a pass if every
   candidate, unmeasured ones at their lower bound, meets the requirement, else "not judged: slot across the minimum,
   path around it not measured". Without `WORKING_V`, state "not judged: working voltage not declared" and
   `covered_general_v` = `creepage_covered_general(outer)`, the highest row the measured outer distance covers.
   Otherwise `required_mm = creepage_required(WORKING_V, required_air, column, group)`, with `column` "printed board"
   when `PCB_COLUMN`, else "general"; `ok = distance_ok(creepage, required_mm, u)`.
8. **Solid insulation**: `target_peak_kv` = largest peak among the `TARGETS`, whatever their nature; `rule_mm` =
   `SOLID_MM` (the product standard's distance through insulation, from the scope) when declared, else
   `solid_insulation_rule(target_peak_kv)`; `inner_ok = distance_ok(inner, rule_mm, u)`, `between_ok =
   distance_ok(between, rule_mm, u)`, each `null` when `inner` or `between` is `None` or within the uncertainty;
   `basis` = "product standard" or "screening"; only a "product standard" basis enters the verdict, a screening
   miss is flagged; `field_kv_per_mm` = `target_peak_kv / between`, `null` when `between` is `None`: with no
   inter-layer pair the criterion between layers does not exist and is left out of the verdict.
9. Chapter verdict, `iec60664.verdict(judged, missing, not_applicable)`, on the criteria of step 6; `NOT_APPLICABLE`
   echoed in the JSON. In the report, `incomplete` is the verdict `INC` of the report base
   (`pcb-verification-report`).

## Validation cases
Cases that check the board's own scripts.
- **Whole chain, down to the distance**, on a synthetic board built in memory: an isolated pad and a logic pad 0.9 mm apart,
  and between them a pad of the isolated footprint that has no net, 0.4 mm from the logic pad → 0.4 mm, not
  0.9 mm. Same board with that pad on a footprint of its own (no connected pad): direct distance 0.9 mm, floating
  path = its two gaps, here 0.2 + 0.4 = 0.6 mm, which is the result. A rule of 0.5 mm fails the first board and
  passes the second.
- **Whole requirement chain**, from a JSON written by hand: outer 1.0 mm, inner 1.0 mm, between 0.304 mm, targets at
  1.414 kV peak (transient and 1 kVrms held): clearance 0.5 and 0.663 mm, both pass; creepage at `WORKING_V` 25 → pass,
  at `None` → "not judged" and the chapter `incomplete` (not `pass`, even with every other criterion met); solid
  screening rule 0.5 mm, inner met, between **not met**, field √2 / 0.304 = 4.65 kV/mm: flagged, `verdict` = `pass` at
  `WORKING_V` 25; with `SOLID_MM` = 0.4 declared, `verdict` = `{verdict: "fail", decided_by: ["solid insulation, between
  layers"]}`, while clearance and creepage pass. **Slot**: F.Cu minimum 1.10 mm across a 1.05 mm slot, path
  around it 4.95 mm, B.Cu minimum 1.30 mm with no slot, required creepage 1.4 mm → creepage 1.30 mm, fail (the path
  around the slot alone passes); B.Cu at 1.50 mm and an F.Cu `beyond_slots` of 1.20 mm → 1.20 mm, fail. Between
  layers with an empty `between_layers` → `between` and `field_kv_per_mm` `null`, the verdict on the other criteria.

## Reporting
Per layer: minimum distance, position, the two objects and their nets (a view of the board at that point is attached);
between layers, the two layers of the shortest path drawn on top of each other, so that the designer sees where to pull
the copper back. Then the three criteria in turn (clearance in air on the outer layers, creepage, solid insulation on
the inner layers and between layers, against the product standard or the screening rule), each with its table targeted
withstand → required distance → verdict, and the table distance → withstand covered, so that the designer sees what each
widening buys. Bridging components with their rated voltage. A deviation is written with its correction and gain, in the
form: "<d> mm between <object A> and <object B> on <layers>: covers <x> kV peak (transient); pull both back to <d'> mm
(same place on each layer) to cover <y> kV peak".

Say once to the designer why the IC isolates with micrometres of oxide and the board needs millimetres: a solid
insulator holds hundreds of volts per micrometre; air and surfaces hold far less and depend on humidity and dust,
hence the few millimetres of external distance a package declares for its withstand. To request: the dielectric
test at the targeted voltage on a prototype, which remains the proof.
