"""Board-free formulas of the power-rail check (pure Python; numpy for `ripple_bank`): regulator set-points, buck
ripple, enable instants and power-up sequence corners, power-good chaining conditions, downstream-rail bounds during
an input dip. SI units: V, A, Ω, F, H, Hz, s.
"""
import itertools
import math

_EPS = 1e-12


# ---------------------------------------------------------------- set-point and ripple

def set_point(vref, tol, rtop, rbot, rtol):
    """(nominal, minimum, maximum) of VREF × (1 + Rtop / Rbot), the VREF tolerance `tol` and resistor tolerance
    `rtol` (fractions) at their opposite corners; ripple and transients excluded."""
    nom = vref * (1 + rtop / rbot)
    lo = vref * (1 - tol) * (1 + rtop * (1 - rtol) / (rbot * (1 + rtol)))
    hi = vref * (1 + tol) * (1 + rtop * (1 + rtol) / (rbot * (1 - rtol)))
    return nom, lo, hi


def inductor_ripple(vout, vin_max, l, f_min, l_tol=0.0):
    """Peak-to-peak inductor ripple ΔI (A) of a buck in continuous conduction at the pessimistic corner (maximum
    input, L × (1 − l_tol), minimum frequency): Vout (Vin − Vout) / (Vin L f)."""
    vin, f = vin_max, f_min
    l = l * (1 - l_tol)
    if vout >= vin:
        raise ValueError("a buck needs Vout < Vin, got %g >= %g" % (vout, vin))
    return vout * (vin - vout) / (vin * l * f)


def ripple(vout, vin_max, l, f_min, c_eff, iout, l_tol=0.0, esr=None):
    """Buck ripple at the pessimistic corner of `inductor_ripple`: {"di", "i_peak" (Iout + ΔI / 2), "dv" (peak-to-peak
    over C_eff in series with `esr`, the bank's ESR at the switching frequency, required), "dv_c", "dv_esr", "l"}."""
    vin, f, c, l_nom = vin_max, f_min, c_eff, l
    l = l_nom * (1 - l_tol)
    di = inductor_ripple(vout, vin, l_nom, f, l_tol)
    # capacitor current: zero-mean triangle, rising from −ΔI/2 over t1 = D T, falling back over t2 = (1 − D) T; the
    # charge is the same at both ends of the rise. On each segment v = q / C + ESR i is a parabola: endpoints and
    # the stationary point (i / C ± ESR × slope = 0) when it falls inside.
    t1, t2 = vout / vin / f, (1 - vout / vin) / f
    v = [esr * -di / 2, esr * di / 2]                     # start and end of the rise (charge 0 at both)
    for t_seg, sign in ((t1, 1.0), (t2, -1.0)):
        s = di / t_seg                                    # |di/dt| on the segment
        i0 = -sign * di / 2
        tau = (sign * -esr * c * s - i0) / (sign * s)     # where i = ∓ESR C s
        if 0 < tau < t_seg:
            q = i0 * tau + sign * s * tau * tau / 2
            v.append(q / c + esr * (i0 + sign * s * tau))
    return {"di": di, "i_peak": iout + di / 2, "dv": max(v) - min(v), "dv_c": di / (8 * f * c), "dv_esr": di * esr,
            "l": l}


def ripple_bank(vout, vin_max, l, f_min, bank, iout, l_tol=0.0, n=4096):
    """As `ripple`, for a bank of parts that differ: `bank` = [(C_eff F, ESR Ω), …], each a series branch, the branches
    in parallel, solved harmonic by harmonic. Returns {"di", "i_peak", "dv", "l"}."""
    import numpy as np                                    # here only: the rest of the module is pure Python
    ref = ripple(vout, vin_max, l, f_min, sum(c for c, _ in bank), iout, l_tol, 0.0)
    di, f = ref["di"], f_min
    d = vout / vin_max
    tt = np.arange(n) / n                                 # one period, in units of T
    i = np.where(tt < d, -di / 2 + di * tt / d, di / 2 - di * (tt - d) / (1 - d))
    spec = np.fft.rfft(i - i.mean())
    w = 2 * math.pi * f * np.arange(1, len(spec))
    y = sum(1 / (r + 1 / (1j * w * c)) for c, r in bank)
    vs = np.zeros_like(spec)
    vs[1:] = spec[1:] / y
    v = np.fft.irfft(vs, n)
    return {"di": di, "i_peak": ref["i_peak"], "dv": float(v.max() - v.min()), "l": ref["l"]}


# ---------------------------------------------------------------- enable instant and sequence corners

