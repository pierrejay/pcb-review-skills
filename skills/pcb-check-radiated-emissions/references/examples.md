# Radiated emissions: application cases

Limits are the indicative ones of `../SKILL.md` (class A / B, 10 m, quasi-peak).

## Cases by mechanism
- **Over a close plane, clock loops are small.** Setting: a four-layer board whose signals run over an unbroken
  plane 0.0994 mm below; clocks of 50 MHz on tracks of 7 to 19 mm, an 80 MHz memory clock, an 18 MHz serial
  clock on 20 mm (frequency read in the firmware); a prototype stackup with the plane 0.2104 mm below. Computed:
  `loop_field` for each clock, 3.3 V swing, 1 ns edge (estimate), worst odd harmonic in 30 MHz – 1 GHz. Result: at
  least 27 to 32 dB under class B on the production stackup; 21 dB on the prototype stackup, where the plane is
  twice as far (the field follows the height: 20·log10(0.2104 / 0.0994) = 6.5 dB). Teaches: the loop area is the
  routed length times the height to the plane, so a close unbroken plane makes the board's own loops a minor
  contributor, and the stackup that will be tested is the one to compute with.
- **A power cable carries the converter's harmonics unless something stops them.** Setting: a buck converter fed
  from a 24 V cable, input current harmonics of the conducted model (envelope case, 5 ns edge, estimate), input
  network as fitted (track inductance and protection-device capacitances, estimated), LISN replaced by 300 Ω per
  wire, ground bonded to the chassis through 50 nH. Computed: `power_cable_cm` for each variant; common-mode
  current, field and margin to class A over 30 MHz – 1 GHz, RMS as the receiver is calibrated.

  | Variant | Worst line | I_CM | Field | Margin to class A |
  |---|---|---|---|---|
  | no filter | 93.5 MHz | 118 µA | 63.1 dBµV/m | −23.1 dB (72 lines above) |
  | 1.5 µH + 10 µF upstream, inductor self-resonance 100 MHz (estimate) | 408 MHz | 0.042 µA | −6.0 dBµV/m | +53.0 dB |
  | same inductor, ideal (no self-resonance) | 93.5 MHz | 0.11 µA | 2.8 dBµV/m | +37.2 dB |
  | no filter, 10 nF from the supply wire to chassis only | 102.3 MHz | 127 µA | 63.7 dBµV/m | −23.7 dB (71 lines above) |
  | filter as above + series bead (0.19 µH ∥ 150 Ω) | 92.4 MHz | 0.016 µA | −14.3 dBµV/m | +54.3 dB |
  | filter as above without the bead, + 10 nF from the supply wire to chassis | 408 MHz | 0.054 µA | −3.7 dBµV/m | +50.7 dB |

  Without a filter, the resonance near 93 MHz puts the cable 23 dB above class A, and up to 8 dB above elsewhere from 35
  to 110 MHz; the spread spectrum of the converter is worth of the order of 10 dB in quasi-peak (estimate, kept apart).
  Bond inductance 5 / 20 / 50 nH: −23.2 / −23.2 / −23.1 dB without a filter, +50.7 / +51.1 / +53.0 dB with the filter:
  the bond does not matter in that case. Over the load cases of the conducted examples and PFM at 202.5 mA (2·Iout /
  Ipk = 0.9, lines 1.7 MHz apart), the filter's margin is +51.2 dB at 407.6 MHz, set by that PFM case (+52.1 dB for the
  worst PWM case, 12 V 0.718 A); the PFM cases at 20 mA, lines 166 and 123 kHz apart, are not established at 120 kHz.
  Folded into `z_wire` instead of entered as a branch, the 10 nF from the supply wire to chassis lands on both wires:
  1.8 µA and 26.7 dBµV/m instead of 127 µA and 63.7 dBµV/m at 102.3 MHz (the row of the table). Teaches: a
  converter's harmonics reach the cable through the common-mode conversion of its input network; the filter that settles
  the conducted emissions settles the radiated side of that cable too; the filtered margin depends on unpublished
  parasitics (the self-resonance moves it by 16 dB here), so it is an order of magnitude; a capacitor from the supply
  wire to the chassis, computed as a variant, does not replace the filter and adds little to it.
- **A network cable radiates what the port converts.** Setting: a long-reach single-pair Ethernet port (three-level
  code, 7.5 MBd, 2.4 V peak-to-peak, so 0.98 V RMS), 50 Ω per line, 150 Ω common-mode impedance of the cable,
  a capacitor to ground on each line (100 pF nominal) plus a protection diode per line (60 pF typical, 100 pF
  maximum); `C_a / C_b` are the totals per line. Computed: conversion `k` by `mode_conversion.conversion`,
  `v_rx` in 120 kHz, `I_CM`, minimum margin to `i_adm` over 30–200 MHz (`min_margin`).

  | C_a / C_b (pF) | Conversion at 1 / 10 / 30 MHz (dB) | I_CM at 30 MHz | Minimum margin, class A / B (dB) |
  |---|---|---|---|
  | 165 / 155 (capacitors at opposite ±5 % extremes, diodes at typical) | 63.4 / 44.2 / 38.2 | 2.57 µA | +13.1 / +3.1 |
  | 205 / 155 (as above, one diode at its maximum) | 49.5 / 30.4 / 24.8 | 11.9 µA | −0.01 / −10.0 |
  | 161 / 159 (capacitors matched to 1 %, diodes equal) | 77.4 / 58.2 / 52.1 | 0.51 µA | +27.1 / +17.1 |

  At 30 MHz the receiver sees `V_rx` = 0.175 V × 0.0796 × 2.24 = 31 mV, and the margins there are +14.2 / +4.2 dB
  in the first row. The minimum margin falls at 47.7 MHz, where the half-wave cap takes over and makes the
  admissible current lowest: on the frequencies 30, 40, 50 … 200 MHz the second row would read +0.27 dB at 40 MHz
  instead of −0.01 dB. Result: 13 dB under class A in the typical case; in the mismatch scenario (a scenario, not a
  bound) the model reaches the class A reference: to be measured, and only the current probe settles it. In this case the spread between the two diodes dominates: matching the capacitors to 1 %
  changes little as long as the diodes differ (the third row needs both). Teaches: the capacitance mismatch of the two lines sets the conversion, so the
  tolerance of the components added on each line counts more than the nominal value; the estimate has no transmit
  filter in the model and is an upper bound.
- **The first risk often has no number.** Setting: a transceiver with an integrated isolated DC-DC converter on
  a cable port. The common-mode current it drives through its barrier cannot be quantified from the datasheet.
  Computed: nothing; the source is named, ranked first, scanned in near field, and the footprint of a stitching
  capacitor between the two grounds is provided (here 1 nF, 2 kV) to be fitted if the measurement calls for it.
  Teaches: a source that cannot be modelled stays in the report, ranked, with its measurement; leaving it out
  makes the computed margins look like the whole picture.
- **Cables whose own signal is clean still carry the board's common mode.** Setting: USB and multidrop ports on
  the same board. Computed: nothing (the common mode driven through the ground plane is not computed); the
  criterion is the admissible current of the table, read with a current probe. Teaches: every connector is a
  cable in the table, with a model or "measurement only".
