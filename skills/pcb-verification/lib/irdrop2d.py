"""DC voltage drop of one net on the board's copper: resistive mesh of square cells over several layers, linked by via
barrels, source pad at 0 V, each load's current spread over its pad cells (numpy, scipy, matplotlib). Geometry and
cells in mm, copper thickness and plating in m. A ValueError is a refusal: the board script writes the step incomplete.
"""
import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from matplotlib.path import Path as _Path
from scipy.sparse.csgraph import connected_components

from copper_dc import RHO, via_barrel_resistance        # one barrel law for every check


def raster(polys, d):
    """(masks {layer: bool (nx, ny)}, xs, ys) of the cells whose centre is inside an outline and outside its holes;
    polys: {layer: [{"outline": [(x, y), …], "holes": [[(x, y), …], …]}]} in mm, d the cell side in mm."""
    pts = np.array([p for ps in polys.values() for pg in ps for p in pg["outline"]], dtype=float)
    xs = np.arange(pts[:, 0].min() - d, pts[:, 0].max() + 1.5 * d, d)
    ys = np.arange(pts[:, 1].min() - d, pts[:, 1].max() + 1.5 * d, d)
    centres = np.array(np.meshgrid(xs, ys, indexing="ij")).reshape(2, -1).T
    masks = {}
    for layer, ps in polys.items():
        m = np.zeros(len(centres), dtype=bool)
        for k, pg in enumerate(ps):
            inside = _Path(pg["outline"]).contains_points(centres)
            for h in pg.get("holes", []):
                if len(h) > 2:
                    inside &= ~_Path(h).contains_points(centres)
            m |= inside
        if m.any():
            masks[layer] = m.reshape(len(xs), len(ys))
    return masks, xs, ys


def pad_cells(a, xs, ys, d, pad):
    """Node numbers of the cells whose centre lies inside the pad's copper outline `pad["outline"]` (required); for a
    pad smaller than a cell, the cell of the outline's centre if it is copper, else an empty array."""
    if len(pad.get("outline") or []) < 3:
        raise ValueError(f"pad {pad.get('label', '?')}: its outline is needed (kicad_copper.rail_pad), not only its box")
    ox, oy = [x for x, _ in pad["outline"]], [y for _, y in pad["outline"]]
    box = (((xs >= min(ox)) & (xs <= max(ox)))[:, None] & ((ys >= min(oy)) & (ys <= max(oy)))[None, :])
    ii, jj = np.nonzero(box)
    if len(ii):
        inside = _Path(pad["outline"]).contains_points(np.column_stack([xs[ii], ys[jj]]))
        ii, jj = ii[inside], jj[inside]
    sel = a[ii, jj]
    sel = sel[sel >= 0]
    if not len(sel):
        cx, cy = (min(ox) + max(ox)) / 2, (min(oy) + max(oy)) / 2          # centre of the copper, not the anchor
        ix, iy = int(round((cx - xs[0]) / d)), int(round((cy - ys[0]) / d))
        if 0 <= ix < len(xs) and 0 <= iy < len(ys) and a[ix, iy] >= 0:
            sel = np.array([a[ix, iy]])
    return sel


