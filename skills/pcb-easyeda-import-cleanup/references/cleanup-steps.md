# Cleanup steps for an EasyEDA Pro import in KiCad 10 (operational reference)

The numbered pitfalls ("pitfall 23") are those of `import-cleanup-guide.md`: the symptom and cause of each are
stated there, the script and its proof here.

Contents: 1. ground rules for the step scripts — 2. inventory — 3. steps at a glance — 4. steps in detail —
5. re-import of a later revision, and carrying a change over from fabrication exports — 6. measured EasyEDA
conventions — 7. 3D models — 8. fabrication outputs for JLCPCB.

## 1. Ground rules for the step scripts

**Board folder.**

```
<board>/
  <board>.kicad_pro  <board>.kicad_pcb  <board>.kicad_sch  <board>.kicad_dru
  <LIB>.kicad_sym  <LIB>.pretty/  sym-lib-table  fp-lib-table
  EASYEDA_MODELS/        3D model files actually used by the board
  _pre_import_backup/    raw import (never edited), the .epro, snapshots before_<step>.*,
                         easyeda_<revision>/ (Gerber, BOM, pick-and-place exported from EasyEDA)
  _cleanup/              one script per step, the four kept scripts (copied, or imported from the skill),
                         reference_nets.json, ERC / DRC reports, README.md (SKILL.md, "Closing")
  fab/                   fabrication outputs
```

**One script per step**, named after the step (`step2a_schema.py`…), board data in a table at the top (file
names, library nickname, reference designators, nets, diameters), logic below. A step script starts from the files
left by the previous step and prints what it changed (counts, names): that output goes into the README.

**Two ways of editing, never mixed in one operation.**

| Way | Use it for | Interpreter |
|---|---|---|
| Text of the S-expression file, located with `scripts/sexp.py` | everything in the `.kicad_sch` and `.kicad_sym`; in the `.kicad_pcb`: `(model …)` blocks, layer names, stackup, `(setup …)` values, text sizes, net of a pad | any Python 3 |
| `pcbnew` API (`LoadBoard` … `Save`) | geometry and objects of the `.kicad_pcb` and of `.pretty` libraries: zones, pads, footprints, shapes, tracks | KiCad's bundled Python |
| `kicad-cli` | netlist export, ERC, DRC with zone refill and parity, Gerber / drill / BOM / position export, 3D render | — |

Edits are replacements inside the located block; the file is never re-serialised, so the diff stays readable. To
write a new object, copy the text KiCad itself writes for an object of that kind (from the file or a scratch
project) and substitute coordinates, names and a fresh `uuid.uuid4()`. Insert new wires before the first
`\n\t(wire\n`, new symbols / labels / markers before `\n\t(sheet_instances` (or the final `\n)`); iterate
`reversed(top_blocks(…))` when removing, so that earlier offsets stay valid.

On macOS the bundled Python is
`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` and `kicad-cli`
is in `…/KiCad.app/Contents/MacOS/`; KiCad's stock libraries are under `…/Contents/SharedSupport/` (`symbols/`,
`3dmodels/`). On other systems, use the Python that ships with the KiCad install (the one that can
`import pcbnew`) and its `kicad-cli`.

**Backups.** The raw import stays untouched in `_pre_import_backup/`; every step that touches copper takes a
snapshot `before_<step>.kicad_pcb` (`if not backup.exists(): copy`, so that a re-run does not overwrite it with an
already modified file). KiCad also keeps its own zips in `<board>-backups/`, useful to rebuild a timeline when
something went wrong.

**Idempotence.** Two levels are needed. (1) The whole chain is replayable: step 0 regenerates the working files
from `_pre_import_backup/`, and every later step depends only on the previous ones; this makes a re-import cheap.
(2) Each step can run twice without damage: it sets values rather than toggling them, tests for what it is about
to add (rule name already in the `.kicad_dru`, symbol definition already in the library, junction already at that
point, reference designator already present, stackup already written) and fails loudly on an unexpected state
(`assert`, `SystemExit`) rather than guessing. Hard-coded reference designators, positions and free-pad
identifiers break first at a re-import: identify objects by net, footprint name or role, and assert the
identification. A step's **Idempotent** bullet (section 4) says how it meets (2); unless it says otherwise, a
second run changes nothing (its printout reports no change).

**Check after every step**: `check_nets.py` must print `IDENTICAL` for the schematic and for the PCB. A step's
**Proof** bullet (section 4) gives what proves it beyond that and the ERC / DRC counts below.

```sh
<kicad-python> scripts/check_nets.py <board> --save     # once, on the renamed import (after steps 0 and J)
<kicad-python> scripts/check_nets.py <board>            # after every step; exit code 1 if anything moved
```

Exit code 1 also when an extraction fails (export error, unreadable or empty netlist, PCB without a net of two
pads): read the message before looking for what moved.

Intended differences are declared, never tolerated silently: `sch_merge` (schematic pins allowed to change group,
e.g. the pin a "Short" tied to a rail) and `new_refs` (reference designators created by the cleanup: test points,
an optional part), in `_cleanup/check_nets_expected.json` (format: docstring of `check_nets.py`). What it does not
see: a net joined by a label name instead of a wire (pitfall 39); free pads without a reference designator and
`#…` references, ignored on both sides until step 2g gives the pads a reference; anything that is not
connectivity (flags, footprints, copper shape): each step proves those its own way.

**ERC and DRC counts** are the second proof, kept in `_cleanup/` with the step name:

```sh
kicad-cli sch erc --format json --severity-error --severity-warning -o _cleanup/erc_<step>.json <board>.kicad_sch
kicad-cli pcb drc --refill-zones --save-board --schematic-parity --format json --severity-error \
          --severity-warning --units mm -o _cleanup/drc_<step>.json <board>.kicad_pcb
```

Count the violations by `type` (ERC: `sheets[].violations[]`; DRC: `violations[]`, plus the unconnected items and
the parity items) and compare with the previous step: a step must only remove the types it targets.

**Traps of the tools** (each gives a wrong result without an error):

