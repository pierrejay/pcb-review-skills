---
name: pcb-check-derating-sourcing
description: "Component derating and sourcing check of a PCB: rated voltage, power, current and temperature of every BOM part (supplier-catalogue data, e.g. JLCPCB) against the stress on its nets under an in-house policy; assembly stock."
---

# Check: derating and sourcing

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `derating_rules.py`: description parser, applied-voltage rule, resistor-between-signals rule and its load formulas,
  policy table, family judgements, states, acceptance check;
- `derating_engine.py`: `analyse`, the walk of the BOM that applies them to every part, and `summary`, the JSON.

## Purpose
Is every passive and every diode of the BOM used far enough below its ratings, under the permanent stresses of
the scope of use, and can the board be ordered today with the parts it names? The check walks the whole BOM
automatically: ratings from the supplier's catalogue, DC stress from the nets of each part, an in-house derating
policy, and the assembly stock of each part number.

## When it applies
- Every board, once the rails and the thermal check are done (it reuses their results). Sourcing alone is worth
  running **at the very start** of a review: a part that cannot be bought outweighs any routing deviation.
- The derating method is generic; the sourcing part and the description parser are written for the parts catalogue
  of one assembler (JLCPCB: one-line descriptions, basic / extended categories, assembly stock).

## Inputs to obtain
- **PCB**: per footprint, reference, value, supplier part number (field name per library: `Supplier Part`,
  `LCSC`, `LCSC Part #`, `JLCPCB Part #`), "excluded from BOM" and DNP attributes, all as the assembly variant judged
  sets them, net of each pad.
- **Supplier catalogue**, per part number: manufacturer part number, description line (it carries the ratings),
  category, package, assembly stock, date of reading.
- **Other checks**: rail ranges with tolerance, lowest and highest (`pcb-check-power-rails`), peak inductor currents,
  isolated nets (`pcb-check-isolation`), board temperature rise (`pcb-check-thermal`), capacitors whose effective
  capacitance was already used.
- **Datasheets**: VRWM of each TVS and ESD part, typed per part number; rail current through each ferrite bead; the
  rated voltage or the tolerance of a resistor whose description does not print it (`v_rated`, `r_tol`).
- **Designer** (scope of use): the permanent range of each supply (nominal ± tolerance of the source; an adjustable
  supply over its whole setting range), the ambient temperature, the temperature grade wanted, the batch size
  (against which the stock is read), who assembles (whose stock counts), and the validation of the policy.

## Method
1. **Ratings** from the description line (`parse_description`); a ceramic capacitor whose line prints no
   temperature range takes the one of its dielectric code. The parts judged are those assembled in the variant
   named, with the supplier part number and value that variant gives them: DNP and excluded-from-BOM parts are
   skipped, and a DNP part carries no voltage from one net to another.
2. **Family from the catalogue description first** (`family_of`), the reference prefix as a last resort.
3. **Stress** (`applied_voltage`) on each part of a judged family with two or three nets, and on protection parts
   whatever their number of lines, supply pin included: every declared rail is its range, every pair of nets is
   taken at opposed corners, and an undeclared net is a signal between 0 V and `v_default` (a screening parameter;
   the part is counted "assumed"). A stress the nets cannot show, or that of a part between two nets that move
   together, is forced with its reason.
4. **Resistor between two undeclared nets** (`resistor_between_signals`): the worst case is a bound, not its load;
   judged on the bound when it holds the limit, else on the declared load of its function, else "not judged: power
   to determine".
5. **Domains** (`domains_of`): the voltages of an isolated domain are referred to its own ground; a part spanning
   two domains is listed "crosses A ↔ B" and left to `pcb-check-isolation`, `pcb-check-surge-esd` and
   `pcb-check-chassis-grounding`.
6. **Currents** declared per reference with their source; **temperature** against ambient + board rise.
7. **Policy** per family (`judge_*`), giving deviations and flags, and the state of every part (`count_states`).
8. **Accepted deviations** (`apply_acceptances`): the designer's decisions only, declared by the board with their
   mark.
9. **Sourcing** (`judge_stock`): assembly stock of each part number against the threshold.

