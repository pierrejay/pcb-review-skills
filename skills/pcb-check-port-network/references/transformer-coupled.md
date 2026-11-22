# Port network: transformer-coupled twisted pair (e.g. 10BASE-T, 100BASE-TX, 1000BASE-T)

The steps carry the numbers of `../SKILL.md`, "Method". No worked case for this family in `examples.md`.

## The network and what to check
- *Inputs.* The PHY's driver type (current-mode or voltage-mode), read in its datasheet. **Magnetics datasheet**:
  turns ratio, open-circuit inductance with its bias current, leakage inductance, inter-winding capacitance,
  isolation rating, return-loss and insertion-loss curves, the internal common-mode termination if any and where
  its end goes.
- *PHY side, by driver type.* A current-mode driver (common on 10/100 PHYs) usually takes a termination resistor
  from each line to the centre tap of the PHY-side winding (of the order of 50 Ω, 1 %), and that centre tap to the
  PHY's analogue supply, decoupled, as its datasheet says. A voltage-mode driver (common on newer and gigabit
  PHYs) is terminated inside the IC: its centre tap goes to ground through a capacitor, or is left as the
  datasheet says, never to a supply; an external termination would double the internal one.
- *Magnetics* (discrete, or inside the jack): turns ratio (1:1 on most 10/100/1000 PHYs, some use another ratio),
  open-circuit inductance under a DC bias (of the order of 350 µH under a few mA is the figure commonly asked for
  100BASE-TX), leakage, inter-winding capacitance, isolation (of the order of 1.5 kV rms is the figure commonly
  quoted for Ethernet), and the common-mode choke on the cable or PHY side. Step 1 judges each against the
  magnetics datasheet, the open-circuit inductance at the bias current that flows in the winding.
- *Cable side.* The centre taps of the cable-side windings are commonly tied, each through of the order of 75 Ω,
  to a common node, then through a high-voltage capacitor (of the order of 1 nF, rated for the surge level) to
  ground or chassis: a common-mode termination of the pairs. Its end net, its effect on discharges and surges, and
  its capacitor's rating are judged with `pcb-check-chassis-grounding` and `pcb-check-surge-esd`. Inside a jack
  with integrated magnetics, its end is a pin whose net the jack's datasheet specifies (`pcb-check-configuration`).
- *Pairs.* 10BASE-T and 100BASE-TX use two pairs (one per direction), the other two are often terminated the same
  way; 1000BASE-T uses four pairs, each carrying both directions through the PHY's hybrid with the same network.
  Pairs with the same network are computed once; the termination of the unused ones is checked.
- *Signal*: 10BASE-T, Manchester at 10 Mbit/s; 100BASE-TX, MLT-3 at 125 MBd (scrambled, most of its energy below
  about 30 MHz); 1000BASE-T, PAM-5 at 125 MBd per pair; amplitudes of the order of 2 V peak-to-peak differential
  for 100 and 1000 Mbit/s, more for 10BASE-T.
- *Return loss.* The standards give a mask over the band of the link; commonly quoted orders of magnitude: about
  16 dB at low MHz up to a few tens of MHz, then decreasing with frequency to the top of the band (about 80 MHz
  for 100BASE-TX, 100 MHz for 1000BASE-T). Magnetics datasheets often give their own return-loss curve, which
  includes their part of the budget.

## Step 2: the return-loss half circuit
Conventions: `method.md` § 3. Current-mode driver: source = the termination resistor of the line (to the
AC-grounded centre tap); ∥ the IC pin capacitance; ∥ half of the open-circuit inductance (it is across the
winding); + half of the leakage of the transformer and of the choke, in series; ∥ the cable-side capacitance of
each line to ground (protections, pads). A voltage-mode driver starts from the source impedance its datasheet
gives. The inter-winding capacitance and the common-mode termination do not enter the differential half circuit.
A turns ratio n other than 1 (cable-side turns / IC-side turns) is the element ("T", "ideal", n): the IC-side
elements before it, the cable-side ones after it, each inductance on the side its datasheet measures it; it
multiplies the impedance before it by n². Self-check of the halving convention before this ladder is trusted: the
capacitor-coupled ladder built with `ladder_impedance` gives the same result as `return_loss_db`.

## Steps 3 to 5: not computed
The network of `method.md` § 3 does not apply (its sources are referenced to ground; a winding's common-mode
impedance is not that): `conversion` and `injection` refuse `coupling="transformer"`. List the mismatch on the
cable side (protections, pads, the centre-tap termination) and the balance of the magnetics, which only its
datasheet gives (longitudinal balance or common-mode rejection); steps 3 to 5 are reported incomplete, with the
measurement specified.

## Criteria rows of the family
| Item | Limit | Source |
|---|---|---|
| Wiring of centre taps, terminations, the end of a common-mode termination | as the datasheet requires (driver type) | line IC and magnetics datasheets |
| Magnetics | turns ratio, open-circuit inductance under bias, isolation as the IC and the link ask | IC datasheet; IEEE 802.3 clause of the link (indicative) |

## Pitfall and limit
- **Wire the centre taps by the driver type of the PHY fitted, read in its own datasheet**, not by habit or from
  another PHY's reference design: the two driver types take their centre taps and terminations to different places.
- Magnetics are modelled by their datasheet parameters (no frequency-dependent core loss).
