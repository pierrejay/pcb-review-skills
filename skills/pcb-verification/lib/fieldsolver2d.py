"""Quasi-static 2D field solver (finite volumes; mm, venv) for a single or coupled microstrip over a plane or a plane
cutout: trapezoidal tracks under solder mask, optional coplanar grounds, one or two dielectrics. Grid lines fall on
every edge inside the fine zone only: outside that zone (the bottom of a slab without a plane) check convergence."""
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

EPS0 = 8.8541878128e-12
EDGE_TOL = 1e-12    # mm: a node within EDGE_TOL of a conductor's edge belongs to it (masks and contact refusals)
C0 = 299792458.0


@dataclass
class Geometry:
    h: float                 # dielectric track -> plane (mm)
    er: float                # permittivity of the dielectric
    w: float                 # width at the base (mm)
    t: float = 0.035         # copper thickness (mm)
    s: float = 0.0           # edge-to-edge gap at the base (0 = single track)
    w_top: float = None      # width at the top (default: = w)
    c1: float = 0.0          # solder mask on substrate (mm)
    c2: float = 0.0          # solder mask on copper (mm)
    er_mask: float = 3.8
    plane: bool = True       # ground plane under the dielectric; False = air under the slab
    er_core: float = None    # permittivity under the prepreg (None = single dielectric)
    h_top: float = 0.0       # prepreg thickness (permittivity er) when er_core is given (mm)
    side_gap: float = None   # coplanar ground at this edge-to-edge distance (mm), on the track layer
    side_w: float = 1.0      # width of each coplanar ground strip (mm)
    side_gap2: float = None  # right side (x > 0) if it differs; None = same value as side_gap, 0 = no ground
    side_left: bool = True   # False: no coplanar ground on the left (right side only, with side_gap2)
    extra: dict = field(default_factory=dict)

    def side_gaps(self):
        """Gap of the coplanar ground on the left and right (None = absent)."""
        left = self.side_gap if self.side_left else None
        right = self.side_gap2 if self.side_gap2 is not None else self.side_gap
        return {-1: left, 1: right}

    def traces(self):
        wt = self.w if self.w_top is None else self.w_top
        if self.s <= 0:
            return [(0.0, self.w, wt)]
        xc = (self.w + self.s) / 2
        return [(-xc, self.w, wt), (xc, self.w, wt)]


def _axis(fine_lo, fine_hi, d_fine, far_lo, far_hi, growth=1.12, breaks=()):
    """Fine axis over [fine_lo, fine_hi] with a grid line on every edge of `breaks` inside it (each interval split
    into equal steps of at most d_fine), geometric progression towards far_lo/far_hi. Without the lines on the edges,
    the width, the gap and the dielectric interfaces snap to the nearest node, differently at each step, and the
    impedance oscillates by about 1 % as the mesh is refined instead of converging."""
    pts = sorted({fine_lo, fine_hi, *[b for b in breaks if fine_lo < b < fine_hi]})
    core = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.ceil((b - a) / d_fine - 1e-9)))
        core.extend(np.linspace(a, b, n + 1)[1:])
    core = np.array(core)
    hi, d = [core[-1]], d_fine
    while hi[-1] < far_hi:
        d *= growth
        hi.append(hi[-1] + d)
    lo, d = [core[0]], d_fine
    while lo[-1] > far_lo:
        d *= growth
        lo.append(lo[-1] - d)
    return np.unique(np.concatenate([lo[::-1], core, hi]))


def _inside_trace(x, y, g, tr):
    xc, wb, wt = tr
    frac = np.clip((y - g.h) / g.t, 0, 1)
    half = wb / 2 - frac * (wb - wt) / 2
    return (y >= g.h - EDGE_TOL) & (y <= g.h + g.t + EDGE_TOL) & (np.abs(x - xc) <= half + EDGE_TOL)


def _in_mask(x, y, g):
    if g.c1 <= 0 and g.c2 <= 0:
        return np.zeros_like(x, dtype=bool)
    m = (y >= g.h) & (y <= g.h + g.c1)
    for xc, wb, wt in g.traces():
        # trapezoid envelope dilated by c2 (approximation by horizontal/vertical distance)
        frac = np.clip((y - g.h) / g.t, 0, 1)
        half = wb / 2 - frac * (wb - wt) / 2
        m |= (y >= g.h) & (y <= g.h + g.t + g.c2) & (np.abs(x - xc) <= half + g.c2)
    return m


