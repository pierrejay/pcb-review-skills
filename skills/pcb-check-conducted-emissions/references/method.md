# Conducted emissions: method in full, board table and algorithm, reporting

## Inputs: what the numbers look like
Orders of magnitude to screen with and to catch an absurd value; each is replaced by the datasheet value or a
computation for the board at hand.
- Effective capacitance under DC bias, per input voltage: a class-2 capacitor (X5R, X7R) at a bias of about half its
  rated voltage typically keeps a third to a half of its nominal value, much less for a large value in a small case
  (a 10 µF 50 V 0805 X5R keeps 2.8 µF at 12 V and 1.4 µF at 24 V on its manufacturer's curve, where a typical curve
  gave 6 and 3.5 µF). Take the curve of the BOM part (that of an equivalent part, an estimate, when its manufacturer
  publishes none): `mlcc_bias.fit_bias` on its published points,
  `effective_capacitance` for a sum. A typical value (`typical_fraction`, a typical curve) only screens: a verdict
  that rests on it (margin, damping) is a reservation until the curve is read. A "capacitor upstream" of the same
  part has the same effective value at the same voltage.
- Routed length from the connector to the input capacitor, as an inductance: a narrow track a fraction of a mm to
  about 1 mm above its reference plane is of the order of 0.5 to 1 nH/mm (the default of `TABLE_DEFAULTS` is
  0.8 nH/mm × 10 mm = 8 nH, an estimate). The value rises with the height above the plane and falls as the track
  widens: compute it from the stackup and the routed geometry when the lines above a few MHz decide.
- Series diode in conduction: `r_d = n·V_T / I + R_S` (`diode_resistance`), with `I` the operating current at which
  the dynamic resistance is taken; the table defaults (n 1.1, V_T 25.85 mV, I 0.15 A, R_S 0.05 Ω) give 0.24 Ω, a
  fraction of an ohm for a small Schottky diode at a few hundred mA.
- TVS capacitances: the defaults (300 pF at the connector, 100 pF at the converter node) are estimates, a power TVS
  often not publishing its capacitance; the capacitance of a junction falls as the reverse bias rises, so a value
  given at 0 V is on the high side for a TVS standing off the line voltage. Filter inductor self-resonance: the
  default (100 MHz) applies only when unpublished (estimate).
- Edge duration of the switching node: rarely published, an estimate of the order of a few ns for a converter with
  integrated switches; it sets the lines above a few tens of MHz.

