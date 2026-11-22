# Power input: chain model, component models, board table, algorithm, netlist template, reference cases, reporting

## 1. Model of the chain
Connector node → bidirectional TVS to ground → series Schottky → node of the first capacitor (and of the
unidirectional TVS when it is there) → filter inductor (inductance, DCR, saturation) → converter node: second
capacitor, load. The values below are starting assumptions (estimates) to be replaced by the datasheet or
the measurement as soon as it is available:
- connector and track on the input side: a capacitance of the order of 100 pF and a leakage resistance of the
  order of 100 kΩ to ground (without a DC path the blocked series diode leaves a floating node);
- class-2 capacitors at their effective value on the curve of the exact part (`mlcc_bias.capacitance`), a constant:
  at the operating voltage first, then, when the margin is small, at the voltage the first run reached, the result
  saying which (`pcb-verification`, failure modes). A part used at about half its rating or more often keeps only a
  third to a half of its nominal value, and the overshoot depends on it. Neither value is a bound: a capacitance that
  falls with the voltage rings higher than any fixed value (lossless, a step of height E reaches 2 E with any fixed
  C, 3.5 E with C0 / (1 + (V / E)²));
  ESR of the order of 5 mΩ and ESL of the order of 1 nH in series for a ceramic of a small case (the ESL raises the
  TVS current on a 1 ns edge);
- load as a resistor R = V / I at the operating current;
- supply cable of the case (`../SKILL.md`, Method 3): loop inductance of the order of 0.7 µH per
  metre for a two-conductor cable (estimate; it depends on the spacing of the conductors) and loop resistance
  from the conductor cross-section (tens of mΩ per metre for common gauges); replace both by the real cable.
  Source at nominal + its tolerance (e.g. + 10 %), applied in a step of about 1 ns (an idealisation: the cable
  and contacts slow a real step);
- surge: lumped combination-wave generator `cwg_iec61000-4-5.lib` (produced by `cwg_fit.py`: 1.20/50.0 µs in open
  circuit, 7.82/20.4 µs in short circuit, 2.00 Ω), coupled through the network of the scope; indicative values of IEC
  61000-4-5: 18 µF (2 Ω source, line to line), 40 Ω + 0.5 µF (42 Ω source, signal-port type) or 10 Ω + 9 µF (12 Ω
  source, line to earth on a power port: § 6, "Line-to-earth surge"); the DC supply feeds the input through a decoupling
  inductance (e.g. 1.5 mH).

## 2. Component models (behavioural, pattern in `lib/models/`)
- **TVS**: a diode model whose breakdown reproduces the datasheet: `BV` = breakdown at 1 mA, `RS` = dynamic
  resistance, so that the clamping voltage at the published 8/20 µs current is met (`tvs_fit_exact` on two
  published points; `tvs_fit_quick` to compare candidates, 0.2 V pessimistic). Two variants: typical (BV =
  typical breakdown) and maximum (BV = Vc max − I × RS − NBV × Vt × ln(I / IBV) at the published point (Vc max, I),
  RS of the exact fit, the same law as the model). A bidirectional part is two such diodes back to back.
- **Series diode**: forward law fitted on two or three datasheet points; `BV` set at VRRM so that exceeding the
  rating shows.
- **Saturable inductor**: the datasheet gives one point (− 30 % at Isat). Soft saturation fitted on that point,
  L(i) = L0 / (1 + (i / IK)²) with IK = Isat / √(1 / 0.7 − 1) (`saturation_ik`, e.g. 6.874 A for Isat = 4.5 A), is an
  **estimate**. The linear inductor is usually higher and converges more easily, but is not a bound (a variant of
  the chain can give a slightly higher peak with the saturable one): near the limit both are run and the verdict
  takes **the higher of the two**.

## 3. Cases and what is read
The order of the cases is that of `../SKILL.md`, Method 3. When the scope allows a reversed connection (a connector or
terminal block that accepts it), the reversed hot-plug: the same step at − (nominal + tolerance) behind the cable, run
until the steady state, an ideal source behind the cable resistance bounding the current (the source's stated current
limit can replace it). On each run read: maximum
and minimum at the converter node; maximum at the clamp node (they differ as soon as an inductor or a resistor sits
between them); clamp current of each TVS against its 8/20 µs rating and its peak power (the maximum of the instantaneous
product v(t)·i(t), not the product of the two maxima); reverse voltage of the series diode against VRRM
(`v(mid) − v(vin)`), its reverse current (negative part of `i(Vd)`) and the energy absorbed in reverse (∫ reverse
current × reverse voltage dt); forward peak of the diode; peak current in the inductor; extreme voltage at the
connector; TVS current `max(0, −min i(Vtvs))`. On the reversed hot-plug, also the steady state at the end of the run:
the voltage at the converter node and across the series element, and the current and dissipation (v × i) of every part
that conducts (TVS or diode forward, body diode of a protection MOSFET), against the continuous ratings; when a fuse is
meant to clear, its clearing time at that current against what the conducting part withstands for that time.

