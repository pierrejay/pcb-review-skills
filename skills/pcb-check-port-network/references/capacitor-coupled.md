# Port network: capacitor-coupled single pair (e.g. 10BASE-T1L, 10BASE-T1S, 100BASE-T1, 1000BASE-T1)

The steps carry the numbers of `../SKILL.md`, "Method"; the common method and circuits are in `method.md`.

## The network and what to check
- *Network.* Series or termination resistors per the datasheet, coupling capacitors (hundreds of nF for a
  low-frequency line code, less for faster links), common-mode choke, capacitors from each line to ground, line
  TVS, second-stage array. With power over the data line, its inductors and their ranges belong to the network.
- *Signal.* E.g. 10BASE-T1L: PAM-3 at 7.5 MBd, a long-reach mode of a few volts peak-to-peak and a short-reach
  mode of about 1 V, useful band from about 0.1 to 20 MHz, signal band up to about 3.75 MHz; 10BASE-T1S: DME at
  12.5 Mbit/s (spectrum up to about 25 MHz), multidrop on a short segment; 100BASE-T1: PAM-3 at 66.7 MBd.
- *Multidrop.* The standard gives a capacitance budget per node of the bus (of the order of 15 pF differential is
  the figure commonly quoted for 10BASE-T1S; step 6).

## Step 2: the return-loss half circuit
`return_loss_db`, or the same ladder (conventions: `method.md` § 3): transmitter = its series resistor (a
low-impedance driver); ∥ one channel of the second-stage array; + coupling capacitor in series; + half of the
choke's differential leakage in series; ∥ (capacitor to ground + line TVS).

## Step 3: mismatch of a multidrop port
With few pF per line: mismatch = two ESD diodes per line, each taken at half its maximum capacitance (estimate) +
routed length mismatch × the per-millimetre capacitance to ground of the stretch (from the solver; e.g. a few
hundredths of a pF/mm over a far plane, of the order of 0.1 pF/mm over an adjacent one), and termination resistors
at ± their tolerance.

## Step 6: multidrop node, differential capacitance budget
Tracks: differential capacitance per millimetre of each stretch from the 2D solver (`method.md` § 4), **each
stretch on its own reference** (plane on the adjacent layer; far plane two layers down; nothing), times its length,
branches included (counted at the coupled-pair value, which over-estimates them). Pads: an SMD pad is a stretch of
single microstrip of the pad's width and length over its reference (fringe of the short sides neglected), i.e.
`c_pf_per_mm` of a single track of the pad's width × pad length; a pad loads its line to ground, and two pads of C
each, one per line, are seen as C / 2 in differential (in series through the ground): the pads add a **quarter** of
the sum of their capacitances to ground (balanced excitation, as `cdiff = c_odd / 2`). Without reference (and for a
through-hole pad), the pair of pads is solved as a pair without plane at their width and gap, `cdiff_pf_per_mm` ×
pad length, plus the barrel, as an estimate (already differential: added as is); unknown is never 0, and a budget
that this estimate decides is a reservation. Through-hole pads of a terminal block over a far plane: of the order of
0.3 pF per line to ground (a ring at a fraction of a millimetre from the plane edge, a few hundredths of a pF per mm
of perimeter), 0.15 pF in differential for the pair. Components, typical and maximum: IC input, each pair of ESD
diodes (half the per-line value), an open relay in series with the termination (a fraction of a pF, estimate). The
choke's inter-winding capacitance is almost never published: the budget gives **what is left for it at the maximum
of the components** (remainder = node budget − total; the verdict is on the maximum).

Self-check: sum of the stretch lengths = extracted length of the nets; every pad of the two nets counted once (a
choke or capacitor pad shared by two stretches belongs to one of them); **failure if a stretch has a reference that
the declared design intent does not expect** (the routing or the extraction has changed).

`node_budget.py`, venv (numpy/scipy), reads the geometry JSON of the impedance check → `results/node_budget.json` =
per stackup `{stretches, pads, C_tracks, C_pads, C_components typ/max, C_without_choke typ/max, left_for_choke
typ/max}`.

