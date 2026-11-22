# Toolchain: what to install, how a board folder is laid out, how the chain is made to fail loudly

Written for KiCad 10.0.x. The programs are found through the variables below; the defaults written in the code are the
macOS application paths, and a program found on `PATH` is taken first where the code
looks for one.

## Programs
| Use | Program | Variable |
|---|---|---|
| ERC, DRC with schematic parity, Gerber / drill / netlist export, 3D render | `kicad-cli` (macOS: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`) | `KICAD_CLI` (Makefile, `check_nets.py`) |
| Reading the board from a script | KiCad's bundled Python, which provides the `pcbnew` module (macOS: `…/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`); filter `Fontconfig|assert` from its output | `KICAD_PY` (Makefile) |
| Computation and plots | a Python venv with numpy, scipy, matplotlib, jinja2, shapely, gerbonara, openpyxl, scikit-rf | `VENV_PY` (Makefile; default `<workspace>/verification-lib/.venv/bin/python`) |
| Circuit simulation | ngspice, on `PATH`; every netlist runs through `spice.run` (`lib/spice.py`) | — |
| PDF report | Chrome or Chromium (headless printing), poppler (`pdftotext`, `pdftoppm`) on `PATH` | `PCB_CHROME` (`report_base.py`; else `google-chrome`, `chromium`… on `PATH`, else the macOS application) |

Two interpreters, never mixed in one script: a script that reads the board runs with KiCad's Python and writes a
JSON; a script that computes runs with the venv and reads that JSON. The header of each script says which.
Anything that needs the network (catalogue lookup, datasheet download) runs with the venv: KiCad's bundled
Python may have no certificate store, in which case every HTTPS request fails.

The checks of a board are the targets of its `verification/Makefile`: `make all` runs them in order, `make <target>`
one. No bytecode folder in a board repository: the Makefile sets `PYTHONDONTWRITEBYTECODE`; run a script by hand
with `python -B`.

Datasheets: archive the PDF of the **part number on the BOM** in `refs/`, with its text extraction
(`pdftotext -layout`). A distributor's datasheet link often returns a web page that redirects to the PDF: follow
the redirection with a browser-like user agent and the distributor's site as referrer, then check that the
file starts with `%PDF`.

## Workspace
```
<workspace>/
  verification-lib/        link to pcb-verification/lib/ (or a copy, then re-copied at each change of the skills;
                           see README § Install), with the venv in .venv/
  <board>/                 one folder and one git repository per board
```
Board scripts reach the shared code with
`sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "verification-lib"))`.

Shared code (`pcb-verification/lib/`): what is hard to rewrite correctly and has no board data in it. Each check lists
the modules it uses under "Resources". Everything else (the board tables, budgets, netlists, audits, and the calls to the shared
functions) is written per board from the directives of each check.

## Board folder
```
<board>/  .gitignore  <board>.kicad_{pro,sch,pcb,dru,sym}  <board>.pretty/  fp-lib-table  sym-lib-table
  _pre_import_backup/   (imported board only) original import, source project file, before_<step>.* backups
  _cleanup/             (imported board only) step scripts, check_nets.py, reference_nets.json, README.md, ERC/DRC reports
  verification/
    Makefile            one target per check (skeleton: pcb-verification/assets/Makefile)
    scripts/            the board's scripts, one or two per check, + report.py and its template
    refs/               datasheets (PDF + .txt extracted with pdftotext), layout guides, standards excerpts
    results/            <script>.json, figures, spice/ waveforms; never edited by hand
    stackups/           stackup and fabricator files the scripts assert their constants against (copied from
                        pcb-verification/assets/stackups/ and assets/fabricators/: one JSON per build and
                        per fabricator, e.g. a production and a prototype build, one fabricator)
    VERIFICATION.md     scope of use, decisions and criteria settled (dated), results, open points
  fab/                  Gerber zip, BOM and pick-and-place for the assembler
