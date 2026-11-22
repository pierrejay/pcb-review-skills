# Clock integrity: forms of requirements, application cases

## Forms of receiver requirements
Two requirement sets, as examples of what the criteria table holds and of how much a datasheet may state; they
are not typical requirements.
- A PHY with a 50 MHz clock input (TI DP83TD510E, datasheet SNLS656D): edge 10–90 % ≤ 4 ns, duty cycle 40–60 %,
  jitter ≤ 40 ps RMS and ≤ 250 ps cumulative, ±100 ppm, input thresholds 0.6 / 1.2 V.
- A second device (WCH CH182D, datasheet V1.8, reference-clock input): duty cycle 40–60 %, nothing else stated.
  The other rows of the table are then "nothing stated by the receiver", and the series-resistor sweep is judged
  on the thresholds and the absolute maximum only.

## Application cases
- **A series resistor trades a little edge for the overshoot.** Setting: a 3.3 V clock driven into inputs of
  1.3 pF at the end of lines of 7 to 20 mm (Z0 51 to 73 Ω, depending on the stackup), strong and typical driver
  assumptions swept. Result: 22 to 33 Ω add 0.1 to 0.2 ns to the edge and bring the overshoot from 8–26 % down to
  0–2 %; a 5 pF input on a star without resistor reached 37 % with a strong, fast driver (10 Ω, 0.5 ns).
  Teaches: the cost is of the order of the resistor times the load capacitance, small against the nanosecond
  edge of a typical stage, while the overshoot depends on the driver, the line and the load together: bracket
  them rather than trust one value.
- **The resistor belongs at the source when the line is not short.** Setting: 13.8 mm line (about a sixth of the
  length of a 0.5 ns edge at 5.7 ps/mm), strong driver (10 Ω, 0.5 ns), 5 pF load. Result: 29 % overshoot
  without resistor; 22 Ω at the driver leaves 4 %, the same 22 Ω at the receiver 9 %, 33 Ω at the driver none.
  Teaches: the resistor in series with the driver terminates the reflection that comes back from the far end;
  placed at the receiver, the line stays driven by the low output impedance and rings.
- **On an electrically short line the overshoot comes from the inductances.** Setting: 7.4 mm line (42 ps of
  delay) with the same kind of driver. Result: 10–11 % of overshoot without resistor, from the package and
  resistor inductances with the load; the resistor only damps (down to 5–7 %), and any value from 22 to 33 Ω does.
  Teaches: below about a tenth of the edge length the line is a lumped load that can still overshoot; the
  position of the resistor matters less.
- **A worst-case source edge leaves no margin, whatever the routing.** Setting: a CMOS oscillator specified at
  ≤ 4 ns (3.8 ns taken as the internal edge) driving receivers that require ≤ 4 ns, over the routed
  topologies (point to point and star, 22 to 33 Ω resistors). Result: 3.84 to 4.00 ns at the receivers. Teaches: it passes only under an assumed driver, so it
  goes in the measurements; the routing cannot recover an edge the source does not provide.
- **A guaranteed range wider than the required one fails on paper.** Setting: a 50 MHz output guaranteed at
  35–65 % duty cycle against an input that requires 40–60 %. Result: rule not met, effect unknown, to be
  measured; one compliant architecture is a single oscillator whose specification meets the requirement and which
  feeds both ICs. The same table holds a jitter given as "450 ps long term" against a limit of 250 ps cumulative
  and 40 ps RMS: different definitions, not comparable. Teaches: the verdict is taken on guaranteed values, and a
  figure of another definition is replaced by a measurement, not converted.
- **A source that publishes nothing is not calculable.** Setting: an SoC clock output with no jitter, edge or
  drive figure, against a receiver asking ≤ 40 ps RMS. Result: no verdict; a measurement plan and a fallback
  architecture. Teaches: say "not published by the source" and specify the measurement, rather than assume a
  value that would decide the verdict.
