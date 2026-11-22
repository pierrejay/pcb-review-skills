# Layout audit: method in full, converter block, board table, algorithm, validation, reporting

## Mode A: the rules, how each is measured

### Where the rules come from
Typical content of a PHY layout guide (e.g. the layout sections of the TI DP83TD510E and DP83825I datasheets,
SNLS656D § 7.4 and SNLS638C § 8.4, in the editions read): differential and single-ended impedance of the target
over the whole length, no stub, pairs parallel with constant coupling and matched in length, a minimum of vias and
the pair on a single layer, a continuous return plane, no copper between the tracks of a pair, no floating
copper, no copper under a discrete transformer. A link standard adds its own figures (e.g. 90 Ω differential for
USB 2.0). Each rule is judged before it is coded (`../SKILL.md`, step 1).

### The table
Criteria and their sources: `../SKILL.md`, "Criteria".

| Rule | How it is measured |
|---|---|
| Z | deviations of `impedance_board.json` (continuous runs outside the tolerance band longer than the local-transition length); total out-of-tolerance length and worst value from the keys |
| L | P/N difference of path length, each leg = sum of track lengths + for each via crossed, the height between the two copper layers it joins (`pad_path(..., via_layers=True)`, which also gives an end pad's layer for a via in that pad; stackup); its skew (`rf_formulas.skew_ps`: length × delay per mm) |
| VIA | vias crossed by each leg |
| CPL | pair gap carrying the greatest coupled length; coupled length at another gap (more than 0.02 mm away); uncoupled length |
| PLAN | unreferenced length (via clearances, plane edges), and apart the length in a deliberate cutout and over a far plane |
| RET | distance from each signal via to the nearest GND via or GND through-hole pad, against `RET_MM` (below) |
| BETWEEN | length over which copper of another net lies midway between the two legs |
| CLS | routed widths against the class (`pcb-check-impedance`: pair width on coupled runs, track width on lone legs); critical nets left in the Default class |

**BETWEEN** protects the symmetry of the coupling of the two legs and the impedance of the pair: copper of another
net close to one leg and not to the other unbalances their capacitance to it (mode conversion) and shifts the
differential impedance. When the rule applies and is not met, the effect is computed apart: impedance of the pair
with and without the foreign copper in the cross-section of the field solver of `pcb-check-impedance`, and the
capacitance imbalance of the legs to it; where the cross-section cannot represent the situation, the effect is "to
be measured".

**RET: the screening distance.** The loop of a signal via and its nearest return via has the inductance L and adds
the delay τ of "Ground return via" below. A distance `RET_MM` is derived by choosing the delay the design
tolerates, a small fraction of the fastest edge of the links concerned (the fraction and the edge are the
designer's choice, written with the distance), then L_max [nH] = 2 · Z0 [Ω] · τ_max [ps] · 10⁻³ and
d_max = r · exp(L_max / (0.4 · h)), h the board thickness and r the barrel radius. The alternative is no
threshold: the inductance and delay of every via are reported and the designer reads them.

## Mode B: converter block (after a placement or a re-route)
Measured on the board with its zones refilled, and compared with the same extraction made before the change.
Criteria: `../SKILL.md`, "Criteria"; the other items are read as below.

| Item | How it is measured | Read as |
|---|---|---|
| Rules and connections | DRC with zone refill and schematic parity, against the run made before the change **with the same rule file** | usual leftovers of hand routing: via clusters of one rail slightly under the hole-to-hole minimum, track stubs of a fraction of a millimetre |
| Ground pour of the component side | islands of the filled zone, with the pads and vias inside each | reported: which input capacitors share an island with the ground pin of their converter, and how many vias each island has |
| Input loop | when capacitor and ground pin sit on two islands, the current returns through the vias and the adjacent plane: L ≈ µ0 · h · l / w (h to that plane, l length of the path, w its width), an estimate | compared with the capacitor's own inductance (typically a few tenths of a nH for a small ceramic case; read the datasheet or the mounting model) |
| Enable and power-good tracks | length; smallest gap to the copper of each switch node; length lying within a few fixed distances of it (e.g. 0.3 / 0.5 / 1 mm) | coupled capacitance ≈ own capacitance of the track (of the order of 0.1 pF/mm for a track whose width is comparable to its height over the plane; compute it with the field solver) × 1 / (1 + (s/h)²), an estimate valid over a continuous plane under both conductors (it can sit a few times above the mutual capacitance of a 2D field solution, the safe side; not applicable over a slot or an edge of the plane). Node released: glitch = swing × Cm / Cnode. Node held low: R_on × Cm × dV/dt. Both against the guaranteed thresholds |
| Feedback tracks | length; gap to the switch nodes | reported |
| Other layers | area and number of islands of each plane inside the window, before and after | the criterion of `../SKILL.md` |
| Silkscreen | outline of each part against the mask openings of the **other** parts; pin-1 marks; DRC with `silk_over_copper` set to "warning" for this run in a copy of the project, items read inside the block (procedure and reading: `pcb-verification/references/toolchain.md`) | the DRC flags the reference marks that fall on a pad; outline overlaps are measured directly and are cosmetic in general, the fabricator clipping silkscreen from pads |

## Quantified effect (`rf_formulas`)
- **Return loss of the path** (`return_loss_sections_db(sections, z0, f_hz, tpd_s_per_mm)`). The sampled points of
  the path in order, each a section at its impedance (`impedance_keys.point_impedance`) over its length, in a
  lossless line Z0 matched at both ends, at the useful frequency f: from the load, Γ = (Z_load − Z) / (Z_load + Z) at
  the far end of a section, Γ·e^(−2jθ) at its near end, θ = 2π·f·L·tpd; RL = −20·log10 |Γin|. The out-of-tolerance
  length grouped at one impedance (`return_loss_db`, one uniform run) is neither a bound nor pessimistic, however
  short the runs: separate runs add up or cancel with the phase of the line between them (`rf_formulas`).
- **Useful frequency** (`USEFUL_FREQUENCY`, with its reason per entry; `rf_formulas.useful_frequency(link_type)`):
  the highest frequency at which a mismatched run can still affect the link. Two bases. For a digital line, the
  knee of its fastest edge, f ≈ 0.35 / t_r (t_r the 10–90 % rise time, the shortest one the driver or the standard
  allows). For a line-coded link whose standard specifies return loss up to a frequency, that frequency, or a
  modest margin above it. Entries of the table, to be confirmed in the standard of the link, e.g.: USB high speed
  700 MHz (0.35 / 0.5 ns); 100BASE-TX 100 MHz (return loss specified up to 80 MHz); 10BASE-T1L 20 MHz;
  10BASE-T1S 40 MHz. A link type not in the table is added there with its reason, never typed in a script.
- **Ground return via** (`via_loop_inductance_nh(h_mm, d_mm, drill_mm, plating_mm=0.020)`, `delay_ps(l_nh, z0)`).
  A signal via and its nearest ground via form two parallel barrels of the board thickness h: loop inductance
  L = (µ0/π)·h·ln(d/r) = 0.4 nH/mm × h × ln(d/r), with d the centre distance and r the barrel radius (drill / 2 +
  plating, 0.02 mm by default; d bounded below by 2 r). Added delay τ = L / (2·Z0).
- **P/N mismatch** (`skew_ps(delta_mm, tpd_s_per_mm)`): skew = ΔL × delay per mm, compared with the edge.

Delay per mm of a link: `impedance_keys.delay_per_mm(bins, emap)` on its keys, `emap` = the "er_eff" of each entry
"<stackup>|<key>" of `impedance_cache.json` for the stackup judged (√εeff / c of the solved section, with the
solder mask of the build; the odd mode for a pair), in s/mm for `rf_formulas`. Its order of magnitude is 6 ps/mm for
an outer-layer track under mask on FR-4.

## Building the tool
Script, outputs and refusals: `../SKILL.md`, "Tool contract".

### Board table
| Declaration | Content |
|---|---|
| `PATHS`, signal-path function | imported, not copied (`PATHS`: `../SKILL.md`, "Tool contract"; `pad_path`: "Resources") |
| `RET_MM` | in-house screening distance with its derivation (above), labelled as such in the comment and in the report |
| `SLOW` | nets of buses too slow for the rule, flagged in the output and excluded from the RET and CLS verdicts |
| `TOL`, `BOARD_T` | tolerance (`impedance_keys.TOL`; the guide's when it differs); board thickness for via barrels |
| `F_USEFUL` | link name prefix → entry of `rf_formulas.USEFUL_FREQUENCY` (the reason lives in the table: "Useful frequency" above) |
| `TPD` | delay per mm (s/mm) of each link, `impedance_keys.delay_per_mm` ("Delay per mm" above) |
| `POWER` | ground and supply net names, read from the board's zones and checked by eye |
| magnetics reference | footprint whose courtyard is examined |

### Algorithm
1. Load the board; split `GetTracks()` into vias and tracks per net (arcs are tracks). Ground return points:
   positions of the GND vias and of the GND through-hole pads.
2. For each path of `PATHS` (one per line a net travels), keep only the legs of the signal path (`pad_path`: the copper
   actually travelled, part of a segment at a T-junction) and the layers each via it crosses joins
   (`via_layers=True`). A net absent from `PATHS` is followed the way `sample_link` follows it: between its two pads
   (`pad_path` with those two pads), or, with one track and not two pads, that track; any other net is named in
   `PATHS`.
3. Z: for each key of the link, impedance from the cache on the production stackup (`impedance_keys.point_impedance`:
   2 × Z0 for a single-line key inside a pair); sum the lengths outside the tolerance band
   (`impedance_keys.out_of_tolerance`: a value on a limit is inside) and keep the value farthest from the target.
   Take the deviations (runs) from `impedance_board.json`.
4. L and VIA as in the table; mean length of the two legs as the link length.
5. CPL: histogram of coupled length per gap from the keys (`parse_key`: `s` of the `diff*` keys).
6. PLAN: the three lengths from `impedance_geom.json` (unreferenced, counted on the points over the adjacent plane
   only; cutout; far plane).
7. RET: for every signal via of the link, distance to the nearest ground return point, loop inductance
   (`via_loop_inductance_nh(BOARD_T, d, drill)`), count of those beyond `RET_MM`; store every via (net, distance,
   inductance, slow flag). Keep exactly the vias on the path: taking every via of a net as soon as its path
   crosses one counts the vias of its branches.
8. BETWEEN: sample the P leg every 0.1 mm; nearest piece of the N leg on the same layer; if the edge-to-edge
   distance is between 0 and 0.5 mm, test the midpoint against the filled area of every zone of another net
   (`zone.HitTestFilledArea(layer, point)`) and against every track of another net (`track.HitTest(point)`);
   accumulate the length per offending net. Cut arcs into chords first (`kicad_routing.track_pieces`, the same
   pieces as the impedance check).
9. CLS: routed length per width on the path; class name of the net (`kicad_copper.net_by_name(board, net).GetNetClassName()`), class
   widths from `net_settings.classes` of the `.kicad_pro` (`impedance_keys.net_classes`); list of critical nets
   whose class is `Default`.
10. Copper inside a footprint: bounding box of its courtyard; per copper layer, area of the intersection of each
    zone's fill with that box (`SHAPE_POLY_SET.BooleanIntersection`, `Area()`), against the area of the box.
11. Pours whose net is not in `POWER`.
12. Return loss per pair: the points of each leg in path order, each (`point_impedance`, its length), cascaded at the
    useful frequency (`return_loss_sections_db(sections, target, f_useful, TPD)`), the lower of the two legs;
    with no length out of tolerance, no call: return loss null, "no run out of tolerance"; `skew_ps` of the P/N
    difference; `delay_ps` of each return loop. Write the JSON; print one line per link.

## Validation cases
On the board: the audit's Z column equals the impedance check's out-of-tolerance length (same keys, same cache),
and the P/N length of a pair without branches equals the net lengths KiCad shows.

## Reporting
- One table: a line per link, a column per rule, with value, criterion and verdict; then the list of return vias
  with distance and inductance.
- Each fail names its run, width or via, and is worded: "<run> routed at <width> in a class at <class width>:
  <impedance> over <length>; return loss <x> dB at <useful frequency>: fails the rule, no effect on the link; to
  correct at the next routing (<width / gap>, by nature of run)".
- Qualitative rules: the table of `pcb-verification/references/qualitative-rules.md`, one row per rule of the
  guides, those judged not applicable included.
- Measurements to request when an effect cannot be computed: emissions pre-scan for return-via outliers,
  common-mode current on the cable for copper under magnetics.
