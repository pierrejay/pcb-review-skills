---
name: pcb-verification-report
description: "PDF verification report of a PCB design review, written or regenerated once the checks are done: one chapter per test with sourced criterion, figures and a computed verdict separating compliance with the rule from the quantified effect; scope of use and stated estimates on the cover; automatic check of the PDF."
---

# PDF verification report

Read `../pcb-verification/SKILL.md` first.

## Resources
- `assets/report/`: the base and the two board skeletons, whose texts and demo data are placeholders (files and their
  names in the board: `references/method.md` § 1);
- `../pcb-verification/lib/messages.py`: coded messages, rendered in the designer's language.

## Purpose
A document readable outside the session (the designer, a reviewer, a client) that gives for each test the
objective, the method, the sourced criterion, the curves, and a verdict that separates **compliance with the
rule** and **quantified effect**. It presents the review (`../pcb-verification/SKILL.md`, workflow step 9); the
consistency checks of the base (stale results, reservations without an estimate, accepted deviations without a
decision) are worth running even when no PDF is wanted.

**Nature**: a design review, which can also support a self-assessment if its sources and models are valid. A
sentence on the cover says it is not a compliance test (`TEXTS["nature"]` of the base, or `FIXED["nature"]`); after
that, "Pass" is written without contortion, and no certification vocabulary is used ("not demonstrated", a triple
status result / proof / decision).

## When it applies
When the checks of a board are done and a report is requested, or must be regenerated after a change of the
board, of a script or of the base.

## Inputs to obtain
- `results/*.json` of every check (the report reads nothing else), with the waveforms in `results/spice/`.
- The board's `VERIFICATION.md`: scope of use, decisions dated, criteria settled, open points.
- Data without a calculation, each with its source (datasheet, §, table): straps read, datasheet consumptions,
  clock specifications, assumptions, estimates, accepted deviations.
- The designer's language (English and French are in the base; another one: `references/method.md` § 1).

## Method
§: the sections of `references/method.md`.
1. **Install the base** in `<board>/verification/scripts/` (§ 1); test with `report.py --demo`. The base is copied so
   that the board stays self-contained and reproducible from git; fix the base in the skill, never in a board, then copy
   it again (constant `VERSION`).
