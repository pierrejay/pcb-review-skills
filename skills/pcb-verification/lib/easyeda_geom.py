"""Geometry of EasyEDA Pro paths and stored fills: `path_points` (a path to points, arcs cut into chords) and
`fill_geometry` (the rings of one fill as a shapely geometry, even-odd rule)."""
import math

from shapely.geometry import Polygon


def _num(p, i, n):
    if i + n > len(p):                               # a truncated path would silently lose its last segment
        raise ValueError(f"path truncated at element {i}: {n} number(s) expected")
    return p[i:i + n]


def path_points(p, k, max_sagitta=1e-3):
    """EasyEDA Pro path [x0, y0, 'L', x, y, ..., 'ARC', angle_deg, x, y, ...] -> points, coordinates × k. ARC
    carries the SIGNED included angle then the end point; each arc is cut into chords of sagitta ≤ max_sagitta (output
    units), on the centre side of the arc. Full circles are not supported."""
    x0, y0 = _num(p, 0, 2)
    pts = [(x0 * k, y0 * k)]
    i, mode = 2, None
    while i < len(p):
        if isinstance(p[i], str):
            mode = p[i]
            i += 1
            _num(p, i, 2 if mode == "L" else 3)      # a command is followed by its first operands, never by the end
        elif mode == "L":
            x, y = _num(p, i, 2)
            pts.append((x * k, y * k))
            i += 2
        elif mode == "ARC":                          # signed included angle, then the end point
            ang, x, y = _num(p, i, 3)
            x, y = x * k, y * k
            i += 3
            x0, y0 = pts[-1]
            a = math.radians(ang)
            d = math.dist((x0, y0), (x, y))
            if abs(a) < 1e-9:
                pts.append((x, y))
                continue
            if d < 1e-9 or abs(ang) >= 360:          # a full circle has no chord to place its centre on
                raise ValueError(f"arc of {ang}° from a point to itself: full circles are not supported")
            r = d / 2 / math.sin(abs(a) / 2)
            h = d / 2 / math.tan(abs(a) / 2)         # signed: negative beyond 180°, the centre changes side
            s = 1 if a > 0 else -1
            ux, uy = (x - x0) / d, (y - y0) / d
            cx, cy = (x0 + x) / 2 - s * h * uy, (y0 + y) / 2 + s * h * ux
            a0 = math.atan2(y0 - cy, x0 - cx)
            half = math.acos(max(-1.0, 1 - max_sagitta / r))      # half-angle of the longest chord allowed
            n = max(1, math.ceil(abs(a) / (2 * half)))
            if r * (1 - math.cos(abs(a) / (2 * n))) > max_sagitta:  # rounding at the boundary: one more chord
                n += 1
            steps = [a0 + a * j / n for j in range(1, n + 1)]
            pts += [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in steps]
            if math.dist(pts[-1], (x, y)) >= 1e-6 * max(r, 1.0):       # not an assert: python -O drops those
                raise ValueError(f"arc of {ang}° does not land on its end point")
            pts[-1] = (x, y)
        else:                                        # a number with no command before it: malformed path
            raise ValueError(f"path element {i} ({p[i]!r}) follows no L or ARC command")
    return pts


def fill_geometry(rings, k, max_sagitta=1e-3):
    """Rings of one stored fill combined with the even-odd rule (outline, then holes), arcs as in `path_points`. A ring
    that crosses itself raises ValueError."""
    g = None
    for n, ring in enumerate(rings):
        q = Polygon(path_points(ring, k, max_sagitta))
        if not q.is_valid:                           # buffer(0) would silently drop a lobe
            raise ValueError(f"ring {n} crosses itself: not a simple polygon")
        g = q if g is None else g.symmetric_difference(q)
    return g
