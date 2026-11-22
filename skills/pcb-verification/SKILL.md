---
name: pcb-verification
description: "Design-review verification of a KiCad PCB before fabrication and EMC testing; entry point of the pcb-check-* skills: scoping with the designer, rigor rules, fail-loud toolchain, order of checks, reporting. Use to verify, review or qualify a board, answer a targeted question on one link, rail, port or part, or re-run checks after a revision."
---

# PCB verification: a design review by calculation and simulation

For each question: set the criterion from the datasheet or the standard, read the board as routed, compute the answer
with a small script for this board, report the verdict and the quantified effect separately.

It is a review, not a certification, and is worded as one (no certification vocabulary). "Pass" means "passes the stated
criterion, with the stated models and assumptions". What cannot be computed is listed as a measurement to make.

Each `pcb-check-*` skill covers one aspect of the board; its folder holds `SKILL.md`, with the shared modules it uses
under "Resources", `references/method.md` (formulas and conditions of each step under the same number or name, board
table, algorithm, validation cases, reporting) and `references/examples.md` (application cases, whose figures hold in
their own setting, and the other pitfalls).

The checks apply to any KiCad board; a board imported from EasyEDA Pro goes through `pcb-easyeda-import-cleanup` and
`pcb-export-fidelity` first. After the checks: `pcb-verification-report`. **A part, a memory type, an interface or
a standard named in a skill is the case its method was written for: do not assume it extends to another.**

## Resources
`lib/` holds the shared code, with no board data: the board scripts import it, never copy it. The KiCad modules state a **validated domain** and
raise `Unsupported` outside it: a check stops with a message, it never reports a number built on a geometry it does not
read correctly. `assets/` holds the `Makefile` skeleton (one target per check), `stackups/` (one
JSON per build) and `fabricators/` (one JSON per fabricator: finished copper, etch profile, solder mask, via plating);
the checks read their constants from these files and assert them: another fabricator or stackup is another file, not
another skill.

## Complete review or targeted question

| Request | Read | Produce |
|---|---|---|
| **Complete review** of a board | this file, `references/scoping.md`, then the skill of each check that applies | the workflow below, in full |
| **Targeted question** on one link, rail, port or part | the ten rules below, the skill of that check, the sections of its `method.md` that the question needs | the answer with its criterion and source, the script that computed it (in `<board>/verification/scripts/`, a target of the Makefile, so that the answer can be re-run after a change), and its scope: what was judged and what was not ("only this link is judged") |

A targeted question asks the designer only what its answer depends on (its criterion, its data, the part of the
scope that decides it) and states the rest as assumptions. Its answer covers what it lists, like any check, and
is never presented as a review of the board. After a change of the board it is re-run; when copper moved, the DRC
with parity too (`make check`): a pour cut can split a net that no check of the question reads.

## Order of the checks

Recommended order: sourcing (stock) → configuration → power rails → power input → impedance → layout audit → timing →
memory bus → clock integrity → crystals → voltage drop → thermal → isolation → surge / ESD → chassis grounding → port
network → conducted emissions → radiated emissions → derating. A check reads the results of those before it. Not every
check applies to every board: the scope decides.

**Before choosing, read `references/not-covered.md`**: what no check covers, and the simple checks to do by hand.

## Metric units only

mm, µm, mm², °C, g, Ω, A, V. Never mil, inch, oz of copper, °F, AWG, in answers, tables, reports, figures,
comments or variable names. A source in other units is converted when read (1 mil = 25.4 µm; 1 oz/ft² ≈ 35 µm)
and quoted in metric from then on. The only exception is the conversion constant itself in the code that reads
the source, or an API that imposes its unit.

## Workflow of a complete review

1. **Prepare**: board cleaned and under version control; decisions and criteria already settled for this board
   read in its `VERIFICATION.md`.
2. **Scope**: questionnaire to the designer (`references/scoping.md`, which also says how to work with the designer:
   their files, their decisions, their language), one grouped list with defaults to correct; answers in
   `VERIFICATION.md` ("Scope of use") and on the report cover. A missing answer is an explicit assumption and the
   verdict says "within this scope".
3. **Set up** `<board>/verification/` (`Makefile`, `scripts/`, `refs/`, `results/`, `stackups/`) and the shared
   library (`references/toolchain.md`). Archive every datasheet used in `refs/`, with its text extraction.
4. **Inventory before any calculation**: supplies, interfaces, clocks, connectors and barriers of the board, and
   for each the checks that apply, with their state (done, not done and why). A check that passes covers only
   what it listed: the inventory tells the reader which parts of the board nobody looked at. It goes at the head
   of `VERIFICATION.md` and of the report.
