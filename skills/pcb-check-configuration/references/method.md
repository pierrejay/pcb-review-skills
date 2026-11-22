# Configuration and interface wiring: method in full, board table, algorithm, validation, reporting

## Shared strap pin
Where a strap pin shares its net with something else (LED and its resistor, another device's input, a data line),
its DC level at reset comes from everything on the net: the external pull, the internal pull of every IC pin on the
net (the strapped pin's own and those of the other ICs, read pin by pin in their tables, e.g. "I, PD" during reset)
and the forward voltage of a LED. `strap_level` solves it by nodal analysis; an LED conducts in its own direction
only, so an LED whose anode sits on a rail that is off never pulls the pin. Each resistor is put at its tolerance
corner and each internal pull at its datasheet spread; the state is "low", "high" or "undetermined" (fails), written
in the report next to the row of the pin.

When the strapped pin becomes an output after reset, the external pull is also a load:
R ≥ (V_rail max − VOL) / IOL (and the same at VOH / IOH), with the current at which the datasheet guarantees VOL.
The two conditions give a window of values; the row says where the fitted value sits in it.

## Around the straps
- Distinct addresses on a shared management bus; each address goes to the device tree.
- Master / slave mode consistent with the clock source; repeater modes (a different data-valid signal on the
  interface) back to back; common reset if the manufacturer asks for it.
- A device whose clock comes from another IC has no clock of its own: its reset is released after that clock is
  stable. When that IC starts the clock only after its own reset, the device needs its reset released later still,
  or a software reset.
- A strap pin shared with a LED: load of the LED branch on the pull, and LED polarity that follows the strap
  (the default active level of the LED output can depend on the strap read).
- A pin that is an **output by default** and becomes an input through another strap (e.g. a reference-clock pin
  switched to input by the pull on a clock-control pin): check that this strap is fitted.
- MCU: boot pins (a pin sampled high at power-up can enter the bootloader) and debug pins reused as GPIO.
- The **manufacturer's reference architecture** (e.g. a datasheet figure showing how several devices share one
  clock): report any difference of architecture together with the worst-case specifications of both sides.

## Interface wiring
Read the application chapter of each datasheet and the reference schematic, then go through each interface pin by
pin. The notes that are requirements: those under a pinout or an internal schematic drawing (e.g. "connect the
shield pin to board ground"), the footnotes of the timing tables (e.g. "the clock shall be available at power ramp;
if not, apply an external reset once the clock is stable"), the sentences of the application chapter that say
"needs", "must", "shall" (e.g. "the analog supply after the I/O supply is fully ramped; if not feasible, an external
reset when both are ramped"). A PDF without text (drawing as an image) is read on the image, and its notes
transcribed in `refs/<part>.txt`. Each row: the note quoted, what the board does, met / deviation / not applicable
with the reason.
- **Ethernet 10/100, PHY to RJ45 with integrated magnetics**: centre taps to ground through a capacitor or to a
  supply according to the driver type (typically a current-mode driver is fed through them, while the centre taps
  of a voltage-mode driver are decoupled to ground and a supply there would fight the driver: the datasheet
  states which); a termination already integrated in the PHY or the magnetics not doubled by an external one; pair
  assignment; ESD array in flow-through on the PHY side; isolation rating of the magnetics; LED polarity against
  the internal pulls; **every pin of the connector that sits on a shell or shield net, one by one**: the shell
  lugs, and any pin that is not the shell (e.g. a jack pin that ends its common-mode termination, which the
  datasheet may ask on ground). A board that keeps such a pin elsewhere is a deviation; its effect is computed by
  `pcb-check-chassis-grounding` (how a surge divides between the termination capacitor and the shell tie).
- **USB**: series resistors as in the reference design, ESD array, Rd on CC1 and CC2 (device), incoming VBUS
  limited by a switch, outgoing VBUS through a switch. Whether the CC pins need an ESD part of their own is judged
  by `pcb-check-surge-esd` from the ESD rating of the receiving pins.
- **Isolated RS-485**: configuration pins not left floating when the datasheet advises against it; |VOD| against
  the RS-485 minimum at the bus-side supply actually used; fail-safe receiver (bias network needed or not);
  termination (on the board or at the terminal block, then stated in the manual); supply current while
  transmitting on a loaded bus, to carry into the rail budget.
- **Power mux**: priority mode, threshold divider with the tolerance of the internal reference (hence a switching
  window, not a value), switchover time and resulting dip, reverse-current blocking, hysteresis specified or not.
- **Core supply and reset of an SoC**: rails and sequence of the reference design, reset RC (numbers in
  `pcb-check-power-rails`).

## Supply, regulator-output and reference pins
Sources, in order: the application diagram of the datasheet, the table of recommended external components, the
schematic and BOM of the evaluation board. A capacitor that the diagram returns to a supply rail rather than to
ground (e.g. the output capacitor of an internal regulator, referred to the rail it regulates from) is easily drawn
to ground; only the far-end net of each part shows it.

**Recommended capacitance: marked or effective.** "2.2 µF ±20 %, ceramic" with a tolerance describes a part (case,
rated voltage, dielectric), not an effective value. What the manufacturer qualified is the part on its evaluation
board: read its BOM. A board part that resembles it (same dielectric, rated voltage and case) is compared at
nominal: the reference design shows that the circuit works with that part (`pcb-verification/references/
failure-modes.md`, decoupling and bulk). A part that does not resemble it, or a datasheet that asks for an
effective value: take the DC-bias curve of that part and of the board's part, and compare the effective values at
the pin's voltage. Against the class-2 0402 rated 6.3 V of `pcb-verification/references/failure-modes.md` § 2, an
0603 rated 10 V or more keeps noticeably more at 3.3 V (read the curves of the exact parts).

## Decoupling of the supply pins
The reference network is a known-good starting point and is computed like any other; the IC's sensitivity to its
supply (current spectrum, rejection) is usually not published. What can be computed is what the network does;
what cannot is whether the IC needs it, which is measured (ripple at the pin, error rate of the link) when the
verdict depends on it. Without a requirement, a board that works on the bench with its manufacturer's network
(e.g. one small capacitor per pin) is a fair reason for the designer to keep it: the computed improvement is a
recommendation.

**Requirement.** When the load's supply range and its current step are known (published, or estimated with both
bounds), a target impedance follows: allowed transient deviation / current step, the deviation allowed being what
the range leaves once the set-point corners and the ripple of `pcb-check-power-rails` are taken. A network that
lets the rail leave the range is then a deviation.

**Model** (ngspice, linear, one script per board): regulator as a source with its load regulation in series and an
inductance for its loop (estimate); the rail's bulk capacitors; a few nH of track to the pin; the ferrite as its
manufacturer's SPICE model (Murata publishes netlists per series; low-frequency inductance and DC resistance read in
it); each capacitor at its capacitance under the rail voltage (DC-bias curve of the exact part, `mlcc_bias`), ESL
of the case + about 0.5 nH of mounting, ESR. One row per pin, on the fitted network; a variant (without the
ferrite, its maximum DC resistance, another capacitor) when the designer asks or the row shows a problem:
- impedance seen from the pin per band: < 1 MHz (current steps), 1–10 MHz, 10–100 MHz (clocks, edges), > 100 MHz
  (dominated by the mounting inductance);
- transmission of the rail's noise to the pin, |V(pin) / V(rail)|: maximum gain (above 0 dB: a resonance that
  amplifies) and attenuation at the frequencies present on the rail (oscillators, data clocks);
