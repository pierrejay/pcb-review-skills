# Qualitative rules: how to judge a rule stated without numbers

Application notes, layout guides and reference designs are a known-good starting point. Many of their rules are
stated without a number ("no copper under the transformer", "match the group lengths", "no floating copper",
"keep the protection on the line"). Such a rule is neither applied by default nor dismissed: it is judged in
three steps.

1. **Mechanism**: what physical effect the rule protects against (coupling, mode conversion, return path, timing
   skew, resonance, charge build-up), and for which kind of circuit, frequency and disturbance it was written.
   The context of the document matters: a note written for one link type, one speed or one market (e.g.
   automotive gigabit links) may aim at an effect that is negligible elsewhere.
2. **Applicability**: whether that mechanism exists on this board, with these parts (a discrete part or an
   integrated one, a fast or a slow link, a surge or an ESD time scale).
3. **Numbers**: the effect computed on the board if the rule is not followed, weighed against the cost of
   following it, which is often another rule (an impedance, a ground return, a placement, a protection's
   inductance). Two rules in conflict are both quantified.

The report gives one row per rule: rule and source / mechanism and domain / numbers on both sides / decision.
The designer decides; an accepted departure is recorded as a decision with its date. A rule found applicable and
quantified becomes a criterion like any other.

## What each kind of manufacturer guidance is worth

- **What a part requires to work** (absolute maximum ratings, operating conditions, clock accuracy, levels, setup and
  hold, "connect X to Y") is a criterion. A routing prescription, even written "must" (an impedance, a width), is a
  means, judged in the three steps above.
- **An application circuit, a layout guide or a reference design** is a known-good starting point, not an optimum
  and not a criterion by itself. Departing from it is not a deviation by itself; a part of the reference circuit
  that is absent from the board is a row judged by calculation; a rule it states without numbers is judged in the
  three steps above.
- **A range that a datasheet table calls recommended** is a known-good starting point too: the criterion is the
  quantity the circuit sees, and the largest value it admits is identified case by case from what the manufacturer
  allows, not by a general rule.
- **An improvement that is not a requirement** (e.g. decoupling values per pin, when no target impedance or supply
  budget applies) is a recommendation with its computed gain, never a fail. A published target, or a rail leaving
  the load's range, is a requirement; a wiring error (a part on the wrong net) is a deviation.

## Patterns

- **A rule that aims at a discrete part may not apply to an integrated one.** "No copper under the transformer"
  protects the cable side of a discrete transformer routed on the board from coupling into the planes. Under a jack
  with integrated magnetics, the coupling through the housing is small (of the order of a pF), while voiding the
  planes there can cost the impedance of the pairs routed over them and the ground continuity of the area. Compute
  both before deciding.
- **A means is not an end.** "Match the lengths of the group" serves a timing budget: when the budget per line has
  margin, the matching is not a criterion (`pcb-check-timing`); when it has none, the budget decides, not the rule.
- **Judge "no floating copper" on what the copper is.** The rule aims at copper with no DC or AC path that charges
  up or resonates. A shield or pour tied through a capacitor is not floating; the tie itself is judged by
  `pcb-check-chassis-grounding`.
- **A placement-driven asymmetry is quantified before a re-route is recommended.** E.g. a protection stub that
  changes layer on one line only: its extra inductance (from the geometry) times the di/dt the protection actually
  sees gives the voltage at stake. Behind a common-mode choke, a microsecond surge has a bounded di/dt and the
  effect is usually small; a nanosecond ESD edge is not bounded the same way and is recomputed.
- **A rule written for another link type is weighed against the requirement of this one.** E.g. "remove the copper
  under an unshielded pair, on all layers, up to the choke" in a layout note for automotive 100 / 1000 Mbit/s
  links aims at mode conversion and return loss at those speeds; the same note asks for a solid ground under the
  ESD protection, whose clamping depends on its ground-return inductance. On a slower multidrop link the
  governing quantity may instead be the node capacitance budget of its standard. Compare variants at equal routing
  (e.g. no plane at all; a plane on the adjacent layer; the track and adjacent layers voided with a plane farther
  down), each with: capacitance added to the node, capacitance of each line to ground and its P/N mismatch (mode
  conversion), impedance and its sensitivity to etching, ESD peak as a function of the protection's ground-return
  inductance (`pcb-check-port-network`, design study). The study gives the numbers; the designer chooses.
- **Two rules in conflict are both quantified.** E.g. a detour added on one leg of a pair to equalise lengths
  leaves that leg uncoupled for a few millimetres: compute the skew it removes against the edge, and the return
  loss of the uncoupled run at the useful frequency; state the design intent and let the designer decide.

Each conclusion holds **under the conditions it was computed in** (part, frequency, kind of disturbance): on
another board, check those conditions first.
