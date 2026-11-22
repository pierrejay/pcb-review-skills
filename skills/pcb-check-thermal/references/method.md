# Thermal: losses, inventory, the 2D model, the fit of h, junctions and verdict, board tables, validation, reporting

## 1. Powers per component, by scenario
- "Typical" and "envelope" scenarios when the manufacturer does not publish the consumption of the main IC;
  "measured" as soon as the designer has a bench figure; transceivers idle or transmitting continuously; two
  input voltages when the range is wide.
- An SoC total is split between its rails by fractions (core, logic, memory, I/O) to obtain the rail currents
  (`soc_rail_split`). The fractions come from the datasheet or from a measurement; assumed fractions are estimates,
  marked as such, to be replaced.
- Buck stage: conduction Irms² × (D × RDS high-side + (1 − D) × RDS low-side), Irms² = I² + ΔI² / 12 with ΔI the
  inductor ripple (`power_sequence.inductor_ripple` at the same corner), plus a fixed term for switching and control
  (the default `p_fixed_w` is of the order of a few tens of mW per output: an estimate, to replace by the datasheet
  or a measurement); inductor Irms² × DCR plus its core loss (`p_core_w`, 0 by default: of the order of a few milliwatts
  for a small power inductor, an estimate to enter) (`buck_loss`, `inductor_loss`). The I² + ΔI² / 12 form is the
  triangle of continuous conduction; in discontinuous conduction use the RMS of the real waveform.
- Upstream converter: loss = P out × (1 / η − 1) with η read on the datasheet curve at the real input voltage and
  current; split between the IC and its inductor by a share that is an assumption to replace (`efficiency_split`,
  argument `ic_share`; the conduction terms of the buck formula give it when the resistances are known).
- Series diode: VF at the input current × that current. Power mux or load switch: I² × on-resistance. LDO:
  (Vin − Vout) × I + Vin × Ignd, the ground current at that input, load and temperature (`ldo_loss`); the input
  power and the upstream current include Ignd too. Isolated transceiver: the part of its input power dissipated in
  the package.
- Power delivered to something outside the board counts in the input power, not in the heat of the board.

## 2. Inventory balance
Power entering the board = Σ placed lines + spread line + off-board lines, within 1 % of the entering power
(`inventory_balance`). The heat dissipated on the board is Σ placed + spread.

## 3. Board temperature
The board is thin compared with its size: one node per square cell through the whole thickness (`thermal2d.py`).
Between neighbouring cells the conductance is the sheet conductance k·t = Σ layers (k_Cu × thickness × copper
fraction) + k_FR4 × board thickness (k_Cu = 390, k_FR4 = 0.3 W/m·K; harmonic mean of the two cells). Each cell
exchanges with the ambient through both faces: (h_top + h_bot) × d²; the board edges exchange nothing. Each source
is spread uniformly over **every cell its footprint box touches** (cell indices floor((c ± w/2) / d), upper one
included: a 5 mm footprint at the centre of the JEDEC board covers 11 cells of 0.5 mm, not 10). The fit of h and
the parts of the board use the same rule: with a different cell rule in the fit and in the board run, the h fitted
and the h applied would not describe the same footprint. The solution is the **rise** above ambient; with a
constant h it does not depend on the ambient.

## 4. The exchange coefficient h
h lumps natural convection and radiation of a board face (of the order of a few to a few tens of W/m²K per face,
depending on orientation, temperature rise and surroundings). It is fitted so that the model reproduces a
datasheet: the solver is run on a model of the JESD51-7 board (114.3 × 76.2 × 1.6 mm, two full inner planes of
35 µm, outer faces of 70 µm covered at 5 %) with 1 W spread over the footprint of the part at the centre;
θ board→air(h) is the mean rise under the footprint. h is the value for which **θ board→air = θJA − θJB**
(bisection between 1 and 60 W/m²K, `calibrate_h`).
Two fits on two datasheets do not agree, because θJA = θJB + θ board→air is only approximately true. Worked
example: a large-package SoC (θJA 17.9, θJB 8.2 °C/W, 12 × 12 mm) gives h = 21 W/m²K; a small-package PHY
(θJA 52, θJB 30 °C/W, 5 × 5 mm) gives h = 5.8 W/m²K. The in-house policy keeps three values (`H_BOUNDS`, with their
provenance in `H_PROVENANCE`): **5.8 (pessimistic, still air), 12 (central, between the two fits: free air, natural
convection and radiation), 21 (optimistic)**, and gives the result at all three; between the two extremes the mean
board rise varies by a factor of the order of three. The two extremes are the fits of those two packages; the
central value is an assumption, not a fit.

## 5. Junction temperatures
Tj rise = mean board rise under the footprint + P × θJB. When θJB is published, use it. When only θJA is
published, **deduce θJB at the same h**: θJB = θJA − θ board→air(JEDEC model, this h, footprint of the part)
(`deduce_theta_jb`). The model then returns exactly the datasheet θJA on the JEDEC board, whatever h, and the
uncertainty on h acts only through the real board. The θJB obtained so is a parameter of this model (JEDEC
parameters hold for their measurement conditions), not an intrinsic resistance to carry to another model. The
board run holds for a part inside the domain of the model (`../SKILL.md`, "Domain of the model"). Maximum
admissible ambient = Tj max − Tj rise.