def solve_rail(masks, xs, ys, d, vias, source, loads, t_cu, z_mm, order, plating_m):
    """({label: drop in V}, {"nodes", "vias_linking_layers"}). vias: [{"x", "y", "drill"}] mm; source, loads: pad
    dicts {"x", "y", "w", "h", "layer", "outline"} (`kicad_copper.rail_pad`), loads also "amps" (≥ 0, drawn) and a
    unique "label"; t_cu: {layer: m}; z_mm: {layer: mm}; order: layers top to bottom; plating_m: via plating (m)."""
    if not loads:
        raise ValueError("no load on this rail: nothing to compute")
    for ld in loads:
        if ld["amps"] < 0:
            raise ValueError(f"load {ld.get('label', '?')}: current must be ≥ 0 A (drawn), got {ld['amps']!r}")
    idx, n = {}, 0
    for l in order:                                    # one node per copper cell, layer after layer
        if l in masks:
            a = -np.ones(masks[l].shape, dtype=int)
            a[masks[l]] = np.arange(n, n + masks[l].sum())
            n += int(masks[l].sum())
            idx[l] = a
    rows, cols, vals = [], [], []

    def link(i, j, g):
        i, j = np.atleast_1d(i), np.atleast_1d(j)
        g = np.broadcast_to(np.asarray(g, dtype=float), i.shape)
        rows.extend([i, j]); cols.extend([j, i]); vals.extend([-g, -g])

    for l, a in idx.items():                           # in plane: square cells, conductance = t / rho
        for u, v in ((a[:-1, :], a[1:, :]), (a[:, :-1], a[:, 1:])):
            ok = (u >= 0) & (v >= 0)
            link(u[ok], v[ok], t_cu[l] / RHO)
    linking = 0
    for via in vias:                                   # barrel between consecutive layers with copper there
        ix, iy = int(round((via["x"] - xs[0]) / d)), int(round((via["y"] - ys[0]) / d))
        inside = 0 <= ix < len(xs) and 0 <= iy < len(ys)
        present = [l for l in order if l in idx and inside and idx[l][ix, iy] >= 0]
        linking += len(present) >= 2
        for la, lb in zip(present, present[1:]):
            za, zb = z_mm[la], z_mm[lb]
            link(idx[la][ix, iy], idx[lb][ix, iy], 1.0 / via_barrel_resistance(via["drill"], abs(zb - za), plating_m))
    if source["layer"] not in idx:
        raise ValueError(f"source pad on {source['layer']}: no meshed copper of the rail on that layer")
    fixed = np.zeros(n, dtype=bool)
    fixed[pad_cells(idx[source["layer"]], xs, ys, d, source)] = True      # source pad held at 0 V
    if not fixed.any():                                # without a reference the system is singular
        raise ValueError("source pad outside the meshed copper: no cell held at 0 V")
    rows, cols, vals = np.concatenate(rows), np.concatenate(cols), np.concatenate(vals)
    G = sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
    _, comp = connected_components(G, directed=False)  # islands: copper with no path to the source
    reached = np.isin(comp, np.unique(comp[fixed]))
    G = G + sp.diags(-np.asarray(G.sum(axis=1)).ravel())     # diagonal = sum of the conductances of the node
    inj, nodes = np.zeros(n), {}
    labels = [ld["label"] for ld in loads]
    doubles = sorted({l for l in labels if labels.count(l) > 1})
    if doubles:                                        # one result per label: a duplicate would hide a load's drop
        raise ValueError(f"duplicate load labels {doubles}: give each pad a unique label (ref.pin)")
    for ld in loads:
        sel = pad_cells(idx[ld["layer"]], xs, ys, d, ld) if ld["layer"] in idx else np.array([], dtype=int)
        if not len(sel):                               # fail rather than underestimate the drop in silence
            raise ValueError(f"load {ld['label']} outside the meshed copper")
        if not reached[sel].all():                     # a missing link in the model (via pad, graphic fill…)
            raise ValueError(f"load {ld['label']} on copper with no path to the source (island)")
        inj[sel] -= ld["amps"] / len(sel)
        nodes[ld["label"]] = sel
    total = sum(ld["amps"] for ld in loads)
    if abs(-inj.sum() - total) > 1e-9 * max(total, 1):  # balance: all the requested current is injected
        raise ValueError(f"current balance: {-inj.sum():.4f} A injected for {total:.4f} A")
    v = np.zeros(n)
    free = ~fixed & reached                            # unreached islands carry no current: left at 0
    v[free] = spla.spsolve(G[free][:, free].tocsc(), inj[free])
    drops = {label: float(-v[s].mean()) for label, s in nodes.items()}    # drop in V per load
    bad = sorted(label for label, x in drops.items() if not math.isfinite(x))
    if bad:
        raise ValueError(f"drop not finite for {bad}: the mesh or its conductances are wrong")
    return drops, {"nodes": int(n), "vias_linking_layers": int(linking)}
