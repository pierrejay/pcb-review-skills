# Scoping: product requirements before any verification

A verification is only worth its criteria, and the criteria come from the **real use of the product**. The same
result can pass or fail depending on the scope: a surge level that destroys a part in one installation may not apply
in another (the scope sets the criteria, e.g. a dedicated supply with a short cable against a shared distribution
network); the dip of a system rail when a peripheral is plugged into an expansion port does not exist if the port is
not hot-pluggable; an automotive-grade component usually adds cost and no benefit in a temperate cabinet. Without a scope, one tests
too much (cost, false problems) or not enough ("works on my desk").

## Contents
1. When and how to scope
2. Questionnaire
3. What each answer changes
4. Rules of conduct
5. Where to record
6. Working with the designer, beyond the scope

## 1. When and how to scope

- **As soon as the project is first looked at**, before the first computation: ask the designer for the scope of use,
  in one series of grouped questions (not piecemeal). Propose reasonable default values so that the designer
  only has to correct them (e.g. "temperate cabinet, dedicated supply with a short cable, industrial CE?").
- **For a targeted question** (one link, rail, port or part), ask only what its answer depends on: an impedance
  needs its target and the stackup, not the market. The rest of the scope is stated as assumptions, and the answer
  says what it does not judge.
- **Anticipate the issues** the designer does not necessarily have in mind: EMC and CE marking (standards, test levels
  according to the type of port and the cable length), electrical safety and isolation, withstand in the real
  environment (temperature, disturbed supply, long cables, earthing), withstand over time (capacitor aging,
  continuous heating), fabrication (stackup, tolerances), sourcing (grade, stock, second source).
- **Come back to the designer** as soon as a verification reveals that an assumption decides the verdict: say so,
  quantify both cases, let the designer decide. The same goes for a datasheet reading that admits two meanings
  and decides a verdict (a supply range "1.8–3.3 V" may list the versions sold rather than one operating range).

## 2. Questionnaire

**Use and installation**
- Function, users, place of installation (office, electrical cabinet, outdoors, vehicle, mobile).
- Enclosure: metal (connected to earth?), plastic, no enclosure; board accessible to touch? mounting, metal
  screws, chassis ground point.
- Production volume, target lifetime, on-site maintenance.

**Environment**
- Operating and storage ambient temperatures (min / max), ventilated or closed cabinet, sun, hot
  neighbors; humidity, condensation, dust (pollution degree), altitude.
- Vibration, shocks (mounting of heavy components, connectors).

**Power supply**
- Source: dedicated power brick, DC distribution network (shared 24 V cabinet supply), battery, USB from a PC, PoE…
- Continuous voltage range (nominal ± tolerance, adjustable supplies), expected transients, possible polarity
  reversal, hot-plug, length and nature of the cable.
- Expected consumption, low-power modes, worst-case load (all ports active).

**Each port / connector**
- Internal (same enclosure) or external; maximum cable length (the immunity standards set test requirements by
  cable length, with thresholds of the order of 3 m and 30 m to be confirmed in the applicable text), shielded
  or not, inside / outside the building, connected to which equipment (earthed or floating).
- Hot-plug or not; accessible to the user (ESD); what can be plugged into it by mistake.
- Data rate and mode actually used (e.g. 10 versus 100 Mbit/s, clock frequency configured in the software).

**Target compliance**
- CE marking: EMC directive (product standard or residential / industrial generic standards: IEC 61000-6-1/-2 immunity,
  -6-3/-6-4 emission, EN 55032 class A/B), low-voltage directive (above 50 V AC or 75 V DC), radio (RED).
- Other markets (FCC, UL), sector standards (railway, medical, automotive, ATEX).
- Isolation: functional, basic, reinforced; withstand voltage and **nature** of the withstand (transient, 60 s AC,
  DC); maximum **working voltage** between the two sides, steady and transient (it alone sizes creepage; three
  different tables of IEC 60664-1 depending on the answer).
- Expected test levels (ESD contact/air, fast transients (EFT), surge per port) or "robustness beyond the standard".