- dip of the pin for a current step (the IC's change of mode; estimate when unpublished).
Every netlist starts with a title line: ngspice takes the first line as the title, and a source written there
silently disappears.

**Reading the results.** The numbers depend on the rail's bulk and its distance, the ferrite's impedance curve, the
effective capacitances and the mounting of each part: they are computed for the board, never taken from another one.
Mechanisms they usually show, to be checked on the board rather than applied:
1. Without a ferrite, a capacitor alone at the pin and the inductance of the path to the bulk form a parallel
   resonance, typically an impedance bump in the 1–10 MHz band for a small capacitor at the end of a long path
   (common 0402 parts, a few to tens of nH of path); a second capacitor of larger value at the pin, or the same case
   in a larger value, lowers it and moves it down; the rail's bulk holds the low frequencies. Adding a small
   capacitor where there is none can cure the high band and create such a bump lower down: compute before
   recommending.
2. With a ferrite, the capacitance after it and the ferrite's inductance resonate, usually below a few MHz; unless
   that resonance is damped (ESR and ferrite resistance against √(L/C)), a small capacitance there amplifies the
   rail's noise near that frequency instead of filtering it, and a larger effective capacitance moves the resonance
   down and lowers its peak. Whether a ferrite is worth its residual gain depends on the noise the rail carries at
   high frequency (e.g. a rail shared with digital ICs) against what the IC tolerates, which is rarely published:
   when the row shows gain, compare the transfer with and without it.
3. Above a capacitor's self-resonance its impedance is set by its mounting inductance, roughly independent of its
   value for a given case and mounting: there a second part in parallel helps more than another value, and the
   staggered values of a reference network act mainly as extra parts, adding little unless their mounting differs.

## Building the tool
Script, outputs and refusals: `../SKILL.md`, "Tool contract".

**Board table** at the top of the script:
- `RAILS`: the set of net names that count as a pull destination (ground and every supply a pull can go to).
- `EXPECTED`: `{(reference, pin number, role): [(ohms, rail), ...]}`, a **list** and not a set (a set would merge
  two equal resistors into one entry, accepting half the resistance or failing a correct board), the role being the
  text of the report row (e.g. "PHY strap 3 = 1"); two entries when two equal resistors are expected in parallel;
  the empty list for a pin left to its internal pull; `[(0, "GND")]` for a pin tied directly to a rail. One comment
  per device giving the datasheet, revision and table the entries come from.
- `SERIES_MAX = 100` (Ω): largest series resistor crossed when looking for a pull. Series resistors on fast signal
  lines are typically tens of ohms and the pull may sit on either side: a search limited to the pin's own net
  reports "no pull".
- `VARIANT`: the assembly variant read, when the board has variants (`''` for the default).
- `SHARED`: per shared strap pin, the branches for `strap_level` with their source (LED colour, forward drop and
  direction read on the schematic, the internal pull of every IC pin on the net and its spread, datasheet section)
  and the thresholds VIL / VIH; for a pin that is an output after reset, VOL / VOH with the current at which they
  are guaranteed, and the window of pull values that the two conditions leave.

**Algorithm**
1. Load the board; index pads by `(reference, pad number)`.
2. Index two-pad footprints whose reference starts with `R` by net: `net → [(resistor, net of the other pad)]`.
3. For each expected pin: fail if the pad does not exist; take its net; add, step by step, the nets reached through
   a resistor whose other net is not a rail and whose value is ≤ `SERIES_MAX` (a chain of 0 Ω included); collect on
   these nets the resistors whose other pad is on a rail (a series resistor to another signal is not a pull);
   convert each Value to ohms, DNP and value as assembled in `VARIANT`. A pin whose net is a rail is a direct tie,
   `(0, rail)`: an expectation `[]` (internal pull only) then fails, as it must. Steps 1 to 3 are
   `read_pulls(board, pins, rails, series_max, variant)`.
4. `ok = (sorted pulls found == sorted pulls expected)`; one row per pin and the number of deviations; print one
   line per pin.
5. For each shared pin: `strap_level`, its level and state in the JSON next to the row.

## Validation cases
- Negative test of the board table: change one expected value and check that the run reports exactly one
  deviation.

## Reporting
- Table: pin / strap or function / wiring found / decoded result / expected. Then one line per interface:
  compliant with the datasheet (section quoted), or the difference and its consequence.
- A strap deviation: the resistor and the level that results, the mode selected instead of the intended one, the
  correction (reference, value, rail).
- Decoupling: one "Recommendations" table (where, now, remedy, computed gain); a reference network found to
  resonate is reported the same way, a manufacturer's own recommendation included.
- Software consequences go to the open points: address to declare in the device tree, register to write, clock
  tree configuration to read back.
- Measurements to request at bring-up: level of the shared strap pins at the release of reset, LED polarity once
  the link is up, registers that reflect the straps read back.
