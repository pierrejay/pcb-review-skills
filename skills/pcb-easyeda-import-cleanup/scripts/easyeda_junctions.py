#!/usr/bin/env python3
"""Junctions lost at the EasyEDA Pro → KiCad import (cross nodes).

In EasyEDA, a wire is a single object whose segments share vertices: a vertex where 3 or 4 branches meet is
connected without a drawn junction dot. The KiCad import does place a junction on T nodes (3 branches), but not on
cross nodes (4 branches): it merges the aligned segments into two wires that cross, which KiCad considers NOT
connected. The schematic net is then cut in two while the imported PCB is right (typical victim: a small node such
as the load capacitor and the feedback resistor of a crystal), and "Update PCB from Schematic" (F8) cuts a node
that the EasyEDA PCB connects.

Usage: easyeda_junctions.py <project.epro> <project.kicad_sch> [--fix]
Without --fix: report only, exit code 1 if a junction is missing. --fix adds the missing junctions (backup
<sch>.before_junctions, next to the schematic) and exits with 0. To be run on the renamed import, before any
other schematic step. No vertex of degree 3 or more in the .esch: nothing to check, exit code 0.
Coordinate system: x_KiCad = x_EasyEDA × 0.254 + dx, y_KiCad = dy − y_EasyEDA × 0.254 (the .esch stores lengths
in units of 0.254 mm, Y up); dx, dy are calibrated on the T nodes that already have a junction, kept to 0.1 µm
(100.254 rounded to 100.25 lands beside the wires). Offsets tied in the vote are told apart by the KiCad wires
(the one under which the nodes land on wires wins); still tied → the script stops (ambiguous calibration). A
junction is added, or counted as present, only where at least two KiCad wires pass EXACTLY through the point, in
KiCad's internal units (0.1 µm): KiCad connects only an exact coincidence. A node with a junction or wires near it
(within 2 µm) without coinciding, or off the wires, stops the script: proximity is not a connection, nothing is
announced as repaired that is not.
The script also stops on a schematic with more than one sheet, on a KiCad schematic without any junction (no
calibration possible), and when the best offset rests on a single node (schematic and .epro do not match). Every
stop exits with code 1 and writes nothing.
"""
import collections
import json
import re
import shutil
import sys
import uuid
import zipfile


def easyeda_nodes(epro):
    """Vertices of degree ≥ 3 (segment ends of a same wire, T on the middle of a segment included)."""
    with zipfile.ZipFile(epro) as z:
        names = [n for n in z.namelist() if n.endswith(".esch")]
        if len(names) != 1:
            sys.exit(f"{len(names)} schematic sheets: not supported")
        lines = z.read(names[0]).decode().splitlines()
    nodes = {}
    for line in lines:
        if not line.startswith('["WIRE"'):
            continue
        # one list per stroke: [x1, y1, x2, y2] (older exports) or a polyline [x1, y1, x2, y2, x3, y3, ...]
        segs = [tuple(s[i:i + 4]) for s in json.loads(line)[2] for i in range(0, len(s) - 3, 2)
                if (s[i], s[i + 1]) != (s[i + 2], s[i + 3])]
        deg = collections.Counter()
        for x1, y1, x2, y2 in segs:
            deg[(x1, y1)] += 1
            deg[(x2, y2)] += 1
        for x1, y1, x2, y2 in segs:  # end of a segment sitting on the middle of another: two more branches
            for t in segs:
                for p in ((t[0], t[1]), (t[2], t[3])):
                    if p in ((x1, y1), (x2, y2)):
                        continue
                    if (min(x1, x2) <= p[0] <= max(x1, x2) and min(y1, y2) <= p[1] <= max(y1, y2)
                            and (x2 - x1) * (p[1] - y1) == (y2 - y1) * (p[0] - x1)):
                        deg[p] += 2
        for p, d in deg.items():
            if d >= 3:
                nodes[p] = max(nodes.get(p, 0), d)
    return nodes


IU = 1e4                                      # KiCad schematic internal units per mm (0.1 µm)
NEAR = 20                                     # IU (2 µm): closer than this without coinciding = uncertain, refused


def iu(v):
    return round(v * IU)


def kicad_wires(s):
    """Wire segments of a .kicad_sch in internal units: [((x1, y1), (x2, y2))]."""
    return [((iu(float(a)), iu(float(b))), (iu(float(c)), iu(float(d)))) for a, b, c, d in re.findall(
        r"\(wire\s*\(pts\s*\(xy ([-\d.]+) ([-\d.]+)\)\s*\(xy ([-\d.]+) ([-\d.]+)\)", s)]


