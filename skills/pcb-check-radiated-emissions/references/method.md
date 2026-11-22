# Radiated emissions: method in full, board table, algorithm, reporting

## Models and units
Models from C. R. Paul, "Introduction to Electromagnetic Compatibility", and H. W. Ott, "Electromagnetic
Compatibility Engineering". Field at distance `r` = 10 m, multiplied by 2 for the reflection on the ground of the
test site. SI units: f in Hz, A in m², L in m, I in A, E in V/m; `dBµV/m = 20·log10(E / 1 µV/m)`. The limits and
their status: `../SKILL.md`, "Criteria".

## Method, step by step
1. **Board loops, differential mode** (`loop_field`). Loop area `A = routed length × height to the plane`. For
   each odd harmonic n of a clock `f0` of swing `V` (50 % trapezoid, edge `t_e`):
   - `V_n = 2V / (nπ) · |sinc(n·t_e·f0)|`, with `sinc(x) = sin(πx) / (πx)`;
   - current that charges the line and the receiver, RMS as the limits are: `I_n = 2π·f·C·V_n / √2`, `C = C_in + length
     × C'` (`C_in` from the receiver's datasheet, of the order of 5 pF for a CMOS input; `C'` = propagation delay / Z0
     per unit length, e.g. about 0.11 pF/mm for a 50 Ω line on an FR-4 type laminate: compute it from the stackup; both
     are required arguments);
   - `E = 2 × 1.316·10⁻¹⁴ · f² · A · I_n / r`.
   Keep the worst harmonic between 30 MHz and 1 GHz. With these formulas `E` goes as `f³·V_n`: it
   rises with frequency up to the top of the band (modulated by the nulls of the sinc), so the worst harmonic of a
   clock is generally in the upper part of the band, not at its first harmonic in band, and a series that stops
   short of the top of the band hides it.
2. **Cable, common mode** (what really radiates; `cable_field`): `E = 2 · min(1.257·10⁻⁶ · f · L, 60) · I_CM / r`
   — short antenna, capped at the resonant half-wave — with `L` = 1 m of radiating cable (test set-up). Inverted
   (`i_adm`), it gives the **admissible common-mode current**: `I_adm = E_lim · r / (2 · min(1.257·10⁻⁶ · f · L, 60))`.
3. **Power cable of a converter** (`power_cable_cm`). The harmonics of the input current (envelope case of the conducted
   model, computed up to 1 GHz with n = 2¹⁷) are injected in the input network as fitted, where the LISN is replaced by
   an impedance `Z_w` = 300 Ω from each wire to earth (common-mode impedance of the cable ≈ 150 Ω, estimate), the board
   ground being tied to the chassis through its bond inductance. `I_CM = |V_P + V_N| / Z_w / √2` (sum of the currents of
   the two wires, the harmonic's peak turned into RMS), then formula 2. Mechanism: a ground tied to the chassis and a
   supply wire that is not turn the differential noise into common mode (imbalance). Spread spectrum in quasi-peak,
   apart: `≈ ½ · 10·log10(2·δ·f / 120 kHz)` dB (estimate; `conducted_emi.spread_gain_db(f, δ, 120e3)`). The bond
   inductance is not extracted: one value (e.g. 20 nH), swept (e.g. 5 to 50 nH) when the margin depends on it. Above
   about 100 MHz the attenuation of a filter is set by parasitics that datasheets rarely publish (inductor
   self-resonance, capacitor ESL, track inductance, protection-device capacitance): run the variants with them, and
   without them when the verdict hangs on the difference; report the lines that lie far above a self-resonance as
   estimates set by the edge duration. A line that sits next
   to a null of the edge's sinc moves by a fraction of a dB for one sample of edge duration. A capacitor from the supply
   wire to the chassis is a branch of the network (`c_supply_earth` of `conducted_emi.fitted`, with its ESL: from the
   supply node to earth, the cable current being read on the cable alone); it is **not** folded into `est_z_wire`, which
   is the common-mode impedance of both wires: the same branch would then land on the two wires and its local current
   would be counted as cable current.
4. **Network cable.** The asymmetry of the port converts the differential signal into common mode. Conversion ratio `k =
   |V_cm| / |V_dm|` from `mode_conversion.conversion(f, ca, cb, rs, dr, z_cm)`: `ca`, `cb` the capacitances of each line
   to ground, `rs` the series resistor of each line (e.g. 50 Ω) with tolerance `±dr`, `z_cm` = 150 Ω; the three-node
   circuit it solves is in `../../pcb-check-port-network/references/method.md` § 3. It models a
   capacitor-coupled port (sources referenced to ground behind `rs`); a transformer-coupled port is refused
   (`coupling="transformer"`) and its cable row is incomplete. Signal seen by the receiver in its 120 kHz bandwidth
   (`v_rx`), for a random line code of RMS amplitude `V` and symbol period `T`: `V_rx(f) = √(2·V²·T·RBW) · env(f·T) ·
   10^(7/20)`, where `env(x) = sinc(x)` up to x = 0.5 and `1/(πx)` beyond (envelope of the lobes, no nulls), and + 7 dB
   for the quasi-peak of a noise-like signal (estimate). Then `I_CM = V_rx · k / Z_cm`, compared with `I_adm`. With no
   transmit filter in the model this is an **upper bound**: the PHY's real spectrum beyond 30 MHz is generally not
   published. The line-code constants come from the PHY datasheet: symbol rate `1/T`, and the RMS amplitude `V` from the
   levels of the code, their probabilities and the peak-to-peak amplitude.
5. **What the calculation cannot give.** The common mode that clocks and fast interfaces drive onto the cables
   through the impedance of the ground plane; the common-mode current that an **isolated transceiver with integrated
   DC-DC** drives through its barrier, at a frequency and level that are rarely published.
6. **Margins**: `margin_db = 20·log10(i_adm / I_CM)`, positive under the limit, at the typical case and at the
   pessimistic bound. A zero current (a perfectly symmetric port, a harmonic at a null of the edge's smoothing) gives
   None: no margin in dB, the criterion is met, judged on the currents (`I_CM ≤ I_adm`).

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table**
- test set-up: `R = 10`, ground reflection 2, `L_CABLE = 1`, `Z_WIRE = 300`, `RBW = 120e3`;
- stackups: height to the plane per stackup, read from the stackup files of `../../pcb-verification/assets/stackups/`,
  `C'`, `C_in`, clock edge;
- clocks: `(label, f0, length, swing)`, the length taken by key in the layout-audit or timing JSON (for a line
  with a series resistor: upstream + downstream), the frequency with its source (schematic, firmware file);
- cables: one entry per cable of the board, each with its model (converter harmonics, mode conversion) or the
  explicit mention "measurement only";
- power cable: the filter variants to compare (as fitted, without filter, alternatives), as `conducted_emi.fitted`
  dictionaries imported from the conducted script's board table together with its load cases;
- network cable: the cases `(C_a, C_b)` read from the port-network JSON, line code constants.

**Algorithm**
1. `limit(f, cls)` and `i_adm(f, cls)`; tabulate `i_adm` at 30, 50, 100, 150, 230, 300, 500, 1 000 MHz.
2. Board loops: for each clock, on the stackup tested, `loop_field` loops on odd n while `n·f0 ≤ 1 GHz`, skips below
   30 MHz, keeps the harmonic with the smallest margin to class B; output length, area, worst frequency, field,
   margin.
3. Power cable: `conducted_emi.input_current(vin, iout, mode, n=1 << 17, …)` on the load case expected to be the
   worst, the PWM envelope or PFM at the highest output current the converter stays in PFM (its strongest lines above
   30 MHz: the amplitude of a line there follows Ipk × the repetition frequency, which rises with the load), the
   other cases of the conducted list when the margin is near the limit; a case whose lines are closer than 240 kHz
   (`lines` at 120 kHz) is not established and is listed with the variant. `power_cable_cm` builds the network with `est_z_wire` for each harmonic in 30 MHz – 1 GHz, injects the harmonic
   amplitude from the converter input to ground, solves, computes `I_CM`, the field, margins A and B and the
   spread-spectrum gain; per variant the margin is the minimum over the cases run, with its case; keep the worst
   line, the number of lines above class A, the lines of zero amplitude (`n_zero`: met, no field in dB) and a
   decimated spectrum for the figure. The bond inductance is passed as `fitted(…, l_bond=)`.
4. Network cable: for each case, `I_CM(f) = v_rx · k / Z_cm` with `k` from `mode_conversion.conversion`; the margin
   kept is the minimum over 30–200 MHz by `min_margin(…, breakpoints=(0.5 / T,))`, a fine sweep that includes the
   breakpoint of the cable factor (47.7 MHz for 1 m), where `i_adm` reaches its lowest value and the minimum
   generally sits, and the knee of `env`. Tabulate the margins at 30, 40, 50, 60, 80, 100, 150, 200 MHz
   (`margin_db`) for display only: between two of them the margin can be lower, and of the other sign.
5. Write assumptions, current budget, loops, cables, minimum margins, `LIMIT_SOURCE`.

## Check by hand
On one case: the units and the order of magnitude, a conversion in dB, a current in µA and a field in dBµV/m being
consistent through `cable_field` and `i_adm`.

## Reporting
- Table of board loops: net, length, area, worst frequency, field, margin to class B.
- Per cable: estimated common-mode current against the admissible current, typical and pessimistic cases, with
  the mechanism in one line; figure of the spectrum against the limit for the power cable, fitted and unfiltered.
- The sources that are not quantified, ranked, each with what will be measured.
- **Measurement plan**, per cable: current probe around the whole cable close to the board, receiver in 120 kHz
  quasi-peak (or peak), reading compared with the admissible current of the table; near-field probe on any
  isolated converter and on the switching node, before and after any change; then the pre-scan in a chamber or on
  an open site. State the value that means pass.
- A deviation names the cable, the mechanism and the frequency; its gain in dB in the model is stated as an order
  of magnitude.
- Estimates listed: edges, receiver capacitance, cable impedance and length, protection-device capacitances,
  inductor self-resonance, quasi-peak factor of a noise-like signal, spread-spectrum gain. The limits are printed
  as indicative, with the test distance.
