# Power rails: formulas of each step, board tables and algorithm, netlist excerpt, validation values, reporting

## Method, step by step
The steps and their decisions are those of `../SKILL.md`, "Method", under the same numbers; steps 1, 10 and 11
have no formula and are entirely there.

### 2. Set-points
`set_point(vref, tol, rtop, rbot, rtol)`: Vout = VREF × (1 + Rtop / Rbot); minimum at VREF × (1 − tol), Rtop × 0.99,
Rbot × 1.01 for 1 % resistors; maximum at the opposite corner (ripple and transients excluded). The margin is that
of the regulator's output, before the copper drop (`pcb-check-pdn-ir-drop`).

### 3. Ripple and inductor
`ripple(vout, vin_max, l, f_min, c_eff, iout, l_tol, esr)` at the pessimistic corner (maximum input voltage, L −
tolerance, minimum switching frequency): ΔI = Vout × (Vin − Vout) / (Vin × L × f); peak current = load + ΔI / 2; ΔV =
peak-to-peak of q / C_eff + ESR × i over one cycle of the triangular current, between the larger and the sum of ΔI / (8
× f × C_eff) and ΔI × ESR. `esr` is the ESR at the switching frequency, read on the part's curve (§ 4), required: near a
limit the ESR term can exceed the capacitive one. This form is for a bank of identical parts (C_eff and ESR of the bank:
n × C, ESR / n). A bank whose parts differ (bulk and small ceramics) goes through `ripple_bank(vout, vin_max, l, f_min,
bank, iout, l_tol)` with each part's (C_eff, ESR): the parallel of the ESRs alone understates the ripple (33 µF and 0.1
µF at 10 mΩ each: 6.0 mV reduced, 10.8 mV in fact). The load used is the rail's budgeted maximum current; when it is not
known, 1 A per rail as an upper-envelope estimate, marked as an estimate in the report.

