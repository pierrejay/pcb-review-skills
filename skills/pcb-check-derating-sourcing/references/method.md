# Derating and sourcing: method in full, lookup, board table and algorithm, reporting

The catalogue lookup itself (network) is described here and stays in the board workspace.

## Contents
1. Method, step by step
2. What the stand-off rule means
3. Building the tool: parts lookup, board table, algorithm
4. Reporting

## 1. Method, step by step
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers.

1. **Ratings** are parsed from the description line of each part (`parse_description`): rated voltage, power,
   resistance and its tolerance, capacitance, current(s), inductance, dielectric, temperature range. A resistor's
   rated voltage or tolerance that the line does not print is read in its datasheet and declared (`v_rated`,
   `r_tol`), else the resistor is not judged. A ceramic capacitor whose line prints no range takes the one of its
   EIA dielectric code (EIA-198 may apply; the ranges commonly printed by capacitor manufacturers are X5R −55 to
   85 °C, X7R and C0G −55 to 125 °C, Y5V −30 to 85 °C; confirm on the datasheet of a part that decides a verdict),
   with its source in `t_source`; a range printed in the line wins.
2. **Family** from the catalogue description first (`family_of`), the letters of the
   reference designator (`C`, `R`, `D`, `L`, `FB`) only as a last resort: a library may name an inductor `U…` and a
   common-mode choke `D…`.
3. **Stress**: the range of DC voltage of each net of the part, then the largest possible difference between two of
   them, taken at opposed corners: one net at its highest, the other at its lowest (`applied_voltage`). It is
   computed for each part of a judged family with up to three distinct nets (capacitor, resistor, diode, inductor,
   bead), and for protection parts (TVS, ESD arrays) whatever their number of lines: their stand-off voltage is
   judged against the largest DC voltage between two of their pins, supply pin included (`judge_protection`).
   - Rails are **declared** by the board as ranges (lowest, highest): ground 0 V; a supply over the tolerance of its
     source (e.g. a 24 V supply with a ±10 % source: 21.6 to 26.4 V; an estimate, replayed by changing one
     constant); a switching node from 0 V to the input maximum, its bootstrap node from the bootstrap voltage of the
     regulator (its datasheet) to the input maximum plus that voltage; regulated rails over their tolerance (the
     set-point range of `pcb-check-power-rails`); feedback nodes at their reference, with its tolerance.
   - **Opposed corners.** Two independent supplies are not at their maxima together: a part between a 12 V and a
     5 V supply, each ±10 %, sees 13.2 − 4.5 = 8.7 V, not 13.2 − 5.5 = 7.7 V. Two nets that move together are the
     exception, and only a forced voltage with its reason states it: a bootstrap capacitor across its switch node
     (the bootstrap voltage, not the input range), a resistor between a rail and its copy behind a filter, a
     sense resistor in series with a rail (the drop at the declared current, not the tolerance band), or a series
     resistor in a signal line between two nets of that signal declared with the same range (the drop at the line
     current). Left to the corners, such a part shows a deviation, which is the prompt to force it.
   - A net that is not declared is a signal anywhere between 0 V and the default I/O voltage `v_default`, and the
     part is counted "assumed": a pull-up from a 3.3 V rail sees 3.3 V when the pin is low, not the few tenths of a
     volt between the rail and `v_default`, and two undeclared nets see `v_default` (opposed levels), with no
     exception. `v_default` is a screening parameter, not a property of the board: set it from the highest I/O
     supply of the scope (the code default, 3.6 V, is that of 3.3 V logic at the top of its tolerance).
   - A stress that the nets cannot show is **forced** with its reason: a series diode conducts in normal use, its
     permanent reverse voltage is the supply connected backwards.
4. **A resistor between two undeclared nets** has no established voltage: the worst case (opposed levels, V² / R at
   the low corner of R, R (1 − tolerance), V from
   `applied_voltage`: `v_default`, or the rails the two nets reach) is a bound, not its load. Three cases
   (`resistor_between_signals`): the bound holds the limit → judged on it, whatever the topology; else the board
   declares the load of the resistor's function, with its calculation (table below) → judged on it, a declared power
   above the limit being a deviation like any other; else "not judged: power to determine", listed with the bound,
   neither a deviation nor a pass. A zero by default would hide a real dissipation, which is why the third case exists.

   | Function, identified on the schematic | Load to declare (function of `derating_rules`) |
   |---|---|
   | In series on a digital line with a single driver (clock, data, reset, UART) | C·V²·f: all the energy of one period (a rising and a falling edge) counted in the resistor, C = capacitance downstream of it (receiver pin + trace, computed from the board; where it cannot be, a fallback of the order of tens of pF, labelled as an estimate), f = the fastest clock of the board, plus the DC current of the smallest pull resistor found on such lines, flowing through the resistor itself: (V / R_pull)² · R (`load_series_digital`) |
   | Series termination of a differential line driver (e.g. a long-reach field-bus transmitter with one resistor per leg) | driver taken as a voltage source of twice the line amplitude, line shorted: half the peak-to-peak line amplitude across each resistor (`load_series_termination`; `matched=True` for the matched-line figure) |
   | Parallel termination of a bus: one resistor across the pair, or two equal resistors in series between the wires (split, midpoint to a capacitor) | across: the whole differential amplitude across it; split: half of it across each (`load_parallel_termination(…, topology)`) |
   | In series on a USB 2.0 pair | the high-speed driver current through it, taken as permanent (P = I²·R: an envelope, the mean over the traffic is lower) (`load_usb_series`) |
   | In series with a crystal | the crystal current: drive level × R / ESR (`pcb-check-crystal`; `load_crystal_series`) |
   | In series with a push-button or a jumper | the current of the pull resistor it closes, V / (R_pull + R) (`load_button_series`) |

   Two outputs driving against each other are a fault, not a derating regime: the load is that of normal
   operation, and the hypotheses (capacitance per line, driver model) are listed as estimates.
