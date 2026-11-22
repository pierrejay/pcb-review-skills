"""Routing of a KiCad board read with pcbnew (KiCad's bundled Python; unit nm): track pieces, the pad-to-pad path of a
net, and the reference plane under a point of a track."""
import heapq
import math
from collections import defaultdict
from dataclasses import dataclass

import pcbnew as P

from kicad_copper import _disc, _poly, copper_items, merge

OWN_RING_NM = 500_000   # screening value: a track within this of the copper of its own via or pad is entering it


def track_pieces(t, chord=100_000):
    """Straight pieces (x0, y0, x1, y1), nm, of a PCB_TRACK or PCB_ARC, an arc cut into chords of at most `chord` nm."""
    if t.GetClass() == "PCB_TRACK":
        return [(t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)]
    cx, cy, r, a0, d = _arc_sweep(t)
    n = max(2, int(abs(d) * r / chord) + 1)
    pts = [(cx + r * math.cos(a0 + d * k / n), cy + r * math.sin(a0 + d * k / n)) for k in range(n + 1)]
    for got, want in ((pts[0], t.GetStart()), (pts[-1], t.GetEnd())):
        if math.dist(got, (want.x, want.y)) > max(1000, chord / 100):   # 1 µm: a nearly straight arc whose radius
            raise ValueError(f"arc at ({P.ToMM(want.x):.3f}, {P.ToMM(want.y):.3f}) mm: its chords do not land on "
                             "its ends (radius beyond what KiCad stores); redraw it as a straight track")
    return [(*p, *q) for p, q in zip(pts, pts[1:])]


def _arc_sweep(t):
    """(centre x, centre y, radius, start angle, signed sweep) of a PCB_ARC, the sweep signed as in track_pieces."""
    c, r = t.GetCenter(), t.GetRadius()
    a0, am, a1 = (math.atan2(p.y - c.y, p.x - c.x) for p in (t.GetStart(), t.GetMid(), t.GetEnd()))
    d = (a1 - a0) % (2 * math.pi)           # counter-clockwise sweep…
    if (am - a0) % (2 * math.pi) > d:       # …unless the midpoint is not on it: the arc turns the other way
        d -= 2 * math.pi
    return c.x, c.y, r, a0, d


def _arc_u(t, x, y):
    """(u, point): the point of the arc `t` at the angle of (x, y) and its position u, fraction of the sweep; off the
    arc, u is read from the nearer end (below 0 before the start, above 1 past the end)."""
    cx, cy, r, a0, d = _arc_sweep(t)
    phi = math.atan2(y - cy, x - cx)
    delta = (phi - a0) % (2 * math.pi) if d > 0 else -((a0 - phi) % (2 * math.pi))
    u, full = delta / d, 2 * math.pi / abs(d)
    if u > 1 and full - u < u - 1:          # nearer the start than the end: just before the start
        u -= full
    return u, (cx + r * math.cos(phi), cy + r * math.sin(phi))


def _arc_part(t, u0, u1, chord=100_000):
    """Chords (x0, y0, x1, y1), nm, of the part of the arc `t` between the positions u0 and u1 (u1 < u0: walked
    backwards), at most `chord` long."""
    cx, cy, r, a0, d = _arc_sweep(t)
    n = max(1, int(abs(d * (u1 - u0)) * r / chord) + 1)
    pts = [(cx + r * math.cos(a0 + d * (u0 + (u1 - u0) * k / n)), cy + r * math.sin(a0 + d * (u0 + (u1 - u0) * k / n)))
           for k in range(n + 1)]
    return [(*p, *q) for p, q in zip(pts, pts[1:])]


