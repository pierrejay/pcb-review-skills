# Thermal: application cases

## Cases by mechanism
- **On a small board the temperature is set by the total power over the area, not by a hot spot.**
  Setting: a four-layer board of 65 × 51 mm (33.2 cm² per face), copper coverage 68 % / 94 % / 94 % / 71 % by
  layer, a few parts dissipating a few tenths of a watt to under a watt, 2D model at the central h = 12 W/m²K.
  Result: 1.96 W dissipated gives + 25 K of mean board rise, 3.79 W gives + 48 K; an SoC of 0.9 W with θJB
  8.2 °C/W sits only 7 K above the board under it. Teaches: when the mean board rise dominates, every part rides
  on that pedestal; the first quantity to read is total power over board area, and moving a part or adding local
  copper changes little (the remedies are a path to the enclosure or less power).
- **A budget is an inventory before it is a map.**
  Setting: the same board, power budget built from the rail currents. Closed inventory: 2.50 W enter at the
  input connector, 0.54 W leave to an external device, 1.96 W are dissipated, of which 0.18 W are a line spread
  over the whole board (loads that have no footprint in the model). Lines of this kind are easy to leave out of
  the placed parts; the injected power then falls short of the dissipated one by their share, and since the board
  rise is proportional to the power the table shows less heat than the board has: on that board, a gap of the
  order of 7 % of the power was worth 4 to 5 K at the lowest h, enough to show 1 K of margin where the board
  had none. Teaches: the solver's energy balance proves the solver, not the inventory
  (a mean rise that matches P / (2·h·A) shows the same); only the balance computed from the rails sees a load
  counted in a rail current and attributed to nothing. The total reported as "dissipated" is the heat on the
  board, not the input power, which here also contains the power assumed for the external device.
- **The exchange coefficient decides, so all three values are shown.**
  Setting: the same board, the main SoC in a "typical" consumption scenario, then with a bench-measured
  consumption, scope maximum ambient 40 °C. Result: the admissible ambient of the SoC spans several tens of K
  across the three h in the typical scenario. With the measured consumption the board holds the 40 °C scope by
  31 K at the central h; at the lowest h a small LDO (admissible ambient 36 °C) and a buck converter (37 °C) fall
  short: "pass with reservation", settled by one measurement on the prototype. Teaches: when h is an estimate, a
  verdict given at one h hides the spread; the three figures show which parts depend on it and what to measure.
- **θJA alone under-estimates a part on a small board, and a pessimistic scenario is not a bound.**
  Setting: a 3.3 V LDO (θJA 92.5 °C/W on the JEDEC board) dissipating 0.43 W on a 43 × 60 mm board that
  dissipates 1.09 W in all, scope maximum ambient 40 °C. Result: the hand calculation gives + 40 K, the model
  + 73 K at the lowest h (θJB deduced 68–76 °C/W): the other 0.66 W heat the board under it. Admissible ambient
  52 / 69 / 76 °C at h = 5.8 / 12 / 21; the part holds 40 °C down to h = 4.4 W/m²K (θJB kept at its value at
  5.8): a pass on a bare board, and nothing says that a closed box stays above 4.4. Teaches: the board under a
  part is heated by its neighbours, which θJA ignores; and the verdict is stated with the minimum h that holds
  (a reservation for a closed enclosure, case temperature to be measured on the mounted board), not with a
  scenario taken for a bound. A reservation exists only if the estimate can flip the verdict for the scope: none
  for a bare board when the pessimistic h passes with a wide margin, a named measurement for a boxed product.
- **The limit can be the part's own ambient range.**
  Setting: a product whose scope reaches a high ambient, built around an SoC of a commercial temperature grade
  (a range narrower at the hot end than an industrial one). Teaches: compare the ambient of the scope with the
  range stated in each part's datasheet; the part's own range may limit the product before its junction does.
- **Remedies are given with their gain.** Setting: an SoC whose junction limits the ambient, and a buck converter, whose
  loss grows with its input voltage, fed at 24 V or at 12 V. Result: a thermal pad from the top of the SoC to a metal
  enclosure is not credited through ψJT (a characterisation parameter, valid only in the conditions of its measurement,
  not the resistance of a path that now carries heat): it is quantified with the package's θJC(top), the pad's contact
  resistance and the enclosure's heat rejection, or measured; a 12 V input instead of 24 V gives + 14 K of admissible
  ambient on the buck. Thermal vias are counted under each exposed pad and compared with the datasheet's land pattern.
  Teaches: a remedy is quantified in K of admissible ambient before it is proposed.

