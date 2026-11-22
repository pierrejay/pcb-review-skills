"""2D electrostatic solver (finite volumes, numpy / scipy): field between conductors of a PCB stack-up, planar (x, z)
or axisymmetric (r, z), maximum field per material read at least (`guard` + 1) × `d_fine` from the copper.
Units: mm, V; field in kV/mm (= V/µm).
"""
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.ndimage import binary_erosion
from scipy.spatial import cKDTree


def strip(x0, x1, zc, t, round_lo=False, round_hi=False):
    """Flat conductor [x0, x1] × [zc − t/2, zc + t/2] as an `inside(X, Z)` mask, ends optionally rounded at radius t/2
    (`round_lo` at x0, `round_hi` at x1)."""
    r = t / 2

    def inside(X, Z):
        m = (X >= x0 + (r if round_lo else 0)) & (X <= x1 - (r if round_hi else 0)) & (np.abs(Z - zc) <= r)
        if round_lo:
            m |= (X - (x0 + r)) ** 2 + (Z - zc) ** 2 <= r ** 2
        if round_hi:
            m |= (X - (x1 - r)) ** 2 + (Z - zc) ** 2 <= r ** 2
        return m
    return inside


def rect(x0, x1, z0, z1):
    """Rectangle [x0, x1] × [z0, z1] as an `inside(X, Z)` mask."""
    return lambda X, Z: (X >= x0) & (X <= x1) & (Z >= z0) & (Z <= z1)


@dataclass
class Problem:
    """Geometry (mm, V): `layers` (z0, z1, εr, name), air elsewhere; `conductors` (inside(X, Z) boolean mask, volts,
    name); `focus` boxes (x0, x1, z0, z1) meshed at `d_fine`; `axisymmetric`: x is the radius; `extra_eps` (inside,
    εr, name) override `layers`. Far edges: zero flux."""
    x_range: tuple                      # (min, max) of the domain
    z_range: tuple
    layers: list                         # [(z0, z1, eps, name)]; air elsewhere (eps 1)
    conductors: list                     # [(inside(X, Z) function, potential V, name)]
    focus: list                          # [(x0, x1, z0, z1)]: regions to mesh finely
    axisymmetric: bool = False
    extra_eps: list = field(default_factory=list)  # [(inside function, eps, name)] takes priority


def _axis(lo, hi, focus, d_fine, d_coarse, breaks):
    pts = [np.arange(lo, hi + d_coarse / 2, d_coarse)]
    for a, b in focus:
        pts.append(np.arange(max(lo, a), min(hi, b) + d_fine / 2, d_fine))
    pts.append(np.array([p for p in breaks if lo <= p <= hi]))
    x = np.unique(np.round(np.concatenate(pts), 9))
    return x


MAX_NODES = 6_000_000   # screening cap: ≈ 0.125 µm on the focus boxes of a pad in its antipad, about a minute and a few GB with SuperLU


def _check_mesh(pb):
    # orders that would otherwise drop a fine box or a layer, or revolve negative radii, without an error
    if pb.axisymmetric and pb.x_range[0] < 0:
        raise ValueError(f"axisymmetric: x is the radius, x_range must start at 0 or above, got {pb.x_range!r}")
    for f in pb.focus:
        if not (f[0] < f[1] and f[2] < f[3]):
            raise ValueError(f"focus box {f!r}: expected (x0, x1, z0, z1), x0 < x1 and z0 < z1")
    for layer in pb.layers:
        if not layer[0] < layer[1]:
            raise ValueError(f"layer {layer!r}: expected (z0, z1, εr, name), z0 < z1")


def _mask(m, shape, name):
    """The boolean mask returned by an `inside` function, of the grid's shape."""
    m = np.asarray(m)
    if m.dtype != bool or m.shape != shape:
        raise ValueError(f"{name!r}: inside(X, Z) must return a boolean array of the grid's shape {shape}, got "
                         f"{m.dtype} {m.shape}")
    return m


def _grid(pb, d_fine, d_coarse):
    _check_mesh(pb)
    breaks_z = [v for l in pb.layers for v in l[:2]]
    x = _axis(*pb.x_range, [(f[0], f[1]) for f in pb.focus], d_fine, d_coarse, [])
    z = _axis(*pb.z_range, [(f[2], f[3]) for f in pb.focus], d_fine, d_coarse, breaks_z)
    return x, z


def node_count(pb: Problem, d_fine=0.5e-3, d_coarse=10e-3):
    """Number of mesh nodes `solve` would build, without solving (the grid is a tensor product: a fine box widens a
    whole row and a whole column)."""
    x, z = _grid(pb, d_fine, d_coarse)
    return len(x) * len(z)