- `kicad-cli pcb drc` reads the stored zone fill (EasyEDA's, on an import) unless given `--refill-zones`;
  `--save-board` writes the refilled board (KiCad closed). In a script: `pcbnew.ZONE_FILLER(b).Fill(b.Zones())`
  then `b.Save(…)`.
- The ERC JSON gives positions in **units of 100 mm** (`x: 3.2893` = 328.93 mm); multiply by 100 and round to
  4 decimals to land exactly on the flagged pin.
- A naive parenthesis count breaks on strings that contain parentheses (part descriptions): always `sexp.py`.
- `for m in f.Models(): m.m_Filename = …` edits a copy: 3D model blocks are edited as text.
- Collect `list(b.GetDrawings())`, `list(b.GetTracks())`, `list(f.GraphicalItems())` before any `Remove`:
  iterating the live container while removing fails, and `GetDrawings()` fails after a track has been removed.
- A Python list of zones compares its elements by value (layer ignored): after `b.Remove(z)`, filter the list
  with `x is not z`, not with `list.remove(z)`.
- An invalid `.kicad_dru` is rejected silently and entirely (`assets/kicad_template/README.md`): after every
  scripted edit of the rule file, check that a rule known to fire still fires.
- Output of a long step is buffered when redirected: run it with `python3 -u`, in the background.

## 2. Inventory (before any modification)

Read from the raw import and from the unzipped `.epro` (`.epcb`, `.esch`, `project.json`):

- copper layers, outline, number of footprints; footprints without a reference designator and without a library
  (`Pad_eNNN` = pads placed by hand in EasyEDA: test points, mounting holes, jumpers);
- `Short-Symbol*` symbols (EasyEDA net ties), the `Sheet-Symbol_A4` title block, symbols placed on the PCB whose
  Footprint field is reduced to `<LIB>:`;
- zones: copper pours (net, layer, priority), rule areas (which layers: "Multi-Layer" hides Edge.Cuts), and the
  `FILL` solid fills of the `.epcb` (layer, net);
- EasyEDA rules of the `.epcb` (`RULE`, `RULE_SELECTOR`): default pour rule, per-net or per-pour selectors (a
  shield net with thermal reliefs everywhere, a power plane with its own edge clearance);
- footprint graphics on Edge.Cuts (circles = holes), non-ASCII silkscreen texts;
- flags of the `.esch` that the import drops: "Add into BOM", "Convert to PCB";
- 3D models: missing files, `3D Model Transform` of `project.json`;
- schematic ↔ PCB connectivity of the import, compared group by group: the Shorts explain the groups that the
  PCB merges; a small node that the schematic splits in two is the signature of a lost cross junction (step J).

## 3. Steps at a glance

In this order, each subsection of section 4 giving what the import leaves, what to do, what makes the step
re-runnable and what proves it (section 1): 0, J, then the `check_nets.py --save` reference (renamed import,
junctions restored), 1, 2a, 2b, 2c, 2d, 2f, 2g, 2e, 3a–3d, 4, 4b–4f, the schematic ↔ PCB re-link, 5; then the
closing (SKILL.md, "Closing") and the fabrication outputs (section 8).

## 4. Steps in detail

### Step 0 — renaming

- **Import leaves**: files named after the EasyEDA project (`ProPrj_<name>_<date>`), a symbol library and a
  library nickname derived from it (`…-easyedapro`), symbol instances that carry the old project name.
- **Do**: copy the raw `.kicad_pcb` and `.kicad_sch` from `_pre_import_backup/` to the board root under the board
  name, replacing in the text the old project name by the new one and `<OLD_LIB>:` by `<LIB>:` (this covers the
  `(instances (project "<old>" …))` blocks, `lib_id`, Footprint fields and the PCB's FPIDs); copy the `.kicad_sym`
  as `<LIB>.kicad_sym` with the same prefix replacement; write `sym-lib-table` and `fp-lib-table` pointing at
  `${KIPRJMOD}/<LIB>.kicad_sym` and `${KIPRJMOD}/<LIB>.pretty`.
- **Traps**: forgetting the instances leaves every reference shown as `?` (pitfall 15). The nickname in the
  tables must be exactly the one in the files; KiCad reads the tables at startup only (pitfall 5). At a re-import
  the previous cleaned version's tables are kept (section 5).
- **Idempotent**: reads the untouched source in `_pre_import_backup/`; prints the number of replacements of each
  kind (0: the names in the table are wrong).
- **Proof**: the netlist exports (`kicad-cli sch export netlist`); the schematic opens with its references.

### Step J — cross-node junctions (before any other work on the schematic)

- **Import leaves**: pitfall 32.
- **Do**: `python3 scripts/easyeda_junctions.py <project.epro> <board>.kicad_sch` (report), then `--fix` (method,
  exit codes and refusals in its docstring), on the renamed schematic, as part of the chain: step 0 regenerates
  the schematic from the raw import, so an earlier fix would be lost at the next replay. Its backup
  `<sch>.before_junctions`, written next to the schematic, is moved to `_pre_import_backup/`.
- **Idempotent**: a second run reports 0 missing.
- **Proof**: each group it reunites equals a group of the PCB. The `check_nets` reference is taken after this
  step, so that its schematic side is the design and not the import artefact.

### Step 1 — project footprint library and 3D models

- **Import leaves**: pitfalls 5 and 8.
- **Do (library)**, with pcbnew: for each distinct footprint name with library nickname `<LIB>`, copy the first
  instance (`pcbnew.FOOTPRINT(f)`, the board is not modified), set reference `REF**`, value = the name,
  orientation 0, position (0, 0), un-flip it if on the back (`Flip(VECTOR2I(0, 0), FLIP_DIRECTION_TOP_BOTTOM)`),
  and save with `PCB_IO_MGR.FindPlugin(PCB_IO_MGR.KICAD_SEXP).FootprintSave("<LIB>.pretty", copy)`. Free pads
  (`Pad_eNNN`, no nickname) are listed and left for step 2g.
- **Do (3D models)**: section 7.
- **Idempotent**: `FootprintSave` overwrites; model blocks are replaced, not appended.
- **Proof**: every FPID of the PCB resolves in `<LIB>.pretty`; render of both sides (step 4f).

### Step 2a — schematic: title block, Shorts, power symbols, Footprint fields

- **Import leaves**: pitfalls 10, 11, 12, 18 and 22.
- **Do**, in this order, on the `.kicad_sch` text:
  1. remove the instances of the title-block symbol and of the Short symbols, and their definitions in
     `(lib_symbols`; note the position of each Short before removing it;
  2. insert a wire between the two pins of each Short, at the exact coordinates (excerpt below);
  3. give the merged net a single name: rename the labels of the side that disappears to the name the **PCB**
     carries for that net (the PCB of the import already has one net), so that the re-link renames nothing;
  4. annotate: in each symbol block whose Reference is `#PWR?`, replace both
     `(property "Reference" "#PWR?"` and `(reference "#PWR?")` by `#PWRnn`;
  5. list the symbols with `(on_board yes)`, no `#` prefix and a Footprint field equal to `<LIB>:`; empty the
     field of those without footprint, and give the others their real footprint, read from the PCB by reference
     designator (`(footprint "<LIB>:<name>"` … `(property "Reference" "<ref>"`).
- **Idempotent**: steps 1, 4, 5 are no-ops on a second run; step 2 must not run without a Short found (fail
  loudly rather than insert a wire at a stale position).
- **Proof**: ERC: nothing left unannotated; `check_nets` identical once the pins of the side joining the other
  net are declared in `sch_merge`, and nothing else. That does not prove the wire touches (the labels now join
  the net by name): the ERC must show no dangling wire end at the two pins (pitfall 39; leftover ends: step 2f).

```python
# excerpt — validated with KiCad 10.0.x
# EasyEDA "Short" symbols replaced by a wire between their two pins (symbol at rotation 0, not mirrored: pins at
# ±2.54 mm). A rotated or mirrored Short stops the script before anything is written.
import re, uuid
from sexp import top_blocks, block_end, remove_block

s = open(SCH).read()
shorts = []
for a, b in reversed(top_blocks(s, "symbol")):          # reversed: the offsets before the removal stay valid
    blk = s[a:b]
    lid = re.search(r'\(lib_id "([^"]+)"', blk).group(1)
    if lid.split(":")[-1].startswith("Short-Symbol"):
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", blk)     # the first (at …) is the symbol's
        if at is None:
            raise SystemExit(f"Short placement unreadable: {blk[:80]!r}; nothing written")
        x, y, angle = map(float, at.groups())
        mirror = re.search(r"\(mirror [xy]\)", blk)
        if angle % 360 or mirror:
            raise SystemExit(f"Short at ({x}, {y}), rotation {angle:g}°{', mirrored' if mirror else ''}: its pins are "
                             "not at x ± 2.54 mm; nothing written")
        shorts.append((x, y))
        s = remove_block(s, a, b)
assert shorts, "no Short found: already replaced?"
for name in SHORT_SYMBOLS:                              # their definitions in the embedded library
    i = s.find(f'(symbol "{LIB}:{name}"')
    if i >= 0:
        s = remove_block(s, i, block_end(s, i))
wires = ""
for x, y in shorts:
    # exact coordinates: KiCad stores the sheet to 0.1 µm, ":.4f" keeps every digit; ":g" keeps six significant
    # digits (1000.254 → 1000.25) and ":.2f" two decimals: the wire would land beside the pins, unconnected and
    # invisible on screen
    x1, x2 = round(x - 2.54, 4), round(x + 2.54, 4)
    wires += (f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1:.4f} {y:.4f}) (xy {x2:.4f} {y:.4f})\n\t\t)\n'
              f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{uuid.uuid4()}")\n\t)\n')
k = s.index("\n\t(wire\n") + 1                           # before the first existing wire
open(SCH, "w").write(s[:k] + wires + s[k:])
```

For a rotated or mirrored Short, take the two pin positions from `pins.placed_pins(text)` **before** removing the
symbol (same transform, 0.1 µm resolution) instead of ±2.54 mm. This variant has not been exercised and is outside
the validated domain: the script stops on such a Short unless the designer asks for the variant, whose result is
then checked with the ERC as above.

### Step 2b — pin electrical types

- **Import leaves**: no electrical type; every pin is `unspecified` or `input`, the ERC is unreadable (pitfall 9).
- **Do**: one function `pin_type(symbol, number, name)` and one rewrite pass applied to **both** the
  `(lib_symbols` block of the `.kicad_sch` (symbols named `<LIB>:<name>`) and the `.kicad_sym` (symbols named
  `<name>`): the ERC reads the embedded copy, and a divergence between the two raises `lib_symbol_mismatch`.
  In each top-level symbol block (skip the sub-unit blocks `<name>_<n>_<m>`, which are inside it), replace
  `(pin <type> ` by the computed type, reading the pin's `(name "…")` and `(number "…")` from its block.
- **Types**: passives, diodes, LEDs, connectors, test points → `passive`; regulator: input and ground `power_in`,
  output `power_out`, enable `input`, unused `no_connect`; load switch: flag `open_collector`; MCU or SoC: supplies
  `power_in`, GPIO and straps `bidirectional`; PHY: per the datasheet pin table (line pins `passive`, clock output
  `output`, interrupt `open_collector`); oscillator: output `output`; ground symbols `power_in`, **not**
  `power_out` (several power outputs on one net is an error). Pass-through "NC" pins of a flow-through ESD array
  are `passive`. An internal regulator output brought out on two pins: one `power_out`, the other `passive`.
- **How to stay honest**: one dictionary per IC, copied from the datasheet pin table and indexed without default
  (`{…}[name]`), so that an unknown pin name stops the script; `passive` is the default only for unlisted symbols.
- **Idempotent**: sets types; prints the number of pins changed.
- **Proof**: the ERC no longer reports pin-type conflicts that are artefacts; what remains is handled in 2e.

### Step 2c — flags lost by the import

- **Import leaves**: "do not populate", "excluded from BOM" and "not on the board" are dropped.
- **Do**: read "Add into BOM" and "Convert to PCB" of each part in the `.esch`, build the table
  `{reference: {dnp, in_bom, on_board, in_pos_files}}` and set `(dnp yes|no)`, `(in_bom …)`, `(on_board …)`,
  `(in_pos_files …)` in the matching symbol blocks. Typical rows: an optional part not on the board (all four), a
  part on the board but not fitted (`dnp yes`, `in_bom no`), debug headers (`in_bom no`, `in_pos_files no`).
- **Idempotent**: sets values; reports a flag absent from the block instead of skipping it.
- **Proof**: the table equals the `.esch`; later, the BOM and placement comparison of `pcb-export-fidelity`.
  A part declared off-board goes into `new_refs` of `check_nets`.

### Step 2d — library file aligned with the embedded library

- **Import leaves / previous steps leave**: pitfall 20.
- **Do**: the embedded copy is authoritative. For each `(symbol "<LIB>:<name>"` at two tabs in `(lib_symbols`,
  take its block, strip the `<LIB>:` prefix on its first line only, remove one leading tab per line, and replace
  the block of the same name in the `.kicad_sym`; report the names absent from the library file. Then empty the
  `<LIB>:` Footprint fields of the `.kicad_sym`.
- **Idempotent**: re-run it after 2e and 2g, which add symbols.
- **Proof**: ERC, 0 `lib_symbol_mismatch`.

### Step 2f — wires that extend past their label

- **Import leaves**: pitfalls 13, 19 and 36.
- **Do**, on the `.kicad_sch` text, with the list of connection points = pin positions (`pins.placed_pins`),
  anchors of labels, global and hierarchical labels, junctions, no-connect markers, and the ends of the other
  wires, all converted to integer internal units (0.1 µm, `iu` of `scripts/easyeda_junctions.py`). KiCad connects
  only an exact coincidence, so "touches" and "on the segment" are exact integer tests: P is on the wire AB when
  `cross(B − A, P − A) == 0` and `0 <= dot(P − A, B − A) <= dot(B − A, B − A)` (`wires_through`, same file); a point
  near the wire but not on it is not a connection point of that wire:
  1. first pass: remove the two-point wires whose two ends touch nothing and that carry no connection point along
     their length (stubs of a few hundredths of a millimetre, sometimes off the sheet);
  2. loop: find a wire with one or both ends free (no connection point equal to it). List the distinct
     connection points on the segment, its connected end included. None, or only its connected end: the wire
     connects a single point, remove it. A single point in the middle of a wire free at both ends: leave it (it
     connects nothing else; the ERC lists it for review). Otherwise move each free end to its nearest connection
     point (text replacement of that `(xy …)`, written with `fmt` of the same file; stop if the text is not
     found). Restart the scan after each change, until no wire is left to change.
- **Rule**: shorten, never delete a wire that carries something in its middle; a pin or a label may sit on the
  segment while only the tip sticks out.
- **Cost**: the rescan makes it quadratic; it can take minutes on a full sheet, silently (run it unbuffered, in
  the background: section 1).
- **Proof**: nothing may move in `check_nets`; ERC `unconnected_wire_endpoint` = 0, apart from stubs shorter than
  0.3 mm, which step 2e removes at the positions the ERC gives, and the wires left for review.

### Step 2g — free pads → test points and mounting holes

- **Import leaves**: pads placed by hand in EasyEDA as footprints without symbol, reference or library. After the
  re-link they keep the old net name while the rest is renamed: two nets in contact (pitfalls 6, 7).
- **Do (schematic, text)**: copy the `TestPoint` symbol of KiCad's `Connector.kicad_sym` (or a mounting-hole
  symbol) into the `.kicad_sym` and, prefixed `<LIB>:` and indented two tabs deeper, into `(lib_symbols`. For each
  free pad add, in a free area of the sheet, a symbol instance (`in_bom no`, `in_pos_files no`, `on_board yes`,
  Footprint `<LIB>:<footprint name>`, an `(instances (project "<board>" (path "/<root sheet uuid>" …)))` block
  copied from an existing symbol) and tie its pin to the net with an object **of the same kind as the net already
  uses**: a local label, a global label, or a copy of an existing power symbol of that net (new uuids, next `#PWR`
  number, translated to the pin; the pin of KiCad's `TestPoint` is at the symbol origin). Keep each new symbol's
  uuid: the PCB needs it.
- **Do (PCB, pcbnew)**: excerpt below; each free pad is identified by its net (asserted) or its position, never by
  its `Pad_eNNN` identifier alone (pitfall 40).
- **Traps**: FPID **with** the library nickname (pitfall 21). A back-side SMD pad arrives as a `B.Cu` pad in an
  unflipped footprint: bring its layers to the front, then flip the footprint; a through-hole pad is not "back"
  (pitfall 44). Reference designators: those of the most recent export (pitfall 31).
- **Idempotent**: library definitions guarded by a presence test; a reference designator already in the schematic
  and on the PCB is skipped, so that a re-run creates no duplicate.
- **Proof**: the new references declared in `new_refs` of `check_nets`; no footprint without reference left;
  after the re-link, parity 0 and no footprint at the origin.

```python
# excerpt — validated with KiCad 10.0.x (pcbnew)
# Free pad of the import (no library, no reference) → project footprint linked to the symbol created for it.
import pcbnew as P

b = P.LoadBoard(PCB)
io = P.PCB_IO_MGR.FindPlugin(P.PCB_IO_MGR.KICAD_SEXP)
free = {f.GetFPIDAsString(): f for f in b.GetFootprints()}
FRONT = {"B.Cu": P.F_Cu, "B.Mask": P.F_Mask, "B.Paste": P.F_Paste}
saved = False
for ref, net, pad_id, sym_uuid in TEST_POINTS:          # board table; sym_uuid = uuid of the schematic symbol
    old = free[pad_id]
    assert [p.GetNetname() for p in old.Pads()] == [net], (ref, pad_id)   # the identifier alone proves nothing
    pos = old.GetPosition()
    back = all(not p.IsOnLayer(P.F_Cu) for p in old.Pads())   # SMD on the back; a through-hole pad is not "back"
    g = P.FOOTPRINT(old)
    if back:                                             # B.Cu pad in an unflipped footprint: to the front first
        for p in g.Pads():
            ls = P.LSET()
            for l in p.GetLayerSet().Seq():
                ls.AddLayer(FRONT.get(P.LayerName(l), l))
            p.SetLayerSet(ls)
    g.SetFPID(P.LIB_ID(LIB, FP_NAME))                    # with the nickname, or the re-link duplicates it
    g.SetAttributes(P.FP_EXCLUDE_FROM_BOM | P.FP_EXCLUDE_FROM_POS_FILES | P.FP_SMD)   # FP_SMD: surface pad
    if not saved:                                        # the first one also becomes the library footprint
        lib = P.FOOTPRINT(g)
        lib.SetReference("REF**"); lib.SetValue(FP_NAME); lib.SetPosition(P.VECTOR2I(0, 0))
        for p in lib.Pads():
            p.SetNetCode(0)
        io.FootprintSave(LIB_DIR, lib)
        saved = True
    g.SetReference(ref); g.Reference().SetVisible(False)
    g.SetValue("TestPoint"); g.Value().SetVisible(False)
    g.SetPath(P.KIID_PATH(f"/{sym_uuid}"))
    g.SetSheetname("/"); g.SetSheetfile(SCH_NAME)
    if back:
        g.Flip(pos, P.FLIP_DIRECTION_TOP_BOTTOM)         # now a back-side footprint with a B.Cu pad, same place
    b.Add(g)
    b.Remove(old)
b.Save(PCB)
```

### Step 2e — end of the ERC

Run the ERC first (`_cleanup/erc_before_2e.json`); every fix is placed at the position the report gives (× 100).

- **Two power outputs on one net**: the pin types of step 2b (one `power_out`, one `passive`, schematic and
  library).
- **`power_pin_not_driven`**: copy `PWR_FLAG` from KiCad's `power.kicad_sym` into the `.kicad_sym` and into
  `(lib_symbols` (prefixed, re-indented), and place one instance (`#FLGnn`) exactly on each flagged pin.
  Typically ground (fed by ground symbols, which are inputs) and the supply entering through a connector; a rail
  leaving a regulator needs none.
- **`pin_not_connected`**: **review each pin** (really unused on this board, or a connection the import lost?),
  then place a `(no_connect (at X Y) (uuid "…"))` on it. Do not change the pin type in the library: unused is a
  decision of this board, not of the symbol.
- **`unconnected_wire_endpoint`** on wires shorter than 0.3 mm with an end within 0.02 mm of the flagged
  position: remove the stub.
- **`same_local_global_label`**: turn the local labels of the names quoted in the report into global labels at
  the same anchor, angle and uuid (`justify left` for 0° and 90°, `right` otherwise).
- **Idempotent**: definitions guarded by a presence test; the markers come from a fresh ERC report, which no
  longer lists what is fixed. Do not replay the step on a stale report.
- **Proof**: ERC 0 errors (`check_nets` ignores the `#FLG` references). Warnings that stay: guide, "What remains
  and is normal".

### Step 3a — rule areas, pad connection, same-number pads

- **Import leaves**: pitfalls 1–4 and 14.
- **Do**, with pcbnew, for each zone: if `GetIsRuleArea()`: `SetDoNotAllowTracks(False)`, `…Vias(False)`,
  `…Pads(False)`, `…Footprints(False)`, `SetDoNotAllowZoneFills(True)`; if it has no copper layer, give it the
  copper layers on which EasyEDA cleared the pour (all of them unless the stored fill says otherwise: measure,
  layer by layer, the copper left inside the polygon in the stored EasyEDA fill; where about none is left, the
  keep-out was active). Otherwise (a pour): `SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)`. For each
  footprint, pads sharing a number must share a net: give a pad without net the net of its namesakes (shield tabs
  of a connector). Then `assets/kicad_template/apply_zone_settings.py <board> --clearance <measured>` (clearance,
  minimum width, thermal gap and spoke of every copper zone; defaults, backup and refusals in its docstring), with
  the values measured for this board (section 6) where they differ from its defaults.
- **Never** delete the rule areas wholesale: most are legitimate.
- **Idempotent**: sets values.
- **Proof**: refill, then compare the filled area of each pour before, after and with EasyEDA's (an area grown by
  a large factor means legitimate rule areas were removed); DRC `items_not_allowed`, `copper_sliver`,
  `isolated_copper`, `connection_width` at 0. Worked mechanism of the pad connection: the narrowest copper neck
  between the supply pads of a load switch and its capacitors is set mostly by the connection mode, not the
  clearance. Thermal reliefs on every pad can shrink it to a fraction of the neck EasyEDA produced with solid
  connections; reliefs on through-hole pads only bring it back to about that value, whereas halving the zone
  clearance gives back little. Measure the neck on the refilled pour for each mode, and in EasyEDA's stored fill.

### Step 3b — footprint circles on Edge.Cuts → NPTH pads

- **Import leaves**: pitfalls 16 and 27.
- **Do**: excerpt below, on every footprint of the PCB and on the same footprints of the `.pretty`
  (`FootprintLoad`, set the FPID with its nickname, convert, `FootprintSave`), with a table
  `{footprint name: drill diameter}` taken from the EasyEDA drill file.
- **Idempotent**: the converted graphics are gone; holes already converted are reset to the table diameter.
- **Proof**: NPTH count and diameters equal to the EasyEDA drill file (`pcb-export-fidelity`); Edge.Cuts holds
  only the outline; pour area around the holes back to EasyEDA's.

```python
# excerpt — validated with KiCad 10.0.x (pcbnew)
# Circles a footprint carries on Edge.Cuts → drilled NPTH pads. DRILL = {footprint name: diameter in mm}.
import math
import pcbnew as P

def convert(f):
    name = f.GetFPID().GetLibItemName().wx_str()
    n = 0
    for p in f.Pads():                                   # re-run: holes already converted reset to size
        if p.GetAttribute() == P.PAD_ATTRIB_NPTH and name in DRILL:
            d = int(DRILL[name] * 1e6)
            if p.GetDrillSize().x != d:
                p.SetSize(P.VECTOR2I(d, d)); p.SetDrillSize(P.VECTOR2I(d, d)); n += 1
    for g in list(f.GraphicalItems()):                   # list(): items are removed inside the loop
        if g.GetLayer() != P.Edge_Cuts:
            continue
        bb = g.GetBoundingBox()
        c, d = bb.GetCenter(), (bb.GetWidth() + bb.GetHeight()) / 2
        if g.GetShape() == P.SHAPE_T_POLY:               # really a circle? radius constant within 2 % AND the
            o = g.GetPolyShape().Outline(0)              # area of a circle (a rectangle has its 4 corners at one
            rs = [math.hypot(o.CPoint(i).x - c.x, o.CPoint(i).y - c.y) for i in range(o.PointCount())]   # radius)
            area = abs(g.GetPolyShape().Area()) if o.PointCount() >= 3 else 0.0
            r = sum(rs) / len(rs) if rs else 0.0
            if o.PointCount() < 8 or max(rs) - min(rs) > 0.02 * d or area < 0.97 * math.pi * r * r:
                print("not a circle, left alone:", f.GetReference(), round(d / 1e6, 2))
                continue
        elif g.GetShape() != P.SHAPE_T_CIRCLE:           # a rectangle, a segment, an arc: a real cut-out, kept
            print("not a circle, left alone:", f.GetReference(), g.GetShapeStr(), round(d / 1e6, 2))
            continue
        d = int(DRILL.get(name, d / 1e6) * 1e6)          # diameter of the EasyEDA drill file when known
        p = P.PAD(f)
        p.SetAttribute(P.PAD_ATTRIB_NPTH); p.SetShape(P.PAD_SHAPE_CIRCLE)
        p.SetSize(P.VECTOR2I(d, d)); p.SetDrillSize(P.VECTOR2I(d, d))
        p.SetLayerSet(P.PAD.UnplatedHoleMask()); p.SetNumber("")
        f.Add(p); p.SetPosition(c)                       # position set after Add (board coordinates)
        f.Remove(g); n += 1
    return n
```

### Step 3c — solder paste

- **Import leaves**: EasyEDA / LCSC footprints draw their paste openings as separate shapes and switch the pad's
  own paste off; the import loses that switch, so the pad gets full paste on top of the dedicated shape.
- **Do**, with pcbnew, on the PCB and on the `.pretty`: (1) for each pad on `F.Paste` whose own shape intersects a
  graphic shape of its footprint on `F.Paste`, remove `F.Paste` from the pad's layer set (the stencil is then
  EasyEDA's). Intersect the polygons, not the bounding boxes (that of a rotated pad covers its neighbours'
  openings): `TransformShapeToPolygon(sp, layer, 0, maxerr, ERROR_INSIDE)` of the pad on its copper layer
  (rotation included) and of the shape on `F.Paste`, then `BooleanIntersection` and an area > 0; (2) **a thermal
  pad still pasted at 100 % is usually an omission of the library footprint**: ordinary footprints rarely print a
  full exposed pad. Check the package's stencil recommendation (the manufacturer's "example stencil design" page
  of the package drawing) and confirm with the designer. For each such pad, listed by footprint name in a table
  with its source: remove `F.Paste` from the pad and add filled rectangles on `F.Paste`, rotated by the pad
  orientation and moved to the pad position: the apertures of the manufacturer's example stencil (e.g. an exposed
  pad split into several openings) or, when the datasheet gives none, one centred rectangle at 64 % of the area
  (side 0.8 × the pad), a common convention of EasyEDA's LCSC footprints, not a requirement. Detect the thermal
  pads rather than trust the table alone: the largest SMD pad of a footprint of at least four pads, at least 2.5
  times the next one, at the centre of the pads (within a quarter of their extent: the tab of a SOT-223 is not
  one). A detected pad at 100 % that the table does not cover stops the step before anything is written. Same for
  `B.Paste` on back-side parts. Tell the designer, so that the same reduction goes into the EasyEDA project (paste
  expansion of the pad): otherwise the next re-import brings the 100 % back.