def wires_through(pt, wires, near=0):
    """Number of wires whose segment holds `pt` (internal units): exactly (`near` 0, the only incidence KiCad
    connects: an end, or a point on the segment), or within `near` units (to detect an uncertain placement)."""
    n = 0
    for (x1, y1), (x2, y2) in wires:
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        if L2 == 0:
            continue
        if near == 0:
            cross = (pt[0] - x1) * dy - (pt[1] - y1) * dx
            dot = (pt[0] - x1) * dx + (pt[1] - y1) * dy
            n += cross == 0 and 0 <= dot <= L2
        else:
            u = max(0.0, min(1.0, ((pt[0] - x1) * dx + (pt[1] - y1) * dy) / L2))
            n += ((pt[0] - x1 - u * dx) ** 2 + (pt[1] - y1 - u * dy) ** 2) ** 0.5 <= near
    return n


def fmt(v):
    return f"{v / IU:.4f}".rstrip("0").rstrip(".")


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: easyeda_junctions.py <project.epro> <project.kicad_sch> [--fix]")
    epro, sch = sys.argv[1], sys.argv[2]
    s = open(sch).read()
    junctions = {(iu(float(a)), iu(float(b))) for a, b in re.findall(r"\(junction\s*\(at ([-\d.]+) ([-\d.]+)\)", s)}
    nodes = easyeda_nodes(epro)
    if not nodes:
        print("no vertex of degree 3 or more in the EasyEDA schematic: nothing to check")
        sys.exit(0)
    if not junctions:                    # the offset is calibrated on the junctions the import did place
        sys.exit("no junction in the KiCad schematic: the EasyEDA → KiCad offset cannot be calibrated; place the "
                 "junctions of the T nodes by hand (or check that the schematic given is the imported one)")
    # calibration, in internal units: most frequent offset between EasyEDA nodes and existing KiCad junctions
    votes = collections.Counter()
    for (x, y) in nodes:
        for jx, jy in junctions:
            votes[(jx - iu(x * 0.254), jy + iu(y * 0.254))] += 1
    n = votes.most_common(1)[0][1]
    if n < 2:                            # one vote proves nothing: any node pairs with any junction once
        sys.exit("calibration impossible: the best offset is supported by a single node; the schematic and the "
                 ".epro do not seem to match")
    wires = kicad_wires(s)
    tf = lambda x, y, o: (iu(x * 0.254) + o[0], o[1] - iu(y * 0.254))  # noqa: E731
    tied = [o for o, c in votes.items() if c == n]
    if len(tied) > 1:                    # told apart by the wires: the nodes must land exactly on KiCad wires
        score = {o: sum(wires_through(tf(x, y, o), wires) >= 2 for x, y in nodes) for o in tied}
        best = max(score.values())
        tied = [o for o in tied if score[o] == best]
        if len(tied) > 1:
            sys.exit(f"ambiguous calibration: offsets {[(fmt(a), fmt(b)) for a, b in tied]} are tied ({n} votes, "
                     f"{best} nodes on wires each)")
    off = tied[0]
    missing, uncertain = [], []
    stats = collections.Counter()
    for p, d in sorted(nodes.items()):
        k = tf(*p, off)
        ok = k in junctions                       # KiCad connects only an exact coincidence
        if ok and wires_through(k, wires) < 2:    # a marker there that the wires do not cross (an earlier repair
            uncertain.append((d, k, "a junction sits on the node but the wires do not pass exactly through it"))
            continue                              # off the wire): not present, refused
        if not ok and any(abs(k[0] - jx) <= NEAR and abs(k[1] - jy) <= NEAR for jx, jy in junctions):
            uncertain.append((d, k, "a junction lies near the node without coinciding"))
            continue
        stats[(d, ok)] += 1
        if not ok:
            if wires_through(k, wires) >= 2:
                missing.append((d, k))
            elif wires_through(k, wires, NEAR) >= 2:
                uncertain.append((d, k, "the wires pass near the node without coinciding"))
            else:
                uncertain.append((d, k, "the node does not land on two KiCad wires"))
    print(f"calibration dx={fmt(off[0])} dy={fmt(off[1])} ({n} matching nodes); nodes (branches, junction present): "
          f"{dict(stats)}")
    for d, k in missing:
        print(f"  missing junction: {d} branches at ({fmt(k[0])}, {fmt(k[1])})")
    if uncertain:                        # proximity is not a connection: nothing announced, nothing written
        sys.exit(f"{len(uncertain)} node(s) not resolved: "
                 + "; ".join(f"({fmt(k[0])}, {fmt(k[1])}): {why}" for _, k, why in uncertain[:5])
                 + "; check them in KiCad (netlist), nothing written")
    if missing and "--fix" in sys.argv:
        shutil.copy2(sch, sch + ".before_junctions")
        add = "".join(f'\t(junction\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n'
                      f'\t\t(uuid "{uuid.uuid4()}")\n\t)\n' for _, (x, y) in missing)
        i = s.index("\n\t(junction\n") + 1
        open(sch, "w").write(s[:i] + add + s[i:])
        print(len(missing), "junction(s) added; check the netlist (check_nets) before F8")
    sys.exit(1 if missing and "--fix" not in sys.argv else 0)


if __name__ == "__main__":
    main()
