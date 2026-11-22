# Report: writing a chapter, drawing a figure, checking before delivery

## Contents
1. Files and installation in the board folder
2. Principle: every number comes from a calculation
3. Structure of the document
4. Writing a chapter
5. Figures
6. Check before delivery

## 1. Files and installation in the board folder

| File | Role | In the board |
|---|---|---|
| `report_base.py` | matplotlib style (palette constants `C1…C5`, `CRIT`, `INK`, `INK2`), language (`set_language`, `LANG`, `DEC_SEP`, `TEXTS`, coded messages `msg`, `_MSG`), `num`/`numg`/`pct`/`date_txt`/`axis_num`, `mm`, `svg`, `png_b64`, `legend_below`, `limit_line`, `load`, `git_info`, verdicts `OK/ACC/RES/NOK/MES/INC`, `verdict_threshold`, `accept`, `accept_estimate`, `worst`, `render` (jinja2 + Chrome), `check_pdf` (alerts + contact sheet) | copied as is |
| `report_base.html` | A4 page: styles, cover, summary, open points, annex; blocks `conclusion`, `tests`, `traceability`, `style` | copied as is |
| `report_macros.html` | `crit(objective, method, criterion)`, `figure(svg, caption)`, `map_img(src, caption)`, `verdict(v)` | copied as is |
| `report_board.py` | skeleton of the board's script (`FIXED`, one function per figure, summary, rendering) | → `report.py` |
| `report_board.html` | skeleton of the board's template (`extends`, one example chapter) | → `report_template.html` |

```
cd <board>/verification/scripts
cp <skill>/assets/report/report_{base.py,base.html,macros.html} .
cp <skill>/assets/report/report_board.py report.py
cp <skill>/assets/report/report_board.html report_template.html
../../../verification-lib/.venv/bin/python <skill>/assets/report/report_board.py --demo   # test of the base
```

**Language**: the fixed texts of the base (cover, summary, annex, verdict labels) exist in English and French in
`TEXTS`; the board script calls `set_language("en")` or `set_language("fr")` (labels, decimal separator, date
format). For another language, add an entry to `TEXTS`, and to `_MSG` when the report prints coded messages. The
chapters themselves are written in the designer's language in the board's template. **Texts produced by the
library modules** (derating deviations, flags and states, convergence reasons of a field study) are coded messages
(`lib/messages.py`): the board script stores `messages.records(...)` in its JSON (or the `Msg` themselves when it
renders directly), the template prints them with `{{ x|msg }}`, in the report's language with its decimal separator
and date format. A new message code is translated once in `report_base._MSG`, never by hand in a board's report.

## 2. Principle: every number comes from a calculation

- A script that only writes a `.txt` (e.g. a check script that prints its table) gets a `results/<script>.json`
  output. Waveforms: `results/spice/*.dat` (columns `t, v0, t, v1, …` of `wrdata` → `d[:, 2k+1]`).
- A sentence that summarises a table (`../../pcb-verification/references/failure-modes.md` § 4) carries its
  extremes, and the name of an extreme ("smallest margin: …") is drawn from the calculation
  (`dictsort(by='value')|first`). More generally, a figure **measured on the board** (length, ΔL, impedance, margin,
  list of the links concerned) is never typed in the template: only datasheet values and design choices are. No
  automatic check exists for it: figures typed by hand (a track width, a rail voltage, a capacitor value) usually
  coincide with some value of the results, so a search for them returns mostly noise; the text diff of the
  self-checks is the net.

## 3. Structure of the document

1. **Cover** (base): title and board, source of the design (e.g. EasyEDA .epro, KiCad project), state verified
   (`git_info`: hash, date, "+ uncommitted changes", **fingerprints of the schematic and the PCB**), stackup, date,
   reproduction command; sentence "Nature of the document" (`FIXED["nature"]` replaces the text of the base);
   **scope of use** (`FIXED["scope"]`): the verdicts only hold within this scope.
2. **Summary**: one line per test, its deciding criterion and the `worst()` of its criteria (the detail is in the
   chapter): table no. / test / criterion / numeric result / verdict, the marks E… of the estimates as
   superscripts on the number, the mark A… of an accepted deviation on the verdict (asterisk); the **Conclusion**
   box (block `conclusion`): blocking deviations or not, each deviation from the rule with its effect, each
   reservation and how to lift it; then the tables **Deviations accepted by the designer**
   (`FIXED["accepted_deviations"]`) and **Stated estimates and shortcuts** (`FIXED["estimates"]`).
