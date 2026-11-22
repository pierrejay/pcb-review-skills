---
name: pcb-check-configuration
description: "Configuration and wiring check of a PCB against datasheets and the reference design: bootstrap straps, device addresses and modes, MCU boot/debug pins, interface wiring (e.g. Ethernet magnetics, USB, RS-485, power mux), supply-pin networks and decoupling."
---

# Check: configuration (straps, addresses, modes) and interface wiring

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `kicad_config.py`: `read_pulls` (pulls seen from a pin), `pin_networks` (the parts around every pin of an IC, with the
  net of their far end), `decoupling_rows` (screening of the supply pins, step 6c);
- `values.py`: `ohms` (resistor values);
- `clock_compat.py`: `strap_level` (DC level of a shared strap pin), `compare` (paper comparison of guaranteed values);
- `decoupling.py`: `pin_impedance` (impedance seen from a supply pin, per band);
- `mlcc_bias.py`: effective capacitance of the decoupling capacitors under the pin's voltage;
- `spice.py`: `run`, kind "once", the launcher of the decoupling netlist when it runs in ngspice.

## Purpose
A board can be routed perfectly and still not start because a strap reads the wrong level, two devices answer at
the same address, or a pin that is an output by default fights another driver. This check answers two questions:
is every configuration pin wired to the level its intended mode requires (by script, on the PCB), and is every
interface wired as its datasheet and the manufacturer's reference design ask (schematic review, pin by pin)?

## When it applies
- As soon as the board has pins sampled at reset or power-up: bootstrap pins of line interface ICs (PHYs,
  transceivers), bus addresses, MCU boot-mode pins, boot options of a controller, USB-C CC pins, enable pins of
  oscillators, pulls of reset, interrupt, chip-select and management-bus lines.
- The scope of use changes the expected table, not the method: which populated variant is fitted, which speed and
  mode the firmware uses, which device is the clock master, which addresses the device tree declares.

## Inputs to obtain
- **PCB** (`.kicad_pcb`): pads and their nets, two-pad resistors and their Value field.
- **Schematic**: the intended mode of each device (text notes, net names), the netlist for the interface review.
- **Datasheets** of every IC that has a pin sampled at reset or an interface: strap tables (pin, internal pull with
  its value or spread, levels and what each selects; a strap can be two-level or multi-level); VIL / VIH or the
  level windows of the strap pins, and VOL / VOH with their test currents for pins that become outputs; the
  default direction of every pin and what changes it; the boot-configuration section of a microcontroller or
  controller; the application chapter, the table of recommended external components and the layout chapter.
- **Manufacturer's reference design**: the reference architecture figure of the datasheet; the schematic and BOM of
  the evaluation board, latest revision (a manufacturer corrects its own board): series resistors, decoupling per
  rail, reset network, power-up order.
- **Designer**: intended mode of each device, which variant is populated, what is decided by software.
- **Firmware**, in the source of each build: addresses declared in the device tree, registers written at start-up,
  speed and auto-negotiation settings, clock-tree configuration.

## Method
1. **Expected wiring**: for every pin whose level at reset selects something, the datasheet table decoded into the
   list of its pulls `(ohms, rail)`, one entry per resistor; the empty list leaves the pin to its internal pull.
2. **Pulls found** (`read_pulls`): the resistors from the pin's net to a rail, as assembled in the variant read,
   also behind a series resistor of at most `SERIES_MAX` (100 Ω): the pull may sit on either side of it.
3. **Comparison** as sorted lists: two equal resistors in parallel count twice.
4. **Shared strap pin** (LED and its resistor, another input, a data line; `strap_level`): DC level at reset from
   everything on the net, with the internal pull of **every** IC pin on it at its datasheet spread. When the pin
   becomes an output after reset, the pull is also its load: the row gives the window of values the two conditions
   leave and where the fitted value sits in it.
5. **Around the straps**: distinct addresses on the management bus; master / slave consistent with the clock
   source; repeater modes back to back; common reset; LED load and polarity; a pin that is an output by default and
   becomes an input through another strap; MCU boot and debug pins; the manufacturer's reference architecture. The
   order between the supplies of each IC, and "clock present at power-up, else reset after the clock", are judged
   in `pcb-check-power-rails` (step 10).
6. **Interface wiring** against datasheet and reference design, pin by pin (e.g. Ethernet magnetics, USB, isolated
   RS-485, power mux, SoC core supply and reset): every note of a datasheet (under a drawing, in a table footnote, a
   "must" of the application chapter) is a requirement with its own row; every pin on a shell or shield net is
   judged on its own row, not as part of the net.
6b. **Supply, regulator-output and reference pins of every IC** (VDD, VDDIO, DVDD, a driver regulator such as
   VDRVN, VREF, CEXT…; `pin_networks`), one row per pin: the parts on its net with the net of **their other pad**,
   and the series parts (e.g. an input ferrite), against the application diagram **and** the evaluation board. A
   part on another net than the datasheet asks, or a part or value the datasheet states as a requirement that the
   board lacks, is a deviation; a difference from a typical application or from the evaluation board is judged by
   calculation (`../pcb-verification/references/qualitative-rules.md`).
