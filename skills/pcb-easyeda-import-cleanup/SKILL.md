---
name: pcb-easyeda-import-cleanup
description: "Cleanup of an EasyEDA Pro project (.epro) imported into KiCad 10 into a clean, verifiable KiCad project fabricable at JLCPCB: libraries and 3D models, schematic repairs, test points, zones, design rules, stackup, net classes, schematic-PCB re-linking; re-import of a later revision of a cleaned board."
---

# Cleanup of an EasyEDA Pro import (EasyEDA Pro → KiCad 10 → JLCPCB)

An EasyEDA Pro project imported into KiCad looks right and is not: it carries the copper EasyEDA computed, and nothing
shows until the zones are refilled and the ERC is run. Done when the ERC, the DRC and the schematic parity are clean,
the fabrication outputs equal what EasyEDA would have produced, and a later revision can be re-imported by the same
scripts.

Scope: EasyEDA Pro (`.epro`) projects imported by KiCad 10 (method checked on 10.0.4), fabricated at JLCPCB. The
rule file covers 2- and 4-layer builds; the inner-layer handling of the steps and scripts (layer numbers, layer
lists, plane rules) is written for 4-layer boards and is adapted for any other layer count.

The step scripts are **written for each board** from the directives of `cleanup-steps.md`: they hold board data
(reference designators, nets, diameters) and are short once the four kept scripts are imported.

Next skills: `pcb-export-fidelity` (KiCad outputs = EasyEDA exports), then `pcb-verification`.

## Resources
- `references/cleanup-steps.md`: per step, what the import leaves wrong, what to do, how to script it, what makes
  it re-runnable and what proves it; inventory; re-import of a revision and its helpers; measured EasyEDA
  conventions; 3D models; fabrication outputs for JLCPCB;
- `references/import-cleanup-guide.md`: the numbered pitfalls (cited as "pitfall N") and their background;
- `scripts/`: four generic scripts, imported or copied, never rewritten: `check_nets.py` (connectivity compared with the
  reference group by group, independent of names), `sexp.py` (S-expression blocks located in the text, quoted strings
  respected), `pins.py` (pin positions of placed symbols), `easyeda_junctions.py` (junctions lost at cross nodes);
- `assets/kicad_template/`: JLCPCB rule file (`JLCPCB_35um.kicad_dru`, 2-layer values, multilayer ones in comments),
  `template.kicad_pro`
  (Board Setup, severities), `apply_zone_settings.py`, and a `README.md` on where each setting lives and on rule
  priority;
- `assets/kicad_dru/`: `thermal_pad_paste.kicad_dru`.

## Units

Metric only (`pcb-verification`, "Metric units only"); EasyEDA units and their conversion:
`references/cleanup-steps.md`, section 6.

## Working rules with the designer

- **Language and conventions** of the user (decimal separator, dates, trade vocabulary).
- **Do not modify their design files without saying so.** Backup before every step that touches copper
  (`_pre_import_backup/before_<step>.*`) and git (first commit = raw import).
- **KiCad closed** while a script writes (no `*.lck` in the board folder, no KiCad process): it rewrites the PCB,
  the project and its local settings on exit. KiCad open → reads only, on a copy. KiCad closed and reloaded
  between a script and an Update PCB from Schematic.
- **Never delete permanently**: move to the trash.
- **An import artefact is found by comparing like with like** (pitfalls 3, 32): the raw import against the raw
  import of the previous revision or of another board, the KiCad Gerber against the EasyEDA Gerber, after a
  refill. A comparison with a board cleaned by hand proves nothing.
- **Do not guess a 3D rotation or offset**: render, show, ask. The designer adjusts by eye; the setting then goes,
  footprint by footprint, into a central footprint / 3D library if the designer keeps one
  (`references/cleanup-steps.md`, section 7).
- **Controlled-impedance widths are asked of the designer** (the figures of their impedance calculator) when the
  import does not give them or they look uncertain, not derived from an ideal computation (step 4).
- **A DRC exception targets one component, with a comment**; a global rule is never relaxed (step 4b).
- Commits only on request, or when a git repository for the board has been requested (the preparation step below
  assumes that agreement; without it, keep the raw import as a dated copy in `_pre_import_backup/`); messages in
  their language.
- **EasyEDA remains the source of the design**: anything done only in KiCad disappears at the next re-import. Say
  so, and ask what must be carried back into EasyEDA (net-class widths, part changes).

## Workflow

### 0. Preparation
1. Obtain the `.epro` from the designer and, when there are several exports, confirm which is the current revision
   (file date and time). Ask at the same time for the fabrication exports **of that same revision** (Gerber,
   BOM, pick-and-place): the fidelity check needs them and they settle what the import cannot (real pour
   clearance, thermal spokes, drill diameters, late renamings).
2. `git init` in the board folder, `.gitignore` (`*-backups/`, `*.lck`, `_autosave-*`, `fp-info-cache`,
   `.DS_Store`, `__pycache__/`, the staging folder of a re-import, bulky simulation outputs), **commit of the raw
   import**.
3. Copy the `.epro` and the raw import (`.kicad_pcb`, `.kicad_pro`, `.kicad_sch`, `.kicad_sym`) into
   `_pre_import_backup/`; unzip the `.epro` in a scratch folder to read `.epcb`, `.esch` and `project.json`
   (rules, pours, solid fills, 3D transforms, flags).
4. Re-read the pitfalls of `references/import-cleanup-guide.md`.

### 1. Inventory, then the steps
Inventory first (`references/cleanup-steps.md`, section 2): it decides which steps apply and fills the board tables of
the scripts. Then the steps in the order of section 3, one script per step, **`check_nets.py` after every step**, ERC
/ DRC counts kept.

### 2. Fidelity (skill `pcb-export-fidelity`)
KiCad Gerber, drill, BOM and placement against the EasyEDA exports of the same revision. Every remaining
difference is **explained** or fixed (step 5).

### 3. Closing
Final ERC and DRC reports kept in `_cleanup/`; README of `_cleanup/`: one line per step (what its script printed),
the deliberate differences with EasyEDA, each DRC exception and why, the state reached; fabrication outputs for
JLCPCB (`references/cleanup-steps.md`, section 8); commit if asked.

A cleaned board: ERC 0 errors; DRC 0 errors, 0 unconnected, parity 0, each remaining warning explained
(`references/import-cleanup-guide.md`, "What remains and is normal"); connectivity identical to the import apart
from the declared merges; every footprint linked to its symbol; poured areas close to EasyEDA's and every Gerber
difference with EasyEDA explained (e.g. a hole that EasyEDA had not subtracted from a pour).

## Re-import of a revision

Procedure: `references/cleanup-steps.md`, section 5. The new cleaned board differs from the old one only by the
designer's changes, and from the new exports by the same differences as at the previous import; it is merged only after
the designer validates.

## Enriching this skill

At the end of a board, or after a correction by the designer: a new import pitfall goes into
`references/import-cleanup-guide.md` under the next number, as a general rule (symptom, cause, fix; no date, no
count of boards, no board or part name that identifies a product, in any file); if it changes how a step is
scripted or proven, update the step in `references/cleanup-steps.md`. Keep this file short.