def _seg_point(px, py, ax, ay, bx, by):
    """Distance from P to segment AB and the position of its projection along AB (0..1)."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    u = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy)), u


def _crossing(s1, s2):
    """Crossing point (nm) of the centre lines of two straight tracks, strictly inside both, or None."""
    (ax, ay), (bx, by) = (s1.GetStart().x, s1.GetStart().y), (s1.GetEnd().x, s1.GetEnd().y)
    (cx, cy), (dx, dy) = (s2.GetStart().x, s2.GetStart().y), (s2.GetEnd().x, s2.GetEnd().y)
    den = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if den == 0:
        return None
    u = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / den
    v = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / den
    return (ax + u * (bx - ax), ay + u * (by - ay)) if 0 < u < 1 and 0 < v < 1 else None


@dataclass
class Leg:
    """Copper travelled by a path: `track` (PCB_TRACK or PCB_ARC, kiid its KIID as a string), whole or the part of a
    segment between two nodes; length (nm) and pieces [(x0, y0, x1, y1)] nm (an arc: its chords) of that part only,
    in the direction of travel (whatever the direction the track is stored in)."""
    kiid: str
    layer: int
    width: int
    length: float
    pieces: list
    track: object


def _pad_contact(q, t):
    """Parameter u ∈ ]0, 1[ of a point of the straight track `t` whose copper lies on the pad `q`, nearest the pad's
    centre when it can, or None."""
    lay, half = t.GetLayer(), t.GetWidth() // 2
    sx, sy, ex, ey = t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y
    at = lambda u: P.VECTOR2I(int(sx + u * (ex - sx)), int(sy + u * (ey - sy)))   # noqa: E731
    hits = lambda u: 0 < u < 1 and q.HitTest(at(u), half, lay)                       # noqa: E731
    c = q.GetPosition()
    u0 = _seg_point(c.x, c.y, sx, sy, ex, ey)[1]
    if hits(u0):
        return u0
    sp = P.SHAPE_POLY_SET()
    q.TransformShapeToPolygon(sp, lay, 0, 1000, P.ERROR_INSIDE)
    if sp.OutlineCount() == 0:
        return None
    o = sp.Outline(0)
    pts = [(o.CPoint(k).x, o.CPoint(k).y) for k in range(o.PointCount())]
    us = []
    den0 = (ex - sx, ey - sy)
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        den = den0[0] * (by - ay) - den0[1] * (bx - ax)
        if den == 0:
            continue
        u = ((ax - sx) * (by - ay) - (ay - sy) * (bx - ax)) / den
        v = ((ax - sx) * den0[1] - (ay - sy) * den0[0]) / den
        if 0 <= v <= 1:
            us.append(u)
    if us and hits((min(us) + max(us)) / 2):
        return (min(us) + max(us)) / 2
    for u in us + [_seg_point(x, y, sx, sy, ex, ey)[1] for x, y in pts]:
        if hits(u):
            return u
    return None


def _pad_entry(q, t, u_off, u_on):
    """Parameter u of the straight track `t`, between u_off (off the pad `q`) and u_on (on it), where its copper first
    touches the pad, taken 2 µm onto it (nodes sit on a 1 µm grid); None within 1 µm of a track end."""
    lay, half = t.GetLayer(), t.GetWidth() // 2
    sx, sy, ex, ey = t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y
    hits = lambda u: q.HitTest(P.VECTOR2I(int(sx + u * (ex - sx)), int(sy + u * (ey - sy))), half, lay)   # noqa: E731
    lo, hi = float(u_off), float(u_on)
    for _ in range(max(8, int(math.log2(max(t.GetLength(), 1) / 100)) + 2)):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if hits(mid) else (mid, hi)
    hi += (u_on - u_off) * 2000 / max(t.GetLength(), 1)
    return hi if min(hi, 1 - hi) * t.GetLength() > 1000 and (hi - u_off) * (u_on - hi) > 0 else None


def pad_path(board, net, ends, via_layers=False):
    """Shortest pad-to-pad path of `net` between ends = ((ref, pad), (ref, pad)): (legs, number of vias crossed), or
    with via_layers=True (legs, [(layer, layer) joined by each via, in path order]); a plated through pad crossed
    counts as a via. legs: `Leg` records from where the copper enters the first end pad to where it enters the other.
    """
    from kicad_copper import require_domain
    require_domain(board)
    tracks = [t for t in board.GetTracks() if t.GetNetname() == net and t.GetClass() in ("PCB_TRACK", "PCB_ARC")]
    key = lambda pt, lay: (round(pt.x / 1000), round(pt.y / 1000), lay)   # noqa: E731
    at = lambda n: P.VECTOR2I(n[0] * 1000, n[1] * 1000)                   # noqa: E731
    adj, half = defaultdict(list), defaultdict(int)                       # node → edges ; node → track half-width
    for t in tracks:
        a, b = key(t.GetStart(), t.GetLayer()), key(t.GetEnd(), t.GetLayer())
        adj[a].append((b, t.GetLength(), t)); adj[b].append((a, t.GetLength(), t))
        half[a] = max(half[a], t.GetWidth() // 2); half[b] = max(half[b], t.GetWidth() // 2)
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == net]
    for v in vias:                                     # a via is a node on each layer it is flashed on: a via in a
        for l in board.GetEnabledLayers().CuStack():   # pad joins the pad with no track on that layer, a via on the
            if v.FlashLayer(l):                        # middle of a track splits it (T-junction below); its copper
                k = key(v.GetPosition(), l)            # radius on that layer counts in every contact
                adj[k]
                half[k] = max(half[k], v.GetWidth(l) // 2)
    nodes = list(adj)

    def link(u, v, length, how):
        adj[u].append((v, length, how)); adj[v].append((u, length, how))

    def along_copper(u, v, reach):
        """True when v is reached from u along tracks within `reach` nm: their copper touches because one track runs
        from one to the other, not because two conductors meet."""
        seen, todo = {u: 0}, [u]
        while todo:
            c = todo.pop()
            for w, length, how in adj[c]:
                if how == "join":
                    continue
                d = seen[c] + length
                if d <= reach and d < seen.get(w, reach + 1):
                    if w == v:
                        return True
                    seen[w] = d
                    todo.append(w)
        return False

    for i, n in enumerate(nodes):                      # contact between two ends of one layer
        for m in nodes[i + 1:]:
            if n[2] == m[2] and math.hypot(n[0] - m[0], n[1] - m[1]) * 1000 <= half[n] + half[m] \
                    and not along_copper(n, m, 2 * (half[n] + half[m])):
                link(n, m, 0, "join")                  # two round ends whose copper overlaps
    segs = [t for t in tracks if t.GetClass() == "PCB_TRACK"]
    for i, s1 in enumerate(segs):                      # two segments crossing with no common end: a node at the crossing
        for s2 in segs[i + 1:]:
            if s1.GetLayer() != s2.GetLayer():
                continue
            x = _crossing(s1, s2)
            if x is not None:
                n = key(P.VECTOR2I(int(x[0]), int(x[1])), s1.GetLayer())
                if n not in adj:
                    nodes.append(n)
                half[n] = max(half[n], s1.GetWidth() // 2, s2.GetWidth() // 2)
                adj.setdefault(n, [])
    pads = [((f.GetReference(), q.GetNumber()), q) for f in board.GetFootprints() for q in f.Pads()
            if q.GetNetname() == net]                  # every physical pad: two pads may share one number
    end_keys = {tuple(e) for e in ends}
    for k, q in pads:                                  # a pad on the middle of a track: a node where the track
        c = q.GetPosition()                            # passes closest to its centre, if that point is on the pad
        for t in tracks:
            if not q.IsOnLayer(t.GetLayer()):
                continue
            ends_on = [q.HitTest(e, t.GetWidth() // 2, t.GetLayer()) for e in (t.GetStart(), t.GetEnd())]
            if t.GetClass() == "PCB_ARC":
                if not any(ends_on) and any(q.HitTest(P.VECTOR2I(int(pc[0]), int(pc[1])), t.GetWidth() // 2, t.GetLayer())
                                            for pc in track_pieces(t)):
                    from kicad_copper import Unsupported
                    raise Unsupported(f"pad on the middle of an arc on {net!r}: not supported")
                continue
            u = None if any(ends_on) else _pad_contact(q, t)   # an end on the pad is its own terminal
            us = [u]
            if k in end_keys:                          # end pad: the path stops where the copper enters it
                if sum(ends_on) == 1:
                    us = [_pad_entry(q, t, 1 if ends_on[0] else 0, 0 if ends_on[0] else 1)]
                elif u is not None:                    # crossing it: one entry from each side
                    us = [_pad_entry(q, t, 0, u), _pad_entry(q, t, 1, u)]
            for u in us:
                if u is None:
                    continue
                x = P.VECTOR2I(int(t.GetStart().x + u * (t.GetEnd().x - t.GetStart().x)),
                               int(t.GetStart().y + u * (t.GetEnd().y - t.GetStart().y)))
                n = key(x, t.GetLayer())
                if n not in adj:
                    nodes.append(n)
                    adj.setdefault(n, [])
                half[n] = max(half[n], t.GetWidth() // 2)
    projected, joins = [], []
    for t in tracks:                                   # junctions (ends, crossings, vias, pads) on the middle of a track:
        a, b = key(t.GetStart(), t.GetLayer()), key(t.GetEnd(), t.GetLayer())   # the track is cut at every one
        inner = []
        for n in nodes:
            if n[2] != t.GetLayer() or n in (a, b):
                continue
            if t.GetClass() == "PCB_ARC":              # on an arc: at an end (joined there), or the arc is cut
                u, (px, py) = _arc_u(t, n[0] * 1000, n[1] * 1000)
                d = math.hypot(n[0] * 1000 - px, n[1] * 1000 - py)        # radial distance to the arc's axis
                if not (0 < u < 1 and d <= t.GetWidth() / 2 + half[n]):   # the node's copper does not touch the arc
                    continue
                if any(math.hypot(n[0] * 1000 - e.x, n[1] * 1000 - e.y) <= t.GetWidth() / 2 + half[n]
                       for e in (t.GetStart(), t.GetEnd())):
                    continue                           # its copper touches an end of the arc: the end contact joins
                    # them (segments of a few µm, e.g. left by an import, may sit between two arcs of a meander)
                if d > 1000:                           # off the arc's axis: cut it ON its axis
                    pn = key(P.VECTOR2I(int(px), int(py)), t.GetLayer())
                    if pn not in adj and pn not in projected:
                        projected.append(pn)
                    half[pn] = max(half[pn], t.GetWidth() // 2)
                    joins.append((pn, n))
                    inner.append((u, pn))
                else:
                    inner.append((u, n))
                continue
            d, u = _seg_point(n[0] * 1000, n[1] * 1000, t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y)
            if d <= t.GetWidth() / 2 + half[n] and 0 < u < 1:   # the end's copper touches the segment
                if d > 1000:                           # off the axis: cut the track ON its axis, joined to the end
                    pn = key(P.VECTOR2I(int(t.GetStart().x + u * (t.GetEnd().x - t.GetStart().x)),
                                        int(t.GetStart().y + u * (t.GetEnd().y - t.GetStart().y))), t.GetLayer())
                    if pn not in adj and pn not in projected:
                        projected.append(pn)
                    half[pn] = max(half[pn], t.GetWidth() // 2)
                    joins.append((pn, n))
                    inner.append((u, pn))
                else:
                    inner.append((u, n))
        chain = [(0, a)] + sorted(inner) + [(1, b)]    # consecutive points joined: no detour through the ends
        for (u0, n0), (u1, n1) in zip(chain, chain[1:]) if inner else []:
            link(n0, n1, (u1 - u0) * t.GetLength(), t)
    for pn in projected:                               # every piece stays on its own track's axis: Leg.length and
        adj.setdefault(pn, []); nodes.append(pn)       # Leg.pieces agree, the step between axes is a contact
    for pn, n in joins:
        link(pn, n, 0, "join")
    for v in vias:
        p = v.GetPosition()
        here = [n for n in nodes if v.IsOnLayer(n[2]) and v.FlashLayer(n[2]) and
                math.hypot(n[0] * 1000 - p.x, n[1] * 1000 - p.y) <= v.GetWidth(n[2]) / 2 + half[n]]
        for i, n in enumerate(here):
            for m in here[i + 1:]:
                link(n, m, 0, "join") if n[2] == m[2] else link(n, m, 1, None)   # None = a via (1 nm: a tie
                # between "through the via" and "along the layer" goes along the layer)
    net_pads = defaultdict(list)
    for k, q in pads:
        net_pads[k].append(q)
    on_pad = lambda q, n: q.IsOnLayer(n[2]) and q.HitTest(at(n), half[n], n[2])   # noqa: E731  (shape of that layer)
    for _, q in pads:                                  # a pad crossed by the routing joins the ends on it; a plated
        inside = [n for n in nodes if on_pad(q, n)]    # through pad joins layers like a via (counted as one)
        for i, n in enumerate(inside):
            for m in inside[i + 1:]:
                if n[2] == m[2]:
                    link(n, m, 0, "join")
                elif q.GetAttribute() == P.PAD_ATTRIB_PTH:
                    link(n, m, 1, None)
    term = []
    for e in ends:
        s = {n for n in nodes if any(on_pad(q, n) for q in net_pads[tuple(e)])}   # any pad of that number
        if not s:
            raise ValueError(f"pad {e[0]}.{e[1]} touches no track of {net!r}")
        term.append(s)
    dist, prev, heap = {n: 0 for n in term[0]}, {}, [(0, n) for n in term[0]]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, math.inf):
            continue
        if n in term[1]:
            legs, joined = [], []
            while n in prev:
                m, how, length = prev[n]
                if how is None:                        # a via: the layers of the two nodes it joins
                    joined.append((m[2], n[2]))
                if how is not None and how != "join":
                    whole = {key(how.GetStart(), how.GetLayer()), key(how.GetEnd(), how.GetLayer())} == {m, n}
                    if whole:
                        pieces = track_pieces(how)
                    elif how.GetClass() == "PCB_ARC":      # part of a cut arc: its chords, from m to n (a node
                        u0, u1 = (min(1.0, max(0.0, _arc_u(how, p[0] * 1000, p[1] * 1000)[0])) for p in (m, n))
                        pieces = _arc_part(how, u0, u1)      # rounded just off an end is that end)
                    else:
                        pieces = [(m[0] * 1000, m[1] * 1000, n[0] * 1000, n[1] * 1000)]
                    if whole and key(how.GetStart(), how.GetLayer()) != m:   # stored the other way: follow the path
                        pieces = [(x1, y1, x0, y0) for x0, y0, x1, y1 in reversed(pieces)]
                    legs.append(Leg(how.m_Uuid.AsString(), how.GetLayer(), how.GetWidth(), length, pieces, how))
                n = m
            legs.reverse()
            merged = []                                # two parts of one segment travelled in a row: one leg
            for g in legs:
                if merged and merged[-1].kiid == g.kiid:
                    a = merged[-1]
                    merged[-1] = Leg(a.kiid, a.layer, a.width, a.length + g.length, a.pieces + g.pieces, a.track)
                else:
                    merged.append(g)
            return merged, (joined[::-1] if via_layers else len(joined))
        for m, length, how in adj[n]:
            if d + length < dist.get(m, math.inf):
                dist[m] = d + length; prev[m] = (n, how, length); heapq.heappush(heap, (d + length, m))
    raise ValueError(f"no path between {ends[0]} and {ends[1]} on {net!r}")


def reference_sets(board, layers, adjacent, ac_ref, not_ref, gnd_net="GND"):
    """Copper sets for `reference_at`, built once. layers: routed copper layers; adjacent: {layer: its adjacent
    reference layer}; ac_ref / not_ref: pour nets that are / are not AC references, every pour net in exactly one;
    gnd_net: the ground of the links' domain, all of its copper a reference."""
    from kicad_copper import require_domain
    require_domain(board)
    ac_ref, not_ref = set(ac_ref), set(not_ref)
    zones = list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]
    pours = {z.GetNetname() for z in zones if not z.GetIsRuleArea() and not z.IsTeardropArea() and z.GetNetname()}
    if pours - ac_ref - not_ref or ac_ref & not_ref:
        raise ValueError(f"pour nets to declare in ac_ref or not_ref: {sorted(pours - ac_ref - not_ref)}; "
                         f"in both: {sorted(ac_ref & not_ref)}")
    all_layers = list(board.GetEnabledLayers().CuStack())            # every copper layer: deeper ones too
    items = {l: copper_items(board, l) for l in all_layers}
    ground = {l: merge([c.poly for c in items[l] if c.connected and c.net not in not_ref and
                        (c.net == gnd_net or (c.net in ac_ref and c.kind in ("zone", "graphic")))])
              for l in all_layers}
    keepouts = [z for z in zones if z.GetIsRuleArea() and z.GetDoNotAllowZoneFills()]
    outline = lambda z: z.Outline().CloneDropTriangulation()          # noqa: E731
    cut_all = merge([outline(z) for z in keepouts if all(z.IsOnLayer(l) for l in layers)])
    cut_adj = {lay: merge([outline(z) for z in keepouts if z.IsOnLayer(adj)]) for lay, adj in adjacent.items()}
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    holes = [q for f in board.GetFootprints() for q in f.Pads() if q.HasHole()]
    drills = [t.GetPosition() for t in vias] + [q.GetPosition() for q in holes]
    own = defaultdict(list)
    maxerr = P.FromMM(0.005)
    for t in vias:
        own[t.GetNetname()].append({"c": t.GetPosition(), "r": max(t.GetWidth(l) for l in (P.F_Cu, P.B_Cu)) / 2,
                                    "poly": {l: _disc(t.GetPosition(), t.GetWidth(l), maxerr) for l in (P.F_Cu, P.B_Cu)}})
    for q in holes:
        r = max(max(q.GetSize(l).x, q.GetSize(l).y) for l in (P.F_Cu, P.B_Cu)) / 2
        own[q.GetNetname()].append({"c": q.GetPosition(), "r": r,
                                    "poly": {l: _poly(q, l, maxerr) for l in (P.F_Cu, P.B_Cu)
                                             if q.IsOnLayer(l) and q.FlashLayer(l)}})
    return {"ground": ground, "cut_all": cut_all, "cut_adj": cut_adj, "layers": list(layers),
            "adjacent": dict(adjacent), "drills": drills, "own": dict(own)}