- **Alternative for (2)**: the rule of `assets/kicad_dru/thermal_pad_paste.kicad_dru`, appended to the board's
  `.kicad_dru`. The detection above (pad geometry) is the primary method; the rule's filter (SMD pads of at least
  0.9 × 0.9 mm, `memberOfFootprint('U*')`) works on the reference designator (pitfall 30).
  `solder_paste_rel_margin` is in tenths of a percent. Check the openings it produces on the paste Gerber against
  EasyEDA's.
- **Idempotent**: a pad already off `F.Paste` is not touched; openings are added only when the footprint has no
  paste shape.
- **Proof**: report of pads changed per footprint and coverage of each reduced thermal pad; paste Gerber against
  EasyEDA's (`pcb-export-fidelity`): the only differences are the thermal pads deliberately reduced, until the
  designer carries the reduction into EasyEDA.

### Step 3d — EasyEDA solid fills → filled polygons with a net

- **Import leaves**: pitfall 24.
- **Do**: read the `FILL` entries of the `.epcb` (excerpt 1), match each with its imported zone (same net and
  layer, bounding-box centres within 0.3 mm and sizes within 0.3 mm: a pour of the same net around a fill may share
  its centre; two candidates stop the script before anything is written), replace the zone by a filled `gr_poly`
  on the same layer with the same net and the exact outline (excerpt 2), then refill. Pours avoid the shape (other
  net) or merge with it (same net), as in EasyEDA. Zones on several layers or with holes are reported and left
  alone; an arc in a polygon outline stops the script (not handled).
