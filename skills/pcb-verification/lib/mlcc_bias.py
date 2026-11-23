"""Effective capacitance of class-2 MLCCs under DC bias: the law C(V) = C0 / (1 + (V / a)^b) fitted on the
manufacturer's points, or the points themselves (`table_bias`), the sum over a rail, charge time and loss, and
typical X5R fractions for screening. Pure Python except `fit_bias` (scipy). V in volts, C in µF.
"""
import bisect
import numbers
import math
from collections import namedtuple

BiasFit = namedtuple("BiasFit", "c0 a b v_min v_max max_dev")   # c0 in µF, a in V, b without unit, range in V
BiasTable = namedtuple("BiasTable", "v c")                      # points: V in volts from 0, C in µF
FIT_TOLERANCE = 0.10       # largest relative deviation `fit_bias` accepts over the working range (fits of usual
                           # low-voltage MLCC curves: 4 to 7 % over the whole curve); beyond it, `table_bias`

# Typical X5R remaining fraction of the nominal value against DC bias: order of magnitude for screening (± a third
# or more for a given part); the curve of the exact part decides. Keys: (EIA case, rated voltage in V) → {bias V: fraction}.
# A bias given as a range (0.9–1 V) is keyed at its upper end (1.0).
X5R_TYPICAL_FRACTION = {
    ("0603", 6.3): {1.0: 0.85, 1.35: 0.80, 2.0: 0.65, 3.3: 0.40},     # 22 µF
    ("0402", 6.3): {1.0: 0.80, 1.35: 0.70, 2.0: 0.55, 3.3: 0.30},     # 10 µF
    ("0603", 10.0): {1.35: 0.90, 3.3: 0.50},                           # 10 µF
    ("0603", 16.0): {3.3: 0.65},
    ("0603", 25.0): {3.3: 0.65},
    ("0402", 25.0): {3.3: 0.57},                                       # 1 µF
}
X5R_TYPICAL_TOLERANCE = 0.35
_EPS = 1e-12


def _params(fit_or_params):
    # (c0, a, b, v_max or None) from a BiasFit or a (c0, a, b) tuple
    if isinstance(fit_or_params, BiasFit):
        return fit_or_params.c0, fit_or_params.a, fit_or_params.b, fit_or_params.v_max
    c0, a, b = fit_or_params
    return c0, a, b, None


def _check_table(t):
    # (v, c) lists of floats of a BiasTable: V strictly increasing from 0 V
    v, c = list(t.v), list(t.c)
    if len(v) != len(c):
        raise ValueError("v and c have different lengths (%d and %d)" % (len(v), len(c)))
    v, c = [float(x) for x in v], [float(x) for x in c]
    if v[0] != 0:
        raise ValueError("a table starts at 0 V (a part starts uncharged), got %g V" % v[0])
    for x0, x1 in zip(v, v[1:]):
        if not x1 > x0:
            raise ValueError("voltages must be strictly increasing, got %g then %g" % (x0, x1))
    return v, c


def table_bias(v, c):
    """The published points of a DC-bias curve as the part's law (V from 0 V, C in µF), C linear between them, never
    read above the last point; taken wherever a fit is."""
    if len(v) != len(c):
        raise ValueError("v and c have different lengths (%d and %d)" % (len(v), len(c)))
    pts = sorted(zip(v, c))              # a manufacturer's export may list its points out of order
    v, c = _check_table(BiasTable(tuple(p[0] for p in pts), tuple(p[1] for p in pts)))
    return BiasTable(tuple(v), tuple(c))


def _part(part):
    # (C(v) without range check, C at 0 V, last point or None, BiasTable or None) of a BiasFit, tuple or BiasTable
    if isinstance(part, BiasTable):
        v, c = _check_table(part)

        def f(x):
            k = min(max(bisect.bisect_right(v, x) - 1, 0), len(v) - 2)
            return c[k] + (c[k + 1] - c[k]) * (x - v[k]) / (v[k + 1] - v[k])
        return f, c[0], v[-1], BiasTable(tuple(v), tuple(c))
    c0, a, b, v_max = _params(part)
    return (lambda x: law(c0, a, b, x)), c0, v_max, None


def _in_range(v, v_max, table, extrapolate):
    if v_max is not None and v > v_max + _EPS and (table is not None or not extrapolate):
        raise ValueError("%.3g V is above the last %s point (%.3g V): an extrapolation, refused"
                         % (v, "tabulated" if table is not None else "fitted", v_max))


def law(c0, a, b, v):
    """C(V) = C0 / (1 + (V / a)^b), same unit as C0."""
    return c0 / (1.0 + (v / a) ** b)


def capacitance(fit_or_params, v, extrapolate=False):
    """C(V) of one part (BiasFit, (c0, a, b) tuple or BiasTable) at bias `v` ≥ 0 (|V| across the part); a BiasFit is
    not read above its last point unless `extrapolate=True`, a BiasTable never."""
    f, _, v_max, table = _part(fit_or_params)
    if v < 0:
        raise ValueError("bias %g V is negative: the curve starts at 0 V (use |V| across the part)" % v)
    _in_range(v, v_max, table, extrapolate)
    return f(v)


