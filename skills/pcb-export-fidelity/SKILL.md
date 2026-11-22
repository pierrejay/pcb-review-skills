---
name: pcb-export-fidelity
description: "Fidelity check between the fabrication outputs of a cleaned KiCad project and the EasyEDA Pro exports of the same revision: rasterised Gerber diff, drills, JLCPCB BOM and pick-and-place. Run before ordering from the KiCad outputs."
---

# Fidelity to the EasyEDA exports (what EasyEDA fabricated = what KiCad fabricates)

Step between `pcb-easyeda-import-cleanup` and `pcb-verification`. Read `../pcb-verification/SKILL.md`, "Rigor, in ten
rules", first: they apply to every comparison.

## Resources
- `scripts/gerber_diff.py`: rasterised Gerber diff;
- `../pcb-verification/lib/easyeda_geom.py`: EasyEDA Pro paths and stored fills.

## Purpose
After an import and its cleanup, does the KiCad project fabricate the same board as the EasyEDA Pro project it
came from: same copper, mask, paste and holes, same BOM, same placement? The check compares the fabrication
outputs of the two tools for the same revision.

## When it applies
After the cleanup of an import, after the re-import of a later revision, and before anything is ordered from the
KiCad outputs.

## Inputs to obtain
- From the designer, **of the same revision** as the imported `.epro`: the Gerber export (zip, drill files
  included), the BOM and the pick-and-place files (`.xlsx`). Archived with the board (e.g.
  `<board>/_pre_import_backup/easyeda_<date>/`).
- The `.epro` itself (a zip: `.epcb`, `.esch`, `project.json`), for the stored pour fills and the "Add into BOM"
  flags.
- The cleaned KiCad project, with the drill / place origin at the bottom-left corner of the outline: the frame
  of the EasyEDA exports.
- On a re-import: the previous pair of exports and the differences recorded for it.

## Method
How each comparison is built: `references/method.md`, in the section given in the last column.

| Step | What is compared | How |
|---|---|---|
| 1. KiCad outputs in the EasyEDA frame | — | `kicad-cli` exports with the drill origin, zones refilled on the fly (§ 1) |
| 2. Gerber | each layer, EasyEDA against KiCad | rasterised diff, islands listed by area and position (§ 6) |
| 3. Drill | holes by type (plated / non-plated, round / slot), diameter, position | sets of holes, each matched on the other side (§ 3) |
| 4. BOM | per reference designator: value, footprint, supplier part number; parts not fitted | both lists expanded to one entry per designator (§ 4) |
| 5. Pick-and-place | per reference designator: position, side, rotation | both lists expanded to one entry per designator (§ 4) |
| 6. Pour clearance (when the diff shows a systematic copper difference) | gap between each pour and the tracks and vias of other nets | measured on the fills stored in the `.epro` (§ 5) |

Each remaining island of the Gerber diff is attributed to a cause; a cause that is an import or cleanup defect is
corrected in the cleanup (zone settings, design rules, mask expansion, hole sizes). Some differences are visible only
here, because the import carries no trace of them: a pour setting changed in EasyEDA between two revisions; a rule of
the KiCad rule file that also applies to zones and changes their fill clearance; the real gap of a stored fill;
thermal-relief gaps and spokes; a plane held back from the edge by a per-pour rule; non-plated holes rebuilt slightly
smaller than the drill; the mask expansion applied by the export; a part marked "Add into BOM = no".

## Criteria
- Every remaining difference is **explained** (deliberate, listed with its cause) or corrected.
- Examples of deliberate differences (each is listed and justified on the board at hand): paste reduced on
  thermal pads by a rule of the cleanup (e.g. to 64 % of the pad), non-plated holes opened in the mask by KiCad,
  silkscreen font and redrawn glyphs, tented vias, exact shape of thermal spokes and small pour tongues.
- Drill: no unmatched hole on either side. A hole matches a hole of the other side of the same type, plating and
  diameter (exact at 1 µm) whose position agrees within 0.02 mm.
- BOM and pick-and-place: no line that differs (value, footprint and supplier part number identical; position
  within 0.01 mm on each axis, same side, rotation within 0.01° modulo 360°), apart from the parts that the
  source marks as not fitted ("Add into BOM = no" in the `.esch`, not in the imported schematic, or a DNP flag;
  e.g. test points). A missing supplier part number is only a hint to check that flag, not the test.
