"""Surge / ESD formulas (pure Python): two-point TVS fit and its ngspice DC check, ground-return inductances, adiabatic
heating, order-of-magnitude currents, trace measurements, and the IEC 61000-4-2 / -4-5 generator checks.
Units: V, A, Ω, mm, µm, nH, K, s; Vt = 25.85 mV.
"""
import math

VT = 0.02585            # thermal voltage, V, 300 K
RHO_CU = 1.7e-8         # Ω·m
CV_CU = 3.45e6          # J/(m³·K)
I2T_FACTOR_8_20 = 0.7   # ∫i²dt ≈ 0.7 · Ipk² · T50 for an 8/20 µs wave (estimate)
T50_8_20_S = 20e-6

# The IEC 61000-4-2 generator of models/esd_iec61000-4-2.lib into the 2 Ω target, per kV of charge (fitted values).
ESD_PER_KV = {"peak_a": 3.71, "rise_ns": 0.88, "i30_a": 2.08, "i60_a": 1.06}
# Nominal values per kV and tolerances of the IEC 61000-4-2 contact-discharge current: indicative values commonly
# used (as in esd_fit.py), to be confirmed in the applicable edition.
ESD_STANDARD = {"peak_a": (3.75, 0.15), "rise_ns": (0.80, 0.25), "i30_a": (2.00, 0.30), "i60_a": (1.00, 0.30)}
# The IEC 61000-4-5 generator of models/cwg_iec61000-4-5.lib, re-checked alone: front / half-value times in µs.
CWG_CHECK = {"open_circuit_us": (1.20, 50.0), "short_circuit_us": (7.82, 20.4), "ratio_ohm": 2.000}
# Nominal values and indicative tolerances of the IEC 61000-4-5 waveform definition (front / half-value times in µs,
# Ûoc / Îsc in Ω, short-circuit undershoot as a fraction of the peak, a maximum), to be confirmed in the applicable edition.
CWG_STANDARD = {"open_circuit_us": ((1.2, 0.30), (50.0, 0.20)), "short_circuit_us": ((8.0, 0.20), (20.0, 0.20)),
                "ratio_ohm": (2.0, 0.10), "undershoot_max": 0.30}


# --- avalanche TVS: two-point fit --------------------------------------------------------------------------------
def avalanche_fit(v1, i1, v2, i2, nbv=1.0, ibv=1e-3):
    """(RS, BV) of a SPICE diode `D(RS BV IBV NBV)` in breakdown through the published points (v1, i1), (v2, i2):
    RS = (V2 − V1 − NBV·Vt·ln(I2/I1)) / (I2 − I1), BV = V1 − RS·I1 − NBV·Vt·ln(I1/IBV)."""
    v1, i1, v2, i2, nbv, ibv = map(float, (v1, i1, v2, i2, nbv, ibv))
    rs = (v2 - v1 - nbv * VT * math.log(i2 / i1)) / (i2 - i1)
    if rs <= 0:
        raise ValueError(f"RS = {rs:.4f} Ω ≤ 0: the two points are not on one avalanche branch")
    bv = v1 - rs * i1 - nbv * VT * math.log(i1 / ibv)
    if bv <= 0:
        raise ValueError(f"BV = {bv:.3f} V ≤ 0: check the points and IBV")
    return rs, bv


def line_fit(v1, i1, v2, i2):
    """(RS, BV) of the straight line through the two points (i1 < i2), BV at zero current; about 0.2 V above the
    points once the model's log term is added (pessimistic)."""
    v1, i1, v2, i2 = map(float, (v1, i1, v2, i2))
    if i2 <= i1 or v2 <= v1:
        raise ValueError(f"points must be in increasing current and voltage: ({v1}, {i1}), ({v2}, {i2})")
    rs = (v2 - v1) / (i2 - i1)
    bv = v1 - rs * i1
    if bv <= 0:
        raise ValueError(f"BV = {bv:.3f} V ≤ 0")
    return rs, bv


def quick_fit(v1_at_1a, v2, i2):
    """`line_fit` with V1 read at 1 A."""
    return line_fit(v1_at_1a, 1.0, v2, i2)


def predicted_voltage(rs, bv, i, nbv=1.0, ibv=1e-3):
    """Voltage across a diode `D(RS BV IBV NBV)` conducting `i` in breakdown: BV + NBV·Vt·ln(I/IBV) + RS·I."""
    rs, bv, i = float(rs), float(bv), float(i)
    return bv + float(nbv) * VT * math.log(i / float(ibv)) + rs * i


def model_line(name, rs, bv, is_a=1e-9, n=1.5, ibv=1e-3, nbv=1.0, cjo_f=None):
    """`.model <name> D(IS=… N=… RS=… BV=… IBV=… NBV=… [CJO=…])`, RS with 4 decimals, BV with 2."""
    parts = [f"IS={is_a:g}", f"N={n:g}", f"RS={rs:.4f}", f"BV={bv:.2f}", f"IBV={ibv:g}", f"NBV={nbv:g}"]
    if cjo_f is not None:
        parts.append(f"CJO={cjo_f:g}")
    return f".model {name} D({' '.join(parts)})"


