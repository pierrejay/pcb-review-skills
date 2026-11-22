# Surge, ESD and fast transients: formulas of each step, excerpts, board table, algorithm, validation, reporting

## Method, step by step
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers.

1. **Common-mode equivalent (surge on a symmetric pair).** Both lines being identical, the line-to-earth surge is
   simulated on one node: shunt elements multiplied by the number of lines (two 100 pF → 200 pF, two TVS), series
   elements divided by it (two 50 Ω → 25 Ω, two 2 kΩ → 1 kΩ, winding resistance / 2). Coupling: the generator
   impedance plus the coupling resistors in parallel, as seen from the common mode
   (`tvs_fit.common_mode_source_ohm`: with a 2 Ω generator and two 80 Ω coupling resistors, 42 Ω). ESD is applied
   to **one** line (worst case) with both lines modelled; fast transients are applied in common mode through the
   capacitive clamp (about 100 pF in total, shared between the lines; confirm in the applicable text).
2. **Generators**: `cwg_iec61000-4-5.lib` (`XCWG out ref CWG params: UPK=<V> TD=1u`, signed open-circuit peak) and
   `esd_iec61000-4-2.lib` (`XESD out ref ESDGUN params: VCH=<V>`, capacitors pre-charged: the analysis **must** end with
   `uic`, and the powered board then gets its operating point as initial conditions, algorithm step 2). Fast transient
   5/50 ns: `EXP(0 {V/0.920} 1n 3n 8n 64n)` behind 50 Ω (10–90 % rise 5.0 ns, about 55 ns at half
   height; 0.920 normalises the peak to the set voltage).
3. **Common-mode choke, surge**: saturable inductance (excerpt below) in parallel with a loss resistance (order of
   1 kΩ), then leakage inductance and winding resistance in series. Saturation in common mode is rarely
   published: the first run takes a saturation current from the choke datasheet (saturation current if
   published, otherwise its rated current as an upper bound for the knee; when nothing is published, a stated
   value of a few tens of mA). Near a limit, add the linear bound (never saturates) and a sweep of the saturation
   current, keeping the worst of each quantity: their order is not a law. Leakage: datasheet, otherwise an
   upper-bound estimate of the order of 1 µH for a small signal choke, labelled as such.
4. **Common-mode choke, ESD and fast transients**: two coupled windings with the coupling coefficient `K` chosen
   to reproduce the leakage (differential leakage ≈ 2·(1 − K)·L) **with the parasitic capacitance across each
   winding** (datasheet; otherwise an estimate of a few pF for a small SMD choke). At nanosecond edges it is this
   capacitance that lets the edge through, not the inductance. Saturation unknown: the inductance expected to be
   worst first (nominal, / 10, / 100 ≈ saturated core), the others near a limit.
5. **Protections**: each TVS fitted on the datasheet of the BOM part at the points near the current actually
   seen (`tvs_fit.avalanche_fit`, excerpt below). Rail-to-rail steering array (e.g. an Ethernet-line array): two
   steering diodes per line (to the supply pin and from ground) and the internal zener from the supply pin to
   ground; the supply pin is a parameter (floating, tied to a rail through its track inductance, or on a local
   capacitor biased through a resistor).
6. **Line IC and rails**: internal diodes from each pin to its supply and from ground (generic diode with a small series
   resistance, of the order of 2 Ω as an estimate), behind the real series resistors. A pin whose datasheet documents
   its own protection (an internal zener on an enable input, with a recommended series resistor) is modelled with it:
   the current into that clamp is then the criterion, not the absolute maximum voltage. Each rail, first, = a
   constant capacitance read on the curve of the BOM part at its operating voltage (`mlcc_bias.capacitance`,
   `effective_capacitance`; `failure-modes.md` of `pcb-verification`, § 2), board unpowered: its rise, the charge
   injected over that capacitance, is judged on top of its operating voltage. Near its bound, the powered model
   proposed to the designer adds the load at its typical consumption (a light load is pessimistic for the rise),
   a regulator as a one-way source (`B… I = max(0, (Vnom − V)·100)`: it cannot absorb the injected current) and
   the capacitance re-read at the voltage reached. The same diodes stay in the ESD and fast-transient netlists,
   with the pin capacitance (datasheet; otherwise an estimate of a few pF): a pin modelled as a bare capacitor has
   no clamp, its voltage climbs to whatever the protection lets through and any voltage criterion fails by
   construction. Each IC pin reached by the line is modelled so (an MCU's USB pins as much as a PHY's).
