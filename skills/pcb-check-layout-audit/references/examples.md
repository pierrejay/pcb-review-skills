# Layout audit: application cases

## Cases by mechanism
- **A routed width that differs from the class width passes the DRC and misses the impedance.** A differential
  pair on an outer layer, target 100 Ω, routed at 0.15 / 0.14 mm in a net class declared at 0.12 mm. On a thin
  prepreg between the outer layer and its plane the run is at 87 Ω over 14.4 mm; on a thicker prepreg the same
  geometry is at 106 Ω, so the verdict depends on the stackup. Effect on the link: return loss 71 dB at 3.75 MHz
  and 57 dB at 20 MHz. Fails the rule, no effect on the link. Teaches: the DRC only checks minima; the
  comparison with the class width is what catches the deviation, and the stackup is stated in the verdict.
- **Orders of magnitude of the return loss of a mismatched run.** One run of 1 to 6 mm, 7 to 19 % off the target,
  alone in a line matched at both ends (`return_loss_sections_db`, 5.7–6.0 ps/mm): return loss of 31–55 dB for a
  high-speed USB link (90 Ω) at 700 MHz, 48–72 dB for a 100BASE-TX link at 100 MHz, 62–86 dB for a 10BASE-T1L link
  at 20 MHz. Teaches: a short run a
  few percent to some 20 % off its target typically costs tens of dB of return loss at the useful frequency, an
  order of magnitude; the figure compared with the return-loss requirement of the link is the cascade of its path
  (grouped runs can add up or cancel); the rule is still failed, and the effect says how much it matters.
- **A threshold decides what the summary says.** Signal vias of high-speed links, nearest ground via found by
  script. Setting 1 (two ground planes): 27 signal vias, the farthest ground via at 2.7 mm (loop 1.8 nH, 18 ps on
  50 Ω): none beyond a 3 mm screening distance, whereas a 1 mm habit presented as a rule gave "10 vias without
  ground" for vias that had a ground via 1.2 to 2.7 mm away. Setting 2: the only two vias beyond 3 mm (5.0 and
  6.1 mm, 2.2 and 2.3 nH) belonged to a 2.5 MHz management bus, outside the verdict of a high-speed rule. Teaches:
  a distance is derived from the delay the edge tolerates, labelled in-house, and applied to the links it
  targets; a column label says what is measured.
- **A protection stub is not the line.** Each leg of a differential link reaches a protection array through a
  0.5 mm wide stub (4.6 mm on one leg; 8.4 mm with two vias on the other). Counted as line, the pair came out at
  50 Ω with 5.7 mm of P/N mismatch; on the signal path, the link is two uncoupled 0.15 mm tracks (2 × 51 Ω).
  Teaches: measure on the pad-to-pad path with the branches excluded, the same way in every check.
- **P/N matching follows the real path.** Near a USB-C receptacle, whose contacts are doubled on two rows, the
  mismatch was 2.2 mm or 4.4 mm depending on the plug orientation once the path through each row was followed.
  Teaches: the net length of a connector with doubled contacts includes both rows; the mismatch is computed per
  usable path.
- **A rule written for a discrete part does not apply as written to an integrated one.** "No copper under the
  transformer" in a layout guide aims at a discrete transformer routed on the board. Under an RJ45 jack with
  integrated magnetics, 268–297 mm² of plane on three layers lay inside a 408 mm² footprint; voiding them would
  have put the Ethernet pairs routed over them at 132–147 Ω instead of 99 Ω. Planes kept; the rule was judged
  not applicable, with the numbers on both sides. Teaches: a manufacturer's rule becomes a criterion after
  mechanism, applicability and numbers, and an unmet rule that does not apply is not a fail.
- **Net classes go stale after a cleanup.** After nets were renamed by an import cleanup, four critical nets were
  found in the Default class: class assignments keyed on net names no longer matched, and the DRC stayed silent.
  Teaches: list the critical nets left in Default at every run.
- **The loop through the plane before asking for a top-layer ground path.** Enable tracks cut the component-side
  pour between three input capacitors and the ground pins of their converters. The current returns through two
  vias at each end and a plane 0.1 mm below: loop of about 0.5 nH (1.1 nH on a 0.21 mm prepreg), the order of the
  capacitor's own inductance (0.3 to 0.5 nH for a 0402 case); no re-route asked. Teaches: compute the loop
  through the plane before recommending a copper change.