def dc_check_netlist(model_lines, currents_a, blocking_model=None):
    """ngspice netlist of the DC sweep (smallest to largest current, 100 steps) that re-checks an avalanche model at
    its published points. `model_lines`: the `.model` text(s), the avalanche model first; `blocking_model`: the name
    of one of them, added in series. Avalanche voltage `v(p)` (`v(k)` without a blocking diode), whole branch `v(k)`."""
    currents = sorted(float(c) for c in currents_a)
    if len(set(currents)) < 2:
        raise ValueError("give at least two distinct currents (the published points)")
    lines = model_lines.splitlines() if isinstance(model_lines, str) else list(model_lines)
    names = [line.split()[1] for line in lines if line.split() and line.split()[0].lower() == ".model"]
    aval = names[0]
    step = (currents[-1] - currents[0]) / 100.0
    text = ["* DC check of an avalanche model at its published points (tvs_fit.dc_check_netlist)"]
    text += lines
    text.append(f"Isrc 0 k {currents[0]}")
    if blocking_model:
        text.append(f"Dblk k p {blocking_model}")
        text.append(f"Daval 0 p {aval}")
        probe = "v(k) v(p)"
    else:
        text.append(f"Daval 0 k {aval}")
        probe = "v(k)"
    text.append(f".dc Isrc {currents[0]:g} {currents[-1]:g} {step:g}")
    text.append(".control\nrun\nprint " + probe + "\n.endc\n.end")
    return "\n".join(text)


# --- ground returns, heating, order-of-magnitude checks --------------------------------------------------------
def via_nh(h_mm, d_mm):
    """Partial inductance of a via (nH), estimate: 0.2·h·(ln(4h/d) + 1), h = length, d = hole diameter (mm)."""
    h, d = float(h_mm), float(d_mm)
    if d >= 4 * h:
        raise ValueError(f"hole {d} mm is not small against the length {h} mm: the formula does not apply")
    return 0.2 * h * (math.log(4 * h / d) + 1)


def track_nh(length_mm, nh_per_mm=0.6):
    """Inductance (nH) of a short return track; the default 0.6 nH/mm is a screening value for a narrow track over a
    close plane."""
    return float(length_mm) * float(nh_per_mm)


def return_path_nh(track_mm, via_h_mm=None, via_d_mm=None, vias=None, nh_per_mm=0.6):
    """Ground return of a protection (nH): track at `nh_per_mm` (as `track_nh`) plus `vias` identical vias in series
    (one when the via geometry is given without a count)."""
    total = track_nh(track_mm, nh_per_mm)
    if via_h_mm is None and via_d_mm is None:
        if vias is not None:
            raise ValueError(f"vias={vias!r} given without the via length and hole diameter")
        return total
    return total + int(1 if vias is None else vias) * via_nh(via_h_mm, via_d_mm)


def i2t_8_20(i_peak, t50=T50_8_20_S, k=I2T_FACTOR_8_20):
    """∫i²dt (A²·s) of an 8/20 µs wave of peak `i_peak`, ≈ k Ipk² T50: an estimate."""
    return float(k) * float(i_peak) ** 2 * float(t50)


def adiabatic_heating(i2t, width_mm, t_m, rho=RHO_CU, cv=CV_CU):
    """Temperature rise (K) of a track carrying ∫i²dt with no time to cool: ΔT = ρ ∫i²dt / (A² cv), A = width × t_m."""
    a = float(width_mm) * 1e-3 * float(t_m)
    return float(rho) * float(i2t) / (a * a * float(cv))


def adiabatic_rise_k(i_pk_a, width_mm, thickness_um, t50_s=T50_8_20_S, i2t_factor=I2T_FACTOR_8_20):
    """Adiabatic heating (K) of a copper connection by one 8/20 µs pulse of peak `i_pk_a`."""
    return adiabatic_heating(i2t_8_20(i_pk_a, t50_s, i2t_factor), width_mm, float(thickness_um) * 1e-6)


def common_mode_source_ohm(generator_ohm=2.0, coupling_ohm=80.0, lines=2):
    """Source impedance seen by the common mode of a symmetric pair: generator + coupling resistor / lines."""
    return float(generator_ohm) + float(coupling_ohm) / int(lines)


def hand_check_earth_current(upk_v, clamp_v, source_ohm=42.0, tvs_count=2):
    """(earth-lead current, current per TVS) = (Upk − Vclamp) / R, order of magnitude."""
    upk, vc = float(upk_v), float(clamp_v)
    if vc >= upk:
        raise ValueError("clamping voltage above the applied peak: nothing flows")
    i = (upk - vc) / float(source_ohm)
    return i, i / int(tvs_count)