### 4. Effective capacitance under DC bias
Class-2 ceramic capacitors lose capacitance under DC bias, the more so in a small case at a low rated voltage (e.g.
a 10 µF 0402 rated 10 V can fall to about a fifth of its marked value under 5 V on one manufacturer's curve). EIA
case codes are kept as part designations: 0402 = 1.0 × 0.5 mm, 0603 = 1.6 × 0.8 mm, 0805 = 2.0 × 1.25 mm. Build the
DC-bias data as follows.
1. Take the exact part number of each capacitor from the BOM.
2. In the manufacturer's online component library (the major MLCC makers publish one), open the DC-bias
   characteristic of that part number (capacitance versus DC voltage at 25 °C) and its impedance / ESR curve against
   frequency. Read the points from the data the page draws rather than off the picture when the page exposes them.
   Traps when reading such a curve: it may give **ΔC in % of the value at 0 V**, not µF (store
   `nominal × (1 + ΔC/100)` and say so in the JSON); the **measurement conditions change from one part to the next**
   (frequency, Vrms: printed with the curve, store them per part); a point can be out of order (sort by voltage).
   The library also shows the lifecycle status of the part: "NRND" (not recommended for new design) is a sourcing
   finding to report.
3. Read 10 to 20 points (V, C in µF) from 0 V up to at least the highest voltage the part sees in the simulation,
   closer together where the curve bends. Read the ESR near the frequency of the phenomenon (about 1.5 MHz for
   events of a few microseconds) and at the switching frequency of the converter that feeds the rail (ripple, § 3).
4. Store them in a JSON kept with the board (`verification/models/mlcc_dcbias.json`): source, measurement
   conditions, date of reading, and per part number `{"desc", "esr", "v": [...], "c": [...]}`.
5. Fit each curve with `mlcc_bias.fit_bias(v, c, v_lo, v_hi)`: the smooth law **C(V) = C0 / (1 + (V / a)^b)**, three
   parameters. The fit records the largest relative deviation between fit and points over the working range of the
   rail (`max_dev`) and refuses one above 10 %: that curve is read as a table of its points (`mlcc_bias.table_bias`),
   accepted by the same functions.
6. Use: effective capacitance of a rail = `effective_capacitance(parts, v)`, the sum of the curves read at the
   rail voltage, a constant in the netlists (`pcb-verification`, failure modes, for a transient). A DC-bias curve
   gives the differential capacitance: the charge time of a constant current is ∫C dV / I, not
   C(V_final) × V_final / I (`charge_time`).
No curve published for the exact part number: the curve of an equivalent part, from a manufacturer that publishes
them, with the same dielectric, rated voltage and value, same case or the nearest, listed as an estimate
(`pcb-verification`, failure modes). Before any curve is read, `typical_fraction(case, rating, bias)` reads the
typical X5R table (`X5R_TYPICAL_FRACTION`, remaining fraction against bias per case and rated voltage), for screening
only (`../SKILL.md`, "Pitfalls").

### 5. Sequence by RC
1. Each enable pin sees either the input rail directly or an RC from it. `enable_instant(vth, r, c, vin, t_ramp)`
   models the input rail as a linear ramp of duration t_ramp followed by a plateau (two cases: a fast ramp of the
   order of 0.1 ms for a plug-in, the soft-start time of the upstream converter otherwise), integrates
   dVen/dt = (Vin(t) − Ven) / RC and takes the instant Ven crosses the enable threshold; with no RC,
   t = Vth / Vin × t_ramp.
2. A rail starts at the later of that instant and the instant its input crosses the regulator's rising UVLO, and is
   settled at the later of one soft-start time after its start and the instant its input reaches `vin_reg`, the
   lowest input at which the regulator holds its output at its set-point: set-point maximum + maximum dropout at the
   load current for a linear regulator, (set-point maximum + I × (RDS(on) + DCR)) / the guaranteed minimum of the
   maximum duty cycle for a buck. Below it the output follows the input: the UVLO only says the regulator runs. On a
   slow ramp the enables can cross before the UVLO: the rails then start together at the UVLO crossing, whatever
   their RC.
3. `sequence_corners(rails, orders, vin, t_ramp, tracking)` enumerates the tolerance corners: enable threshold
   min / max, rising UVLO min / max, soft-start min / max **and the time constant of each enable network, min /
   max** (resistor tolerance × capacitor tolerance; for a class-2 capacitor the caller adds its drift with
   temperature and ageing to `c_tol`, an estimate that is listed), **each regulator and each network
   independently** (every combination). Every rail carries its threshold, UVLO and soft-start pairs and its
   `vin_reg`, and every network its R, C and both tolerances: a missing one is refused, not taken as zero. The start
   grows with the threshold, the UVLO and the time constant, so the extremes are enough. Channels of one IC may be
   taken as moving together only for the threshold, the UVLO and the soft-start, and only if the datasheet
   guarantees channel-to-channel tracking (`tracking={ic: "clause"}`); the R and C of two networks are separate
   parts, so they do not track. Without that guarantee the correlated result is an estimate (`correlated`), given
   next to the independent one, and the verdict is on the independent corners. Neither effect is negligible:
   compute both.
4. For each required order "A settled before B starts", margin = start(B) − end(A), worst over the corners. A
   negative margin means the order is not guaranteed.

### 6. Chained power goods
The open-drain power good of the upstream converter holds the enable of the next one low; pull-up to the input
rail, no capacitor. The order then holds by construction, whatever the tolerances, and the check is on levels
instead of times. `power_good_chain_conditions` returns every condition as a line (label, value, limit,
direction), judged one by one by `judge_conditions`:
- *enable held low*: the power-good low level the datasheet guarantees, at its test current, ≤ the threshold under
  which the converter is guaranteed off. When both are the same value the condition holds at equality, zero margin
  at the guaranteed limits (`at_equality` says so, with the level at the real pull-up current next to it). The
  pull-up current (V / R, an upper bound: the transistor may pull lower than its guaranteed level, so (V − VOL) / R
  would understate it) must stay **at or under that test current**, or the held-low level is not established. At
  a pull-up current under the test current the level is proportionally lower, which is an estimate and is listed;
- *sink*: the pull-up current at the highest rail ≤ the sink current the power good accepts. The sink rating and
  the guaranteed level are two conditions, both judged: a pull-up can stay within the sink rating and still exceed
  the current at which the low level is guaranteed;
- *enable released*, **computed with a declared leakage** (power-good leakage of every output on the node + enable
  input current; when the datasheet gives a typical only, an estimate that is listed) **at the lowest input at
  which a converter runs** (the lockout): lockout − leakage × pull-up ≥ the threshold above which the converter is
  guaranteed on; give the leakage the network tolerates, (V − Von) / R;
- *pins*: the highest pull-up rail ≤ what the power-good and enable pins accept (absolute maximum);
- *input rail rising*: a power-good output is only valid above a stated input voltage, which must be ≤ the lowest
  under-voltage lockout (typical, maximum falling, plus hysteresis): below the lockout no converter starts, so a
  floating power good does no harm, provided all the converters share the input net (read from the board);
- several power goods tied to one enable form an AND: the next rail waits for all of them;
- *timing*: each stage adds one soft-start time. The power-good threshold (a percentage of the nominal output,
  rising and falling) is often published as typical only: say so.

The chain is **read from the board**: for each converter, its rail (through the feedback divider), the nets of its
enable and power-good pins, the pull-up of the enable; the rails a converter waits for are those whose power good
is on its enable net (`chain_matches` compares it with the order required).

**The release threshold is compared with what the load asks, and the requirement is declared.** "The downstream
rail starts after the release" and "the upstream rail is inside its load's range before the downstream one starts"
are two requirements. A power good released at a percentage of the rail close to the lower edge of the load's range
sits on the edge of the range, and under it at the estimated lower bound of the power-good threshold. If the
reference only gives an order, the first is judged and the levels at release are reported next to the range; if the
designer declares the second, it enters the verdict.

Reported at the corners (lockout, soft-start, power-good threshold, independent per converter): level of the
upstream rail when the downstream one starts (power-good threshold taken at the lower bound of its estimated range
when only a typical is published), level of the downstream rail when the upstream one reaches 100 %. The time margin
"upstream at 100 % → downstream starts" is negative by construction when the power good releases below 100 % of the
rail.

What it changes for the designer, to state: there is no order at power-down (the converters stop together when the
input falls, and without output discharge each rail falls at the pace of its load), and an upstream rail falling
under its power-good threshold shuts the downstream rails in cascade.

### 7. Rail transients (ngspice)
Model each element by what it does at the microsecond scale:
- capacitors at their effective value at the rail voltage, with ESR (ESL neglected);
- a group of converters as a **constant-power load** I = P / V, with a step from the typical to the envelope
  power in about 1 µs (pessimistic: their regulation typically spreads it over some ten µs);
- a host port as its nominal voltage (and its lower bound) behind its source resistance, with the capacitance at
  the port and the cable's resistance and loop inductance. Typical constants for a USB host port: 5.0 V or 4.75 V
  behind about 50 mΩ, about 120 µF at the port, a cable of about 0.2 Ω and 0.7 µH; replace them with the host and
  cable of the product;
- a current-limited input switch as its on-resistance with a soft limit (reaction delay ignored);
- an upstream converter as a source behind its estimated closed-loop output impedance (e.g. 10 mΩ + 0.5 µH for a
  loop crossover near 50 kHz: estimate), with its soft-start ramp;
- a power mux as two one-way channels (on-resistance, no reverse current), each driven by an enable; at the
  switchover the first channel opens when the priority input crosses the threshold and the second closes after
  the switchover time, with **no channel conducting in between**;
- a load switch that limits only after its reaction time as a switch whose limit engages once the **charge passed
  above its threshold** reaches a trip value fitted on the datasheet curve of reaction time against overcurrent:
  trip charge ≈ (I − I_threshold) × t_reaction. For one such switch's datasheet (40 µs at 2.5 A, 20 µs at 4 A,
  10 µs at 6 A, 5 µs at 10 A, threshold 1 A) this gives 45 to 60 µC; use the points of the switch on the board;
