"""2D thermal model of a board: square cells of side d, in-plane conduction (sheet k·t of the layers) and exchange h
per face with the ambient (numpy, scipy). Units: m, W, K.
"""
import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

K_CU, K_FR4 = 390.0, 0.3


def sheet_kt(cover, t_cu, t_fr4):
    """k·t (W/K) per cell; cover: {layer: array of copper fractions in [0, 1]}, t_cu: {layer: thickness m}."""
    kt = K_FR4 * t_fr4
    for l, c in cover.items():
        c = np.asarray(c, dtype=float)
        if (c < 0).any() or (c > 1).any():
            raise ValueError(f"coverage of layer {l!r} must be fractions in [0, 1]")
        kt = kt + K_CU * t_cu[l] * c
    return kt


def solve(kt, mask, d, h_top, h_bot, power):
    """Temperature rise (K) per cell, NaN off the board; kt, mask, power: arrays (nx, ny), d in m, h per face."""
    kt, mask, power = np.asarray(kt, dtype=float), np.asarray(mask, dtype=bool), np.asarray(power, dtype=float)
    nx, ny = kt.shape
    idx = -np.ones((nx, ny), dtype=int)
    idx[mask] = np.arange(mask.sum())
    n = int(mask.sum())
    rows, cols, vals = [], [], []
    for sl_a, sl_b in (((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                       ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
        a, b = idx[sl_a], idx[sl_b]
        ka, kb = kt[sl_a], kt[sl_b]
        ok = (a >= 0) & (b >= 0)
        g = 2 * ka[ok] * kb[ok] / (ka[ok] + kb[ok])  # square cells: G = k·t
        rows += [a[ok], b[ok]]
        cols += [b[ok], a[ok]]
        vals += [-g, -g]
    G = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    diag = -np.asarray(G.sum(axis=1)).ravel() + (h_top + h_bot) * d * d
    G = G + sp.diags(diag)
    t = spla.spsolve(G.tocsc(), power[mask])
    if not np.isfinite(t).all():
        raise ValueError("thermal solution is not finite")
    out = np.full((nx, ny), np.nan)
    out[mask] = t
    return out


def jedec_2s2p(d=0.5e-3):
    """(kt, mask, nx, ny) of the JESD51-7 2s2p board: 114.3 × 76.2 × 1.6 mm, two 35 µm inner planes of 74.2 × 74.2 mm
    centred on the part, 70 µm outer faces at 5 % coverage."""
    nx, ny = int(114.3e-3 / d), int(76.2e-3 / d)
    mask = np.ones((nx, ny), dtype=bool)
    x, y = (np.arange(nx) + 0.5) * d, (np.arange(ny) + 0.5) * d
    plane = ((abs(x - 57.15e-3) <= 37.1e-3)[:, None] & (abs(y - 38.1e-3) <= 37.1e-3)[None, :]).astype(float)
    cover = {"top": np.full((nx, ny), 0.05), "p1": plane, "p2": plane, "bot": np.full((nx, ny), 0.05)}
    kt = sheet_kt(cover, {"top": 70e-6, "p1": 35e-6, "p2": 35e-6, "bot": 70e-6}, 1.6e-3)
    return kt, mask, nx, ny


def cell_span(c_mm, w_mm, d_mm, n):
    """Slice of the cells of [c − w/2, c + w/2] on a grid of n cells of d_mm from 0 (floor of each end, upper one
    included, clamped to [0, n]); None when off the grid."""
    lo = math.floor((c_mm - w_mm / 2) / d_mm)
    hi = math.floor((c_mm + w_mm / 2) / d_mm) + 1
    lo, hi = max(lo, 0), min(hi, n)
    return slice(lo, hi) if hi > lo else None


def theta_board_ambient(kt, mask, d, h, footprint_mm, center):
    """Board → ambient θ (K/W) under a footprint (w, l mm) at `center` (mm): mean rise under the cells of `cell_span`
    for 1 W spread over them."""
    nx, ny = kt.shape
    p = np.zeros((nx, ny))
    w, l = footprint_mm
    cx, cy = center
    ix, iy = cell_span(cx, w, d * 1e3, nx), cell_span(cy, l, d * 1e3, ny)
    sub = np.zeros((nx, ny), dtype=bool)
    if ix is not None and iy is not None:
        sub[ix, iy] = True
    sub &= mask
    if not sub.any():
        raise ValueError(f"footprint {footprint_mm} mm at {center} mm touches no cell of the board")
    p[sub] = 1.0 / sub.sum()
    t = solve(kt, mask, d, h, h, p)
    return float(np.nanmean(t[sub]))


def calibrate_h(theta_ja, theta_jb, footprint_mm, d=0.5e-3, bounds=(1.0, 60.0)):
    """(h W/m²K per face, θ reached) such that the JEDEC board's θ board → air under the footprint equals θJA − θJB;
    ValueError when no h in `bounds` gives it or the bisection does not converge."""
    kt, mask, nx, ny = jedec_2s2p(d)
    target = theta_ja - theta_jb
    lo, hi = bounds[0], bounds[1]

    def theta(h):
        return theta_board_ambient(kt, mask, d, h, footprint_mm, (57.15, 38.1))

    th_lo, th_hi = theta(lo), theta(hi)
    if not th_hi <= target <= th_lo:
        raise ValueError(f"no h between {lo} and {hi} W/m²K gives a board→air θ of {target:.2f} °C/W for this "
                         f"footprint (the model spans {th_hi:.2f} to {th_lo:.2f}): check θJA, θJB and the footprint")
    for _ in range(40):
        h = (lo * hi) ** 0.5
        th = theta(h)
        lo, hi = (h, hi) if th > target else (lo, h)
    if abs(th - target) > 1e-3 * target:
        raise ValueError(f"calibration not converged: {th:.4f} for {target:.4f} °C/W")
    return h, th