def time_beyond(t_s, v, limit_v):
    """Time (s) a sampled trace spends beyond ±`limit_v`, on |v|, linear between samples (for an asymmetric limit,
    pass the excess over each bound)."""
    t, y = [float(x) for x in t_s], [float(x) for x in v]
    if len(t) != len(y):
        raise ValueError(f"time and voltage differ in length ({len(t)} and {len(y)})")
    if len(t) < 2:
        raise ValueError("a trace needs at least two samples")
    if any(b <= a for a, b in zip(t, t[1:])):
        raise ValueError("time must be strictly increasing")
    lim = float(limit_v)

    def above(a, b):                                      # fraction of the segment a → b where the line is > lim
        if a > lim and b > lim:
            return 1.0
        if a <= lim and b <= lim:
            return 0.0
        s = (lim - a) / (b - a)
        return s if a > lim else 1.0 - s
    return sum((t1 - t0) * (above(a, b) + above(-a, -b)) for t0, t1, a, b in zip(t, t[1:], y, y[1:]))


def rail_ratios(v, lower_v, upper_v):
    """A rail trace against the bounds of its absolute maximum ratings (lower_v < 0 < upper_v): {"max_v", "min_v",
    "upper": max / upper, "lower": min / lower, "worst"}; a ratio above 1 is a fail."""
    y = [float(x) for x in v]
    hi, lo = float(upper_v), float(lower_v)
    out = {"max_v": max(y), "min_v": min(y), "upper": max(y) / hi, "lower": min(y) / lo}
    out["worst"] = max(out["upper"], out["lower"])
    return out


# --- generator checks -------------------------------------------------------------------------------------------
def esd_expected(kv):
    """What the fitted generator gives into 2 Ω at `kv` (linear scaling of ESD_PER_KV): {"peak_a", "rise_ns",
    "i30_a", "i60_a"}."""
    k = float(kv)
    return {"peak_a": ESD_PER_KV["peak_a"] * k, "rise_ns": ESD_PER_KV["rise_ns"],
            "i30_a": ESD_PER_KV["i30_a"] * k, "i60_a": ESD_PER_KV["i60_a"] * k}


def esd_check(kv, peak_a, rise_ns, i30_a, i60_a):
    """A measured set (peak, 10–90 % rise, currents at 30 and 60 ns) against `ESD_STANDARD`; returns {quantity:
    (value, nominal, tolerance, ok)}, ValueError if one is outside."""
    k = float(kv)
    got = {"peak_a": peak_a, "rise_ns": rise_ns, "i30_a": i30_a, "i60_a": i60_a}
    out, bad = {}, []
    for key, (nominal, tol) in ESD_STANDARD.items():
        nom = nominal * (k if key != "rise_ns" else 1.0)
        val = float(got[key])
        ok = abs(val - nom) <= tol * nom
        out[key] = (val, nom, tol, ok)
        if not ok:
            bad.append(f"{key} = {val:g} for {nom:g} ± {tol:.0%}")
    if bad:
        raise ValueError("ESD generator outside IEC 61000-4-2: " + "; ".join(bad))
    return out


def cwg_check(oc_front_us, oc_half_us, sc_front_us, sc_half_us, ratio_ohm, undershoot=None):
    """A measured or fitted IEC 61000-4-5 set (times in µs, Ûoc / Îsc in Ω, undershoot as a fraction of the peak)
    against `CWG_STANDARD`; returns {quantity: (value, nominal or maximum, tolerance or None, ok)}, ValueError if one
    is outside."""
    got = {"oc_front_us": oc_front_us, "oc_half_us": oc_half_us, "sc_front_us": sc_front_us,
           "sc_half_us": sc_half_us, "ratio_ohm": ratio_ohm}
    (ocf, och), (scf, sch) = CWG_STANDARD["open_circuit_us"], CWG_STANDARD["short_circuit_us"]
    nominal = {"oc_front_us": ocf, "oc_half_us": och, "sc_front_us": scf, "sc_half_us": sch,
               "ratio_ohm": CWG_STANDARD["ratio_ohm"]}
    out, bad = {}, []
    for key, (nom, tol) in nominal.items():
        val = float(got[key])
        ok = abs(val - nom) <= tol * nom
        out[key] = (val, nom, tol, ok)
        if not ok:
            bad.append(f"{key} = {val:g} for {nom:g} ± {tol:.0%}")
    if undershoot is not None:
        u, u_max = float(undershoot), CWG_STANDARD["undershoot_max"]
        out["undershoot"] = (u, u_max, None, u <= u_max)
        if u > u_max:
            bad.append(f"undershoot = {u:.0%} for at most {u_max:.0%}")
    if bad:
        raise ValueError("combination wave generator outside IEC 61000-4-5: " + "; ".join(bad))
    return out
