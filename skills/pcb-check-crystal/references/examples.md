# Crystals: application cases, requirements as examples

## Reference crystal
The cases below that say "reference crystal" use this one: a 3.2 × 2.5 mm fundamental-mode crystal, CL 12 pF,
ESR 50 Ω, C0 3 pF maximum and no minimum published (the shift is taken at C0 = 0, gm and drive level at 3 pF),
±10 ppm at 25 °C, ±20 ppm stability over −40 to 85 °C, ±3 ppm ageing in the first year, 200 µW maximum drive level;
estimates at the defaults of `crystal.py`. Its load capacitors are 2 × 18 pF unless the case
says otherwise.

## Requirements as the board table holds them
Each entry carries a value, its source and the interface it protects; the most demanding consumer of the clock
sets the entry. Examples of such entries (to be taken again from the datasheet of the part at hand, not copied):
- an interface standard for the link the clock feeds, e.g. ±50 ppm for 100 Mb/s Ethernet over copper
  (IEEE 802.3; indicative until confirmed in the applicable edition);
- an IC that asks tighter than that standard, e.g. ±40 ppm on a 25 MHz clock (about 24.999 to 25.001 MHz) with
  ±20 ppm recommended, in a table of its electrical characteristics;
- an IC that asks ±100 ppm or better, with a crystal of CL 12 pF and 15 pF fitted on each pin in its recommended
  external components.

Teaches: the entry is read from the datasheet of the IC and from the standard of the link, the tighter one is
kept, and each carries its source into the JSON.

## Cases by mechanism
- **A load a pF off centre is ten to seventeen ppm.** Reference crystal at 24 MHz with 11 mm and 5 mm of track and a
  22 Ω series resistor: 10.9 pF seen, +16.7 ppm at C0 = 0 (+10.5 ppm at its 3 pF maximum), budget 49.7 ppm against a
  ±50 ppm requirement on the nominal load: the load corners decide. The centring value (20 pF, 11.9 pF seen,
  +1.3 ppm) is the remedy if they fail. Teaches: compare the budget with the requirement before proposing any
  change; a centred load matters only when the budget is tight, and the minimum C0 is what makes it tight here.
- **A margin from the temperature range of the stability term is not counted.** Reference crystal at 25 MHz with
  integrated load capacitors (the case after next): budget 43.2 ppm against ±40 ppm (39.6 ppm had C0 been 3 pF),
  with a stability given over −40 to 85 °C in a product scoped for 0 to 40 °C: a margin is likely, the datasheet
  neither quantifies nor guarantees it (the extreme of the curve can fall inside 0 to 40 °C). The budget fails on
  paper; it passes from C0 = 2.6 pF, the minimum C0 to obtain from the manufacturer; the report states both ranges.
  Teaches: the range of the stability term is stated next to the range of the scope, and a margin that nothing
  guarantees is not taken as one.
- **The shift can come from an estimate.** 2 × 15 pF as recommended by the IC manufacturer gave 9.3 pF seen and
  +48 ppm (C0 = 0) with a pin capacitance taken at 2 pF; with 5 to 6 pF per pin the load is centred. The
  manufacturer's fitting is kept; budget 81 ppm for ±100. Reference crystal at 25 MHz, tracks of 8.4 mm and
  4.4 mm, no series resistor. The budget is tight through data no crystal publishes (C0 min, C1), not through the
  board, which follows the IC manufacturer's recommendation: the designer accepts it (Pass *) or has the frequency
  measured on a buffered clock output. Teaches: when the shift rests on an estimate that the datasheet does not
  publish, vary the estimate over its plausible range before recommending a change, and settle unpublished data
  by the manufacturer's recommendation or a measurement rather than by a reservation.
- **With integrated capacitors, the routing is the whole deviation.** Reference crystal at 25 MHz, integrated
  capacitors assumed 22 pF per side plus the pin (a datasheet declaring them for a crystal of CL 12 pF), tracks of
  2.6 mm and 9.5 mm: the 9.5 mm output track moved the load to 12.8 pF (−10 ppm at C0 = 0). Teaches: the only
  terms the board controls are tracks and pads, so the track length of each side is the quantity to look at.
- **Oscillation margin and drive level end in a measurement.** On the three cases above, `gm_crit` of 0.75 to
  1.27 mA/V with no gm published; drive level 76 to 125 µW at 1.8 V peak-to-peak and 254 to 419 µW at 3.3 V for a
  200 µW maximum: the bracket straddles the limit. Teaches: with no published gm or amplitude, the report gives
  `gm_crit`, the gm needed for a margin of 5 and the bracket, and specifies the measurement.
