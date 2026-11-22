---
name: pcb-check-chassis-grounding
description: "Ground, enclosure and shield strategy of a PCB: how fixing points, connector shells and cable shields tie to ground (directly, through a capacitor or not at all) in a plastic, floating metal or earthed metal enclosure; connector protections, parasitic capacitances, ESD on shields (ngspice), dielectric stress in the laminate, common-mode current paths."
---

# Check: chassis ground, shields, common-mode paths

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `estatic2d.py`: field solver;
- `edge_field.py`: convergence at fixed reading distance, extrapolation to the copper surface;
- `kicad_copper.py`: copper per net, overlaps, parallel-plate capacitance;
- `iec60664.py`: `clearance_f2`, the indicative air clearance for a transient overvoltage;
- `tvs_fit.py`: `esd_expected`, `esd_check`, the check of the discharge generator;
- `models/cwg_iec61000-4-5.lib`: combination-wave generator, for the surge on a shield (step 3b);
- `models/esd_iec61000-4-2.lib`: discharge generator;
- `spice.py`: `run`, the launcher of every netlist (results only from a run that reached its stop time).

## Purpose
How should signal ground be tied to the enclosure, to the fixing points and to the cable shields, and does that
choice hold? For the strategies and installations of the scope: the voltage an electrostatic discharge puts between
the touched copper and ground, the resulting stress in the laminate and on the tie components, the path taken
across the board by the common-mode current of a cable event. The designer chooses; the check computes first the
configuration expected to be the worst and proposes the others, including those an installation manual could
allow by mistake.

## The strategy space
No strategy is right by default; the designer's scope gives the candidates.

- **Enclosure**, typically one of three:
  - *plastic, or none*: the board floats; a discharge reaches the copper the user can touch (connector shells,
    shields, screws) and returns through the board's capacitance to its surroundings and through the cables;
  - *metal, floating* (not earthed): a large capacitance to the surroundings, and the first electrode a discharge
    meets; the voltage between enclosure and board ground is set by the capacitive divider between them;
  - *metal, earthed* (strap to protective earth): the reference toward which discharges and cable common-mode
    currents flow; what matters is the path they take across the board to reach it.
- **Tie of each conductive part** (fixing holes, connector shells, cable shields), each one of:
  - *direct to ground* (plated holes on GND, shell on GND): lowest impedance, no voltage between that part and
    ground; the common-mode current of the cables crosses the board's ground on its way to the enclosure;
  - *through a capacitor* (often with a bleed resistor for static charge): blocks DC and low frequency (earth
    potential differences, mains loops), stays a path at discharge and burst frequencies; the capacitor and the
    laminate around the part then hold the voltage;
  - *not connected*: only parasitic capacitance ties it (Pitfalls). Kept only when the part cannot be touched and
    no cable current reaches it.
  A separate chassis net on the board (a copper area tied to the enclosure, with a link or a capacitor to ground)
  is one way of grouping these ties, not a requirement.
- **The far end of each cable**: a peer earthed or floating, a shield earthed at the other end, a supply whose 0 V
  is earthed, a host on battery. The far ends decide where low-frequency, surge and burst currents return; a
  strategy that looks sound on the board alone can carry current through it (an earth difference between the two
  ends of a shielded cable, a surge returning through the coupling network of another port).

## When it applies
- As soon as a cable leaves the enclosure or a conductive part of the board can be touched, whatever the strategy,
  including boards with no chassis net at all (shields and holes on ground).
- The scope of use sets the cases: enclosure type, where the 0 V of the supply is earthed, which cables leave and
  what is at their far end, what the user can touch, the test levels.
- Bare board with no cable leaving a protected volume: only step 1 (protection close to each connector) remains.
- Texts that may apply (the reader confirms which edition and which product or generic standard governs the market
  aimed at): ESD, IEC 61000-4-2; electrical fast transients, IEC 61000-4-4; surge, IEC 61000-4-5; clearances and
  creepage, IEC 60664-1; the laminate's dielectric strength is a datasheet value measured by a method the datasheet
  names (e.g. an IPC-TM-650 method). Levels are those of the scope; the values commonly used in design, indicative,
  are listed in `pcb-check-surge-esd`.

## Inputs to obtain
- **PCB**: chassis net names; copper of every net per layer (zones filled); stackup (dielectric thickness and
  εr between adjacent layers, copper thicknesses, solder mask); pad and drill diameters of the through-hole pins
  on chassis nets and their clearance to the inner planes; position of connectors, chassis screw, free holes.
