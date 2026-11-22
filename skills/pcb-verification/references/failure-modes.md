# Failure modes of a design review, and the rule that prevents each

Each rule prevents a mistake a review can make (a wrong verdict, a recommendation built as written that turns out
harmful, a report that contradicts its own tables) and is followed by its mechanism or its symptom. The rules are
grouped by the stage where the mistake is made, and the ten rules of `pcb-verification` summarise them: read a
section when the review reaches its stage. Rules specific to one check are in its skill ("Pitfalls"); a new kind of
mistake that cuts across checks is added here.

## 1. Criteria and verdicts

- **Set the target before computing**, from the datasheet or the layout guide, and never blank it afterwards. A
  target replaced or removed once the result is known drifts towards the result: the deviation becomes "within
  tolerance", or a dash in the summary called harmless.
- **Every verdict is computed by a script, and the tooling refuses a typed one.** A typed verdict stays as typed when
  the numbers change; a rule with no automatic check is applied only while someone remembers it.
- **Compliance with the rule and quantified effect are two answers.** A rule not met is a fail even when the effect
  is nil; the effect goes in the comment. Softened into a reservation, the deviation is hidden from the person who
  decides whether to accept it.
- **Criteria settled with the designer are coded exactly as settled.** A changed verdict is first shown in a before /
  after table (value, criterion or scope), and the designer decides before the report is touched. A threshold
  re-coded more severely flips verdicts with identical values, and a report rewritten to match hides whether the
  board or the criterion changed.
- **Only the designer accepts a deviation, and an acceptance never outlives its object.** The reviewer brings the
  cause, the quantified effect and what would reopen the decision; the accepted deviation stays written at the head
  of the report; the tooling refuses an acceptance whose deviation has gone. Otherwise a reviewer's note closes the
  designer's question without comparison with the rule, or an old acceptance vouches for something no longer there.
- **A reservation you can lift yourself is not a reservation.** Find the datasheet, read it, archive it, conclude;
  judge at the pessimistic bound of an estimate, and if it still passes, the verdict is a plain pass. A needless
  reservation makes a pass look doubtful and sends the designer to answer a question already answered.
- **An in-house threshold is labelled in-house, aims at outliers, and is judged on the links it targets.** Presented
  as a datasheet rule, it is contested on a point of fact and the report loses credibility; a rule for fast links
  applied to slow ones (e.g. management buses) lists links it was never meant for, and the real outliers disappear.
- **A per-component datasheet range is brought back to the quantity the circuit sees.** Two ranges of one application
  table that add on one node are neither contradictory nor judged part by part: the IC sees their sum.
- **A conclusion drawn from one case keeps its conditions** (component, frequency, kind of disturbance, edition and
  note of a standard); a value attributed to a standard is indicative unless read in the applicable edition. E.g.
  "di/dt is bounded by the leakage inductance behind a common-mode choke" holds for microsecond surges, not for
  nanosecond ESD edges.
- **Selection range and physical quantity are two kinds of criteria.** A *selection range* recommended by a datasheet
  ("an inductance between x and y", a capacitor tabulated per resistor value, a cell of an L/C table) says which
  part to buy and is judged on the part's **nominal** value: a convention of the review, written in the report,
  since a datasheet rarely says whether its range covers the part's tolerance (when it says so, follow it). A
  *physical quantity* computed from the parts (a voltage, a time, a current, a margin) is judged at the **tolerance
  corners**. Corners never apply to a selection range, unless the datasheet states it as an effective value (e.g. a
  capacitance given "−50 / +20 % anticipated": then the range of the effective value at the corners must fit). A
  check that does both says which line is which: corners on a selection range fail the part the datasheet names;
  nominal values on a computed quantity hide the case that decides.
- **The DRC only checks minima, and fidelity is not compliance.** Compare the routed width with the width the net
  class intends: a pair routed wider respects every minimum and misses its impedance. DRC, schematic parity and a
  clean Gerber diff prove the copy of a design, not its routing.
- **The stackup is explicit in every verdict.** The same geometry moves by +19 to +42 % between two four-layer builds
  with 0.10 and 0.21 mm of prepreg (`pcb-check-impedance`, method, validation table): a pass on one build can be a fail
  on the other, and a verdict without its stackup cannot be reproduced.

## 2. Measurements and models

- **One definition of each measurement, the same in every check and on every board** (the signal path, pad to pad).
  Net length is not path length, a protection stub is not the line, a via clearance is not a plane cutout, a result
  depends on mesh convergence: each confusion gives a wrong verdict with no message, and two checks that measure one
  object differently contradict each other. A path clearly shorter than its net's copper is looked at before use (on
  one line with no stub the two agree within the pad entries); an improvement made in one script is carried to the
  others.
