---
name: pcb-check-thermal
description: "Thermal check of a PCB: dissipation per component, board temperature on the real copper (2D conduction plus convection), junction temperatures (SoC, converter, LDO) and maximum admissible ambient, LDO dissipation and dropout."
---

# Check: thermal (junction temperatures, admissible ambient)

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `thermal2d.py`: solver, JEDEC board, `calibrate_h`;
- `thermal_budget.py`: inventory balance, the three-h policy, θJB deduced at the same h, admissible ambient, the h that
  gives the hottest junction, the minimum h that holds, loss formulas;
- `kicad_copper.py`: `board_mask`, `copper_fraction`.

## Purpose
Up to which ambient temperature does each dissipating component stay under its maximum junction temperature, on
this board, with its real copper and its real neighbours? The answer is a **maximum admissible ambient** per
component and per consumption scenario, to compare with the ambient of the scope of use. For a linear regulator
the check also covers its dropout at the real input voltage.

## When it applies
- **Hand calculation is enough** for a lone part with a wide margin: P = (Vin max − Vout) × I max + Vin max ×
  Ignd for a linear regulator (ground current), Tj = Ta + P × θJA at the published board conditions.
- **Use the 2D model** when the margin is thin, when several sources share a small board (Pitfalls), or when the
  consumption of the main IC is uncertain and scenarios must be compared.
- The scope sets the judgement: maximum ambient, open air or enclosure, ventilation, input voltage range,
  duty of the transceivers. The ambient meant here is the air around the board: inside an enclosure, the internal
  rise comes on top.

## Inputs to obtain
- **PCB**: board outline, copper of each layer, position and side of each dissipating footprint. **Stackup**:
  copper thickness per layer, board thickness.
- **Datasheets**: θJA with the board it was measured on (typically the JEDEC 2s2p board of JESD51-7; the
  datasheet states the conditions), θJB and ψJT when published, maximum junction temperature, ambient range of
  the part itself; converter efficiency curves at the real input voltage and load, switch resistances, inductor
  DCR and the ripple current; ground current of each linear regulator at its input, load and temperature; forward
  voltage of a series diode at the real current.
- **Power budget** per scenario (shared with `pcb-check-power-rails`), an **inventory**: every watt that enters
  the board is attributed to a component, to an explicit "spread over the board" line, or to an explicit
  off-board line.
- **Designer**: maximum ambient and enclosure, measured input power or current when it exists.

## Method
1. **Powers per component, by scenario** (`buck_loss`, `inductor_loss`, `efficiency_split`, `diode_loss`,
   `switch_loss`, `ldo_loss`, `soc_rail_split`): the envelope scenario first, the others (main-IC consumption,
   transceiver duty, input range) when its margin is thin.
2. **Inventory balance** (`inventory_balance`) of a scenario before its board is solved.
3. **Board temperature** (`thermal2d.solve`, `sheet_kt`, `footprint_cells`): each source is spread over the cells
   of its footprint by the same rule as the JEDEC fit of h; the solution is the rise above ambient.
4. **The exchange coefficient h is the estimate that decides** (`calibrate_h`, `H_BOUNDS`): every result is given
   at the three values of the in-house policy. Refit on the parts of the board at hand (several packages with
   published θJA and θJB) and widen the bracket if the fits fall outside it: the three values are a policy, not a
   measurement. A package whose θJB is most of its θJA fits poorly (θJA = θJB + θ board→air is weakest there): such
   a fit widens the bracket as a sensitivity, and the answer at that end is the condition of step 6, not a verdict
   at that h.
5. **Junction temperatures** (`junction_rise`, `admissible_ambient`): θJB published, else deduced **at the same
   h** as the board run (`deduce_theta_jb`). A deduced θJB is a parameter of this model, not a property of the
   package to reuse in another model.
6. **Verdict** at the h that gives the hottest junction, computed from the results (`worst_h`), never assumed to
   be the lowest h; next to it the **smallest h that still holds the limit** (`min_h_holding`), with θJB frozen at
   its value at the lowest h because the datasheet measurement does not change when the product is boxed: that is
   the condition a measurement must confirm. A limit that holds at the top of the bracket and not at its bottom is
   that condition, "pass if h ≥ h_min", a reservation with the measurement that settles it, not a fail. A limit
   that already fails at the upper end of that search (`fails_at_top`) is a fail, written with its margin there.
