# EasyEDA Pro import in KiCad 10: pitfalls and background

What the import translates badly, why, and what to do. "Step 3a" refers to `cleanup-steps.md`, where each step is
scripted and proven.

## 1. Numbered pitfalls

Each entry: symptom — cause — fix; a fix reduced to "step N" is entirely in that step. The numbers are stable: step
scripts, READMEs and reports cite them. By theme:

- schematic: 9–13, 15, 18–20, 22, 31, 32, 36, 39;
- zones, copper, holes: 1–4, 14, 16, 23–29, 35, 41, 42;
- footprints, paste, silkscreen, 3D: 5, 8, 17, 21, 30, 34, 37, 44;
- rules, classes, update from schematic, re-import: 6, 7, 33, 38, 40, 43, 45.

**1. Masses of `items_not_allowed`.** The rule areas come out forbidding tracks, vias, pads and pours, whereas
EasyEDA only excluded the pour. Fix (step 3a): pour only, `(tracks allowed) (vias allowed) (pads allowed)
(copperpour not_allowed) (footprints allowed)`.

**2. Keep-outs with no effect.** They land on Edge.Cuts, which the import renames "Multi-Layer". The dialog shows
a "multi layer" checkbox, but it is a non-copper layer that the zone filler never consults. Fix (step 3a, which
measures the layers): move them to the copper layers on which they acted, `(layers "Edge.Cuts")` →
`(layers "F.Cu" "In1.Cu" "In2.Cu" "B.Cu")`.

**3. Pours choked around SMD parts; pads that look badly connected.** `(connect_pads (clearance …))` without
keyword means thermal reliefs on **all** pads, whereas EasyEDA relieves through-hole pads only and floods SMD
pads ("Direct"). Fix: step 3a; refill before judging any current path.

**4. Raw clearance and thermal values.** The zones carry the values the import writes (clearance, thermal gap),
not those EasyEDA applied when it computed the pours (see 35). Fix: step 3a, then step 5.

**5. Footprint library not found.** Neither `fp-lib-table` nor `.pretty`: the footprints live only in the
`.kicad_pcb`. Fix: step 1, with the library tables of step 0.

**6. "Cannot add X" at the first Update PCB from Schematic.** No footprint has a `(path …)` to its symbol. Fix:
re-link by reference designator (`cleanup-steps.md`, "Schematic ↔ PCB re-link").

**7. Duplicated nets `/X` and `X` after the update, in contact (`shorting_items`).** A footprint without symbol
(a pad placed by hand: test point, jumper) keeps the old net name while the update renames the schematic's net.
Fix: step 2g. Moving the items of the old net to the new one works once and comes back at the next rename.

**8. 3D models not found or misplaced.** Model paths of the form `<hash>{bar}<hash>.step`, Z offsets missing.
Fix: `cleanup-steps.md`, section 7. A model can also be the wrong part under the right name, or sit entirely
under the board (see 37).

**9. Unreadable ERC.** No pin electrical type is imported: everything is `unspecified` or `input`. Fix: step 2b.

**10. `Footprint '' not found in library`.** A Footprint field equal to `"<LIB>:"`, a nickname followed by
nothing. Fix: empty the field after checking pitfall 22 (step 2a).

**11. `#PWR?` not annotated.** The import does not number the power symbols. Fix: step 2a, or Tools → Annotate
Schematic.

**12. An object that cannot be annotated.** The EasyEDA title block (`Sheet-Symbol_A4`, no pin) arrives as a
component whose reference is `1`, its page number. KiCad splits a reference into letters and a number: `1` has no
prefix, the annotation answers `Updated  from 1 to 1?` then `Error: Item not annotated: 1?`. Fix: delete it
(step 2a; KiCad has its own title block in File → Page Settings); failing that, rename it `#FRAME1`, the `#`
marking a virtual symbol.

**13. Wires with one end dangling.** The label is anchored in the middle of the wire, not at its end (section 2).
Fix: step 2f.

**14. Floating pads.** Pads with a duplicated number (shield tabs of a USB-C connector): only one of them
receives the net. Fix: step 3a.

**15. Every reference shown as `?` after renaming the files.** The `(instances (project "<old name>" …))` blocks
of the schematic carry the project name. Fix: step 0.

**16. Unexpected holes or cut-outs, pours pulling back around them.** Footprint graphics on EasyEDA's Multi-Layer
layer land on Edge.Cuts: the circles are non-plated holes (locating pegs of a USB-C connector, screw passage of
an SMD nut). Fix: step 3b. A small circle on the outline (e.g. 0.7 mm) may be poorly milled.

**17. `?` or an empty box printed on the silkscreen.** A glyph missing from the text's font (earth symbol, small
triangle); EasyEDA had used a fallback font. Fix: step 4e.

**18. A pin on a net of its own (a backup-supply pin separated from its rail, for example).** An EasyEDA "Short"
symbol (net tie) has no KiCad equivalent. Fix: step 2a.

**19. "Dangling" wires of 4 to 20 mm.** A wire that leaves a pin already carrying its label and runs into empty
space. Fix: step 2f.

