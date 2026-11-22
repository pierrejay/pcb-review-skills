# Configuration and interface wiring: application cases, the other pitfalls

## Cases by mechanism
- **A strap shared with a LED can sit between the thresholds.** Setting: a strap pin pulled down by 2.49 kΩ, with a
  red LED (1.8 V forward drop) fed from 3.3 V through 1 kΩ on the same pin; the pin thresholds are VIL 0.6 V and
  VIH 1.3 V. Computed with `strap_level`: 1.07 V, and 0.99 V once the internal pull-down of the pin (taken at
  9 kΩ, an estimate) is added: undetermined in both cases, to correct (LED moved or buffered, or pull value
  changed). Without the LED the pin sits at 0 V (low). Teaches: the script sees the right resistor and passes;
  only the level calculation of step 4 shows the pin between the thresholds.
- **A strap is decoded against what it must agree with elsewhere.** Setting: a PHY strap that selects the 50 Ω
  receive tap, a strap giving the device address, a strap that moves a data-valid signal onto a shared pin. Result:
  the first is right only with the 50 Ω / 2 kΩ network actually fitted on the port, the second only against the
  other devices of the same management bus, the third against the MAC or the back-to-back PHY that reads it.
  Teaches: a strap table row is decoded together with the circuit the strap refers to.
- **A strap can change the polarity or the direction of a pin.** Setting: a clock pin that is an output by default
  and becomes an input through a pull on another strap pin; a LED pin whose active level follows its strap.
  Result: without the pull the clock pin fights the SoC clock output; the LED must be checked off with the link
  down, without any register write. Teaches: read the default direction and polarity of every strapped pin and
  see which strap changes them.
- **"Allowed" is not "advised".** Setting: a select pin that the datasheet permits to leave floating for one
  supply option but advises tying for immunity. Result: tie it (e.g. to a neighbouring ground pin); reported as a
  recommendation with its reason, not as a deviation. Teaches: separate what the datasheet requires from what it
  advises.
- **A threshold set by a divider carries the tolerance of the reference.** Setting: a power mux in priority mode
  with a divider at 0.233 × the input and an internal reference of 0.92–1.08 V. Result: it switches somewhere
  between 4.0 and 4.6 V; with no hysteresis specified the switchover is clean only if the input falls fast.
  Teaches: a switching window, not a value.
- **Interface review is a line-by-line comparison with the datasheet figure.** Setting: RJ45 centre taps through a
  capacitor to ground for a voltage-mode PHY, terminations already internal to the PHY, USB series resistors and
  Rd as in the reference design, an RS-485 driver on a 3.3 V bus-side supply. Result: no external 49.9 Ω where
  the termination is internal; the RS-485 driver meets |VOD| ≥ 1.5 V on 54 Ω with no margin, and its 100–135 mA
  while transmitting go into the power budget. Teaches: an interface that "looks like the reference" is checked
  on every pin, and its supply current goes to the rail budget.
- **A manufacturer's decoupling recommendation can resonate with the ferrite it marks optional.** Case: the analog
  supply of an Ethernet PHY, network of its datasheet = optional ferrite, then 1 µF + 100 nF + 10 nF; 3.3 V rail
  with 2 × 10 µF of bulk; the ferrite from its manufacturer's SPICE model (about 0.25 µH and 66 mΩ at low
  frequency). In that case:

  | At the pin | No ferrite, < 1 / 1–10 / 10–100 MHz | Ferrite, < 1 MHz | Ferrite, max gain | Dip, 20 mA |
  |---|---|---:|---:|---|
  | 100 nF alone | 0.14 / 0.66 / 0.66 Ω | 14 Ω | +23 dB at 1 MHz | 2 / 33 mV |
  | 2 × 100 nF | 0.14 / 0.71 / 0.23 Ω | 16 Ω | +21 dB | 2 / 24 mV |
  | 100 nF + 1 µF | 0.14 / 0.17 / 0.23 Ω | 4.2 Ω | +17 dB at 0.38 MHz | 2 / 12 mV |
  | 100 nF + 10 µF 0402 | 0.12 / 0.05 / 0.23 Ω | 0.45 Ω | +11 dB at 0.16 MHz | 2 / 5.5 mV |
  | 100 nF + 10 µF 0603 | 0.11 / 0.06 / 0.24 Ω | 0.28 Ω | +9 dB at 0.12 MHz | 2 / 4.5 mV |
  | 10 nF + 100 nF + 1 µF + 10 µF | 0.11 / 0.04 / 0.14 Ω | 0.27 Ω | +9 dB | 2 / 4.3 mV |

  (Dip: without / with the ferrite.) The recommended network resonated with the ferrite (4.2 Ω near 0.4 MHz, rail
  noise amplified by 17 dB at the pin); a larger effective capacitance in the same footprint lowered both while
  keeping the ferrite's attenuation at tens of MHz (about 40 dB at 25–50 MHz for that part). What it teaches: a
  recommended network is computed like any other, with the ferrite's own model.

## The other pitfalls
- **A mode forced through a register can defeat the partner's negotiation.** Example: forcing a speed through the
  control register of an Ethernet PHY facing a port in auto-negotiation leaves the duplex to parallel detection,
  which selects half duplex; advertise only the wanted speed and restart auto-negotiation.
- **Treat a schematic net that reaches a pin through an unnamed component as a schematic ↔ PCB difference.**
  Components without reference designator ("?") exist in the schematic and not on the PCB: to fix at cleanup.
