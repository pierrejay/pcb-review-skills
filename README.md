# pcb-review-skills

Agent skills for reviewing a PCB before it is fabricated and tested: bringing an EasyEDA Pro design into KiCad, then
verifying the design by calculation and simulation. It is a design review, not a certification: "pass" means "passes
the stated criterion", every estimate is listed, every verdict is computed, every computed quantity is taken at its
tolerance corners where the margin at nominal does not cover them.

## Structure

Four skills are entry points:
- `pcb-easyeda-import-cleanup`: an EasyEDA Pro import turned into a clean KiCad project, and the re-import of a later
  revision;
- `pcb-export-fidelity`: proof that KiCad fabricates the same board as the EasyEDA exports;
- `pcb-verification`: the verification itself (scoping with the designer, rigor rules, toolchain, order of the
  checks);
- `pcb-verification-report`: the PDF report, with computed verdicts.

The `pcb-check-*` skills are the resources of `pcb-verification`, one per aspect of the board. They cover:
- configuration: straps, addresses, modes, interface wiring;
- power: rails, input protection and filtering, DC drop in the copper;
- thermal;
- signal integrity: impedance, layout rules, timing, memory bus, clocks, crystals, port networks;
- protection: surge, ESD, fast transients, chassis grounding, isolation barriers;
- EMC pre-estimates: conducted and radiated emissions;
- components: derating and sourcing.

The name of a skill says what it checks, and its `description` says when to use it. In each skill folder, `SKILL.md`
is the check; `references/method.md` holds its formulas and algorithm, and `references/examples.md`
its application cases and the other pitfalls.

`skills/pcb-verification/lib/` holds the code shared by the checks, with no board data. Each skill lists the modules
it uses under "Resources". The scripts
that read a board are written per board, from the skill.

What no check covers yet is listed in `skills/pcb-verification/references/not-covered.md`.

## Install

Each skill is a folder with a `SKILL.md` (front matter `name` and `description`, then the instructions). An agent
that supports skills loads them from its skills directory; any other agent can be pointed at the `SKILL.md` files.

1. Link (or copy) every folder of `skills/` into the agent's skills directory, user-wide or per project. Linking
   keeps this repository the single source. Do not overwrite an existing entry of the same name: report it.
2. In the workspace that holds the boards, link `skills/pcb-verification/lib` as `verification-lib`: the board
   scripts import it from there.
3. Create a Python venv outside the repository (or in `verification-lib/.venv`, git-ignored) with numpy, scipy,
   matplotlib, jinja2, shapely, gerbonara, openpyxl and scikit-rf.

Requirements: KiCad 10 (`kicad-cli` and its bundled Python with `pcbnew`), ngspice, poppler, Chrome or Chromium for
the PDF report. Programs are located through `KICAD_CLI`, `KICAD_PY`, `VENV_PY` and `PCB_CHROME`, with the macOS
application paths as defaults (`skills/pcb-verification/references/toolchain.md`, "Programs"). Validated with KiCad
10.0.x on macOS and ngspice; code that uses `pcbnew` must be re-validated on another version.

## License

MIT, see `LICENSE`.