**20. `lib_symbol_mismatch` after fixing the pin types.** The embedded library and the `.kicad_sym` diverge (font,
Footprint field, types). Fix: step 2d.

**21. The update duplicates the footprints created by script and places the duplicates at the origin.**
`pcbnew.FootprintLoad(lib, name)` returns a footprint whose FPID has no library nickname (`name` instead of
`LIB:name`): the update does not attach it to its symbol. Fix: `f.SetFPID(pcbnew.LIB_ID("LIB", "name"))` before
saving; after the fact, `cleanup-steps.md`, re-link.

**22. A component without footprint after emptying the `"<LIB>:"` fields.** The field reduced to the nickname can
also hide a **real** component whose footprint name the import lost (e.g. a regulator). Fix: step 2a.

**23. Pours at 0.08 mm from the tracks.** The JLC rule "Minimum Trace Width and Spacing" (`clearance 0.09mm`,
`A.Type == 'track'`) also applies between a track and a **zone** and takes precedence over the zone's own
clearance. Effect: pairs and single tracks next to pours lose several ohms of impedance as the copper-to-pour
clearance shrinks (recompute with `pcb-check-impedance`). Fix: a rule at the end of the `.kicad_dru`, `clearance`
and `hole_clearance` 0.254 mm for `A.Type == 'Zone' && A.Net != B.Net` (in the template of
`assets/kicad_template/`).

**24. Copper islands filled at only a fraction of their area** (e.g. 20 to 65 %: ground under a QFN, supply
islands on inner layers). An EasyEDA solid fill ("Fill") arrives as a zone: a zone is cut by the rule areas, by the
neighbouring zones and by its own clearances, a solid fill never is; the import also loses the rounded corners and
replaces a polygon by its bounding rectangle. Fix: step 3d.

**25. Mask tighter than EasyEDA on every pad.** The EasyEDA mask expansion (0.05 mm per side) is not imported;
KiCad is at 0. Fix: step 4.

**26. A pour held further from the board edge than the global rule (e.g. a power plane).** An EasyEDA pour rule
specific to one pour is not imported. Fix: a targeted rule, `edge_clearance` with
`A.Type == 'Zone' && A.NetName == '<net>' && A.Layer == '<layer>'`.

**27. NPTH holes about 0.01 mm smaller than the EasyEDA drill.** The imported Edge.Cuts circle (16) is
slightly smaller than the EasyEDA drill. Fix: step 3b.

**28. Pour clearance different from one pour to the next; EasyEDA rules unreadable.** EasyEDA's pour rules (a
spacing matrix, a "copperRegion" rule, selectors per pour or net) do not translate. Fix: measure on the stored
fills, confirm on the Gerber export (`cleanup-steps.md`, section 6).

**29. Thermal spokes narrower than in EasyEDA; SMD pads flooded where EasyEDA relieves them.** The spoke width
and the per-pour connection mode (a rule putting thermal reliefs on every pad of a shield net) are lost. Fix
(step 5): measure the spokes on the Gerber (the width varies between designs); `SetThermalReliefSpokeWidth`, and
`ZONE_CONNECTION_THERMAL` on the pours concerned.

**30. A paste rule for "U*" that also shrinks inductors.** `memberOfFootprint('U*')` filters on the reference
designator, and some designs designate their inductors `U…`. Fix: list the pads the rule hits; if every
thermal pad already has its dedicated opening (step 3c), do not add the rule.

**31. A reference designator that differs between the `.epro` and the fabrication exports.** A renaming done in
EasyEDA after the `.epro` was exported. Fix: compare the BOM and placement exports with the imported schematic
before concluding; align on the most recent export.

**32. A small node cut in two; after the update, a short circuit and unconnected items on it.** Lost cross node:
in EasyEDA, four branches of one wire meeting at a vertex are connected without a junction dot. The import places
the junction on T nodes (three branches) but not on crosses: it merges the aligned segments into two crossing
wires, which KiCad does not connect. The PCB is right, the schematic is cut (e.g. the load capacitor of an
oscillator, isolated from the oscillator input). Fix: step J (`scripts/easyeda_junctions.py`).

**33. Parity: hundreds of "Missing symbol field" and differing BOM attributes.** The update was run without
"Update footprint fields from symbols". Fix: run it again with that box checked, without re-link.

**34. Narrow, "distorted" silkscreen texts.** The EasyEDA font size (one value) becomes height = 0.7 × size and
width = 0.6 × size; with a TrueType font KiCad also squeezes the glyphs to about 0.86 of their width, so the printed
width ends well below EasyEDA's. Fix: step 4d.

**35. "Spread-out" thermal reliefs: an empty 0.5 mm ring around through-hole pads, a spoke missing near a pour
edge.** The import writes a thermal gap of 0.5 mm; EasyEDA's default pour rule leaves 0.254 mm (confirm on the
Gerber, spokes included). Fix: `SetThermalReliefGap` at 0.254 mm on every pour (step 5).

**36. Wires sticking out on both sides of each replaced Short; replacement wires not connected.** Labels sit in
the middle of the wires (13), and the imported schematic is on a 0.001 mm grid: a wire written to 0.01 mm does
not touch the pins. Fix: exact coordinates (`:.4f`, KiCad's 0.1 µm; never `:.2f` nor `:g`, six significant
digits; step 2a), then step 2f.

