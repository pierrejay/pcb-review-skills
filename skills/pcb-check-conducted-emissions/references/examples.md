# Conducted emissions: application cases, the other pitfalls

## Common setting
The cases that say "common setting" use this one. A 24 V DC input from a dedicated supply, cable up to 30 m, feeding
a buck converter 24 → 5 V at 1.1 MHz with ±6 % spread spectrum and PFM at light load (peak inductor current
0.45 A), a 4.7 µH inductor, one 10 µF 50 V 0805 X5R input capacitor behind a series Schottky diode and a TVS at the
connector. Effective capacitance of that capacitor on its manufacturer's DC-bias curve: 1.4 µF at 24 V, 2.8 µF at
12 V (a typical curve gave 3.5 and 6 µF). A "10 µF upstream" in a variant is the same part. Load cases: PWM at 24 V
with 0.436, 0.542 and 0.751 A of output and at 12 V with 0.718 A; PFM at 20 mA, at 24 and 12 V (lines 166 and
123 kHz apart); standby at 1 mA, whose PFM lines (8.3 kHz apart at 24 V) `lines` refuses: not established, listed
with every result. Margins are read in average detection against class A of the mains-port limits taken as a
reference (60 dBµV above 0.5 MHz), minimum over the load cases unless stated.

## Cases by mechanism
- **State first whether a limit applies.** Setting: the common setting, with the premise that the targeted generic
  emission standard sets no limit on a DC power port (a premise to confirm in the edition that applies to the
  product; another standard or edition may differ). Margins are computed against class A of the mains port as a
  reference and the verdict says "our reference". Teaches: a margin is useful without a requirement behind it, and
  naming the reference is what keeps a non-requirement from being reported as a failure.
- **One input capacitor is not a filter.** Common setting, no filter. Fundamental at 82 to 86 dBµV: 22 to 26 dB
  **above** class A in average and 9 to 13 dB above in quasi-peak; lines from 17 to 30 MHz 3.5 to 11 dB above
  (edges and mounting inductance estimated). Spread spectrum gains about 12 dB in average: not enough. Teaches: the
  input capacitor of a converter is sized for the converter's ripple, not for the LISN, and the margin has to be
  computed before concluding that no filter is needed.
- **The bias on the capacitor counts, voltage by voltage.** Common setting, no filter: the capacitor is 1.4 µF at
  24 V and 2.8 µF at 12 V, against 10 µF nominal. Where the capacitor's reactance sets the impedance, the fundamental
  rises by 20·log10(10 / 1.4) = 17.1 dB at 24 V and 11.1 dB at 12 V compared with the nominal value; the typical
  curve (3.5 and 6 µF) would have made every margin about 7 to 9 dB too good. Teaches: the input voltage range
  decides which case is the worst, and the capacitance of each case comes from the curve of the part, not from its
  label or a typical curve.