5. **First pass, coarse**: for each check that applies, the cheapest calculation that places it (a closed form,
   nominal values, a bound, one simulation of the case expected to be the worst), written with the functions of
   `lib/` in the script that a detailed study would extend. Each answer is a verdict with its base ("bound", "at
   nominal", "one simulated case"); it settles a topic only with a bound shown to be one or a margin that covers the
   uncertainties of its inputs (rule 7).
6. **Back to the designer before the long computations**: where the review stands, what was found with its figure,
   what looks critical and why, the readings and assumptions that decide a verdict, the detailed studies proposed
   with what each could change and its rough cost, and each deviation whose effect is negligible, with that effect,
   proposed for acceptance (pass * if the designer agrees). Then wait for the answers: a long computation on an
   assumption the designer could have corrected in one sentence is work lost.
7. **Refine** only the studies the designer keeps, in their order; the others keep their first-pass answer, written
   as such. Give each result to the designer when it is done and wait for the answer before the next study. A model
   that fails twice gives way to a simpler one that bounds the result, or the topic is incomplete with what is
   missing, and the designer is told.
8. **After any change to the board**: `make all`, compare with the previous results, explain every number that
   moved.
9. **Report**: update `VERIFICATION.md`; the structured results and a readable summary are the deliverable, the
   PDF (`pcb-verification-report`) is their presentation when one is wanted. For every unknown that decides a
   verdict, the measurement is specified: where to probe, in which conditions, with which instrument, and the
   value that means pass.

## Rigor, in ten rules

Each has its mechanism in `references/failure-modes.md`, whose section is given in brackets. With
`references/not-covered.md`, and `references/scoping.md` for a complete review, they are the reading required before
starting; a section of `failure-modes.md` is read when the review reaches its stage.

1. **The target is set before computing**, from the datasheet (section and page) or from a layout-guide rule
   judged applicable (`references/qualitative-rules.md`), and never blanked afterwards. For a standard, the report
   names the texts that may apply; the skills give indicative values commonly used in design, to be confirmed in
   the applicable edition, and a verdict that rests on one says "indicative"; a value is attributed to a clause
   only when it was read in that clause [1].
2. **The verdict is produced by a script**, every out-of-tolerance item listed with location and value; the
   tooling refuses a typed verdict [1].
3. **Two answers, never merged**: does it meet the rule, and what is the quantified effect; a rule not met is a
   fail even when the effect is nil [1].
4. **Criteria settled with the designer are coded as settled**; a changed verdict is explained before / after
   first; only the designer accepts a deviation [1].
5. **Know what the measurement measures**, one definition on every board, verified by a balance (length,
   current, power: every watt counted is attributed); the DRC only checks minima, fidelity is not compliance,
   the stackup is explicit [1, 2].
6. **Component models** are fitted on the published points at the current that matters, for the part on the
   BOM; a voltage that sits on a model's rating is the model clamping [2].
7. **A result has stopped moving under refinement**, everything else held fixed; a bound is justified or the condition
   that still holds the limit is reported; **listed is not judged**: every item ends judged or "not judged" with its
   reason. **Compute what the decision needs**: a bound or a light method first, with its error band, refined only near
   the threshold. A value that has not converged is never a verdict; it may be replaced by a bound that is shown to be
   one (a more severe geometry already computed, a closed form known to overestimate), written as such. The
   refinement check is run on the cases that carry a verdict, not on every case of a sweep [2].
8. **One tolerance policy, set once for the whole chain**; selection ranges are judged at nominal, physical
   quantities at the corners where the margin at nominal does not cover them [1, 3].
9. **The chain fails loudly**: no input silently skipped, the known correction applied in the code [3].
10. **A deviation is understood on a picture and the recommendation is complete**: cause, what is concerned,
    precise correction, quantified gain, verified under the stresses that decided the original verdict;
    rules of thumb are judged, not applied (`references/qualitative-rules.md`) [4].

## What a verdict means

| Verdict | Meaning |
|---|---|
| Pass | the criterion is met, no debate |
| Pass * | a deviation from the rule exists and the designer has accepted it, with its effect and a dated decision; or the verdict rests on a value the datasheet does not publish and the designer has accepted plausible values (partial data, only with a comfortable margin, or for a crystal that follows the IC manufacturer's recommendation: `pcb-check-crystal`); listed at the head of the report |
| Pass with reservation | the criterion passes, but an estimate or a point not yet arbitrated can flip it; or it misses its limit by less than the resolution of the inputs the value is computed from, the deviation carried by an estimate (a source assumed at 4 ns, the board adding 0.6 ps to a limit of 4 ns): such a deviation shows nothing, a larger one is a Fail |
| Fail | clear deviation from the rule, not arbitrated |
| To be measured | nothing calculable: only a measurement decides |
| Incomplete | a tooling state, not a sixth verdict class: a criterion that applies could not be judged (an input not declared, a geometry outside the validated domain of `lib/`); never shown as compliant, ranks just below Fail; the box says what is missing |

A deviation from a rule of caution can be acceptable: the review exists to avoid obvious defects before the tests,
and use and the tests have the last word. But only the designer accepts; the reviewer brings the cause, the
quantified effect and what would make the decision be reviewed.

**What a result looks like**: short answer first (what is good, what is not), then tables, then questions and
decisions for the designer; one line per rule (criterion and source, value found, verdict, quantified effect);
every number with its source or its assumption, estimates marked; for each deviation the cause, what is
concerned, the correction (net, position, value) and the gain, or "Nothing to do"; the measurements to make on the
prototype, each with the value that means pass.

## Keeping these skills alive

A new kind of mistake, or a conclusion the designer corrects, becomes a general rule in the "Pitfalls" of the check
concerned, or in `references/failure-modes.md` when it cuts across checks: in one place, with the condition under which
it holds; a board where it was met goes in `references/examples.md` as an application case.
