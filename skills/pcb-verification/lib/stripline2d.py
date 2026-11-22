"""Quasi-static 2D solver (finite volumes; mm) for one or two traces on an inner layer between two planes, one
dielectric under the trace and one around it: impedance and propagation delay. Run with the venv.
"""
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

EPS0 = 8.8541878128e-12
C0 = 299792458.0
TOL = 1e-9          # mm: a node within TOL of a conductor's edge belongs to it (masks and contact refusals alike)


@dataclass
class Stripline:
    """Lower plane, dielectric h1 (er1) up to the base of the trace, upper plane at h1 + h2: h2 counts from the BASE of
    the trace (copper t plus the dielectric above it), in er2. s > 0 makes a pair; side_gap: coplanar ground."""
    h1: float
    er1: float
    h2: float
    er2: float
    w: float
    t: float = 0.0152
    s: float = 0.0
    w_top: float = None
    side_gap: float = None

    def traces(self):
        wt = self.w if self.w_top is None else self.w_top
        if self.s <= 0:
            return [(0.0, self.w, wt)]
        xc = (self.w + self.s) / 2
        return [(-xc, self.w, wt), (xc, self.w, wt)]


def _axis(core_lo, core_hi, d, lo, hi, growth=1.15):
    core = np.arange(core_lo, core_hi + d / 2, d)
    a, b = [core[0]], [core[-1]]
    st = d
    while a[-1] > lo or b[-1] < hi:
        st *= growth
        if a[-1] > lo:
            a.append(max(a[-1] - st, lo))
        if b[-1] < hi:
            b.append(min(b[-1] + st, hi))
    return np.unique(np.round(np.r_[a[::-1], core, b], 7))


def _axis_y(pts, d):
    """y axis through exactly `pts`, with a step of about d."""
    out = {0.0}
    for a, b in zip(pts, pts[1:]):
        n = 1
        L = b - a
        if L <= 2 * d:
            for k in range(1, max(2, int(round(L / d)))):
                out.add(round(a + L * k / max(2, int(round(L / d))), 7))
        else:
            n = max(4, int(np.ceil(L / d)))
            for k in range(1, n):
                out.add(round(a + L * k / n, 7))
    out |= {round(p, 7) for p in pts}
    return np.array(sorted(out))


def _capacitance(g, x, y, uni, signs, with_dielectric):
    nx, ny = len(x), len(y)
    idx = lambda i, j: i * ny + j  # noqa: E731
    H = g.h1 + g.h2
    fixed = np.zeros((nx, ny), bool)
    potential = np.zeros((nx, ny))
    fixed[:, 0] = fixed[:, -1] = True
    fixed[0, :] = fixed[-1, :] = True
    for (xc, w, wt), sign in zip(g.traces(), signs):
        for j, yy in enumerate(y):
            if g.h1 - TOL <= yy <= g.h1 + g.t + TOL:
                f = (yy - g.h1) / g.t if g.t > 0 else 0
                hw = (w + (wt - w) * f) / 2
                m = np.abs(x - xc) <= hw + TOL
                fixed[m, j] = True
                potential[m, j] = sign
    if g.side_gap is not None:
        edge = abs(g.traces()[-1][0]) + g.w / 2 + g.side_gap
        for j, yy in enumerate(y):
            if g.h1 - TOL <= yy <= g.h1 + g.t + TOL:
                m = np.abs(x) >= edge
                fixed[m, j] = True
    ym = (y[:-1] + y[1:]) / 2
    eps = np.where(ym < g.h1, g.er1, g.er2) if with_dielectric else np.ones(ny - 1)
    dx, dy = np.diff(x), np.diff(y)
    rows, cols, data = [], [], []
    # conductance between nodes: sum of the two half cells
    def add(a, b, c):
        rows.extend([a, b, a, b]); cols.extend([a, b, b, a]); data.extend([c, c, -c, -c])
    for i in range(nx - 1):
        for j in range(ny):
            e = 0.0
            if j > 0:
                e += eps[j - 1] * dy[j - 1] / 2
            if j < ny - 1:
                e += eps[j] * dy[j] / 2
            add(idx(i, j), idx(i + 1, j), e / dx[i])
    for i in range(nx):
        for j in range(ny - 1):
            e = 0.0
            if i > 0:
                e += eps[j] * dx[i - 1] / 2
            if i < nx - 1:
                e += eps[j] * dx[i] / 2
            add(idx(i, j), idx(i, j + 1), e / dy[j])
    K = sp.csr_matrix((data, (rows, cols)), shape=(nx * ny, nx * ny))
    f = fixed.ravel()
    phi = potential.ravel().copy()
    free = np.where(~f)[0]
    A = K[free][:, free].tocsc()
    rhs = -K[free][:, np.where(f)[0]] @ phi[f]
    phi[free] = spla.spsolve(A, rhs)
    return float(phi @ (K @ phi)) * EPS0  # 2 × energy: F/m for unit voltages