3. **Open points**: subject / what / nature (prototype measurement, routing, software, documentary); then the
   optional table of recommendations for a board revision (`FIXED["recommendations"]`).
4. **One chapter per test** (block `tests`, one `<section class="test">` = new page), in the order of the checks
   recommended in `../../pcb-verification/SKILL.md` ("Order of the checks"), restricted to those the scope
   retained.
5. **Annex** (base + block `traceability`): assumptions and limits (`FIXED["assumptions"]`), traceability
   (notes of the import cleanup when the board was imported, scripts, VERIFICATION.md, datasheets of `refs/`); the
   full tables of sweeps and matrices (block `details`), referenced from their chapters.

## 4. Writing a chapter

```
<section class="test">
<h2>N. Title of the test</h2>
{{ crit("Objective.", "Method (tool, model, key assumptions).", "Numeric criterion (datasheet §, table).") }}
{{ figure(fig_x, "Fig. N-1 — What the figure shows and how to read it.") }}
<table>…numbers read from the JSON, |num(n)…</table>
<div class="box">{{ verdict(vd["N"]) }} — quantified effect, margin, condition, estimates involved (E…).</div>
</section>
```

- A chapter holds what its verdict rests on, in a page or two: the criterion, the figure and the cases that decide
  (the worst of each criterion, those near their limit); the rest of a sweep or a matrix goes to the annex.
- A rule not met with no effect is `NOK`, the effect in the box (e.g. a pair a few ohms outside its impedance
  tolerance whose computed return loss stays far above what the receiver needs).
- The box of a deviation or a reservation is actionable (`../../pcb-verification/references/failure-modes.md` § 4):
  the cause term by term in the budget table, the correction down to the file and line where it applies; a
  deviation accepted by the designer is written as such, with its date.
- A deviation of routing comes with its **view** (tracks by width, pads, out-of-tolerance points).
- Qualitative rules: table rule / mechanism and domain / numbers / decision
  (`../../pcb-verification/references/qualitative-rules.md`).
- Cell classes: `td.n` (right-aligned numbers), `.small` (sources), `.box` (verdict), `.box.v` (conclusion),
  `img.map` (tall image capped at 92 mm).
- Skeleton marks `<…>` are swallowed as HTML tags: write them `[…]`.

## 5. Figures

One function `fig_x(data) → svg(fig)` per figure, width `W` (170 mm; sizes in mm through `mm(width, height)`,
never in inches). Rules (the palette is the set of constants defined in `report_base.py`):
- categorical colours `C1…C5` in order, never recycled; `CRIT` (red) reserved for limits, through `limit_line()`;
- labels and text in `INK`/`INK2`, never in the colour of the series; selective labels;
- legend **under** the plot (`legend_below`); a single scale per axis (no dual axis);
- numbers in the format of the designer's language: `num(x, n)` in the labels, `axis_num(ax.xaxis, n)` for the
  ticks, separator set by `set_language()` (`DEC_SEP`);
- two curves two decades apart (with / without protection), or a reference curve decades above the board's curve,
  which it flattens: `set_yscale("symlog", linthresh=…)`;
- existing field map or render (PNG): `map_img(png_b64(path), caption)`; an image left by an older script may carry
  tick labels in another convention: re-plot from the JSON with the report's own code, or keep only an image with
  integer ticks;
- a sinc² spectrum plotted point by point falls into the nulls and zigzags: plot the envelope of the lobes;
- a limit drawn in dashes whose label is hidden by bars: put the limit in the title of the panel.
Figure types that fit the usual checks: stacked bars (consumption), sorted horizontal bars (drop per pad),
min–max ranges + median with tolerance band (impedances, in % of deviation from the target to put links of
different targets on the same axis), grouped bars with error bars (solver convergence), margin bars with limit
(timing), waveforms with input-threshold lines (clock), symlog waveforms on two panels (surge), bars per scenario
with limit (ground paths), spectrum with limit lines (emissions).

## 6. Check before delivery

`render()`, then `check_pdf(pdf, results/report)`:
- alerts: `nan` / `NaN` / `None` / `inf` / `Undefined` (a value lost in the data);
- contact sheet `results/report/verification_report_sheet.png`, looked at as the self-checks of `../SKILL.md` say,
  then the doubtful pages at 70 dpi (`pdftoppm -r 70 -f N -l N`);
