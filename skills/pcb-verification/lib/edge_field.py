"""Convergence of a peak field read near a rounded copper edge (`estatic2d.solve`) at a fixed reading distance, and
its extrapolation to the copper surface (numpy). Units: mm for the mesh, µm for the reading distances, kV/mm.
"""
import math

import numpy as np

from messages import Msg  # coded reasons: the report renders them in its language

LAST_STEP_MAX = 0.02       # convergence screening threshold of this tool: last relative step of a converging series
RATIO_MAX = 0.6            # convergence screening threshold: |difference ratio| for the differences to be shrinking
FLAT_BAND = 0.01           # convergence screening threshold: a series whose spread is inside this is at the noise of the calculation
FIT_RESIDUAL_MAX = 0.01    # the fit must give back each reading within this
SURFACE_JUMP_MAX = 0.15    # convergence screening threshold: the surface value may not exceed the closest reading by more than this


def fixed_distance_guard(x_mm, d_fine):
    """`guard` for `estatic2d.solve(pb, d_fine=d, guard=…)` that keeps the reading distance at `x_mm` whatever the
    mesh: round(x / d) − 1; x must be a whole number of cells, at least two."""
    n = x_mm / d_fine
    if abs(n - round(n)) > 1e-6 * max(1.0, n):
        raise ValueError(f"reading distance {x_mm} mm is {n:.4f} cells of {d_fine} mm: use a whole number of cells")
    guard = int(round(n)) - 1
    if guard < 1:
        raise ValueError(f"reading distance {x_mm} mm is one cell of {d_fine} mm: at least two cells (guard ≥ 1)")
    return guard


def converged(series):
    """Readings at ONE fixed reading distance, mesh halved between entries (coarse → fine). Returns {"converged",
    "value", "method" ("flat", "richardson", "last" or None), "last_step", "ratio", "spread", "reason"}; does not
    raise on a series that does not converge (`require_converged` does)."""
    s = np.asarray(series, dtype=float).ravel()
    last = float(s[-1])
    spread = float((s.max() - s.min()) / abs(last))
    diffs = np.diff(s)
    last_step = float(abs(diffs[-1]) / abs(last))
    ratio = float(diffs[-1] / diffs[-2]) if s.size >= 3 and diffs[-2] != 0 else None
    out = {"converged": False, "value": None, "method": None, "last_step": last_step, "ratio": ratio,
           "spread": spread, "reason": ""}
    if spread <= FLAT_BAND:
        out.update(converged=True, value=last, method="flat", reason=Msg(f"series inside {FLAT_BAND:.0%}", "series_flat", band=FLAT_BAND))
        return out
    if s.size < 3:
        out["reason"] = Msg(f"two readings {spread:.1%} apart: a third mesh is needed to see the differences shrink",
                            "series_two_readings", spread=spread)
        return out
    if last_step > LAST_STEP_MAX:
        out["reason"] = Msg(f"last step {last_step:.1%} > {LAST_STEP_MAX:.0%}", "series_last_step", step=last_step,
                            limit=LAST_STEP_MAX)
        return out
    if ratio is None or abs(ratio) > RATIO_MAX:
        out["reason"] = Msg(f"differences not shrinking: ratio {ratio if ratio is None else round(ratio, 2)} > {RATIO_MAX}",
                            "series_not_shrinking", ratio=ratio, limit=RATIO_MAX)
        return out
    if np.all(diffs > 0) or np.all(diffs < 0):
        r = ratio
        out.update(converged=True, value=last + float(diffs[-1]) * r / (1.0 - r), method="richardson",
                   reason=Msg(f"monotonic, ratio {r:.2f}: Richardson with the observed ratio", "series_richardson", ratio=r))
    else:
        out.update(converged=True, value=last, method="last", reason=Msg("oscillating and damping: last value", "series_oscillating"))
    return out


def require_converged(series, label="series"):
    """`converged(series)["value"]`, or ValueError naming the series and the reason."""
    c = converged(series)
    if not c["converged"]:
        raise ValueError(f"{label} not converged: {c['reason']}; fix the model, do not quote")
    return c["value"]


def surface_field(distances_um, fields):
    """Surface field from converged readings at ≥ 3 distances (µm), fit E(x) = A / (R + x). Returns {"surface",
    "R_um", "A", "residual", "jump" (surface / closest reading − 1), "readings"}."""
    x = np.asarray(distances_um, dtype=float).ravel()
    e = np.asarray(fields, dtype=float).ravel()
    if x.size != e.size or x.size < 3 or np.unique(x).size < 3:
        raise ValueError("the surface fit needs converged readings at three distinct distances at least")
    slope, intercept = np.polyfit(x, 1.0 / e, 1)
    if slope <= 0 or intercept <= 0:
        raise ValueError("1/E does not grow with the distance: the readings do not rise toward the surface")
    a = 1.0 / slope
    r_um = intercept * a
    fit = a / (r_um + x)
    residual = float(np.max(np.abs(fit / e - 1.0)))
    surface = a / r_um
    closest = float(e[np.argmin(x)])
    jump = surface / closest - 1.0
    if residual > FIT_RESIDUAL_MAX:
        raise ValueError(f"fit A/(R + x) misses a reading by {residual:.1%} (> {FIT_RESIDUAL_MAX:.0%}): "
                         "the readings are not on one curve; check their convergence")
    if jump > SURFACE_JUMP_MAX or jump < 0:
        raise ValueError(f"surface value {surface:.2f} is {jump:+.0%} from the closest reading {closest:.2f} "
                         f"(limit +{SURFACE_JUMP_MAX:.0%}): read closer to the copper before extrapolating")
    return {"surface": float(surface), "R_um": float(r_um), "A": float(a), "residual": residual, "jump": float(jump),
            "readings": {float(xi): float(ei) for xi, ei in zip(x, e)}}


def edge_field_study(distances_um, series_by_distance):
    """`series_by_distance` = {distance_um: [readings over successive halvings]}: every series must converge, then
    `surface_field` on the converged values. Returns the `surface_field` dict plus "converged": {distance: result}."""
    conv = {}
    values = []
    xs = []
    for d in distances_um:
        c = converged(series_by_distance[d])
        if not c["converged"]:
            raise ValueError(f"series at {d} µm not converged: {c['reason']}")
        conv[d] = c
        xs.append(d)
        values.append(c["value"])
    out = surface_field(xs, values)
    out["converged"] = conv
    return out


def scale_to_voltage(field_per_kv, peak_kv):
    """Field at a peak voltage (kV) from the field per kV (linear problem)."""
    return field_per_kv * peak_kv


def margin(strength_kv_mm, field_kv_mm):
    """strength / field."""
    return strength_kv_mm / field_kv_mm


if __name__ == "__main__":  # pragma: no cover - example values, no board data
    print(converged([17.19, 18.09, 18.41]), converged([20.26, 20.86, 21.13]), converged([22.82, 22.92]), sep="\n")
    print(converged([17.19, 20.26, 22.82]))
    print(surface_field([3, 1.5, 0.75], [18.59, 21.35, 22.92]))
    print(math.isclose(surface_field([3, 1.5, 0.75], [19.06, 21.90, 23.51])["surface"], 25.6, rel_tol=0.01))