def _ramp(vin, t_ramp, t):
    return vin * min(t, t_ramp) / t_ramp if t_ramp > 0 else vin


def enable_instant(vth, r, c, vin, t_ramp, t_max_tau=30.0):
    """Instant (s) at which an enable pin behind `r` (Ω) and `c` (F) from the input crosses `vth`, the input a linear
    ramp from 0 to `vin` in `t_ramp` then a plateau; without RC (r or c None or 0), vth / vin × t_ramp."""
    if vth >= vin:
        raise ValueError("threshold %g V is never reached by an input of %g V" % (vth, vin))
    if not r or not c:
        return vth / vin * t_ramp
    tau = r * c

    def step(v0, t0, h):                                  # exact response to a linear input on [t0, t0 + h]
        u0, u1 = _ramp(vin, t_ramp, t0), _ramp(vin, t_ramp, t0 + h)
        s = (u1 - u0) / h
        return u1 - s * tau + (v0 - u0 + s * tau) * math.exp(-h / tau)

    t, v = 0.0, 0.0
    t_end = t_ramp + t_max_tau * tau
    while t < t_end:
        h = min(t_ramp / 50.0 if t < t_ramp - _EPS else tau / 50.0, max(t_ramp - t, 0.0) or tau / 50.0)
        v1 = step(v, t, h)
        if v1 >= vth:
            lo, hi = 0.0, h
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if step(v, t, mid) >= vth:
                    hi = mid
                else:
                    lo = mid
            return t + 0.5 * (lo + hi)
        t, v = t + h, v1
    raise ValueError("threshold %g V not crossed within %g s" % (vth, t_end))


def _pair(r, key):
    lo, hi = r[key]
    return float(lo), float(hi)


def _rail(name, rails, vin):
    r = rails[name]
    vth, uvlo, ss = _pair(r, "vth"), _pair(r, "uvlo"), _pair(r, "soft_start")
    if uvlo[1] >= vin:
        raise ValueError("rail %r: rising UVLO up to %g V is never left by an input of %g V" % (name, uvlo[1], vin))
    if (r["r"] is None) != (r["c"] is None):
        raise ValueError("rail %r: an enable network needs both R and C, got r=%r c=%r" % (name, r["r"], r["c"]))
    out = {"vth": vth, "uvlo": uvlo, "ss": ss, "r": None, "c": None, "r_tol": 0.0, "c_tol": 0.0, "ic": r.get("ic")}
    if r["r"] is not None:
        out["r"], out["c"] = float(r["r"]), float(r["c"])
        out["r_tol"], out["c_tol"] = float(r["r_tol"]), float(r["c_tol"])
    return out


def _vin_reg(name, rails, vin):
    v = float(rails[name]["vin_reg"])
    if v >= vin:
        raise ValueError("rail %r: an input of %g V never reaches the %g V the regulator needs to hold its output"
                         % (name, vin, v))
    return v


def _start(rail, vth, uvlo, k_rc, vin, t_ramp):
    # the later of the enable crossing and the input crossing the rising UVLO (the input is the ramp itself)
    r, c = rail["r"], rail["c"]
    t_en = enable_instant(vth, (r * k_rc) if r is not None else None, c, vin, t_ramp)
    return max(t_en, uvlo / vin * t_ramp)


