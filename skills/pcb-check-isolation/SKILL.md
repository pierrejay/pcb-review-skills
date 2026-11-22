---
name: pcb-check-isolation
description: "Isolation-barrier check of a PCB: minimum copper distance between the isolated and logic sides on every layer and parts bridging the barrier, against the distance the targeted withstand voltage requires (IEC 60664-1 may apply); isolated bus transceivers, digital isolators, isolated DC-DC."
---

# Check: isolation barrier

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `iec60664.py`: the tables of IEC 60664-1 and their readings;
- `kicad_copper.py`: copper, sides and distances.

## Purpose
On every copper layer, what is the smallest distance between the copper of the isolated side and the copper of
the logic side, between which two objects, and which withstand voltage does that distance cover? Does anything
other than the barrier component link the two sides?

## When it applies
- The board carries an isolation barrier: isolated transceiver (e.g. RS-485, CAN), digital isolator, isolated DC-DC
  converter, optocoupler, transformer.
- The criterion comes from the scope of use: kind of isolation, withstand voltage, and **nature of the test** (peak, DC,
  surge, 60 s AC); for solid insulation, the distance through insulation of the product standard when it gives one
  (`SOLID_MM`). Without these the measured distance has no criterion; it is a decision of the designer, to obtain at
  scoping. The tables here size **functional** insulation. Basic or reinforced insulation (protection against electric
  shock) takes its clearance, creepage, solid insulation and tests from the product standard for that kind of
  insulation: until the designer gives them, the check is incomplete, whatever the distances measured. Below the voltage
  range of the low-voltage directive (50 V AC or 75 V DC, to be confirmed for the product) the directive sets no
  distance, though the product safety standard may: the target is then what the designer declares (often a functional
  isolation).
- The line-to-earth surge of an isolated bus is carried by the barrier: it is judged here, not by the bus TVS.

**Texts that may apply** (the reader confirms which edition and which product standard governs the market aimed
at): IEC 60664-1, insulation coordination (clearances, creepage, solid insulation); IEC 60664-3, protection of a
printed board by coating or potting; the product-family safety standard (e.g. IEC 62368-1 for IT and audio-video
equipment, IEC 61010-1 for measurement and control equipment); the component standard that defines the barrier
part's ratings (VIOTM, VIOWM; e.g. IEC 60747-17 for capacitive and magnetic couplers). The tables held in
`iec60664.py` are indicative values commonly used in design; their numbers (F.2, F.5, F.8) are those of recent
editions of IEC 60664-1.

## Inputs to obtain
- **PCB**, zones filled: barrier component(s); seed nets of the isolated side (isolated ground and supply, bus
  lines); logic-side nets (ground, logic supplies); copper layers; stackup.
- **Schematic**: components meant to bridge the barrier (stitching or Y capacitor, second isolator), rated voltage.
- **Barrier datasheet**, insulation table, each field with its unit and the test it comes from (RMS or peak,
  duration, DC or AC): VISO (60 s), VIOTM and VIOWM (maximum transient and working voltages), package clearance and
  creepage, distance through insulation, CTI, pollution degree, keep-out channel (no copper under the component).
  They are values of the component, not of the board around it. **Laminate**: comparative tracking index.
- **Designer**: targeted withstand(s) and the nature of each test; the maximum potential difference between the two
  sides in service, transient and steady (its RMS value is the working voltage across the barrier); whether a
  stitching capacitor will be fitted.

## Method
1. **Isolated side** (`isolated_nets`): grown from the seed nets through every component except the barrier; a
   component touching both sides is a bridge, reported and not crossed.
2. **Copper of each side, per layer** (`copper_items`, `side_of`): every piece of copper as polygons covering it;
   netless copper kept, unconnected pads sided by their footprint, the rest floating.
3. **Minimum per layer**: exact minimum between the two sides (overlap tested first), the two objects that give it,
   and the shortest path through floating copper, chains included; the smaller is the layer minimum.
4. **Between layers**: each layer's isolated side against every other layer's logic side, straight distance through
   the insulation between those two layers: a prepreg between close layers, a core and more between distant ones;
   of the builds the board may be ordered on (`scoping.md`), the thinnest for that pair.
5. **Requirement** of each target in the table of its **nature** (transient → F.2, held peak → F.8, creepage → F.5
   at the working voltage); **reverse reading**: what the routed distance covers in each table.
6. **Verdict**: three criteria on three geometries, then the chapter verdict: pass, fail or incomplete.

## Criteria
Three criteria, each on its own geometry; a verdict names the one it comes from, and each number says which
quantity it is (clearance, creepage or distance through insulation).

| Criterion | Judged on | Required |
|---|---|---|
| Clearance in air | minimum on the **outer** layers | F.2 (transient) or F.8 (held), most demanding declared target |
| Creepage | smallest surface path over both **outer** layers; the path around a slot of the board replaces only the distance of the pair the slot crosses | F.5 at the working voltage, never below the required clearance |
| Solid insulation | minimum on each **inner** layer and **between layers** | the distance through insulation of the product standard when the scope names one; otherwise no table applies, and the F.2 distance of the targeted peak is a screening rule of the review: a distance below it is flagged with its field, not a fail |

