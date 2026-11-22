# Power rails: application cases, the other pitfalls

## Cases by mechanism
- **A set-point is judged against the intersection of the domains it feeds.** A 0.9 V logic rail feeding a
  logic domain (0.855–0.998 V) and analog domains (0.81–0.99 V) has 0.855–0.990 V to live in. With VREF 0.6 V
  ± 2 % and 1 % resistors, 49.9 kΩ on 100 kΩ gave 0.899 V [0.876; 0.924], 21 mV of low margin; 52.3 kΩ gives
  0.914 V [0.889; 0.939], 34 mV. A memory I/O rail at 1.362 V [1.320; 1.405] sat 13 mV from the top of
  1.283–1.418 V: one resistor from 127 kΩ to 124 kΩ centres it (margins 20 and 32 mV). Teaches: a thin margin has
  a one-resistor remedy, and the remedy is given with the resulting nominal and range, not as a remark.
- **The lower limit of a rail is set by its most demanding load.** On a 3.3 V rail, one Ethernet PHY analog supply
  asked 3.15 V minimum while the other loads accepted 3.0 V; the downstream-rail criterion is 3.15 V. Teaches:
  read the range of every domain a rail feeds and keep the highest minimum and the lowest maximum.
- **The input a buck needs at its current.** A 3.3 V buck with a 100 mΩ switch and a 44 mΩ inductor, 0.4 A:
  3.3 + 0.4 × 0.144 ≈ 3.36 V of input at the limit of regulation, about 3.5 V with an in-house margin (stated as
  such). Teaches: the input the converter needs is output + I × (RDS(on) + DCR) plus a margin, and it is that
  value, not the nominal input, that a source dip is compared with.
- **An RC on an enable is a time; a power good is a state.** Four rails sequenced by RC networks on enables
  guaranteed only between 0.4 and 1.5 V had negative margins at the datasheet limits. Chained by power good, the
  same four rails start about 0.9 ms apart (one soft-start each); what remains to check is a level, as in the next
  case. Teaches: a time that depends on thresholds spread over a wide guaranteed range cannot be guaranteed, a
  state that does not can be.
- **Chained power goods: every level, each judged.** Setting: buck converters on a 5.0 to 5.5 V input, the
  open-drain power good of each holding the enable of the next low through a 100 to 150 kΩ pull-up to the input
  rail. Datasheet constants: power-good low level 0.4 V at 1 mA (sink rating 5 mA), enable guaranteed off ≤ 0.4 V
  and on ≥ 1.2 V, power good valid from 1.4 V of input, lockout 2.3 V typical and 2.45 V maximum falling, pins rated
  6 V, power-good threshold 95 % rising and 90 % falling (typical), soft-start 0.9 ms typical.
  - *Held low*: 0.4 V ≤ 0.4 V is met at equality (zero margin at the guaranteed limits); at the real pull-up
    current of 33 to 50 µA the level is about 13 to 20 mV (proportional estimate). With a 1.5 kΩ pull-up at 5 V the
    current is up to 3.33 mA: within the 5 mA sink rating, but above the 1 mA at which 0.4 V is guaranteed, so the
    held-low level is not established.
  - *Released*: at the lowest input where a converter runs (2.2 V with these constants), 2 µA of declared leakage
    (1 µA per pin) on 150 kΩ gives 1.9 V against 1.2 V; the network tolerates 6.7 µA there and 25 µA under 5 V. A
    declared leakage of 30 µA reaches only 0.5 V under 5 V: the verdict must fail on that line alone.
  - *Pins*: 5.5 V pull-up rail on a part rated 6 V; power good valid from 1.4 V, below the lockout: met.
  - *Release level against the load*: 95 % of a 1.35 V rail is 1.2825 V, for a load range starting at 1.283 V: on the
    edge; at the estimated 90 % bound of the threshold on the minimum rail, 1.18 V: under it.
  - *Corners* (lockout, soft-start, power-good threshold, independent per converter): upstream rail at 90 % when
    the downstream one starts (threshold estimated between 90 and 98 %); downstream rail at 20 % at most when the
    upstream one reaches 100 % (soft-starts of 0.6 to 1.2 ms). The time margin "upstream at 100 % → downstream
    starts" is −0.12 ms by construction.
  - Teaches: sink rating and guaranteed level are two conditions; the leakage the released enable tolerates is a
    number to compute; the release threshold must be compared with the load's range under a declared requirement;
    the criterion of an RC sequence does not apply to a chained one.
- **An order set by RC on the enables holds only if the RC ratio beats the threshold spread.** Two regulators with
  enable thresholds spread over 0.9–1.4 V and RC values in a ratio of 1.5: − 1.6 ms at worst, order not
  guaranteed; the later enable capacitor from 100 nF to 220 nF gives + 1.9 ms (both figures at nominal R and C: the
  tolerance of the two capacitors comes on top and is part of the corners). Second setting: four channels of one
  multi-rail PMIC, thresholds guaranteed 0.4–1.5 V, networks of 10 and 15 ms, soft-start 0.3 to 0.8 ms: − 0.4 ms
  correlated and − 3.2 ms independent at nominal R and C (− 0.6 and − 3.8 ms with R at 1 % and C at 10 %). Third
  setting: two networks of 10 and 11 ms behind one fixed threshold go from + 0.29 ms to − 0.92 ms with nothing but
  capacitors at ± 20 %. Teaches: thresholds of separate chips are independent, channels of one IC move together only
  on a datasheet clause, the R and C of two networks are separate parts and do not track, and the tolerances of the
  capacitors can reverse a small positive margin.
