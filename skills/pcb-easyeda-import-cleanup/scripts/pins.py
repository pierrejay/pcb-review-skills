"""Positions of the pins placed in the schematic (KiCad transform: Y inverted, rotation, then mirror).

A pin of the library symbol at (px, py) (symbol frame, Y up) lands in the sheet (Y down) at: (px, −py), rotated
by the symbol angle, THEN mirrored ("mirror x" flips Y, "mirror y" flips X), then translated by the symbol
position. Mirroring before rotating gives wrong positions on any symbol that is both rotated and mirrored, and a
live wire end then looks dead.
Works on the text of a .kicad_sch (single sheet): `placed_pins(text)` → [(reference, pin number, x, y), …], mm.
"""
import math
import re
from sexp import top_blocks, block_end


_PIN = re.compile(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)[\s\S]*?\(number "([^"]*)"')


def lib_pins(s):
    """Pins of each symbol of the embedded library: {lib_id: [(number, x, y, unit, body_style), …]} (symbol frame).
    KiCad keeps the pins in sub-symbols named `<name>_<unit>_<style>`: unit 0 is common to every unit, style 0 to
    both body styles. A pin outside any sub-symbol counts as (0, 0)."""
    i = s.index("(lib_symbols"); lib = s[i:block_end(s, i)]
    out = {}
    for m in re.finditer(r'\n\t\t\(symbol "([^"]+)"', lib):
        a = m.start() + 3
        blk = lib[a:block_end(lib, a)]
        pins, taken = [], []
        for sm in re.finditer(r'\(symbol "[^"]*?_(\d+)_(\d+)"', blk[1:]):
            sa = sm.start() + 1
            sb = block_end(blk, sa)
            taken.append((sa, sb))
            unit, style = int(sm.group(1)), int(sm.group(2))
            pins += [(num, float(x), float(y), unit, style) for x, y, num in _PIN.findall(blk[sa:sb])]
        rest = "".join(blk[k:l] for k, l in zip([0] + [b for _, b in taken], [a_ for a_, _ in taken] + [len(blk)]))
        pins += [(num, float(x), float(y), 0, 0) for x, y, num in _PIN.findall(rest)]
        out[m.group(1)] = pins
    return out


def placed_pins(s):
    """Sheet position of each pin of each placed symbol: [(reference, pin number, x, y), …] (0.1 µm, KiCad's
    internal unit, so that a test of exact coincidence holds). Only the pins of the unit placed and of its body
    style, with the common ones (unit 0, style 0): unit 1 of a dual op-amp has pins 1, 2, 3, not the other unit's nor
    the power unit's (those would be phantom pins at wrong positions)."""
    lp = lib_pins(s)
    res = []
    for a, b in top_blocks(s, "symbol"):
        blk = s[a:b]
        lid = re.search(r'\(lib_id "([^"]+)"', blk).group(1)
        x0, y0, rot = (float(v) for v in re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", blk).groups())
        mir = re.search(r"\(mirror (\w)\)", blk)
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        mu = re.search(r"\(unit (\d+)\)", blk)
        ms = re.search(r"\((?:convert|body_style) (\d+)\)", blk)
        unit, style = int(mu.group(1)) if mu else 1, int(ms.group(1)) if ms else 1
        for num, px, py, pu, ps in lp.get(lid, []):
            if pu not in (0, unit) or ps not in (0, style):
                continue
            x, y = px, -py
            r = math.radians(-rot)  # KiCad rotation (counter-clockwise on screen, Y pointing down)
            x, y = x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)
            if mir and mir.group(1) == "x": y = -y
            if mir and mir.group(1) == "y": x = -x
            res.append((ref, num, round(x0 + x, 4), round(y0 + y, 4)))
    return res