- **A geometry extraction is verified by a balance** (extracted length = routed length), and object classes are
  counted before filtering on one. A class the extraction does not enumerate (arcs taken for straight tracks, or
  ignored) vanishes from every script that shares the filter: short lengths, a partner absent opposite a meander,
  paths not found. Only a balance shows the loss.
- **Record the design intent, and look at a drawing of the run before writing "to be fixed".** Otherwise a structure
  built on purpose (a pair without a plane) is computed as if it had the usual one and set aside as "indicative",
  or a leg is called uncoupled because the extraction missed the partner's track a fraction of a millimetre away,
  and the designer is asked to fix what is not wrong.
- **A simulated voltage exactly at a component's rating is the model clamping**, not a margin. Redo without the
  breakdown and read the current and energy in the clamp (e.g. a series diode avalanching at a current far above
  its rating); check both polarities. Read as "at its limit", it leads to a part change recommended on an artefact.
- **A component model is verified by a DC run at the published points, and models the part on the BOM**; clamping is
  taken at the current actually seen. A model fitted on the maximum values clamps off the datasheet; a run with
  another part than the one fitted, or a discrete part and an array under different models, judges the model, not
  the part.
- **A rail that moves while it is off the current path is a model artefact**: understand it before writing it. A
  lossless element in a ground or return path sustains a resonance or a DC offset that no real circuit has, and an
  unrelated analogue rail moves by volts.
- **Cross-check a new result by an independent method before announcing it** (closed form, hand calculation),
  re-read your own parameters and units, and re-check your own corrections the same way. A wrong unit (a factor 1000
  on a per-length quantity), two thicknesses swapped in a conversion or a convergence test coarser than the default
  all give plausible numbers; two field calculators can differ by tens of percent on one geometry because their
  copper models differ.
- **A numerical result is a result only once it has stopped moving under refinement**, everything else held fixed:
  hold the reading point fixed, halve the mesh or the time step, and require the successive differences to shrink
  geometrically, at a ratio the tool states. A value that keeps moving is "not converged", never "x ± something".
  When the reading point moves closer to a surface at each refinement, the values drift together and look
  converged, while at a fixed distance the calculation converges elsewhere. A peak at a sharp corner (a field, a
  stress at a notch, a current density, the temperature of a point source) has no limit and is replaced by a
  quantity read at a fixed distance.
- **A budget is an inventory: every unit counted is attributed** (power entering = power placed + power explicitly
  spread + power explicitly leaving, checked from the source side). A share attributed to no part is injected short;
  the solver's own energy balance stays perfect because it only sees what it was given, and the missing share can
  shift a temperature or a drop by as much as the margin claimed.
- **Listed is not judged.** Every item a check walks ends judged against a criterion, or not judged with its reason,
  and the counts per state are in the result; "0 deviations" is read with the number of items judged. Otherwise the
  items that cannot be judged (no declared current, an array of unknown family) are skipped silently, and the parts
  most likely to deviate were never compared.
- **The interface cases a skill lists are examples, not the scope: every IC gets its supply table** (each supply,
  regulator and reference pin, the parts on it and the net at their far end, by script), compared with the
  application diagram and the evaluation board of that IC. Without it, a capacitor that the datasheet returns to a
  supply rail can sit on ground unnoticed, found back only through an unrelated flag.
- **Nothing is filed as "minor" without its computed effect, and a free improvement is proposed with its gain** (a
  recommendation, not a fail): a pin noted "minor" can hide a resonance and a remedy in the same footprint.
- **A capacitance that enters a computation is its effective value on the curve of the exact part**, a constant read
  at the voltage of the case: the operating voltage in steady state (ripple, filter, resonance, hold-up); in a
  transient (surge, ESD, hot-plug), the operating voltage first, then, when the margin is small, the voltage the first
  run reached, the result saying which. Not the marked value nor a typical fraction: a 10 µF 50 V 0805 X5R keeps
  2.8 µF at 12 V and 1.4 µF at 24 V on its curve, where a typical estimate gave 6 and 3.5 µF. Without the curve, the
  verdict that depends on it is a reservation, and the action is to obtain the curve.
- **A part whose manufacturer publishes no C(V) curve takes the curve of an equivalent part** (same dielectric, rated
  voltage and value, same case or the nearest), an estimate of `FIXED["estimates"]`; a larger case keeps more of its
  value, so its curve is optimistic.