7. **Ground returns as inductances** (`tvs_fit.via_nh`, `track_nh`, `return_path_nh`): via 0.2·h·(ln(4h/d) + 1) nH
   (h, d in mm); track: of the order of a few tenths of nH per mm, falling as the track widens or gets closer to
   its reference plane (`track_nh` takes the value per mm as an argument, its default is a screening value;
   compute the real value from the routed width and the height over the plane). Example with the defaults:
   0.6 mm of track plus a via to a plane 1.38 mm down (0.25 mm hole) ≈ 1.5 nH. Run at twice the computed value as
   margin (estimates).
8. **Ground configurations** (below): the one expected to be worst first; the others, the other choke bound and
   the level sweep (algorithm, step 5) near a limit or when the designer asks.

### Ground-return configurations: a parameter of the netlist
The board ground is a node of its own (`bgnd`); earth is node 0. Each configuration is a netlist fragment between
them, chosen by name. Their elements are estimates to be replaced by what the product gives (cable length, board
area, standoff geometry): stray capacitance board ↔ reference plane, tens of pF (ε0·A/d, or measured); a host
cable, of the order of 1 µH per metre of two-wire cable plus a small resistance; an earthed host, a few tenths of
µH to earth; a battery-powered host, tens to hundreds of pF to earth; an earthed metal enclosure through a
standoff, tens of nH. Each port of the board is a candidate return path, listed with the designer
(`../../pcb-verification/references/failure-modes.md` § 2). A second bus cabled to equipment earthed elsewhere is
modelled with its real elements: clamps on both ends, coupling capacitors, resistance and inductance of the pair
(of the order of 1 Ω and 1 µH for a few metres of cable), bleed resistors.

### Choosing protections
- Compare candidates on the **clamping at the current actually seen** (often 1–3 A behind a choke), not on VC at
  maximum current: read each datasheet's clamping at that current. Avalanche parts rated for a low working
  voltage typically clamp noticeably above it at an ampere; punch-through or snap-back parts clamp lower for the
  same working voltage, at the price of a constraint: the line in operation must never exceed the snap-back
  voltage (and a DC-bias measurement is wanted when one is considered). `tvs_fit.quick_fit` (V1 at 1 A, V2 at I2)
  gives a comparison model 0.2 V above the two points: pessimistic, say so.
- A rail-to-rail array left with its supply pin floating clamps at its internal zener, which is higher than a rail
  plus a diode drop: a line IC whose diodes conduct below that voltage takes the current. Biasing the pin from a
  local capacitor fed from the rail through a resistor lowers the clamp towards the rail plus a diode drop
  without injecting the wave into the rail; tying it directly to a small supply lifts that supply, and directly to
  the main rail pushes the rail towards the absolute maximum of its most fragile IC. Simulate the chosen
  arrangement for the board at hand (pin floating, tied, biased): the effect depends on the capacitor, the
  resistor and the rail.
- A low clamping voltage **at the connector** means less voltage pushed through the choke during the tens of µs of
  the wave: the current downstream is set by the difference between the connector clamp and the downstream
  clamps, over the choke's leakage and resistance, so what the second stage and the line IC absorb falls with the
  first-stage clamp. Compute it for each candidate rather than assuming.
- Where the board has a low-inductance path to the enclosure near the connector (chassis copper, a screw), a line
  TVS returned to it can keep the surge current out of the signal ground plane; returned to ground, its current
  crosses the plane to wherever ground meets the enclosure or the far end of another cable. Both returns are
  candidates of `GROUNDS`, computed with the tie strategy of `pcb-check-chassis-grounding`.
