# Parallel memory bus: application cases

- **A matching rule missed, margins of a few percent.** Setting: DDR3L at 1066 MT/s, one 16-bit device point to
  point, routes on outer and inner layers, single traces and a differential clock. A guide asks for addresses 0 to
  1 mm shorter than the clock, counting package and vias, with package tables on request. Computed: on the board
  alone, 21 lines of 24 outside the rule in length; in time with vias, offsets of −6 to +16 ps. With t_IS 140 to
  290 ps and t_IH 210 ps over a 1876 ps window: at least 640 ps of setup and 710 ps of hold before the controller,
  1.2 % of the free window. Data: −23 to +14 ps against the strobe, 3 to 4 %. Teaches: the rule cannot be judged
  without the package, the margins can be given, and they are what a designer decides on; the balancing offset was
  −35 ps at one input level, +40 ps at the other.
- **A short bend is not a short circuit.** Setting: a meander whose bends are as long as the track is wide. A path
  graph joining ends whose copper touches lost every bend, 3 mm on a 22 mm line, and reported them as a branch.
  Teaches: compare a path with the copper of its net.