def sequence_corners(rails, orders, vin, t_ramp, tracking=None):
    """Margins start(B) − end(A) (s) of the required orders `orders` = [(A, B)], "A settled before B starts", at
    nominal and at the worst of the independent tolerance corners. `rails`: {name: {"vth", "uvlo" (rising UVLO of the
    input, (0, 0) without one), "soft_start": (min, max) pairs, "r", "c" (both None without an RC network), "r_tol",
    "c_tol", "vin_reg" (lowest input at which the regulator holds its set-point), "ic" (optional)}}; `tracking`: {ic:
    datasheet clause} lets the channels of that IC share their threshold, UVLO and soft-start corner. Returns {"vin",
    "t_ramp", "is_verdict" (False when an RC network has both tolerances at 0), "label", "orders": [{"a", "b",
    "nominal", "worst", "corner", "n_corners", "tracked", "correlated"}]}."""
    vin = float(vin)
    t_ramp = float(t_ramp)
    tracking = dict(tracking or {})
    orders = list(orders)
    out, verdict = [], True
    for a, b in orders:
        ra, rb = _rail(a, rails, vin), _rail(b, rails, vin)
        ra["vin_reg"], rb["vin_reg"] = _vin_reg(a, rails, vin), _vin_reg(b, rails, vin)
        for name, r in ((a, ra), (b, rb)):
            if r["r"] is not None and r["r_tol"] == 0 and r["c_tol"] == 0:
                verdict = False
        ka = ((1 - ra["r_tol"]) * (1 - ra["c_tol"]), (1 + ra["r_tol"]) * (1 + ra["c_tol"]))
        kb = ((1 - rb["r_tol"]) * (1 - rb["c_tol"]), (1 + rb["r_tol"]) * (1 + rb["c_tol"]))
        same_ic = ra["ic"] is not None and ra["ic"] == rb["ic"]
        tracked = same_ic and ra["ic"] in tracking

        def margin(vth_a, vth_b, uv_a, uv_b, ss_a, k_a, k_b):
            settled_a = max(_start(ra, vth_a, uv_a, k_a, vin, t_ramp) + ss_a, ra["vin_reg"] / vin * t_ramp)
            return _start(rb, vth_b, uv_b, k_b, vin, t_ramp) - settled_a

        mid = lambda pair: sum(pair) / 2  # noqa: E731
        nominal = margin(mid(ra["vth"]), mid(rb["vth"]), mid(ra["uvlo"]), mid(rb["uvlo"]), mid(ra["ss"]), 1.0, 1.0)
        worst, corner, n = math.inf, None, 0
        for vth_a, vth_b, uv_a, uv_b, ss_a, k_a, k_b in itertools.product(
                set(ra["vth"]), set(rb["vth"]), set(ra["uvlo"]), set(rb["uvlo"]), set(ra["ss"]), set(ka), set(kb)):
            n += 1
            m = margin(vth_a, vth_b, uv_a, uv_b, ss_a, k_a, k_b)
            if m < worst:
                worst, corner = m, {"vth_a": vth_a, "vth_b": vth_b, "uvlo_a": uv_a, "uvlo_b": uv_b,
                                    "soft_start_a": ss_a, "rc_a": k_a, "rc_b": k_b}
        correlated = None
        if same_ic:
            inside = lambda x, key: all(r[key][0] - _EPS <= x <= r[key][1] + _EPS for r in (ra, rb))  # noqa: E731
            correlated, c_corner = math.inf, None
            for vth, uv, ss_a, k_a, k_b in itertools.product(set(ra["vth"]) | set(rb["vth"]),
                                                             set(ra["uvlo"]) | set(rb["uvlo"]), set(ra["ss"]),
                                                             set(ka), set(kb)):
                if inside(vth, "vth") and inside(uv, "uvlo"):
                    m = margin(vth, vth, uv, uv, ss_a, k_a, k_b)
                    if m < correlated:
                        correlated, c_corner = m, {"vth_a": vth, "vth_b": vth, "uvlo_a": uv, "uvlo_b": uv,
                                                   "soft_start_a": ss_a, "rc_a": k_a, "rc_b": k_b}
            if correlated is math.inf:
                correlated = None
        if tracked and correlated is not None:       # the corner returned is the one that gives the correlated margin
            worst, corner = correlated, dict(c_corner, tracking=tracking[ra["ic"]])
        out.append({"a": a, "b": b, "nominal": nominal, "worst": worst, "corner": corner, "n_corners": n,
                    "tracked": tracked, "correlated": correlated})
    return {"vin": vin, "t_ramp": t_ramp, "is_verdict": verdict,
            "label": "at the tolerance corners" if verdict else "at nominal R and C: not a verdict", "orders": out}


def sequence_verdict(result):
    """{"verdict": "pass" | "fail", "decided_by": [orders with a negative worst margin]} from `sequence_corners`."""
    if not result.get("orders"):
        raise ValueError("corner table without any order")
    if not result.get("is_verdict"):
        raise ValueError("corner table %s: put the R and C tolerances in before asking a verdict" % result.get("label"))
    failed = ["%s -> %s" % (o["a"], o["b"]) for o in result["orders"] if o["worst"] < 0]
    return {"verdict": "fail" if failed else "pass", "decided_by": failed}


# ---------------------------------------------------------------- power-good chaining

def chain_matches(read, required, enable_capacitance_f=None):
    """True when the chain read from the board, [(converter, [rails it waits for])], equals the required one in any
    order; `enable_capacitance_f`: {converter: F} on chained enables, refused when > 0."""
    for conv, c in (enable_capacitance_f or {}).items():
        if c > 0:
            raise ValueError("a capacitor (%g F) sits on the chained enable of %s: the level model does not apply" % (c, conv))
    norm = lambda chain: sorted((str(k), tuple(sorted(str(x) for x in v))) for k, v in chain)  # noqa: E731
    return norm(read) == norm(required)