def _check(g, d=None):
    """Refuse a geometry the grid would misread: a trace reaching the upper plane, conductors that touch."""
    if g.t >= g.h2:
        raise ValueError(f"trace thickness t {g.t} mm ≥ h2 {g.h2} mm: the trace reaches the upper plane. h2 counts from "
                         "the base of the trace (copper thickness + dielectric above it)")
    wide = max(g.w, g.w if g.w_top is None else g.w_top)
    if g.s > 0 and wide >= g.w + g.s - 2 * TOL:       # each trace's mask reaches TOL beyond its edge
        raise ValueError(f"the two traces touch: width {wide} mm (base or top) ≥ w + s = {g.w + g.s} mm (within "
                         f"{2 * TOL} mm)")
    if g.side_gap is not None and (wide - g.w) / 2 >= g.side_gap - TOL:
        raise ValueError(f"the trace touches the coplanar ground: its top overhangs its base by {(wide - g.w) / 2} mm, "
                         f"side_gap {g.side_gap} mm")


def solve(g: Stripline, d=None):
    """→ {"z0", "er_eff", "tpd_ps_mm"} for one trace, {"z_odd", "z_even", "zdiff", "er_eff", "tpd_ps_mm"} for a pair
    (er_eff and tpd of the odd mode); d: fine step in mm."""
    _check(g, d)
    H = g.h1 + g.h2
    d = d if d is not None else max(min(g.w, g.h2) / 16, 0.002)
    tr = g.traces()
    xmax = max(abs(xc) + w / 2 for xc, w, _ in tr)
    x = _axis(-xmax - 4 * d, xmax + 4 * d, d, -xmax - 12 * H, xmax + 12 * H)
    # noeuds exacts sur les bords des traces
    extra = []
    for xc, w, wt in tr:
        extra += [xc - w / 2, xc + w / 2, xc - wt / 2, xc + wt / 2]
    if g.side_gap is not None:
        e = xmax + g.side_gap
        extra += [e, -e]
    x = np.unique(np.round(np.r_[x, extra], 7))
    # drop the nodes that are too close
    x = x[np.r_[True, np.diff(x) > d / 4]]
    pts = [0.0, g.h1, g.h1 + g.t, H] if g.t > 0 else [0.0, g.h1, H]
    y = _axis_y(pts, d)
    res = {}
    if g.s <= 0:
        c = _capacitance(g, x, y, None, [1.0], True)
        c0 = _capacitance(g, x, y, None, [1.0], False)
        z = 1 / (C0 * np.sqrt(c * c0))
        ee = c / c0
        res.update(z0=float(z), er_eff=float(ee), tpd_ps_mm=float(np.sqrt(ee) / C0 * 1e9))
        return res
    co = _capacitance(g, x, y, None, [1.0, -1.0], True) / 2
    co0 = _capacitance(g, x, y, None, [1.0, -1.0], False) / 2
    ce = _capacitance(g, x, y, None, [1.0, 1.0], True) / 2
    ce0 = _capacitance(g, x, y, None, [1.0, 1.0], False) / 2
    zo = 1 / (C0 * np.sqrt(co * co0))
    ze = 1 / (C0 * np.sqrt(ce * ce0))
    ee = co / co0
    res.update(z_odd=float(zo), z_even=float(ze), zdiff=float(2 * zo), er_eff=float(ee),
               tpd_ps_mm=float(np.sqrt(ee) / C0 * 1e9))
    return res