**Components and fabrication**
- Desired temperature grade (commercial, industrial, automotive) — deduce from it the range actually needed.
- Manufacturer and stackup (the production and the prototype builds may differ), assembly, production tests. The
  stackup declared in the board can differ from the one ordered: unless it is stated clearly, confirm it with the
  designer. Layer thicknesses, permittivities and copper come from the stackup the fabricator publishes for that
  build (e.g. JLCPCB's), written in a stackup file (`assets/stackups/`), not from the board's declaration alone:
  impedance, distance between layers, capacitance and heat spreading depend on them.
- Widths of the controlled-impedance links (differential pairs: width and gap; single-ended lines, e.g. where a pair
  splits), to be entered
  in the net classes rather than assumed. If the designer has them from a calculator, take them; if not, do not
  ask for what the review can compute: propose candidate dimensions for the declared stackup with the solver
  (`pcb-check-impedance`), each with its impedance and its sensitivity to etching, and let the designer choose.
- Constraints of space, cost, imposed parts.

**Software and configuration**
- Configured frequencies and modes (buses and clocks), sequencing handled by the software, internal pull
  resistors used.

## 3. What each answer changes

| Answer | Verifications affected | Example |
|---|---|---|
| Type of source and length of the supply cable | surge (generator impedance of the combination wave: of the order of 2 Ω for the power-port case and 42 Ω for the signal-port case, indicative values of IEC 61000-4-5), sizing of the TVS and series diode | a dedicated supply with a short cable → the surge test may not be required by the generic standard for this port type (cite the edition and the note, and read them in the applicable text); a level kept for robustness → a TVS and a series diode sized by the computed surge |
| Continuous range of the supply | standoff voltage of the TVS, rating of the regulators | a TVS whose stand-off voltage lies below the top of an adjustable supply range is incompatible with that range |
| Hot-pluggable port or not | voltage dip, inrush current, ESD on pins | an internal expansion port → hot-plug cases discarded |
| Length of the signal cables | surge and fast transients (EFT) per port (cable-length thresholds of the immunity standards) | a port with a long cable → surge levels simulated; a short internal link → ESD only |
| Enclosure (plastic, metal floating, metal earthed), fixing, what each cable meets at its far end | ESD, common-mode paths, tie of each shield, shell and fixing point to ground (direct, capacitor, none) | the candidate ties are computed for each enclosure of the scope; the designer chooses (`pcb-check-chassis-grounding`) |
| Ambient temperature and enclosure | thermal, component grade, oscillator drift | the highest admissible ambient is computed from the dissipation and compared with the grade of the part (`pcb-check-thermal`) |
| Temperature grade | choice of parts, cost | an automotive-grade component usually adds cost and no benefit in a temperate cabinet; tell the designer so |
| Target isolation | copper spacings, IEC 60664-1 | the required clearance and creepage follow from the working voltage, the pollution degree, the material group and the altitude: the same barrier voltage can need different distances in two scopes (`pcb-check-isolation`) |
| Software configuration | timing (frequency, sampling edge) | a memory clocked faster than its default needs another sampling edge or a delay; the budget is recomputed at the configured frequency |
| Production stackup | impedances, verdicts that flip between builds | a pair on target on the production prepreg may be off target on the prototype one |

## 4. Rules of conduct

- **Do not decide in the designer's place.** When an answer is missing, make an **explicit** assumption, mark it
  as such, and give the verdict "within this scope". If the verdict flips depending on the assumption, quantify both
  cases and ask; the work that does not depend on the answer goes on meanwhile.
- **Useful exception: showing a limit, an aberration or a shortcut.** E.g.: "the reference tolerance of the
  power mux makes a higher threshold impossible", "automotive grade adds cost and no benefit here", "the surge test does not apply
  to a dedicated supply with a short cable". It is information for deciding, not a decision.
- **A conditional verdict says so in writing**: "pass for a dedicated supply with a short cable", "not applicable if
  the port is not hot-pluggable". The report recalls the scope on the cover.
- **A rule drawn from a standard or from a case is cited with its condition** (type of port, cable length, edition,
  note) and does not apply outside that condition; a value attributed to a standard that was not read in the
  applicable edition is labelled indicative (`failure-modes.md`, section 1).
- **The designer's decisions are traced** (date, reason) and are only reopened if the designer asks for it or if a
  new computation contradicts them (report it then, without deciding).

## 5. Where to record

- `VERIFICATION.md` of the board: "Scope of use" section at the top (answer, source, date; "assumption" if not
  confirmed).
- PDF report: `FIXED["scope"]` → "Scope of use" table on the cover (base `report_base.html`), one row
  per requirement with its status (declared by the designer / assumption).
- Project memory: the decisions and their reasons.

## 6. Working with the designer, beyond the scope

- **Their language and conventions**: decimal separator, date format, vocabulary; the report follows.
- **Their files are theirs**: no change to design files without saying so; a backup before any step that touches
  copper; version control from the first import.
- **KiCad closed while a script writes** (lock files, running process): KiCad rewrites its files on exit. While it
  is open, work on a copy and only read.
- **Nothing is deleted permanently**: move to the trash.
- **Compute rather than assume**; label every estimate; source every value (datasheet, table, line).
- **When a datum is missing, estimate it openly rather than give up**: neighbouring part, qualification level,
  typical value with margin, the designer's own measurement. List it with its basis and the checks it touches; if
  it decides a verdict, ask the designer, who may have it (a measurement, the supplier's answer, the intended
  reading); failing that, it becomes a measurement to request.
- **Do not decide in the designer's place** (§ 4).
- **Prefer parts the designer's assembler stocks**, and check the assembly stock, not only the distributor's.
- **No textbook recommendation that ignores a visible constraint** (placement, layer): first quantify what the
  deviation costs, then propose.
