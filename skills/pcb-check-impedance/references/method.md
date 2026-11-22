# Impedance on the routed geometry: method in full, board table, algorithm, validation, reporting

## Declare: the board table
At the top of the extraction script:

| Declaration | Content |
|---|---|
| `PAIRS` | (link name, P net, N net, target Ω), one per net segment, checked against the schematic |
| `SINGLE` | single-ended nets (target Ω from the link's datasheet), both sides of each series resistor |
| `PATHS` | net → [((ref, pad), (ref, pad)), …] for every net with branches, one path per line the signal travels, each sampled by its own `sample_link` call and judged apart (a USB-C receptacle: one per orientation; a star: one per arm); their lengths are not added. Other nets are sampled whole |
| `AC_REF`, `NOT_REF` | pour nets accepted as AC reference (ground, decoupled supplies); pour nets refused, each with its reason (shield through a capacitor, chassis, floating, other domain) |
| `ADJ`, `LAYERS`, `DEEPER` | adjacent layer of each routed outer layer; the routed layers; layers beyond the adjacent one, nearest first (every one a copper layer of the board). The reference the designer intends (`SKILL.md`, Inputs) is expressed by these lists and by `AC_REF`: a reference deeper than the adjacent layer is solved as a far plane |
| `H_PREPREG`, `H_MAX` | prepreg height of the build sampled, for the oblique distance off the plane, and the largest prepreg height among the builds (`h_max_mm`, which sets the coupling limit and the side-ground reach), read from the stackup files (`Slab.h_prepreg`). Builds of different prepregs are sampled once each, with their own `H_PREPREG` and the same `H_MAX`; the solver script checks each sample against its build (`impedance_keys.check_sampled_h`) |
| stackup and fabricator | the names of the stackup file of every build and of the fabricator file |
| constants | all in `impedance_keys` and `kicad_sampling`: step 0.1 mm; coupling limit 5 h and side-ground reach 6 h, at least 0.5 and 0.6 mm (`reach_mm`); far-plane pair reach 3 mm; clearance at most 3 mm across; nothing to retype |

In the solver script: `STACKUPS` = {name: `read_stackup(path)`} for every build, the fabricator dict =
`read_fabricator(path, slab)` (copper thicknesses asserted against the stackup), `TOL` 0.10, `L_TRANS_MM` 3 mm,
`NEIGHBOUR_MM` 0.25 mm imported from `impedance_keys`.

## Sample: what is measured at a point
- **Signal path**: on a net with branches only the pad-to-pad shortest path is the line (`kicad_routing.pad_path`);
  the branches are measured apart (total length, and length per reference situation, because they load the node).
- **Both legs of a pair** are sampled, each with the other as partner (`sample_link(P, partner=N)` and
  `sample_link(N, partner=P)`). Sampled on one leg only, the other leg enters only as the partner: its width is not
  checked against the class and a run where it is alone is not judged; the report then says so.
- **Partner of a leg**: the nearest piece of **any track of the partner net on the same layer, branches
  included**. A leg that runs along a branch of the other net is coupled to it.
- **Coupled or not**: over an adjacent plane, a leg whose partner is more than 5 h away edge to edge (h: `H_MAX`; at
  least 0.5 mm) is a single line; it is solved as such and counts 2 × Z0 in the pair, which then overstates the
  differential impedance by about 2 %. When several builds are judged, the limit of the thickest applies to all of them:
  the thinner build moves too, and the number of geometries to solve grows (2.5 × when the limit goes from 0.5 to 1.05
  mm).
- **Coplanar ground**: distance from the track edge, perpendicular to the track and away from the partner, to the first
  copper of a pour **whose net is declared as an AC reference** (`AC_REF`: ground, and the supply pours decoupled to it)
  or the first GND track or pad; searched in 0.01 mm steps up to 6 h (at least 0.6 mm; beyond, effect ≤ 0.1 %: recorded
  as absent). Measured on the **filled** copper. A shield or chassis pour tied through a capacitor or a resistor, a
  floating pour, the ground of another isolated domain are not references: they go to `NOT_REF` with the reason. The
  same sets serve the far plane.
- **Reference plane**: AC-reference copper on the adjacent layer (`reference_sets`: declared pours and every copper of
  the ground net of the links' domain, `gnd_net`, "GND" by default; no net of `NOT_REF`, its tracks and pads
  included; the same set that decides "plane" in `reference_at`). A point classified on the adjacent plane (Classify) is
  also flagged "unreferenced" when that copper does not cover the whole normal segment from −3 to +3 track widths (a
  generous band: the return current spreads over about three dielectric heights): via clearance, plane edge, a slot
  parallel to the track anywhere in the band. Unreferenced points are counted and located, and still solved over the
  plane; a real plane cut is an unreferenced run away from any via or pin. Wording: an "unreferenced" point is a track
  still over its plane whose band is nicked by a clearance, not a track without a plane; write "plane nicked within ±3
  widths (via or pin clearance)" in a report, never "no plane", which a reader takes for a cut.

## Classify: three reference situations
| Situation | Keys | How it is recognised (`kicad_sampling.situation_at`) | How it is solved |
|---|---|---|---|
| Plane on the adjacent layer | `diff`, `se` | ground copper under the point on the adjacent layer, or the point in a drilled clearance of that plane at most 3 mm across (`reference_at`) | microstrip at the prepreg height |
| **Cutout** (no plane at all) | `diff_np`, `se_np` | no ground copper under the point on the adjacent layer nor on any deeper layer | bare laminate (prepreg on core, air below), `plane=False` |
| **Far plane** | `diff_p2`, `se_p2` + name of the reference layer | no ground copper under the point on the adjacent layer, ground copper on a deeper layer | plane at its real distance through prepreg then core (`Slab.h_between`, read from the stackup file: the outer layer to the deeper plane, whatever the layer count); the dielectrics after the prepreg at the permittivity of the first of them (`Slab.er_core`) |

- The classification comes from the **copper**, not from the keep-out areas. A hole in the adjacent plane that
  holds a drill (via clearance, antipads in a row) is "plane": the criterion "nothing under the axis" alone
  classifies short stretches at via antipads as plane cutout, and `reference_at` answers it by the exact clearance
  test. The entry of a track into a via or pad of its own net is a transition too (`reference_at` with the net and
  the sampled piece: the piece must END in the real copper of that via or pad, within half its width, and the point
  lie within `OWN_RING_NM` = 0.5 mm of that copper, with ground of the adjacent layer near the drill; a track that
  only passes near a pad of its net, or a point beyond 0.5 mm of an oblong pad's real outline, is not an entry): a
  clearance merged with a channel of the plane, or the common clearance of a row of through-hole pins (a USB-C
  connector), is not an opening of the plane for the track that ends in it; a 2D section solved over a deeper plane
  for those few tenths of a millimetre has no meaning. A via or pad inside a deliberate void (no ground near it)
  keeps its situation. A gap that cuts the return path under the track is still seen by this classification, along
  the track; the ground via near the layer change is judged in `pcb-check-layout-audit`.
- The keep-out areas say whether the designer **declared** the absence of plane (`declared_at`): far and cutout
  lengths found outside any keep-out go to `undeclared_mm`, a finding to show the designer. Inside a pour keep-out
  of the adjacent layer a point is never "plane", even around a drill: a declared void that holds a via is not a via
  clearance.
- Far plane, on a clearance of that plane (through-hole pad of a terminal block): the plane is kept as reference
  when the point lies in a hole of the plane that holds a drill (via or pad hole) and is at most 3 mm across
  (`reference_at`: an exact test, no sampling; a slot holds no drill, a split is not a hole); otherwise (a slot,
  whatever its angle; a split; a wider opening) the point is a cutout.
- No plane: a lone leg has no impedance. The pair is solved at its real gap (10 µm under 0.5 mm, 0.1 mm above),
  and a partner 0.5 mm away or more (fan-out to pads) is counted uncoupled for the width. Beyond 1.5 mm
  (`CUTOUT_GAP_CAP_MM`, a cost bound: about 100 s per key there, 15 min at 3 mm) the gap is solved at 1.5 mm, a
  lower bound of the impedance: out of tolerance if that bound is above the upper limit, refused by `judge_link`
  otherwise (a lower bound inside the tolerance does not show that the real value is). Orders of magnitude, 0.136 mm
  tracks on the outer layer of a four-layer build with no plane under them: 188 Ω at 0.5 mm, 262 Ω at 1.5 mm,
  320 Ω at 3 mm. A single-ended line in a cutout has no return: it is given the
  sentinel 999 Ω (`NO_RETURN_OHM`) and is a deviation.
- Far plane: two legs stay coupled far beyond 0.5 mm, so the pair gap is searched up to 3 mm.
- Off the adjacent plane (cutout or far plane), ground copper on the adjacent layer (the plane edge, one prepreg
  lower) is side ground at its **oblique** distance √(d² + h²), never coplanar ground touching the track; the gap
  is then rounded up to 0.05 mm (the impedance varies slowly there and every distinct value costs a solver run).

## Group
The points of one cross-section share one key (`impedance_keys.make_key`): a JSON list that names the cross-section
without board data, layers by name, dimensions rounded so that one solver run serves every point within the rounding.
`bins` cumulates the length per key; `points` keeps each point,
in path order, for the runs.

## Solve

### Cross-section parameters: the fabricator's, not the skill's
Five quantities come from the fabricator's published assumptions (finished outer copper, etch profile, the two
solder-mask thicknesses and the mask permittivity) and the rest from the stackup file of each build. They live in
`pcb-verification/assets/fabricators/<name>.json` and `pcb-verification/assets/stackups/`, read by
`impedance_keys.read_fabricator` and `read_stackup` and asserted against each other (copper thicknesses) and
against the constants the scripts use; another fabricator is another file, not another skill.

| Quantity | Where it comes from | Order of magnitude on a four-layer build of a low-cost fabricator (illustration; read the real value) |
|---|---|---|
| Outer copper, finished | fabricator file | of the order of 40 µm after plating; trapezoid, top narrower than the base by of the order of 20 µm |
| Solder mask | fabricator file | thicker on laminate (`c1`, of the order of 30 µm) than on copper (`c2`, of the order of 15 µm), εr near 3.8 |
| Prepreg under the outer layers | stackup file | 0.1 to 0.2 mm, εr 4.1 to 4.4 depending on the glass style |
| Inner copper, core | stackup file | of the order of 15 µm; core of the order of 1 mm, εr near 4.4 |
| Outer copper to outer copper (`Slab.slab_mm`) | stackup file | the slab of a cutout; of the order of 1.5 mm |
| Outer layer to the far inner plane (`Slab.h_between`) | stackup file | of the order of 1.3 to 1.4 mm |

### Impedance of a cross-section
`fieldsolver2d` computes the capacitance per unit length with the dielectrics (C) and in air (C0):
Z0 = 1 / (c·√(C·C0)), εeff = C / C0, delay per unit length √εeff / c (εeff kept in the cache, the odd mode for a
pair); a pair is solved in its even and odd modes, Zdiff = 2·Zodd.

### Table key → Geometry
Each key becomes a `fieldsolver2d.Geometry` and a fine mesh step (`impedance_keys.geometry(key, slab, fab)`; lengths
in mm, the fields as `Geometry` defines them):

| Key | `h` | Other fields | Mesh |
|---|---|---|---|
| `se`, `diff` | prepreg height under the track layer | `er` of the prepreg | default |
| `diff_np` | outer copper to outer copper | `plane=False`, `h_top`, `er_core` | `d_fine = min(max(w, s, 0.05) / 80, 0.003)` |
| `se_np` | not solved | 999 Ω | — |
| `se_p2`, `diff_p2` | distance from the track layer to the named reference layer (`Slab.h_between`: slab − prepreg − inner copper for the far inner layer, whole slab for the opposite face) | `h_top`, `er_core` | `d_fine = 0.004` |

Always, from the fabricator file: `t` = finished outer copper, `w_top` = `w` − etch reduction, `c1` = mask on
laminate, `c2` = mask on copper (all read from the file, none retyped); for a pair `w` is the mean of the two
leg widths. Side ground: `side_gap=g_self, side_left=(g_self is not None),
side_gap2=(g_partner if g_partner is not None else 0.0)`. The trap: `side_gap2=None` means "same as the left
side"; "no ground on the right" is `0.0`.

### Two passes, and the cache
The cache is discarded whole when its signature differs (`cache_signature(STACKUPS, fab, extra)`, `extra` being the
source of the board script's own function that calls the solver). `impedance_solve.solve_keys` does both passes; the
board script gives it the pairs `impedance_solve.pending(cache, pairs, targets, corners)` returns (an entry absent, or
without a field the links now require), the targets of each key (`targets_of`) and the corner keys, then merges the
results into the cache. Corners in two calls: `corner_keys([(link, pair)])` (main keys), then
`corner_keys(links, zmaps)` with those at their corners (the keys of the links they can change). Light pass:
every pair at 2 × and 4 × the step of the table, extrapolated (`richardson`), the corner keys at their two etching
corners too. Fine pass: only the values, nominal or corner, for which `needs_fine` is true (within
`RICHARDSON_BAND`, 1 %, of a tolerance limit of a link that uses the key), at the step of the table. Error of the
light pass against the fine pass: under 0.2 % on the shipped stackups (plane, far plane, no plane), for a sixth to a
fifth of the time; the fine pass is typically left with one key in twenty. On another kind of build (stripline,
thicker copper, another solver), re-measure it on a sample before relying on it. Two processes by default
(`workers`: from hundreds of MB to 2 GB each on a fine mesh), one board at a time, so that the machine stays
usable; more only on a machine left to the review. The script calls `solve_keys` under `if __name__ == "__main__":` (processes are started by spawn). The cost per cross-section grows with the node
count: seconds over an adjacent plane (about 10⁵ nodes), up to minutes over a far plane, which is why the cache is keyed
and kept.

## Judge per continuous run
Per link and per stackup, `link_stats` gives the length-weighted minimum, median and maximum, the lengths out of
±10 % and ±15 % and the uncoupled length; the unreferenced, cutout, far-plane and branch lengths come from the
geometry JSON. The out-of-tolerance points are grouped into runs **along the path** (`runs`, `judge_link`):
consecutive in the sampled order, on one layer, closer than `NEIGHBOUR_MM` (0.25 mm); more than `HEAL_MM` (1 mm)
of conforming points between two of them separates them. Joining on XY proximity would merge portions far apart along the path, or stacked on two
layers, into one longer deviation. A run longer than the local-transition length (`L_TRANS_MM`, 3 mm) is a
deviation; shorter runs are counted as transitions, with the longest.

## Compare the routed width with the net class
The same runs, on the points whose width differs from the width the class intends for them (`expected_width`: pair
width on coupled points, track width on lone legs and single lines; a lone leg is not judged when the class gives
both the same width).

## Cross-check the solver
On the cross-sections that decide a verdict: the solver at 1, 0.7 and 0.5 times the default step.
The grid has a line on every copper and dielectric edge near the tracks (the bottom of a slab without a plane is
the exception: it lies between nodes), so the value converges as the step shrinks: it moves by less than 0.2 %
between these steps, and a larger spread is a meshing defect, not a result. Where a section is one
of "Validation cases", its value is found again there. A closed-form calculator can be off by of the order of 10 %
on Zdiff for an outer-layer pair of this size when it ignores the mask or falls outside the domain of its thickness
correction: check any calculator against the solver on a nominal section before using it.

## Draw
For each deviation, a window around its centroid showing the tracks of both nets coloured by width (branches
included), the pads and the out-of-tolerance points.

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

### Algorithm
Extraction, KiCad's Python:
1. Load the board.
2. Build the copper sets once per ground domain of the links: `sets = reference_sets(board, LAYERS, ADJ, AC_REF,
   NOT_REF, gnd_net=<ground net of the domain>)`; print the two lists.
3. For each build of distinct prepreg, each net of a link and each of its paths (one call without `ends` for a net not
   in `PATHS`): `sample_link(board, net, sets, DEEPER, H_PREPREG, partner=<other net or None>, ends=<path>,
   h_max_mm=H_MAX)` (Sample, Classify, Group).
4. Per link, the record of the tool contract; the class name of a net is `kicad_copper.net_by_name(board, net).GetNetClassName()`, its
   widths are read from `net_settings.classes` of the `.kicad_pro` through `impedance_keys.net_classes`.

Solving, venv:
5. Collect the distinct keys of all links; load the cache; light pass, then fine pass (Solve).
6. Per link and per stackup: `check_sampled_h` on its sample, then `link_stats`, `judge_corners` (Judge per continuous
  run at the nominal and the corners solved, Compare the routed width). An unreferenced run longer than `L_TRANS_MM`
  is judged between its key (full plane) and `zmaps["no_plane"]`, the same section re-keyed off the plane
  (`make_key("far", …, ref_layer=<first deeper plane>)`, or "cutout"), solved only when its reservation matters.
7. Cross-check the cross-sections that decide a verdict; draw each deviation.

## Validation cases
Solver values with the two stackup files shipped (a thin-prepreg and a thick-prepreg build) and the fabricator file
`jlcpcb.json` (default mesh unless stated), through `impedance_keys.geometry` as a board script computes them: a
board script finds them again on the same cross-section. **Stackup A**: prepreg 0.0994 mm, εr 4.1, core 1.265 mm,
1.494 mm outer copper to outer copper, 1.380 mm to the far inner plane. **Stackup B**: prepreg 0.2104 mm, εr 4.4,
core 1.065 mm, 1.516 mm and 1.291 mm. They illustrate orders of magnitude and the size of each effect; they are not
targets for another build:

| Cross-section (width / gap, mm) | A | B |
|---|---|---|
| Single 0.15 | 51.1 Ω, εeff 3.26 (6.0 ps/mm), 0.118 pF/mm; without mask 54.4 Ω, εeff 2.88 (5.7 ps/mm) | 72.5 Ω, εeff 3.26 (6.0 ps/mm), 0.083 pF/mm; without mask 76.5 Ω (5.7 ps/mm) |
| Single 0.12; single 0.5 | 56.5 Ω; 25.0 Ω | |
| Pair 0.12 / 0.17 | 98.7 Ω | 117.3 Ω |
| same, no mask; Kirschning–Jansen | 107.6 Ω; 109.9 Ω | 127.8 Ω; 133.2 Ω |
| Pair 0.136 / 0.14 | 90.4 Ω; no mask 98.7 Ω; closed form 101.7 Ω | 106.8 Ω; 116.7 Ω; 123.0 Ω |
| Pair 0.15 / 0.14 | 86.8 Ω; no mask 94.3 Ω; closed form 97.2 Ω | 103.7 Ω; 113.1 Ω; 119.0 Ω |
| Fabricator's own dimensions for 90 Ω (0.1321 / 0.14) and 100 Ω (0.1107 / 0.1699) | 91.5 Ω and 101.8 Ω | |
| No plane, 0.192 / 0.14 | 111.1 Ω; ±10 µm of etching per flank: 103–119 Ω | 109.3 Ω |
| No plane: 0.12 / 0.17; 0.25 / 0.12; 0.30 / 0.14; 0.192 / 0.10 | 132; 99; 101; 98 Ω | 1.5 to 2 Ω lower |
| Far plane at 1.380 mm, 0.30 / 0.14 (`d_fine=0.004`) | 99.8 Ω; ±10 µm per flank: 93–106 Ω | 98.2 Ω |
| Far plane, 0.24 / 0.12 | 99.3 Ω | |

- The mask lowers Zdiff by about 8 % for an outer-layer pair of this size (98.7 Ω against 107.6 Ω in the table).
  Without mask the closed forms come out 2 % (A) to 5 % (B) above the solver: their thickness correction for
  40 µm of trapezoidal copper is the approximation.
- No plane, 0.192 / 0.14 mm: without mask +10 Ω; with thin copper (exact thin-strip formula, 1.53 mm of εr 4.4)
  134 Ω. A thin-copper calculator, or one with an approximate thickness correction, can therefore return 100 Ω as
  well as 134 Ω for this geometry.
- Far plane at about 1.4 mm on an εr near 4.4 laminate: the result hardly depends on the thickness of the prepreg
  above it, and a 50 Ω single line would need of the order of 2.5 mm of width; pads and tracks weigh little in
  capacitance. Another plane distance or permittivity changes these statements: compute the cross-section.

## Reporting
- Per link and per stackup: target, minimum / median / maximum, number and length of deviations, worst value,
  number of transitions and the longest, uncoupled / unreferenced / cutout / far-plane lengths.
- Each deviation: net, layer, position (x, y), length, width, gap, value, and **why**: "a lone leg because the
  transmit pins are separated by the receive pins at the IC" (e.g.), "a leg that leaves its via 4 mm before its
  partner", not just "separated legs at 0.12 mm".
- The picture of each deviation is attached.
- A correction, by nature of run: "lone legs of pair X between the IC and the termination resistors, L mm: w1 → w2
  mm (Z1 → Z2 Ω); coupled part unchanged at w / g mm".