5. **Domains** (isolated side, chassis; `domains_of`): each net belongs to one domain, "main" by default, and the
   voltages of an isolated domain are referred to its own ground: judged against the board ground, every part of
   the isolated side would look either unstressed or overstressed. The lines of a bus are not bounded by the local
   supply: they follow the bus's common-mode and fault range relative to that ground (for an RS-485 bus, typically
   −7 to +12 V in normal use, more for fault-tolerant parts; read the transceiver's datasheet), so declare that range
   for the parts on the lines. A part whose nets span two domains is not judged here: its DC voltage is zero and its
   real stress is the surge or the ESD pulse; it is listed with the note "crosses A ↔ B".
6. **Currents** are declared per reference designator with their source: peak inductor current = output current
   of the envelope case + ΔI/2; ferrite beads at the maximum current of the rail they feed (estimate).
   **Temperature**: maximum operating temperature of each part against the scope's ambient + the average board rise
   (thermal check, scenario "measured") (`judge_temperature`).
7. **Policy** applied per family (`POLICY`, `FAMILY_RULES`, `judge_*`), giving deviations (policy exceeded) and
   flags (to look at). Every part ends "judged" on a rating, or "not judged" with its reason: crosses a barrier,
   family outside the policy, signal-line choke without DC current, current not declared, rating not read in the
   description (a resistor's tolerance or rated voltage included), a 0 Ω link, a diode that is not a Schottky,
   rectifier or switching diode (LED, Zener), a resistor between two signals whose power is to determine
   (`not_judged`, `count_states`).
8. **Deviations accepted by the designer** are declared by the board, each attached to the part number decided on
   and to the deviation texts accepted verbatim (rating and stress included), so that a decision does not outlive
   the part or the stress it was taken for; they stay listed, apart, and stop counting in the verdict
   (`pcb-verification`, "What a verdict means").
9. **Sourcing**: assembly stock of each part number against a threshold (`judge_stock`), read on a dated catalogue
   (§ 3).

## 2. What the stand-off rule means
It is a rule of caution that a part chosen for a voltage class (e.g. "5 V") easily breaks when the supply it
protects can sit above that class. Up to VRWM the datasheet guarantees the leakage current, so the protection is
invisible to the line. Between VRWM and the breakdown voltage nothing is guaranteed: the part does not clamp yet,
but its leakage rises steeply with voltage and temperature. The effect of a small excess is therefore a leakage
current (typically microamperes or less, to be read on the curve if the datasheet has one), not a failure; it
matters on a battery-powered or high-impedance line and hardly on a supply pin. Report the deviation with that
effect, and let the designer accept it or change the part.

## 3. Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract". The lookup needs the network; the rest is
replayable offline from the cache. Run time depends on the network and the size of the board: typically a fraction
of a second per new part number for the lookup and a few seconds for the analysis.

### Parts lookup (supplier catalogue data with a local cache)
Interface contract: for a supplier part number, the source returns `{mpn, description, category, stock, package}`;
the lookup adds `read_on`. Any source that provides these fields will do (an official interface or an export,
where available). An assembler may publish no documented interface for its parts library: an unofficial endpoint
can change without notice, so the lookup is a separate, replaceable script and nothing else depends on how it
fetches.
1. Load the cache (a JSON object keyed by supplier part number), or start empty.
2. For each requested number **absent from the cache or read more than a maximum age ago** (one day by
   default, a screening parameter: ratings do not move, stock does, in both directions): query the source with
   the number as keyword, and keep only the result whose part number is exactly the one asked — a search also
   returns neighbours. Store `{mpn, description, category, stock, package, read_on}` with the date of the day.
   Pause between requests (0.2 s is courteous).
3. A failed request (offline, changed interface) does not stop the run: a number already cached keeps its old
   entry and goes to a `stale` list, printed with its date; a number never read goes to a `missing` list. Write
   the cache at the end.
4. Put the lookup in the analysis target of the Makefile, before the analysis, so that a report is never issued on a
   stock nobody re-read. Keep network access out of the board scripts and run the lookup with an interpreter that
   has a working certificate store (the interpreter bundled with an application may have none, in which case
   every HTTPS request fails).

### Board table
The board script builds the configuration from the other checks' JSON files (rail ranges, board temperature rise,
isolated nets, inductor currents), types only what exists nowhere else (supply range of the scope, VRWM table,
forced voltages, notes), then calls the engine and writes the result.

