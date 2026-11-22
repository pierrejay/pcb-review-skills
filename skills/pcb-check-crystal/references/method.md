# Crystals: method in full, board table, algorithm, validation, reporting

## Method, step by step
For each crystal:
1. **Load capacitance seen.** Each side: `C_side = C_ext + length × C' + C_pad + C_pin`. Then `CL_seen = C_a·C_b / (C_a
   + C_b) + C_pp` (series of the two sides, plus the capacitance between the pins) (`crystal.side_capacitance`,
   `crystal.load_seen`). `C'` is computed for the board: `C' = t_pd / Z0`, with the propagation delay and the impedance
   of the track as routed (width, dielectric, plane distance, from the stackup file and the impedance check). The
   default of `crystal.py` (`C_PER_MM_DEFAULT`, 0.112 pF/mm) is an order of magnitude for a track of about 50 Ω over a
   close plane (a 0.15 mm track over 0.1 mm of prepreg: 0.118 pF/mm under solder mask, 0.105 pF/mm bare;
   `fieldsolver2d.solve(...)["c_pf_per_mm"]` gives the board's). The other defaults (`C_PAD_DEFAULT` 0.3 pF,
   `C_PIN_DEFAULT` 2 pF, `C_PP_DEFAULT` 0.3 pF between the pins) are estimates to list; the pin capacitance varies
   widely between ICs (a few pF). IC with integrated load capacitors that its datasheet declares "for a crystal of CL x"
   without publishing the internal value: the series of the two sides is then x, so take 2x per side including the pin,
   that is `C_int = 2x − C_pin` per side (estimate; 22 pF per side for x = 12 pF and a 2 pF pin). The board then only
   adds tracks and pads.
2. **Frequency shift.** From the equivalent circuit, `Δf/f = (C1/2)·(1/(C0 + CL_seen) − 1/(C0 + CL))` (the finite
   change; the slope `S = C1 / (2·(C0 + CL)²)` is given for reading only, it understates a shift of several pF)
   (`pulling_sensitivity`, `frequency_shift`). With C1 unpublished: 4 fF for a 3.2 × 2.5 mm crystal in fundamental
   mode (estimate). |Δf/f| = (C1/2)·|CL − CL_seen| / ((C0 + CL_seen)·(C0 + CL)) decreases as C0 grows: the budget
   takes the minimum C0, 0 when the datasheet gives only a maximum (`worst_shift`, over the load corners); the
   maximum C0 is the one of steps 4 and 5.
