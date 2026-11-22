# Export fidelity: application cases

## Cases by mechanism
- **A faithful copy still differs, and every difference has a name.** A four-layer board of about a hundred
  parts, first comparison after the cleanup. Outline, paste and drill identical; mask identical apart from the
  non-plated holes that KiCad opens; copper: islands under 0.25 mm², about 1.5 mm² per layer for 2 200 to
  3 000 mm² of copper (of the order of 0.05 % of the copper area: shape of thermal spokes, small pour tongues);
  silkscreen: the KiCad font, slightly offset. Drill: 355 distinct holes on each side (18 vias of 0.305 mm,
  4 slots, 4 non-plated holes), no unmatched hole. BOM: 112 parts identical in value, footprint and part
  number; positions within 0.005 mm, rotations and sides identical; the source listed eight test points more,
  without part number, not fitted. Teaches: the deliverable is a short list of named differences, not zero;
  and the counts and orders of magnitude of a faithful copy are what show that the comparison itself works.
- **The diff finds the settings the import lost.** Same board. The comparison showed pours filled 0.09 mm from
  the tracks instead of the 0.254 mm of the source (the rule file had a track-to-track spacing rule that also
  applied between tracks and zones, so KiCad filled at the minimum track spacing, bringing the planes closer to
  the controlled-impedance pairs and changing their impedance), a mask expansion to set to 0.05 mm (0.051 mm per
  side in the source export), and a power plane to hold 0.5 mm from the edge by a rule attached to that single
  pour. Cure of the first: a dedicated clearance and hole-clearance rule for zones against other nets. Teaches:
  settings that the import neither carries nor reports, and that sit in rules rather than in geometry, show up
  as a systematic copper difference on the layer, and only the comparison of outputs reveals them.
- **A re-import is compared with the previous comparison.** Later revision of the same board. Same islands
  (≤ 0.25 mm², 1.1 to 1.7 mm² per layer), same mask difference, BOM identical apart from the parts marked not
  fitted in the source. One real change of the designer was visible in the diff only: the inner planes had gone
  from 0.254 to 0.15 mm of clearance between the two revisions, confirmed on the stored fills. Teaches: against
  the previous figures, a difference that is new is a change of the designer or an import defect; against zero,
  it would have been lost among the deliberate ones.
- **Stored fill against exported copper.** Two pours of the same board: stored gap 0.202 mm with a 0.100 mm
  pour stroke, and 0.252 mm with a 0.203 mm stroke; both measure 0.15 mm on the Gerber, i.e. stored gap − w/2.
  Teaches: the stored EasyEDA fill is an inner contour, the exported copper is that polygon thickened by half the
  stroke; a clearance read on the stored fill alone is overestimated by w/2, and the unit factor of the stored
  coordinates (ten times that of tracks) is confirmed by this match.
- **Smaller things that only this comparison shows.** On boards of that kind: thermal-relief gap of 0.254 mm in
  EasyEDA where the import set 0.5 mm; pads connected "Direct" in EasyEDA that came out as thermals, and solid
  fills lost by the import; non-plated holes imported from outline circles at 0.69 mm for a 0.70 mm drill; a part
  marked "Add into BOM = no" in the `.esch`, or a designator renamed after the `.epro` was exported, seen in the
  BOM comparison. Teaches: each is an import or export convention, visible in one comparison and in none of the
  KiCad-side checks (DRC, schematic parity).
