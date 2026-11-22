"""Board-free formulas of the power-input check: two-point TVS fit (from `tvs_fit`, under the names this check uses),
soft-saturation law of an inductor, series and R–C dampers of an LC input filter (pure Python). SI units.
"""
import math

from tvs_fit import VT, avalanche_fit, line_fit, predicted_voltage


def tvs_fit_exact(v1, i1, v2, i2, nbv=1.0, ibv=1e-3):
    """(RS, BV) of an ngspice diode D(RS BV IBV NBV) through two published clamping points, log term included."""
    return avalanche_fit(v1, i1, v2, i2, nbv, ibv)


def tvs_fit_quick(v1, i1, v2, i2):
    """(RS, BV) of the straight line through the two points (about 0.2 V above them once the log term is added)."""
    return line_fit(v1, i1, v2, i2)


def tvs_model_voltage(bv, rs, i, nbv=1.0, ibv=1e-3):
    """Reverse voltage (V) of the model at current `i` (A); argument order BV, RS (that of `predicted_voltage` is
    RS, BV)."""
    return predicted_voltage(rs, bv, i, nbv, ibv)


def saturation_ik(i_sat, drop=0.3):
    """IK (A) of L(i) = L0 / (1 + (i / IK)²) with the inductance down by `drop` at `i_sat`: an estimate of the law."""
    return i_sat / math.sqrt(1.0 / (1.0 - drop) - 1.0)


def saturable_inductance(l0, ik, i):
    """L(i) = L0 / (1 + (i / IK)²), H."""
    return l0 / (1.0 + (i / ik) ** 2)


def _series_peak(r):
    # peak of |Z| / Z0 of (R + jωL) ∥ 1 / (jωC), r = R / Z0
    u = -r * r + math.sqrt(2 * r * r + 1)
    return math.sqrt((r * r + u) / ((1 - u) ** 2 + r * r * u))


def series_damper(l_source, c_eff, z_max):
    """Smallest series resistance between the source inductance and the effective capacitance that keeps the peak
    output impedance under `z_max`: {"z0", "r_min" (None when z_max < √2·Z0), "r_first_order" (L / (C z_max))}."""
    l, c, z = l_source, c_eff, z_max
    z0 = math.sqrt(l / c)
    out = {"z0": z0, "r_min": None, "r_first_order": l / (c * z)}
    t = z / z0
    if t < math.sqrt(2):
        return out
    lo, hi = 0.0, math.sqrt(1.5)
    for _ in range(200):
        mid = (lo + hi) / 2
        if mid > 0 and _series_peak(mid) > t:
            lo = mid
        else:
            hi = mid
    out["r_min"] = hi * z0
    return out


def damper(l, c_eff, c_factor=4.0):
    """Optimal R–C damper (Erickson and Maksimović) across the converter-side capacitor, C_damper = c_factor × C_eff:
    {"z0", "r", "c_min", "z_out_peak"}."""
    c, n = c_eff, c_factor
    z0 = math.sqrt(l / c)
    return {"z0": z0, "r": z0 * math.sqrt((2 + n) * (4 + 3 * n) / (2 * n * n * (4 + n))), "c_min": n * c,
            "z_out_peak": z0 * math.sqrt(2 * (2 + n)) / n}
