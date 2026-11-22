"""Copper of a KiCad board read with pcbnew (KiCad's bundled Python; unit nm unless a function says mm): one
enumeration of the copper of a layer (`copper_items`) and the polygon, isolation, capacitance, DC-drop and thermal
helpers built on it. A board outside what they read raises `Unsupported` (`require_domain`)."""
import heapq
import math
from dataclasses import dataclass
from pathlib import Path

import pcbnew as P

MAXERR = P.FromMM(0.002)       # arc approximation; ERROR_OUTSIDE: polygons cover the real copper (a distance
                               # is never optimistic, by at most MAXERR per side the other way)
GRAPHIC_KINDS = {"PCB_SHAPE", "PCB_TEXT", "PCB_FIELD"}   # graphic items read as copper; any other kind is refused
NO_NET = "(no net)"


class Unsupported(ValueError):
    """The board holds something these functions do not read (`require_domain`): refused, not guessed."""


def fills_current(board, tol_mm2=0.0):
    """Zones whose stored fill differs from a refill (beyond twice the arc error, then `tol_mm2`): [{"net", "layer",
    "stored_mm2", "refilled_mm2", "differing_mm2"}]. Refills `board` in memory: pass a load made for this check,
    never saved, with its .kicad_pro (and .kicad_dru) beside the file."""
    name = board.GetFileName()
    if name and not Path(name).with_suffix(".kicad_pro").exists():
        raise ValueError(f"{Path(name).with_suffix('.kicad_pro').name} missing beside {name}: a refill without the "
                         f"project's rules differs from the stored fill; copy the .kicad_pro (and .kicad_dru) with it")
    shrink = board.GetDesignSettings().m_MaxError

    def fills():
        out = {}
        for z in board.Zones():
            if z.GetIsRuleArea():
                continue
            for lay in z.GetLayerSet().CuStack():
                if z.HasFilledPolysForLayer(lay):
                    out[(z.m_Uuid.AsString(), lay)] = (z.GetNetname(), P.SHAPE_POLY_SET(z.GetFilledPolysList(lay)))
        return out
    before = fills()
    P.ZONE_FILLER(board).Fill(board.Zones())
    after = fills()
    stale, empty = [], P.SHAPE_POLY_SET()
    for k in sorted(set(before) | set(after)):
        net = (before.get(k) or after.get(k))[0]
        p0, p1 = before.get(k, (net, empty))[1], after.get(k, (net, empty))[1]
        xor = P.SHAPE_POLY_SET(p0)
        xor.BooleanXor(p1)
        d = xor.Area() / 1e12
        wide = P.SHAPE_POLY_SET(xor)
        wide.Deflate(shrink, P.CORNER_STRATEGY_ROUND_ALL_CORNERS, shrink)   # slivers under 2 × the arc error go
        if d > 0 and wide.Area() / 1e12 > tol_mm2:
            stale.append({"net": net, "layer": board.GetLayerName(k[1]), "stored_mm2": round(p0.Area() / 1e12, 3),
                          "refilled_mm2": round(p1.Area() / 1e12, 3), "differing_mm2": round(d, 6)})
    return stale


