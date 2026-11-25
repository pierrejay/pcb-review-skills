---
name: pcb-check-surge-esd
description: "Surge, ESD and fast-transient simulation (IEC 61000-4-5, -4-2, -4-4 may apply) of a PCB's signal ports in ngspice, across the ground-return configurations: whether a port survives, which TVS to fit and where, chosen by its clamping at the current actually seen."
---

# Check: surge, ESD and fast transients on signal ports; choice of protections

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `tvs_fit.py`: TVS fit, return inductances, connection heating, generator check values, metrics of a simulated
  trace (`time_beyond`, `rail_ratios`);
- `models/cwg_iec61000-4-5.lib`, `models/esd_iec61000-4-2.lib`: generators;
- `spice.py`: `run`, the launcher of every netlist (results only from a run that reached its stop time).

## Purpose
For each signal port that leaves the enclosure: under the standard pulse, does every component between the
connector and the IC pins stay inside its ratings, in the ways the product can be earthed? If not, which
protection, placed where, brings it back inside, and up to what level does the design then hold?
Power inputs: `pcb-check-power-input`; shields and enclosure: `pcb-check-chassis-grounding` (including a surge
applied to a cable shield tied to ground by a capacitor, its step 3b: the line-to-ground surge on the conductors
does not cover it).

## When it applies
Tests depend on the port type and the declared cable length. Texts that may apply (the reader confirms which
edition and which product or generic standard governs the market aimed at): ESD, IEC 61000-4-2; electrical fast
transients, IEC 61000-4-4; surge, IEC 61000-4-5; conducted RF, IEC 61000-4-6; levels per port type, the generic
immunity standard for the environment (IEC 61000-6-1 / -6-2) or the product-family standard. The values below are
the ones commonly used in design for an industrial environment, indicative.

| Port | Tests | Level simulated (indicative) |
|---|---|---|
| internal to the enclosure | none | — |
| external, short cable (of the order of 3 m or less; e.g. USB) | ESD | 4 kV contact (8 kV as margin) |
| external, longer cable (above about 3 m) | + fast transients, conducted RF | 1 kV through the capacitive clamp |
| external, cable declared above about 30 m (e.g. a long-reach field bus) | + surge, line-to-earth | ±1 kV (±2 kV as margin) |

A bus whose declared length stays under the surge threshold (e.g. a multidrop bus limited to 25 m) takes ESD and
fast transients, not the surge; an isolated port is judged on its barrier (`pcb-check-isolation`). Enclosure and
earthing change the **return paths**, not the levels: a parameter of the simulation, not a reason to skip it.

## Inputs to obtain
- **Schematic**: the chain end to end (connector, capacitors to ground, line protection, filter or common-mode
  choke, coupling capacitors, second-stage protection, series and termination resistors, IC pins; an Ethernet
  port, with its magnetics and PHY, is one instance; a USB, CAN, RS-485 or UART port has its own, shorter chain:
  write the one of the port at hand); the rails behind the line IC's internal diodes, their capacitance and the
  ICs on them; what the supply pin of any rail-to-rail array is tied to.
- **PCB**: ground return of each protection (pad → track → via → plane: lengths, plane depth), distance to the
  connector, chassis track nearby.
- **Datasheets, for the part number of the BOM**: TVS (VRWM, VBR min/max, clamping voltage at several currents:
  table, curve, TLP for ESD parts; IPP in 8/20 µs; capacitance); choke (inductance and tolerance, resistance,
  leakage inductance, saturation in common mode if published, parasitic capacitance, withstand voltage **and how
  it is defined**); capacitors (rated voltage, dielectric class); line IC (absolute maxima of the line pins and of
  the supplies, pin capacitance) and every other IC on the same rails (absolute maxima); regulators (they source,
  they do not sink); effective capacitance of the rail capacitors under DC bias.
- **Designer**: test level per port, enclosure, where earth can come from, what each *other* port is cabled to
  (earthed or floating equipment), criteria already agreed.