## 4. LC input filter: transient, not only stability
An input filter is usually sized on attenuation and on stability (Middlebrook: output impedance of the filter
well below the negative input resistance V² / P of the converter). That says nothing about its response to a
step. If the clamp sits **before** the inductor, it holds its own node, and the inductor with the converter-side
capacitor forms a resonant circuit of characteristic impedance Z0 = √(L / C) that rings above the clamped level
on every step (hot-plug, surge). An undamped LC often has a Z0 more than ten times its losses, and a step can
then approach twice its height: for example, 1.5 µH and 1.3 µF (a 10 µF 50 V 0805 X5R at 24 V) give Z0 ≈ 1.07 Ω
against some tens of mΩ of losses, almost no damping. Therefore:
1. simulate the filter in transient, in the full chain, with the clamp where it is on the board;
2. simulate the corrections and tabulate them: **clamp moved to the converter side of the inductor** (it then limits the
   converter pin directly; check what the first capacitor and the diode see); **series R–C damper** across the
   converter-side capacitor (`damper`: the optimum R of Erickson and Maksimović for a damping capacitance n times the
   one it damps, 0.61 × Z0 for n = 4, as a starting point to verify in transient on the full chain; an electrolytic
   capacitor whose ESR is near that R does both; its capacitor must reach n × C in EFFECTIVE value, often more than
   a class-2 part of the same size holds); a **resistance in series in the supply path**, between the clamp and the
   converter capacitors (`series_damper`, C effective, verified by `conducted_emi.damping` with `r_series`; about
   L / (C·z_max) for R well under Z0, and nothing reaches a z_max under √2·Z0), one part that also limits the
   current of a clamp behind it, at the cost of I²R losses, a DC drop and the hot-plug and surge pulse it takes; a
   resistor in parallel with the inductor (often the least effective, to be simulated like the others).
3. judge the damping or limiting resistor that carries the pulse (series or in an R–C damper) on the **single-pulse
   curve** of its manufacturer: the energy of the pulse from the transient (∫ R i² dt in ngspice; by hand,
   `mlcc_bias.charge_loss` for a hot-plug onto a discharged input, ½ C V² for a fixed C), its equivalent
   duration E / P_peak, and the curve's power at that duration. A family that publishes no single-pulse curve
   ("anti-surge" lines without one) cannot be verified: its verdict is a reservation, or a part with a curve is
   proposed.

## 5. When the clamp is not enough: coordination
- **Two coordinated stages**: power TVS at the connector → series diode → pulse resistor → second TVS and
  capacitor at the converter. The resistor limits the current of the second TVS, and its value is bracketed:
  - lower bound, from the second TVS: R ≳ (V1 − Vd − V2) / I2max, with V1 the clamping voltage of the first stage
    at the current it carries, Vd the drop of the series diode, V2 the clamping voltage of the second TVS and
    I2max the current it may take (its 8/20 µs rating, with the margin of the scope); a first-order estimate,
    verified in transient;
  - upper bound, from the resistor itself: the voltage across it during the wave (I × R, of the order of the
    wave current times R) within its 1.2/50 µs withstand, and its continuous dissipation R × I² within its
    rating at the operating current, plus the DC drop the converter's input range can afford.
  The window between the two is often narrow: simulate a few values on both sides before choosing.
- **Converter with a higher input rating**: with a power TVS fitted on its 8/20 µs data, a single stage can keep
  the node under the rating. The higher rating buys the permanent range; whether it also removes a stage is
  shown by the simulation, not assumed.
- A dedicated protection IC (eFuse) has its own absolute maximum: it still needs an input TVS that holds the
  node under it during the wave. It brings functions, not the removal of the power TVS.

## 6. Board table and algorithm
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table** at the top of the main script: the chain as a netlist template with the values read from the PCB;
DC-bias curves of the capacitors and their source; inductor L0, DCR, Isat; model names of each TVS and diode with the
datasheet and the points they were fitted on in a comment; `LIMITS` (converter continuous and short-duration maxima,
diode VRRM, TVS 8/20 µs rating); cable cases; the list of cases `(key, label, source fragment, TVS model variant,
stop time, time step)`: the node voltages judged with the maximum TVS model (the typical model beside it for the TVS
current), the input capacitors at their effective value (§ 1). A capacitor corner, when the margin calls for it, is
per group (the parts on one node), × (1 − tolerance) or × (1 + tolerance): the charge drawn through the source path
grows with C (hot-plug I²t of a fuse, C × E² / (2 R) through a resistive path; forward peak and IFSM of the series
diode); a node voltage need not, and can peak on a mixed corner, the group ahead of the filter high and the one
behind it low. The stop time contains the whole wave and the decay of the resonance (typically tens of µs at a step
of about 1 ns for a hot-plug, a hundred µs or more at about 10 ns for a surge).