- a hot-plugged device as a discharged capacitor closed onto the port, at the largest capacitance the interface
  allows (of the order of 10 µF for USB, indicative).
Cases, the one expected to be the worst first: loss of the priority source at the lowest mux threshold and the
fastest fall; hot-plug of the largest device on the weakest source; load step at the envelope power. The other
thresholds, fall times, sources, device values and the return of the priority source are added when a result is
near its limit or the designer asks; those not run are written with their reason.

### 8. Capacitance corner
A case runs first with the effective capacitances at nominal (`ktol` = 1); when its margin is small, again with every
capacitor of the model at its low corner at once (`ktol` = 1 − tol, 0.8 for ± 20 % parts; the hot-plugged device
capacitor stays at its declared value, it is the aggressor), ESR nominal. The nominal row is reported next to the
low-corner one, so that the share of the margin owed to the tolerance shows.

### 9. Downstream rail during a dip: two independent bounds
`downstream_bounds(...)`: (a) the downstream regulator runs at 100 % duty cycle (if its datasheet allows it):
V ≥ Vin_min − I × (RDS(on) + DCR), capped at its regulated minimum; (b) the regulator supplies nothing while its
input is under the limit and the output capacitors hold alone: ΔV = I × t / (C_eff × ktol) from the regulated
minimum. Take the lower of the two, with in-house margins on the current (`i_factor`, e.g. × 1.5 on an envelope
current) and on RDS(on) when only a typical value is published (`rds_factor`, e.g. + 50 %). Both bounds use the
same corner as the upstream scenario they read: Vin_min and t from its row, C_eff of the downstream rail times the
same `ktol`.

