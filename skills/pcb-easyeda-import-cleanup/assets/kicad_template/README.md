# KiCad / JLCPCB template

Reference settings for a project imported from EasyEDA and fabricated at JLCPCB. Folder contents:
`JLCPCB_35um.kicad_dru` (JLCPCB rules, below), `template.kicad_pro` (Board Setup, severities, pre-defined sizes),
`apply_zone_settings.py` (zone settings) and this file.

Scope: the rule file is for 35 µm outer copper; `template.kicad_pro` and the
numbers below are starting values, to be replaced by what the board uses and by the fabricator's current
capability table. The skill's scripts handle inner layers for 4-layer boards.

## Why three items and not just one

A `.kicad_dru` is not enough: three families of settings live in three places, and only one can be carried over
as a file:

| Setting | Stored in | Transport |
|---|---|---|
| JLCPCB fab rules | `.kicad_dru` | copy the file |
| Board Setup, netclass, severities | `.kicad_pro` | Import Settings from Another Board |
| Zone clearance, thermal, min width | each `(zone)` of the `.kicad_pcb` | `apply_zone_settings.py` |

User preferences (shortcuts, snapping, grid) are not project data and do not travel with the project.

## Procedure after an EasyEDA import

1. Copy `JLCPCB_35um.kicad_dru` into the project, rename it `<project>.kicad_dru`; for a 4-layer board,
   comment the 2-layer trace and via blocks and uncomment the 4-layer ones (exactly one active rule of each name)
2. PCB Editor → File → Board Setup → **Import Settings from Another Board…** → point to `template.kicad_pro`
3. KiCad closed: `./apply_zone_settings.py <project>`
4. Reopen, **B** to refill, then Inspect → Design Rules Checker

## Values

Board Setup / netclass (starting values, to be adjusted to the board and to the fabricator's capability table):

    netclass Default clearance   0.12     (track <-> track)
    netclass via                 0.5 / 0.3
    min_track_width              0.127
    min_clearance                0.0      <- absolute floor, leave it at 0
    copper to edge               0.25
    hole clearance               0.2
    via diameter / drill         0.5 / 0.3
    via annular width            0.1

Pre-defined sizes (the ones that W / Shift+W cycle through):

    tracks                       0.15  0.2  0.25  0.3  0.4  0.5  0.75
    vias                         0.5 / 0.3

The first entry of each list is 0, i.e. "netclass value". These widths are examples: replace them with the board's
widths. While the list is empty, W and Shift+W have nothing to cycle through and seem broken.

Zones (via the script):

    clearance                    0.254
    min_thickness                0.127
    thermal_gap                  0.254   (EasyEDA default, measured on the Gerber; the import writes 0.5)
    thermal_bridge_width         0.3     (measure the spokes on the Gerber: they vary between designs)

The clearance, thermal gap and spoke width should be those EasyEDA applied to the board, measured as in
`references/cleanup-steps.md` (section 6): when they differ from these defaults, pass them to the script
(`--clearance`, `--thermal-gap`, `--thermal-bridge`).

## The rule file

`JLCPCB_35um.kicad_dru` holds JLCPCB's published minimums, with the date of the capability page in its header: the
2-layer values are active, the multilayer ones in comments next to them. A via below 0.3 mm hole or 0.45 mm diameter
is fabricable down to 0.15 / 0.25 mm but costs extra: the rule flags it so that the option is chosen when ordering.
A value of the board below a published minimum is a deviation for the designer to accept, recorded in the board's
`_cleanup/README.md`.

The last rule is not a fabrication limit: **copper pours at 0.254 mm** from other nets and from drills, the EasyEDA
default. Without it, the track rule also applies between a track and a copper pour, and KiCad fills at that distance:
the copper-to-pour clearance shrinks and the impedance of pairs and single tracks next to pours drops by several ohms
(recompute it with `pcb-check-impedance`). The rule must stay last (the last rule that applies wins). If EasyEDA used
another pour clearance on some layers (e.g. inner planes tighter than outer layers), split the rule by layer rather
than rely on the zone's local clearance, over which a custom rule takes precedence (`references/cleanup-steps.md`,
step 5).

## Net-class track width

A net-class track width (Net Classes → Track Width) is the router's default width, not a DRC rule (verified on
KiCad 10.0.4: a thinner track triggers no violation): set it to the smallest width the board uses. The check is
done by `min_track_width` and by the `.kicad_dru`, against the fabricator's minimum
for the layer count and copper weight (0.1 mm on 2 layers, 0.09 mm multilayer). A width imposed above what a
controlled-impedance pair needs on its stackup prevents the router from holding the target
(`pcb-check-impedance`); controlled-impedance nets get a class of their own (`references/cleanup-steps.md`,
step 4).

## Per-board exception

A connector at the board edge (e.g. a USB-C receptacle) carries its own cutout in its footprint, and its shield
pads can fall under the edge clearance. Then add a local rule, at the end of the `.kicad_dru`:

    (rule "Connector edge clearance exception"
        (constraint edge_clearance (min 0.15mm))
        (condition "A.memberOfFootprint('J_USB') || B.memberOfFootprint('J_USB')"))

Adapt the reference designator (`J_USB` here) and the value to the measured one, and comment the rule with the
reason. Do not lower the global `copper to edge` instead: that would relax the whole board instead of the one
component concerned. Insert the exceptions before the copper-pour rule, which must stay last.

## Behaviours verified on KiCad 10.0.4

**Rule priority.** From strongest to weakest for clearance: Board Setup `Minimum clearance` (absolute floor,
beats everything) > `.kicad_dru` custom rules (the last rule that matches wins) > zone clearance (`max()` with
the netclass) > netclass clearance. All the other Constraints fields (copper to edge, hole clearance, min track
width) can be overridden by the `.dru`, including downwards; `Minimum clearance` is the only one that cannot:
leave it at 0.

**An invalid `.kicad_dru` is rejected silently, in its entirety.** A misspelled constraint name is enough: no error
displayed, zero rules applied. Use the syntax check button
on the Custom Rules page, and after every edit check that a rule known to fire still fires.

**`kicad-cli pcb drc` reads the zone fill stored in the file** unless given `--refill-zones`: the report then
describes the copper last filled (for an import, EasyEDA's). Pass `--refill-zones` (with `--save-board` to keep
the refilled board, KiCad closed) or refill in KiCad (**B**) before concluding anything from a DRC report.

## Not covered

3D model offsets: `references/cleanup-steps.md` of the skill (section "3D models").
Everything else the import leaves wrong (keep-outs, pad connection, pin types, test points…):
`references/cleanup-steps.md` and `references/import-cleanup-guide.md`.