- Verify for the retained part: VRWM above the line's working voltage, capacitance acceptable as a total per
  line (`pcb-check-port-network`), IPP above the current at the margin level, and that the BOM part number is
  the one modelled: under one generic name, the IPP, the clamping and the working voltage differ from brand to
  brand.
- Width of the TVS connections. Surge: **compute** the adiabatic heating (`tvs_fit.adiabatic_rise_k`),
  ΔT = ρ·∫i²dt / (A²·cv), copper ρ = 1.7·10⁻⁸ Ω·m, cv = 3.45·10⁶ J/(m³·K), ∫i²dt ≈ 0.7·Ipk²·T50 for an 8/20
  (estimate); ΔT therefore scales as Ipk² over (width × thickness)². For an 8/20 µs pulse on common track widths
  and copper thicknesses it is usually small (a fraction of a kelvin to a few kelvin at tens of amperes), which
  makes width a minor concern for the surge; check it with the function. ESD: what counts is the length and the
  vias of the return (tenths of nH per mm, falling by roughly half as a track over a close plane goes from 0.15
  to 0.5 mm of width).

## Building the tool
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract". A single run takes seconds; a sweep is the product
of its dimensions. Run first the case expected to bound the others (the shortest return, the highest level) and
widen only where it does not conclude; a long sweep is proposed to the designer with the question it answers.

**Board table** at the top of each script:
- the chain, element by element, with values read from the PCB (Value field exported by a small pcbnew script, or
  asserted against it) and the **manufacturer part number of each protection asserted**: a model holds for one
  part number of one brand;
- `MODELS`: one `.model` per device with, in a comment, the datasheet, its revision and the points fitted
  (`tvs_fit.model_line` writes the line from the fitted RS and BV);
- `GROUNDS`: name → netlist fragment between `bgnd` and 0; `LABEL`: name → text of the report;
- `LIMITS`: result key → (limit, source, kind), kind "transient data", "test" or "estimate": the verdict reads the kind,
  so it is data, not a comment; agreed criteria quoted as such;
- `CASES`: (label, netlist options, levels), including the reference "without the protection".

**Algorithm**
1. `netlist(upk, ground, isat, tvs, bias, …)` returns the text. Put a 0 V source in series with every branch whose
   current is judged (choke, TX resistor, TVS group, array supply pin, other-port return). Give every node
   without a DC path a 100 MΩ–1 GΩ leak.
