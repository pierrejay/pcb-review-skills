"""Clock compatibility on paper (guaranteed source figures against receiver requirements), lumped-line cell values
equal to `clockline.Net`, and the DC level of a strap pin sharing its net. Pure Python: KiCad's Python 3.9 or the venv.
"""
import math

VERDICT_PASS = "pass"
VERDICT_NO_MARGIN = "pass, no margin: to measure"
VERDICT_FAIL = "fails on paper, effect to be measured"
VERDICT_DEFINITION = "not comparable: different definitions"
VERDICT_NOTHING = "nothing stated by the receiver"
VERDICT_UNPUBLISHED = "not published by the source: to measure"
VERDICT_TYPICAL = "typical only, not guaranteed: to measure"
_EPS = 1e-12


def _spec(name, spec, side, keys):
    # an unknown key, an inverted interval or a ± figure mixed with bounds would be read silently as something else
    unknown = set(spec) - set(keys) - {"definition"}
    if unknown:
        raise ValueError(f"{name}: the {side} figure has unknown keys {sorted(unknown)} (expected {keys})")
    if "min" in spec and "max" in spec and spec["min"] > spec["max"]:
        raise ValueError(f"{name}: the {side} min {spec['min']} > max {spec['max']}")
    if "abs" in spec and (spec["abs"] < 0 or "min" in spec or "max" in spec):
        raise ValueError(f"{name}: the {side} ± figure must be ≥ 0 and alone (no min or max with it), got {spec!r}")


def compare_row(name, required, guaranteed):
    """One row. `required`: None (nothing stated) or {"max"} / {"min"} / {"min", "max"} / {"abs"} (a ± tolerance);
    `guaranteed`: None (not published), the same forms or {"typ"}; both may carry a jitter "definition". Returns
    {"name", "verdict" (one of the VERDICT_* strings), "required", "guaranteed"}."""
    row = {"name": name, "required": required, "guaranteed": guaranteed}
    if required is None:
        row["verdict"] = VERDICT_NOTHING
        return row
    _spec(name, required, "required", ("min", "max", "abs"))
    if guaranteed is not None:
        _spec(name, guaranteed, "guaranteed", ("min", "max", "abs", "typ"))
    if guaranteed is None:
        row["verdict"] = VERDICT_UNPUBLISHED
        return row
    if set(guaranteed) - {"definition"} == {"typ"}:
        row["verdict"] = VERDICT_TYPICAL
        return row
    if required.get("definition") != guaranteed.get("definition"):
        row["verdict"] = VERDICT_DEFINITION
        return row
    checks = []                                       # (ok, equal)
    if "abs" in required:
        checks.append((guaranteed["abs"] <= required["abs"] + _EPS, abs(guaranteed["abs"] - required["abs"]) <= _EPS))
    else:
        for key, sign in (("max", 1), ("min", -1)):
            if key in required:
                g = guaranteed[key]
                checks.append((sign * (g - required[key]) <= _EPS, abs(g - required[key]) <= _EPS))
    if not checks:
        raise ValueError(f"{name}: requirement {required!r} has no min, max or abs")
    if not all(ok for ok, _ in checks):
        row["verdict"] = VERDICT_FAIL
    elif any(eq for _, eq in checks):
        row["verdict"] = VERDICT_NO_MARGIN
    else:
        row["verdict"] = VERDICT_PASS
    return row


def compare(rows):
    """[(name, required, guaranteed), …] → {"rows", "fails" (names), "to_measure" (names)}."""
    if not rows:
        raise ValueError(f"no row to compare, got {rows!r}")
    out = [compare_row(*r) for r in rows]
    fails = [r["name"] for r in out if r["verdict"] == VERDICT_FAIL]
    measure = [r["name"] for r in out if r["verdict"] in
               (VERDICT_NO_MARGIN, VERDICT_DEFINITION, VERDICT_UNPUBLISHED, VERDICT_TYPICAL)]
    return {"rows": out, "fails": fails, "to_measure": measure}


def line_cells(z0, tpd_s_per_mm, dseg_mm=0.5):
    """Cell values of `clockline.Net(z0, tpd, dseg)`: {"l_cell" (H), "c_cell" (F), "dseg_mm", "cells"},
    `cells(length_mm)` the cell count of `Net.line`, max(1, round(length / d))."""

    def cells(length_mm):
        return max(1, round(length_mm / dseg_mm))

    return {"l_cell": z0 * tpd_s_per_mm * dseg_mm, "c_cell": tpd_s_per_mm * dseg_mm / z0, "dseg_mm": dseg_mm,
            "cells": cells}


def strap_level(branches, vil, vih):
    """DC level of a pin fed by resistive branches: [(name, v_source, r_ohm, v_f)] for a resistor (v_f 0), [(name,
    v_source, r_ohm, v_f, direction)] for a branch with an LED, direction "to_pin" (anode on the source side) or
    "from_pin" (anode on the pin side). Returns {"v", "state" ("low", "high", "undetermined"), "branches_on"}."""
    if not 0 < vil < vih:
        raise ValueError(f"thresholds must satisfy 0 < VIL < VIH, got {vil!r}, {vih!r}")
    norm = []
    for b in branches:
        name, v, r, vf = b[:4]
        d = b[4] if len(b) == 5 else None
        if vf > 0 and d not in ("to_pin", "from_pin"):
            raise ValueError(f"branch {name!r}: an LED needs its direction, 'to_pin' (anode on the source side) or "
                             f"'from_pin' (anode on the pin side), got {d!r}")
        norm.append((name, v, r, vf, d))
    branches = norm

    def v_eff_of(v, vf, d):
        return v if vf == 0 else (v - vf if d == "to_pin" else v + vf)

    def conducts(v, vf, d, v_pin):
        """A plain resistor always; an LED only beyond its drop, in its own direction."""
        return vf == 0 or (v - v_pin > vf + _EPS if d == "to_pin" else v_pin - v > vf + _EPS)

    # the current into the pin is affine between the break points of the LEDs (where one starts to conduct): on each
    # segment the conducting set is fixed and the zero of the current is the divider of that set
    breaks = sorted({v_eff_of(v, vf, d) for _, v, _, vf, d in branches if vf > 0})
    edges = [-math.inf] + breaks + [math.inf]
    roots = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        probe = ((lo + hi) / 2 if math.isfinite(lo) and math.isfinite(hi)
                 else hi - 1.0 if math.isfinite(hi) else lo + 1.0 if math.isfinite(lo) else 0.0)
        on = [conducts(v, vf, d, probe) for _, v, _, vf, d in branches]
        den = sum(1.0 / r for (_, _, r, _, _), a in zip(branches, on) if a)
        if den == 0:
            raise ValueError(f"no branch conducts with the pin between {lo:.3g} and {hi:.3g} V: the pin floats, "
                             "no DC level")
        x = sum(v_eff_of(v, vf, d) / r for (_, v, r, vf, d), a in zip(branches, on) if a) / den
        if lo - 1e-9 <= x <= hi + 1e-9:
            roots.append(x)
    v_pin = roots[0]
    on = [conducts(v, vf, d, v_pin) for _, v, _, vf, d in branches]
    state = "low" if v_pin <= vil + _EPS else "high" if v_pin >= vih - _EPS else "undetermined"
    return {"v": v_pin, "state": state, "branches_on": [b[0] for b, a in zip(branches, on) if a]}