- **Frame**: `ORIGIN` is the EasyEDA origin in KiCad coordinates (section 6); the centre distance printed for
  each fill checks it.
- **Idempotent**: on a second run each fill finds its polygon ("already converted": filled, no stroke, one outline
  without hole, same layer, net and corners) and no zone is searched.
- **Proof**: every fill converted (`n/n`); the filled percentage printed before conversion documents the defect;
  DRC after refill: 0 unconnected, no new clearance error; copper Gerber against EasyEDA's.

```python
# excerpt — validated with KiCad 10.0.x
# 1/2: outline of each solid fill of the .epcb (one JSON array per line; lengths in units of 0.0254 mm, Y up).
import json, math, zipfile

def fill_outline(geo):
    """["R", x, y, w, h, rot, r]: rectangle from its top-left corner, rotated counter-clockwise about that
    corner, corner radius r; otherwise a polygon [x0, y0, "L", x1, y1, …]. Corner arcs in 10° segments."""
    if geo[0] == "R":
        x, y, w, h, rot, r = geo[1:7]
        r = min(r, w / 2, h / 2)
        loc = []                                        # local frame: x right, y up, top-left corner at (0, 0)
        for cx, cy, a0 in ((w - r, -r, 0), (r, -r, 90), (r, -h + r, 180), (w - r, -h + r, 270)):
            if r <= 0:
                loc.append((cx, cy))
                continue
            for k in range(10):
                a = math.radians(a0 + 10 * k)
                loc.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        a = math.radians(rot)
        return [(x + u * math.cos(a) - v * math.sin(a), y + u * math.sin(a) + v * math.cos(a)) for u, v in loc]
    assert all(v == "L" or isinstance(v, (int, float)) for v in geo), "arc in a solid fill: not handled"
    nums = [v for v in geo if isinstance(v, (int, float))]
    pts = list(zip(nums[0::2], nums[1::2]))
    return pts[:-1] if pts[0] == pts[-1] else pts

def easyeda_fills(epro, layers):                        # 4-layer board: {1: F_Cu, 2: B_Cu, 15: In1_Cu, 16: In2_Cu}
    with zipfile.ZipFile(epro) as z:
        lines = z.read(next(n for n in z.namelist() if n.endswith(".epcb"))).decode().splitlines()
    out = []
    for line in lines:
        if line.startswith('["FILL"'):
            e = json.loads(line)                        # e[1] id, e[3] net, e[4] layer, e[7][0] geometry
            if e[4] in layers and e[3]:
                pts = fill_outline(e[7][0])
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                out.append((e[1], e[3], layers[e[4]], (min(xs) + max(xs)) / 2 * 0.0254,
                            (min(ys) + max(ys)) / 2 * 0.0254, pts))
    return out
```