- On a **re-import** of a revision: **the same Gerber differences as at the previous import, to the mm² per
  layer**, plus what the designer changed, and nothing else. If the previous figures were not kept, recompute
  them on the old pair before judging the new one.

## Self-checks
- Print the counts on both sides before the differences (holes per diameter, parts in each BOM, parts placed): a
  comparison of two empty sets also returns no difference.
- Both sets in the same frame before anything else: with the origin elsewhere than the bottom-left corner every
  layer differs entirely.
- Zones refilled before comparing (`--check-zones`): a stale or absent fill produces large copper differences
  that are not in the design.
- Every layer file of both exports is paired in `PAIRS` (written for 4 layers; `references/method.md` § 6): a
  layer absent from the list is not compared, and nothing says so.
- Drill: sets of holes compared, not entries (`references/method.md` § 3); diameters taken from the EasyEDA
  drill file.
- What a faithful copy looks like, to recognise a broken comparison: the same number of distinct holes on both
  sides for each type, plating and diameter, and no unmatched hole; the same number of parts in both BOMs, with
  identical value, footprint and part number; positions equal to the rounding of the files (of the order of a few
  µm, well inside the 0.01 mm tolerance), rotations and sides identical; for a pour, a stored gap minus half the
  stroke that matches the gap measured on the Gerber. A result far from this (half the holes, a systematic offset,
  a gap that is off by the unit factor) points to the comparison, not to the board.

## Tool contract
Interpreters: `kicad-cli` for the exports; a Python environment with gerbonara, numpy, pillow, scipy for the diff,
openpyxl for the spreadsheets, shapely for the pour measurement. Everything except the rasterised diff is short and
rebuilt per workspace.
- **Shell wrapper**: unzips the EasyEDA archive into `<out>/easyeda/`, runs the two `kicad-cli` exports of
  `references/method.md` § 1 into `<out>/kicad/` with their log kept, then the diff into `<out>/diff/`;
  `set -e -o pipefail`, so that a failed export cannot be followed by a diff of stale files.
- `scripts/gerber_diff.py <dir_EasyEDA> <dir_KiCad> <out_dir> [--res 0.01] [--tol 0.05]`: per layer one printed
  line (areas, EasyEDA-only and KiCad-only areas after opening, islands, raw differences, mm²), `<layer>.png`,
  `<layer>.npz`, `<layer>_islands.tsv` (colours and columns in its docstring). Exit status non-zero, at the end,
  if a layer is missing on either side.
- **Drill comparison**: prints, for each side, the number of distinct holes and of entries and the count per
  (type, plating, diameter), then the unmatched holes of each side; exit status 1 on an unmatched hole.
- **BOM and placement comparison**: prints the number of differences to explain, the designators only on one
  side, those whose line differs, and the largest position difference; non-zero exit status if any remains.
- **Pour clearance on the stored fills**: `path_points` and `fill_geometry` of `easyeda_geom.py` (arcs within
  `max_sagitta` of their chords); prints per pour the minimum gap and the three most frequent values.
- **Refusals**, besides a failed export and a missing layer: an empty drill file or an unreadable spreadsheet
  header stops the comparison. None of them may end as "0 difference".
- **Fabrication folder for the assembler** (Gerber zip, BOM, placement, origin check, consistency of the
  designator sets): `../pcb-easyeda-import-cleanup/references/cleanup-steps.md`, section 8.

## Pitfalls
- **Compare exports of the same revision as the `.epro`.** A designator renamed or a part edited after the
  `.epro` was saved shows up as a false difference; check the dates and align on the most recent export.
- **Do not estimate a pour gap from the stored fill alone.** The export thickens the stored polygon by half the
  stroke width, so the gap on the Gerber is smaller than the stored one by that amount (`references/method.md`
  § 5).
- **Look at the image of each island before naming its cause.** The table gives area and position; only the
  picture tells a thermal spoke from a missing fill; an import defect shows by comparing import against import.

## Limits
Raster comparison at 10 µm with a 50 µm opening (the defaults): a difference narrower than the opening shows only
in the raw figures, not among the islands.