def _check_points(v, c):
    if len(v) != len(c):
        raise ValueError("v and c have different lengths (%d and %d)" % (len(v), len(c)))
    if len(v) < 4:
        raise ValueError("a three-parameter law needs at least four points, got %d" % len(v))
    v, c = [float(x) for x in v], [float(x) for x in c]
    for x0, x1 in zip(v, v[1:]):
        if not x1 > x0:
            raise ValueError("voltages must be strictly increasing, got %g then %g" % (x0, x1))
    return v, c


def max_deviation(fit_or_params, v, c, v_lo=None, v_hi=None):
    """Largest |law − point| / point over the points whose voltage lies in [v_lo, v_hi] (whole set by default)."""
    v, c = _check_points(v, c)
    lo = -math.inf if v_lo is None else v_lo
    hi = math.inf if v_hi is None else v_hi
    c0, a, b, _ = _params(fit_or_params)
    return max(abs(law(c0, a, b, x) - y) / y for x, y in zip(v, c) if lo - _EPS <= x <= hi + _EPS)


def fit_bias(v, c, v_lo=None, v_hi=None, start=None, tolerance=FIT_TOLERANCE):
    """Least-squares fit (absolute residuals) of the law on the points (V, µF): a BiasFit whose `max_dev` is over
    [v_lo, v_hi] and `v_max` the last point; ValueError above `tolerance` (then use `table_bias`)."""
    v, c = _check_points(v, c)
    import numpy as np                                   # venv side only
    from scipy.optimize import least_squares
    va, ca = np.array(v), np.array(c)
    p0 = [c[0], 2.0, 1.5] if start is None else [float(x) for x in start]
    res = least_squares(lambda p: p[0] / (1.0 + (va / p[1]) ** p[2]) - ca, p0,
                        bounds=([0.0, 1e-6, 1e-6], [np.inf, np.inf, np.inf]))
    if not res.success:
        raise ValueError("fit did not converge: %s" % res.message)
    c0, a, b = (float(x) for x in res.x)
    fit = BiasFit(c0, a, b, v[0], v[-1], 0.0)
    fit = fit._replace(max_dev=max_deviation(fit, v, c, v_lo, v_hi))
    if fit.max_dev > tolerance:
        raise ValueError("the law C0 / (1 + (V / a)^b) misses the points by %.1f %% (tolerance %.1f %%): it does not "
                         "suit this curve; use table_bias(v, c), the points linear between them"
                         % (100 * fit.max_dev, 100 * tolerance))
    return fit


def effective_capacitance(parts, v, extrapolate=False):
    """Sum over a rail of n × C(V): `parts` = [(part, n)], a part being a BiasFit, a (c0, a, b) tuple, a BiasTable or
    a fixed capacitance (a plain number, µF)."""
    total = 0.0
    for part, n in parts:
        if isinstance(part, numbers.Real):
            total += n * part
        else:
            total += n * capacitance(part, v, extrapolate)
    return total


def charge_time(fit_or_params, v_final, i_a, c_unit=1e-6, steps=2000, extrapolate=False):
    """Time (s) for a constant current `i_a` (A) to charge the part from 0 to `v_final`: ∫ C(v) dv / I, C in units of
    `c_unit`."""
    f, _, v_max, table = _part(fit_or_params)
    vf = v_final
    _in_range(vf, v_max, table, extrapolate)
    i = i_a
    h = vf / steps
    s = 0.5 * (f(0.0) + f(vf))
    for k in range(1, steps):
        s += f(k * h)
    return s * h * c_unit / i


def charge_loss(fit_or_params, v_final, c_unit=1e-6, steps=2000, extrapolate=False):
    """Energy (J) dissipated in the series resistance while a stiff source charges the part from 0 to `v_final`:
    ∫ (V − v) C(v) dv, C in units of `c_unit`."""
    f, _, v_max, table = _part(fit_or_params)
    vf = v_final
    _in_range(vf, v_max, table, extrapolate)
    h = vf / steps
    s = 0.5 * vf * f(0.0)
    for k in range(1, steps):
        s += (vf - k * h) * f(k * h)
    return s * h * c_unit


def typical_fraction(case, rating_v, bias_v):
    """Remaining fraction of the nominal value from `X5R_TYPICAL_FRACTION` (an order of magnitude, for screening),
    only at a tabulated (case, rating, bias)."""
    key = (str(case), float(rating_v))
    if key not in X5R_TYPICAL_FRACTION:
        raise ValueError("no typical row for case %s rated %g V" % key)
    row = X5R_TYPICAL_FRACTION[key]
    bias = bias_v
    for v, frac in row.items():
        if abs(v - bias) < 1e-9:
            return frac
    raise ValueError("no typical value at %g V for case %s rated %g V (tabulated: %s)" % (bias, key[0], key[1], sorted(row)))