2. **Produce the results with the board's Makefile** (`make all`), the report as its last target.
3. **Compute every verdict** in `report.py`: `verdict_threshold(value, limit, "max"|"min", reserve=…)` per
   criterion (`resolution=` when the value misses its limit by less than the resolution of its inputs, below;
   `screening=` when the limit is a screening value and not the part's withstand: to be measured above it),
   combined by `worst()` when a test has several (setup **and** hold, voltage **and** current);
   `accept(NOK, mark, test, value)` for a deviation the designer accepted, `accept_estimate(RES, mark, test, value)`
   for partial data the designer accepted (below), `value` being the result the decision was taken on, rounded as
   the finding prints it. The summary is the single source: a chapter displays `verdict(vd["n"])`.
4. **Fill `FIXED`** (§ 3 says where each entry appears): board, title, source, stackup, reproduction command,
   `scope` (requirement, value, status "declared (date)" / "assumption"), `estimates` (mark, subject, value, basis,
   tests, how to confirm; a basis is a neighbouring part, a qualification level, a typical value with margin or the
   designer's own measurement), `accepted_deviations` (mark, tests, rule, finding, effect, dated decision, to be
   reviewed if, {test: value accepted}),
   `open_points`, `assumptions`, `nature` if the default text is replaced; optional `recommendations` (where, now,
   recommended, computed gain): improvements without verdict, such as the decoupling rows of
   `pcb-check-configuration` step 6c.
5. **Write the chapters** in the board's template (§ 4), one `<section class="test">` per test, in the order of § 3:
   criterion, figure(s), table of numbers read from the JSON, verdict box = compliance with the rule, then the
   quantified effect.
6. **Figures** (§ 5): one function per figure, data as argument, returning `svg(fig)`.
7. **Render and check** (§ 6): `render()`, then `check_pdf()` and the contact sheet, looked at.
8. **Deliver**: commit of the scripts, regeneration, commit of the PDF (the cover then quotes the commit of the
   scripts, with no mention of a change); the PDF, a summary per chapter, the regeneration command, the commit.

## Criteria
What the base enforces, and what it cannot:

| Rule | Enforced by |
|---|---|
| A chapter displays the verdict of its summary line, one source for both; a verdict typed in a template fails the rendering, whatever its spelling | `render()`: `verdict()` displays only a verdict drawn from the summary; `OK`, `NOK`… only compare |
| A missing or non-finite value gives no verdict | `verdict_threshold` raises |
| A reservation cites an estimate of `FIXED["estimates"]`, and every reservation mark exists | `render()` |
| An accepted deviation is listed, applied with `accept()` for that test on the value it was decided for, and still a deviation; accepted partial data is listed, applied with `accept_estimate()` on its value, and still rests on an estimate | `render()`, `accept()` and `accept_estimate()` raise otherwise |
| A variable absent from the context fails the rendering | `StrictUndefined` |
| No `nan` / `None` / `inf` in the delivered text (a value lost in the data) | `check_pdf()` |
| Every number in the format of the report's language, in metric units | the author: every value through `|num` / `|numg`, units written once in the template |
| Summary sentences are generated from the tables; texts describing the board are re-read at each regeneration; the cover carries the fingerprints of the files verified | the author (the base gives `git_info` and the statistics) |

Whether a verdict is computed is decided in the Python summary, not by the template: each one comes from
`verdict_threshold` / `worst` / `accept` / `accept_estimate` on the result and its criterion, and that is where it is
reviewed.

## Verdicts
The five verdicts and the tooling state `INC` of `../pcb-verification/SKILL.md` ("What a verdict means") are the
constants `OK` (✔ Pass / Conforme), `ACC` (✔ Pass * / Conforme *, through `accept(NOK, "A1", "19", 5.5)` or
`accept_estimate(RES, …)`), `RES` (▲ Pass with reservation / Conforme avec réserve, through `reserve="E…"`), `NOK` (✖
Fail / Non conforme), `MES` (◷ To be measured / À mesurer) and `INC` (◌ Incomplete / Incomplet, ranked just below `NOK`
by `worst()`; a step that wrote a refusal instead of its result gives it through `incomplete(result)`, the message
printed in the chapter). Always icon + label, never colour alone.

**Deviation within the resolution.** A value that misses its limit by less than the resolution of the least
precise input it is computed from (a rise time stated to 0.1 ns, a curve read to 5 %) shows no deviation: with the
estimate that carries it, `verdict_threshold(value, limit, sense, reserve="E…", resolution=…)` gives `RES`, the action
listed being to measure or to obtain the value. The resolution is that of the inputs, stated in the chapter, not a
margin: a deviation larger than it stays `NOK`. Rounding the value to make it pass is not the way: the value is
printed as computed.

**Partial data.** When a datasheet does not publish a value (e.g. the output stage of an oscillator, the motional
capacitance of a crystal, the injected current a pin withstands), the designer may take plausible values and accept
the risk of declaring the test passed: `accept_estimate(RES, mark, test, value)` gives `ACC` (Pass *), listed with the
accepted deviations ("partial data: …", the values taken, the margin they give, the dated decision, the measurement
or the published value that would reopen it). The reviewer proposes it only when the margin is comfortable with
sensible defaults, or for a crystal when the board follows the IC manufacturer's recommendation
(`pcb-check-crystal`, "Unpublished C0 min and C1"); if those defaults give a tight or meaningless result, the
reservation stays, or the test is to be measured. A capacitance that enters a computation and was not read on the
curve of the exact part (typical fraction or curve, the curve of an equivalent part when its manufacturer publishes
none) is an estimate of `FIXED["estimates"]`: when it decides the verdict, the verdict is a reservation, and the
action listed is to obtain the curve or to measure. The marked value is not an estimate of it. Decoupling and bulk
judged only against the manufacturer's recommendation, with a part that resembles the qualified one, compare at
nominal and need no curve (`pcb-verification/references/failure-modes.md`).

## Self-checks
- `report.py --demo` renders after any change of the base.
- `render()` passes.
- `check_pdf()`: alerts read one by one; the contact sheet **looked at** (orphan heading, box alone at the top
  of a page, figure too tall pushing its table, legend on a curve, overlapping labels), then the doubtful pages at
  70 dpi.
- At each regeneration after a change: `pdftotext -layout` before / after and `diff`. A table that moved while the
  sentence under it did not is a hard-coded figure; after a migration or a change of the base, only the intended
  corrections appear.
- At each regeneration after a change to the board: every text that describes its state re-read, and the written
  texts (conclusion, quantified-effect boxes) re-read where a result changed meaning; the designer is told so.

## Tool contract
- `report.py` (venv: matplotlib, numpy, jinja2; Chrome or Chromium and poppler, located as in
  `../pcb-verification/references/toolchain.md`): reads `results/*.json` through `load(R, name)` only; writes
  `results/report/verification_report.html`, `verification/verification_report.pdf`, the contact sheet
  `results/report/verification_report_sheet.png`; prints pages and alerts.
- `report_template.html`: `{% extends "report_base.html" %}`, blocks `conclusion`, `tests`, `traceability`;
  macros `crit`, `figure`, `map_img`, `verdict` from `report_macros.html`; filters `num(n)`, `numg`, `pct`, `msg` (coded
  messages of the modules in the report's language).
- Makefile: the `report` target, last (skeleton `../pcb-verification/assets/Makefile`).
- **Refusals**: the functions of the base refuse their inputs themselves (Criteria above).

## Pitfalls
- **A module's message inserted as text** (`{{ row.flags[0] }}`) prints English, ISO dates and four decimals in a
  report in another language: store `messages.records(...)` and print `|msg` (`references/method.md` § 1).
- **A value inserted without a filter** (`{{ F.ldo.vin_max }}`, a dictionary key such as `"0.12"`) prints the wrong
  decimal separator in a comma-decimal report: `|num(n)`, `|numg`, or `|replace('.', DEC_SEP)` on a string; a list
  of values is separated by "/", not ",".

## Limits
`check_pdf()` reads the text of the PDF only: a
tick label inside a PNG image escapes it (`references/method.md` § 5). Headless Chrome can hang at printing: kill it
and run again.