## Criteria
In-house policy (`derating_rules.POLICY`, `FAMILY_RULES`): a screening habit, not a derating standard, validated by
the designer. A new project sets its own thresholds with its designer (from its quality requirements, the
manufacturers' derating guidance and the standards of its market) and codes them there.

| Family | Deviation if | Flag if |
|---|---|---|
| Capacitors | V > 80 % of rated voltage | class 2 dielectric (X5R, X7R, Y5V…) of 1 µF or more above 50 % of rated voltage: effective capacitance to verify on the part's DC-bias curve, unless a calculation already used it (`bias_done`); judged against what the circuit needs (regulator stability, a minimum the datasheet requires, the computed decoupling) |
| Resistors | P = V² / (R (1 − tolerance)) > 50 % of rated power; V > rated voltage | — |
| Series diodes (Schottky, rectifier, switching) | reverse voltage > 80 % of VRRM | — |
| TVS and ESD diodes | VRWM < permanent DC voltage | VRWM less than 10 % above it |
| Power inductors | peak current > 80 % of the lowest rated current of the description | — |
| Ferrite beads | current > 50 % of rated current | — |
| Every part | — | maximum temperature ≤ ambient + board rise |
| Sourcing | — | assembly stock < 1 000 (read it against the batch size); **zero blocks an assembled order** |

Verdict: pass when there is no deviation and no flag "judged on an assumed voltage above half its rating"; "pass *"
when the only deviations are accepted ones; flags, assumed voltages and stock reported next to it, each with its date
or basis. The verdict covers the parts judged: the count of "not judged" parts is in the same sentence, and a board
with one such part is not fully checked. What the stand-off rule means (leakage, not failure):
`references/method.md` § 2.

## Self-checks
- **Nothing skipped in silence.** Parts without a supplier part number, numbers absent from the cache, and parts
  of a judged family whose rating did not parse are counted and listed, in the output and in the report.
- A TVS or ESD part takes its stand-off from `vrwm` (Pitfalls); an inductor with a declared current has a current
  in its description.
- Print the parsed ratings of one part per family and compare them with the datasheet once per board, and any rating
  that decides a verdict: the parser takes the first number followed by a unit, skipping for the voltage a value in
  millivolts and a value attached to `@` (a characteristic at a test condition); a voltage range (e.g. `2.7V~5.5V`)
  gives no rated voltage, and the part is then not judged on it. A resistor whose line prints no rated voltage or no
  tolerance (`±x%`) is "not judged" until its datasheet value is declared in `v_rated` / `r_tol`.
- The number of assumed voltages is printed and reported; every stock figure carries its `read_on` date.

## Tool contract
| Script | Interpreter | Reads | Writes |
|---|---|---|---|
| `parts_lookup.py <cache.json> <part numbers…>` or `--pcb <board>` | the venv (standard library, network) | supplier catalogue | `results/bom_parts.json` (cache) |
| `derating_check.py` (board: configuration, then `derating_engine.analyse` and `summary`) | KiCad's bundled Python | PCB, cache, results of the other checks | `results/derating.json` |

- **JSON**: the policy, the scope values, the rails, one row per part (identity, stock and date, category, family,
  nets, applied voltage and whether assumed, rating, ratio, deviations, flags, note, state), the list
  `to_determine` (resistors between two signals, with their bound), the counts of deviations, flags and assumed
  voltages, the accepted deviations, the count per state, the date of the stock. On the console: one line per
  deviation, one per flag, then the totals and the states.
- **Refusals of the engine**: a BOM part without catalogue data (collected, the run stops at the end), a key of a
  board table naming a reference absent from the board (a stale key applies a current, a voltage or a note to the
  wrong part), a net of `rails` or `domains` with no pad on the board (renamed), a board with assembly variants and
  none named (`variant=`), an entry of `powers` left unused, an accepted deviation that no longer occurs, a
  non-finite value in the configuration or the cache.

## Pitfalls
- **Read the stand-off of each protection in the datasheet of the part number on the BOM.** A protection rated
  below the permanent voltage of the supply it sits on leaks; the stand-off differs between brands under one
  generic name, and the first voltage of the description is not reliably the stand-off.
- **Declare every net that can exceed `v_default`**: the supply nets of every port, and a signal of another domain. An
  undeclared net is judged between 0 V and the highest rail it reaches through resistors, inductors, beads, diodes and
  fuses (`reach_spans`), at least `v_default`; a net that leaves the board through a connector is not judged until its
  range is declared; a part flagged on an assumed voltage gets its net declared.

## Limits
Permanent DC stress only. ICs, connectors and passives with more than three nets are not judged for voltage
(protection arrays are), only for temperature and stock, counted "not judged: family outside the policy". Ratings
come from a one-line description: parse tolerance, no curve.