**37. A through-hole connector sunk into the board or hanging under it (vertical USB-C, RJ45).** The z offset
derived from the "3D Model Transform" is wrong for some STEP files, whose axes differ from the model EasyEDA
displays. Fix: `cleanup-steps.md`, section 7.

**38. A pair leg routed away from its partner at the pair width; a net class with a single width.** A leg that
runs alone at the width meant for the coupled pair has a different (usually higher) impedance than the target.
The import does not carry the intended widths, and one width per class conflates the coupled pair and the lone
track. Fix: step 4; legs running alone over a length that matters for the target impedance are widened (check
with `pcb-check-impedance`).

**39. A replacement wire that does not touch, and nothing reports it.** After a Short is replaced and the labels
of both sides are given the same name, the two sides are joined by name: the netlist is the intended one and
`check_nets` is satisfied whether the wire touches or not. Fix: exact coordinates everywhere, and prove the wire
with the ERC (no dangling wire end at the two former pins of the Short), not with the netlist (step 2a).

**40. Free pads not found at a re-import.** The `Pad_eNNN` identifiers of hand-placed pads can differ from one
export to the next. Fix: step 2g.

**41. A pour setting changed in EasyEDA between two revisions, and nothing shows it.** A pour rule (e.g. the
clearance of the inner planes) changed between revisions leaves no trace in the import: only the Gerber comparison
shows it, and the measurement on the stored fills confirms it. Fix: step 5; never skip the Gerber comparison at a
re-import.

**42. Dangling track ends that come back after being removed.** EasyEDA leaves stubs of a few hundredths of a
millimetre in chains: removing the one the DRC reports exposes the next. Fix: step 4b.

**43. After an update run in the graphical editor, pads moved to a new net `Net-(<ref>-Pad<n>)`, their tracks
left on the old net, DRC errors.** The schematic on disk is right (the netlist exported by `kicad-cli` shows the
node whole): it is the cross node of pitfall 32, seen differently by the editor. Fix: put the pads back on their
net in the PCB (text edit, KiCad closed) and restore the junction; do not repair with another update (checks
after any update: `cleanup-steps.md`, re-link).

**44. Through-hole test points flipped to the back with wrong layers.** The test "has a pad on B.Cu" is true for
any through-hole pad. Fix: "on the back" means SMD without `F.Cu` (step 2g).

**45. An update that undoes a script's work.** It was run from a schematic or a board left open from before the
script. Fix: KiCad closed while scripts write, and reloaded before any update from schematic.

## 2. Background

### Label anchors (pitfalls 13, 19, 36)

The connection point of a label is its anchor (the small cross), not its text. With `left` justification and no
rotation the anchor is at the left edge of the text, which extends to the right. A label placed to the **left**
of a component therefore falls at the end of its wire; a label placed to the **right** has its anchor in the
middle of the wire, which continues into empty space (`unconnected_wire_endpoint`). Two repairs: rotate the label
by 180°, so that the anchor moves to the end of the wire and the wire runs under the text (clean, manual); or
shorten the wire to the anchor by script (step 2f: the net does not change, the text stays beside the wire).

### Settings that are not design rules

Where each setting lives (`.kicad_dru`, `.kicad_pro`, each zone of the `.kicad_pcb`) and how it travels, the
clearance priority, the net-class width that is not a DRC rule, the silent rejection of an invalid `.kicad_dru`:
`assets/kicad_template/README.md`.

### What remains and is normal

- `silk_overlap`, `courtyards_overlap`, `pth_inside_courtyard`, `track_not_centered_on_via`: EasyEDA's silkscreen
  and courtyard data are approximate. The template sets them to `ignore`; they are not fabrication defects.
- `text_thickness`, `text_height` on TrueType silkscreen: compare the printed height and stroke with the
  fabricator's minimum text size (its capability table), not with KiCad's threshold, and decide with the designer.
- `hole_to_hole` warnings: the template asks JLCPCB's 0.2 mm between vias and 0.45 mm between pad holes; compare with
  the fabricator's current table before treating one as a defect.
- `endpoint_off_grid` in the ERC: the EasyEDA grid.
- `via_dangling` on vias tied to an inner plane only.

### Differences with the EasyEDA Gerbers that may remain after a complete cleanup

The comparison is the `pcb-export-fidelity` skill; the categories of difference that can remain and be explained,
as a yardstick (the magnitudes depend on the board):

- outline, drills, bottom paste, mask: identical (KiCad also opens the mask on the NPTH holes, without effect);
- top paste: only the thermal pads deliberately reduced;
- copper: EasyEDA may keep its pours farther from some tracks, and between pours, than the clearance chosen in
  KiCad; compute the effect on the impedance of the pairs and tracks concerned (`pcb-check-impedance`); an arc of
  a pour slightly different (EasyEDA's fill can differ from its own outline); thermal spokes of slightly
  different shape;
- silkscreen: KiCad font slightly offset vertically, margin around inverted texts, redrawn glyphs.