## Method
1. **Common-mode equivalent** for the surge on a symmetric pair: shunt doubled, series halved, source impedance
   generator + coupling resistors in parallel (`tvs_fit.common_mode_source_ohm`); ESD on **one** line, both lines
   modelled; fast transients through the capacitive clamp.
2. **Generators** from `lib/models` (ESD: `uic`); fast transient 5/50 ns: `EXP` behind 50 Ω. The run lasts until
   the slowest LC network has given its maximum (`references/method.md`, algorithm, step 2).
3. **Choke, surge**: saturable inductance + parallel losses, leakage and resistance in series; the saturation
   current is a bound: first the datasheet's value or, if unpublished, a low stated one; linear near a limit.
4. **Choke, ESD / fast transients**: coupled windings **with the parasitic capacitance** (it passes the edge);
   inductance nominal, / 10, / 100: the one expected to be worst first.
5. **Protections**: each TVS fitted on the BOM part near the current seen (`tvs_fit.avalanche_fit`, `quick_fit`
   for candidates); array = steering diodes + zener, supply pin a parameter.
6. **Line IC, other ICs and rails**: internal diodes of each pin (to its supply and from ground) behind the real
   series resistors, for the surge, ESD and fast transients alike, plus the pin capacitance (an estimate if
   unpublished); rail = its effective capacitance, a constant, board unpowered. The charge injected into a rail
   divided by its capacitance says how far it rises: far from its bound, a fuller model adds nothing; near it,
   propose the powered model (+ typical load + one-way regulator, from the operating point).
7. **Ground returns as inductances** (`tvs_fit.return_path_nh`, from the routed geometry): estimates, run at twice
   the value as margin.
8. **First case**: this local model of the port, the ground configuration expected to be worst, at the test level,
   both polarities if the chain is not symmetric. Near a limit, propose the other `GROUNDS` (each port a candidate
   return path), choke bounds, the level sweep and a doubled stop time; write those not run with their reason.
9. **Choosing protections** on the clamping at the current actually seen; check VRWM, capacitance per line, IPP at
   the margin level, BOM part number; connection width by `adiabatic_rise_k`.
10. **Verdict** per case from `metric / LIMITS`.

## Criteria
| Quantity | Limit | Source |
|---|---|---|
| Voltage of each capacitor on the path | rated voltage | component datasheet |
| same, ceramic capacitor in a nanosecond pulse | a multiple of the rated voltage (2.5 × as a screening value) | estimate (ceramic withstand test), said as such |
| Peak current of each TVS | IPP (8/20 µs); beyond it the model means nothing | datasheet |
| Choke | withstand voltage as the datasheet defines it (between windings); the voltage across a winding reported beside it, with its duration | datasheet |
| Each rail | both absolute-maximum bounds: the lowest maximum and the highest minimum (e.g. −0.3 V) of all the ICs on it | every IC's datasheet |
| Supply pin of a rail-to-rail array | its VRWM | array datasheet |
| IC pin with internal ESD diodes, transient | injected current: latch-up injection current (surge); ESD and fast transients: HBM rating / 1.5 kΩ | **stated estimates**, see below |
| IC pin without internal clamp (rated for a transient voltage) | that voltage | IC datasheet |
| IC pin with a protection its datasheet documents (an internal zener behind a recommended series resistor) | the current into that clamp, the clamp modelled | IC datasheet |
| Line in operation | below VRWM and below a snap-back part's snap-back voltage | datasheet |

