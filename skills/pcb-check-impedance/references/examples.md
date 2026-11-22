# Impedance on the routed geometry: application cases

## Stackups used in the cases
Two builds of a four-layer board (about 1.6 mm), both from the stackup files shipped in
`pcb-verification/assets/stackups/`:
- **Stackup A**: prepreg of about 0.10 mm (εr about 4.1) under each outer layer, 1.38 mm from an outer layer to the
  far inner plane.
- **Stackup B**: prepreg of about 0.21 mm (εr about 4.4) under each outer layer, 1.29 mm to the far inner plane.

Finished outer copper of about 40 µm and solder mask as in the fabricator file. Widths and gaps are written
"width / gap" in mm.

## Cases by mechanism
- **Nominal cross-sections first, then the routed geometry: they do not tell the same story.** Setting: pair
  classes aimed at 90 Ω and 100 Ω and a 50 Ω single-line class. Computed: the nominal cross-sections on both
  stackups. Result: on A the nominal pairs are 90.4 and 98.7 Ω and the single line 51.1 Ω, so the classes are
  right; on B the same geometries give 107, 117 and 72.5 Ω, that is +19 %, +17 % and +45 % against the targets. The
  routed board still had 4.1 mm of a 100 Ω pair at 110–113 Ω near its connector, where the legs separate while
  keeping the pair width. Teaches: the class can be right and the copper wrong, and the stackup is part of the
  verdict (one verdict per build).
- **A lone leg wants the single-line width, not the pair width.** Setting: the legs of a 100 Ω pair (stackup A) leave
  the coupled part and run apart for a few millimetres, as when a transmit pair is separated by receive pins at the
  IC. Computed: the legs at the pair width 0.12 mm, then at 0.15 mm. Result: 113 Ω over 3 to 4 mm at 0.12 mm,
  102 Ω at 0.15 mm; hence two widths per pair class (track 0.15 mm, pair 0.12 mm with a 0.17 mm gap). With one
  width per class, a correction "0.12 mm for this pair" is applied to the lone legs too (102 → 113 Ω). Teaches:
  state a correction by nature of run, and give the class both widths.
- **A width off by 30 µm is a class error, not a detail.** Setting: stackup A, pair class 0.12 / 0.17 mm. Computed:
  the pair as routed, 0.15 / 0.14 mm. Result: 87 Ω over 7.5 to 8.3 mm for a 100 Ω target; the DRC stays silent
  because it only checks minima. Teaches: compare the routed width with the class, not only with the DRC.
- **A pair routed without a plane on purpose is judged for what it is.** Setting: a pair on the cable side of a
  twisted-pair port, the plane removed under it by design (stackup A). Computed: the pair as drawn, 0.192 / 0.14 mm
  with no plane; then a redraw at 0.30 / 0.14 mm over a far plane at 1.38 mm. Result: 112 Ω for 100 Ω intended
  (104–122 Ω with ±10 µm of etching per flank); 100.5 Ω for the redraw. A 3.8 mm fan-out of 0.12 mm legs past the
  edge of the adjacent plane reads 129–266 Ω, has no effect at 40 MHz, and nothing is asked. A pair in a deliberate
  cutout or over a far plane leaves the tolerance on its fan-outs to pads (choke, capacitors, terminal block): a
  deviation from the rule with a quantified effect, and no correction is asked when the effect is nil. Teaches:
  record the intention before judging; the rule is judged, the effect is quantified separately.
- **A deliberate length-matching detour leaves one leg alone for a few millimetres: two rules in conflict.** Setting:
  a pair with a meander on one leg to match lengths. Computed: skew in ps against the edge, return loss of the lone
  run, and the sampled impedance along the meander. Result: the straight leg stays coupled to the meandering one
  (gap 0.17–0.31 mm, 99–107 Ω, median 100 Ω), so the pair width is the right one along it; the lone stretch is
  quantified on both sides. Teaches: quantify both rules, record the designer's choice, and keep the accepted
  deviation listed as such.
- **A neighbouring branch can make a deviation false.** Setting: a USB pair at a receptacle whose second row of pins
  is fed by a branch of the other leg. Computed: the leg judged alone, then with the branch as partner. Result:
  107 Ω alone; the leg runs 0.14 mm from the branch, 91 Ω. Teaches: draw the run before writing "to be fixed", and
  take as partner any track of the partner net.
- **Unreferenced runs are mostly vias and through-hole pins.** Setting: a board whose "unreferenced" points
  (plane nicked within ±3 track widths) were listed. Result: runs of 0.5 to 5 mm, all at a via antipad or at the pins
  of an RJ45 jack: no plane cut. Teaches: word it "plane nicked", not "no plane"; the bounds judge it.
- **A plane edge entered as coplanar ground.** Setting: a pair off its plane, the adjacent-layer plane ending a
  little to the side. Computed: the copper of the adjacent layer taken as side ground 5 µm from the track, then at
  its oblique distance. Result: 55 Ω against about 250 Ω. Teaches: lower-layer copper is at an oblique distance,
  never coplanar ground, and the extreme cross-sections of a new situation are re-read before solver time is
  spent on them.
- **A plane gap with no keep-out is not a plane.** Setting: a 0.15 mm single line for a 50 Ω target, the adjacent
  plane interrupted without a keep-out, the next plane two layers down. Computed: the line solved over the missing
  adjacent plane, then over its real reference. Result: 51 Ω against 139 Ω, with no DRC error. Teaches: classify
  from the copper and report undeclared gaps as a finding.
- **A protection stub is not the line.** Setting: a differential pair with a protection device on a stub. Result:
  with the whole net sampled, the stub gave a "pair" at 49 Ω judged pass and a P/N mismatch of 5.7 mm that did not
  exist. Teaches: measure the pad-to-pad path.
- **A blanked target makes a fail pass.** Setting: a link whose target was replaced by "—" in a summary. Result: it
  was summarised as "within ±3 %" at 87 Ω. Teaches: the target is set before computing and kept; summary sentences
  are generated from the statistics.
- **A closed-form calculator and a solver disagree by the mask and the thickness.** Setting: no plane, 0.192 / 0.14 mm
  on 1.53 mm of εr 4.4. Result: the solver with the real copper and mask gives about 112 Ω; with copper thinned to 2 µm
  it gives 134 Ω, like the exact thin-strip formula; a calculator with a thin-copper model or an approximate
  thickness correction can therefore return 134 Ω as well as 100 Ω for this geometry. Teaches:
  check any calculator against the solver on a nominal section; it must model thickness and mask.