def require_domain(board):
    """Raise Unsupported, naming the item, if the board holds something these functions do not read."""
    cu = list(board.GetEnabledLayers().CuStack())
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetViaType() != P.VIATYPE_THROUGH:
            raise Unsupported(f"via of type {t.GetViaType()} at ({P.ToMM(t.GetPosition().x):.3f}, "
                              f"{P.ToMM(t.GetPosition().y):.3f}) mm: only through vias are supported")
        if t.GetClass() == "PCB_VIA" and any(t.IsBackdrilledOrPostMachined(l) for l in cu):
            raise Unsupported(f"backdrilled or post-machined via at ({P.ToMM(t.GetPosition().x):.3f}, "
                              f"{P.ToMM(t.GetPosition().y):.3f}) mm: not supported")
    for f in board.GetFootprints():
        for q in f.Pads():
            if q.HasHole() and any(q.IsBackdrilledOrPostMachined(l) for l in cu):
                raise Unsupported(f"{f.GetReference()}.{q.GetNumber()}: backdrilled or post-machined hole, not supported")
    for z in list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]:
        if z.GetIsRuleArea():
            continue
        if not z.IsFilled():
            raise Unsupported(f"zone {z.GetNetname() or NO_NET} not filled in the file read: refill (B) and save")
        layers = [l for l in board.GetEnabledLayers().CuStack() if z.IsOnLayer(l)]
        for l in layers if z.GetNetname() else []:   # islands KiCad found unconnected at the last fill, whatever
            fill = z.GetFilledPolysList(l)           # the removal mode ("never" or "below an area" keep them)
            isles = [i for i in range(fill.OutlineCount()) if z.IsIsland(l, i)]
            if isles:
                c = fill.Outline(isles[0]).BBox().Centre()
                raise Unsupported(f"zone {z.GetNetname()} has {len(isles)} isolated island(s) on "
                                  f"{board.GetLayerName(l)} (one near ({P.ToMM(c.x):.2f}, {P.ToMM(c.y):.2f}) mm): "
                                  "floating copper of a net would pass for a connected plane; remove the islands "
                                  "(island removal 'always') and refill")
        if z.GetNetname() and all(z.GetFilledPolysList(l).OutlineCount() == 0 for l in layers):
            raise Unsupported(f"zone {z.GetNetname()} has an empty fill on every layer: refill (B) and save, or "
                              "remove it")
    items = [d for d in board.GetDrawings()] + [d for f in board.GetFootprints()
                                                for d in list(f.GraphicalItems()) + list(f.GetFields())]
    for d in items:
        if not any(P.IsCopperLayer(l) for l in d.GetLayerSet().Seq()):
            continue
        if d.GetClass() == "PCB_SHAPE" and d.IsHatchedFill():
            raise Unsupported("hatched shape on a copper layer: its plotted copper is not its outline")
        if d.GetClass() not in GRAPHIC_KINDS:
            raise Unsupported(f"{d.GetClass()} on a copper layer: copper of a kind the enumeration does not read")


@dataclass
class Copper:
    net: str                   # net name, NO_NET for copper without a net (still copper)
    kind: str                  # "pad", "barrel", "track", "arc", "via", "zone", "graphic"
    ref: str                   # what to print: "U3.4", "zone GND", "PCB_SHAPE of J1"…
    poly: object               # SHAPE_POLY_SET, nm
    footprint: object = None   # owning FOOTPRINT for pads, barrels and footprint items, else None
    connected: bool = True     # False for a barrel crossing a layer where it has no pad: copper, not a connection
    item: object = None        # the pcbnew object


def _poly(item, layer, maxerr):
    sp = P.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(sp, layer, 0, maxerr, P.ERROR_OUTSIDE)
    return sp


def _disc(center, diameter, maxerr):
    """Circle as a polygon (barrel of a plated hole: the hole wall is copper on every layer it crosses)."""
    sp = P.SHAPE_POLY_SET()
    n = max(16, math.ceil(math.pi / math.acos(max(-1.0, 1 - maxerr / (diameter / 2)))))   # sagitta ≤ maxerr
    r = diameter / 2 / math.cos(math.pi / n)            # circumscribed: the polygon covers the circle (ERROR_OUTSIDE)
    sp.NewOutline()
    for k in range(n):
        a = 2 * math.pi * k / n
        sp.Append(int(center.x + r * math.cos(a)), int(center.y + r * math.sin(a)))
    return sp


def _is_copper_layer(board, layer):
    return P.IsCopperLayer(layer) and board.IsLayerEnabled(layer)