- **Decoupling and bulk judged only against the IC manufacturer's recommendation compare at nominal**, when the
  fitted part resembles the one it qualified (dielectric, rated voltage, case: its evaluation board BOM): the
  reference design shows that the circuit works with that part. A smaller case or a lower rating loses much more
  (a 10 µF class-2 0402 rated 6.3 V keeps about a third of its value at 3.3 V, `mlcc_bias.X5R_TYPICAL_FRACTION`;
  an 0805 50 V in place of a 1206 or 1210): compare effective values then. A manufacturer that specifies an
  effective capacitance (a range under bias) is compared in effective values.
- **Values are read, not assumed**: component values from the PCB, software configuration from the firmware source.
  A typed value outlives its change on the board; an assumed bus clock or mode gives the margin of a configuration
  that does not exist, possibly negative at the real one.
- **Another port can be the return path**, not only the supply and the chassis. With a floating host and a bus
  earthed elsewhere, the surge or ESD current of one port can return through the coupling capacitors of another and
  overstress them.
- **Compute what the decision needs, and no more.** Start with a bound or a light method whose error band is known (a
  closed form, a coarse mesh with Richardson extrapolation, a value per volt from a more severe geometry); stop when
  the margin holds at the pessimistic end of the band; refine only the items near a threshold, to a convergence
  target set by the uncertainty of the data (etching and permittivity move an impedance by 5–10 %; a laminate
  strength is measured in a near-uniform field). A solver pushed to 0.1 % on a quantity known to 5 % costs hours and
  gigabytes, and the cost pushes the reviewer to skip the cases that matter; a light method used near a threshold
  without its error band gives a verdict it cannot support. A value that does not converge is never a verdict; it
  may be replaced by a bound shown to be one, written as such.
- **An unpublished datum is estimated openly**, both bounds side by side, the verdict at the pessimistic one;
  otherwise the calculation is abandoned, or an estimate decides a verdict silently.
- **A scenario is not a bound.** State why a "worst case" covers the scope, or keep the maximum of the scenarios and
  report the condition that holds the limit. A linear inductor called "upper bound" is exceeded by its saturable
  model in the same table; a heat-exchange coefficient for a bare board in still air bounds nothing for a product in
  a closed box; a typical value is not a guaranteed minimum.