- **Order between the supplies of one IC, its clock and its reset.** Setting: an Ethernet PHY whose datasheet asks
  its analogue supply "after the I/O supply is fully ramped", both fed from one 3.3 V rail, one through a ferrite;
  its 25 MHz oscillator, on the same rail, starts up to a few ms after the rail; the reset comes from a GPIO of the
  MCU, which is an input at power-up, so the pull-up releases the reset as the rail rises. Result: the supply order
  is not met by construction (a ferrite between two pins on one rail delays by far less than the ramp), the reset is
  released before the clock is stable, and the datasheet's fallback (reset held, released some 100 µs after a stable
  clock) falls on the firmware, to be written as a requirement with its delays. Judging the supply order "met by
  construction" without looking at the clock misses the second failure. Teaches: check inside the IC (supplies,
  clock, reset) as well as between regulators.
- **A part change moves other checks.** Replacing a PMIC by discrete converters removed the 1 µF that decoupled its
  supply pin: the input rail went from 8.9 to 8.5 µF effective, and the margin of the 3.3 V rail during a source
  switch-over from 57 to 46 mV. The lockout threshold of the new converters (2.45 V for 1.8 V) had to be set in the
  same check; the thermal part list, the derating keys and the hand-written lines of the report named the old part.
  Teaches: a removed passive changes a capacitance sum elsewhere; search the old reference everywhere
  (`pcb-verification/references/failure-modes.md`).
- **Ripple is computed on the effective capacitance.** 59 µF nominal on a 3.3 V rail is about 33 µF under bias: ripple
  4.1 mV p-p from the capacitance with the parameters of the validation case (3.38 V out of 5.5 V, 1.5 µH − 20 %, 1 MHz,
  1 A), against 3.4 mV for 40.3 µF; 5 mΩ of bank ESR at 1 MHz brings the 33 µF case to 6.0 mV, over a 5 mV limit that
  the capacitance alone meets. Same value, other part: a 10 µF 0603 under 3.3 V is 4.41 µF in a 10 V part and 6.10 µF in
  a 25 V part of the same case (+ 38 %): worth a BOM change. A typical X5R table gives 0.80 of the marked value for a
  1 µF 0402 25 V at 3.3 V where the curve of the part gives 0.57. Teaches: the capacitors of a rail are read from the
  board and the curve of the exact part number decides; the table only screens.
- **A current limit above the inductor's saturation matters only in a fault.** Limit ≥ 4 A (5 A typical, no
  maximum published) for 4.5 A of saturation and 1.6 A of operating peak: no effect in operation; in a short
  circuit the inductor may saturate before the limit acts (a part limiting at 4.1 A meets the same datasheet line
  and does not saturate it). An inductor of Isat ≥ 5.5 A covers the typical limit with 10 % of margin, not the
  short circuit: with no published maximum, a part limiting at 6 A is within the datasheet. To cover it, obtain
  the maximum from the manufacturer or measure the limit on the prototype. Teaches: write "may saturate", not
  "saturates", when only a minimum of the limit is published.
- **A hot-plugged capacitor is fed by the rail, not through the switch's limit.** 5 V rail of 8.9 µF effective
  behind a power mux (40 mΩ) and a current-limited input switch; a discharged device capacitor plugged on a
  downstream port: 1 µF → rail minimum 4.52 V; 4.7 µF → 3.83 V; 10 µF → 3.19 V, 16 µs under 3.5 V, 16 A of
  peak in the load switch. The switch never limits: the inrush lasts about 1 µs and about 10 µC above 1 A,
  under its trip charge. A 22 µF added next to the port capacitor does as well for the rail as on the rail
  itself (3.66 V) and better for the port (3.42 V against 2.77 V), with the peak halved. Teaches: a limiter with a
  reaction time does not protect against an inrush shorter than it; the useful bulk is the one on the side of the
  inrush.
- **A mux switchover is a hole whose depth follows the threshold tolerance and the fall time.** Loss of the
  priority source with the second one present, capacitors at nominal, rail of 8.5 µF effective: upstream output
  falling in 1 ms, threshold 4.3 / 3.96 V → rail minimum 3.69 / 3.36 V (4.5 µs under 3.5 V at the lowest
  threshold); falling in 100 µs at 3.96 V → 3.31 V, 5.8 µs under 3.5 V. A capacitor upstream of the mux or behind
  the load switch changes nothing: no channel conducts during the hole. Teaches: the lowest threshold and the fastest
  fall make the deepest hole; add bulk only where it holds the rail during the hole.
- **A thin margin at nominal capacitance is not a margin.** 3.3 V converter during the 100 µs switchover above:
  envelope current × 1.5 = 0.44 A, RDS(on) + DCR = 194 mΩ, 33 µF effective, regulated minimum 3.260 V → 3.183 V
  with the capacitors at nominal, 33 mV above the 3.15 V of the most demanding load. With every capacitor at
  − 20 % the 5 V rail falls to 3.18 V (8.0 µs under 3.5 V) and the 3.3 V to 3.099 V (bound (a): 3.184 V −
  0.436 A × 194 mΩ), 51 mV under. One 22 µF 0805 25 V on the 5 V rail, still at − 20 %: 3.89 V, never under
  3.5 V, the 3.3 V stays regulated. Teaches: a thin margin is read again on the low capacitance corner, and the
  remedy verified under it.

## The other pitfalls
- **Give every resonant loop of the transient model its losses**: ESR on the capacitors, DCR on the inductors, a
  resistance on the diodes.