def copper_items(board, layer, maxerr=MAXERR):
    """Every piece of copper on one enabled copper layer, as `Copper` records, nothing filtered by net or class; a
    plated hole crossing the layer without a pad there is a "barrel" (connected=False)."""
    if not _is_copper_layer(board, layer):
        raise ValueError(f"layer {layer} is not an enabled copper layer of this board")
    require_domain(board)
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if not p.IsOnLayer(layer) and p.GetAttribute() != P.PAD_ATTRIB_PTH:
                continue
            net = p.GetNetname() or NO_NET
            ref = f"{f.GetReference()}.{p.GetNumber()}"
            if p.GetAttribute() == P.PAD_ATTRIB_NPTH:
                if p.IsOnLayer(layer) and p.FlashLayer(layer):       # KiCad plots copper around the hole
                    sp = _poly(p, layer, maxerr)
                    hole = P.SHAPE_POLY_SET()
                    p.TransformHoleToPolygon(hole, 0, maxerr, P.ERROR_INSIDE)   # hole drawn small: copper not lost
                    sp.BooleanSubtract(hole)
                    if sp.OutlineCount():
                        out.append(Copper(net, "pad", ref, sp, f, True, p))
                continue                                            # unplated hole without ring: no copper
            if p.IsOnLayer(layer) and p.FlashLayer(layer):
                out.append(Copper(net, "pad", ref, _poly(p, layer, maxerr), f, True, p))
            elif p.GetAttribute() == P.PAD_ATTRIB_PTH and p.HasHole():
                wall = P.SHAPE_POLY_SET()                         # the real hole: a slot keeps length and angle
                p.TransformHoleToPolygon(wall, 0, maxerr, P.ERROR_OUTSIDE)
                out.append(Copper(net, "barrel", ref, wall, f, False, p))
    for t in board.GetTracks():
        net = t.GetNetname() or NO_NET
        cls = t.GetClass()
        if cls == "PCB_VIA":
            if not t.IsOnLayer(layer):                              # outside the span of a blind or buried via
                continue
            if t.FlashLayer(layer):
                out.append(Copper(net, "via", f"via {net}", _poly(t, layer, maxerr), None, True, t))
            else:
                out.append(Copper(net, "barrel", f"via {net}", _disc(t.GetPosition(), t.GetDrillValue(), maxerr),
                                  None, False, t))
        elif cls in ("PCB_TRACK", "PCB_ARC"):
            if t.IsOnLayer(layer):
                out.append(Copper(net, "arc" if cls == "PCB_ARC" else "track", f"{cls} {net}",
                                  _poly(t, layer, maxerr), None, True, t))
        else:
            raise ValueError(f"{cls} among the tracks: an item the enumeration does not read")
    zones = [(z, None) for z in board.Zones()] + [(z, f) for f in board.GetFootprints() for z in f.Zones()]
    for z, f in zones:
        if z.GetIsRuleArea() or not z.IsOnLayer(layer):
            continue
        net = z.GetNetname() or NO_NET
        out.append(Copper(net, "zone", f"zone {net}" + (f" of {f.GetReference()}" if f else ""),
                          P.SHAPE_POLY_SET(z.GetFilledPolysList(layer)), f, True, z))
    graphics = [(d, None) for d in board.GetDrawings()] + \
               [(d, f) for f in board.GetFootprints() for d in list(f.GraphicalItems()) + list(f.GetFields())]
    for d, f in graphics:
        if not d.IsOnLayer(layer):
            continue
        cls = d.GetClass()                                         # one of GRAPHIC_KINDS (require_domain)
        if cls in ("PCB_TEXT", "PCB_FIELD") and not d.IsVisible():
            continue                                                # hidden text is not plotted: no copper
        net = (d.GetNetname() if hasattr(d, "GetNetname") else "") or NO_NET
        out.append(Copper(net, "graphic", cls + (f" of {f.GetReference()}" if f else ""),
                          _poly(d, layer, maxerr), f, True, d))
    return out


def copper_by_net(board, layer, connected_only=False, maxerr=MAXERR):
    """Net name → SHAPE_POLY_SET of all its copper on one layer (merged, holes kept). connected_only drops barrels."""
    per = {}
    for c in copper_items(board, layer, maxerr):
        if connected_only and not c.connected:
            continue
        per.setdefault(c.net, []).append(c.poly)
    return {n: merge(polys) for n, polys in per.items()}


# --- polygon operations ---------------------------------------------------------------------------------------
def merge(polys):
    """Union of SHAPE_POLY_SETs, holes kept (copper sitting in a hole of another copper is not covered)."""
    out = P.SHAPE_POLY_SET()
    for sp in polys:
        out.Append(sp)
    out.Simplify()
    return out