2. `run(name, upk, **options)`: write the netlist and run it with `spice.run` (`pcb-verification/lib/spice.py`),
   the launcher of every netlist of the check, `measures` naming the `.meas` of the quantities the verdict reads: a
   probe judged on its peak, the `MAX` of a B source `V=abs(v(x))`; a rail, its maximum and its minimum, each
   against its bound. The `.dat` is kept only for the cases a figure reads (`toolchain.md`, Disk). `wrdata` writes
   (time, value) pairs: quantity k is column 2k + 1.
   Surge, kind "slow": `.options method=gear reltol=1e-3 abstol=1n vntol=10u itl4=200`, `.tran 5n 120u 0 20n`. ESD
   and fast transients, kind "fast": `reltol=1e-4 abstol=1p vntol=1u`, `.tran 20p {TSTOP} 0 20p`, `uic` added for
   ESD only. `spice.run` returns measures only from a run that reached its stop time (ngspice prints the `.meas` of
   a run it aborted, the peaks up to the stop, and a stalled run prints nothing); a run that does not converge:
   `toolchain.md`. Each row records the `note` of its run (options kept).
   **Initial state.** With `uic` nothing is solved before t = 0: a node not given starts at 0 V and an inductor at
   0 A, which is the unpowered board of the first calculation. A powered ESD case (refinement) would otherwise take
   the discharge from 0 V and clamp it low: first solve the same netlist with `VCH=0` and without `uic` (`op`, then
   `print all` in a `.control` block: node voltages and inductor currents `l…#branch`), and write that state into
   the ESD netlist: `.ic v(node)=…` for each node of the board (rails, the inner node of each capacitor's ESR, the
   bias capacitor of an array, line nodes) and `IC=…` on each inductor that carries current (a rail fed through an
   inductor carries its load). The generator's capacitors keep their own `IC={VCH}`, which takes precedence over
   `.ic`. Check, with these conditions but the generator left out (its capacitors at 0 V on a pin held high would
   draw a few mV from the rail and hide the test): each rail holds within 1 mV of its operating point up to
   `TSTOP`; a rail that moves lacks an initial condition. Fast transients run without `uic`: the `EXP` source is
   at 0 V at t = 0 and ngspice computes the operating point.
   **Stop time.** The discharge is over in about 200 ns, but the charge it leaves moves between the board's
   capacitances at their own resonances: an inductance L between two capacitances Ca and Cb (a supply filtered by an
   inductor or a ferrite, the bias network of an array, a ground-return configuration) resonates at f0 = 1 /
   (2π·√(L·Ca·Cb / (Ca + Cb))), and the far node peaks about half a period after the discharge (0.5 µH between 12 µF
   and 1.11 µF: f0 ≈ 223 kHz, maximum near 2.2 µs). `TSTOP` = the larger of 300 ns and 2 / f0 of the lowest such
   resonance of the netlist, or a few R·C of the slowest resistor sharing charge between two capacitances (1 kΩ
   between 1 µF parts: milliseconds), whichever is longer (count the run time at the 20 ps step). Near a limit,
   propose the verdict case with `TSTOP` doubled: its judged extremes and times beyond a limit move by less than 1 %,
   or it is doubled again.
3. Metrics = maximum of |x| over the run for each probe; for a rail, its maximum and its minimum against the two
   bounds of its limit (`tvs_fit.rail_ratios`: a dip under the lower bound fails like an overshoot); for ESD, the
   time spent beyond a limit, on |v| (`tvs_fit.time_beyond`): a 0.1 ns overshoot and a 200 ns one are not the same
   finding.