7. **Linear regulator dropout** (`ldo_dropout_margin`): dissipation judged at the maximum of the source, dropout
   at its minimum, after the drop in the switch and in the cable both ways of the current they carry: the
   regulator's output current plus its ground current, plus the other loads fed through the same switch and cable.
   The dropout itself is read at the output current.
8. **Ambient range of the parts themselves**: the range stated in each part's datasheet checked against the
   ambient of the scope (a commercial-grade part may have a narrower range than the product).

## Criteria
| Criterion | Form | Number read in |
|---|---|---|
| Junction | Tj ≤ Tj max at the maximum ambient of the scope, envelope scenario, at the hottest of the three h, for a verdict without reservation **on a bare board** (in-house choice of h) and for a part inside the model's domain (below); the minimum h that holds is reported for any other mounting | part datasheets |
| Ambient range | ambient of the scope inside the range of each part | datasheets |
| Regulator | Vin min − Vout ≥ dropout at the real current | regulator datasheet |
| Thermal vias | counted under each exposed pad, compared with the land pattern | datasheet; no numeric criterion |

The lowest of the three h is a bare board in still air, not a physical bound: inside a closed enclosure the
exchange referred to the outside ambient can be lower. If the scope excludes a closed enclosure and the
pessimistic scenario passes, no reservation; otherwise the reservation names the measurement (case temperature
of the limiting part, board mounted, worst supply and load). If it passes only at the central value, say so with
the three figures and ask for the measurement that settles it.

**Domain of the model, checked part by part.** One node through the thickness assumes that the heat of a part
reaches every layer under it. That holds when the part's thermal path is tied to the inner planes: an exposed pad
on a plane net with thermal vias, or leads into copper that vias connect to a plane. A part whose heat stays on an
outer layer (no vias under it, a pad on an isolated island) is outside the domain, and the model is optimistic
for it, all the more as the part is small and dissipates much. Its verdict is a reservation, unless a pessimistic
bound is computed with, in the cells under and around the part, only the copper its heat actually reaches.

## Self-checks
- **The total printed and reported is the heat dissipated on the board**, with the input power and the
  off-board power beside it; never the input power under the name "dissipated".
- A deduced θJB must be positive; a negative value means the footprint or the θJA entered is wrong.
- The verdict line names the h it was taken at, computed.
- A fit of h is accepted only with its residual.

## Tool contract
Two scripts, one JSON each in `results/`.
- **Export**, KiCad's bundled Python: writes `results/thermal_geometry.json` (PCB file name, cell size, origin, grid,
  board mask, copper fraction per layer and cell, per dissipating reference its value, side and the bounding box of its
  pad centres).
- **Model**, venv (numpy, scipy, matplotlib), reads the geometry: writes `results/thermal.json` (per h and scenario:
  input power, mean and maximum board rise, per part power, board rise, θJB used, junction rise, Tj max, admissible
  ambient; the minimum h with its θJB and residual) and a map of the board rise for the envelope scenario.
- **No export yet**, for a single regulator: `simplified_board` in the model (a rectangle of the board size, inner
  planes full, outer layers at an estimated coverage, the sources at their positions with estimated footprints);
  the report says it is not the real copper.
- **Refusals of the board scripts**: a dissipating reference of the budget missing from the export.

## Pitfalls
- **A missing share of the power lowers every rise by about that share.** The board rise is, to first order,
  proportional to the power injected: when the mean board rise dominates, a share of the dissipated power left out
  of the inventory lowers every rise by about the same share, and a thin margin can be an artefact of it.
- **Do not use θJA alone on a small board with several sources.** θJA assumes the part alone on a large JEDEC
  board; the heat of the neighbours raises the board under the part, and the model can read much more than the
  hand calculation.

## Limits
h is constant: no dependence on the rise, on orientation or on the enclosure; radiation is lumped into it; an
enclosure is not modelled. One node through the thickness (domain of the model: Criteria); heat leaving through
the top of a package ignored. Copper is a smeared fraction per cell; power is uniform under each footprint.
Converter losses come from efficiency curves and resistances, not from a measurement. What to measure:
`references/method.md` § 10.
