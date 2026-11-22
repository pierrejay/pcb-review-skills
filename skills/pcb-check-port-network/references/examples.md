# Port network: a plane-or-no-plane study, a stackup pitfall

The cases of each family are in its file (`capacitor-coupled.md`; none yet for `transformer-coupled.md`).

## A plane-or-no-plane study (multidrop pair, cable side)

Setting: the 26 mm of pair on the cable side of the 10BASE-T1S-type node of `capacitor-coupled.md`, three variants
at equal routing (production stackup; range for ±10 µm of etching per flank):

| Variant (pair, mm) | Zdiff | C added | Left for the choke, typ / max | Line → ground | Return inductance → peak across the choke at 4 kV |
|---|---|---|---|---|---|
| No copper on any layer (0.192 / 0.14) | 112 Ω (104–122) | 1.3 pF | 6.6 / 4.1 pF | 0.4–0.8 pF | 6 nH → 191 V |
| Plane on the adjacent layer (0.12 / 0.17) | 99 Ω (91–108) | 3.1 pF | 4.8 / 2.3 pF | 5.7 pF | 0.5 nH → 42 V |
| Plane two layers down (0.192 / 0.14) | 111 Ω (103–120) | 1.55 pF | 6.3 / 3.8 pF | 1.25 pF | 1.2 nH → 57 V |

Retained by the designer in that case: the far plane, the protections returned to it by a direct via, and the
pair widened to 0.30 / 0.14 mm for 100 Ω. Mode conversion was unchanged by the far plane and 0.9 to 4.9 dB better
with the adjacent one; under the choke a far plane kept continuous cost about 0.1 pF, where a plane on the
adjacent layer would have cost 0.76 pF. Teaches: voiding everything under a pair saves node capacitance but
lengthens the return of the protections; a far plane can keep most of the capacitance gain and most of the ESD
return.

## Pitfall
**The stackup moves a pair over an adjacent plane far more than one over a far plane**: tens of ohms between a
production and a prototype laminate for the first, much less for the second.
