# Power input: application cases, the other pitfalls

## Reference chain
The cases below that say "reference chain" use this one: a 24 V cable-fed input, with a converter rated 35 V
continuous and 40 V for 400 ms. From the connector: a bidirectional TVS to ground, a series Schottky diode, a first
capacitor (and a unidirectional TVS) on the node behind it, an LC filter (inductor, then a second capacitor) and the
converter with its load. The input capacitors are 10 µF 50 V 0805 X5R parts (3.1 µF at 12 V, 1.3 µF at 24 V, 0.85 µF
at 33 V on their curve; ESR 5 mΩ, ESL 1 nH), the cable is 2 m or 10 m, the source is at nominal + 10 %. The cases
that give another setting say so. The figures are orders of magnitude, not values to reproduce.

## Cases by mechanism
- **A model must first reproduce the test its part is qualified for.** Setting: Schottky, a 27 V flat-clamp TVS
  and one capacitor at the converter. Hot-plug: 32.7 V with the TVS, which takes 47 A for its 40 A 8/20 µs rating,
  and 91 V without it. + 1 kV / 42 Ω: 33.6 V with 22.1 A,
  which is the case the manufacturer qualifies the part for. At ± 0.5 kV / 2 Ω the same chain gives 38.6 V and
  213 A in a TVS rated 40 A: outside what this hardware can hold, to be said as such.
  Teaches: a robustness figure is credible when the model reproduces the manufacturer's own test first; and a
  result beyond the rating of the part is reported as "not held", not as a number to optimise.
- **A reverse voltage sitting on VRRM is a model that clamps.** Reference chain with a 60 V series diode and no
  clamp ahead of it. Negative wave: the reverse voltage reads 60–61 V and looks "at the limit". With the reverse
  current read: the diode is the only part in the path and absorbs 19 A and 21 mJ in avalanche whatever its
  rating (936 V without breakdown). After a positive wave the swing-back reaches 104 V. Remedy: a bidirectional
  TVS at the connector (400 W, 33 V) and a 150 V diode → 94.6 V in reverse at the negative wave, no avalanche,
  19.5 A and 14 mJ in the connector TVS (its 8/20 µs rating is not published: about 2.8 kW over 20 µs from the
  power-duration curve against 1.4 kW seen, an estimate); after the positive wave the reverse voltage is 71 V,
  where a 100 V part would have been too tight. Teaches: a voltage that equals a rating is read as a current and
  an energy, and a series diode is rated for the swing-back of the coupling network after the positive wave as
  well as for the negative wave.
- **A filter that improves emissions can raise the overshoot at hot-plug.** Reference chain with an LC added (1.5 µH
  between the two capacitors, chosen on attenuation; at 12 V, with 3.1 µF on the curve, it leaves 63.9 Ω of output
  impedance at 6.4 kHz with the board floating (31.9 Ω at 9.0 kHz earthed), the LISN's resonance, against 12 Ω allowed,
  and the 22 µF + 0.68 Ω damper below brings it to 5.49 Ω: `conducted_emi.damping`), the clamp left before the
  inductor: the converter pin goes from 33.6 V without the LC to 51.9 V with it (saturable inductor; 92 V with the
  linear one) at the 2 m hot-plug, and 45.5 V at the + 1 kV surge, for a 40 V limit.
  Corrections, worst of the four cases:

  | Variant | Converter node |
  |---|---:|
  | As fitted, linear inductor / saturable (estimate) | 92 / 51.9 V |
  | Clamp moved to the converter side, saturable / linear | 34.7 / 33.7 V |
  | Damper 22 µF + 0.68 Ω (electrolytic) across the second capacitor, saturable / linear | 34.7 / 33.7 V |
  | Damper 47 µF + 0.47 Ω, saturable / linear | 32.9 / 32.5 V |
  | 0.68 Ω in parallel with the inductor, saturable / linear | 39.2 / 44.2 V |

  With the clamp on the converter side the pin is held, but the TVS takes 67 A at the 2 m hot-plug for its 40 A, and
  the first capacitor reaches 44.0 V (50.2 V with the linear inductor, the rating of the part). The 22 µF + 0.68 Ω
  damper keeps the clamp where it is, the pin at 34.7 V and the TVS at 20.4 A at most, and does not change the
  attenuation. Teaches: a filter is verified in the time domain, with the cable parasitics, the capacitors at their
  effective value and the clamp where it sits, before it is written; a correction is judged on every part it loads, not
  only on the node it protects.
- **Two stages need a resistance between them, and its window is narrow.** Setting: distribution-network scope
  (3 kW 26 V TVS at the connector, pulse resistor, 27 V flat-clamp TVS at the converter; power TVS extrapolated
  from its 10/1000 µs data, pessimistic), + 0.5 kV / 2 Ω. With 1 Ω: 33.7 V at the converter, 185 A in the first
  TVS and 24 A in the second; with 0.5 Ω the second reaches 41 A for 40 A: over its rating; with 1.5 Ω, 33.5 V
  and 17.1 A. A 3.2 × 1.6 mm anti-surge resistor of that value withstands about 100 V in 1.2/50 µs for 26.5 V seen
  and dissipates 0.24 W at 0.4 A. Teaches: the lower bound comes from the current of the second TVS, the upper bound
  from the resistor's own pulse withstand and dissipation; simulating a few values on both sides is what finds
  the window.
- **A single power TVS only protects a converter with headroom.** Same distribution-network scope, + 0.5 kV /
  2 Ω, power TVS fitted on its 8/20 µs data: a 5 kW 33 V part gives 50.5 V (passes with a 63 V converter), a
  3 kW 33 V part 62.5 V (refused), a 3 kW 26 V part 46.4 V (still too high for a 40 V converter). Teaches: at a
  2 Ω source the clamp carries hundreds of amperes, so its dynamic resistance, not only its clamping voltage at
  a small current, sets what the converter sees; compare candidates by simulation.
- **The clamp fixes the permanent input range.** A TVS with 27 V of stand-off, 29.3 V of minimum breakdown and
  12 mA of maximum continuous breakdown current accepts a 24 V supply + 10 %; a supply adjustable to 28–30 V puts
  that clamp in permanent conduction. Teaches: the stand-off and the minimum breakdown are compared with the
  permanent maximum of the source, before any transient is run.
- **A 5 V USB input rings like a 24 V one.** Setting: USB debug port, 10 µF 0603 (4.2 µF under 5.25 V), 100 nF and
  the VBUS pin of a USB ESD array on the input of a switch rated 6.0 V absolute maximum; host at 5.25 V behind
  120 µF, cable 0.7 µH/m and 0.07 Ω/m + 30 mΩ of contacts, 0.5 to 3 m. With the capacitor fixed at its 0 V or 5.25 V
  value the switch input reaches 7.2 to 8.5 V, above its 6.0 V; a capacitance that falls with the voltage rings
  higher still. Teaches: a low-voltage, hot-plugged input is a power input like any other, and a ceramic capacitor
  with a cable inductance can bring the pin well above its rating.

## The other pitfalls
- **Do not count on the series diode against noise.** Conducting, it is a dynamic resistance; blocked, a junction
  capacitance; common mode ignores it. Read both on the diode's datasheet at the operating point.
- **Rate the series diode for the swing-back after the positive wave.** The coupling capacitor of the test
  discharges backwards across the diode: size VRRM on the simulated swing-back for the coupling network and the
  filter of the board, with a margin.
