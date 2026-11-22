# Export fidelity: building the comparisons, step by step

Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

## Contents
1. KiCad exports in the EasyEDA frame
2. Fabrication folder for the assembler
3. Drill comparison
4. BOM and pick-and-place comparison
5. Pour clearance on the stored fills of the `.epro`
6. The rasterised diff
7. Self-checks and validation
8. Reporting

## 1. KiCad exports in the EasyEDA frame
```
kicad-cli pcb export gerbers -o <out>/kicad/ \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
  --use-drill-file-origin --check-zones <board>.kicad_pcb
kicad-cli pcb export drill -o <out>/kicad/ --format excellon --excellon-units mm --excellon-separate-th \
  --drill-origin plot <board>.kicad_pcb
```
`--check-zones` refills the zones for the export without modifying the board file; `--excellon-separate-th`
gives one file for plated and one for non-plated holes.

## 2. Fabrication folder for the assembler (Gerber zip, BOM, placement)
Built as in `../../pcb-easyeda-import-cleanup/references/cleanup-steps.md`, section 8 (origin check, archive of
the files of the run only, BOM, placement, consistency of the designator sets, rotations); its BOM and placement
files are the KiCad side of § 4.

## 3. Drill comparison
1. Read every Excellon file of each side with gerbonara (`Drill_*.DRL` for EasyEDA; `*.drl` for KiCad). Plated =
   the file name does not contain `NPTH`.
2. Build one key per hole, in mm (convert when reading a file that is not in mm), rounded to 1 µm: a flash gives
   `("round", plated, x, y, diameter)`; a routed line gives `("slot", plated, sorted(end points), diameter)`.
3. Count the keys but compare the **sets**: EasyEDA lists its vias twice (once among the plated holes, once in a
   via file).
4. A hole of one side is matched if the other side has a hole of the same type, plating and diameter whose
   coordinates all agree within the position tolerance of the criteria (`../SKILL.md`). A slot's end points are
   compared in both orders, the closer kept: the sort of step 2 swaps the ends of a nearly vertical slot when its
   two x differ by a micrometre.

## 4. BOM and pick-and-place comparison
1. EasyEDA BOM (`.xlsx`, first row = header): columns `Designator` (comma-separated list), `Comment`, `Footprint`,
   `Supplier Part`. KiCad BOM: that of § 2. Expand both to one entry per reference designator:
   (value, footprint, supplier part number).
2. Sort the designators: only in EasyEDA, apart from the parts not fitted (criteria of `../SKILL.md`; a
   designator without a supplier part number is the candidate, confirmed on the "Add into BOM" flag of the
   `.esch` or the DNP flag); only in KiCad; present on both sides with a triple that differs.
3. EasyEDA placement (`.xlsx`): `Designator`, `Mid X`, `Mid Y` (strings ending in `mm`), `Layer` (`T` / `B`),
   `Rotation`. Compare with the KiCad placement of § 2: position on each axis, side, and rotation difference
   wrapped to ±180°, against the tolerances of the criteria. Parts not fitted that EasyEDA still places (e.g. test
   points) are not counted, identified as in the BOM.

## 5. Pour clearance on the stored fills of the `.epro`
Used to confirm what the Gerber diff suggests, and to read a clearance that the EasyEDA rules (spacing matrix,
pour rule, per-pour and per-net selectors) do not state simply.
1. Open the `.epro` as a zip, take the `.epcb`, and parse each line that starts with `[` as a JSON array; the
   first element is the record type.
2. Records used (field positions as read in the `.epcb` files examined; the format is not published, so check
   them on yours): `POUR` — `[1]` identifier, `[3]` net, `[4]` layer, and a stroke `["SOLID", w]`; `POURED` —
   `[2]` identifier of its pour, `[4]` true for a computed fill, `[5]` list of rings; `LINE` — `[3]` net, `[4]`
   layer (1 top, 2 bottom, 15 and 16 the inner layers), `[5..8]` x1, y1, x2, y2, `[9]` width; `VIA` — `[3]` net,
   `[5]`, `[6]` position, `[8]` diameter.
3. Units: tracks and vias in units of 0.0254 mm; the rings of the stored fills in units ten times larger
   (multiply by 10 when read; make the factor a parameter and confirm it on a known dimension).
4. A ring is a path `[x0, y0, "L", x, y, …, "ARC", angle, x, y, …]`, the angle being the signed included angle;
   the rings of one fill are combined with the even-odd rule (`fill_geometry`). The fills of one pour are merged.
5. For each pour: for every track segment of the same layer and of another net, gap = distance from the merged
   fill to the segment's axis − half its width; for every via of another net, distance to its centre − half its
   diameter. Keep the gaps under a screening window (about 1 mm, adjustable) and convert to mm.
6. Read the result with the stroke: **real gap ≈ stored gap − w/2**, and confirm on the Gerber export.

**Code**: `../../pcb-verification/lib/easyeda_geom.py` (Python with shapely): `path_points(p, k, max_sagitta)` (a
path → points × k) and `fill_geometry(rings, k, max_sagitta)` (the rings of one fill, even-odd rule). Arcs are cut
into chords of sagitta at most `max_sagitta`, in output units (default 1e-3): a gap measured on the polygons is off
by up to that much, so keep it well under the resolution you read the gaps at. The centre offset is taken in the
signed form `h = (d/2) / tan(|θ|/2)` (chord d, included angle θ): it changes side beyond 180°, where the unsigned
form `√(r² − d²/4)` would put the centre on the wrong side and the swept arc would miss its end point; the
function's check on the end point covers both.

## 6. The rasterised diff
- The raster grows with the area: at 10 µm, a board of 25 cm² is about 25 Mpixel per layer (coarsen the
  resolution for a large board, at the cost of the narrowest differences).
- The comparison window is the bounding box of the EasyEDA outline plus 1 mm.
- Layer pairing by file-name pattern (`PAIRS` at the top of the script: EasyEDA `*TopLayer.GTL`, `*InnerLayer1*`,
  `*BoardOutline*`… against KiCad `*F_Cu*`, `*In1_Cu*`, `*Edge_Cuts*`…), written for 4 layers: for another
  layer count add one tuple `(name, EasyEDA pattern, KiCad pattern)` per extra inner layer, following the
  existing ones, after checking the file names of both exports and that the KiCad export lists the layer.
- Each layer is rendered to a boolean raster (dark and clear polarities in order), then `A and not B`,
  `B and not A`, and their morphological opening by a square of the tolerance's side, which takes the slivers of
  edge rounding and half-pixel shifts out of the "only" figures; the raw differences are kept beside them.
- Zero-width straight draws are ignored, and a zero-width arc is drawn one pixel wide, narrower than the opening;
  rotated rectangle apertures are rebuilt from their corners, because the library's own polygon conversion
  ignores the rotation and returns the bounding box.

## 7. Self-checks and validation
The self-checks: `../SKILL.md`, "Self-checks"; the figures of a faithful copy and of two pours
measured both ways: `examples.md`, "Cases by mechanism".

## 8. Reporting
- Table per layer: area on each side, EasyEDA-only and KiCad-only areas (mm²), number of islands, the largest
  island with its position and its cause.
- Drill: counts per type and diameter on each side, unmatched holes.
- BOM and placement: number of parts on each side, lines that differ, parts not fitted.
- The list of deliberate differences with their reason, and what was corrected in the cleanup because of the
  diff. All of it goes into the README of the cleanup folder; on a re-import, next to the previous figures.
- Wording of the conclusion: "faithful to the EasyEDA exports of revision X, with the differences listed".
