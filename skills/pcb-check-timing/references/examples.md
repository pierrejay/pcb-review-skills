# Interface timing budgets: application cases

## Format of the datasheet constants
The board table holds each constant with its document, table, symbol and the conditions it is given at (load,
supply). One illustrative line, to show the format only (the values are not transferable to another part without its
own datasheet): a PHY's "slave timing" table gives outputs 4 to 14 ns after the clock, inputs setup 4 ns and hold 2 ns
(document, table, symbol and 3.3 V / load noted next to each). Where a part publishes nothing, the interface
specification's values are entered as flagged estimates, indicative until confirmed in the applicable edition.

## Cases by mechanism
- **On a common-clock interface, length matching is not the criterion.** Setting: a 50 MHz RMII (T = 20 ns)
  between two PHYs, six lines of 11 to 45 mm, the clock reaching the receiver 0.08 ns after the transmitter.
  Computed: the budget of each line against the clock. Result: delays up to 0.27 ns; setup 1.82 to 1.97 ns and
  hold at least 2.03 ns on the six lines; the 26.6 mm difference inside one group costs 0.15 ns. Teaches: when
  the margins are of the order of nanoseconds and the lengths cost tenths of a nanosecond, a matching rule of a
  layout guide has no effect on the verdict; what is judged is each line against the clock.
- **A maximum without a minimum gives a setup and no hold.** Setting: an RMII between a PHY and a microcontroller
  whose datasheet publishes only a 16 ns maximum for its RMII outputs. Computed: setup and hold on both
  directions, the controller side with the published maximum and no minimum. Result: setup −0.21 to −0.51 ns once
  routing and the clock skew (+0.15 ns) are added; hold not demonstrable; the budget holds if the outputs fall
  between 1.8 and 15.5 ns after the clock. Teaches: the report gives the window, so that the deviation can be
  accepted or not on a measurable quantity; a deviation record names what would reopen it (frame errors on a
  long run, a measured delay outside the window, an answer from the manufacturer, another IC). Error-free traffic
  proves the typical part, not the worst-case margin, and a maximum with no minimum cannot be completed by a
  trial.
- **A lower data rate on a full-rate clock keeps the full-rate budget.** Setting: the same RMII link running at
  10 Mbit/s: each dibit is held for ten clock periods. Computed: nothing new; the criterion stays the 50 MHz
  budget. Teaches: the data are stable for ten periods, but the receiver can still sample on the edge that
  follows a transition, so the stability does not substitute for a margin unless the interface specification
  defines the sampling at that rate.
- **A half period is an assumption.** Setting: a controller reading a peripheral over a mode 0 serial bus
  (peripheral output valid 12 ns after the clock edge, controller setup 10 ns, 0.5 ns of routing), clocked at
  18 MHz. Computed: MISO setup on T/2 and on the minimum clock low time published by the controller (42 % of the
  period). Result: +5.3 ns on T/2, +0.8 ns at the minimum low time: pass with reservation, the clock low time to be
  measured; limit frequency 18.7 MHz; a test build at 24 MHz is at −5.0 ns. Teaches: the datasheet's minimum low
  time, not T/2, enters the budget; the lowest duty cycle that still holds (here 40.5 % at 18 MHz) turns the
  reservation into a measurement the designer can make.
- **A negative margin is written as an action.** Setting: the 24 MHz build of the previous case. Wording:
  "MISO setup −5.0 ns at 24 MHz: 12 ns of output delay + 10 ns of controller setup + 0.5 ns of routing in a clock
  low time that can be as short as 17.5 ns; nothing to change on the board; concerns only the build whose CPU
  clock selects the divider 2; correction: divider 4 (12 MHz, +12.5 ns) or the half-period sampling option
  (+19.1 / +4.4 ns)". Teaches: cause term by term, scope (which build), precise correction (file, line, value)
  and gain; "negative margin at 24 MHz" alone leaves the reader unable to decide.
- **When the controller publishes nothing, the verdict is on what the routing consumes.** Setting: an RMII link to
  an SoC whose datasheet and reference manual give no interface timing; traces of 26 mm at most. Computed:
  routing delay and skew. Result: 0.15 ns; the routing is not the issue. Teaches: the verdict states what the
  routing consumes, the missing controller timings are listed as an estimate with the admissible window, and the
  validation is long-duration traffic and a measurement.
- **For a serial memory the limit is the controller's sampling mode, not the board.** Setting: a serial
  NAND on an SoC, 133 MHz capable (output valid 7 ns at most, output hold 2 ns at least, input setup and
  hold 2 ns), routing 0.15 ns of clock delay and 43 ps of skew, tCLQV − tCLQX = 5 ns. Computed: write margins,
  read window, the two sampling edges. Result: write margins at least 1.66 ns up to 133 MHz; read limited to
  69 MHz when sampling on the next rising edge without delay, while the vendor's driver runs 80 MHz on the
  falling edge with a calibrated delay line (+5.25 ns of setup, +2.2 ns of hold before any delay). Teaches: the
  board consumes tenths of a nanosecond of a window of several nanoseconds; what fixes the frequency is the
  sampling edge and delay line of the controller, which the criterion must state and the boot log must prove.
- **Input capacitance of the receiver, unpublished.** Setting: a 22 Ω series resistor on a data line whose
  receiver capacitance is not in the datasheet. Computed: the delay at both ends of a 2 to 10 pF bracket. Result:
  the bracket moves the delay by about 0.2 ns (1.204 · 22 Ω · 8 pF); the verdict is read at the pessimistic end.
  Teaches: an estimate is shown as a bracket with its sensitivity, and it is its worst end that decides.