```python
# excerpt — validated with KiCad 10.0.x (pcbnew)
# 2/2: the zone the import made of each solid fill → filled polygon with the same net. ORIGIN in mm (KiCad).
U = 0.0254
b = P.LoadBoard(PCB)
zones = [z for z in b.Zones() if not z.GetIsRuleArea()]
done = {(s.GetLayer(), s.GetNetname().lstrip("/"), tuple((q.x, q.y) for q in s.GetPolyPoints()))
        for s in b.GetDrawings() if s.GetClass() == "PCB_SHAPE" and s.GetShape() == P.SHAPE_T_POLY
        and s.IsSolidFill() and s.GetWidth() == 0              # the copper this step writes: an outline is not
        and s.GetPolyShape().OutlineCount() == 1 and s.GetPolyShape().HoleCount(0) == 0}
for fid, net, layer, cx, cy, pts in easyeda_fills(EPRO, LAYERS):
    corners = [P.VECTOR2I(round((ORIGIN[0] + u * U) * 1e6), round((ORIGIN[1] - v * U) * 1e6)) for u, v in pts]
    if (layer, net, tuple((q.x, q.y) for q in corners)) in done:
        print(f"{fid} {net}: already converted")      # a second run: no zone is searched, a pour stays
        continue
    w = (max(u for u, v in pts) - min(u for u, v in pts)) * U
    h = (max(v for u, v in pts) - min(v for u, v in pts)) * U
    found = []
    for z in zones:
        if z.GetNetname().lstrip("/") != net or not z.IsOnLayer(layer):
            continue
        bb = z.GetBoundingBox()
        d = abs(bb.GetCenter().x / 1e6 - ORIGIN[0] - cx) + abs(ORIGIN[1] - bb.GetCenter().y / 1e6 - cy)
        if d < 0.3 and abs(bb.GetWidth() / 1e6 - w) + abs(bb.GetHeight() / 1e6 - h) < 0.3:
            found.append((d, z))
    if len(found) > 1:                                   # b.Save() not reached: nothing written
        raise SystemExit(f"{fid} {net}: {len(found)} zones of this net and layer have its centre and size; "
                         "nothing written")
    if not found:
        print(f"{fid} {net}: no matching zone")
        continue
    d, z = found[0]
    if len(z.GetLayerSet().Seq()) > 1 or z.Outline().OutlineCount() != 1 or z.Outline().HoleCount(0):
        print(f"{fid} {net}: zone on several layers or with holes, left as is")
        continue
    s = P.PCB_SHAPE(b, P.SHAPE_T_POLY)
    s.SetLayer(layer); s.SetFilled(True); s.SetWidth(0)
    s.SetPolyPoints(corners)
    s.SetNet(z.GetNet())                                 # KiCad 10: a graphic shape on copper carries a net
    b.Add(s)
    print(f"{fid} {net} centre gap {d:.3f} mm, was filled "
          f"{100 * z.GetFilledArea() / z.Outline().Area():.1f} % → solid shape ({len(pts)} points)")
    b.Remove(z)
    zones = [x for x in zones if x is not z]             # identity: list.remove() compares zones by value
b.Save(PCB)                                              # then: kicad-cli pcb drc --refill-zones --save-board
```

### Step 4 — design rules, Board Setup, net classes, stackup, mask

- **Import leaves**: no fabrication rules, EasyEDA layer names, no stackup, mask expansion 0 (pitfall 25), net
  classes without the intended widths (pitfall 38). Where each setting lives: `assets/kicad_template/README.md`.
- **Do (`.kicad_dru`)**: start from `assets/kicad_template/JLCPCB_35um.kicad_dru`. For four layers, comment
  the rule "Minimum Trace Width and Spacing (outer layer)" and the 2-layer "Minimum Via Diameter and Hole Size",
  uncomment their 4-layer versions, and assert that exactly one rule of each name is active. Append the board's
  exceptions (step 4b) **before** the copper-pour rule, which must stay last. Write the result as
  `<board>.kicad_dru`.
- **Do (`.kicad_pro`, JSON)**: copy `board.design_settings` from `assets/kicad_template/template.kicad_pro`
  (equivalent to Board Setup → Import Settings from Another Board); write `net_settings.classes` and
  `net_settings.netclass_patterns` as `{"netclass": …, "pattern": "*<net name>"}` entries. Patterns on anonymous
  nets must be updated after the re-link, which renames them (`$1N…` → `Net-(<ref>-Pad<n>)`).
- **Net classes of controlled-impedance pairs carry two widths** (pitfall 38): pair width and gap (coupled legs:
  target differential impedance) and track width (a leg routed away from its partner, sized for the impedance
  wanted for a lone leg), values asked of the designer (SKILL.md, working rules). The figures for a given stackup
  come from the 2D field solver of `pcb-verification/lib/`, through `pcb-check-impedance`, which is also the
  verification (with `pcb-check-layout-audit`).
- **Do (`.kicad_pcb`, text)**: reset the layer names to the standard ones (drop the user name in
  `(<n> "F.Cu" signal "<user name>")`, same for the technical layers); insert the `(stackup …)` block at the top
  of `(setup`, refusing to run if one is present; set `(pad_to_mask_clearance 0.05)` (vias stay covered). The
  stackup values (copper thicknesses, prepreg and core thicknesses and εr, solder-mask thickness and εr, loss
  tangent where the stackup states it) are those of the stackup actually ordered, from the fabricator's stackup
  sheet or the designer's file, never assumed.
- **Idempotent**: the `.kicad_dru` and `.kicad_pro` are regenerated from the templates; the stackup is guarded.
  Give the script a `--pcb-only` mode: at a re-import only the PCB part is replayed, and the rule and project
  files of the previous cleaned version are kept (they hold the exceptions and classes added since).
- **Proof**: DRC runs and reports rule names of the file (section 1, traps); the pre-defined track and via sizes
  list the widths of the board.

### Step 4b — dangling track ends and targeted DRC exceptions

- **Import leaves**: track stubs of a fraction of a millimetre covered by other tracks of the same net
  (`track_dangling`), and geometry of EasyEDA footprints or vias that falls just under a JLC rule.
- **Do (stubs)**: from the DRC JSON, take the `uuid` of the items of the `track_dangling` violations, find the
  tracks with `t.m_Uuid.AsString()` in that set, assert each is shorter than a threshold (e.g. 0.15 mm; longer ones
  are looked at one by one: a longer end can be a real leftover of the design), print net, layer and length,
  remove. **Run the DRC again and repeat** until none is left (pitfall 42).
- **Do (exceptions)**: each exception is a rule appended to the `.kicad_dru` that targets one component or one
  object type, with a comment giving the measured value and whether the fabricator's capability table covers it or
  the designer accepts it. Typical cases: edge clearance of a board-edge connector whose shield tabs fall under the
  global clearance (`edge_clearance (min <measured value>)`,
  `A.memberOfFootprint('<ref>') || B.memberOfFootprint('<ref>')`); annular ring of imported vias whose drill and
  pad leave a ring under the rule (compare with the minimum of the fabricator's capability table for the layer
  count); via-to-track hole clearance a few micrometres under the rule because of EasyEDA's rounding (rule set at
  the rounded value); locating pegs (NPTH) of a connector closer to the pads of the same footprint than the
  hole-clearance rule (`hole_clearance (min <measured value>)` restricted to that footprint on both sides).