## Board tables and algorithm
Scripts, outputs and refusals: `../SKILL.md`, "Tool contract".

**1. Set-points, ripple, sequence.** The export step in KiCad's Python writes the Value of the listed references and the
capacitors of each rail net. Board table: `RANGES` (rail → min, max, domains intersected, datasheet table in a comment);
per regulator or variant: VREF and tolerance, frequency (min, max), current limit, inductance and Isat, enable threshold
(min, max), rising UVLO (min, max), soft-start (min, max), `vin_reg` with the dropout or the maximum duty cycle it comes
from, `tracking` ({IC: the datasheet clause that guarantees channel-to-channel tracking, quoted}, only when such a
clause exists), and per rail the references of Rtop, Rbot and of the enable RC with the tolerance of each (resistor;
capacitor, drift included); `COUT` (rail → capacitors with value, case, rating, part number); the assumptions (load per
rail, maximum input voltage, ramp times). For a chained sequence, the chain, the dividers and the pull-ups read from the
board (§ 6) are compared with the table, and the capacitance read on each chained enable is passed to `chain_matches`.

**2. Rail transients.** Board table: sources, switches and mux with their datasheet constants (source in a
comment), capacitors of each node as `(part number, count)`, limits read on the rail, list of scenarios (name,
label, sources present, enable waveforms, step or plug event, stop time), list of bulk variants to compare.
Algorithm:
1. Load the DC-bias JSON, fit each part (`fit_bias`), store the fit error, sum each node at its voltage.
2. For each scenario write the netlist from the excerpt below. `.nodeset` only helps convergence: the operating
   point charges a "discharged" device capacitor through the switch's Roff, however large. Its initial state is
   imposed with `.ic v(dv)=0 v(dvx)=0` (without `uic`: the rest of the operating point is still computed).
3. Run it with `spice.run`, kind "slow" (its timeout, a few minutes), `measures` naming the `.meas` of the minimum of
   each rail after the event (`MIN v(rail) FROM={t0}`).
4. Read the waveforms (`wrdata` writes a time column before every vector: vector k is column 2k + 1), ignore the
   settling before the event (t > t0), compute minima and the time under each limit as the sum of the time steps
   where the voltage is below it. For a hot-plug, the device capacitor passes its check when `v(dv, dvx)` is below
   1 % of the rail just before the event and the charge it receives (C × final voltage) is above zero. A discharged
   capacitor equal to the rail capacitance shares its charge: a rail at 5 V falls to about half, so a rail still at
   5 V after the plug is the signature of a `.nodeset` that left the device capacitor charged.
