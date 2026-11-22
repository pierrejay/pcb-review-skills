---
name: pcb-check-conducted-emissions
description: "Pre-estimate of the conducted emissions (150 kHz - 30 MHz) of a buck (step-down) converter on a PCB power input, through the real input network into a LISN, against indicative CISPR 32 class A/B limits (CISPR 11 or IEC 61000-6-3 / -4 may apply instead); sizing and damping of an input LC filter, before an EMC pre-scan."
---

# Check: conducted emissions of a converter (pre-estimate)

Read `../pcb-verification/SKILL.md` first.

## Resources
In `../pcb-verification/lib/`:
- `conducted_emi.py`: source waveform, nodal network with its LISN, limits, spread-spectrum estimate;
- `mlcc_bias.py`: `fit_bias`, `effective_capacitance`, `typical_fraction`, the input capacitors under DC bias;
- `power_input_models.py`: `damper`, the starting point of a filter damper.

## Purpose
How far is the switching noise of the input converter from the limit, read at the measuring network (LISN) on the
power port? The check gives a margin per spectral line before a pre-scan is paid for, and puts numbers on an input
filter proposal: attenuation, and damping seen by the converter. It is a linear, frequency-domain estimate; the
pre-scan decides.

## When it applies
- A **buck (step-down) converter** fed from a power port that leaves the board on a cable: the source model is the
  input current of a buck (`input_current`).
- **First question: does the targeted standard put a limit on this port?** Whether and how a DC power port is
  limited depends on the standard and on its edition; when none applies, the limits are a reference for margin
  (Criteria).

## Inputs to obtain
- **Converter datasheet**: switching frequency, spread spectrum (± %), forced PWM or PFM at light load and the PFM
  peak inductor current, efficiency; edge duration (rarely published: an estimate); the PWM duty cycle per load
  case when measured or given by a loss model (otherwise estimated from the efficiency).
- **Schematic and PCB**: the input chain in its real order (connector, TVS, series diode, capacitors, filter
  inductor, converter), values from the PCB; the converter's inductor; routed length connector → input capacitor,
  converted to an inductance from the stackup and the routed geometry (`references/method.md`, Inputs).
- **Component datasheets**: DC-bias curve and ESR of each input capacitor; DCR and self-resonance of the filter
  inductor; diode ideality factor and series resistance; TVS capacitances.
- **Power budget** (`pcb-check-power-rails`, `pcb-check-thermal`): output current in the cases typical, measured,
  envelope, lowest input voltage; a light-load case if the converter has a PFM mode.
- **Designer** (the scope of use sets the reference): targeted standard and class (A industrial, B residential),
  type of supply (dedicated or DC distribution network) and cable length, input voltage range, load cases,
  enclosure and earthing (board ground tied to an earthed metal enclosure, or floating in a plastic one).

## Method
1. **Source** (`input_current`): input current of the buck over one period, in the form of the converter's mode in
   each load case, PWM or PFM, each inside its domain; a converter in forced PWM is declared as such in the board
   table. PWM duty cycle: the declared one (`duty`) when known, else `Vout / (η·Vin)`, an estimate. Edges smoothed
   over the edge duration.
2. **Input network as fitted** (`fitted`, `network`): every branch of the input chain in its real order, with the
   board's values; the LISN (50 µH / 50 Ω) on each wire.
3. **Transfer** (`transfer`): 1 A drawn at the converter input; the level kept is that of the higher receiver,
   board ground bonded to an earthed enclosure (usually the higher); floating is added when the margin is small.
4. **Level** of each line in 0.15–30 MHz (`lines`, `level_dbuv`).
5. **Detectors**: without spread spectrum, the level of each line is compared with both the quasi-peak and the
   average limits (`limits`): an upper bound.
6. **Spread spectrum apart** (`spread_gain_db`, estimate): margin with and without; never in the verdict.
7. **Filter variants** (inductor, capacitor upstream, doubled capacitor, damper, resistance in series in the supply
   path, bead in series, capacitor to chassis): same computation, first on the load case expected to be the worst
   (for an LC section, the one whose lines fall nearest its resonance, often PFM at light load); the others when the
   margin is near the limit, the cases not run listed. A case that `lines` refuses (lines closer than twice the 9 kHz bandwidth) is not
   established for that variant and is listed with it. The attenuation is that of an ideal lumped model, which
   placement caps for a single stage. A variant proposed to the designer is complete as `references/method.md`,
   "Reporting", lists.