def _check(g, d_fine=None):
    """Refuse a geometry the grid would misread: with er_core, a prepreg h_top outside ]0, h[; conductors that touch."""
    if g.er_core is not None and not 0 < g.h_top < g.h:
        raise ValueError(f"h_top must lie in ]0, h[ = ]0, {g.h}[ mm with er_core, got {g.h_top!r}")
    # a top wider than the base reaches past the base edges, where the other trace and the side grounds are placed
    over = (g.w if g.w_top is None else g.w_top) - g.w
    if g.s > 0 and over >= g.s - 2 * EDGE_TOL:
        raise ValueError(f"the two traces touch or overlap: top width {g.w + over} mm ≥ w + s = {g.w + g.s} mm "
                         f"(within {2 * EDGE_TOL} mm, the masks' tolerance)")
    for side, gap in g.side_gaps().items():
        if gap and over / 2 >= gap - 2 * EDGE_TOL:
            raise ValueError(f"a trace and its {'left' if side < 0 else 'right'} side ground touch or overlap: the "
                             f"top passes the base edge by {over / 2} mm ≥ side gap {gap} mm")


def default_step(g: Geometry):
    """The fine mesh step `solve` uses when none is given (mm): min(ref, max(w, s, 0.05)) / 80, ref = h over a
    plane, max(w, s, 0.05) without one."""
    ref = g.h if g.plane else max(g.w, g.s, 0.05)
    return min(ref, max(g.w, g.s, 0.05)) / 80