5. Write the JSON.

```spice
* excerpt of the netlist template; {...} are filled in by the script from the board table and the datasheets,
* times in µs; in1 = priority source, in2 = second source, sys = the rail, port = the downstream port
* capacitors of node x: effective value at the rail voltage (c_eff in µF, times the corner ktol), ESR in series
Rc1 x x_c1 {esr}
Cc1 x_c1 0 {c_eff*ktol}u
* power mux: each channel conducts one way only (softplus over 4 mV keeps the solver stable), gated by v(en)
Ven1 e1 0 PWL(0 1 {t_cross}u 1 {t_cross+0.01}u 0)
Ven2 e2 0 PWL(0 0 {t_cross+t_switch}u 0 {t_cross+t_switch+0.01}u 1)
B1 in1 sys I = v(e1)*(max(v(in1,sys),0)+0.004*ln(1+exp(-abs(v(in1,sys))/0.004)))/{r_mux}
B2 in2 sys I = v(e2)*(max(v(in2,sys),0)+0.004*ln(1+exp(-abs(v(in2,sys))/0.004)))/{r_mux}
* converters as a constant-power load; the floor on v(sys) (the converters' UVLO) avoids a runaway current below it
Vpw pw 0 PWL(0 {p_typ} {t_step}u {p_typ} {t_step+1}u {p_env})
Bload sys 0 I = v(pw)/max(v(sys),{v_floor})
* input switch with a soft current limit (on-resistance {r_in}, limit {i_lim})
Bin vbus in2 I = {i_lim}*tanh(max(v(vbus,in2),0)/({r_in}*{i_lim}))
* load switch that limits at {i_sw_lim} only after {q_trip} µC have passed above {i_th} (v(q) is that charge in µC)
Vsw sys sw 0
Bsw sw port I = (1-v(fl))*max(v(sw,port),0)/{r_sw} + v(fl)*min(max(v(sw,port),0)/{r_sw}, {i_sw_lim})
Bq 0 q I = max(i(Vsw)-{i_th}, 0)*1e6
Cq q 0 1
Rq q 0 1e12
Bfl fl 0 V = 0.5*(1+tanh((v(q)-{q_trip})/2))
* every node behind a behavioural source needs a DC path, or the operating point is singular
Rl1 in1 0 1Meg
Rl2 in2 0 1Meg
Rls sys 0 1Meg
Rlp port 0 1Meg
* hot-plugged device: discharged capacitor closed onto the port at {t_plug}
Vpl pl 0 PWL(0 0 {t_plug}u 0 {t_plug+0.01}u 1)
Spl port dv pl 0 SWP
Cdev dv dvx {c_dev}u
Rdev dvx 0 {esr_dev}
.ic v(dv)=0 v(dvx)=0
.model SWP SW(Ron={r_plug} Roff=1e9 Vt=0.5 Vh=0.1)
.options method=gear reltol=1e-4 abstol=1n vntol=10u itl4=200
* other attempt: that of spice.run, kind "slow" (lib/spice.py)
.tran 20n {t_stop}u 0 0.2u
```

**3. Downstream bound.** Reads the two JSON above (regulated minimum, minimum and time under the limit per
scenario), applies `downstream_bounds` (§ 9) on the rows that carry the verdict, and skips by an explicit rule the
scenarios the scope excludes.

## Reporting
- Tables: rail / range of the load / nominal [min; max] / smallest margin; rail / ΔI / peak against Isat and
  limit / nominal and effective capacitance / ripple; sequence margins per ramp case with the bar chart; scenario /
  minimum of the rail / time under the limit / port minimum / switch peak.
- A variant table that answers "where does extra bulk help?" with numbers, one row per placement.
- A deviation gives the cause (which tolerance term or which capacitor), what is concerned (which domain, which
  case of use), the precise correction (reference, value, resulting nominal and range, or capacitor and node) and
  the gain in mV or µs.
- Estimates listed: converter and cable impedances, constant-power load, trip charge, typical capacitor table
  when used. Measurements to request: load-step response of each converter, start-up oscillogram of all rails,
  rail during a switchover.