def _in_clearance(ground, pt, max_nm, drills):
    """True if pt lies in a hole of the ground set that holds a drill and is at most max_nm across (a via or pad
    clearance)."""
    for i in range(ground.OutlineCount()):
        o = P.SHAPE_POLY_SET(); o.AddOutline(ground.Outline(i))
        if not o.Contains(pt):
            continue
        for h in range(ground.HoleCount(i)):
            hole = P.SHAPE_POLY_SET(); hole.AddOutline(ground.Hole(i, h))
            if hole.Contains(pt):
                bb = hole.BBox()
                return max(bb.GetWidth(), bb.GetHeight()) <= max_nm and any(hole.Contains(d) for d in drills)
    return False


def _own_entry(ground_adj, pt, own, ring_nm, lay, seg, seg_w=0):
    """True when the track piece `seg` ((x0, y0), (x1, y1)) nm, of width `seg_w`, ends in the copper of one of `own`
    (its net's vias and pad holes), pt lies within ring_nm of that copper, and adjacent ground surrounds its drill."""
    ends = [P.VECTOR2I(int(x), int(y)) for x, y in seg]
    for o in own:
        cu = o["poly"].get(lay)
        if cu is None or not any(cu.Collide(e, int(seg_w / 2) + 10_000) for e in ends):
            continue
        if cu.Collide(pt, int(ring_nm)) and ground_adj.Collide(o["c"], int(o["r"] + ring_nm)):
            return True
    return False


