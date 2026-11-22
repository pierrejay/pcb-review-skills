"""Radiated emissions, 30 MHz – 1 GHz, as orders of magnitude (numpy): indicative CISPR 32 field limits at 10 m,
admissible common-mode current per cable, clock-loop field, line-code and power-cable common mode. SI units; currents
and fields RMS (a peak harmonic is divided by √2 before comparison); field ×2 for the ground reflection.
"""
import math

import numpy as np

from mode_conversion import env, table_limit  # noqa: F401  (env re-exported; the pure-Python definition is the reference)

LIMIT_SOURCE = ("CISPR 32 class A / B radiated limits at 10 m, quasi-peak: indicative values commonly used, to be "
                "confirmed in the applicable edition (similar figures in 47 CFR part 15)")
_LIMITS = {"A": (40.0, 47.0), "B": (30.0, 37.0)}        # dBµV/m, 30–230 MHz then 230–1 000 MHz
F_LO, F_HI, F_SPLIT = 30e6, 1e9, 230e6
K_LOOP = 1.316e-14                                       # E = K·f²·A·I / r for a small loop (far field)
K_CABLE = 1.257e-6                                       # short monopole/dipole factor: E = K·f·L·I / r
CABLE_CAP = 60.0                                         # resonant half-wave cap of K·f·L
GROUND_REFLECTION = 2.0
QP_NOISE_DB = 7.0                                        # quasi-peak of a noise-like signal: ESTIMATE


def dbuv_m(e):
    """V/m → dBµV/m."""
    return 20 * math.log10(e / 1e-6)


def limit(f, cls, table=None):
    """Field limit (dBµV/m, quasi-peak at 10 m) at `f` Hz, class "A" / "B" (indicative, `LIMIT_SOURCE`); at 230 MHz
    the lower limit applies. `table`: the user's limits {class: segments} (`table_limit`), read instead."""
    if table is not None:
        return table_limit(f, table[cls])
    if not F_LO - 1e-3 <= f <= F_HI + 1e-3:
        raise ValueError(f"{f / 1e6:.1f} MHz outside the radiated band 30 MHz – 1 GHz")
    lo, hi = _LIMITS[cls]
    return hi if f > F_SPLIT + 1e-3 else lo


def cable_factor(f, l_cable=1.0):
    """`min(1.257·10⁻⁶·f·L, 60)`, f in Hz, L in m."""
    return min(K_CABLE * f * l_cable, CABLE_CAP)


def cable_field(f, i_cm, r=10.0, l_cable=1.0):
    """Field (V/m) of a common-mode current `i_cm` (A RMS) on `l_cable` m of cable at `r` m: `2·cable_factor·I / r`."""
    return GROUND_REFLECTION * cable_factor(f, l_cable) * i_cm / r


def i_adm(f, cls, r=10.0, l_cable=1.0, table=None):
    """Admissible common-mode current (A RMS, as a current probe reads it) for the class limit at 10 m:
    `E_lim·r / (2·cable_factor)`; another `r` does not give the admissible current of a test at that distance."""
    e_lim = 10 ** (limit(f, cls, table) / 20) * 1e-6
    return e_lim * r / (GROUND_REFLECTION * cable_factor(f, l_cable))


def margin_db(i_adm_, i_cm):
    """`20·log10(i_adm / i_cm)`, positive under the limit; None for `i_cm = 0` (met: judge on the currents)."""
    return None if i_cm == 0 else 20 * math.log10(i_adm_ / i_cm)


def min_margin(i_cm_of_f, cls, f_lo=F_LO, f_hi=F_HI, breakpoints=(), r=10.0, l_cable=1.0, table=None,
               per_decade=500):
    """Minimum margin over [f_lo, f_hi] Hz of a common-mode current `i_cm_of_f(f)` (A RMS) to `i_adm`, swept with the
    cable-factor cap, the class transition, the table's edges and the source's own `breakpoints` included. Returns
    {"margin_db", "f", "i_cm", "i_adm", "met"}; margin_db and f None when the current is zero everywhere."""
    if per_decade < 50:
        raise ValueError(f"per_decade must be an integer ≥ 50, got {per_decade!r}")
    edges = [CABLE_CAP / (K_CABLE * l_cable), F_SPLIT]
    if table is not None and cls in table:
        edges += [e for seg in table[cls] for e in seg[:2]]
    edges += list(breakpoints)
    n = int(math.ceil(per_decade * math.log10(f_hi / f_lo))) + 1
    fs = np.unique(np.concatenate([np.geomspace(f_lo, f_hi, n), [e for e in edges if f_lo <= e <= f_hi]]))

    def at(f):
        i = float(i_cm_of_f(float(f)))
        if not i >= 0:                     # a NaN would be skipped below and the band read as met
            raise ValueError(f"common-mode current at {float(f):.6g} Hz must be a finite number ≥ 0, got {i!r}")
        a = i_adm(float(f), cls, r, l_cable, table)
        return (math.inf if i == 0 else 20 * math.log10(a / i)), i, a

    vals = [at(f) for f in fs]
    met = all(i <= a for _, i, a in vals)
    m = [v[0] for v in vals]
    best = None
    for k in range(len(fs)):
        if not math.isfinite(m[k]) or (k > 0 and m[k] > m[k - 1]) or (k < len(fs) - 1 and m[k] > m[k + 1]):
            continue
        cand = (m[k], float(fs[k]), vals[k][1], vals[k][2])
        lo, hi = fs[max(k - 1, 0)], fs[min(k + 1, len(fs) - 1)]
        for _ in range(30):
            if hi <= lo:
                break
            g = np.geomspace(lo, hi, 21)
            gv = [at(x) for x in g]
            met = met and all(i <= a for _, i, a in gv)
            j = min(range(21), key=lambda q: gv[q][0])
            moved = cand[0] - gv[j][0] > 1e-3
            if gv[j][0] < cand[0]:
                cand = (gv[j][0], float(g[j]), gv[j][1], gv[j][2])
            lo, hi = g[max(j - 1, 0)], g[min(j + 1, 20)]
            if not moved:
                break
        if best is None or cand[0] < best[0]:
            best = cand
    if best is None:
        return dict(margin_db=None, f=None, i_cm=0.0, i_adm=None, met=True)
    return dict(margin_db=best[0], f=best[1], i_cm=best[2], i_adm=best[3], met=met and best[0] >= 0)