- **Trap**: an exception written too broadly also applies to the pours (a hole-clearance exception meant for
  the pads of one connector lets the pours come closer to its NPTH holes than the global rule). State both sides of
  the condition (`A.…` and `B.Type == 'Pad'`).
- **Idempotent**: test for the rule name before appending; a removed stub is no longer reported.
- **Proof**: DRC 0 errors, 0 unconnected; what remains and is normal: guide, "What remains and is normal".

### Step 4c — library footprints re-exported from the PCB

After 3b, 3c or a manual fix, the PCB instance is authoritative: re-export the footprints concerned to the
`.pretty` as in step 1 (copy, `REF**`, orientation 0, position 0, un-flipped). Proof: 0 `lib_footprint_mismatch`.

### Step 4d — silkscreen text aspect

- **Import leaves**: narrow silkscreen texts (pitfall 34).
- **Do**, on the `.kicad_pcb` text, for `gr_text`, footprint `property` and `fp_text` entries on `F.SilkS` and
  `B.SilkS`: in `(size <height> <width>)`, set the width equal to the height (height kept). Backup first.
- **Idempotent**: entries with equal values are skipped; prints the count.
- **Proof**: silkscreen Gerber against EasyEDA's: printed width close to EasyEDA's, height unchanged.

### Step 4e — glyphs missing from the font

- **Import leaves**: a character absent from the KiCad font printed as "?" or an empty box (pitfall 17).
- **Do**: list the visible texts with a non-ASCII character; test each character against the font
  (`fc-list ':charset=<hex code>'` lists the fonts that have it) and handle only the missing ones. Replace the
  text by filled polygons on the same layer, taken from the silkscreen Gerber of the EasyEDA export (polygons in
  mm, converted to the KiCad frame with the drill origin: x = ox + x, y = oy − y). Keep the polygons in a small
  JSON next to the script with the text, layer and position they replace, and assert that the text is still
  there: if it moved, extract the glyph again.
- **Idempotent**: on a second run the text is gone and nothing is added.
- **Proof**: silkscreen Gerber diff at that place.

### Step 4f — 3D render

`kicad-cli pcb render --side top` and `--side bottom` (and an oblique view) after step 1 and after any model
change. Look for models sunk into the board, hanging under it or missing; the back view shows what the top view
hides. Corrections: section 7.

### Schematic ↔ PCB re-link (F8)

- **Import leaves**: no footprint has a `(path …)` to its symbol (pitfall 6); nets carry EasyEDA names.
- **By the designer, in KiCad** (reloaded after the last script, pitfall 45): Update PCB from Schematic with
  "Re-link footprints to schematic symbols based on their reference designators" **checked, once**; "Delete
  footprints with no symbols" and "Replace footprints with those specified by symbols" **unchecked** (the first
  would delete free pads, the second overwrite local fixes: mask, paste, 3D offsets). Then a second pass with
  "Update footprint fields from symbols" checked, without re-linking (pitfall 33).
- **Or by script**: section 5, "Helper 3".
- **Checks afterwards, every time**: `check_nets` identical; DRC with `--schematic-parity`: 0 parity items,
  0 unconnected, 0 errors; every footprint has a path; no duplicated reference designator and no footprint at the
  origin; the nets of each pad compared with the last commit (only names may change); net-class patterns updated
  for the renamed anonymous nets.
- **If the update moved a pad to a new net** (`Net-(<ref>-Pad<n>)`): pitfall 43, not a second update.
- **If footprints were duplicated** (created without library nickname, pitfall 21): for each reference present
  twice, the original (well placed, no path) takes the FPID, path, sheet name and file, value, attributes and net
  of the duplicate (at the origin, with a path), then the duplicate is removed.

### Step 5 — fixes from the Gerber comparison

The comparison itself belongs to `pcb-export-fidelity`. What it typically sends back here (cause and fix in the
guide): thermal gap (pitfall 35); spoke width and per-net connection mode (29); pours too close to the
tracks (23); pour clearance that differs on some layers (28, 41); a plane too close to the board edge (26); mask
expansion (25); NPTH diameters (27, step 3b); partly filled copper islands (24, step 3d).