4. Verdict per case: `ratio[k] = metric[k] / limit[k]`; worst key = max ratio; fail if > 1, except on a screening
   limit (the injection test, the HBM rating): above it the case is to be measured (`verdict_threshold(…,
   screening=…)`), the stress located, not a fail. A limit with a duration ("up to 32 V, less than 1 ns beyond
   30 V") is two keys, the peak against 32 V and `time_beyond(t, v, 30)` against 1 ns, both in the verdict. At or
   below 1, the kind of each limit decides: a case whose deciding limits are screening estimates is a reservation,
   or a pass * when the designer accepts the estimate (`../SKILL.md`, "Criteria"), never a plain pass; a plain pass
   needs the pin's transient data or a test.
5. Sweep, when proposed: for a ground × choke bound × polarity, levels from 1 kV upward in 0.5 kV steps (to the
   margin level of the port); stop at the first level whose worst ratio on a withstand limit (a rating, a rail
   bound) exceeds 1 and record that level and **which limit**; withstood level = the previous step; the design's
   figure is the minimum over the series run, those not run named. The first level where a screening limit is
   exceeded is recorded apart, as the level from which that pin is to be measured: it neither stops the sweep nor
   sets the withstood level.

```spice
* excerpt — validated with ngspice
* Saturable common-mode choke between nodes a and b (both windings in parallel in common mode).
* L0: small-signal inductance; ISAT: saturation bound under study; LSAT: inductance after saturation.
.param L0=470u ISAT=50m LSAT=2u
* flux = integral of the winding voltage: 1 F charged by a current equal to V(a,b) -> V(phi) in V.s
Bint 0 phi I = V(a,b)
Cphi phi 0 1
Rphi phi 0 1e12
* current as a function of flux: slope 1/L0 at the origin, 1/LSAT once the flux exceeds about L0*ISAT
Bcm a b I = V(phi)/LSAT - (L0*ISAT)*(1/LSAT - 1/L0)*tanh(V(phi)/(L0*ISAT))
* losses in parallel; leakage inductance and winding resistance in series (b -> c -> d)
Rloss a b 1k
Lk b c 1u
Rk c d 0.07
* never-saturating bound: replace the four lines Bint..Bcm by   Lcm a b {L0}
```
The knee is soft and early: with these illustrative values a 1 V step gives 47.5 mA after 5 µs (a linear 470 µH
would give 10.6 mA) and 0.30 A after 10 µs; beyond, the slope is 0.5 A/µs (= 1 V / LSAT). The model is therefore
on the pessimistic side of a choke "rated ISAT"; say that ISAT is a bound (the datasheet's value or a swept one),
not the choke's measured saturation.

```spice
* excerpt — validated with ngspice
* Bidirectional TVS between `line` and `bgnd`, the board-ground node of the bench (earth is node 0; a node
* named gnd would be node 0 for ngspice and would tie the clamp to earth, so that the line then sits near 0 V
* instead of at the board-ground level plus the clamp). For a TVS returned to the chassis, put that node instead.
* Two anti-parallel branches, each = blocking diode + avalanche diode.
* Avalanche diode fitted on two published points near the current seen (here, as an illustration, 11 V at 10 A
* and 15 V at 30 A, maxima):
*   RS = (V2 - V1 - NBV*Vt*ln(I2/I1))/(I2 - I1)     BV = V1 - RS*I1 - NBV*Vt*ln(I1/IBV)     Vt = 25.85 mV
.model DBLOCK D(IS=1n N=1.5 BV=100)
.model DAVAL  D(IS=1n N=1.5 RS=0.1986 BV=8.78 IBV=1m NBV=1 CJO=100p)
Dpf line p DBLOCK
Dpz bgnd p DAVAL
Dnf bgnd q DBLOCK
Dnz line q DAVAL
* quick form for comparing candidates (V1 at 1 A, V2 at I2): RS = (V2 - V1)/(I2 - 1), BV = V1 - RS; it sits
* 0.2 V above the two points (illustration: 4.5 V at 1 A, 5.5 V at 5 A -> 4.68 V and 5.72 V): pessimistic, say so
*   .model DTV D(IS=1e-12 N=1 RS=0.25 BV=4.25 IBV=1m CJO=10p)
* n identical devices in parallel: write   Dpar a k DMODEL area=2   (a bare "2" after a model name that ends
* with a digit gives "could not find a valid modelname")
```
The two formulas of the comment are `tvs_fit.avalanche_fit` and `tvs_fit.quick_fit`; `tvs_fit.predicted_voltage`
gives the voltage of the model at any current, `tvs_fit.dc_check_netlist` the DC sweep that re-checks it.

## Validation of the board script
Build the script's chain once with the elements of the board, then check it by hand before trusting any verdict:
- the earth-lead current against `hand_check_earth_current`, with the clamp voltage read from the TVS model at
  that current (`tvs_fit.predicted_voltage`);
- each TVS model against its published points (DC sweep, `tvs_fit.dc_check_netlist`);
- the case "without the protection": the unprotected chain must show the bare-wave voltage on the capacitors, a
  case that is also the reference of every comparison;
- the generators alone.

## Reporting
Table variant × ground configuration → voltage of each capacitor, current of each TVS, line IC current, rails, each
cell against its limit; sweep: per series the level withstood, the first level that fails and the limit that
fails; bars per scenario with the limit; waveforms on a symmetric-log axis, on two panels. A deviation is
written with its cause and its remedy in numbers: "<cause> at <level> puts <voltage> on <part> rated <rating>;
<remedy, with position and return>: <voltages and currents>, holds <level>". Measurements to request:
pre-compliance surge and ESD shots, DC bias of the line pins when a snap-back part is considered, the choke's
common-mode saturation if the verdict depends on the bound.