3. **Budget** = tolerance + stability + |load shift| + ageing, arithmetic sum (worst case), in ppm, against the
   requirement (`frequency_budget`; the budget at the minimum C0, its `verdict` "pass", "unpublished_c0" (fails only
   at the C0 of 0 of an unpublished minimum, passes at the maximum C0: a reservation, `../SKILL.md`, "Unpublished
   C0 min and C1") or "fail"). A budget that fails gives the smallest
   C0 that would pass, from `(C0 + CL_seen)·(C0 + CL) = (C1/2)·|CL − CL_seen| / ((requirement − tolerance − stability
   − ageing)·10⁻⁶)` at each corner (`c0_needed_pf`): the minimum C0 to obtain from the crystal's manufacturer,
   reported with the verdict; when even the maximum C0 fails (`c0_max_passes` False), say so: no C0 figure rescues it.
4. **Oscillation margin.** Critical transconductance with the two sides apart, `gm_crit = (ESR + R_s)·ω²·(Ca·Cb +
   C0'·(Ca + Cb))² / (Ca·Cb)`, `C0' = C0 + C_pp` (equal sides: `4·(ESR + R_s)·ω²·(C0' + Ca/2)²`), `R_s` being the series
   resistor on the output side, added to the ESR as a pessimistic simplification with no published source (with `R_s` =
   0 it is the formula of the crystal application notes, e.g. ST AN2867); transconductance required for a gain margin of
   5: `5·gm_crit` (`gm_crit`, `gm_margin5`). At fixed Cb it is convex in Ca, lowest at `Ca = Cb·C0' / (Cb + C0')`: the
   worst is at a corner of the two sides, not necessarily the largest load (`worst_gm_crit` over the ends of each side).
5. **Drive level.** `I = ω·(C0 + CL_seen)·V_pp / (2√2)`, `P = ESR·I²` (`drive_level`). The amplitude at the crystal
   is rarely published: bracket it with 1.8 V and 3.3 V peak-to-peak (estimate).
6. **Centring value** (information): among the standard C0G values (15, 18, 20, 22, 24, 27 pF), the one that,
   fitted on both sides, brings `CL_seen` closest to CL (`centring_value`).

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table**
- one dictionary per crystal part: `CL`, `ESR`, `C0_max`, `C0_min` (None when unpublished: 0 is used), `tol`, `stab`
  (with its temperature range in the comment),
  `age`, `DL_max` — source: datasheet and page;
- estimates as named constants: `C_PER_MM`, `C_PAD`, `C_PIN`, `C_PP`, `C1_MOTIONAL`, internal capacitors (the
  defaults of `crystal.py` are the values above; a board that measured or recomputed one of them passes its own);
- cases: `(label, frequency, (net_in, net_out), (cap_ref_in, cap_ref_out) or (None, None) when the capacitors
  are integrated, series resistance, requirement in ppm, source of the requirement)`.

**Algorithm**
1. Load the board; index footprints by reference designator.
2. Length of a net = sum of `GetLength()` over the tracks of that net whose class is `PCB_TRACK` **or**
   `PCB_ARC`, converted from nanometres to millimetres. The whole net counts, branches included: every piece of
   copper adds capacitance (this is not a signal-path length).
3. External capacitor: parse the footprint's Value field (`"18pF"`); integrated: the declared estimate.
4. Steps 1 to 6 of the method, by the functions of `crystal.py`; round only when writing.
5. Write the JSON of the tool contract, with the verdict lines computed from these numbers by the criteria of
   `../SKILL.md`.

## Validation cases
Reference values for the arithmetic by hand: a crystal of CL 12 pF, ESR 50 Ω, C0 3 pF, ±10 ppm at 25 °C, ±20 ppm
over −40 to 85 °C, ±3 ppm ageing in the first year, 200 µW maximum; estimates at the defaults of `crystal.py`. Its
pulling sensitivity at CL is `S` = 8.9 ppm/pF (C1 4 fF). These are checks of the formulas, not expected results for
a board: C0 is 3 pF in every column. At C0 = 0 (a crystal that publishes only its
3 pF maximum) the shifts read +16.7 / −10.2 / +48.2 ppm and the budgets 49.7 / 43.2 / 81.2 ppm; the second fails its
40 ppm and passes from C0 = 2.60 pF (`c0_needed_pf`), against 35 ppm not even at 3 pF.

| Case | Sides (pF) | CL_seen | Shift | Budget / requirement | gm_crit (×5) | Drive level, 1.8 / 3.3 V |
|---|---|---|---|---|---|---|
| 24 MHz, 2 × 18 pF, tracks 11.2 and 5.3 mm, R_s 22 Ω | 21.55, 20.89 | 10.91 pF | +10.5 ppm | 43.5 / 50 ppm | 1.27 (6.3) mA/V | 89 / 299 µW |
| 25 MHz, integrated capacitors (22 pF + pin), tracks 2.6 and 9.5 mm, R_s 0 | 24.59, 25.36 | 12.79 pF | −6.6 ppm | 39.6 / 40 ppm | 1.23 (6.1) mA/V | 125 / 419 µW |
| 25 MHz, 2 × 15 pF, tracks 8.4 and 4.4 mm, R_s 0 | 18.24, 17.79 | 9.31 pF | +29.2 ppm | 62.2 / 100 ppm | 0.75 (3.7) mA/V | 76 / 254 µW |

Centring value for the first case: 20 pF → 11.91 pF; for the third: 20 pF → 11.81 pF.

## Reporting
- One table per crystal: CL specified, each side term by term, `CL_seen`, shift, each term of the budget, total,
  requirement with its source, margin; `gm_crit` and the gm needed; drive-level bracket against the maximum.
- State the temperature range of the stability term next to the scope's range.
- A deviation gives its cause term by term (which capacitance, which track), the correction (reference of the
  capacitor, new value, resulting `CL_seen` and budget) and the gain in ppm. If the budget passes, "Nothing to
  do", even when the load is not centred.
- A budget tight or failing only through C0 = 0 and an estimated C1 is unpublished data, not a defect of the board:
  `../SKILL.md`, "Unpublished C0 min and C1" (the IC manufacturer's recommendation or a measurement on a buffered
  clock output settles it).
- A budget that fails at the minimum C0 gives `c0_needed_pf` next to the verdict, as the minimum C0 to request from
  the crystal's manufacturer.
- Estimates listed with what they touch: C' when it is not computed for the board, pin, pad and pin-to-pin
  capacitances (`CL_seen`), C1 and C0 taken at 0 for want of a published minimum (shift), amplitude (drive level),
  internal capacitors.
- Say which ageing figure is in the budget: the first-year value is not the value at the end of the service life.
  When the datasheet gives only the first year, take the figure the manufacturer publishes over the service life
  (for the part or its family); otherwise the extrapolation is an estimate said as such, with its law: ageing
  usually slows with time, and the ratio of 10 years to the first year varies with the part. If the
  verdict depends on it, the figure is asked of the designer or the manufacturer.
- Measurements to request when gm or the amplitude is unpublished, or when the drive-level bracket straddles the
  maximum: start-up at the cold end of the temperature range; drive level with a current probe on the crystal
  lead or a probe of 1 pF or less (a heavier probe on the pins changes the load it is supposed to observe).
