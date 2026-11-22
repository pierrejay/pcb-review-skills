"""Check step: `fills_check.py <board.kicad_pcb>`, with KiCad's bundled Python, exits 1 with one line per zone whose
stored fill differs from a refill (`kicad_copper.fills_current`, on a load of the board that is never saved).
"""
import sys

import pcbnew

from kicad_copper import fills_current


def main(path):
    stale = fills_current(pcbnew.LoadBoard(path))
    for s in stale:
        print(f"stale fill: {s['net']} on {s['layer']}: stored {s['stored_mm2']} mm², "
              f"refilled {s['refilled_mm2']} mm², {s['differing_mm2']} mm² differ")
    if stale:
        sys.exit(f"{len(stale)} stale zone fill(s): refill the zones in KiCad (B) and save the board")
    print("zone fills current")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: fills_check.py <board.kicad_pcb>")
    main(sys.argv[1])
