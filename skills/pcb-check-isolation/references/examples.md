# Isolation barrier: application cases, the other pitfalls

The table values quoted are the indicative ones held in `iec60664.py`.

## Application cases
- **The distance routed decides the withstand that can be claimed, step by step.** Setting: a four-layer board with
  an isolated bus transceiver (integrated isolated supply, 2.5 kVrms rated, a few mm of package creepage); the
  isolated-ground pour faces the logic pours on the outer layers. Computed: for each declared target, the
  required air distance in the table of its nature, against the routed minimum, then the reverse reading.

  | Targeted withstand | Required | 0.447 mm | 1.0 mm |
  |---|---:|---|---|
  | 1 kV peak, transient (F.2) | 0.2 mm (floor; the row gives 0.15) | pass | pass |
  | 1.41 kV peak, transient (F.2) | 0.5 mm | insufficient | pass |
  | 1 kVrms held 60 s (F.8) | 0.66 mm | insufficient | pass |
  | 1.5 kVrms held 60 s (F.8) | 1.40 mm | insufficient | insufficient |
  | 3.54 kV peak, transient (F.2; the peak of the IC's 2.5 kVrms) | 3.0 mm | insufficient | insufficient |

  Result: 0.447 mm covers a 1.2 kV peak transient; widened to 1.0 mm it covers a 2.0 kV peak transient and
  1.23 kVrms held. Reading the 1 kVrms target in F.2 at its peak would ask 0.5 mm: the table for a held voltage
  asks 0.66 mm, a third more; at 1.5 kVrms the two readings (1.5 and 1.40 mm) happen to agree. Creepage: 1.0 mm
  on the outer layers holds the general column up to 25 V of working voltage and not 40 V (1.10 mm); not judged
  while the working voltage between the two grounds is not declared. Teaches: the verdict depends on the nature of
  the test, so it is asked before computing; the reverse reading tells the designer what each widening buys, and the
  designer chooses the target.
- **A slot that holds on every layer can be short between two of them.** Setting: the same kind of board, an
  isolation slot of 1.0 mm drawn on each layer, but not at the same place on an inner layer. Computed: the isolated
  side of each layer against the logic side of every other layer. Result: the isolated inner plane came within
  0.287 mm, in projection, of the logic copper of the outer layer 0.099 mm above it, 0.304 mm through the prepreg.
  Screening rule not met (0.5 mm asked on every path): flagged; field 4.65 kV/mm at 1.414 kV peak in a solid insulator. The
  standard neither condemns nor proves this path: the withstand at 1 kVrms is shown only by a dielectric test on
  representative boards (IEC 60664-3 gives reduced distances, of the order of 0.3 mm at 1.2 to 1.5 kV peak in the
  values commonly quoted, for a *qualified* protection: the same figure, without the qualification and without
  margin). Correction: pull the inner plane back by 0.2 mm at least, 0.7 mm to align the slot. Teaches: a per-layer
  minimum is not a barrier distance; measure between layers and draw the two layers of the shortest path on top of
  each other.
- **An intended bridge becomes part of the barrier.** Setting: the footprint of a 1 nF, 2 kV stitching capacitor
  between the two grounds, not fitted. Computed: the bridging components of the isolated-side growth. Result: it
  is the only bridging component reported, and its pad gives the minimum on its layer. Teaches: a declared bridge is
  listed, its rating is checked against the targeted withstand, and its pads count in the barrier distance.

## The other pitfalls
- **Take the real gap of an imported pour.** A fill stored with an outline stroke has a real gap smaller than the
  stored one by half the stroke; confirm on the Gerber (`pcb-easyeda-import-cleanup`).
- **Two different AC tests.** The AC test that replaces an impulse test to verify a clearance lasts a few periods
  (three, in the procedure commonly described); the 60 s hold is the test of solid insulation.
