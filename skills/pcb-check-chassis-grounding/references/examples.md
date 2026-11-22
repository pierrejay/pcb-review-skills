# Chassis ground: application cases, the other pitfalls

- **Case A, separate chassis net with a jumper.** A board of about 65 × 51 mm with shielded connectors at one
  corner and the supply connector at the opposite edge, 50 mm away; chassis nets = enclosure pad, Ethernet jack
  shell and cable shield, each shield tied to the enclosure pad by 1 nF 2 kV (plus 1 MΩ on the jack shell); a
  ground-to-chassis jumper. The inner ground planes pass about 0.1 mm from every through-hole pin of the shielded
  connectors. Parasitic capacitances of the chassis nets to ground, from the copper overlaps: 64 pF (cable-shield
  net), 25 pF (enclosure pad), 3.3 pF (jack shell).
- **Case B, no chassis net.** A board of about 28 × 50 mm with an Ethernet jack and a USB connector at one end and a
  shielded field-bus terminal block at the other; each shield and the jack shell tied to ground by 4.7 nF 2 kV (plus
  1 MΩ on the jack shell); the USB shell on ground; three plated fixing holes on ground. Plastic enclosure declared,
  floating and earthed metal enclosures computed as variants, with the board fixed by no screw, one or three.

## Cases by mechanism

- **A discharge on a shield puts the chassis–ground voltage across the antipad gap of the connector pins.**
  Case A, contact discharge, converged surface field of the most severe geometry (25.6 kV/mm per kV, see the
  convergence case below), laminate strength taken at 30 kV/mm:

  | Case | Peak chassis–ground | Edge field | Margin |
  |---|---:|---:|---:|
  | Plastic enclosure, jumper closed, 4 kV on the RJ45 shell | 550 V | 14 kV/mm | 2.1 |
  | same, shield capacitor degraded to 0.6 nF | 840 V | 22 kV/mm | 1.4 |
  | same, 8 kV | 1.1 kV | 28 kV/mm | 1.1 |
  | Plastic, jumper **open**, 4 kV, ground earthed (floating) | 2.8 (1.8) kV | 72 (46) kV/mm | 0.4 (0.7) |
  | Metal enclosure, jumper **open**, ground earthed, 4 kV | 1.8 kV | 46 kV/mm | 0.7 |
  | Metal, jumper open + 4.7 nF chassis–ground, 4 kV (8 kV) | 135 (270) V | 3.5 (6.9) kV/mm | 8.7 (4.3) |
  | Metal, jumper closed, 4 kV | 31 V | 0.8 kV/mm | 38 |

  Teaches: with a separate chassis net, the voltage between chassis and ground is set by the divider between the
  tie (capacitor or jumper) and the parasitic capacitances, so the margin moves by an order of magnitude with the
  state of the tie, with the capacitor's value under bias and with the level; it has to be computed for the
  positions the installation allows.
- **An open tie is the dangerous position; a capacitor across it removes it.** Case A, jumper open: the
  chassis–ground voltage reaches 1.8 to 2.8 kV. A 4.7 nF 2 kV capacitor fitted permanently in parallel with the
  jumper (closed = direct tie; open = HF tie only, chosen on site without soldering) leaves 135 V in a metal
  enclosure and 645 / 609 V in a plastic one (margins 1.8 and 1.9): no dangerous position left. The installation
  instructions written for that board: closed by default; open only if the metal enclosure is earthed, the supply
  0 V is earthed elsewhere, and the double tie is forbidden or a 50 Hz loop through the enclosure disturbs.
  Teaches: a position that the manual offers is computed like the default one; a component that keeps a HF path in
  the position that opens the DC path can remove the dangerous state at no cost in the others.
- **A wider clearance does not remove the coupling through the prepreg.** Case A, jumper open (1.8 kV): antipads of
  1 mm would leave the overlap through 0.1 mm of prepreg at about 18 kV/mm uniform and about 30 kV/mm at the edge,
  and a 0.26 mm gap on the surface would flash over first (≈ 1.2 kV in air, estimate).
  Teaches: a clearance table for air or a "typical FR-4" order of magnitude does not replace the calculation of the
  stress.
- **Insulating the board from a metal enclosure can be worse than tying it.** Case A, with plastic washers: 1.0–2.4
  kV between enclosure and ground at 4 kV (5–20 pF to the enclosure, strap of 0.3–1 µH); it would have needed
  ≥ 2 mm of air everywhere, nylon screws, and a connector shell that does not touch the panel.
  Teaches: a small capacitance between board and enclosure facing the enclosure's large capacitance to the
  surroundings makes a divider that puts most of the voltage across the small one; "floating" is a configuration
  to compute, not a safe default.
- **Without a chassis net, the tie capacitors and the screws do the work.** Case B: every touchable part is either
  ground or one capacitor away from it, so a discharge on a shield puts its voltage across that capacitor and the
  laminate around the connector pins, and nothing else. Over the discharge points, enclosures, fixings and cables
  computed, no component rating was exceeded and the laminate margin stayed above 2. Screwed through ground holes
  into a metal enclosure, the enclosure becomes a second ground path between the two ends of the board, in
  parallel with the plane: for a burst on one cable, part of the current then bypasses the plane under the ICs.
  Teaches: when every conductive part is ground or a capacitor away from it, the stress is bounded by the tie
  components and the strategy is robust to the installation; the enclosure screws change the path of common-mode
  current, not the discharge stress.