def pieces(sp):
    """Connected pieces of a polygon set: each outline with its own holes, as a separate SHAPE_POLY_SET."""
    out = []
    for i in range(sp.OutlineCount()):
        p = P.SHAPE_POLY_SET()
        p.AddOutline(sp.Outline(i))
        for h in range(sp.HoleCount(i)):
            p.AddHole(sp.Hole(i, h))
        out.append(p)
    return out


def overlap(a, b):
    """Common area (nm²) of two polygon sets and one point of it; (0, None) if they are disjoint."""
    if a.OutlineCount() == 0 or b.OutlineCount() == 0:
        return 0.0, None
    c, d = P.SHAPE_POLY_SET(a), P.SHAPE_POLY_SET(b)
    c.Simplify(); d.Simplify()
    c.BooleanIntersection(d)
    area = c.Area()
    return (area, _copy(c.Outline(0).CPoint(0))) if area > 0 and c.OutlineCount() else (0.0, None)


def _copy(pt):
    """A point that owns its memory: CPoint returns a reference into the polygon set, invalid once the set is freed."""
    return P.VECTOR2I(int(pt.x), int(pt.y))


def min_distance(a, b):
    """(minimum distance nm, a point where it is reached) between two polygon sets, holes included; 0 if they overlap,
    (inf, None) if one is empty."""
    area, pt = overlap(a, b)                   # crossing outlines have no vertex inside each other
    if area > 0:
        return 0.0, pt
    best, where = math.inf, None
    for src, dst in ((a, b), (b, a)):
        if dst.OutlineCount() == 0:
            continue
        for i in range(src.OutlineCount()):
            for chain in [src.Outline(i)] + [src.Hole(i, h) for h in range(src.HoleCount(i))]:
                for k in range(chain.PointCount()):
                    pt = chain.CPoint(k)
                    d = dst.SquaredDistance(pt)
                    if d < best:
                        best, where = d, _copy(pt)
    return (math.sqrt(best), where) if where is not None else (math.inf, None)


def floating_path(side_a, side_b, floating):
    """Shortest path side_a → floating copper → side_b through one or several floating pieces (`floating`:
    [(description, SHAPE_POLY_SET)]): (total nm, [(description, gap nm before it), …, ("side b", last gap)]), or None.
    """
    nodes = {"a": (side_a, "side a"), "b": (side_b, "side b")}
    for k, (desc, sp) in enumerate(floating):
        parts = pieces(sp)
        for i, piece in enumerate(parts):
            nodes[(k, i)] = (piece, desc + (f" #{i + 1}" if len(parts) > 1 else ""))
    isles = [k for k in nodes if k not in ("a", "b")]
    if not isles or not side_a.OutlineCount() or not side_b.OutlineCount():
        return None
    gaps = {}

    def gap(u, v):
        key = frozenset((u, v))
        if key not in gaps:
            gaps[key] = min_distance(nodes[u][0], nodes[v][0])[0]
        return gaps[key]

    dist, prev, queue, done, n = {"a": 0.0}, {}, [(0.0, 0, "a")], set(), 0
    while queue:
        d, _, u = heapq.heappop(queue)
        if u in done:
            continue
        done.add(u)
        if u == "b":
            break
        for v in isles + ([] if u == "a" else ["b"]):
            if v not in done and d + gap(u, v) < dist.get(v, math.inf):
                n += 1
                dist[v], prev[v] = d + gap(u, v), u
                heapq.heappush(queue, (dist[v], n, v))
    if math.isinf(dist.get("b", math.inf)):
        return None
    hops, v = [], "b"
    while v != "a":
        hops.append((nodes[v][1], gap(prev[v], v)))
        v = prev[v]
    return dist["b"], list(reversed(hops))