def solve(g: Geometry, d_fine=None):
    """Per-unit-length solution of `g`, fine mesh step d_fine (mm) near the tracks (default `default_step`): {"nodes"}
    and, for a single track (s = 0), "z0" (Ω), "er_eff", "c_pf_per_mm"; for a pair, "z_even", "z_odd", "er_eff_even",
    "er_eff_odd", "c_even_pf_per_mm", "c_odd_pf_per_mm" (per track), "zdiff" = 2 × z_odd, "cdiff_pf_per_mm" =
    c_odd / 2. Without a plane only the odd (differential) mode is meaningful."""
    _check(g, d_fine)
    ref = g.h if g.plane else max(g.w, g.s, 0.05)  # field scale near the tracks
    # fine mesh matched to the smallest scale (dielectric or track/gap)
    d_fine = d_fine or default_step(g)
    tr = g.traces()
    xmax_tr = max(abs(xc) + wb / 2 for xc, wb, _ in tr)
    gaps = [v for v in g.side_gaps().values() if v]
    x_fine = xmax_tr + (max(gaps) + g.side_w if gaps else 0) + ref
    far = 30 * g.h + 2 * x_fine
    xb = [e for xc, wb, wt in tr for e in (xc - wb / 2, xc + wb / 2, xc - wt / 2, xc + wt / 2)]
    xb += [sgn * (xmax_tr + gap + w) for sgn, gap in g.side_gaps().items() if gap for w in (0.0, g.side_w)]
    x = _axis(-x_fine, x_fine, d_fine, -far, far, breaks=xb)
    top = g.h + g.t + max(g.c1, g.c2)
    yb = [0.0, g.h, g.h + g.t, g.h + g.c1, g.h + g.t + g.c2] + ([g.h - g.h_top] if g.er_core is not None else [])
    if g.plane:
        y = _axis(0.0, top + 0.5 * ref, d_fine, 0.0, 25 * g.h + g.t, breaks=yb)
        y = y[y >= 0]
    else:
        y = _axis(g.h - ref, top + 0.5 * ref, d_fine, -far, far, breaks=yb)
    nx, ny = len(x), len(y)
    X, Y = np.meshgrid(x, y, indexing="ij")

    # permittivity per cell (centre)
    xc_ = (x[:-1] + x[1:]) / 2
    yc_ = (y[:-1] + y[1:]) / 2
    XC, YC = np.meshgrid(xc_, yc_, indexing="ij")

    def cell_eps(with_dielectric):
        e = np.ones(XC.shape)
        if with_dielectric:
            e[(YC < g.h) & (YC >= 0)] = g.er
            if g.er_core is not None:
                e[(YC < g.h - g.h_top) & (YC >= 0)] = g.er_core
            e[_in_mask(XC, YC, g) & (YC >= g.h)] = g.er_mask
        return e

    dx, dy = np.diff(x), np.diff(y)
    idx = np.arange(nx * ny).reshape(nx, ny)

    cond = np.zeros((nx, ny), dtype=int)  # 0 = free, k = conductor k
    for k, t_ in enumerate(tr, start=1):
        cond[_inside_trace(X, Y, g, t_)] = k
    for sgn, gap in g.side_gaps().items():  # coplanar ground strips, potential 0
        if gap:
            xc = sgn * (xmax_tr + gap + g.side_w / 2)
            cond[_inside_trace(X, Y, g, (xc, g.side_w, g.side_w))] = -1
    boundary = np.zeros((nx, ny), dtype=bool)
    boundary[0, :] = boundary[-1, :] = True
    boundary[:, 0] = boundary[:, -1] = True  # y = 0 ground plane, shielded sides and top

    def assemble(eps):
        # horizontal (i,j)-(i+1,j) and vertical (i,j)-(i,j+1) conductances
        ep = np.pad(eps, ((0, 0), (1, 1)), mode="edge")
        dyp = np.concatenate([[0], dy, [0]])
        gx = (ep[:, :-1] * dyp[:-1] / 2 + ep[:, 1:] * dyp[1:] / 2) / dx[:, None]
        ep = np.pad(eps, ((1, 1), (0, 0)), mode="edge")
        dxp = np.concatenate([[0], dx, [0]])
        gy = (ep[:-1, :] * dxp[:-1, None] / 2 + ep[1:, :] * dxp[1:, None] / 2) / dy[None, :]
        rows = np.concatenate([idx[:-1, :].ravel(), idx[:, :-1].ravel()])
        cols = np.concatenate([idx[1:, :].ravel(), idx[:, 1:].ravel()])
        vals = np.concatenate([gx.ravel(), gy.ravel()])
        n = nx * ny
        off = sp.coo_matrix((-vals, (rows, cols)), shape=(n, n))
        off = off + off.T
        diag = -np.asarray(off.sum(axis=1)).ravel()
        return (off + sp.diags(diag)).tocsr()

    fixed = (cond != 0) | boundary
    free = ~fixed.ravel()

    def energy(K, volts):
        phi = np.zeros(nx * ny)
        for k, v in enumerate(volts, start=1):
            phi[(cond == k).ravel()] = v
        Kff = K[free][:, free]
        rhs = -K[free][:, ~free] @ phi[~free]
        phi[free] = spla.spsolve(Kff.tocsc(), rhs)
        return phi @ (K @ phi)  # = sum G (dphi)^2, without eps0

    K = assemble(cell_eps(True))
    K0 = assemble(cell_eps(False))
    out = {"nodes": nx * ny}
    if len(tr) == 1:
        c, c0 = EPS0 * energy(K, [1]), EPS0 * energy(K0, [1])
        out.update(z0=1 / (C0 * np.sqrt(c * c0)), er_eff=c / c0, c_pf_per_mm=c * 1e9)
    else:
        for mode, v in (("even", [1, 1]), ("odd", [1, -1])):
            c = EPS0 * energy(K, v) / 2
            c0 = EPS0 * energy(K0, v) / 2
            out[f"z_{mode}"] = 1 / (C0 * np.sqrt(c * c0))
            out[f"er_eff_{mode}"] = c / c0
            out[f"c_{mode}_pf_per_mm"] = c * 1e9  # per track
        out["zdiff"] = 2 * out["z_odd"]
        out["cdiff_pf_per_mm"] = out["c_odd_pf_per_mm"] / 2  # seen between P and N
    return out


if __name__ == "__main__":
    import sys
    # example geometry (one four-layer build): a coupled pair over a plane, 0.0994 mm of dielectric; fine mesh step
    # in mm from the command line (default 0.002)
    g = Geometry(h=0.0994, er=4.1, w=0.1321, s=0.14)
    print(solve(g, d_fine=float(sys.argv[1]) if len(sys.argv) > 1 else 0.002))