| Declaration | Content |
|---|---|
| `rails` | {net: (V low, V high)}, ground 0: the range of each declared net (step 3) |
| `domains` | {net: domain name}, "main" for the others (step 5) |
| `v_default`, `ta_max`, `dT_board` | voltage of an undeclared net (step 3); ambient of the scope and average board rise (step 6) |
| `currents` | {ref: (A peak, source)} (step 6) |
| `no_current` | {ref: reason}: a choke on a signal line |
| `vrwm` | {mpn: V}, from the datasheet of each protection's part number |
| `forced_voltages` | {ref: (V, reason)} (step 3) |
| `bias_done` | {ref: the calculation that already used the effective capacitance} |
| `notes` | {ref: text} |
| `accepted_deviations` | {ref: {"mark": the designer's decision, "mpn": the part number decided on, "deviations": [the deviation texts accepted, verbatim]}} (step 8) |
| `powers` | {ref: (W, justification)}: load of a resistor between two signals whose bound exceeds the limit (step 4) |
| `v_rated`, `r_tol` | {mpn: (V, source)}, {mpn: (fraction, source)}: rated voltage, resistance tolerance of a part whose description does not print them, from its datasheet |
| `variant` (argument of `analyse`) | the assembly variant judged, required when the board has variants (`""` for the default) |

### Algorithm
The engine is `derating_engine.analyse`, on `derating_rules`; the board script builds the configuration and the cache,
calls it, then writes `summary`. Check the whole `rails` table once at the start (`rail_spans`), and every net of
`rails` and `domains` against the nets of the board (a renamed rail would fall back to `v_default`), so that a bad
entry stops the run before any row; then, per footprint of the board:
1. Skip it if DNP or excluded from the BOM in the variant judged (a DNP part does not carry a rail to the nets it
   would join either: `reach_spans`). Look up its supplier part number, as the variant judged sets it, in the cache
   (a variant may fit another part: `GetFieldValueForVariant`, value included); a part of the BOM without catalogue
   data is collected.
2. Parse the description (`parse_description`): first value of each unit, dielectric, temperature range.
3. Flags that do not depend on the nets: stock under the threshold (`judge_stock`); maximum temperature ≤
   `ta_max + dT_board` (`judge_temperature`).
4. Family (`family_of`, step 2).
5. Nets = distinct net names of the pads, without empty names and without names starting with `unconnected`.
   Judge the voltage for parts of a judged family with 2 or 3 nets, **and for protection parts whatever their
   number of nets**.
6. If the nets span more than one domain (`domains_of`): note it and go to the next part.
7. Applied voltage (`applied_voltage(nets, rails, v_default, forced)`, step 3), with the forced voltage of the
   reference designator if it has one. A resistor between two undeclared nets without a forced voltage goes through
   `resistor_between_signals` (step 4) with its entry of `powers`, if any: judged on the bound and marked "worst
   case: opposed levels", or judged on the declared power with the justification written in the row, or put in
   `to_determine` with the bound. As a triage aid, write next to it the pin found when one of its nets carries only
   this resistor and one other pad (count the pads of the whole board per net): the resistor is then in series with
   that pin.
8. Apply the family's rule and set the state (step 7): capacitor (`judge_capacitor`, with `bias_done`); resistor
   (`judge_resistor`: power from the parsed resistance at the low corner of its tolerance, or the declared power,
   and rated voltage); protection
   (`judge_protection`: stand-off from `vrwm`); diode (`judge_diode`, with its description).
9. Inductors, beads and common-mode chokes (`judge_inductor`, `judge_bead`): with a declared current, inductor →
   lowest of **all** the `…A` values of the description, bead → its rated current; or with the `no_current`
   reason.
10. Append the row (`../SKILL.md`, "Tool contract", JSON).
11. At the end: stop on the refusals collected during the run, then move the accepted deviations out of the count
    (`apply_acceptances`, step 8).

## 4. Reporting
- Deviations first: reference designator, part, rating, stress, ratio, limit, and the correction (part with the
  next rating in the same footprint, with its part number and its stock on the day).
- Flags by kind: thin TVS margin, temperature, bias to verify, assumed voltages (count, and the list for the
  parts that sit above half of their rating).
- **Stock table with the date of reading**: every part under the threshold, zero-stock parts on top and written
  as blocking; for each, the alternative with its part number (same footprint, same or better ratings) or the
  explicit statement that none was found, and where else the original can be bought.
- Deviations accepted by the designer: apart, with the mark that points to the list at the head of the report
  (rule, finding, effect, dated decision, what would reopen it).
- The count of parts per state (judged; not judged, by reason), so that the reader sees what the zero covers.
- Parts that cross a domain, with the chapter that judges them.
- The policy table, labelled in-house, with the statement that another project sets its own.