# --- the two sides of an isolation barrier ----------------------------------------------------------------------
def isolated_nets(board, seeds, barrier_refs, logic_stop):
    """(nets of the isolated side, sorted bridges): grown from `seeds` through every component except `barrier_refs`;
    a component touching a `logic_stop` net is a bridge, listed, not crossed."""
    present = {p.GetNetname() for f in board.GetFootprints() for p in f.Pads()}
    refs = {f.GetReference() for f in board.GetFootprints()}
    for what, names, known in (("seed nets", seeds, present), ("logic_stop nets", logic_stop, present),
                               ("barrier references", barrier_refs, refs)):
        missing = sorted(set(names) - known)
        if missing:                       # a stale name would move the barrier or empty one side, silently
            raise ValueError(f"{what} not found on the board: {missing}")
    if not barrier_refs or not logic_stop:
        raise ValueError("the barrier and the logic side must both be named")
    nets, bridges, changed = set(seeds), set(), True
    while changed:
        changed = False
        for f in board.GetFootprints():
            if f.GetReference() in barrier_refs:
                continue
            fn = {p.GetNetname() for p in f.Pads() if p.GetNetname()}
            if fn & nets and not fn <= nets:
                if fn & set(logic_stop):
                    bridges.add(f.GetReference())
                    continue
                nets |= fn
                changed = True
    if nets & set(logic_stop):
        raise ValueError(f"logic nets reached the isolated side: {sorted(nets & set(logic_stop))}")
    return nets, sorted(bridges)


def _connected(net):
    return bool(net) and net != NO_NET and not net.startswith("unconnected-")


def side_of(c, iso):
    """True isolated, False logic, None floating; copper of a footprint with no real net takes the side of the
    footprint's nearest connected pad."""
    if _connected(c.net):
        return c.net in iso
    if c.footprint is None:
        return None
    others = [q for q in c.footprint.Pads() if _connected(q.GetNetname())]
    if not others:
        return None
    bb = c.poly.BBox()
    here = P.VECTOR2I(int(bb.GetCenter().x), int(bb.GetCenter().y))
    q = min(others, key=lambda q: (q.GetPosition() - here).EuclideanNorm())
    return q.GetNetname() in iso


# --- capacitance between facing copper -----------------------------------------------------------------------
EPS0 = 8.854e-12


def overlap_area_mm2(a, b):
    """Area (mm²) of copper a facing copper b (two layers): area of their intersection."""
    return overlap(a, b)[0] / 1e12


def parallel_plate_pf(area_mm2, h_mm, er):
    """Parallel-plate capacitance (pF) through a dielectric of thickness h_mm; fringing not counted (a lower bound)."""
    return EPS0 * er * area_mm2 * 1e-6 / (h_mm * 1e-3) * 1e12


# --- one rail, exported for the DC-drop solver (millimetres) -------------------------------------------------------
def _pts_mm(chain):
    return [(chain.CPoint(k).x / 1e6, chain.CPoint(k).y / 1e6) for k in range(chain.PointCount())]


def net_by_name(board, net):
    """The net item that bears `net` now (`FindNet` still answers to a name changed in memory); ValueError if none."""
    for n in board.GetNetInfo().NetsByNetcode().values():
        if str(n.GetNetname()) == net:
            return n
    raise ValueError(f"net {net!r} not found on the board")


def _require_net(board, net):
    """Raises unless a net of the board bears that name now."""
    net_by_name(board, net)


def rail_copper(board, net, layer, maxerr=P.FromMM(0.005)):
    """Copper that carries `net` on one layer, barrels excluded, in mm: [{"outline": [(x, y)], "holes": [[(x, y)]]}].
    Raises if no net bears that name now."""
    _require_net(board, net)
    sp = merge([c.poly for c in copper_items(board, layer, maxerr) if c.net == net and c.connected])
    return [{"outline": _pts_mm(sp.Outline(i)), "holes": [_pts_mm(sp.Hole(i, h)) for h in range(sp.HoleCount(i))]}
            for i in range(sp.OutlineCount())]