8. **Damping** (Middlebrook, `damping`): maximum impedance seen by the converter against the criterion, at the
   lowest input voltage and highest power, floating (usually the higher peak; bonded when the margin is small),
   over a sweep that starts a decade under the lowest resonance of the network, the LISN's included. Two ways to
   damp: a series R–C damper across the converter capacitor (`damper`; its capacitor must reach n × C in EFFECTIVE
   value, often more than a class-2 part of the same size holds), or a resistance in series in the supply path
   (`r_series`, starting point `series_damper` on the source inductance and the effective C; no series R reaches a
   limit under √2·Z0), one part, judged on its losses, its drop and its single-pulse curve
   (`pcb-check-power-input`). It damps the source with the capacitors, not a filter inductor's own resonance with
   its capacitors (`references/examples.md`).
9. **Hand check** of the fundamental (`fundamental_hand`), then the JSON.

## Criteria
| Criterion | Value (indicative) | Source |
|---|---|---|
| Limit on a DC power port | none, or the one of the applicable text: depends on the standard and edition | to confirm in the text that applies to the product; if none, the rows below are a reference for margin only |
| Reference for margin, class A | 0.15–0.5 MHz: QP 79, AV 66 dBµV; 0.5–30 MHz: QP 73, AV 60 dBµV | mains-port limits commonly used for CISPR 32 / EN 55032 class A (similar figures appear in the conducted limits of 47 CFR part 15); held by `limits`, status carried by `LIMITS_SOURCE` |
| Reference for margin, class B | 0.15–0.5 MHz: QP 66 → 56, AV 56 → 46 dBµV, linear in log f; 0.5–5 MHz: 56 / 46; 5–30 MHz: 60 / 50 | same |
| Damping | maximum filter output impedance ≤ `|Zin| / 3` | Middlebrook's criterion (output impedance well under the converter's input impedance); the factor 3 is the margin chosen here, not a figure of the criterion's authors, to settle with the designer |

Texts that may apply (the reader confirms which, for the product and market aimed at): CISPR 32 / EN 55032
(multimedia equipment), CISPR 11 / EN 55011 (industrial, scientific and medical equipment), the generic emission
standards IEC 61000-6-3 (residential) and IEC 61000-6-4 (industrial), CISPR 16-1-2 (artificial networks: the LISN)
and CISPR 16-1-1 (receiver, detectors, 9 kHz bandwidth). The limit values above are the ones commonly used in
design, **indicative**. The LISN modelled is the 50 µH / 50 Ω network, fixed: a standard that calls for another
artificial network needs another model.

When no limit applies to the port, the margin is still computed and the verdict names its reference, or a
non-requirement is reported as a failure: "x dB under class A in average, against our reference (no normative limit
on this port), to be confirmed at the pre-scan". A filter variant is **quantified, not decided**: the designer
chooses.

## Self-checks
- An input voltage without a declared effective capacitance fails (no default value: `c_eff_at`).
- Part numbers and values of the inductors and capacitors are compared with the PCB export of the power-input
  check: after a component change the script fails instead of keeping the old model.

## Tool contract
One board script, `conducted_emissions.py` (not `conducted_emi.py`, the module it imports), computation venv (numpy);
reads no board file, writes `results/conducted_emissions.json` in seconds. The radiated check
reuses `input_current` and `network(…, z_wire=)` up to 1 GHz, with another termination in place of the LISN.
- **JSON**: tagged assumptions; per case the repetition frequency, every line with level and margins (QP, AV,
  A, B), spread gains apart, the limiting line; per variant the minimum margins with and without spreading and the
  case that sets them, the cases not established, `z_out_max` with its frequency and ground set-up, `zin / 3`,
  `damped`, the envelope-case lines, the cases not run; `limits_source`.
- **Refusals of the board script**: a part number or value that no longer matches the PCB export.

## Pitfalls
- **Put the capacitor upstream of the inductor in the proposal.** Without it the inductor is in series with the
  50 Ω of the LISN and attenuates nothing.
- **Use the effective capacitance of the BOM part under each input voltage.** Where the capacitor's reactance sets
  the impedance (above its self-resonance, ESL and ESR set it instead), dividing the capacitance by 2 to 3, as DC
  bias commonly does near half the rated voltage (`references/method.md`, Inputs), raises the line by 6 to 9.5 dB
  (20·log10 of the ratio).
- **Plot spectral lines or their envelope.** Sampled point by point, a sinc-shaped spectrum falls into the nulls
  and suggests margin that does not exist.

## Limits
Differential-mode noise of one converter through a lumped network: no common-mode path from the switching node to
the chassis, no coupling between the input and the output of the filter, no near-field coupling to the connector;
above about 10 MHz the result is an order of magnitude. Several converters on the same input are not summed. The
inductor's saturation and the capacitors' tolerance are not swept.