6c. **Decoupling of the supply pins**: `decoupling_rows` screens the pins worth computing (its parameters select
   what to compute, they are not rules); `decoupling.pin_impedance` gives each one row: its impedance per band from
   the effective capacitances of the fitted network. Variants (with and without the ferrite, DCR corners, other
   capacitors, a remedy) are computed when the designer asks or a row shows a problem. Without a requirement
   (Criteria), the rows are recommendations with no verdict; the wiring of 6b stays a deviation. Exceptions are
   declared with their reason (a hot-plug input kept small on purpose, a feedback pin on a rail).
7. **Two ICs sharing signal nets** (e.g. two PHYs back to back on their MAC interface): one pull serves the strap of
   the IC whose pin is an output at reset; the role column says which device the pull is meant for.

## Criteria
- Each strap is wired to the level the intended mode requires (datasheet strap table, section quoted).
- A strap pin loaded by something else settles below VIL max or above VIH min of that pin (datasheet); a level
  between the two is undetermined and fails (`strap_level` state "undetermined").
- A pull on a pin that is an output after reset draws at most the current at which the datasheet guarantees VOL
  (and VOH).
- A guaranteed value of a source outside the range its receiver requires (duty cycle, jitter, level) fails the
  rule. Comparison at equal definition and the effect: `pcb-check-clock-integrity` (`clock_compat.compare`).
- RS-485 driver output: texts that may apply are the RS-485 standard (TIA/EIA-485, ISO/IEC 8482) and the
  transceiver datasheet; a differential output of the order of 1.5 V minimum into a 54 Ω load is the value commonly
  used in design (indicative, to be confirmed in the applicable text).
- USB-C device (sink): a pull-down Rd on each CC pin; the text that applies is the USB Type-C specification, which
  gives the nominal value (commonly 5.1 kΩ, indicative) and its tolerance.
- A capacitance a datasheet recommends: the target is what the IC needs (a datasheet minimum, or what its internal
  regulator needs to be stable). A board part that resembles the one of the evaluation board (dielectric, rated
  voltage, case) is judged at nominal against the recommendation; a part that does not, or a datasheet that asks
  for an effective value, is judged on the effective capacitance of the board's part under its bias (DC-bias curve
  of the exact part), at the tolerance corner when the datasheet asks for an effective value.
- Decoupling (step 6c): a requirement the manufacturer publishes (target impedance, ripple or noise limit at the
  pin) is a criterion, and so is the rail budget of `pcb-check-power-rails`; without either, the network, the
  reference one included, is a recommendation (`references/method.md`, "Decoupling of the supply pins").

## Self-checks
- `read_pulls` stops on a pin of the table missing from the board, a name of `RAILS` with no pad and an unreadable
  value: do not bypass these stops, a renumbered pin or a renamed rail would otherwise read "no pull" and pass.
- `read_pulls` reads two-pad parts whose reference starts with `R`; a multi-pad network whose reference does not
  start with `R` is not seen. List the resistive parts that touch a net of the table: a hit is handled by hand,
  otherwise an unexpected pull stays unseen and matches an empty expectation.

## Tool contract
One script, KiCad's bundled Python (`pcbnew`), reads the `.kicad_pcb`, writes `results/straps.json`; a few seconds, its
own target of the Makefile. The decoupling network of step 6c (`pin_impedance`, or its ngspice netlist) runs in a second
script, venv, reading that JSON.
- **JSON**: one row per pin (reference, pin, role, net, wiring found as text, wiring expected as text, `ok`), the
  DNP resistors and resistors to other nets met, the level and state of each shared pin, the number of deviations;
  the rows of step 6b (`pin_networks`: pin, net, each part on the net with its value, the net of its other pad, its
  distance and DNP state) and of step 6c (`decoupling_rows`: pin, net, the inductor it sits behind, the capacitors
  to ground within reach, the screening state).
- **Refusals of the board script**: a resistive part on a net of the table that `read_pulls` does not read
  (self-checks).

## Pitfalls
- **The right resistor does not make the right level.** The script compares resistors and passes; a LED branch,
  another input or the internal pulls of the other ICs on the net (in parallel with the external pull: two equal
  pulls halve the resistance) can still put the pin in the undetermined band. Only the level of step 4 shows it.
- **Check the default direction of every clock and strap pin, and compare with the reference architecture, not
  only pin by pin.** A pin that is an output until a strap says otherwise drives against the other source if that
  strap is missing; a clock tree or reset scheme that differs from the manufacturer's figure can meet every pin
  table and still violate an input specification.
- **A note under a drawing is a requirement on its own pin.** In an image-only PDF it is invisible to a text
  search, and it is missed when a net is judged as a whole: e.g. a jack asking for the end of its termination on
  ground while the board ties it to the shell.

## Limits
- The script checks the wiring of the pulls, not the voltage on the pin, nor what the firmware later writes over
  the strapped defaults. Shared pins need the calculation of step 4 and a measurement.
- Only two-pad footprints whose reference starts with `R` are read as pulls (self-checks for the others), and only
  behind series resistors of at most `SERIES_MAX`. A pull to a net missing from `RAILS` is listed with the
  resistors to other nets, not counted as a pull.
- Internal pull values and strap thresholds are taken from the datasheets; their spread is covered only by the
  level calculation of step 4.
- The interface review is a reading of the schematic against documents.