def rail_pad(board, ref, number, layer, maxerr=P.FromMM(0.005), piece=None):
    """A source or load pad for `irdrop2d`, mm: {"x", "y", "w", "h" (bounding box of its copper on `layer`), "anchor"
    (pad position), "layer", "outline"}. A pad number with several pieces of copper needs `piece` (0-based, by x, y)."""
    pads = [q for f in board.GetFootprints() if f.GetReference() == ref for q in f.Pads() if q.GetNumber() == str(number)]
    pads = sorted((q for q in pads if q.IsOnLayer(layer) and q.FlashLayer(layer)),
                  key=lambda q: (q.GetPosition().x, q.GetPosition().y))
    if not pads:
        raise ValueError(f"pad {ref}.{number} has no copper on {board.GetLayerName(layer)}")
    if piece is None and len(pads) > 1:
        raise ValueError(f"{len(pads)} pads {ref}.{number} with copper on {board.GetLayerName(layer)} (a pad in "
                         f"pieces): pass piece=0…{len(pads) - 1} and declare one load per piece")
    q = pads[piece or 0]
    sp = _poly(q, layer, maxerr)
    bb = sp.BBox()
    c = bb.Centre()
    return {"x": c.x / 1e6, "y": c.y / 1e6, "w": bb.GetWidth() / 1e6, "h": bb.GetHeight() / 1e6,
            "anchor": (q.GetPosition().x / 1e6, q.GetPosition().y / 1e6), "layer": board.GetLayerName(layer),
            "outline": _pts_mm(sp.Outline(0))}


def rail_links(board, net):
    """Inter-layer links of a rail, mm: [{"x", "y", "drill"}] for its vias and plated through pads; a slot's "drill" is
    the round hole of the same wall length (perimeter / π)."""
    require_domain(board)
    _require_net(board, net)
    out = [{"x": t.GetPosition().x / 1e6, "y": t.GetPosition().y / 1e6, "drill": t.GetDrillValue() / 1e6}
           for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == net]
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != net or p.GetAttribute() != P.PAD_ATTRIB_PTH:
                continue
            s = p.GetDrillSize()
            if p.GetDrillShape() == P.PAD_DRILL_SHAPE_OBLONG and s.x != s.y:
                L, W = max(s.x, s.y), min(s.x, s.y)
                d = (2 * (L - W) + math.pi * W) / math.pi
            else:
                d = s.x
            out.append({"x": p.GetPosition().x / 1e6, "y": p.GetPosition().y / 1e6, "drill": d / 1e6})
    return out


# --- grids for the thermal model ----------------------------------------------------------------------------------
def board_mask(board, xs, ys):
    """1 where the cell centre (mm) is inside the board outline, else 0. Raises if the outline is not closed."""
    outline = P.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outline, True):
        raise ValueError("board outline not closed")
    return [[1 if outline.Contains(P.VECTOR2I(P.FromMM(x), P.FromMM(y))) else 0 for y in ys] for x in xs]


def copper_fraction(board, layer, xs, ys, d, maxerr=MAXERR):
    """Copper fraction of each d × d mm cell centred on (x, y) of one layer (3 × 3 point sampling)."""
    sp = merge([c.poly for c in copper_items(board, layer, maxerr)])
    sub = [(dx, dy) for dy in (-d / 3, 0, d / 3) for dx in (-d / 3, 0, d / 3)]
    return [[sum(sp.Contains(P.VECTOR2I(P.FromMM(x + dx), P.FromMM(y + dy))) for dx, dy in sub) / 9
             for y in ys] for x in xs]


# --- isolation, from the board to the minimum distance of one layer -----------------------------------------------
def isolation_minimum(board, layer, iso):
    """Isolation of one layer, iso the nets of `isolated_nets`: {"direct_mm", "floating_mm" (None without a floating
    path), "min_mm", "iso_empty", "logic_empty", "floating_count"}; min_mm None when one side has no copper."""
    items = copper_items(board, layer)
    sides = [(c, side_of(c, iso)) for c in items]
    a = merge([c.poly for c, s in sides if s is True])
    g = merge([c.poly for c, s in sides if s is False])
    fl = [(c.ref, c.poly) for c, s in sides if s is None]
    out = {"iso_empty": a.OutlineCount() == 0, "logic_empty": g.OutlineCount() == 0, "floating_count": len(fl)}
    if out["iso_empty"] or out["logic_empty"]:
        return {**out, "direct_mm": None, "floating_mm": None, "min_mm": None}
    direct = P.ToMM(int(min_distance(a, g)[0]))
    path = floating_path(a, g, fl)
    floating = P.ToMM(int(path[0])) if path else None
    return {**out, "direct_mm": direct, "floating_mm": floating,
            "min_mm": min(direct, floating) if floating is not None else direct}
