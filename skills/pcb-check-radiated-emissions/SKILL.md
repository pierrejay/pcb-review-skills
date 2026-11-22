---
name: pcb-check-radiated-emissions
description: "Order-of-magnitude estimate of the radiated emissions (30 MHz - 1 GHz) of a PCB and its cables against CISPR 32 or the applicable product standard (class A / B), giving the admissible common-mode current per cable as a current-probe target, and ranking the risks."
---

# Check: radiated emissions (estimate)

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `radiated_emi.py`: limits, admissible current, loop field, receiver's view of a line code, power-cable common mode;
- `mode_conversion.py`: port asymmetry;
- `conducted_emi.py`: converter source and input network.

## Purpose
Which source on the board is likely to exceed the radiated limit, and what must be measured on the prototype to
know? The check ranks the risks (board loops, each cable) and turns the field limit into a **measurable
criterion**: the admissible common-mode current on each cable, read with a current probe. It does not predict the
field: everything here is an order of magnitude, ±10 dB at best, and it ends with a measurement plan.

## When it applies
- Any board with clocks or a switching converter and at least one cable. The cables are what usually radiates; the
  traces of a board whose signals run over an unbroken ground plane a fraction of a millimetre away (of the order
  of 0.1 to 0.2 mm) enclose a small loop area and rarely do (to be computed: step 1). A trace routed over a void,
  or a two-layer board, does not inherit that conclusion.
- Texts that may apply (the reader confirms which edition and which standard governs the market aimed at):
  CISPR 32 (emissions of multimedia equipment), or the product-family or generic emission standard; CISPR 11 for
  industrial, scientific and medical equipment; FCC 47 CFR Part 15 for the United States.

## Inputs to obtain
- **PCB**: routed length of each clock or fast periodic net (from the layout-audit or timing results); height
  from the signal layer to its reference plane in each stackup that will be built (stackup files; the production
  and the prototype stackups can differ); list of connectors and cables.
- **Schematic and firmware**: frequency and swing of each clock; frequencies set by software (SPI clock, MCU
  system clock) read in the firmware source, for each build.
- **Conducted-emission model** (`pcb-check-conducted-emissions`): input current harmonics of the converter and the
  input network as fitted, for the power cable.
- **Port-network results** (`pcb-check-port-network`): capacitance to ground of each line of a network port, with
  its typical and worst mismatch, for the network cable; line code, symbol rate and amplitude of the PHY.
- **Datasheets**: edge durations (rarely published: an estimate); for an isolated transceiver with integrated
  DC-DC, switching frequency and barrier capacitance if published.
- **Designer**: class targeted (A industrial, B residential) and test distance; enclosure (metal and earthed,
  plastic, bare board); each cable, its type, its length and whether it is shielded.

## Method
1. **Board loops, differential mode** (`loop_field`): loop area from the routed length and the height to the
   plane, the receiver's input capacitance and the line's capacitance per mm; every odd harmonic of the clock up to
   the top of the band, the worst one in 30 MHz – 1 GHz kept, on the stackup that will be tested (Pitfalls).
2. **Cable, common mode** (`cable_field`, `i_adm`): 1 m of cable as a short antenna capped at the half-wave;
   inverted, the **admissible common-mode current**.
3. **Power cable** (`power_cable_cm`): the converter's harmonics up to 1 GHz, on the load case expected to be the
   worst first (the others when the margin is near the limit), injected in the input network as fitted, the LISN
   replaced by an estimated impedance from each wire to earth (`est_z_wire`), ground bonded to the chassis through an
   inductance that is not extracted (swept when the margin depends on it). Above about 100 MHz the result hangs on
   unpublished parasitics: the variants run with them, and without them when the verdict hangs on it. A capacitor
   from the supply wire to the chassis is a branch of the network, never folded into `est_z_wire`. Spread spectrum
   apart.
