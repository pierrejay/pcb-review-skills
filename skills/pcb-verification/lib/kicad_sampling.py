"""Sampling of one controlled-impedance link of a KiCad board, read with pcbnew (KiCad's bundled Python; nm inside,
mm in what it returns): cross-section keys and lengths along the signal path (`sample_link`), the reference situation
of a point, the pads of a net."""
import math
from collections import defaultdict

import pcbnew as P

from impedance_keys import (FAR_COUPLE_MM, FAR_PAIR_STEP_MM, FAR_SIDE_STEP_MM, SIDE_REACH_MM, SIDE_STEP_MM,
                            coarsen_far, make_key, reach_mm, round_gap_off_plane, round_s, runs)
from kicad_routing import _arc_part, _arc_u, pad_path, reference_at, track_pieces

MM = 1e6
STEP_MM = 0.1
BAND_WIDTHS = 3            # unreferenced test: the normal segment, ±3 track widths (return current spreads over ~3 h)
TILE_NM = 5_000_000        # band test: the ground is cut once per window of a 5 mm grid (speed only, same result)
BALANCE = 0.02             # sampled length against path length
COPPER_BALANCE = 0.001     # path + branches against the net's tracks (relative)…
COPPER_BALANCE_MM = 0.01   # …or absolute, whichever is larger
SNAP_NM = 1500             # a leg end read back within this of a track end is that end (nodes sit on a 1 µm grid)


def _seg_near(px, py, x0, y0, x1, y1):
    """Distance from (px, py) to segment and the nearest point on it (nm)."""
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy
    u = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / l2))
    qx, qy = x0 + u * dx, y0 + u * dy
    return math.hypot(px - qx, py - qy), qx, qy


def _walk(x, y, nx, ny, half_nm, poly, reach_mm=SIDE_REACH_MM, step_mm=SIDE_STEP_MM):
    """Track edge → first copper of `poly` along (nx, ny): middle of the step that found it (mm), None beyond reach."""
    for k in range(1, int(round(reach_mm / step_mm)) + 1):
        d = half_nm + k * step_mm * MM
        if poly.Contains(P.VECTOR2I(int(x + nx * d), int(y + ny * d))):
            return round((k - 0.5) * step_mm, 3)
    return None


def _rect(x0, y0, x1, y1):
    c = P.SHAPE_LINE_CHAIN()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        c.Append(int(x), int(y))
    c.SetClosed(True)
    sp = P.SHAPE_POLY_SET()
    sp.AddOutline(c)
    return sp


def _band_gaps(piece, nx, ny, half_nm, ground, tiles, tag):
    """The reference copper missing (`ground` subtracted) in the band swept by the normal (nx, ny) of a straight piece,
    ±half_nm; `tiles` caches the ground cut per TILE_NM window."""
    x0, y0, x1, y1 = piece
    corners = [(int(round(x + s * nx * half_nm)), int(round(y + s * ny * half_nm)))
               for x, y, s in ((x0, y0, 1), (x1, y1, 1), (x1, y1, -1), (x0, y0, -1))]
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    win = (math.floor(min(xs) / TILE_NM), math.floor(min(ys) / TILE_NM), math.floor(max(xs) / TILE_NM) + 1,
           math.floor(max(ys) / TILE_NM) + 1)
    local = tiles.get((tag, win))
    if local is None:
        local = tiles[(tag, win)] = _rect(*(k * TILE_NM for k in win))
        local.BooleanIntersection(ground)
    c = P.SHAPE_LINE_CHAIN()
    for x, y in corners:
        c.Append(x, y)
    c.SetClosed(True)
    band = P.SHAPE_POLY_SET()
    band.AddOutline(c)
    band.BooleanSubtract(local)
    return band


def situation_at(board, x, y, lay, sets, deeper, net=None, seg=None, seg_w=0):
    """Reference situation of a point (nm) on layer `lay`, read from the copper (`kicad_routing.reference_at`):
    ("plane", None), ("far", reference layer name) or ("cutout", None)."""
    ref, far_name = reference_at(board, x, y, lay, sets, deeper, net=net, seg=seg, seg_w=seg_w)
    if ref == "plane":
        return "plane", None
    if ref == "far":
        return "far", far_name
    if ref == "none":
        return "cutout", None


def declared_at(sets, x, y, lay):
    """True when the point (nm) lies inside a pour keep-out of the adjacent layer of `lay` (a declared absence of
    plane)."""
    return bool(sets["cut_adj"][lay].Contains(P.VECTOR2I(int(x), int(y))))