- **An ideal value is an assumption: search the archived datasheet first** (half a period, a 50 % duty cycle, "not
  published"). A clock budget at half a period overstates the margin when the datasheet gives duty-cycle limits,
  which can take most of it; a timing reported as "not published" is in a table of the archived datasheet.
- **Look at the whole event and at both polarities.** A detector that starts after a milestone, or handles one edge,
  reports "none" for what it never looked at: a false-edge check that starts at the 90 % crossing passes a
  high-low-high excursion around the threshold and never examines the falling edge, the sensitive one with low
  thresholds.
- **A placement is announced from every layer of the area, not from the package outlines.** Other layers take the
  room back: a supply trunk on the opposite side leaves no room for ground vias under a converter, and a track of a
  net "of the block" may only be passing through.
- **A distance measured layer by layer says nothing between layers.** A slot or a keep-out drawn at different places
  on each layer can leave an inner plane of one side much closer to the outer copper of the other side than any
  same-layer distance.
- **A list of parts typed into a script is a snapshot.** Read the inventory a calculation needs from the board (the
  capacitors of a rail, with case and rating), stop on a part the table does not know, and compare a converter's
  output capacitance with the manufacturer's validated combinations only from that inventory. Otherwise a removed or
  changed part stays counted: the rail's capacitance, ripple and hold-up are wrong with no error, and a condition
  ("output capacitance above the validated range") is reported on a design that does not have it.
- **A model reads the topology it assumes from the board** (the net of a pad), and the report refuses to render when
  the topology differs from the one its text was written for: a hard-coded clamp node keeps returning the old
  result after the clamp has moved, with no message.

## 3. Toolchain

- **After a cleanup, a revision or a component change, re-run the checks (`make all`) and compare each result with
  the previous one**; explain every number that moved and search
  the old part number in all scripts. Reused results keep the old state (a drop computed without fills no longer
  read, an isolation distance on a renamed pin, a thermal model on the replaced part), and a comment appended to a
  line of a configuration table can swallow the next declaration: the script runs, values shift, and only the
  comparison shows it.
- **The chain fails loudly**: no input silently skipped, balance checks, `make all` run end to end before
  delivering. A load without meshed copper dropped without a message, or a known warning that stops the first target,
  hides everything behind it.
- **Describe a tool from its code, not from its header.** A docstring, a README or a skill that says something else
  than the code is a defect on one side or the other: a distance documented edge to edge and measured centre to
  centre, a cache written and never re-read, a search documented for every topology and implemented for one.
- **Before accusing the design, check whether the import or the tool produced the defect.** An import can lose a
  junction or create thermal reliefs, and the designer is sent to repair what was never drawn.
- **A weakness listed under "Limits" of an algorithm is fixed in the algorithm.** The excerpt is rebuilt as written,
  flaw included (e.g. an undeclared net taken at a default voltage, which under-estimates pull-ups).
- **Compare multisets, parse whole strings, test intersections.** A set accepts two equal resistors in parallel for
  one; a parser that accepts a prefix reads a capacitor value as a resistance; distances between vertices and an
  outline miss two polygons that cross.
- **One tolerance policy, set once for the whole chain.** Where the margin at nominal does not cover the tolerances,
  a passive that enters a verdict sits at its corner in the direction that hurts the check (± 20 % for a class-2
  capacitor whose BOM line says nothing, on top of DC bias); a result at nominal values says "at nominal". Write the
  policy at the head of the verification notes; selection ranges stay judged at nominal (section 1).
- **A DRC item set to "ignore" is a check that was not run.** Measure it independently when a change can touch it:
  after a scripted placement, silkscreen can lie on neighbouring pads and pin-1 marks on a pad, items ignored since
  the project was created or imported.
- **No tool imports code from another board's folder**; shared code lives in the shared library. Otherwise the tool
  runs code that changes with that board (e.g. a previous revision), a fix in the library never reaches it, and two
  boards compute the same thing differently.

## 4. Reporting and recommendations

- **A recommendation gets built as written, so it is complete**: where each part goes relative to the others, and the
  proposal verified under the stresses that decided the original verdict. E.g. an input LC filter recommended on
  stability alone, its clamp on the wrong side of the inductor (`pcb-check-power-input`, method § 4).
- **Every deviation is actionable**: cause term by term, what is concerned, the precise correction (net, position,
  value; by nature of run for routing), the quantified gain, ending with "To do: …" or "Nothing to do". A bare
  negative margin leaves the designer to find cause and action; a width request that does not say which runs it
  applies to is understood the wrong way round.
- **No textbook fix against a visible constraint before quantifying what the deviation costs** (e.g. routing a
  protection on the line without vias, against the placement): otherwise its cost is found after the layout has
  been changed.
- **Do not bring back a choice the designer has dropped** (e.g. the regulator of the previous revision): it reopens a
  closed decision and fills the report with text that no longer concerns the board.
- **Sentences that summarise a table are generated from the table, texts that describe the board are re-read at every
  regeneration, and the cover carries fingerprints of the files verified.** A typed sentence keeps saying what was
  true when it was typed: "within ±3 %" beside a larger deviation, "to be placed" for a part already placed, a stock
  count or a mean rise printed after both changed.
- **A margin is written with its direction in words** ("12 dB above the limit", "29 dB under"), never as a signed
  number beside "under" or "margin", which is read the wrong way round.
- **The delivered document is written right, then looked at**: every number through the report's formatter, in
  metric units, so that no parser has to look for a wrong separator; text extraction only for `nan` / `None` (a
  value lost in the data); a contact sheet for the layout.
- **Brief an external reviewer the way the board is scoped** (design review, stated estimates, "pass" = our
  criteria), then sort the remarks: real bugs, one-line clarifications, certification vocabulary, missing coverage.
  Asked to "qualify before production", a reviewer answers in certification terms.
- **An ambiguous word is restated before the work, not after.** A dictated or translated term can name two layers or
  objects (a stencil for the paste, or the silkscreen), and a study of the wrong object is delivered.
- **Advice about a tool's interface is tested or labelled untested**: an untried dialog option can cancel the whole
  change instead of keeping the nets.
- **"Do we follow the reference design?" is answered from the reference figure itself**: render the page, read it line
  by line against the board, quote the sheet title and page, then study tolerances. A note attributed to the wrong
  variant without opening the page is wrong when the same note sits on the sheet of the other variant.
- **Before listing what is left to decide, re-read the open points of the report**: an action already retained is to
  do, not to decide.
- **Rules of thumb from datasheets are judged, not applied** (mechanism, applicability, numbers:
  `qualitative-rules.md`). Applied outside their domain, they produce deviations that do not exist (copper under a
  connector, a matched group, a distance to a shield).
