# Surge, ESD and fast transients: application cases

## Reference chain
The cases below that say "reference chain" use this one. A long-reach single-pair Ethernet port (a field bus over
cable above 30 m, 3.3 V logic), tested line-to-earth at 1 kV, with 2 kV as margin. From the connector: two
capacitors to ground (100 pF each, in the common-mode equivalent 200 pF), optionally a line TVS per line, a
common-mode choke (a few hundred µH, leakage of the order of a µH), two coupling capacitors (rated 100 V), a
second-stage rail-to-rail steering array whose supply pin is a parameter, series resistors (25 Ω transmit side,
1 kΩ receive side in the equivalent), then the PHY pins, whose internal diodes go to the 3.3 V rail and to an
analogue supply. The PHY pins are judged on the current injected into their diodes (limit 100 mA, the latch-up
injection current, an estimate).

## Cases by mechanism
- **Without a clamp at the connector, the coupling capacitors take the wave.** Reference chain, 1 kV, worst choke
  bound, no line TVS: 615–854 V on the connector capacitors and 610–734 V on the coupling capacitors for 100 V
  rated, 12–21 A in the second-stage array, 0.3–0.8 A in the PHY. Teaches: when a series capacitor, a choke and a
  second stage follow an unclamped connector, the first element that can conduct is the weak one, and the
  voltage across everything before it is set by the wave, not by the circuit.
- **The clamping voltage of the first stage sets what the second stage and the PHY see.** Reference chain, array
  supply pin on the 3.3 V: two 33 V parts (clamping ≈ 40 V) → 41 V, 12 A in the array, 0.12 A in the PHY; one
  7 / 12 V dual part → 24 V, 62 mA, but 12 A for 17 A rated (24 A at 2 kV: no margin); two 5 V parts → 11–12 V,
  18 V on the coupling capacitors, 2.2 A in the array, 22 mA in the PHY, 11 A for 30 A rated (23 A at 2 kV).
  Teaches: a low clamp at the connector pushes less current through the choke during the tens of µs of the wave;
  comparing candidates means computing the downstream currents, and checking the IPP at the margin level.
- **A second-stage array works through its supply pin.** Reference chain with the pin floating instead of on a
  capacitor biased from the rail: 0.22 A in the PHY, ten times more. Against one discrete TVS per line behind the
  choke (PHY limit 100 mA, ±1 / ±2 kV): biased array 39 / 50 mA; floating pin 218 / 235 mA; "3.3 V" avalanche
  parts that clamp at 6.0–7.5 V under 1 A: 75 to 126 mA at 1 kV. In that case (that port, those limits) no cheap
  discrete part replaced the biased array. The bias used there was 10 µF with 1 kΩ from the 3.3 V rail. Teaches:
  the clamp of a steering array is the voltage on its supply pin plus a diode drop, so the arrangement of that
  pin is part of the protection and has to be simulated.
- **The surge returns through whichever port is earthed.** Reference chain, level sweep: it holds 2.5 kV with the
  host earthed, with an earthed enclosure, or with a second bus earthed elsewhere (first failure at 3 kV: TVS
  above 30 A); no failure up to 6 kV on a floating host. But **floating host + second bus cabled to a node
  earthed elsewhere fails at 1 kV**: 396 V on that bus's 100 V coupling capacitors, 8.2 A in each of its small
  ESD diodes (4.3 µs, 2.1 mJ, the order of their withstand; estimate), 823 V and 17 A at 2 kV. What matters at
  the remote node is an earthed 0 V **and** a low-impedance path from the pair to it: remote node floating →
  0 V; earthed with only its termination (2 × 50 Ω + 4.7 nF) → 22 V and 2.2 A; earthed with line clamps → 395 V
  (695 V if earthed in DC). Series capacitors block DC, not a surge. Remedies in that case: declare the
  combination out of scope, or 250 V / 500 V coupling capacitors in place of 100 V ones. Teaches: with several
  ports, every one of them is a candidate return path; the single-port model does not show this failure.
- **For ESD, the return inductance of the clamp is the result.** Contact discharge on a multidrop terminal
  (10BASE-T1S-type bus, pins rated ±30 V for a transient), worst case over polarity, termination relay and choke
  inductance: without connector-side diodes, 4.4 kV behind the coupling capacitors, 4.45 kV across a 125 V choke,
  41 V on a ±30 V pin for 260 ns. With two diodes after the coupling capacitors and a 1.5 nH return: 66 V across
  a winding, 30.3 V on the pin (0.08 ns above 30 V), 14 A in the diode. Return swept at 4 kV: 0.5 / 1.2 / 2.5 /
  6 / 10 nH → 42 / 57 / 97 / 191 / 281 V across the winding. Fast transients at 1 kV: 60 V and 28.9 V (935 V and
  31 V for 90 ns without the diodes). Teaches: for a nanosecond edge the clamp voltage is L·di/dt of its return
  plus the diode's own clamp, so a position and a via count, not the part, decide the margin.
