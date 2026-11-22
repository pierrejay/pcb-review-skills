# Derating and sourcing: application cases, the other pitfalls

The policy thresholds used (80 %, 50 %, 10 %) are those of the in-house policy; another policy reaches other verdicts on
the same parts.

## Cases by mechanism
- **A part listed is not a part judged.** Setting: a four-line protection array on the connector of a bus whose
  supply can sit above its nominal value (for a 5 V bus, between 5.25 V and 5.5 V depending on the specification
  and edition: indicative values, confirmed in the applicable text). The part fitted has a 5 V stand-off, a
  breakdown of 6 V minimum and a leakage of 80 nA at 5 V. An engine that judged only parts with two or three nets
  listed it without comparing it with the supply, and a hand-written note said "only the leakage rises". Judged on
  every line, supply pin included, the part is a deviation (VRWM below the permanent voltage). Effect: the part
  stays below its breakdown and does not clamp; its leakage above 5 V is not specified. The designer accepted it
  (dated decision, to reopen if the part number changes or an abnormal leakage is measured): "pass *", listed at
  the head of the report. Teaches: the rule makes the choice explicit; it is not bent to make the part pass, and
  the acceptance is attached to the part number and the condition it was taken for.
- **A stand-off close to the permanent maximum is a flag, not a deviation.** A 27 V TVS on a 24 V supply with a
  ±10 % source (26.4 V): 2 % above the permanent voltage, leakage rising near the stand-off. Teaches: the flag
  margin (10 % in the in-house policy) separates "would conduct" from "leaks more than expected".
- **An alternative that looks equivalent is checked in the circuit.** Setting: the 27 V flat-clamp TVS of the case
  above, on a 24 V input, is out of stock; the only part available is a 33 V one of another brand, same package and
  pinout. It cures the 2 % margin. In the input chain (hot-plug and a +1 kV / 42 Ω surge, the input capacitor on the
  curve of its part) it lets the node of a converter rated 40 V reach 38.8 to 41.0 V (34.3 V with the original): a
  fail by 1.0 V at the 2 m hot-plug, where the original kept 5.7 V. Moving it in front of the series diode gains
  0.8 V, still 40.2 V, and being unidirectional it would then conduct forward when the supply is reversed: the
  reverse-polarity protection is lost. The alternative is refused on this converter; a 60 V converter gives it room.
  Teaches: a different clamp voltage or polarity changes the stress downstream and the reverse-polarity behaviour;
  equal footprint and pinout are not equal protection (`pcb-check-power-input` is where the chain is re-simulated).
- **Temperature ratings meet the board rise, not the ambient.** A jack with integrated magnetics rated to 70 °C,
  for 40 °C of ambient + 32 K of board rise: 72 °C against 70 °C, flagged. Teaches: the temperature to compare is
  the local one, ambient plus the rise read from the thermal check.
- **A forced voltage states its case.** A series Schottky in a reverse-polarity path, on a 24 V supply at 26.4 V:
  its permanent reverse voltage is the supply connected backwards, 26.4 V against 80 % of VRRM, which the nets
  (both at the supply voltage) do not show. A buck converter's inductor at Iout + ΔI/2 (0.75 + 0.42 = 1.17 A)
  against 80 % of the lowest rated current of the description (an inductor listing 1.5 A and 1.2 A is judged on
  1.2 A: ratio 0.975, deviation). Teaches: judge the peak, not the mean, against the lowest rating, and give a
  reason with every forced value.
- **A zero by default hides a real load.** A 120 Ω resistor between two signals at 3.3 V and 0 V dissipates
  90.75 mW on a 62.5 mW part (limit 50 %: 31.25 mW). Teaches: with no established voltage, a resistor is judged on
  the bound, on a declared load of its function, or "not judged: power to determine"; never on zero.

## The other pitfalls
- **Check the assembler's stock, not only the distributor's.** They are two inventories; an assembled order
  draws on the first, and a part at zero stock blocks it at the assembler and at the distributors alike.
- **Read the stock against the batch.** A part whose stock is smaller than the batch blocks beyond that quantity;
  a nearly exhausted common value of a passive is handled by naming an alternative part number in the same
  footprint.
- **A fallback must exist in the current revision.** Before writing "the alternative footprint covers it", check
  that the alternative footprint or part is on the board as it is now: a variant no longer fitted is not a
  fallback.