def reference_at(board, x, y, lay, sets, deeper, clearance_nm=3_000_000, net=None, seg=None, seg_w=0,
                 own_ring_nm=OWN_RING_NM):
    """Reference of a sample point (nm) of a track on layer `lay`: ("plane", None), ("far", name of the first deeper
    layer with ground there) or ("none", None); a drilled clearance at most clearance_nm across counts as plane, and
    so, given `net` and the sampled piece `seg`, does the track's entry into its own via or pad. deeper: {layer:
    [farther layers, nearest first]}."""
    pt = P.VECTOR2I(int(x), int(y))
    ground, adj = sets["ground"], sets["adjacent"][lay]
    in_cut = sets["cut_adj"][lay].Contains(pt)
    if not in_cut and (ground[adj].Contains(pt) or _in_clearance(ground[adj], pt, clearance_nm, sets["drills"])
                       or (net is not None and seg is not None
                           and _own_entry(ground[adj], pt, sets["own"].get(net, []), own_ring_nm, lay, seg, seg_w))):
        return "plane", None
    if sets["cut_all"].Contains(pt) and not any(ground[l].Contains(pt) for l in ground if l != lay):
        return "none", None
    for l in deeper.get(lay, []):
        if ground[l].Contains(pt) or _in_clearance(ground[l], pt, clearance_nm, sets["drills"]):
            return "far", board.GetLayerName(l)
    return "none", None