Splitting the pour rule by layer (a custom rule takes precedence over the zone's local clearance, so both are set).
The layer names and values below illustrate a 4-layer board (inner planes `In1.Cu` and `In2.Cu`); use the values
measured on the board (section 6):

```
(rule "Copper pour: 0.254 mm from other nets"
	(constraint clearance (min 0.254mm))
	(constraint hole_clearance (min 0.254mm))
	(condition "A.Type == 'Zone' && A.Net != B.Net && A.Layer != 'In1.Cu' && A.Layer != 'In2.Cu'"))
(rule "Inner planes: 0.15 mm from other nets"
	(constraint clearance (min 0.15mm))
	(constraint hole_clearance (min 0.254mm))
	(condition "A.Type == 'Zone' && A.Net != B.Net && (A.Layer == 'In1.Cu' || A.Layer == 'In2.Cu')"))
```

Each fix is a small script (set the zone values, edit the rule file under a name guard, refill with
`kicad-cli pcb drc --refill-zones --save-board`), followed by `check_nets` and by the Gerber comparison again.

## 5. Re-import of a later revision

1. The designer exports the `.epro` and, **for the same revision**, Gerber, BOM and pick-and-place, and imports
   the `.epro` in KiCad into a staging folder (`<board>/IMPORT/`, git-ignored). KiCad closed afterwards.
2. Freeze the existing state: commit, tag `before-import-<revision>`, branch `import-<revision>`. The current
   version stays intact on the main branch until the new one is validated.
3. Tidy `_pre_import_backup/`: previous raw import into `import_<old revision>/`, EasyEDA exports into
   `easyeda_<revision>/`, new raw import at its root.
4. **Compare raw import against raw import** first (helper 0 below): the result lists what the designer changed
   and is the yardstick for everything that follows.
5. Replay the step scripts in order (0, J, 1, 2a…). Keep `.kicad_pro`, `.kicad_prl`, `.kicad_dru` and the library
   tables of the previous cleaned version, which do not depend on the imported content (step 0 without its
   tables, step 4 in `--pcb-only` mode). Carry the 3D settings over (helper 1). Scripts written for one revision
   are made generic as they break (section 1, idempotence).
6. Checks: `check_nets` after each step against the new reference; the ERC taken before step 2e compared with
   the previous import's (same free pins?); old cleaned board against new cleaned board (helper 2): only the
   designer's changes may come out; fidelity against the new exports, judged against the differences of the
   previous import (`pcb-export-fidelity`).
7. Schematic ↔ PCB link (helper 3, or the designer's F8), proven by parity 0.
8. Merge into the main branch only after the designer has validated.

What a re-import can bring: free-pad identifiers that change between exports (pitfall 40); a pour setting
changed in EasyEDA that only the Gerber comparison reveals (pitfall 41); a new part with "Add into BOM = no"
(step 2c reads the `.esch` again); stubs in chains (step 4b).

### Helper 0 — raw import against raw import

Load both raw `.kicad_pcb` with pcbnew and compare, by reference designator: footprint name, position, angle,
side; the net of each pad (both imports carry EasyEDA's net names; compare anonymous nets by their pad groups,
their names are not guaranteed stable); per net and layer, the histogram of track widths with lengths, and the
via count; zones (net, layers, bounding box, rule-area flags). Print only the differences. Typical output for a
routing revision: parts added, removed or moved; tracks re-routed at another width (listed per net and layer); a
rule area reduced to some layers; a return path moved to vias (more vias, fewer tracks).

### Helper 1 — carrying the 3D model blocks over, by reference designator

The offsets, rotations and replacement models set by eye live in the `(model …)` blocks of the previous PCB and
`.pretty`; a new import starts again from EasyEDA's. Text-level tool, dry run by default:

1. In both PCBs, list the footprints (`\n\t(footprint "<fpid>"` … `block_end`), with their Reference property and
   their `(model …)` blocks (two tabs deep).
2. For each footprint of the new PCB: skip it and say so if its reference is absent from the old PCB, or if the
   footprint name (without nickname) changed; skip it silently if its model blocks equal the old ones once
   whitespace is normalised; otherwise remove its model blocks and insert the old ones before the closing
   parenthesis of the footprint.
3. Print one line per distinct change: file name, offset and rotation before → after.
4. Same for the `.pretty`, by file name, model blocks one tab deep.
5. `--write` writes. Proof: second run reports 0 differences; render.

### Helper 2 — old cleaned board against new cleaned board

The new cleaned board may differ from the old one only where the designer changed something. Compare, with
pcbnew, what the cleanup sets and routing does not touch:

- per reference designator: attributes, footprint name and nickname, the sorted list of pads as (number,
  attribute, shape, size, drill, layer set), the count of graphic items per (layer, class), visibility of
  reference and value, layer of the reference; "linked to the schematic" is counted apart (old yes / new no is
  expected before the re-link); a reference present a different number of times is a difference;
- zones as multisets: rule areas by (layers, the five "do not allow" flags); pours by (local clearance, thermal
  gap, spoke width, minimum thickness, pad connection, island removal mode);
- board drawings as a multiset of (layer, class, net name); texts as (layer, text, width, height);
- the `(setup …)` block without the plot parameters and the `(layers …)` block: text diff;
- track and via counts, for information.

Every line that comes out is either in the list of helper 0 or a cleanup step that did not replay identically.

### Helper 3 — schematic ↔ PCB re-link by reference designator (scripted equivalent of F8)

**Warning.** This tool writes the PCB. It is validated against the result of a real "Update PCB from Schematic"
(nets, pin functions and fields identical, pad by pad), and only on single-sheet schematics: it writes the sheet
name as `/` whatever the sheet. A schematic with hierarchical sheets or multi-unit symbols is outside that domain:
detect it before any write and use KiCad's "Update PCB from Schematic" instead. It never adds, removes, replaces or
moves a footprint. The designer's plain F8 keeps the last word (proof, item 8).

Inputs: board folder, KiCad closed; `--dry-run` prints the counts without saving.

1. Export the netlist: `kicad-cli sch export netlist --format kicadsexpr`; stop if no file is produced.
2. From its `(components` section, per `(comp`: reference, footprint (with nickname), value, and the `tstamps`:
   the last one is the symbol uuid, the first one the sheet path (`/` for the root). Footprint path =
   `/<uuid>` on the root sheet, `<sheet path>/<uuid>` otherwise.
3. From the `.kicad_sch` text, per symbol instance: reference, the flags `dnp`, `in_bom`, `on_board`,
   `in_pos_files`, and every property (name, value, with `\"` and `\\` unescaped).
4. From the `(nets` section: for each net its name and nodes (reference, pin, pin function, pin type). Build
   `pin_net[(ref, pin)]`, `pin_info[(ref, pin)]`, `nodes[net]`.
5. Load the board; group the footprints by reference.
6. **Consistency checks; any failure is listed and nothing is written**:
   - every schematic component that is on the board and not `#…` has exactly one footprint, whose FPID equals
     the symbol's Footprint field;
   - every footprint has a symbol that is on the board;
   - for each PCB net, the schematic nets of its pads: exactly one, and no pad unknown to the schematic; no
     schematic net is the target of two PCB nets; no schematic pin of that net (whose reference exists on the
     PCB) is missing from the PCB net. This is what guarantees that renaming changes no connectivity.
7. Write (excerpt below): path, sheet name and file of each footprint; attributes DNP / excluded from BOM /
   excluded from position files from the flags; symbol fields copied to the footprint (not Reference, not
   Footprint), an empty Value written as `~`, fields created by the script hidden on the Fab layer of the
   footprint's side; each PCB net renamed to its schematic name; pin function and pin type on each pad; a pad
   without net whose pin is alone on its schematic net receives that net (`unconnected-(…)`), created if needed;
   a pad without net whose pin is connected to others in the schematic stops the script before any change, whether
   or not that schematic net already has a PCB net.
8. Proof: `kicad-cli pcb drc --schematic-parity` → **0 parity items**; `check_nets` identical; a second run
   reports 0 everywhere; the designer's F8 changes nothing.

```python
# excerpt — validated with KiCad 10.0.x (pcbnew)
# Step 7 of the re-link. comps[ref] = {"uuid", "sheet"}; ren = {PCB net name: schematic net name};
# by_ref[ref] = [footprints].
# A pad without net whose pin is connected to others in the schematic: assigning the net would create a connection.
lost = [(r, n) for f in b.GetFootprints() for p in f.Pads()
        for r, n in [(str(f.GetReference()), str(p.GetNumber()))]
        if p.GetNetCode() == 0 and (r, n) in pin_net and len(nodes[pin_net[(r, n)]]) > 1]
if lost:
    sys.exit(f"pads without net on the PCB but connected in the schematic: {lost}")
for ref, c in comps.items():
    if ref not in by_ref or ref.startswith("#"):
        continue
    f = by_ref[ref][0]
    path = "/" + c["uuid"] if c["sheet"] == "/" else c["sheet"].rstrip("/") + "/" + c["uuid"]
    if f.GetPath().AsString() != path:
        f.SetPath(P.KIID_PATH(path))
    f.SetSheetname("/"); f.SetSheetfile(f"{name}.kicad_sch")
    fl = flags.get(ref, {})
    attr = f.GetAttributes() & ~(P.FP_DNP | P.FP_EXCLUDE_FROM_BOM | P.FP_EXCLUDE_FROM_POS_FILES)
    attr |= (P.FP_DNP if fl.get("dnp") else 0) | (0 if fl.get("in_bom", True) else P.FP_EXCLUDE_FROM_BOM) | (
        0 if fl.get("in_pos_files", True) else P.FP_EXCLUDE_FROM_POS_FILES)
    f.SetAttributes(attr)
    fab = P.B_Fab if f.IsFlipped() else P.F_Fab
    for k, v in fields.get(ref, []):
        if k in ("Reference", "Footprint"):
            continue
        if k == "Value":
            f.SetValue(v or "~")                         # empty symbol value: "~" in the footprint
        elif not f.HasField(k) or str(f.GetFieldText(k)) != v:
            new = not f.HasField(k)
            f.SetField(k, v)
            if new:                                      # as F8 does: hidden, Fab layer of the footprint's side
                fld = next(x for x in f.GetFields() if str(x.GetName()) == k)
                fld.SetVisible(False); fld.SetLayer(fab); fld.SetPosition(f.GetPosition())
for code, ni in b.GetNetInfo().NetsByNetcode().items():
    bn = str(ni.GetNetname())
    if code > 0 and ren.get(bn, bn) != bn:
        ni.SetNetname(ren[bn])
for f in b.GetFootprints():
    for p in f.Pads():
        k = (str(f.GetReference()), str(p.GetNumber()))
        if k in pin_info:
            p.SetPinFunction(pin_info[k][0]); p.SetPinType(pin_info[k][1])
        if p.GetNetCode() == 0 and k in pin_net:         # free pin: its single-pin net of the netlist (`lost` above)
            t = pin_net[k]
            ni = b.FindNet(t)
            if ni is None:
                ni = P.NETINFO_ITEM(b, t); b.Add(ni)
            p.SetNet(ni)
b.Save(str(pcb))
```

### Carrying a change over from fabrication exports only (no re-import)

Case: the KiCad project has become the working copy (it carries changes EasyEDA does not have), the designer fixes
something in EasyEDA and hands over the Gerber zip, the BOM and the pick-and-place file, no project file. A re-import
would erase the KiCad-only work, so the difference is carried over instead.

1. Archive the exports (`_pre_import_backup/easyeda_<date>/`) and compare them **with the exports of the previous
   revision**, not with KiCad, which differs for its own reasons:
   - BOM and placement: parts added, removed, moved, rotated;
   - `FlyingProbeTesting.json`, shipped in the Gerber zip: net, position and layer of **every pad** (lengths in the
     unit given by `lengthUnit`; convert on reading). The per-pad net difference is the schematic change. An
     auto-named net (`$1N…`) renamed between two exports shows as all of its pads changing together;
   - copper Gerbers object by object (gerbonara `Line` with its aperture, `Flash`, `Region`): strokes of a track
     width are tracks, round flashes added or removed are vias (drill diameter from the drill file), regions are
     the pours. Thin strokes, narrower than any routed track, are pour outlines, not tracks;
   - a raster difference of the two export sets shows at a glance which areas are touched.
2. Frame: the drill origin. A KiCad zone outline is the Gerber pour region enlarged by half the EasyEDA outline
   stroke, with sharp corners; check that rule on an unchanged zone before using it.
3. Write the change as two replayable scripts (schematic, board) that refuse to write when the board is not in the
   expected state, and try them on a copy of the project.
4. Checks on the copy: netlist before / after (only the intended pins change), ERC unchanged, DRC and parity,
   Gerbers of the copy against the EasyEDA Gerbers **inside the touched areas** (no difference expected), Gerbers of
   the copy before / after **outside them** (no difference expected).
5. Apply to the project, the designer's current state committed first.

## 6. Measured EasyEDA conventions (re-check them on each board and EasyEDA version)

**Files.** An `.epro` is a zip: `project.json`, one `.epcb` (PCB) and one `.esch` per sheet, each a text file with
one JSON array per line, the first element being the kind (`"WIRE"`, `"LINE"`, `"VIA"`, `"POUR"`, `"POURED"`,
`"FILL"`, `"RULE"`, `"RULE_SELECTOR"`…).

**Units and frames.**

- `.epcb`: lengths in units of 0.0254 mm, Y up. x_KiCad = x × 0.0254 + ox; y_KiCad = oy − y × 0.0254. (ox, oy)
  is the EasyEDA origin in KiCad coordinates, often the bottom-left corner of the outline; align it
  on a known object (a free pad, a via) and check it on a second one.
- `.esch`: lengths in units of 0.254 mm, Y up. x_KiCad = x × 0.254 + dx; y_KiCad = dy − y × 0.254, (dx, dy)
  calibrated on existing junctions (`easyeda_junctions.py` does it by vote).
- Stored fills (`POURED`): coordinates usually in units of 0.254 mm (ten times the `.epcb` unit); check on a known
  edge.
- Layer numbers: 1 top copper, 2 bottom copper, 15 and 16 the two inner layers of a 4-layer board (for another
  layer count, read the numbers from the `.epcb`).
- Fields used by the scripts: `LINE` net [3], layer [4], ends [5..8], width [9]; `VIA` net [3], centre [5], [6],
  diameter [8]; `POUR` id [1], net [3], layer [4], stroke `["SOLID", w]`; `POURED` pour id [2], fill flag [4],
  rings [5] (path `x, y, "L", x, y, …, "ARC", angle, x, y`; rings combined even-odd: outline then holes); `FILL`
  id [1], net [3], layer [4], geometry [7][0]; `WIRE` list of segments [2] as `[x1, y1, x2, y2]`.

**Pours.**

- The stored fill is the **inner contour**: the exported copper is the stored polygon thickened by half the
  stroke width `w` of the pour. **Real gap ≈ stored gap − w/2.** Example: a stored gap of 0.202 mm with a 0.1 mm
  stroke and one of 0.252 mm with a 0.203 mm stroke both give about 0.15 mm on the Gerber.
- To measure the gap EasyEDA really applied (its rule matrix does not translate, pitfall 28): union of the stored
  rings of each pour (shapely), distance from that polygon to each track of another net on the same layer minus
  half the track width, and to each via minus its radius; keep the distances under 1 mm and take the most
  frequent value; subtract w/2; confirm on the Gerber export.
- The EasyEDA default is 0.254 mm; a designer may choose another value, possibly on inner planes only. The
  setting can change between two revisions without anything else changing (pitfall 41).

**Thermal reliefs.** Measure the gap and the spoke width on the Gerber: EasyEDA's default gap is 0.254 mm (the
import writes 0.5 mm, pitfall 35), the spoke width varies between designs (pitfall 29), and the default
connection relieves through-hole pads only (pitfall 3).

**Mask, vias, drills.** Mask expansion 0.05 mm per side (0.051 measured); vias tented; EasyEDA lists the vias
twice in its drill files (once with the plated holes, once in a via file).

**3D.** `3D Model Transform` in `project.json`: `width, depth, height, rotZ, rotX, rotY, dx, dy, dz`, lengths in
units of 0.0254 mm; the first rotation is about Z.

## 7. 3D models

**Where the alignment lives.** In the `(model "<path>" (offset (xyz …)) (scale (xyz …)) (rotate (xyz …)))` block
of each footprint: in the `.kicad_mod` files and, separately, in every instance in the `.kicad_pcb`. Not in the
STEP file. A correction made in the 3D viewer is stored on the PCB instance.

**Method** (text-level tool; a central footprint / 3D library, if the designer keeps one, is the store of
corrections already made: a `.pretty` whose footprints carry validated model blocks, and a model folder):

1. Collect the model references of the PCB and of the project `.pretty` (path, footprint name).
2. Copy **only the files the board uses** into `<board>/EASYEDA_MODELS/` (`.step` and `.wrl`), found by file name
   in the model store, and rewrite the paths to `${KIPRJMOD}/EASYEDA_MODELS/<file>`: the project is then
   self-contained and light.
3. Missing files: find the supplier part number of the footprint in the symbol properties (supplier-part field)
   and fetch the part with `easyeda2kicad --full --lcsc_id=<id>`, run in the library folder; stop after three
   consecutive failures (the part service sometimes returns an unusable answer) instead of failing once per
   part.
4. **Pull**: for each footprint whose name exists in the central library, replace its model blocks, in the
   project `.pretty` and in every PCB instance, by those of the library (with the project path prefix). This
   restores offsets and rotations already validated.
5. Render both sides (step 4f). The designer adjusts what is wrong, by eye, in KiCad.
6. **Push**, footprint by footprint: copy the corrected block of the PCB instance into the central footprint of
   the same name. A bulk push rewrites every footprint of the project for a handful of real corrections: push only
   the corrected ones. A name-based push silently skips a footprint absent from the library under that name:
   create it first.

**Cases.**

- *Same part, other footprint name* (EasyEDA renames a footprint between revisions; the library knows a
  connector as "…-6PIN-…", the board uses "…-16PIN-…"): check pads and locating pegs are the same, copy the
  library `.kicad_mod` under the new name with its model block, then pull.
- *Model file expected under another name*: copy the equivalent model under the expected file name in the store
  and in the project; the footprint is not touched.
- *No model published for the exact part*: try the other part numbers of the same series (colour or packing
  variants share the body), or the stock KiCad model of the same package (same body size, pitch and thermal pad;
  check pin 1), then write the block by hand in the `.kicad_mod` (one tab deep) and in every PCB instance (two
  tabs deep).
- *Namesakes*: model files are stored under the EasyEDA model title, and two different parts can share a title
  (e.g. a top-view LED stored under the name of a side-view LED, of different heights). Compare the bounding box
  of the STEP with width, depth, height of the `3D Model Transform`.
- *Model sunk into the board*: a STEP whose body lies at z < 0 (e.g. a wire-to-board connector whose body spans
  below the board surface) disappears in KiCad, while EasyEDA re-seats it silently. Only the back-side render
  shows it.
- *Model centred in height* (chip capacitors, side-view LED): z offset = half the height.
- *Through-hole connector hanging under the board or sunk* (vertical USB-C, RJ45): the imported z is wrong for
  some STEPs (pitfall 37).

**Why nothing is guessed** (SKILL.md, working rules): a rotation deduced from the dimensions of a connector can be
wrong by 180°, and the STEP downloaded for a part may have other axes than the model EasyEDA displays. Push to the
central library only what has been seen right in 3D.

**Check of the tool**: break an offset on purpose in a copy of the project, pull, and see it come back.

## 8. Fabrication outputs for JLCPCB

One script (plain Python driving `kicad-cli`) writes everything into `<board>/fab/`; it fails rather than leave a
folder that looks ready.

1. **Origin**: the drill / placement origin (`(aux_axis_origin x y)` in `(setup`) must be the bottom-left corner
   of the outline, i.e. the minimum x and maximum y of the points of the top-level `gr_*` items on Edge.Cuts
   (KiCad's y axis points down; same frame as the EasyEDA exports). Warn beyond 0.01 mm.
2. **Gerbers**, zones refilled on the fly without modifying the board:
   `kicad-cli pcb export gerbers -o fab/gerber/ -l <F.Cu,In1.Cu,…,B.Cu>,F.Paste,B.Paste,F.Silkscreen,`
   `B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --use-drill-file-origin --check-zones <board>.kicad_pcb`
   (copper layers taken from the `(layers` block of the board).
3. **Drill**: `kicad-cli pcb export drill -o fab/gerber/ --format excellon --excellon-units mm`
   `--excellon-separate-th --drill-origin plot --generate-map --map-format gerberx2 <board>.kicad_pcb`.
4. **Archive** `<board>_gerber.zip`: only the files written by this run, whose modification time is later than
   the start of the export (a file left by an earlier run, for a layer since removed, is reported and left out);
   stop if top or bottom copper, either mask, the top silkscreen, the outline or a drill file is missing.
5. **BOM** `<board>_BOM_JLC.csv`, columns `Comment, Designator, Footprint, LCSC Part #`:
   `kicad-cli sch export bom --exclude-dnp --fields "Value,Reference,Footprint,<part field>" --labels`
   `"Comment,Designator,Footprint,LCSC" --group-by "Value,Footprint,<part field>" --ref-range-delimiter ""`.
   `<part field>` is the first symbol field present among `Supplier Part`, `LCSC`, `LCSC Part`, `LCSC Part #`,
   `JLCPCB Part #` (stop if none). Strip the library nickname from Footprint; list the designators without a
   part number. Not-fitted parts and parts excluded from the BOM are absent.
6. **Placement** `<board>_CPL_JLC.csv`, columns `Designator, Mid X, Mid Y, Layer, Rotation`:
   `kicad-cli pcb export pos --format csv --units mm --use-drill-file-origin --side both --exclude-dnp`; write
   positions as `<x>mm` with four decimals, Layer `Top` / `Bottom`, Rotation modulo 360. Not-fitted parts and
   parts excluded from position files are absent.
7. **Cross-check**: the set of designators of the BOM must equal that of the placement file; otherwise stop and
   list both differences.

**Rotations.** KiCad's rotations are usually JLC's when the footprints come from EasyEDA / LCSC (same zero
orientation as the JLC library): compare the BOM and placement files with the EasyEDA exports
(`pcb-export-fidelity`) and verify on the assembler's preview for each board. For a footprint taken from the stock
KiCad library, the zero orientation differs for some packages: check the assembly preview.