def power_good_chain_conditions(v_pullup, r_pullup, v_in_low, en_off_max, en_on_min, pg_low_v, pg_low_test_i,
                                pg_sink_max, pin_abs_max, pg_valid_from_v, leakage_a, enable_capacitance_f=0.0):
    """Conditions of a sequence chained by open-drain power goods pulled up to the input rail: a list of {"label",
    "value", "limit", "direction" ("<=", ">=", or None for an informative line), "ok", "estimate"}, for
    `judge_conditions`. `v_in_low`: the lowest input at which a converter runs (lockout); `leakage_a`: power-good
    leakage of every output on the node + enable input current."""
    if enable_capacitance_f > 0:
        raise ValueError("a capacitor sits on a chained enable: the level model does not apply")
    vp, r, vlow, off, on, pgl, pgi, sink, pin, valid, leak = map(float, (
        v_pullup, r_pullup, v_in_low, en_off_max, en_on_min, pg_low_v, pg_low_test_i, pg_sink_max, pin_abs_max,
        pg_valid_from_v, leakage_a))
    i_pu = vp / r                                # upper bound: the transistor may pull below its guaranteed VOL
    released_low = vlow - leak * r
    cond = lambda label, value, limit, direction, estimate=False: {
        "label": label, "value": value, "limit": limit, "direction": direction, "estimate": estimate,
        "ok": None if direction is None else (value <= limit + _EPS if direction == "<=" else value >= limit - _EPS)}
    return [
        cond("power-good held low, guaranteed level (V) <= enable guaranteed-off threshold", pgl, off, "<="),
        cond("held-low level guaranteed at the pull-up current: pull-up current (A) <= test current of the "
             "guaranteed low level", i_pu, pgi, "<="),
        cond("held-low level at the pull-up current (V), proportional to the test current, estimate",
             pgl * i_pu / pgi, off, None, True),
        cond("enable released at the lowest input, lockout minus declared leakage x R (V) >= enable guaranteed-on threshold",
             released_low, on, ">="),
        cond("released level at the pull-up rail (V)", vp - leak * r, on, None),
        cond("leakage tolerated at the lowest input (A)", (vlow - on) / r, leak, None),
        cond("leakage tolerated at the pull-up rail (A)", (vp - on) / r, leak, None),
        cond("pull-up current at the highest rail (A) <= power-good sink current", i_pu, sink, "<="),
        cond("pull-up rail (V) <= absolute maximum of the power-good and enable pins", vp, pin, "<="),
        cond("power good valid from an input (V) <= lowest lockout", valid, vlow, "<="),
    ]


def judge_conditions(conditions):
    """{"verdict": "pass" | "fail", "decided_by": [labels], "at_equality": [labels with zero margin]} over the judged
    lines (direction not None)."""
    judged = [c for c in conditions if c["direction"] is not None]
    if not judged:
        raise ValueError("no judged condition")
    failed = [c["label"] for c in judged if not c["ok"]]
    equal = [c["label"] for c in judged if c["ok"] and abs(c["value"] - c["limit"]) <= _EPS]
    return {"verdict": "fail" if failed else "pass", "decided_by": failed, "at_equality": equal}


# ---------------------------------------------------------------- downstream rail during a dip

def downstream_bounds(vin_min, i_load, rds_on, dcr, v_reg_min, t_under, c_eff, ktol=1.0, i_factor=1.0,
                      rds_factor=1.0, allows_100pct_duty=True):
    """Bounds (V) of a downstream rail while its input dips to `vin_min` for `t_under`: (a) 100 % duty cycle, Vin_min −
    I (RDS(on) + DCR) capped at `v_reg_min`; (b) output capacitors alone, V_reg_min − I t / (C_eff ktol), ktol the low
    corner. `i_factor`, `rds_factor`: margins on I and RDS(on). Returns {"a", "b", "bound" (the lower), "i", "rds"}."""
    vin, vreg, t, c, k = vin_min, v_reg_min, t_under, c_eff, ktol
    i = i_load * i_factor
    rds = rds_on * rds_factor
    if not k <= 1:
        raise ValueError("ktol is the low capacitance corner, in ]0, 1], got %r" % k)
    a = min(vin - i * (rds + dcr), vreg) if allows_100pct_duty else None
    b = vreg - i * t / (c * k)
    bound = b if a is None else min(a, b)
    return {"a": a, "b": b, "bound": bound, "i": i, "rds": rds}