- **A filter that resonates on the lines of a light-load mode amplifies them.** Common setting; variants computed as
  the minimum margin against class A in average over the load cases, and the maximum output impedance at 12 V
  (`damping`, both ground set-ups) against the limit `|Zin| / 3 = 12 Ω` (`|Zin| = (12 V)² / 3.99 W = 36.1 Ω`).
  Only the 1.5 µH inductor carries a self-resonance (100 MHz, estimate). Standby (1 mA) not established for any
  variant:

  | Variant | Margin (dB), limiting case | PWM cases only (dB) | Zout max (Ω, at), floating |
  |---|---|---|---|
  | no filter (one 10 µF) | −26.4 PWM 24 V 0.751 A (QP −13.4; with spreading −14.8) | −26.4 | 132.7 at 9.4 kHz (LISN, see below) |
  | same + 3.3 Ω in series in the supply path | −25.9 PWM 24 V 0.751 A | −25.9 | 11.8 at 9.2 kHz |
  | two 10 µF, no inductor | −20.4 PWM 24 V 0.751 A | −20.4 | 72.3 at 6.7 kHz |
  | 1 µH (30 mΩ) + 10 µF upstream | −12.3 PFM 24 V 20 mA | +10.7 | 70.7 at 6.7 kHz |
  | 1.5 µH (44 mΩ) + 10 µF upstream | −16.3 PFM 24 V 20 mA | +14.3 | 70.0 at 6.7 kHz |
  | same + 2.2 Ω in series in the supply path | −15.9 PFM 24 V 20 mA | +14.7 | 8.58 at 6.5 kHz |
  | same + 22 µF and 0.68 Ω in series across the converter capacitor | −2.9 PFM 24 V 20 mA | +14.4 | 5.46 at 3.0 kHz |
  | same + 47 µF electrolytic, ESR 0.47 Ω | −0.02 PFM 24 V 20 mA | +14.5 | 3.15 at 2.2 kHz |
  | 2.2 µH (50 mΩ) + 10 µF upstream | −3.2 PFM 24 V 20 mA | +17.7 | 70.0 at 6.7 kHz |
  | 4.7 µH (80 mΩ) + 10 µF + 33 µF electrolytic, ESR 0.4 Ω | +15.7 PFM 24 V 20 mA | +24.5 | 4.68 at 2.5 kHz |

  The inductor alone leaves 26.2 dB above the limit instead of 26.4 (it only adds to the 50 Ω of the LISN, which is
  in series with it). Doubling the capacitor gains 6 dB. On the PWM lines (1.1 MHz and up) the LC sections attenuate
  as expected, and the margin grows with the inductance. But the PFM case at 20 mA sets every LC variant, and fails:
  the 1.5 µH inductor and its two 1.4 µF capacitors in series resonate at 155 kHz, on the first PFM line (166 kHz),
  where the filter gains 7 dB instead of the 3 dB it loses without filter: −16.3 dB there, against −6.0 dB with no
  filter at all. A damping resistance across the converter capacitor settles it (22 µF and 0.68 Ω: −2.9 dB; the
  electrolytic: −0.02 dB) and settles the damping criterion with it; the 4.7 µH filter puts its resonance under the
  first PFM line and damps it (+15.7 dB). A resistance in series in the supply path (2.2 Ω, `series_damper`) settles
  the damping criterion (8.58 Ω for 12 Ω) but leaves the filter's own resonance undamped (−15.9 dB): it sits outside
  that LC. Without a damping resistance, every variant peaks floating near 6.7 kHz, where the two LISNs in series
  (100 µH) resonate with the whole input capacitance: 70 Ω for 12 Ω allowed, whatever the filter inductor (35 Ω at
  9.4 kHz earthed). Teaches: an LC section attenuates only if its capacitor sits on the source side of the
  inductor; on the effective capacitance its resonance can fall on the lines of a light-load mode and amplify them,
  so a variant judged on its PWM cases alone is overstated (run the light-load case first), and the damping
  resistance across the filter's capacitor is part of the filter.
- **A filter judged on attenuation and stability alone is not finished.** The 1.5 µH + 10 µF filter above, with the TVS
  left on the upstream capacitor, overshoots the converter's rating at hot-plug and surge: the case and its corrections
  are in `../../pcb-check-power-input/references/examples.md`, "A filter that improves emissions can raise the overshoot
  at hot-plug".
- **The ideal figure is capped by the layout.** The 1.5 µH + 10 µF filter gives 14 dB under class A on the PWM lines
  in the lumped model. Placement (coupling between the two sides of the filter, a shared ground path) and the
  inductor's self-resonance usually cap a single stage at 30 to 40 dB (estimate). Teaches: a lumped margin of a few
  dB is not margin, and a stage that reaches the cap needs a second stage or a better placement, not a larger
  inductor.
- **The LISN itself resonates with the input capacitance.** Common setting, no filter: the maximum output
  impedance seen by the converter is 132.7 Ω at 9.4 kHz floating (61.8 Ω at 13.2 kHz earthed), above the 12 Ω
  allowed; with two 10 µF it is 72.3 Ω at 6.7 kHz (35.5 Ω at 9.4 kHz). It is the 50 µH of the LISN, the two LISNs
  in series when the board floats, against the input capacitance, a property of the measurement set-up, not of the
  installation (whose source is the cable and the supply); the converter is still tested on it, inside its control
  bandwidth. A resistance in series in the supply path of 3.3 Ω (`series_damper`: 3.44 Ω for 100 µH, 2.8 µF and
  12 Ω on the source and the capacitor alone; the diode's own resistance adds to it in the network) brings it to
  11.8 Ω, for 0.36 W and 1.1 V of drop at the 0.33 A drawn at 12 V. Teaches: the damping sweep starts
  under the lowest resonance of the network, the LISN's included, a few kHz here, where a sweep from 10 kHz sees only
  its flank; the peak is damped (damper, electrolytic, series resistance) or reported with its frequency and the
  set-up that makes it.
- **Lines above the capacitor's self-resonance are estimates.** Edge duration and mounting inductance set them and
  neither is published. When the edge duration puts a harmonic near a null of the sinc-shaped spectrum of the edge,
  one sample more or less in the smoothed edge moves that line by a fraction of a dB (0.6 dB for a line near
  400 MHz in the radiated reuse of the source). Teaches: report such lines as estimates and
  decide on the lines below the capacitor's resonance, which the capacitance and the ripple current set.

## The other pitfalls
- **Do not count on the series diode to block noise.** In conduction it is a fraction of an ohm (`method.md`,
  Inputs): it only shifts the divider slightly.