def _pieces_by_layer(tracks):
    out = defaultdict(list)
    for t in tracks:
        for x0, y0, x1, y1 in track_pieces(t):
            out[t.GetLayer()].append((x0, y0, x1, y1, t.GetWidth()))
    return out


def _arc_pos(t, x, y):
    """Position u ∈ [0, 1] along the arc `t` of a point lying on it, snapped to an end within SNAP_NM."""
    u = _arc_u(t, x, y)[0]
    return _snap(min(1.0, max(0.0, u)), t.GetLength())


def _snap(u, length):
    """u ∈ [0, 1] along a track of `length` nm, set to 0 or 1 when it is within SNAP_NM of that end."""
    if u * length <= SNAP_NM:
        return 0.0
    if (1 - u) * length <= SNAP_NM:
        return 1.0
    return u


def _branch_pieces(tracks, legs):
    """([(layer, (x0, y0, x1, y1))] nm, untravelled length nm): the copper of `tracks` outside the intervals the legs
    travel; intervals shorter than SNAP_NM are node rounding."""
    done = defaultdict(list)                      # kiid → travelled intervals [u0, u1] along the track
    for g in legs:
        t = g.track
        if t.GetClass() == "PCB_ARC":             # a whole arc or the part of it between two nodes, in either direction
            us = (_arc_pos(t, g.pieces[0][0], g.pieces[0][1]), _arc_pos(t, g.pieces[-1][2], g.pieces[-1][3]))
            done[g.kiid].append((min(us), max(us)))
            continue
        ax, ay, bx, by = t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        for x0, y0, x1, y1 in g.pieces:
            u = sorted(((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2 if L2 else 0.0 for x, y in ((x0, y0), (x1, y1)))
            done[g.kiid].append((_snap(max(0.0, u[0]), t.GetLength()), _snap(min(1.0, u[1]), t.GetLength())))
    out, left = [], 0.0
    for t in tracks:
        iv = sorted(done.get(t.m_Uuid.AsString(), []))
        length, arc = t.GetLength(), t.GetClass() == "PCB_ARC"
        ax, ay, bx, by = t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y
        at = 0.0
        for u0, u1 in iv + [(1.0, 1.0)]:
            if (u0 - at) * length > SNAP_NM:      # an untravelled interval of this track
                left += (u0 - at) * length
                if arc:
                    out += [(t.GetLayer(), pc) for pc in _arc_part(t, at, u0)]
                else:
                    out.append((t.GetLayer(), (ax + (bx - ax) * at, ay + (by - ay) * at,
                                               ax + (bx - ax) * u0, ay + (by - ay) * u0)))
            at = max(at, u1)
    return out, left


def sample_link(board, net, sets, deeper, h_prepreg_mm, partner=None, ends=None, step_mm=STEP_MM, h_max_mm=None):
    """Sample one net of a link. sets: `kicad_routing.reference_sets`; deeper: {layer: [farther layers, nearest
    first]}; h_prepreg_mm: prepreg under the outer layers; h_max_mm: the thickest prepreg among the builds judged
    (default h_prepreg_mm); partner: the other net of a pair, None for a single line; ends: ((ref, pad), (ref, pad)),
    required unless the net has two pads or one track.
    Returns {"total_mm", "unreferenced_mm", "cutout_mm", "far_mm", "undeclared_mm", "branch_mm",
    "branch_by_situation_mm", "arc_mm", "skipped_mm" {layer name: mm not handled}, "path_vias", "bins" {key: mm},
    "points" [[x_mm, y_mm, length_mm, key]] in path order, "unreferenced_runs" [{"mm", "x", "y", "span": [first,
    last point index]}], "h_prepreg_mm", "h_max_mm"}.
    """
    layers = list(sets["layers"])
    adjacent = sets["adjacent"]
    ground = sets["ground"]
    tracks = [t for t in board.GetTracks() if t.GetNetname() == net and t.GetClass() in ("PCB_TRACK", "PCB_ARC")]
    partner_pieces = {}
    if partner is not None:
        ptracks = [t for t in board.GetTracks() if t.GetNetname() == partner and t.GetClass() in ("PCB_TRACK", "PCB_ARC")]
        if not ptracks:
            raise ValueError(f"partner net {partner!r} has no track on the board")
        partner_pieces = _pieces_by_layer(ptracks)
    arc_mm = sum(t.GetLength() for t in tracks if t.GetClass() == "PCB_ARC") / MM
    path_vias = None
    if ends is None:                             # the order of the points must be the order along the line
        pads = [(f.GetReference(), q.GetNumber()) for f in board.GetFootprints() for q in f.Pads()
                if q.GetNetname() == net]
        if len(pads) != 2 and len(tracks) > 1:
            raise ValueError(f"net {net!r}: {len(tracks)} tracks and {len(pads)} pads; name the two ends of the "
                             "signal path (ends=...): the line cannot be ordered otherwise")
        ends = tuple(pads) if len(pads) == 2 else None
    if ends is not None:
        legs, path_vias = pad_path(board, net, ends)
        path = [(g.layer, g.width, pc) for g in legs for pc in g.pieces]     # in the direction of travel
        expected = sum(g.length for g in legs if g.layer in layers)
        branch, left = _branch_pieces(tracks, legs)   # the copper of the net that the path does not travel
        copper, travelled = sum(t.GetLength() for t in tracks), sum(g.length for g in legs)
        if abs(copper - travelled - left) > max(COPPER_BALANCE_MM * MM, COPPER_BALANCE * copper):
            raise ValueError(f"net {net!r}: {copper / MM:.3f} mm of tracks for {travelled / MM:.3f} mm of path + "
                             f"{left / MM:.3f} mm of branches: copper lost between path and branches, or counted twice")
    else:
        path = [(t.GetLayer(), t.GetWidth(), pc) for t in tracks for pc in track_pieces(t)]
        expected = sum(t.GetLength() for t in tracks if t.GetLayer() in layers)
        branch = []
    branch_mm = sum(math.hypot(x1 - x0, y1 - y0) for _, (x0, y0, x1, y1) in branch) / MM

    if h_max_mm is not None and float(h_max_mm) < float(h_prepreg_mm):
        raise ValueError(f"h_max_mm {h_max_mm} is below h_prepreg_mm {h_prepreg_mm}: give the thickest prepreg")
    couple_lim, side_reach = reach_mm(h_prepreg_mm if h_max_mm is None else h_max_mm)

    def side_gap(x, y, nx, ny, half, lay, situation):
        g1 = _walk(x, y, nx, ny, half, ground[lay], reach_mm=side_reach)
        if situation == "plane":
            return coarsen_far(g1, h_prepreg_mm, FAR_SIDE_STEP_MM)
        g2 = _walk(x, y, nx, ny, half, ground[adjacent[lay]], reach_mm=side_reach)
        if g2 is not None:
            g2 = math.hypot(g2, h_prepreg_mm)
        if g1 is None and g2 is None:
            return None
        return round_gap_off_plane(min(v for v in (g1, g2) if v is not None), reach_mm=side_reach)

    bins, points, unref_ids, tiles = defaultdict(float), [], set(), {}
    total = unref = cutout = far = 0.0
    skipped, undeclared = defaultdict(float), defaultdict(float)
    for lay, w, (x0, y0, x1, y1) in path:
        L = math.hypot(x1 - x0, y1 - y0)
        if L == 0:
            continue
        if lay not in layers:
            skipped[board.GetLayerName(lay)] += L / MM
            continue
        name = board.GetLayerName(lay)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -uy, ux                                   # left normal
        n = max(1, int(L / (step_mm * MM)))
        dl = L / n / MM
        band, gaps = BAND_WIDTHS * w, None                 # gaps: reference copper missing in the band of this piece
        for k in range(n):
            x, y = x0 + (x1 - x0) * (k + 0.5) / n, y0 + (y1 - y0) * (k + 0.5) / n
            total += dl
            situation, ref_name = situation_at(board, x, y, lay, sets, deeper, net=net, seg=((x0, y0), (x1, y1)),
                                               seg_w=w)
            if situation == "plane":
                if gaps is None:
                    gaps = _band_gaps((x0, y0, x1, y1), nx, ny, band, ground[adjacent[lay]], tiles, adjacent[lay])
                seg = P.SEG(P.VECTOR2I(int(x - nx * band), int(y - ny * band)),
                            P.VECTOR2I(int(x + nx * band), int(y + ny * band)))
                if gaps.OutlineCount() and gaps.Collide(seg):
                    unref += dl
                    unref_ids.add(len(points))
            cutout += dl if situation == "cutout" else 0.0
            far += dl if situation == "far" else 0.0
            if situation != "plane" and not declared_at(sets, x, y, lay):
                undeclared[situation] += dl
            key = None
            if partner_pieces.get(lay):
                best = min(((_seg_near(x, y, *q[:4]), q[4]) for q in partner_pieces[lay]), key=lambda r: r[0][0])
                (d, qx, qy), wq = best
                s = (d - w / 2 - wq / 2) / MM
                limit = max(FAR_COUPLE_MM, couple_lim) if situation == "far" else couple_lim
                if s < limit or situation == "cutout":
                    side = 1 if (qx - x) * nx + (qy - y) * ny > 0 else -1     # partner on the left (+1) or right
                    g_self = side_gap(x, y, -side * nx, -side * ny, w / 2, lay, situation)
                    g_part = side_gap(qx, qy, side * nx, side * ny, wq / 2, lay, situation)
                    s_key = round_s(s, situation)
                    if situation == "plane":
                        s_key = coarsen_far(s_key, h_prepreg_mm, FAR_PAIR_STEP_MM)
                    key = make_key(situation, name, w / MM, (g_self, g_part), partner=(wq / MM, s_key),
                                   ref_layer=ref_name)
            if key is None:
                gl = side_gap(x, y, nx, ny, w / 2, lay, situation)
                gr = side_gap(x, y, -nx, -ny, w / 2, lay, situation)
                key = make_key(situation, name, w / MM, (gl, gr), ref_layer=ref_name)
            bins[key] += dl
            points.append([round(x / MM, 3), round(y / MM, 3), round(dl, 4), key])
    flagged = {id(points[i]) for i in unref_ids}
    index = {id(q): i for i, q in enumerate(points)}
    if total == 0:
        raise ValueError(f"net {net!r}: no sampled length" + (f"; tracks on layers not handled: "
                         f"{ {k: round(v, 3) for k, v in skipped.items()} }" if skipped else ""))
    if abs(total - expected / MM) > BALANCE * max(expected / MM, 1.0):
        raise ValueError(f"net {net!r}: {total:.3f} mm sampled for {expected / MM:.3f} mm of path tracks")
    by_situation = defaultdict(float)
    for lay, (x0, y0, x1, y1) in branch:
        if lay not in layers:
            by_situation["layer not handled"] += math.hypot(x1 - x0, y1 - y0) / MM
            continue
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L / (step_mm * MM)))
        for k in range(n):
            sit, _ = situation_at(board, x0 + (x1 - x0) * (k + 0.5) / n, y0 + (y1 - y0) * (k + 0.5) / n,
                                  lay, sets, deeper, net=net, seg=((x0, y0), (x1, y1)))
            by_situation[sit] += L / n / MM
    return {"total_mm": round(total, 3), "unreferenced_mm": round(unref, 3), "cutout_mm": round(cutout, 3),
            "far_mm": round(far, 3), "undeclared_mm": {k: round(v, 3) for k, v in sorted(undeclared.items())},
            "branch_mm": round(branch_mm, 3),
            "branch_by_situation_mm": {k: round(v, 3) for k, v in sorted(by_situation.items())},
            "arc_mm": round(arc_mm, 3), "skipped_mm": {k: round(v, 3) for k, v in sorted(skipped.items())},
            "path_vias": path_vias, "bins": {k: round(v, 3) for k, v in bins.items()}, "points": points,
            "unreferenced_runs": [{"mm": r["mm"], "x": r["x"], "y": r["y"],
                                   "span": [index[id(r["pts"][0])], index[id(r["pts"][-1])]]}
                                  for r in runs(points, lambda q: id(q) in flagged, heal_mm=0.0)],
            "h_prepreg_mm": round(float(h_prepreg_mm), 4),
            "h_max_mm": round(float(h_prepreg_mm if h_max_mm is None else h_max_mm), 4)}


def net_pads(board, net, sets, deeper):
    """Pads of a net with their size and the reference situation under their centre: [{"pad": "C50.1", "w_mm", "l_mm",
    "through_hole", "situation"}] sorted by name, situation None on a layer not handled."""
    out = []
    layers = sets["layers"]
    for f in board.GetFootprints():
        for q in f.Pads():
            if q.GetNetname() != net:
                continue
            lay = next((l for l in layers if q.IsOnLayer(l)), None)
            sz = q.GetSize(lay if lay is not None else P.F_Cu)
            sit = situation_at(board, q.GetPosition().x, q.GetPosition().y, lay, sets, deeper)[0] if lay is not None else None
            out.append({"pad": f"{f.GetReference()}.{q.GetNumber()}", "w_mm": round(min(sz.x, sz.y) / MM, 3),
                        "l_mm": round(max(sz.x, sz.y) / MM, 3), "through_hole": q.GetAttribute() == P.PAD_ATTRIB_PTH,
                        "situation": sit})
    if not out:
        raise ValueError(f"net {net!r} has no pad on the board")
    return sorted(out, key=lambda d: d["pad"])
