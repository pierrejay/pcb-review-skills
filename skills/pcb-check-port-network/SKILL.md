---
name: pcb-check-port-network
description: "Passive network of a wired port between its line IC and its connector: Ethernet over twisted pair, transformer-coupled (10BASE-T / 100BASE-TX / 1000BASE-T) or capacitor-coupled single pair (10BASE-T1L / T1S / 100BASE-T1), other differential links when the IC manufacturer gives a network. Components against the manufacturer's ranges (coupling capacitors, terminations, centre taps, choke, protection capacitance), magnetics, return loss, line symmetry (mode conversion), common-mode emission and immunity estimates, capacitance budget of a multidrop node, plane or no plane under the pair."
---

# Check: interface network of a port (MDI)

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `mode_conversion.py`: mode conversion, half-circuit return loss of any ladder, selection ranges, common-mode level and
  limits of a network port (pure Python, runs under KiCad's Python);
- `fieldsolver2d.py`: capacitance per millimetre;
- `kicad_config.py`: `pin_networks`, the network as built around the line IC and the magnetics or connector;
- `impedance_keys.py`: `mesh_step`, the solver step of the node budget.

## Purpose
Between a line IC (an Ethernet PHY, a field-bus transceiver) and its connector sits a passive network: series or
termination resistors, coupling capacitors or a transformer, centre-tap connections, common-mode choke,
capacitors to ground, common-mode termination, protections. Is each element inside the range its manufacturer
gives and wired as the datasheet requires, and what do the protections and the mismatch between the two lines of
a pair cost in numbers: return loss at the connector, mode conversion, common-mode emission on the cable,
differential noise under conducted immunity? On a multidrop node, does the capacitance fit the budget of the
standard, and how much is left for the part whose capacitance nobody publishes?

## When it applies
- A port with a discrete line interface whose IC manufacturer gives a reference network (with ranges or values).
  Two families cover most wired Ethernet; read only the file of the family on the board (its network, criteria
  rows, pitfalls and cases; values indicative, read in the line IC's datasheet and confirmed in the applicable
  clause of the standard):
  - **transformer-coupled pairs** (e.g. 10BASE-T, 100BASE-TX, 1000BASE-T): `references/transformer-coupled.md`;
  - **capacitor-coupled single pair** (e.g. 10BASE-T1L, 10BASE-T1S, 100BASE-T1), multidrop node budget included:
    `references/capacitor-coupled.md`.
  Other differential links (e.g. CAN, RS-485, an isolated bus) take the parts of the method that apply
  (`references/method.md` § 1).
- After impedance and surge / ESD: the protections chosen in `pcb-check-surge-esd` are judged here for their
  capacitance and their balance.
- Cable length decides which emission and immunity tests apply to the port (texts and indicative thresholds:
  `pcb-check-surge-esd`, "When it applies"). The conducted emission of the port itself is judged here (step 4),
  converter or not.
- A layout question such as "plane or no plane under the pair, cable side" is answered with the same tools
  (step 7).

## Inputs to obtain
- **Line IC datasheet**, application chapter: the reference network with its component ranges or values,
  integrated termination or not, input capacitance of the line pins (typical **and maximum**), transmit amplitude,
  line code and symbol rate; the IC's evaluation board as a second source. Magnetics: the family file.
- **PCB**: value and manufacturer part number of each element; routed length of each stretch of the pair, its
  branches and pads, each with the reference under it (`pcb-check-impedance` extraction); length mismatch
  (`pcb-check-layout-audit`).
- **Component datasheets, of the BOM part**: tolerance; capacitance of each protection, typical **and maximum**;
  choke inductance, tolerance, resistance, leakage, inter-winding capacitance when published; relay contact.
- **Stackups** of production and prototypes. **Designer**: criteria already agreed; design intent (plane removed
  under the pair, where, on which layers).
- **Texts that may apply** (named, their values indicative, to be confirmed in the applicable edition): the
  IEEE 802.3 clause of the link (return loss, isolation, node capacitance of a multidrop link), the emission
  standard of the product (e.g. CISPR 32 for the common-mode voltage of a network port), IEC 61000-4-6 for
  conducted immunity; application notes of the IC or magnetics vendors, judged as qualitative rules
  (`../pcb-verification/references/qualitative-rules.md`).

## Method
0. **Identify the family and draw the network as built**, pin by pin, from the IC to the connector, with the net
   at both ends of each part (`kicad_config.pin_networks` on the line IC and on the magnetics or connector);
   compare with the reference network and with the datasheet's wiring requirements. A part on the wrong net is a
   deviation whatever its value, a row of `pcb-check-configuration` step 6.
1. **Components against the ranges** (`in_range`): a selection range is judged on the **nominal** value, the
   tolerance given for information (rigor rule 8); an upper bound of capacitance also on the component's
   datasheet **maximum**. A range the datasheet calls recommended is a known-good starting point: a part outside
   it is judged by the quantity the circuit sees (for capacitances on one line, their total against the largest
   total the manufacturer allows on that node, identified case by case).
2. **Return loss at the connector** (`ladder_return_loss_db`; `return_loss_db` for the capacitor-coupled
   topology): half circuit over the useful band of the link, protections at their maximum against the network
   without them first (`references/method.md` § 2 step 2).
3. **Symmetry** (`conversion_db`): case "mismatched" first; on a multidrop port the routed length mismatch counts
   beside the diodes. Not computed on a transformer-coupled port (`coupling="transformer"` refuses): steps 3 to 5
   are reported incomplete (`references/transformer-coupled.md`).
4. **Conducted common-mode emission of the port** (`cm_level_dbuv`, `cm_limit_dbuv`), 0.15–30 MHz: the density
   of the line code in the receiver bandwidth through the conversion, against the class limits; an exactly
   symmetric port has no level (`None`): met.
5. **Conducted immunity** (`differential_noise`): differential noise at the IC lines in the signal band, solved
   as the reverse excitation on the port's own terminations, not as the EMF × the DM → CM conversion. An estimate
   to decide on a measurement, not a verdict.
6. **Multidrop node budget** (multidrop links only): `references/capacitor-coupled.md`.
7. **Design study, plane or not under the pair** (cable side): variants at equal routing compared on added
   capacitance, line-to-ground capacitance and its P/N difference, impedance and etching sensitivity in both
   stackups, ESD return inductance; the study gives the numbers and a width / gap for the variant retained, the
   designer decides.

## Criteria
| Item | Limit | Source |
|---|---|---|
| Each component of the reference network | inside its range (nominal); upper bounds of capacitance also at the component's maximum. A range stated as a requirement is a criterion; a recommended range is a known-good start, a part outside it judged by the rows below | line IC datasheet, application chapter |
| **Total capacitance from a line to ground** | ≤ the largest total the manufacturer allows on that node, at the components' maxima | identified case by case from the datasheet (the designer may set another) |
| Return loss at the connector | above the mask of the PHY or of the standard, when one is given | datasheet or standard (indicative); otherwise reported, not judged |
| Common-mode voltage of a network port | class A / B limits (`cm_limit_dbuv`) | emission standard of the product (indicative) |

The family rows and a filled table for one PHY are in the family file; each PHY brings its own, read in its
datasheet. A part that exceeds its own recommended row is reported with its effect under the total (return loss,
balance), not as a non-conformity on its own; the single-component figure that a criterion agreed with the designer
supersedes is still reported for information. No limit is coded for the immunity estimate.

## Self-checks
- Low-frequency return loss checked by hand: where one element dominates (a coupling capacitor, a magnetising
  inductance), |Z| of that element against Zref gives the return loss.
- Solver: mask parameters re-read against their definition (`c1` substrate, `c2` copper), not their order of
  appearance.

## Tool contract
- `port_network.py`, KiCad's bundled Python (`pcbnew`, no numpy): steps 0 to 5 → `results/port_network.json` = `{rules,
  out_of_range_nominal, out_of_range_guaranteed, return_loss: [{case, points}], port: {case: {Ca, Cb, points, min
  margins, min conversion, differential noise in band}}, assumptions}`. Node budget: the capacitor-coupled file.
- `plane_study.py`, venv: step 7 → `results/plane_study.json`. Once the decision is applied to the routing, the
  study is **frozen** with its results; it is not re-run on the new board.
- **Refusals of the board scripts**: an unreadable value suffix, a part number that differs from the PCB, a stretch on
  an unexpected reference.

## Pitfall
**Halve the differential elements in the half circuit**: an element between the two lines, or a differential
leakage, enters at half its impedance (`references/method.md` § 3). Passing a whole leakage moves the return loss
by about 20 dB at 1 MHz and 4 dB at 20 MHz (220 nF, array 1.8 pF, leakage 0.5 µH).

## Limits
The half circuit ignores the cable, the IC's own return loss and, when its input impedance is not given, the
receive branch (`references/method.md` § 2 step 2); the dispersion between two lines is not characterised by the
datasheets (typical against maximum is a scenario, not a bound); the transmit spectrum is an upper bound without
filter; the immunity figure is not compared with a receiver threshold.
