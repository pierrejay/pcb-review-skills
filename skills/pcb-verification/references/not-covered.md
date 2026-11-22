# Not covered yet, and simple checks to do by hand

## Not covered by any check
- Rail impedance versus frequency and regulator loop stability: the checks give the DC drop, the ripple and
  the step response by simulation only where a model exists (`pcb-check-power-rails`, `pcb-check-pdn-ir-drop`).
- Sensitivity of impedance to the fabricator's tolerances beyond a ±10 µm variation of etching, computed on a few
  cross-sections.
- Links on inner layers: `lib/stripline2d.py` computes them (impedance and delay); the sampling and the reference
  situations for them are board tables, not yet part of the `pcb-check-impedance` tool contract.
- Multi-gigabit channels (PCIe, USB 3, SATA, other SerDes, the SGMII side of a gigabit PHY) and memory channels:
  losses, crosstalk, jitter and equalisation need a channel simulation with the manufacturer's models.
  `pcb-check-memory-bus` gives the wiring and first-order margins of one DDR3/DDR3L chip point-to-point, necessary but
  not sufficient; other memory buses are not covered.
- Fast transients and ESD on a power input: not simulated, measured.
- Start-up time and spurious modes of a crystal oscillator: the loop is not simulated.
- Crosstalk between links, and the placement rules of a layout guide (decoupling, crystal): not audited.
- Conducted emissions of converters other than a buck (boost, flyback, SEPIC, isolated): the network and LISN of
  `lib/conducted_emi.py` apply, its source model does not. Radiation of data buses and their simultaneous
  switching: only clocks are taken as on-board sources.
- Ripple current of capacitors and pulse power of resistors: the component check judges the permanent DC stress
  only. Second sources beyond the assembler's catalogue, and price.
- Long-term reliability, humidity, vibration, electrical safety and component life cycle: only if the scope asks.

## Simple checks with no skill yet
To do by hand when they apply; each would be a short skill in the common format once a board calls for it:
- logic-level compatibility between two ICs: VOH / VOL against VIH / VIL, across supply domains, and with one of
  them unpowered;
- currents per pin and per supply group, floating inputs, two outputs driving one net, and an IC powered through
  its I/O by a neighbour while its own supply is off;
- rise time and low-level current of an open-drain bus: pull-up value against the estimated bus capacitance;
- an ADC input: source impedance and anti-alias capacitor against the acquisition time (settling to the
  resolution wanted), after a multiplexer switch too; reference and its decoupling; error budget;
- an amplifier or a sensor front end: input common-mode range, output swing under load, offset and drift, stability
  with the capacitive load, a protection that does not degrade the measurement;
- a CAN or RS-485 port: termination, failsafe bias, stub lengths, common-mode range, behaviour unpowered;
- symbol against footprint against the exact package: pin numbering, pad 1;
- pinout and orientation of connectors against what will plug into them;
- a bring-up plan: order of the measurements and the values expected.
