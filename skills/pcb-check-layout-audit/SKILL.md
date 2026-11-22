---
name: pcb-check-layout-audit
description: "Scripted audit of a KiCad PCB's routing against the layout-guide rules that apply to its critical links, one verdict per rule and link: impedance runs, P/N matching, vias, coupling, reference plane, ground return vias, routed width versus net class; return loss of the path. Also a switching-converter block after a placement or a re-route: ground islands, input loop, enable tracks near switch nodes, silkscreen on neighbouring pads. Use to audit routing or quantify a deviation."
---

# Check: scripted layout audit

Read `../pcb-verification/SKILL.md` first. This check uses the outputs and the signal-path function of
`pcb-check-impedance`: build that one first.

The skill has two modes, which share the discipline of the review and nothing else: **link audit** (mode A, the
routing of controlled-impedance and timing-critical links) and **converter block audit** (mode B, a
switching-converter block after a change).

## Resources
In `../pcb-verification/lib/`:
- `rf_formulas.py`: return loss, via loop inductance, delay, skew, useful frequencies;
- `kicad_routing.py`: `pad_path`, the signal path;
- `impedance_keys.py`: keys, delay per mm.

## Purpose
- **Mode A**: does the routing of each critical link follow the layout rules that apply to it? The layout guide of
  the IC (or, failing one, the requirements of the link's standard) is turned into rules that a script judges link
  by link, each deviation with its quantified electrical effect.
- **Mode B**: is a converter block that has just been placed or re-routed sound (rules and connections, ground
  islands, input loop, sensitive tracks near switch nodes, planes, silkscreen)?

## When it applies
- **Mode A**: any board with links covered by a layout guide or by a standard that bounds the routing (impedance,
  skew, return path): PHY pairs, USB, buses clocked from a common source, clocks.
- **Mode A, link without a layout guide**: derive the rules from the link's standard and from the mechanisms
  (impedance and its tolerance, return loss up to the useful frequency, skew against the edge, return path). The
  guide of another IC of the same family may serve as a starting point; the report says it is borrowed and the
  rule is judged applicable like any other.
- **Mode B**: after a switching-converter block has been placed or re-routed; the block is not a link, but it is
  measured the same way (step 5).

## Inputs to obtain
- **Layout guides** of the ICs on the critical links (e.g. the layout section of a PHY datasheet), and the
  requirements of the link standard (e.g. the differential impedance of a USB 2.0 link); typical rules:
  `references/method.md`, "Where the rules come from".
- **From `pcb-check-impedance`**: `impedance_geom.json` (sampled points and their keys), `impedance_board.json`
  (deviations per continuous run), `impedance_cache.json` (impedance and εeff of each key), and the `PATHS` table.
- **PCB and project**: tracks, vias, pads, filled zones; net classes and their assignment (`.kicad_pro`).
- **Designer**: board thickness; which stackup is the production one; the names of the supply nets; which buses
  are too slow for a high-speed rule; the interface rates actually used; the design intent of any link routed
  differently from its guide (pair without a plane on purpose, deliberate cutout).

## Method
Every rule is measured on the signal path, pad to pad with the branches excluded, as the impedance check measures it
(self-checks).

### Mode A: link audit
1. **Select the rules** ("Where the rules come from"). For each critical link, list the rules of its guide and
   standard and judge each, whether or not it states a number: mechanism, domain, numbers, cost of following it
   (`../pcb-verification/references/qualitative-rules.md`). A requirement of a datasheet ("must", an absolute
   maximum) is a criterion directly; a rule judged applicable is coded as a criterion like any other; a rule
   judged not applicable keeps its row, with the reason, and gets no verdict.
2. **Measure each rule on the path** ("Mode A: the rules, how each is measured"): Z from the keys and the cache of
   the impedance check on the production stackup, its runs from `impedance_board.json`; L and VIA with the vias
   the path crosses; CPL; PLAN from `impedance_geom.json`; RET on the vias of the path only; BETWEEN; CLS by nature
   of run. RET needs its screening distance `RET_MM`, derived with the designer from the delay the fastest edge of
   the links concerned tolerates, or no threshold and every via reported ("RET: the screening distance").
3. **Also reported** ("Algorithm"): copper inside the footprint of a magnetics component (transformer, jack with
   integrated magnetics), per layer; pours on nets that are neither ground nor supply; path lengths and delays of a
   group of lines clocked from a common source when its timing budget cannot be closed (the budget itself:
   `pcb-check-timing`).
4. **Effect** ("Quantified effect"): return loss of the path at the useful frequency of the link, skew of the
   P/N mismatch, delay of each return loop, with the delay per mm of the link from the εeff of the impedance cache
   (`impedance_keys.delay_per_mm`).

### Mode B: converter block
5. **Converter block** ("Mode B: converter block"), after a placement or a re-route. An input loop split over two
   ground islands is computed through the vias and the plane before a top-layer ground path is asked for.

## Criteria
One verdict per rule and per link, the effect computed apart (step 4): the useful frequency sizes the effect, never
the verdict.

**Mode A**

| Rule | Criterion | Where the number is read |
|---|---|---|
| Z | no continuous run outside the tolerance band longer than the local-transition length | tolerance of the guide or the standard (commonly ±10 % of the target for a PHY pair; `impedance_keys.TOL`); local-transition length (`impedance_keys.L_TRANS_MM`): **in-house**, see `pcb-check-impedance` |
| L | the guide's figure when it has one and it applies; else reported with its skew | layout guide; `skew_ps` |
| VIA | reported: a guide's "minimise, pair on a single layer" has no number | layout guide |
| CPL | reported | guide: constant coupling |
| PLAN | every unreferenced run explained by a via or a pin; a cutout is an intent, judged by its impedance | guide: continuous return plane |
| RET | signal via to nearest GND via or GND through-hole pad ≤ `RET_MM` (step 2) | **in-house** (a guide that asks for a continuous return plane gives no distance), agreed with the designer; buses too slow for the rule are measured, out of the verdict |
| BETWEEN | no foreign copper between the legs, when the guide asks for it and it applies; effect computed when not met | layout guide |
| CLS | no width deviation; no critical net in `Default` | KiCad project |

**Mode B**: no new violation against the run made before the change, with the same rule file; no ink on a
neighbour's pad and no reference mark lost; no plane cut by the new tracks and vias; the other items are reported
with their estimate (`references/method.md`, "Mode B: converter block").

The audit is judged on the production stackup; repeat it on the prototype stackup when a verdict can flip.

## Self-checks
- The audit and the impedance check call the same path function (`kicad_routing.pad_path`) with the same `PATHS`.
- Critical nets in the `Default` class are listed: after a cleanup that renames nets, class patterns keyed on
  names go stale and the DRC stays silent.
- Useful frequencies through `rf_formulas.useful_frequency`, not typed.

## Tool contract
One script, `layout_audit.py`, KiCad's Python (`pcbnew`): the three impedance JSON files, the board and the `.kicad_pro`
→ `results/layout_audit.json`. It imports `PATHS` from the board's impedance extraction script; its target (`audit` in
`../pcb-verification/assets/Makefile`) comes after the impedance target.
- **JSON**: one row per pair and per single net (path length, target, median, out-of-tolerance length, worst
  value, useful frequency, return loss, branch length, P/N difference and skew, vias, vias beyond `RET_MM`,
  dominant gap, other-gap and uncoupled lengths, unreferenced length, foreign copper between, class and routed
  widths), the lengths and delays of the common-clock groups, copper under the magnetics per layer with the
  footprint area, pours outside `POWER`, the screening distance `RET_MM`, the state of each rule of the guides
  (criterion, reported, not applicable with its reason), and every return via (net, distance, inductance, added
  delay, slow flag).
- **Refusals of the board script**: a link without geometry, a key without impedance.

## Pitfalls
- **P/N matching follows the usable path.** A connector with doubled contacts (e.g. a USB-C receptacle, two rows)
  puts both rows in the net length: the mismatch is computed per usable path, and depends on the row in use.

## Limits
The return loss cascades the 2D sections of the path in a lossless line matched at both ends, at one delay per mm;
vias, pads and connectors are not in it. The return-via loop is an order of magnitude (two bare cylinders, planes
ignored); its effect on emissions is not computed here. BETWEEN tests the midpoint only, and from the P leg.