- **Schematic**: per connector the protection parts or first stage on the cable side; the tie of each shell,
  shield and fixing point (direct, capacitor with or without bleed resistor, link or jumper, none); terminations
  that end on a shell or shield net (e.g. the common-mode termination of a connector with integrated magnetics,
  such as an Ethernet jack) and the net the datasheet asks for their end.
- **Datasheets**: tie capacitors (rated voltage, dielectric class, DC-bias curve), laminate dielectric strength
  with its test method and thickness (a laminate datasheet often gives a specification minimum and a typical
  value), isolation voltage and inter-winding capacitance of any magnetics or isolator on a cable.
- **Designer**: enclosure type and earthing, how the board is fixed (metal screws and spacers or not), length of
  the enclosure's earth strap, what each cable meets at its far end, candidate strategies, test levels.

## Method
1. **Geometry from the PCB** (`kicad_copper.copper_by_net`, same distance function as `pcb-check-isolation`):
   chassis copper per layer and its minimum distance to every other net, nearest first; per connector, the
   distance from its pins to each protection on a shared net, the label saying what is measured.
2. **Parasitic capacitance** chassis ↔ ground and chassis ↔ chassis, from the copper overlaps of each pair of
   adjacent layers (`overlap_area_mm2`, `parallel_plate_pf`).
3. **Contact discharge on the touchable parts** (ngspice): first the part and installation expected to be worst
   (the weakest tie: an open link, else a capacitor; cables unplugged), at the level of the scope; the other parts
   (shields and shells on ground included, enclosure, screws), plugged cables and positions near a limit or on
   request. A tie component fitted on the board is present in every position (a capacitor across a jumper is not
   an option once soldered); magnetics and isolators carry their inter-winding capacitance, and a termination that
   ends on a shell or shield net goes to the net the board gives it. The defaults of the model are estimates,
   replaced by the board's values where known.
3b. **Surge on a shield or shell tied to ground through a capacitor** (combination wave applied to the shield
   itself, at the level of the scope, ground first held to earth by another path; the margin level and the other
   installations near a limit): what holds ground to earth decides whether the whole surge stands between the
   shield copper and the ground planes. A distributed shield–ground capacitance helps at ESD and above the tie
   capacitor's self-resonance, and does nothing during a surge but put a thin dielectric under its voltage: weigh
   both.
4. **Field in the laminate: the bound first**, per kV and scaled to the peaks of steps 3 and 3b. A bound that meets
   the criterion is the result, its margin a lower bound reported as such. Outside the domain where its factor k
   was fitted (another build, prepreg or copper thickness), k is checked by one fine calculation before the bound
   is relied on.
5. **Field in the laminate: fine calculation** (`estatic2d`, `edge_field`), only where the bound misses the
   criterion or the designer asks for the margin itself: the field judged is the surface field, from series
   converged at a fixed reading distance and extrapolated to the copper (`references/method.md` § 3). The meshes
   are planned within memory before running.
6. **Common-mode paths** (ngspice): the ground plane in nodes at the cable entries, linked by its partial
   inductance (an estimate: a range when the result depends on it); each cable to what it meets at its far end;
   first the event and cable expected to load the plane most; the other surges and fast transients, and the
   candidate HF ties, near a limit or on request.
7. **Strategy × installation table**: the configurations computed → peak voltages and margins; those not
   computed listed with their reason.
8. **Margin**: the field of the most severe of the geometries computed (bound or fine calculation) × each peak
   voltage of steps 3 and 3b, against the laminate strength.

## Criteria
- Each protection within a few millimetres of its connector and on the signal's path (in-house rule; the
  mechanism is the inductance of the track between the connector and the clamp, which adds to the clamping voltage
  at a nanosecond edge).
- Edge field at the required discharge level **and at the surge level** (step 3b) ≤ the laminate's specification
  minimum (laminate datasheet, with its test thickness; a short-time AC test in a near-uniform field, which makes
  the comparison prudent for a 50 µs impulse, as the report says); the margin is stated; ≥ 2 is comfortable
  (in-house). Read as in step 8.
- Tie capacitors below their rated voltage; isolation of magnetics or isolators not exceeded at the surge level
  (component datasheet; an rms test voltage is compared through its peak); a capacitor inside a termination
  (e.g. in an Ethernet jack, when its drawing gives it) below its rating.
