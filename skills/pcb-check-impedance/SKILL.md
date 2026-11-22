---
name: pcb-check-impedance
description: "Controlled-impedance check of the routed geometry of a KiCad PCB's outer layers (microstrip under solder mask) with a 2D field solver on the fabricator's stackup (over a plane, a far plane or none), for every link whose standard sets an impedance (e.g. USB, Ethernet and field-bus pairs). Use to verify or choose widths and gaps, or explain a deviation."
---

# Check: impedance on the routed geometry

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `kicad_sampling.py`: the measurement of one link (KiCad's Python), on `kicad_routing.py` and `kicad_copper.py`;
- `impedance_keys.py`: keys, geometries, stackups, cache signature, judgement;
- `fieldsolver2d.py`: the solver;
- `impedance_solve.py`: `solve_keys`, the two passes with a bounded number of processes, and `targets_of`.

## Purpose
Does every controlled-impedance link keep its target impedance **along its whole routed length**, on the copper as drawn
rather than on the nominal width and gap? The check lists every continuous run that does not, with its position, length,
value and cause, and compares the routed width with the width the net class intends. The electrical effect of a
deviation (return loss of the path at the useful frequency) is computed in `pcb-check-layout-audit`.

## When it applies
- Every link whose standard sets an impedance (e.g. a USB or Ethernet pair, a long-reach field-bus pair). An
  impedance that an IC datasheet or a layout guide prescribes for a clock or a parallel bus (e.g. RMII), even written
  "must", is a means (`../pcb-verification/references/qualitative-rules.md`), judged by its effect in the timing or
  clock check.
- An electrically short link is still checked.
- The scope of use sets the stackups the board may be built on (one verdict per build), the zones where planes were
  removed on purpose, and the useful frequency of each link, which sizes the effect.

## Inputs to obtain
- **PCB** cleaned, zones filled; its `.kicad_pro` (net classes: track width, pair width, pair gap).
- **Schematic**: the critical links **end to end**, one entry per net between two components, IC pin to connector
  (a list that stops at the series resistors leaves the IC side unchecked); for every net with branches (protection
  device, pull, receive branch, second row of a USB-C receptacle), the two pads between which the signal travels.
- **Datasheets, layout guides, standards**: target and tolerance of each link, with the section of the IC's
  datasheet or of the standard that states them.
- **Fabricator**: one stackup JSON per build (`../pcb-verification/assets/stackups/`) and the fabricator file
  (e.g. `assets/fabricators/jlcpcb.json`: finished outer copper, etch profile, solder-mask thicknesses and
  permittivity), read and asserted by `impedance_keys`.
- **Designer**: the design intent before judging (a pair without a plane on purpose, a plane removed on the
  adjacent layer only, a length-matching detour); their own calculator's widths for the coupled pair and for a
  separated leg, entered in the net classes instead of assumed values; the reference layer of each routed layer,
  asked whenever no continuous plane under the links makes it obvious, or whether there is one at all. None is
  assumed from the stackup: neither the adjacent layer nor the middle layer of a group of close layers.

## Method
1. **Declare** the links (`PAIRS`, `SINGLE`), the end pads of the nets with branches (`PATHS`), and sort every pour
   net into `AC_REF` or `NOT_REF`, in writing, each refused pour with its reason (`reference_sets` stops on a pour
   net in neither).
2. **Sample** both nets of each pair and each single line with `kicad_sampling.sample_link`, along the signal path;
   the branches are measured apart.
3. **Classify** each point from the copper as routed (`situation_at`): adjacent plane, far plane or cutout. The
   keep-outs say whether an absence of plane was declared; an undeclared far or cutout length is a finding.
4. **Group** the points by cross-section key (`impedance_keys.make_key`), with their cumulated length.
5. **Solve** each key once per stackup (`impedance_keys.geometry` → `fieldsolver2d.solve`), cached under
   `cache_signature`, in two passes: the light method, then the fine mesh for the values near a tolerance limit of a
   link that uses them (`impedance_solve.solve_keys`, two processes by default). Etching corners: the main key of
   each link first, then the keys of the links whose verdict they can change (`corner_keys`).
6. **Judge per continuous run** of out-of-tolerance points, at the nominal and at the corners solved
  (`impedance_keys.judge_corners`); a run ends after more than `HEAL_MM` of conforming points.
7. **Compare the routed width with the net class**, by nature of run: coupled, or lone leg (`expected_width`).
8. **Cross-check the solver** by mesh refinement on the cross-sections that decide a verdict.
9. **Draw** every deviation and look before writing a verdict.

## Criteria
| Criterion | Source |
|---|---|
| Target ± tolerance over the whole length, as the link's own document states them (e.g. 100 Ω differential, ±10 %) | the section of the standard or IC datasheet; ±10 % in-house when none is stated, or when the stated one is wider (next row) |
| The same at the two etching corners of the fabricator file (width ± 2 × `etch_tolerance_per_flank`), where the nominal margin does not cover them: a link longer than `L_TRANS_MM` takes its corners when its nominal values, scaled by the corner excursion of its main key, show a deviation (`corner_keys`); otherwise its verdict is "at nominal". Nominal out of tolerance → fail; nominal in, a corner out → pass with reservation naming the corner, lifted (and no corner solved) when the designer states the board is ordered with impedance control | rule 8 of `pcb-verification`; fabricator file |
| Cumulated out-of-tolerance length, transitions included, above the larger of `L_TRANS_MM` and 10 % of the link: pass with reservation, the transitions listed | in-house |
| A continuous unreferenced run longer than `L_TRANS_MM` lies between its sampled value (full plane) and its value without the adjacent plane: both in tolerance → no deviation; the full-plane value above the upper limit → deviation; otherwise pass with reservation naming the run, its length and both bounds (`judge_corners`; the no-plane value is solved only on request) | in-house |
| A link whose standard allows a wider tolerance than the default (e.g. a USB pair: 90 Ω differential, tolerance of the order of ±15 %, to be confirmed in the edition that applies) is judged at ±10 % like the other links; the length outside the standard's tolerance is reported beside it | in-house for the ±10 %; the standard for the target |
| Judged per continuous run; an out-of-tolerance run of at most `L_TRANS_MM` is a **local transition** (branch-off to a pad, opening gap, meander): listed, not counted. A transition is local when its delay is small against the edge (e.g. under a twentieth of the rise time); its length follows from the edge and the delay per mm of the link (`delay = √εeff / c`, of the order of 6 ps/mm on outer-layer microstrip). The tool's 3 mm (about 17 ps) suits edges of about 0.5 ns or slower; recompute it for a faster edge | in-house, agreed with the designer, aims at outliers |
| Routed width = class pair width on coupled runs, class track width on lone legs and single lines (deviation over 1 µm, same transition rule) | KiCad project; in-house |
| A class whose pair width equals its track width does not encode the lone-leg width: reported, impedance alone judges | in-house |
| Single-ended line inside a plane cutout: deviation (sentinel 999 Ω) | no return path |

Numbers: `impedance_keys` (`TOL`, `L_TRANS_MM`, `reach_mm`, `NO_RETURN_OHM`), the stackup and fabricator files, the
board table (target of each link, from its datasheet or standard). Lone legs, fan-outs off the plane and deliberate
detours: `references/examples.md`, "Cases by mechanism".

## Self-checks
- Path tracks on a layer the tool does not handle are counted per link (`skipped_mm`) and reported; the link is then
  incomplete (`judge_corners`) unless its judged part fails.
- Each plane layer has a non-empty GND fill: zones not refilled leave the links without any plane (`require_domain`
  refuses an unfilled zone).
- Before any solver run, print per link the lengths per reference situation and the number of distinct keys, and
  re-read the extreme cross-sections of a new situation (smallest side gaps, widest pair gaps): a plane edge entered
  as coplanar ground a few µm from the track makes the track look walled in, and the impedance comes out several
  times too low.

## Tool contract
Numbers reach the report only through the JSON files. The target `impedance_board` of the Makefile runs the extraction with
KiCad's Python, then the solver script with the venv.
- `impedance_extract.py`, KiCad's Python: board and `.kicad_pro` → `results/impedance_geom.json`. Per link: name, nets,
  target, class (name, track width, pair width, pair gap), what `sample_link` returns, optionally `net_pads` (the pads
  of the net with their size and the reference under their centre, read by `pcb-check-port-network`).
- `impedance_board.py`, venv: that JSON, stackup and fabricator JSONs → `results/impedance_board.json` (per stackup and
  link: `link_stats`, `judge_corners`) and `results/impedance_cache.json` (`{"_signature", "<stackup>|<key>": {"z", "pass",
  "er_eff", "z_narrow", "pass_narrow", "z_wide", "pass_wide"}}`, as `solve_keys` returns them; "er_eff" gives the
  delay per mm of `pcb-check-layout-audit`).
- `zdiff_check.py`, venv: nominal cross-sections → `results/zdiff_check.json`; `impedance_view.py`, venv: one
  picture per deviation.
- **Refusals**: an input refused by a shared module makes the chapter incomplete, never a number.

## Pitfalls
- **The partner of a leg is any track of the partner net, branches included, and the line is the signal path.** A
  partner search limited to the partner's own path makes a false lone leg; a protection stub sampled as line makes a
  false pair and a false P/N mismatch.
- **A via antipad is plane because it holds a drill; a plane gap with no keep-out is not.** Solved over a plane
  that is not there, the gap reports an impedance far below the real one, whose reference is deeper.
- **A net between two parts of a link keeps an automatic name** (`Net-(D8-IO1-Pad6)`, between a series resistor
  and a protection) that the class patterns miss: it falls in the default class, and its width is compared with
  the wrong one. List the nets of every link from the schematic and report a net outside the link's class.
- **Give the lone leg its own class width, and judge runs, not points.** One width per class sends the coupled-pair
  width to the lone legs, whose impedance then rises; point counting buries the outliers under every fan-out.

## Limits
Quasi-static 2D solution of uniform sections of outer-layer microstrip under solder mask: no loss, no frequency
dependence; vias, pads and connectors are not modelled. Over an adjacent plane a pair run with legs more than 5 h apart
(at least 0.5 mm) is counted 2 × Z0, a convention, not a differential impedance (about 2 % high); over a far plane the
pair stays a pair up to 3 mm, in a cutout always, solved at its real gap up to 1.5 mm (beyond, a lower bound that is
judged only when it is already out of tolerance). Values rest on the fabricator's published assumptions; the check does
not replace a TDR measurement or the fabricator's impedance report.