## Self-checks
- Print the isolated net list and read it once against the schematic; fail on a `LOGIC_STOP` net in it or a
  seed net absent from the board (renamed by a cleanup or a revision).
- Bridging components: the list must equal what the schematic intends (nothing, or the declared stitching
  capacitor); anything else is a finding, not a filter. A connector that carries both sides (logic supply or ground
  beside the bus lines) has its pads in the layer minimum like any copper; inside its body the distance is the
  connector's own, from its datasheet, reported beside. Such a cable brings the logic ground next to the isolated
  lines: what the isolation protects is then asked of the designer.
- A minimum of 0 on one layer is a misclassified net, not a result: fail.
- Between layers, an in-plane distance of 0 is a real result (one side's copper above the other's): report it
  with the insulation thickness.
- The polygons make each gap short by up to 2 µm per side: every criterion is judged by `iec60664.distance_ok`
  with 0.004 mm per gap of the distance; within that band of the requirement the criterion is neither pass nor fail
  but missing, with the two numbers.

## Tool contract
Two scripts; results in `results/`, next to `scripts/`; distances unrounded in the JSON, rounded only in the report.
- `isolation.py`, KiCad's bundled Python (`pcbnew`) → `results/isolation.json` = `{iso_nets, bridging_components,
  layers: {name: {min_mm, gaps, at_mm, iso_item, logic_item, netless, floating, slot_pairs, beyond_slots}},
  between_layers: [{isolated, logic, in_plane_mm, insulation_mm, distance_mm, at_mm, iso_item, logic_item}]}`;
  `min_mm` is `null` with copper on one side only; `gaps` = gaps the minimum crosses (1 direct, more through floating
  copper); on an outer layer with pairs in `SLOT_PAIRS`, `slot_pairs` = those pairs `[{min_mm, at_mm, iso_item,
  logic_item}]` and `beyond_slots` = `{min_mm, gaps, at_mm, iso_item, logic_item}`, the minimum without them
  (`references/method.md`, algorithm, step 3), `null` otherwise; `between_layers` is sorted by `distance_mm`; `at_mm`
  = [x, y] in millimetres, board coordinates.
- `isolation_requirement.py`, any Python, no dependency beyond `iec60664`, reads `isolation.json` →
  `results/isolation_requirement.json` = `{clearances: [{scenario, kv_peak, nature, table, required_mm, measured_mm,
  uncertainty_mm, ok}], covered: {transient_kv_peak, steady_kv_peak, steady_kvrms}, creepage: {measured_mm, path,
  uncertainty_mm, working_v, column, required_mm, ok, state, covered_general_v}, solid: {rule_mm, basis,
  inner_layers_mm, between_layers_mm, inner_ok, between_ok, field_kv_per_mm}, targets, required_air_mm,
  target_peak_kv, verdict: {verdict, decided_by, missing, not_applicable}}`, and prints the verdict of each
  criterion, then the overall one. Values: `table` "F.2" or "F.8"; `column` "general" or "printed board"; `ok`
  `null` within the uncertainty of the requirement; creepage `path` "planar" or the path around a slot, `state`
  "judged", "not applicable: <designer's reason>", "not judged: working voltage not declared" or "not judged: slot
  across the minimum, path around it not measured", with `required_mm`, `column` and `ok` at `null` when not
  judged; `covered_general_v` always on the general column, as a reading aid; `between_layers_mm` and
  `field_kv_per_mm` `null` when the board has no inter-layer pair; `verdict` "pass", "fail" or "incomplete".
- **Refusals**: a voltage outside a table stops the requirement script with no partial result written; a held voltage
  beyond the rows is never re-declared as a transient to obtain a number: the criterion stays "not judged" and the
  chapter incomplete until the rows of the applicable edition are supplied (`clearance_f8(…, table=…)`). An input
  refused by a shared module makes the chapter `INC`, with its message.

## Pitfalls
- **Look at which two objects give the minimum.** After a cleanup or an import, a pin left unconnected on the
  barrier part can become a net of its own. Copper with a real net that is not on the isolated side counts on the
  logic side (only `unconnected-…` nets and netless copper take the side of the nearest connected pad of their
  footprint): the minimum is then the pin pitch, which is false.
- **Classify the copper, then filter.** An extraction that drops copper without a net before giving it a side
  over-states the gap (0.9 mm reported for 0.4 mm of real gap in the whole-chain validation case of
  `references/method.md`). A test of the classifying function alone passes; only a test of the whole chain shows it.

## Limits
The tables are indicative values for an altitude up to 2 000 m, F.2 up to 12 kV, F.8 and F.5 for a few rows, without
later amendments: outside those rows nothing is judged, and a formal claim is made from the applicable text. Distances
between copper only, per layer and between layers: component bodies, connector pins, screws and the enclosure are not in
the model. Distance through insulation is judged against the product standard's distance when the scope names one,
otherwise only screened: the laminate's electric strength and the standard's rules for solid insulation and cemented
joints are to be read for any formal claim. The keep-out channel under the component is checked by eye on the layer
views, not by this tool.