- Bleed resistor across a shield capacitor: its working and overload voltages (e.g. 75 V, and 150 V for 5 s) are DC
  ratings and **not** the criterion under a discharge. Judge it on the manufacturer's pulse or ESD withstand when
  published (single-pulse curve; an ESD test of the component qualification family, e.g. AEC-Q200-002); otherwise
  report the voltage with the energy it takes (V²·t/R: 1.5 kV for 100 ns in 1 MΩ is 0.2 µJ) and the air gap
  between its terminals against flashover (clearances of IEC 60664-1, `pcb-check-isolation`): an estimate, and a
  pre-compliance shot if the verdict depends on it.
- Surface distances in air between chassis and ground copper against the clearances of IEC 60664-1 for a transient
  overvoltage (indicative values: `iec60664.clearance_f2`; `pcb-check-isolation`) when the two can be separated.
  Those clearances are given for a 1.2/50 µs impulse; under a discharge of a few nanoseconds they are a screening
  value (`verdict_threshold(…, screening=…)`). A gap below it is a possible flashover, which ties chassis to ground
  at that point once the voltage has built up: the direct tie at that position, which never lets it build up, does
  not bound it. It is a finding when that tie fails or the scope needs chassis and ground kept apart, and otherwise
  a reservation with a pre-compliance shot, unless the arc's transient is bounded.
- No position that the manual allows ends with a margin below 1.

## Self-checks
- A protection reference of `PROTECT` absent from the board is reported as a finding, not dropped; the list is
  compared with the schematic at each revision.
- The copper area of the chassis nets per layer and the list of their pads are printed and read once: a missing
  zone (unfilled file) or an NC pin renamed "unconnected-…" by a cleanup shows there.
- Before the first real result (`references/method.md` § 5): the capacitance of one overlap of the board by hand,
  the generators alone against the nominal values of the standard scaled to the level.
- Edge field: convergence at fixed reading distance demonstrated and extrapolation to the surface validated by its
  residual (`edge_field.edge_field_study`, or `require_converged` then `surface_field`); the run fails otherwise.
  A series at fixed `guard` is never reported as a convergence series.

## Tool contract
Five scripts, one JSON each in `results/`. `chassis_geometry.py`, `chassis_caps.py` (KiCad's bundled Python, `pcbnew`) →
`chassis.json`, `chassis_caps.json`; `esd_chassis_sim.py` (venv + ngspice; reads `chassis_caps.json`; discharge cases of
step 3 and surge cases of step 3b) → `esd_chassis_sim.json` + waveform figure (20 ns and 300 ns; the surge over its
duration); `field_stress.py` (venv, numpy/scipy; reads `esd_chassis_sim.json`; the bound for every geometry, the fine
calculation only where it does not decide) → `field_stress.json` + field map when the fine calculation ran;
`cm_paths_sim.py` (venv + ngspice) → `cm_paths_sim.json`.
- **JSON**: distances chassis → each net; capacitances per net pair and layer pair; per discharge case and per
  surge case the peaks (and the voltage on the tie capacitor); per geometry the bound per kV, and where the fine
  calculation ran the converged readings, fitted R, residual, surface field per kV; then field, its origin (bound
  or fine) and margin per case; per common-mode event the plane current, ΔV (per plane inductance), screw and cable
  currents, magnetics and shield-capacitor voltages.
- **Refusals**: a geometry refused by a shared module quotes no field; a `PROTECT` reference absent from the board is a
  finding (self-checks), not a filter.

## Pitfalls
- **A part left unconnected is not separated at discharge or burst frequencies.** Its parasitic capacitance and,
  beyond, a flashover take the place of the tie: the voltage builds until something flashes over. Present "not
  connected" (or an open jumper) only with its computed voltage, not as a neutral position.
- **Compute the stress instead of judging a clearance by a table, and look at the capacitive divider first.**
  When a small coupling capacitance faces a large enclosure capacitance, the voltage divides across the small one:
  enlarging a clearance does not help if the facing copper that carries the coupling remains (a wider antipad
  leaves the overlap through the prepreg), and the capacitor in series, not the clearance, holds the voltage.

## Limits
Plane inductance estimated, not extracted; the enclosure is a single node (its inductance between two screws is
ignored); parasitic capacitances without edge effect; laminate interfaces and manufacturing defects outside the
model; air discharge not modelled. The immunity criterion of fast transients allows a temporary disturbance:
the real effect on the link and on the processor is judged at the test, as is the discharge withstand in
pre-compliance.