def loop_field(f0, swing, length_mm, h_mm, t_edge, c_in, c_per_mm, n_max=None, r=10.0, cls="B", f_lo=F_LO, f_hi=F_HI,
               table=None):
    """Differential-mode loop field of a clock trace (`length_mm` over a plane `h_mm` below), odd harmonics of a 50 %
    trapezoid of `swing` V, `t_edge` the whole linear edge (s); the line charges `c_in + length × c_per_mm` (F, F/mm).
    `n_max` only caps the harmonics, which follow the band. Returns {"area_mm2", "harmonics": [(n, f, V_n peak, I_n
    RMS, E dBµV/m, margin dB)], "worst"}."""
    if 2 * t_edge * f0 > 1 + 1e-12:
        raise ValueError(f"t_edge {t_edge * 1e9:g} ns longer than half the period {0.5e9 / f0:g} ns: a 50 % trapezoid "
                         "cannot reach its swing (a period or a 10–90 % time typed for the edge?)")
    n_band = int(math.floor(f_hi / f0))
    if n_max is None:
        n_max = n_band
    elif int(n_max) * f0 < f_hi - 1e-9:
        raise ValueError(f"n_max {int(n_max)} covers {int(n_max) * f0 / 1e6:.0f} MHz of a band to {f_hi / 1e6:.0f} MHz: "
                         "let it follow the band (n_max=None) or lower f_hi")
    area = length_mm * 1e-3 * h_mm * 1e-3
    c = c_in + length_mm * c_per_mm
    out = []
    for n in range(1, int(n_max) + 1, 2):
        f = n * f0
        if f < f_lo:
            continue
        if f > f_hi:
            break
        v_n = 2 * swing / (n * math.pi) * abs(np.sinc(n * t_edge * f0))      # np.sinc(x) = sin(πx)/(πx), peak
        i_n = 2 * math.pi * f * c * v_n / math.sqrt(2)                       # RMS: the limits are RMS-calibrated
        e = GROUND_REFLECTION * K_LOOP * f * f * area * i_n / r
        e_db = dbuv_m(e)
        out.append((n, f, v_n, i_n, e_db, limit(f, cls, table) - e_db))
    return dict(area_mm2=length_mm * h_mm, harmonics=out, worst=min(out, key=lambda h: h[5]))


def v_rx(f, v_rms, t_symbol, rbw=120e3, qp_db=QP_NOISE_DB):
    """What the receiver sees (V) in `rbw` of a random line code, RMS `v_rms`, symbol period `t_symbol`:
    `√(2·V²·T·RBW)·env(f·T)·10^(qp_db / 20)`, an upper bound with a quasi-peak ESTIMATE; then `I_CM = v_rx·k / z_cm`."""
    return math.sqrt(2 * v_rms ** 2 * t_symbol * rbw) * env(f * t_symbol) * 10 ** (qp_db / 20)


def i_cm_wires(v_p, v_n, z_wire):
    """Common-mode current (A) of a two-wire cable from its node voltages: `|V_P + V_N| / |Z_w|`."""
    return abs(v_p + v_n) / abs(z_wire)


def power_cable_cm(src, vin, filt, est_z_wire=300.0, r=10.0, l_cable=1.0, f_lo=F_LO, f_hi=F_HI, delta=0.0, table=None):
    """Common mode on the power cable from the converter harmonics `src` (`conducted_emi.input_current`) through
    `filt` (`conducted_emi.fitted`), each wire `est_z_wire` to earth (an ESTIMATE), board ground bonded. Returns
    {"lines": [(f, I_CM, E dBµV/m, margin A, margin B, spread QP gain)], "worst_a", "n_above_a", "n_zero"}; a line of
    zero amplitude has None field and margins."""
    import conducted_emi as ce
    out = []
    for m, f, i_m in ce.lines(src, f_lo, f_hi, rbw=120e3):
        v = ce.solve(f, vin, True, filt, z_wire=est_z_wire, i_amp=i_m)
        i_cm = i_cm_wires(v["P"], v["N"], est_z_wire) / math.sqrt(2)      # peak harmonic → RMS
        lim_a, lim_b = limit(f, "A", table), limit(f, "B", table)
        e = cable_field(f, i_cm, r, l_cable)
        e_db = dbuv_m(e) if e > 0 else None
        out.append((f, i_cm, e_db, None if e_db is None else lim_a - e_db, None if e_db is None else lim_b - e_db,
                    ce.spread_gain_db(f, delta, 120e3)[1]))
    judged = [h for h in out if h[3] is not None]
    return dict(lines=out, worst_a=min(judged, key=lambda h: h[3]) if judged else None,
                n_above_a=sum(1 for h in judged if h[3] < 0), n_zero=len(out) - len(judged))