4. **Network cable** (`mode_conversion.conversion`, `v_rx`, `min_margin`): conversion of the port asymmetry, for the
   capacitance cases of the port-network results, applied to what the receiver sees of the line code; an **upper
   bound** (no transmit filter in the model). The minimum margin over the band includes the breakpoint of the cable
   factor (47.7 MHz for 1 m), not only the points of a list of frequencies. Capacitor-coupled ports only: for a
   transformer-coupled port `conversion` refuses (`coupling="transformer"`); the network-cable row is incomplete and
   the cable's common-mode current is measured with a current probe.
5. **What the calculation cannot give**, named, ranked and sent to measurement: the common mode driven onto every
   cable by the ground plane, the cables whose own signal is clean included; the switching node's capacitance to
   the chassis; a source whose level is not published, such as an isolated transceiver with integrated DC-DC
   (ranked by its barrier capacitance and switching frequency when published, scanned in near field, with the
   footprint of a stitching capacitor between the two grounds provided in case the measurement calls for it).
6. **Margins** in dB (`margin_db`), typical and pessimistic; a zero current (symmetric port, a line at a null of
   the edge's spectrum) has no margin in dB and meets the limit, judged on `I_CM ≤ I_adm`; the measurement plan per
   cable.

## Criteria
| Criterion | Value (indicative) | Source |
|---|---|---|
| Field limit, class A | 40 dBµV/m (30–230 MHz, 230 MHz included: the lower limit at the transition), 47 dBµV/m (230–1 000 MHz), quasi-peak at 10 m | CISPR 32, to be confirmed in the applicable edition (`limit`, `LIMIT_SOURCE`; the user's table with `table=`); the same order as 47 CFR § 15.109 class A at 10 m |
| Field limit, class B | 30 and 37 dBµV/m, same bands and distance | same |
| Admissible common-mode current on 1 m of cable | class A: 13.3 µA at 30 MHz, 8.3 µA (18.4 dBµA) from 50 to 230 MHz, 18.7 µA above; class B: 4.2, 2.6 (8.4 dBµA), 5.9 µA | `i_adm`, computed from the limits above |
| Verdict | margin in dB at the typical case and at the pessimistic bound; a negative or thin margin at the bound means "measure", not "fail" | in-house |

The built-in limits are those at 10 m, in the code as in this table: `i_adm` given another distance `r` applies
them there unless `table=` passes the values of the applicable text for that distance.

## Self-checks
- A clock whose length key is missing from the source JSON fails (no default length).
- Each connector of the board appears in the cable table (count compared with the connector list), with a model
  or "measurement only".

## Tool contract
One board script, `radiated_emissions.py` (named apart from `radiated_emi.py`, the module it imports), numpy
(computation venv); it reads only results of other checks, needs no `pcbnew`, writes
`results/radiated_emissions.json`. Seconds (some 900 harmonics per power-cable variant).
- **JSON**: assumptions (each tagged), `i_adm` table at 30, 50, 100, 150, 230, 300, 500, 1 000 MHz, loops (net,
  length, area, worst frequency, field, margin to class B), cables (worst line, `I_CM`, field, margins A and B, lines
  above class A, lines of zero amplitude, decimated spectrum, spread gain apart, the bond inductance, the limiting
  load case, the cases not run or not established), network cable per case: minimum margin and its frequency
  (`min_margin`), values at 30 to 200 MHz for the table, `limit_source`.
- **Refusals of the board script**: a clock whose length key is missing from the source JSON, a connector without an
  entry in the cable table.

## Pitfalls
- **Plot the envelope of a sinc-shaped spectrum.** Sampled point by point it falls into the nulls, zigzags, and
  shows margin at frequencies where the neighbouring lobe has none.
- **Compute with the stackup that will be tested.** The loop area, hence the field, follows the height to the
  plane: 20·log10 of the ratio of the heights between two stackups.

## Limits
- No enclosure, no shielding effectiveness, no cable resonance other than the half-wave cap, no coupling between
  cables; 1 m of straight cable at 10 m.