**Algorithm**
1. Build the netlist: includes of the models, the chain with a 0 V source in series with each element whose
   current is needed, the source fragment (hot-plug or surge: one per run, the excerpt shows both), options,
   `.tran`, and a `wrdata` of the probes. The transient starts from the DC operating point, without `uic`: all
   capacitors discharged and the source at 0 V for a hot-plug, the chain settled at the supply voltage for a surge.
2. Run it with `spice.run`, kind "slow", `measures` naming the `.meas` of the quantities the verdict reads (a rail's
   maximum and minimum, a current's peak as the `MAX` of a B source `V=abs(i(v…))`): it tries one other option and
   raises when neither converges. The row records the inductor model and the `note` of the run.
3. Read the columns (`wrdata` writes a time column before each vector: vector k is column 2k + 1) and compute
   the quantities of § 3.
4. Studies import the main module, substitute one element (clamp node, inductor law, damper, alternative TVS)
   and run the case that decided the verdict first.

The script around the netlist (write, run, read, loop on the cases) is ordinary and is rebuilt per board; the
netlist is the part worth keeping. `{…}` are filled in by the script:

```spice
* excerpt (chain template; values and model names are examples taken from lib/models, node names generic)
* first: .include of the TVS, Schottky and connector-TVS models and of cwg_iec61000-4-5.lib
* connector: bidirectional TVS; 0 V sources are ammeters (current counted from first to second node)
Vcon vin ncon 0
Xcon ncon 0 SMAJ33CA
Cvin vin 0 100p
Rvin vin 0 100k
* series Schottky, then the node of the first capacitor ("mid"); each class-2 capacitor is its effective value
* (section 1): here a 10 uF 50 V 0805 X5R, 1.3 uF at 24 V (section 4), ESL 1 nH, ESR 5 mOhm
Vd vin nd1 0
Dser nd1 mid DSS3150
Lc1 mid mid_c1_l 1n
Rc1 mid_c1_l mid_c1 5m
Cc1 mid_c1 0 1.3u
* unidirectional TVS, cathode on the rail, on the node under study: {clamp} = mid or conv
Vtvs 0 ntvs 0
Dtvs ntvs {clamp} DTVS2700_MAX
* filter inductor with its ammeter, then the converter input ("conv")
* saturable (estimate, -30 % at ISAT = 4.5 A: IK = ISAT / sqrt(1/0.7 - 1) = 6.874); linear run: Lf nl nr 1.5u
Vl mid nl 0
Lf nl nr L = '1.5u/(1+(i(Vl)/6.874)^2)'
Rf nr conv 44m
Lc2 conv conv_c2_l 1n
Rc2 conv_c2_l conv_c2 5m
Cc2 conv_c2 0 1.3u
Rload conv 0 60
* optional damper, series R-C across the converter-side capacitor:   Cd conv nd 22u   /   Rd nd 0 0.68
* --- source, hot-plug: step behind the cable ({l_cable}, {r_cable}: loop inductance and resistance of the cable of the case, § 1)
* --- reversed hot-plug: the same step to -26.4
Vsrc src 0 PWL(0 0 1u 0 1.001u 26.4)
Rcab src ncab {r_cable}
Lcab ncab vin {l_cable}
* --- source, surge between the two wires: supply behind its decoupling network, generator, coupling
*     2 Ohm: Ccpl sg vin 18u          42 Ohm: Rcpl sg sgc 40  +  Ccpl sgc vin 0.5u
Vsup sup 0 24
Ldec sup ndec 1.5m
Rdec ndec vin 0.1
XCWG sg 0 CWG params: UPK={u_peak} TD=5u
.options method=gear reltol=1e-3 abstol=1n vntol=10u itl4=200
* other attempt: that of spice.run, kind "slow" (lib/spice.py)
* probes written with wrdata: v(conv) v(vin) i(vtvs) i(vd) i(vcon) v(mid) i(vl); their extremes as .meas
```

In ngspice, write `area=2`, never a bare area factor, after a model name
ending in a digit (the parser otherwise takes the factor for part of the name: "could not find a valid
modelname").

### Line-to-earth surge
The chain is the same with its ground renamed `bgnd` (earth is node 0); one netlist per wire (`vin` or `bgnd`) and
ground configuration, the fragments below replacing the source of the excerpt. Only the configurations of the scope,
the one expected to be the worst first: earthed for the clamps and the converter node, floating or through a capacitor
for the barrier to earth (§ 7). They are those of `../../pcb-check-surge-esd/references/method.md`, "Ground-return
configurations", with their estimates: each is a candidate the designer confirms or removes.

```spice
* supply on both wires through the decoupling network; its supply side held to earth (1 uF each: estimate)
Vsup sp sn 24
Cdp sp 0 1u
Cdn sn 0 1u
Ldp sp vin 1.5m
Ldn sn bgnd 1.5m
* generator to earth, line-to-earth coupling on the wire under test ({wire} = vin or bgnd); {r_cpl} + {c_cpl}:
* 10 Ohm + 9 uF on a power port, 40 Ohm + 0.5 uF on a port treated as a signal port
XCWG sg 0 CWG params: UPK={u_peak} TD=5u
Rcpl sg sgc {r_cpl}
Ccpl sgc {wire} {c_cpl}
* board ground to earth, one configuration per run (0 V source: the current of the link)
*   floating:          Cst bgnd 0 50p  +  Rleak bgnd 0 1meg
*   earthed enclosure: Vge bgnd ng 0  +  Lge ng 0 20n
*   Y capacitor:       Vge bgnd ng 0  +  Cy ng ny 4.7n  +  Ly ny 0 20n  +  Rleak bgnd 0 1meg
* Rleak (estimate of the leakage to earth, 1 mA at 1 kV) gives a ground with no DC path to earth its operating
* point: without it ngspice places bgnd anywhere (tens of volts) and the stress read against earth is offset
* probes: v(conv)-v(bgnd) v(vin)-v(bgnd) v(bgnd) i(vtvs) i(vd) i(vcon) i(vge)
```

Every quantity of § 3 is read **against `bgnd`**, and two more: `v(bgnd)` against earth, from its value before the wave
(the barrier: capacitors to earth, distances to earthed parts) and the current of the ground link. Generator check: the
coupling network alone into a short to earth gives about U / 12 Ω through 10 Ω + 9 µF (83 A at 1 kV) and 0.93 × U / 42 Ω
through 40 Ω + 0.5 µF (22.1 A at 1 kV).

## 7. Reference cases
Chain of the excerpt: 400 W 33 V bidirectional TVS at the connector, 150 V Schottky, 27 V unidirectional TVS and a
10 µF 50 V 0805 X5R at the first node, 1.5 µH / 44 mΩ / Isat 4.5 A, the same capacitor and 60 Ω at the converter;
source 26.4 V at hot-plug, 24 V under surge. Orders of magnitude, not values to reproduce, kept for what they teach.

At hot-plug the clamp node holds about 33 V while the converter node behind the filter rings to 51.9 V on the 2 m
cable (saturable inductor; 51.2 A in the TVS, 57.4 A with the linear one) and to 39.3 V on the 10 m one (20.9 A; 35.9 V
with the linear one): the shorter cable damps less, and neither inductor model is the higher on every quantity. The
ESL of the capacitors raised the TVS current on the 1 ns edge by up to 43 %. The series diode sees 94.6 V in reverse
at − 1 kV / 42 Ω, and 71 V after the + 1 kV wave.

Line-to-earth, + 1 kV through 10 Ω + 9 µF, against `bgnd`: with the board ground earthed (20 nH), the wave on the +
wire goes through the series diode into the first clamp, about U / 12 Ω (88 A in the TVS, 82 A in the ground link):
four times the current of the 42 Ω line-to-line case (23 A), and the converter node at 49.5 V, above its 40 V; on
the − wire it goes straight to earth through the ground link. Floating (50 pF) or through a 4.7 nF capacitor, the
whole board follows the wave: the differential stress stays moderate (36 to 38 V at the converter) and the barrier to
earth takes about the full peak (965 to 986 V).

## 8. Reporting
- Table case × variant: converter node, clamp node, TVS currents, diode reverse voltage, with the limits in the
  header; the verdict at the higher of the two inductor models when both were run; the two waveform figures with the
  limits drawn.
- A correction names which part moves to which node, its value and footprint, with the simulated result of that
  change.
- Estimates listed: effective capacitances, saturation law, cable, TVS ratings read from a power-duration curve; the
  cases not run (cables, levels, wires and ground configurations, corners), with their reason.
- Out-of-scope levels are reported separately, as information for the manual.
- Measurements to request: hot-plug oscillogram at the converter pin with the longest and the shortest cable;
  fast transients (not simulated here).
