# Parallel memory bus: method in full

## Wiring, from the pins, whatever the names of the nets
A byte lane is its data bits, its mask and its strobe pair: the strobe captures its own bits, so the lane is the unit
of everything that follows, the matching included.

| Exchange | What it does | Usual rule (read the guide, for this memory type) |
|---|---|---|
| Strobe alone, or one bit, to the other lane | bits captured by a strobe that is not theirs | never |
| Whole lanes, strobe with its bits | the controller still sees coherent lanes | often allowed |
| Bits inside a lane | same strobe, same mask | often allowed; may be refused on the lane that carries mode-register reads or calibration feedback |
| Address, bank, command lines | the mode registers are written through these pins, so the value written changes | not allowed, unless the guide says otherwise |
| Strobe P and N | inverted capture | never |

Example of a rule that depends on the memory type: one SoC vendor's guide allows both exchanges on DDR3L and, on
LPDDR2/3, ties byte 0 to byte 0 with its bits in order. `byte_lane_wiring` only says whether each lane is whole; the
guide's rule is then judged on its mapping. Do not require lane 0 on the low byte unless the guide does: a legal
exchange would be reported as an error.

Lengths and delays are matched **inside a lane, against that lane's strobe**; two lanes are only tied through their
strobes' relation to the clock. A matching table built on net names before the wiring is checked means nothing if a
strobe is on the wrong lane.

## Margins
A line valid for a window W is captured by a clock or a strobe; the routing only moves the line and the clock relative
to each other. The window is one bit time for data, one clock period for a line that changes once per clock (more in a
mode that holds the command longer: read it in the controller's configuration).

| Quantity | Formula |
|---|---|
| Delay of a line | Σ section length × delay per mm of that layer and mode + Σ vias (height crossed × delay per mm) |
| Offset | arrival of clock or strobe − arrival of the line; for a pair, mean of its two conductors |
| Setup, hold | W / 2 + offset − t_su; W / 2 − offset − t_h |
| Share | \|offset\| / (W − t_su − t_h) |

Read t_su, t_h from the memory's table at the speed grade and input level in use, with their derating against the edge
rate if the margin is thin. Read data: window = t_QH − t_DQSQ or the memory's equivalent. The controller's launch and
capture uncertainties, when unpublished, are not estimated: the margin is given **before the controller**, and says
so. A controller with write leveling or per-byte delays removes a byte's mean offset; per-bit deskew also reduces the
spread inside the byte. What is corrected, and over what range, is read from the controller's documentation: a
statement about data lines says nothing of the address lines. Package delays, when the guide counts them and they are
available, enter the delay of each line; a share of the order of a percent does not justify chasing them.

Screen in this order: wiring, lengths in time, shares; go further only if a share is not small. Order of magnitude:
6 to 7 ps/mm on FR-4, against a bit time of about 940 ps at 1066 MT/s.
