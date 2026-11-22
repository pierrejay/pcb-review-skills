# PDN voltage drop: application cases

## Cases by mechanism
- **The highest current does not give the worst rail.** Setting: the core rails of an SoC fed by a multi-rail
  power-management IC on a four-layer board; the manufacturer publishes no per-pin currents, so envelope values
  are used and the copper temperature of the scope is 70 °C. Computed: the mesh drop of each rail against its
  regulated low margin (set-point check). Result: CPU rail 1.0 A, 8.7 mΩ, 10.4 mV for 116 mV of margin; logic
  rail (0.9 V) 0.5 A, 25.5 mΩ, 15.3 mV for 21 mV; memory rail 0.3 A, 21.2 mΩ, 7.6 mV for 25 mV. The 0.9 V rail
  combines the thinnest set-point margin with the highest resistance (it runs on the two outer layers only): 6 mV
  left. The correction is on the set-point (one feedback-divider resistor, computed as in the set-point cases of
  `pcb-check-power-rails`), not on the copper. Teaches: rank rails by remainder and equivalent resistance, not by
  current; and when the margin is eaten by the set-point tolerance, the remedy is the divider, not more copper.
- **On a small board fed by one regulator through planes, the drop is negligible, and it is worth one run to say
  so.** Setting: a 3.3 V rail from one regulator to all consumers (90 to 200 mA each) over four layers with
  planes. Computed: the mesh at two cell sizes, the loads declared pad by pad: an analogue supply taken at the
  rail-side pad of its ferrite, and a microcontroller's current split 60 % on its core pins and 40 % on its I/O
  pins (an assumption, to be listed among the estimates). Result: 0.6 to 1.1 mV at 70 °C. Teaches: a run closes
  the question with a number in minutes; the declaration of the loads (which pad, which share of the current) is
  where the effort goes.