## 6. Verdict
Judge at the **pessimistic scenario**: of the three h, the one that gives the hottest junction, taken from the results
and not assumed (`worst_h`). When the board is smaller than the JEDEC board it is usually the lowest h; check it. When
it is larger, with θJB deduced at each h, it can be another: a 200 × 150 mm board with the layers of the JEDEC board and
one 5 × 5 mm source of θJA 100 °C/W at its centre, 1 W, 25 °C of ambient, gives 120.2 °C at h = 5.77, 123.4 °C at h = 12
and 124.4 °C at h = 21, because the deduced θJB grows with h (78.0, 83.6, 86.2 °C/W) faster than the large board cools
(17.2, 14.8, 13.2 °C/W). Give, next to it, **the smallest h that still holds the limit** (`min_h_holding`). It answers
"how much worse than still air may the product be", so only the exchange of the product board varies: θJB stays at the
value used at the lowest of the three h (deducing θJB at a lower h would shrink it, which is favourable for no reason).
With θJB fixed the rise falls when h grows, which is what makes a bisection legitimate; `min_h_holding` checks it over
the interval before searching. When the limit already fails at the upper end of the search it answers `fails_at_top`
with the margin there: no minimum exists in the interval, and the junction is a fail, not an incomplete chapter. The
limiting part is the one with the smallest margin to its own junction limit at each
trial h, not the hottest one, nor the one found at the start.

## 7. Linear regulator dropout
Vin at the regulator = minimum of the source − (I + Ignd + other loads) × (switch resistance + cable resistance,
both ways): the resistance carries the regulator's input current, its output current I plus its ground current Ignd
at that input and load, and the other loads fed through the same switch and cable; margin = Vin − Vout − dropout at
the output current I (when only one point is published, dropout taken proportional to the current: estimate)
(`ldo_dropout_margin`, `i_gnd_a` required, `i_other_a`).

## 8. Board tables and algorithm
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Export.** Board table: the layers; the dissipating references (every key of the budget); the cell size (e.g.
0.25 mm). Algorithm:
1. Grid: `bb = board.GetBoardEdgesBoundingBox()`, `x0, y0 = bb.GetX() / 1e6, bb.GetY() / 1e6` (nm → mm),
   `nx = int(width / d)`, `xs = [x0 + (i + 0.5) * d for i in range(nx)]`, same for ys.
2. Board mask (`board_mask(board, xs, ys)`) and copper fraction of each layer
   (`copper_fraction(board, layer, xs, ys, d)`): the slow step, several sampled points per cell and per layer, each
   tested against the copper.
3. Per dissipating reference: its value, side and the bounding box of its pad centres.

**Model.** Board table: `H_BOUNDS` (the three h); `PARTS`: reference → (name, θJA on the JEDEC board, published
θJB or `None`, Tj max, footprint in mm used for the JEDEC model), each with its datasheet in a comment and assumed
values marked; copper thickness per layer; the `budget(scenario)` function returning `{reference: watts}` and the
input power; the scenarios; an optional measured consumption, a parameter of its target in the Makefile.
Algorithm:
1. Sheet conductance of the board from the copper fractions (`sheet_kt`; grid in mm in the JSON, metres in the
   solver).
2. Cell set of each part: bounding box of its pad centres from the export + 0.3 mm, intersected with the board
   mask (`footprint_cells`). A dissipating reference of the budget with no cell set stops the run.
3. For each h and each scenario (`junction_table`): θJB of each part (§ 5, deduced at that same h when not
   published), power map with each line spread uniformly over its cells, `solve`, mean rise under each footprint,
   junction rise and admissible ambient (§ 5); mean and maximum rise of the board.
4. **Minimum h that holds** (`min_h_holding`, § 6): at the worst scenario and the maximum ambient of the scope,
   bisection between a floor (1 W/m²K) and an upper end that is a parameter, by default the lowest of the three h,
   on the h of the board alone, θJB of each part frozen at its value at that lowest h; the quantity followed is the
   smallest margin to Tj max over all the parts.
5. Write one block per (h, scenario) and the minimum h; map of the board rise for the envelope scenario.

## 9. Validation cases
- Mean board rise by hand: P / (2 h A) for a plate of area A, whatever its conductivity (2 W on 65 × 51 mm at
  h = 12: 25.1 K); a board run's mean rise is of that order.

## 10. Reporting
- Table component / scenario → maximum admissible ambient at the central h, with both bounds in brackets; mean
  board rise; copper coverage per layer; thermal vias under each exposed pad (count); the thermal path of every
  part judged (pad net, vias counted, plane reached); the minimum h that holds, "holds at least down to" the
  floor of the search, or "fails at the upper end" with the margin there; the map.
- A deviation gives the cause (which power, which resistance), what is concerned (which scenario and ambient),
  the precise remedy with its quantified gain (thermal pad from the package top to a metal enclosure, lower
  input voltage, other package), not an asserted one.
- Estimates listed: h, assumed θJA values, consumption scenarios, loss model of the converters.
- Measurements to request when consumption decides: input power under maximum load (maximum CPU load for a
  processor), then a re-run with the measured value; the temperature of the top of the main IC (thermocouple)
  re-fits h.
- Maps drawn from the current result by one plotting function, labels in the report's language, and looked at in the
  rendered report.