def solve(pb: Problem, d_fine=0.5e-3, d_coarse=10e-3, guard=2, max_nodes=MAX_NODES):
    """Potential and field of `pb`, mesh `d_fine` on the focus boxes and `d_coarse` elsewhere (mm). Returns {"nodes",
    "x", "z" (mm), "phi" (V, nodes), "E" (kV/mm, cells), "mat", "by_material": {name: {"E_max_kV_mm", "at_mm"}}}, the
    maximum read at least (`guard` + 1) × `d_fine` from any conductor (`edge_field.fixed_distance_guard`)."""
    x, z = _grid(pb, d_fine, d_coarse)
    nx, nz = len(x), len(z)
    if max_nodes is not None and nx * nz > max_nodes:   # SuperLU would take tens of GB, or fail in malloc
        raise ValueError(f"{nx * nz:,} mesh nodes at d_fine {d_fine * 1e3:g} µm, above max_nodes {max_nodes:,}: "
                         f"keep the fine mesh on the edge that carries the maximum only (one focus box, found on a "
                         f"coarse run), shrink the boxes to a few tens of reading distances, or stop the series at a "
                         f"coarser mesh; raise max_nodes only knowing the memory it takes")
    X, Z = np.meshgrid(x, z, indexing="ij")
    xc, zc = (x[:-1] + x[1:]) / 2, (z[:-1] + z[1:]) / 2
    XC, ZC = np.meshgrid(xc, zc, indexing="ij")

    eps = np.ones(XC.shape)
    mat = np.full(XC.shape, "air", dtype=object)
    for z0, z1, e, name in pb.layers:
        m = (ZC >= z0) & (ZC < z1)
        eps[m], mat[m] = e, name
    for inside, e, name in pb.extra_eps:
        m = _mask(inside(XC, ZC), XC.shape, name)
        eps[m], mat[m] = e, name

    cond = np.full((nx, nz), -1)
    volts = []
    for k, (inside, v, name) in enumerate(pb.conductors):
        m = _mask(inside(X, Z), X.shape, name)
        if not m.any():                    # thinner than the mesh, or outside the domain: the field would be wrong
            raise ValueError(f"conductor {name!r} occupies no mesh node: refine the mesh there (focus) or check it")
        clash = {pb.conductors[j][2] for j in np.unique(cond[m]) if j >= 0 and volts[j] != v}
        if clash:                          # two potentials on the same nodes: one would silently overwrite the other
            raise ValueError(f"conductor {name!r} overlaps {sorted(clash)} at another potential")
        cond[m] = k
        volts.append(v)
    if len(set(volts)) < 2:                # one potential only: zero field by construction, not a result
        raise ValueError("fewer than two distinct potentials: no field to compute")

    dx, dz = np.diff(x), np.diff(z)
    idx = np.arange(nx * nz).reshape(nx, nz)
    ax = pb.axisymmetric
    # horizontal conductance (i,j)-(i+1,j): half-cells above and below the edge
    ep = np.pad(eps, ((0, 0), (1, 1)), mode="edge")
    dzp = np.concatenate([[0], dz, [0]])
    rx = ((x[:-1] + x[1:]) / 2)[:, None] if ax else 1.0
    gx = (ep[:, :-1] * dzp[:-1] / 2 + ep[:, 1:] * dzp[1:] / 2) / dx[:, None] * rx
    # vertical conductance (i,j)-(i,j+1): half-cells on the left and right
    ep = np.pad(eps, ((1, 1), (0, 0)), mode="edge")
    dxp = np.concatenate([[0], dx, [0]])
    if ax:
        r_lo = np.maximum(x - dxp[:-1] / 4, 0)[:, None]
        r_hi = (x + dxp[1:] / 4)[:, None]
    else:
        r_lo = r_hi = 1.0
    gz = (ep[:-1, :] * dxp[:-1, None] / 2 * r_lo + ep[1:, :] * dxp[1:, None] / 2 * r_hi) / dz[None, :]
    rows = np.concatenate([idx[:-1, :].ravel(), idx[:, :-1].ravel()])
    cols = np.concatenate([idx[1:, :].ravel(), idx[:, 1:].ravel()])
    vals = np.concatenate([gx.ravel(), gz.ravel()])
    n = nx * nz
    off = sp.coo_matrix((-vals, (rows, cols)), shape=(n, n))
    off = (off + off.T).tocsr()
    K = off + sp.diags(-np.asarray(off.sum(axis=1)).ravel())

    fixed = (cond >= 0).ravel()
    phi = np.zeros(n)
    phi[fixed] = np.array(volts)[cond.ravel()[fixed]]
    free = ~fixed
    K = K.tocsr()
    phi[free] = spla.spsolve(K[free][:, free].tocsc(), -K[free][:, fixed] @ phi[fixed])
    P = phi.reshape(nx, nz)

    ex = np.diff(P, axis=0) / dx[:, None]
    ez = np.diff(P, axis=1) / dz[None, :]
    E = np.hypot((ex[:, :-1] + ex[:, 1:]) / 2, (ez[:-1, :] + ez[1:, :]) / 2) / 1000  # kV/mm
    inside = cond >= 0
    edge = inside & ~binary_erosion(inside)                 # conductor nodes that face a dielectric node
    XN, ZN = np.meshgrid(x, z, indexing="ij")
    dist, _ = cKDTree(np.column_stack([XN[edge], ZN[edge]])).query(np.column_stack([XC.ravel(), ZC.ravel()]))
    cell_near = dist.reshape(XC.shape) < (guard + 1) * d_fine * (1 - 1e-9)
    res = {"nodes": n, "x": x, "z": z, "phi": P, "E": E, "mat": mat, "by_material": {}}
    for name in set(mat.ravel()):
        m = (mat == name) & ~cell_near
        if m.any():
            k = np.unravel_index(np.argmax(np.where(m, E, -1)), E.shape)
            res["by_material"][name] = {"E_max_kV_mm": float(E[k]), "at_mm": (float(xc[k[0]]), float(zc[k[1]]))}
    return res