## Method, step by step
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers.
1. **Source: input current of the buck over one period** (`input_current`):
   - PWM: `D` the duty cycle declared for the case (`duty`: measured at the switching node, or from the
     converter's loss model), else `D = Vout / (η·Vin)`, an estimate that draws every loss through the switch: a
     loss drawn as DC input current does not switch, and the lines then move either way (a 12 → 5 V, 100 kHz case
     with its losses drawn as DC: minimum margin 1 dB too high); tag it estimate. A declared D lies in
     `[Vout / Vin, Vout / (η·Vin)]`. `ΔI = (Vin − Vout)·D / (L·fsw)`, `ton = D / fsw`;
     `i(t) = Iout − ΔI/2 + ΔI·t/ton` for `0 ≤ t < ton`, 0 elsewhere (mean `D·Iout`): during `ton` the current ramps
     from `Iout − ΔI/2` to `Iout + ΔI/2`, and is zero for the rest of the period.
   - PFM: `ton = L·Ipk / (Vin − Vout)`, `toff = L·Ipk / Vout`, repetition frequency `f = Iout / (½·Ipk·(ton + toff))`;
     `i(t) = Ipk·t/ton` for `t < ton`, 0 elsewhere. Lower and denser lines.
   - **Each form has its domain**, checked before the FFT. PFM: the inductor current must return to zero before
     the next pulse, `f·(ton + toff) = 2·Iout / Ipk ≤ 1`, that is `Iout ≤ Ipk / 2`; above it the converter is not
     in PFM, and the energy balance alone does not show it. PWM: `Iout ≥ ΔI/2` for the ramp to stay positive;
     below, the form holds only for a converter in forced PWM, whose inductor current reverses (`forced_pwm=True`,
     declared in the board table); a converter that skips pulses or blocks the reverse current is in the PFM or
     discontinuous case and is computed as such.
   - Edges: the waveform is smoothed by a circular moving average of duration `t_edge`.
   - Harmonics: `I_m = 2·|FFT_m| / N` (peak amplitude of harmonic m, at `m·f`); mean = the average of the samples.
2. **Input network as fitted** (`fitted`, `network`), as a nodal admittance matrix `Y(f)` (6 × 6, complex; a helper
   stamps an admittance between two nodes, one of which may be earth). Nodes: `P`, `N` (the two wires at the
   connector; `N` is the board ground), `B` (after the series diode), `A` (converter input), `RP`, `RN` (the two
   receiver nodes). Branches and default values (`TABLE_DEFAULTS`: estimates, overridden by the board table):

   | Branch | Model | Default |
   |---|---|---|
   | LISN, each wire (CISPR 16-1-2, 50 µH / 50 Ω) | 50 µH to the supply (AC ground); 0.1 µF then 50 Ω receiver to earth | fixed |
   | `P`–`B`: series diode in conduction + track | `r_d + jωL_track`, `r_d = n·V_T / I + R_S` | n 1.1, V_T 25.85 mV, I 0.15 A, R_S 0.05 Ω → 0.24 Ω; 8 nH |
   | `P`–`N`: TVS at the connector | capacitance | 300 pF (estimate) |
   | `P`–earth: capacitor from the supply wire to chassis (variant) | `jω·ESL + 1/(jωC)` | ESL 0.5 nH (estimate) |
   | `B`–`A`: filter inductor | `(DCR + jω·L·k_L) ∥ C_srf`, `C_srf = 1 / (L·(2π·f_srf)²)` from the NOMINAL L (the winding capacitance does not follow the spread of L: at the corner k_L the self-resonance is f_srf / √k_L) | f_srf 100 MHz if unpublished; no filter: short (the diode branch then lands on `A`) |
   | `B`–`A`: ferrite bead in series with the inductor (variant) | `jωL_b ∥ R_b` (resistive region) | — |
   | `B`–`N`: capacitor upstream of the inductor | `ESR + jω·ESL + 1/(jωC_eff)`, C_eff at the input voltage like the converter capacitor | 5 mΩ, 1.5 nH mounting ESL |
   | `A`–`N`: converter input capacitor(s); TVS at that node | same model, `n_cap` in parallel; capacitance | 5 mΩ, 1.5 nH; 100 pF (estimate) |
   | `A`–`N`: damper (variant) | `R + jω·5 nH + 1/(jωC)` | — |
   | `N`–earth | bond inductance if the board ground is tied to the earthed enclosure, else open | 50 nH |

   The cable between the LISN and the board is short; its inductance is neglected.
3. **Transfer** (`solve`, `transfer`): the converter draws 1 A from `A` to `N` (−1 A at `A`, +1 A at `N`); solve
   `Y·v = i`; `Z_t(f) = max(|V_RP|, |V_RN|)`. With the ground bonded
   to earth through a low impedance, almost all the noise appears on the positive line; floating, it splits between
   the two receivers (about 6 dB lower on each when the split is even).
4. **Level** of each line between 150 kHz and 30 MHz (`lines`, `level_dbuv`): `V_m = I_m·Z_t(m·f)`, in dBµV
   `20·log10(V_m / √2 / 1 µV)`. A line of zero amplitude (`None`, at a null of the edge's smoothing) is met.
5. **Detectors**: without spread spectrum, and with lines at least twice the 9 kHz bandwidth apart, each harmonic is a
   stable line resolved by the receiver, so peak = quasi-peak = average: the level is compared with both limits and is
   an upper bound. Closer lines (PFM at light load) fall several at once in the filter: `lines` refuses them, and the
   detector margin of that case is not established by this model.
6. **Spread spectrum, quantified apart (estimate, `spread_gain_db`)**: the power of harmonic m is spread over
   `2·δ·m·fsw` (δ = 0.06 for ±6 %) and seen through the 9 kHz filter: gain in average ≈ `10·log10(2·δ·m·fsw / 9 kHz)`
   (floored at 0), half of it (in dB) in quasi-peak; none in PFM.
7. **Filter variants** (inductor value, capacitor upstream, doubled capacitor, damper, resistance in series in the
   supply path `r_series`, bead, capacitor to chassis): same computation, with and without the spread-spectrum
   gain, on the load case expected to be the worst, then on the others when the margin is near the limit; the margin
   of a variant is the minimum over the cases run, with the case that sets it. A case that `lines` refuses (step 5)
   is not established for the variant and is listed with it. The attenuation is that of an ideal lumped model:
   capacitor ESR and ESL are in, the coupling between the input and the output of the filter is not. In practice
   placement usually caps the attenuation of a single stage below the lumped value, at an estimated 30 to 40 dB:
   stray capacitance across the inductor, mutual inductance and a ground path shared by input and output set the
   cap, with the inductor's self-resonance. Keep the line list of the envelope case for the figure.
8. **Damping** (Middlebrook, `damping`): impedance seen by the converter between `A` and `N` (`z_out`: +1 A at `A`,
   −1 A at `N`, `|V_A − V_N|`), the LISN being the source. Floating, the two LISNs are in series (100 µH), which
   lowers the LISN's resonance and raises its peak, about twice the earthed one when the LISN sets it. It is
   compared with the converter's input impedance at the lowest input voltage and highest power,
   `|Zin| = Vin² / Pin` (`zin_converter`); `damped = z_out_max ≤ Zin / 3`. A well damped filter with a resistance in
   series has no peak: its output impedance settles at low frequency on the resistance of the supply path, and that
   plateau is the maximum judged. A converter regulating its output draws a constant power, hence a negative
   incremental input resistance of magnitude `Vin² / Pin` below its control bandwidth: an input filter whose output
   impedance approaches it can oscillate. The resonances that matter are therefore low, often a few kHz (the LISN's
   50 µH, 100 µH floating, with the input capacitance, a filter inductor of tens of µH with its capacitors): the
   sweep starts a decade under the lowest resonance the network can have, `1 / (2π·√(ΣL·ΣC))`, ends at 3 MHz or a
   decade above the highest LC resonance, and each peak is refined. A maximum at an end of the sweep is refused.
9. **Hand check** (`fundamental_hand`): fundamental `≈ 2·Iout·sin(πD)/π` times the impedance of the input capacitor,
   read across 50 Ω.

## The limits
`limits(f, cls, det)` holds the table of Criteria (`../SKILL.md`); class B below 0.5 MHz is
`hi − (hi − lo)·log10(f / 0.15 MHz) / log10(0.5 / 0.15)`. At a band edge the lower limit applies. If the applicable
text gives other values, the line levels (`lines`, `level_dbuv`) do not change: only the comparison does, in the
board script.

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract". The steps are those above; what the script adds:

**Board table** at the top of the script:
- converter: `FSW`, spread `δ`, `VOUT`, `ETA`, inductor `L`, `IPK_PFM`, `T_EDGE` (source: datasheet, page; edge
  marked estimate);
- load cases `(label, Vin, Iout, mode, duty)`: output currents derived from the power budget (board power × η /
  Vout), read from that check's JSON (typical, envelope, envelope at minimum Vin, light load); `duty` the
  measured or computed PWM duty cycle with its source, or None (estimated from η);
- effective capacitance of the input capacitors per input voltage, `{Vin: C_eff}`, with the curve it comes from;
- network constants: ESR, ESL, track inductance, bond inductance, TVS capacitances, diode n / R_S and the current
  at which its dynamic resistance is taken, each tagged datasheet or estimate, passed to `fitted(c_eff, …)`; each
  overrides its entry of `TABLE_DEFAULTS`, an estimate for an unknown board, never a datasheet value;
- `FITTED`: the filter as built (`l` nominal, `dcr`, `c_up` present or not, `damper` `(C, R)` or None, `f_srf`,
  `bead` `(L, R)` or None, `c_supply_earth` or None; the inductance corner passed as `kl`, never as `l × kl`), and the
  dictionary of variants to quantify, among them "no filter".

**Algorithm**: for each case, on the board as fitted: the source (`input_current`), every line `m·f` in 0.15–30 MHz
(`lines`), its level through `transfer`, margins A and B in QP and AV (`limits`), spread-spectrum gains; keep all
lines, the minimum margins and the limiting line. For each variant: the quantities of steps 7 and 8 (`damping`). Then
the JSON.

## Reporting
- Spectrum of the envelope case with the limit lines, fitted board and "no filter" on the same figure, as lines or
  their envelope (`../SKILL.md`, Pitfalls).
- Table case → repetition frequency, limiting line, level, margins in QP and AV (class A, class B for
  information), spread-spectrum gain apart.
- Table of filter variants: margins, maximum output impedance and its frequency against `|Zin| / 3`, damped or
  not.
- Estimates listed with what they touch: edges and mounting ESL (lines above the capacitor's resonance),
  effective capacitances, TVS capacitances, inductor self-resonance, spread-spectrum gain, and the indicative status
  of the limits.
- A deviation names the line and the impedance that sets it; its correction gives the part, the value and the
  position in the chain ("capacitor between the series diode and the inductor"), with the gain in dB.
- A filter proposal gives the inductor, the capacitor upstream, the damper, **on which side of the inductor the clamp
  (TVS) sits**, and the result of the transient verification of that exact arrangement (hot-plug and surge:
  `pcb-check-power-input`). Starting point for the damper: `power_input_models.damper` (the optimum of Erickson and
  Maksimović); the damping criterion above (`damping`) and the transient verification decide.
- Measurements to request: pre-scan with a LISN on the DC input, the only verdict, both ground set-ups, peak and
  average detectors, at typical and full load; the edge duration at the switching node (probe ≤ 1 pF) if the high
  lines decide.