- **Each disturbance takes its own path; the plane only works for one of them.** Case A, metal enclosure, jumper
  closed:

  | Event | Current in the ground plane | ΔV across the plane | On the magnetics |
  |---|---:|---:|---:|
  | Surge on the Ethernet cable, 1 kV (2 kV) | 0.25 A (0.5 A) | < 1 V | 1.0 kV (2.0 kV) |
  | Fast transient 1 kV on the Ethernet cable | 3.5 A | 36 V (22–49 V for 5–15 nH) | 0.2 kV |
  | same + 4.7 nF ground → enclosure near the far connector | 2.4 A | 15 V (12–17 V) | 0.2 kV |
  | Fast transient 1 kV on the supply cable | 3.7 A | 7 V (3–11 V) | — |

  The surge is held by the isolation of the magnetics (2 kV is at its limit); only a capacitive 0.25 A reaches
  ground. Fast transients on the Ethernet cable are the one case where the plane works (36 V for ≈ 50 ns between
  its two edges, through the inter-winding capacitance); an HF tie near the far connector divides it by 2.4 and
  keeps the single DC point; it does nothing for transients entering by the supply cable (7 V with or without).
  A short, wide enclosure-to-earth strap is what pulls the current away from the plane.
  Teaches: a surge, a fast transient and a discharge cross different elements (isolation, winding capacitance,
  the plane); a tie chosen for one is checked against the others, and the plane inductance is run as a range.
- **Convergence of an edge field.** Case A geometry (a through-hole pad of Ø 1.6 mm, hole 1.0 mm, in the antipads
  of two inner planes with a gap of 0.094 mm, inner copper 15.2 µm thick, so a rounding radius of 7.6 µm, in 0.1 mm
  of prepreg of εr 4.1): maximum field in the prepreg for 1 kV, in kV/mm, read at a fixed distance from the copper
  while the mesh is halved.

  | Reading distance | `d_fine` 1 µm | 0.5 µm | 0.25 µm | 0.125 µm | Converged |
  |---|---:|---:|---:|---:|---:|
  | 3 µm | 17.19 | 18.09 | 18.41 | | ≈ 18.6 |
  | 1.5 µm | | 20.26 | 20.86 | 21.13 | ≈ 21.4 |
  | 0.75 µm | | | 22.82 | 22.92 | ≈ 23.0 |

  The differences shrink by 0.36 and 0.45 at each halving: converged. The fit of `A / (R + x)` on the three
  distances gives R = 8.9 µm (rounding radius 7.6 µm), a residual below 1 %, and a **surface field of 24.9 kV/mm per
  kV**. The finest meshes hold 0.27 / 0.52 / 1.24 / about 5 million nodes at 1 / 0.5 / 0.25 / 0.125 µm. The
  diagonal of the table (17.19, 20.26, 22.82: default `guard`, three meshes) is what a naive "mesh series" shows:
  it rises by 3.1 then 2.6 without settling, because it is three different reading distances:
  `edge_field.converged` returns it not converged, and `require_converged` raises on it. Same study on the other
  geometries: a pad of Ø 2.5 mm, hole 1.8 mm gives converged readings 19.06 / 21.90 / 23.51 and a surface field
  of **25.6 kV/mm per kV** (the worst of the three, R = 8.8 µm); the edge of a 35 µm zone over a plane through
  0.0994 mm of prepreg gives 10.1 kV/mm in the uniform part, converged readings 18.59 / 19.40 / 19.57 (the 3 µm
  series oscillates inside 0.5 %) and a surface field of **20.0 kV/mm per kV** (R = 41 µm).
  Teaches: a single reading near a rounded edge is a number that depends on where it is read; the quantity to
  quote is the surface field obtained from series converged at fixed distance and extrapolated, and the geometry
  with the largest one decides (here the larger pad, not the one used for the first study).

- **A surge on a capacitively tied shield is the case that sizes the laminate, not the ESD.** Setting: a cable
  shield tied to ground by 4.7 nF 2 kV, a shield zone on both outer faces over the ground planes (one prepreg of
  0.1 mm, about 50 pF), vias of the shield in 0.155 mm antipads; host earthed through USB. ESD 8 kV, worst
  corner: about 530 V shield–ground, margin 2.2 against the laminate. Surge ±1 kV on the shield: about 1.05 kV
  shield–ground, 20 kV/mm at the worst edge (fine calculation), margin 1.4; ±2 kV: about 2.1 kV, margin 0.7 and the
  tie capacitor at its rating. Host on battery: under 150 V even at 2 kV. The distributed capacitance changed the
  ESD peak by 0 to 30 % depending on the inductance to the tie capacitor, and nothing during the surge. Teaches:
  with a capacitive tie, run the surge on the shield itself; what holds ground to earth decides the voltage; the
  insulation between shield copper and planes sets the surge level the board withstands.

## The other pitfalls

- **Do not add an ESD part on pins that lead nowhere.** USB-C configuration pins that only go to their pull-down
  resistors have no IC to protect; the test is applied to the shell.
- **Take the real pour gap, not the stored one.** The distance used for a stress is that of the plotted copper;
  for a fill imported from another tool the stored gap can differ from the plotted one (see
  `pcb-easyeda-import-cleanup`); confirm on the fabrication files.