Limits are read in the script's `LIMITS` table with their source. **A pin with internal diodes, whose DC absolute
maximum range sits close to its rails, is screened on the current injected into them.** That range is a DC rating:
under a transient the pin sits at its rail plus a diode drop whenever the diodes conduct, so it is exceeded in every
case, whatever the current, and does not tell one protection from another; it does not describe the pin's transient
withstand either. The voltage stays the criterion for rails and for pins rated for a transient voltage without
internal clamp. The screening limits of the injected current are estimates, listed in the report (often
unpublished for a line pin; the datasheet's value when it is): for a surge, the injection current of the latch-up
test of the IC qualification standard (JESD78; 100 mA is the value commonly quoted, for a duration far longer than
a surge); for nanosecond events, the IC's HBM rating as a peak current (V_HBM / 1.5 kΩ: a 2 kV rating gives
1.33 A, a pulse of about 150 ns). Neither is a withstand of the pin: a peak current leaves out the duration, the
edge rate, the internal path and the IC's own protection, and a component-level ESD rating does not predict the
robustness of the system. They rank protections and locate the stress. A distance to a threshold whose uncertainty
is not bounded does not establish survival, however wide, and an excess over it does not establish a failure: a
verdict that rests on these estimates is never a plain pass nor a fail (`report_base.verdict_threshold(…,
screening=…)`: to be measured above, a reservation below). Below it is a reservation with the measurement to make, or, when the margin is
comfortable and the designer explicitly accepts the estimate as an assumption, a pass * (`pcb-verification`, "What a
verdict means"). Survival is concluded only from transient data for that pin (the manufacturer's system-level or TLP
figures) or from a test. Under an agreed criterion, the excess over the limit it relaxes is still reported.

## Self-checks
- The bounds of a judged rail are the lowest maximum and the highest minimum of the ICs on it, listed from the
  PCB (each part with a pin on the rail's net, oscillators and memories included), with their datasheet values;
  a part that publishes none gets a pessimistic bound listed as an estimate (e.g. its supply tolerance).
- Each TVS model checked by a `dc` sweep at the published points before any transient
  (`tvs_fit.dc_check_netlist`), not by a single `op`: the back-to-back model can converge on a non-physical
  point, and a model fitted on the maximum values can sit a fraction of a volt to a volt off the datasheet. A
  blocking diode in series adds its drop: the branch is then pessimistic by that amount, written in the report.
- Generators checked alone against the values held in `tvs_fit` (`CWG_CHECK` with `cwg_check`, `ESD_PER_KV` with
  `esd_check`).
- Order of magnitude by hand on one case (`tvs_fit.hand_check_earth_current`): (surge peak − clamp) / source
  impedance in the earth lead, split between the line TVS.
- A powered case: with the generator left out, each rail holds within 1 mV of its operating point.
- Any rail or node that moves while **not on the current path** is investigated before it is written.
- Any voltage sitting exactly on a model's `BV` means the model clamps: rerun without breakdown and report the
  current and energy the real part would have taken.

## Tool contract
Venv Python (numpy) + ngspice; each script writes its netlists, runs them with `spice.run`, reads the measures and the
`wrdata` files and writes one JSON in `results/`: `surge_<port>.py` → `surge_<port>.json`; `esd_<port>.py` →
`esd_<port>.json`; when proposed, `surge_<port>_sweep.py` (imports the first) → `surge_<port>_sweep.json` and
`tvs_candidates.py` (swaps one protection block for candidates).
- **JSON**: per case and ground, max |x| of each probe (maximum and minimum for rails), for ESD the time beyond each
  limit, `ratio` per key, worst key, verdict; sweep: per series the level withstood (a series failing at its first level
  is "below the first level", not "holds 0.5 kV"), the first failing level and its limit. The printed table flags
  each exceeded cell.
- **Refusals of the board scripts**: a BOM part number not matching the model; a node named `gnd` (node 0 for
  ngspice).

## Pitfalls
- **A straight line from VBR to VC at maximum current is not the clamping behind a choke.** At the small currents
  seen there it misrepresents the clamping and can flip a verdict either way, a fail into a pass when the real
  points sit above the line: read the clamping at that current on the BOM part's datasheet.

## Limits
Choke saturation in common mode unknown (bounded, not measured); 8/20 withstand of ESD arrays generally
unpublished (their current is reported, not judged); internal diodes generic (a small series resistance); cables
not listed with the designer absent (pessimistic for the clamp of the port under test, which takes the whole
current; not for the parts between two ports: `references/method.md`, "Ground-return configurations"); the
configurations, bounds and levels not run; return inductances, effective capacitances: estimates; air discharge
and the real coupling of a fast-transient clamp to the harness not modelled. Fast-transient immunity allows a
temporary disturbance (criterion B of the standard): judged at the test. The simulation ranks solutions and finds
the weak component; pre-compliance shots confirm.