- **Behind a choke, a stub asymmetry costs little in a surge.** Stubs to the array of 3.9 nH (two vias) against
  0.7 nH: the voltage across the choke's leakage cannot exceed the connector clamping (≈ 15 V), so di/dt ≤
  15–150 mA/ns and the 3.2 nH of difference give 0.05–0.5 V. No reroute needed, **for the surge**; the same
  asymmetry is judged separately for ESD and for mode conversion. Teaches: bound the effect from the voltage
  the wave can put across the inductance before asking for a layout change.
- **An agreed criterion is coded as agreed.** A ±30 V pin accepted by the designer with 31–32 V for less than a
  nanosecond is judged on both conditions, the peak against 32 V and the time beyond ±30 V against 1 ns; coding a
  strict 30 V flips the verdict with identical numbers, and dropping the duration passes 31.5 V held for 10 ns.
  Teaches: the verdict follows the criterion in force, and a change of criterion is shown before / after.
- **A pin with internal diodes is not judged on its DC voltage range.** Under a 1 kV fast transient a line IC pin
  rated −0.3 V to 4 V reads −0.6 V with 0.3 mA flowing: 200 % of the range, but three hundred times under the
  100 mA injection estimate. Modelled as a bare 5 pF capacitor in an ESD run, a USB data pin reaches 10 V for a
  3.6 V rating in every case. Teaches: the clamp has to be in the model, and the quantity judged is the current
  injected; a model without the clamp cannot answer the question.
- **Same generic name, different brands.** Bidirectional 5 V parts under one name give IPP from 10 to 30 A for one
  brand and 7 to 17 A with 20 to 28 V working voltage for another; a copy of a part can have no TLP point and
  40 V at 1 A where the original gives 38 V at 8 A. Teaches: model and verify the part on the BOM.
- **Model checks at the published points.** A TVS fitted on two maxima (here 11 V at 10 A and 15 V at 30 A)
  gives, in the DC sweep, 11.00 and 15.00 V across the avalanche diode and 11.90 and 15.94 V across the whole
  branch with the blocking diode: 0.9 V on the pessimistic side, written in the report. An isolated `op` at one
  current converged on a non-physical 52 V with the back-to-back pair. Teaches: sweep before simulating; the
  sweep, not the formula, is what is quoted.
- **Heating of the connections.** 19.5 A in 0.5 mm × 35 µm: about 0.1 K; 23.7 A in 0.15 mm × 35 µm: about 1.4 K
  (8/20 µs, `adiabatic_rise_k`). Teaches: for the surge the width of a TVS connection is rarely the issue; for
  ESD it is the length and the vias of the return (on the stackup concerned, 0.31 nH/mm at 0.15 mm width fell to
  0.16 nH/mm at 0.5 mm).
- **Hand check of the earth lead and a validated chain.** Reference chain with the line TVS (two avalanche
  diodes fitted on 11 V at 10 A and 15 V at 30 A), a choke of 470 µH with 1 µH leakage, two 220 nF coupling
  capacitors, array (steering diodes `IS=1e-12 N=1 RS=0.55 CJO=1p`, zener `BV=9 RS=0.55 CJO=16p`, supply pin on
  10 µF to ground and 1 kΩ from the 3.3 V), PHY diodes (`IS=1e-14 N=1 RS=2`) to a 1.11 µF analogue supply behind
  0.5 µH + 0.1 Ω from a 3.3 V rail (12 µF, 22.8 Ω, one-way regulator), earthed host. Hand check: 1 kV behind
  42 Ω into clamps at ≈ 12 V gives ≈ 23.5 A in the earth lead, half in each line TVS. Simulated:

  | Case | Connector capacitors | Coupling capacitors | Array | PHY | Each TVS | Earth lead |
  |---|---:|---:|---:|---:|---:|---:|
  | +1 kV, linear choke | 12.3 V | 15.6 V | 0.26 A | 22 mA | 11.8 A | 23.6 A |
  | +1 kV, ISAT 50 mA | 12.1 V | 15.7 V | 2.33 A | 39 mA | 11.1 A | 23.6 A |
  | +2 kV, ISAT 50 mA | 14.5 V | 19.8 V | 3.06 A | 50 mA | 22.6 A | 47.5 A |
  | +1 kV, ISAT 50 mA, **without the line TVS** | 617 V | 609 V | 21 A | 540 mA | — | 21.6 A |

  Board ground against earth: 58 V at 1 kV (host earthed), 1 009 V with a battery-powered host (the board rises
  with the wave: 0.31 A per TVS, nothing in the PHY). Teaches: the hand value of the earth lead and the
  simulated one agree because the lead sees the clamps, not the rest of the chain; a mismatch points at the
  netlist.