```
Out of git: what can be regenerated (`verification/results/spice/`, KiCad's backups and locks, the configuration
copy `results/kicad_config/`); in git: the JSON the report reads, the report, `fab/` and the datasheets.

**Disk.** A waveform file (`.dat`) is an intermediate: kept only for the cases a figure of the report reads, never
for every case of a sweep. A matrix of cases reads its peaks with `.meas` (or reads the `.dat` and overwrites one
file) and stores the numbers in its JSON; a sweep kept as waveform files can reach gigabytes for numbers that fit
in a few megabytes of JSON. **A sweep starts from the case expected to be the worst**; a dimension is added only when
the result is near its limit or the designer asks, and the dimensions not run are written with their reason.
Measure the disk taken by `results/` and the venv at the end of a review and report it.

## Conventions of a board script
- A docstring that states the question, the models, the assumptions with their values, the criteria with their
  source.
- A **board table** at the top: nets, pads at the ends of each link, rails, datasheet constants (each with its source in
  a comment), each row naming the reference designator and the part number it was read for; the script asserts that part
  number against the board (MPN or supplier-part field) and stops when it differs. Component values are read from the
  PCB (Value field), not typed.
- One output: `results/<script>.json`, written at the end, with the inputs that decide the result next to the
  results. The report reads only these files.
- It fails rather than skip: pad not found, missing layer, balance not met. A simulation that does not converge is
  replaced by a simpler model that bounds the result, else the topic is incomplete with what is missing, and the
  review goes on. A refusal of a
  shared module (`kicad_copper.Unsupported`, or a `ValueError` of a function of `lib/`) is caught at the call of the
  module and written as the step's result (`messages.write_incomplete`), and the script exits 0: the following steps run
  and the report shows the chapter as INC with the message. Any other exception stops the run. The refused item is never
  removed, filtered or redrawn to obtain a number.

## Making the chain fail loudly
- `check` target: complete ERC/DRC reports, then failure on errors only. An ERC or DRC error on the board as
  received is a finding of the review, listed with its position: run the other targets by name and state on the cover that
  `check` fails; never lower a severity or add an exclusion in the designer's project to get past it. The DRC also runs
  on a scratch copy with the rule file of the fabricator of the scope (e.g.
  `pcb-easyeda-import-cleanup/assets/kicad_template/JLCPCB_35um.kicad_dru`): a violation there is a finding even when
  the project's own rules pass.
- Balance checks inside the scripts: injected current = requested current; sampled length = routed length;
  number of budget lines = number of expected nets.
- Parallel solvers: half the cores, one board at a time (each process holds its own mesh: measure the memory of one
  before choosing the count).
- After any change to the board: `make all`, then compare each JSON with its previous version, list every number
  that moved by more than 1 %, and explain each one before quoting anything.

## Typical commands
```
# Gerbers with the drill/place origin as reference
kicad-cli pcb export gerbers -o out/ -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --use-drill-file-origin board.kicad_pcb
kicad-cli pcb export drill -o out/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin plot board.kicad_pcb
# DRC with zone refill and parity (KiCad closed); KiCad open: work on a copy
kicad-cli pcb drc --refill-zones --save-board --schematic-parity --format json --severity-error --severity-warning --units mm -o drc.json board.kicad_pcb
kicad-cli sch erc --format json --severity-error --severity-warning -o erc.json board.kicad_sch   # positions in units of 100 mm
kicad-cli pcb render --side top|bottom|front --rotate "-45,0,30" --width 1400 --height 2000 --quality high -o r.png board.kicad_pcb
```

## pcbnew pitfalls (KiCad 10.0.x)
- Arc tracks are `PCB_ARC`, not `PCB_TRACK`: count the objects of each class before filtering on one.
- `zones.remove(z)` compares by value: filter by identity.
- `m.m_Filename = …` on `f.Models()` modifies a copy: edit the `(model …)` block as text.
- `FootprintLoad` returns an identifier without library: `SetFPID(LIB_ID(lib, name))`.
- `GetDrawings()` fails after a `Remove` of a track: collect the lists first.
- Net names come back as `wxString`: convert to `str` before sorting or using as keys.
- **A net name depends on how the schematic labels it.** A net named by a local label of the root sheet is
  `/NAME`; named by a global label or a power symbol it is `NAME`. A change of labelling therefore renames nets
  with no change of connectivity: net-class patterns written without a wildcard stop matching, and scripts that
  quote bare names find nothing. Make the check scripts independent of the choice: load the board through one
  helper that strips the root-sheet slash **in memory** (never before a save), and look a net up through a helper
  that tries both spellings — after an in-memory `SetNetname`, `FindNet` still answers to the old name only. Stop if
  both `NAME` and `/NAME` exist: those are two nets. Renaming the nets of the design files themselves belongs to
  `pcb-easyeda-import-cleanup`.
- **A scripted edit of a schematic is judged on the full netlist (names and pin groups), on a copy, never on the
  render.** A wire end that lands on another wire is a connection; a plain crossing of two perpendicular wires is
  not, so shortening a label stub can merge nets. Test every added wire against wires, pin ends, label anchors and
  junctions.
- Use the layer constants (`pcbnew.F_Cu`, `In1_Cu`…), never their numeric values, which differ between versions.
- Filled zones must be filled before reading them: refill with `kicad-cli pcb drc --refill-zones --save-board` on a
  copy, or `ZONE_FILLER` in the script. The `check` target proves it: it starts with `fills_check.py`,
  which runs `kicad_copper.fills_current` on a load of the board made for that purpose, with its .kicad_pro and
  .kicad_dru beside it (default rules refill differently); a stored fill whose shape differs from a refill by more
  than the filler's own noise (slivers under twice the arc approximation error) stops the run, and the designer
  refills and saves.
- KiCad open while a script writes the board: KiCad rewrites the files on exit and the change is lost.
  Check both the process and the lock files (`*.lck`): the project manager alone leaves only the project lock.
- After `board.Remove(obj)` or `footprint.Remove(obj)`, keep a Python reference to the removed object (a list is
  enough): otherwise later calls return unusable objects. Read `GetTracks()` once, before any change.
- A new footprint from an existing one: `Cast_to_FOOTPRINT(fp.Duplicate(False))`. The copy keeps the pin function
  and pin type of the donor's pads, and a type containing `no_connect` draws a cross on the pad: set both on every
  pad from the symbol (`SetPinFunction`, `SetPinType`), and read them back.
- Load the board from the project folder. From a backup folder the project rule file is not found (its name is
  the project's), zones are filled with other clearances and saving rewrites a project file.
- A script that moved copper refills the zones and saves (the DRC command above): otherwise the designer opens a
  board showing clearance errors between the stale fill and the new tracks.
- Editing the graphics of a footprint on the board (silkscreen trimmed, a mark moved) raises
  `lib_footprint_mismatch` on it, and "update footprint from library" undoes the edit: say both.

## Comparing with the previous results
Read the old version of a result with `git show HEAD:path/to/result.json` into a scratch folder.

## Modifying a block of the board by script
Editing a design is not the aim of a verification, but a proposal is often tried by script. Rules a script that
edits copper follows (the steps of a cleanup of an imported board are in `pcb-easyeda-import-cleanup`):
1. **Export every layer of the area before announcing that a placement fits**: tracks, vias, copper polygons and
   test points of all copper layers. Package outlines are not enough: a supply trunk on the opposite side forbids
   vias, and a net "of the block" may only be passing through to feed something else.
2. Choose vias by a check on each layer (hole-to-hole, via to track, pad clearances of the rule file).
3. Apply on a copy in a scratch folder first, run the DRC with parity and compare with a reference run made with
   the same rules: it finds what the study missed (copper polygons left on removed nets, a feed that went through
   removed vias).
4. Then the project file, KiCad closed, after a backup; one backup per kind of change (copper, silkscreen) so
   that one can be undone without the other.
5. A scripted edit is followed by a DRC in which the silkscreen and courtyard items are not ignored (a project may
   carry them as "ignore", e.g. `silk_over_copper`: run it on a copy with that severity raised to "warning"), with a
   before / after drawing. What matters is a reference mark lost on a neighbour's pad; outline overlaps are
   cosmetic.
6. Advice on how the KiCad interface behaves is tested (strings of the installed version, connectivity read on a
   copy) or given as untested. E.g. changing the net of a via that sits in a filled zone offers to rename every pad
   of that zone or to cancel; emptying the zones first (the via then touches no pad) is what works.