| Item | Limit | Source |
|---|---|---|
| Differential capacitance of a multidrop node | ≤ the node budget of the standard | IEEE 802.3 clause of the link (indicative) |

Report: table stretch → length, reference, impedance, pF/mm, pF; table of pads; components typical / maximum; total
and what is left for the choke, as a reservation that no datasheet lifts: "choke capacitance not published: <x> pF
left at the components' maximum; measure the differential capacitance of the node on a prototype before freezing
the choke". Limits: pads as microstrip stretches, through-hole pads and relay as estimates.

## Cases
- **A filled criteria table for one PHY.** A 10BASE-T1L-type PHY, long-reach mode, whose datasheet gives its
  network with ranges:

  | Item | Limit | Source |
  |---|---|---|
  | Transmit / receive resistors | 50 Ω / 2 kΩ (±1 % retained, in-house) | PHY datasheet, application figure |
  | Coupling capacitors | 230 nF (±10 % retained, in-house) | same |
  | Capacitor from each line to ground | 100–400 pF | same, component table |
  | TVS line → ground | < 75 pF | same |
  | Total capacitance of a line to ground | ≤ 475 pF at the components' maxima | the two rows above bound two parts on the same line: the manufacturer allows up to 400 pF of capacitor and a 75 pF TVS together |
  | Protection between lines | < 100 pF differential | same |
  | Common-mode choke | 450 µH – 2.2 mH; leakage < 500 nH; < 200 mΩ | same |

  Both tables are titled as recommended ranges: each row is a known-good starting point, the total of the line
  is what the PHY sees. Teaches: the table is read in the datasheet of the PHY fitted, and the largest total is
  identified from what that datasheet allows; a second PHY of the same link type may give other ranges.
- **The protection is most of the port's capacitance, and its spread is most of the imbalance.** Same port: 2 ×
  100 pF C0G ±5 %, one bidirectional TVS of 60 pF typical / 100 pF maximum per line, 2 × 220 nF, a 470 µH ±50 %
  choke, an array of 1.8 pF per channel. All elements in range; 160 to 205 pF per line for 475 pF allowed; the TVS
  alone at its maximum (100 pF, at 0 V) exceeds its own recommended row (75 pF): reported with its effect, not a
  deviation. Return loss 28 dB at 3.75 MHz with the TVS (24 dB at its maximum) against 43 dB without. Conversion
  ≥ 38 dB with equal TVS, 25 dB with one at its typical value and the other at its maximum, 52 dB if everything
  were matched at 1 %. Emission margin to class A 42 / 28 dB; injected noise 8.3 / 41 mV at the PHY lines in band
  (10 V EMF behind 150 Ω, reverse excitation; reusing the DM → CM conversion would have given 25 / 124 mV).
  Teaches: when the protections' spread dominates the imbalance, tighter capacitors to ground bring little; the
  immunity estimate needs the reverse excitation, not the conversion ratio.
- **On a multidrop port, a length mismatch adds to the capacitance mismatch.** A 10BASE-T1S-type node, a few pF
  per line: 2.55 mm of difference between the legs over a far plane adds about 0.13 pF to the 1 pF of ESD diode
  estimate: 1.13 pF of mismatch, conversion ≥ 46 dB. Teaches: on a node with few pF per line, routing mismatch is
  of the same order as the parts' spread.
- **A node budget is spent mostly by the components.** Same node: a pair of 7.5 mm over the adjacent plane then
  26 mm over a far plane; tracks 1.99 pF, pads 0.30 pF (a quarter of their 1.18 pF to ground), components 6.5
  typical / 9.0 maximum (PHY 5.5 / 7.5, two diode pairs, a relay): 8.8 / 11.3 pF for a 15 pF budget, **3.7 pF left
  for the choke at the maximum**, which its datasheet does not give: to be measured.
- **Count the pads and the branches.** On a small node they can be a large share of the track capacitance;
  branches to protections are capacitance (of the order of 0.25 pF/mm over an adjacent plane), not line.
