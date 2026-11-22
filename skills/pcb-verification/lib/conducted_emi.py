"""Conducted emissions (150 kHz – 30 MHz) of a buck converter on a DC power port: input-current harmonics, the input
network into a LISN (nodal model and its ngspice deck), Middlebrook damping, indicative CISPR 32 limits (numpy).
"""
import math

import numpy as np

from mode_conversion import table_limit

# LISN of CISPR 16-1-2 (50 µH / 50 Ω V-network), fixed.
LISN_L, LISN_C, R_RX = 50e-6, 0.1e-6, 50.0
V_T = 25.85e-3                       # thermal voltage at 27 °C
NODES = ("P", "N", "B", "A", "RP", "RN")
MIN_EDGE_SAMPLES = 30                # the moving average must cover a few tens of samples
# First-run ESTIMATES for a power input made of a series diode, a TVS at the connector, a TVS at the converter and a
# short track; the board table overrides each of them and tags it datasheet or estimate.
TABLE_DEFAULTS = dict(
    r_diode=None,                    # None → diode_resistance(i_diode): n·V_T / I + R_S
    n_diode=1.1, r_s_diode=0.05, i_diode=0.15,
    l_track=8e-9,                    # connector → input capacitor, ≈ 0.8 nH/mm, 10 mm
    c_tvs_connector=300e-12,         # TVS at the connector, P–N
    c_tvs_node=100e-12,              # TVS at the converter node, A–N
    esr=5e-3, esl=1.5e-9,            # each input capacitor: ESR, mounting ESL
    l_bond=50e-9,                    # board ground → earthed enclosure, when `earthed`
    l_damper=5e-9,                   # ESL of the damper branch
    esl_supply_earth=0.5e-9,         # ESL of a capacitor from the supply wire to chassis, at the connector
)
LIMITS_SOURCE = ("mains-port limits of CISPR 32 edition 2.0 / EN 55032, Annex A (similar figures in 47 CFR "
                 "part 15): indicative values commonly used, not checked against the original here, to be confirmed "
                 "in the applicable edition; on a DC power port, a reference for margin only, whether a limit applies "
                 "depends on the standard and its edition")
# (The text above is printed with every margin: the status of the limits, to be confirmed in the edition
# that applies to the product.)
# Class A: (QP, AV) dBµV per band; class B: 0.15–0.5 MHz decreasing linearly with log f.
_A = {(0.15e6, 0.5e6): (79.0, 66.0), (0.5e6, 30e6): (73.0, 60.0)}
_B_LOW = ((66.0, 56.0), (56.0, 46.0))                    # (QP, AV) at 0.15 MHz, then at 0.5 MHz
_B = {(0.5e6, 5e6): (56.0, 46.0), (5e6, 30e6): (60.0, 50.0)}
F_LO, F_HI = 0.15e6, 30e6


def diode_resistance(i, n=1.1, r_s=0.05):
    """Dynamic resistance (Ω) of the series diode conducting `i` (A): `n·V_T / i + r_s`."""
    return n * V_T / i + r_s


def input_current(vin, iout, mode, n, fsw, vout, eta, l, ipk_pfm, t_edge, forced_pwm=False, duty=None):
    """Input current of a buck over one repetition period (`n` samples, edges smoothed over `t_edge` s) and its
    harmonics. `mode` "PWM" (duty `duty`, None: the estimate Vout / (η·Vin); `forced_pwm`: the inductor current may
    reverse) or "PFM" (peak current `ipk_pfm`). Returns {"f", "mean", "harmonics" (index m: peak amplitude at m·f),
    "d", "d_source", "delta_i", "ton", "toff", "mode", "n", "edge_samples", "i"}.
    """
    vin, iout, fsw, vout, eta, l, t_edge = (float(x) for x in (vin, iout, fsw, vout, eta, l, t_edge))
    if vout >= vin:
        raise ValueError(f"buck form needs Vout < Vin, got {vout} ≥ {vin}")
    if eta > 1:
        raise ValueError(f"efficiency η must be ≤ 1, got {eta!r}")
    d_source = None
    if mode == "PWM":
        if duty is None:
            d, d_source = vout / (eta * vin), "estimate"
        else:
            d, d_source = float(duty), "declared"
            d_lo, d_hi = vout / vin, vout / (eta * vin)
            if not d_lo * (1 - 1e-3) <= d <= d_hi * (1 + 1e-3):
                raise ValueError(f"declared duty {d:.4f} outside [Vout / Vin, Vout / (η·Vin)] = [{d_lo:.4f}, "
                                 f"{d_hi:.4f}]: inconsistent with the voltages and the efficiency")
        if d >= 1:
            raise ValueError(f"duty {d:.3f} ≥ 1: outside the buck PWM form")
        delta_i = (vin - vout) * d / (l * fsw)
        if iout < delta_i / 2 and not forced_pwm:
            raise ValueError(f"PWM form outside its domain: Iout {iout:.3f} A < ΔI/2 = {delta_i / 2:.3f} A; the ramp "
                             "reverses. Declare forced PWM in the board table, or compute the PFM / discontinuous case")
        f, ton, toff = fsw, d / fsw, None
        t = np.arange(n) / (n * f)
        i = np.where(t < ton, iout - delta_i / 2 + delta_i * t / ton, 0.0)
        p_expected = vin * d * iout                            # = Pout / η with the estimated D
    elif mode == "PFM":
        ipk = ipk_pfm
        ratio = 2 * iout / ipk
        if ratio > 1 + 1e-12:
            raise ValueError(f"PFM form outside its domain: 2·Iout / Ipk = {ratio:.2f} > 1 (Iout {iout:.3f} A, Ipk "
                             f"{ipk:.3f} A): more than one pulse per period, the converter is not in PFM there")
        ton, toff = l * ipk / (vin - vout), l * ipk / vout
        f = iout / (0.5 * ipk * (ton + toff))
        d, delta_i = None, None
        t = np.arange(n) / (n * f)
        i = np.where(t < ton, ipk * t / ton, 0.0)
        p_expected = vout * iout
    else:
        raise ValueError(f"mode {mode!r}: expected 'PWM' or 'PFM'")
    k = int(round(t_edge * f * n))
    if k < MIN_EDGE_SAMPLES:
        raise ValueError(f"edge of {t_edge * 1e9:.2f} ns covers {k} samples at n = {n}: fewer than "
                         f"{MIN_EDGE_SAMPLES}; raise n")
    kernel = np.zeros(n)
    kernel[:k] = 1.0 / k
    i_s = np.real(np.fft.ifft(np.fft.fft(i) * np.fft.fft(kernel)))          # circular moving average
    mean = float(i_s.mean())
    if abs(vin * mean - p_expected) > 1e-3 * p_expected:
        raise ValueError(f"energy balance off: Vin × mean = {vin * mean:.4f} W, expected {p_expected:.4f} W")
    spec = np.fft.rfft(i_s)
    return dict(f=f, mean=mean, harmonics=2 * np.abs(spec) / n, d=d, d_source=d_source, delta_i=delta_i, ton=ton,
                toff=toff, mode=mode, n=n, edge_samples=k, i=i_s)


def lines(src, f_lo=F_LO, f_hi=F_HI, rbw=9e3):
    """Harmonics of `src` (`input_current`) in [f_lo, f_hi] Hz: list of (m, f_m, I_m peak). `rbw`: the receiver's
    resolution bandwidth (9 kHz conducted, 120 kHz radiated)."""
    f, h = src["f"], src["harmonics"]
    if f < 2 * rbw:
        raise ValueError(f"lines {f / 1e3:.2f} kHz apart, under twice the {rbw / 1e3:g} kHz bandwidth: several fall "
                         "in the receiver at once, the single-line level is not a bound")
    if (len(h) - 1) * f < f_hi:
        raise ValueError(f"n/2 · f = {(len(h) - 1) * f / 1e6:.1f} MHz does not reach {f_hi / 1e6:.0f} MHz: raise n")
    m_lo, m_hi = max(1, math.ceil(f_lo / f - 1e-9)), math.floor(f_hi / f + 1e-9)
    out = [(m, m * f, float(h[m])) for m in range(m_lo, m_hi + 1)]
    if not out:
        raise ValueError(f"no harmonic of {f / 1e3:.1f} kHz in {f_lo / 1e6}–{f_hi / 1e6} MHz")
    return out


def level_dbuv(i_peak, z_ohm):
    """Level (dBµV) at the receiver of a line of PEAK current `i_peak` through `z_ohm`, taken RMS:
    `20·log10(I_peak·Z / √2 / 1 µV)`; None for a line of zero amplitude (under every limit)."""
    v = i_peak * z_ohm
    if v == 0:
        return None
    return 20 * math.log10(v / math.sqrt(2) / 1e-6)


def fundamental_hand(iout, d):
    """Hand check of the PWM input current's fundamental, peak: `2·Iout·sin(πD) / π`."""
    return 2 * iout * math.sin(math.pi * d) / math.pi


def fitted(c_eff, l=None, dcr=0.0, f_srf=None, c_up=False, n_cap=1, damper=None, kl=1.0, bead=None,
           c_supply_earth=None, r_series=0.0, **constants):
    """The input network as built (the dict `network` reads). `c_eff`: {input voltage V: effective capacitance F of
    ONE converter capacitor}; `l`: NOMINAL filter inductor (None: none), `kl` its tolerance corner (the winding
    capacitance from `f_srf` stays the nominal part's); `bead`: (L_b, R_b) in parallel, in series with `l`; `c_up`:
    a capacitor upstream of `l`; `damper`: (C, R) across the converter capacitors; `c_supply_earth`: supply wire to
    chassis at the connector; `r_series`: in the diode branch; `constants`: overrides of `TABLE_DEFAULTS`.
    """
    unknown = set(constants) - set(TABLE_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown network constants {sorted(unknown)}; known: {sorted(TABLE_DEFAULTS)}")
    if l is None and c_up:
        raise ValueError("a capacitor upstream of no inductor is a converter capacitor: use n_cap")
    if l is None and bead is not None:
        raise ValueError("a bead is modelled in series with the filter inductor: give l")
    if l is not None and dcr == 0:
        raise ValueError("dcr = 0 with a filter inductor: a winding has a resistance; give the DCR of the part")
    net = dict(TABLE_DEFAULTS)
    net.update(constants)
    if net["r_diode"] is None:
        net["r_diode"] = diode_resistance(net["i_diode"], net["n_diode"], net["r_s_diode"])
    c_srf = None if l is None or f_srf is None else 1 / (l * (2 * math.pi * f_srf) ** 2)
    return dict(c_eff=dict(c_eff), l=None if l is None else l * kl, l_nominal=l, kl=float(kl), dcr=float(dcr),
                f_srf=f_srf, c_srf=c_srf, bead=bead, c_up=bool(c_up), n_cap=n_cap, damper=damper,
                c_supply_earth=c_supply_earth, r_series=float(r_series), **net)


def c_eff_at(filt, vin):
    """Effective capacitance declared for `vin` in `filt["c_eff"]`."""
    for v, c in filt["c_eff"].items():
        if abs(v - vin) <= 1e-6 * max(1.0, abs(v)):
            return c
    raise ValueError(f"no effective capacitance declared for Vin = {vin} V (declared: {sorted(filt['c_eff'])})")


def _stamp(y_mat, a, b, y):
    if a is not None:
        y_mat[a, a] += y
    if b is not None:
        y_mat[b, b] += y
    if a is not None and b is not None:
        y_mat[a, b] -= y
        y_mat[b, a] -= y


def network(f, vin, earthed, filt, z_wire=None):
    """Nodal admittance matrix (6 × 6, complex, earth as reference) of `filt` at `f` Hz, and the node index: P, N the
    wires at the connector (N = board ground), B after the series diode, A the converter input, RP, RN the receivers.
    `earthed`: board ground bonded to earth through `l_bond`; `z_wire`: an impedance from each wire to earth in place
    of the LISNs (receivers then unused)."""
    w = 2 * math.pi * f
    jw = 1j * w
    y_mat = np.zeros((6, 6), dtype=complex)
    p, n_, b, a, rp, rn = range(6)
    if z_wire is None:
        for wire, rx in ((p, rp), (n_, rn)):
            _stamp(y_mat, wire, None, 1 / (jw * LISN_L))
            _stamp(y_mat, wire, rx, jw * LISN_C)
            _stamp(y_mat, rx, None, 1 / R_RX)
    else:
        _stamp(y_mat, p, None, 1 / z_wire)
        _stamp(y_mat, n_, None, 1 / z_wire)
        _stamp(y_mat, rp, None, 1.0)
        _stamp(y_mat, rn, None, 1.0)
    y_cap = 1 / (filt["esr"] + jw * filt["esl"] + 1 / (jw * c_eff_at(filt, vin)))
    y_diode = 1 / (filt["r_diode"] + filt.get("r_series", 0.0) + jw * filt["l_track"])
    if filt["l"] is None:
        _stamp(y_mat, p, a, y_diode)
        _stamp(y_mat, b, None, 1.0)                                  # node unused
    else:
        _stamp(y_mat, p, b, y_diode)
        y_ind = 1 / (filt["dcr"] + jw * filt["l"])
        if filt["c_srf"] is not None:
            y_ind += jw * filt["c_srf"]
        if filt["bead"] is not None:
            l_b, r_b = filt["bead"]
            y_b = 1 / (jw * l_b) + 1 / r_b
            y_ind = y_ind * y_b / (y_ind + y_b)          # series; Re(y_ind + y_b) ≥ 1/R_b > 0
        _stamp(y_mat, b, a, y_ind)
        if filt["c_up"]:
            _stamp(y_mat, b, n_, y_cap)
    _stamp(y_mat, p, n_, jw * filt["c_tvs_connector"])
    if filt["c_supply_earth"] is not None:
        _stamp(y_mat, p, None, 1 / (jw * filt["esl_supply_earth"] + 1 / (jw * filt["c_supply_earth"])))
    _stamp(y_mat, a, n_, filt["n_cap"] * y_cap + jw * filt["c_tvs_node"])
    if filt["damper"] is not None:
        c_d, r_d = filt["damper"]
        _stamp(y_mat, a, n_, 1 / (r_d + jw * filt["l_damper"] + 1 / (jw * c_d)))
    if earthed:
        _stamp(y_mat, n_, None, 1 / (jw * filt["l_bond"]))
    return y_mat, dict(zip(NODES, range(6)))


def solve(f, vin, earthed, filt, z_wire=None, i_amp=1.0, sign=-1):
    """Node voltages {node: complex} for `i_amp` drawn by the converter from A to N (`sign=-1`) or injected into A
    (`sign=+1`)."""
    y_mat, idx = network(f, vin, earthed, filt, z_wire)
    i = np.zeros(6, dtype=complex)
    i[idx["A"]] = sign * i_amp
    i[idx["N"]] = -sign * i_amp
    v = np.linalg.solve(y_mat, i)
    return {k: complex(v[j]) for k, j in idx.items()}


def transfer(f, vin, earthed, filt):
    """|V_RP|, |V_RN| at the two receivers, in V per ampere drawn by the converter."""
    v = solve(f, vin, earthed, filt)
    return abs(v["RP"]), abs(v["RN"])


def z_out(f, vin, earthed, filt):
    """Impedance (Ω) seen by the converter between A and N at `f`, the LISN being the source."""
    v = solve(f, vin, earthed, filt, sign=+1)
    return abs(v["A"] - v["N"])


def damping(vin, p_in, filt, f_hi=3e6, per_decade=200):
    """Middlebrook check at `vin` (lowest input voltage) and `p_in` (highest input power): maximum of `z_out` over both
    ground set-ups against `zin_converter / 3`. Returns {"z_out_max", "f_max" (0.0 for a resistive plateau), "setup",
    "setups", "zin", "limit", "damped", "f_lo", "f_hi", "resonances"}."""
    zin = zin_converter(vin, p_in)
    f_hi = float(f_hi)
    if per_decade < 50:
        raise ValueError(f"per_decade must be an integer ≥ 50, got {per_decade!r}")
    c = c_eff_at(filt, vin)
    c_a = filt["n_cap"] * c + (filt["damper"][0] if filt["damper"] else 0.0) + filt["c_tvs_node"]
    c_b = c if filt["c_up"] else 0.0
    c_sum = c_a + c_b + filt["c_tvs_connector"] + 2 * LISN_C + (filt["c_supply_earth"] or 0.0)
    l_f = 0.0 if filt["l"] is None else filt["l"] + (filt["bead"][0] if filt["bead"] else 0.0)
    l_sum = 2 * LISN_L + filt["l_track"] + l_f + filt["l_bond"]
    res = {"LISN / input capacitance (earthed)": 1 / (2 * math.pi * math.sqrt(LISN_L * (c_a + c_b))),
           "both LISNs in series / input capacitance (floating)":
               1 / (2 * math.pi * math.sqrt(2 * LISN_L * (c_a + c_b)))}
    if l_f:
        res["filter inductor / converter capacitance"] = 1 / (2 * math.pi * math.sqrt(l_f * c_a))
        if c_b:
            res["filter inductor / both capacitors in series"] = 1 / (2 * math.pi * math.sqrt(l_f * c_a * c_b
                                                                                               / (c_a + c_b)))
    f_lo = min(10e3, 1 / (2 * math.pi * math.sqrt(l_sum * c_sum)) / 10)
    f_top = max(f_hi, 10 * max(res.values()))
    n = int(math.ceil(per_decade * math.log10(f_top / f_lo))) + 1
    fs = np.geomspace(f_lo, f_top, n)
    setups = {}
    for name, earthed in (("earthed", True), ("floating", False)):
        z = np.array([z_out(float(x), vin, earthed, filt) for x in fs])
        i_max = int(np.argmax(z))
        if i_max == n - 1:
            raise ValueError(f"maximum of z_out ({name}) at the end of the sweep ({fs[i_max]:.4g} Hz): the peak is "
                             "not bracketed")
        best_z, best_f, plateau = -1.0, None, False
        if i_max == 0:
            # rising towards DC: the resistance of the supply path is the maximum when z_out settles on it, a plateau
            # (well damped filter, resistance in series); anything else at the low end is a peak not bracketed
            low = [z_out(float(fs[0]) / 10 ** k, vin, earthed, filt) for k in (1, 2, 3)]
            if not (low[0] >= z[0] * (1 - 1e-9) and low[1] >= low[0] * (1 - 1e-9)
                    and abs(low[2] - low[1]) <= 1e-4 * low[2]):
                raise ValueError(f"maximum of z_out ({name}) at the end of the sweep ({fs[0]:.4g} Hz) without a "
                                 "resistive plateau under it: the peak is not bracketed")
            best_z, best_f, plateau = float(low[2]), 0.0, True
        for i in range(1, n - 1):
            if not (z[i] >= z[i - 1] and z[i] >= z[i + 1]):
                continue
            lo, hi, zp, fp = fs[i - 1], fs[i + 1], float(z[i]), float(fs[i])
            for _ in range(20):
                g = np.geomspace(lo, hi, 21)
                zz = [z_out(float(x), vin, earthed, filt) for x in g]
                j = int(np.argmax(zz))
                moved = abs(zz[j] - zp) > 1e-4 * zp
                zp, fp, lo, hi = float(zz[j]), float(g[j]), g[max(j - 1, 0)], g[min(j + 1, 20)]
                if not moved:
                    break
            if zp > best_z:
                best_z, best_f, plateau = zp, fp, False
        setups[name] = dict(z_out_max=best_z, f_max=best_f, plateau=plateau)
    worst = max(setups, key=lambda k: setups[k]["z_out_max"])
    best_z, best_f = setups[worst]["z_out_max"], setups[worst]["f_max"]
    limit = zin / 3
    return dict(z_out_max=best_z, f_max=best_f, setup=worst, setups=setups, zin=zin, limit=limit,
                damped=best_z <= limit, f_lo=f_lo, f_hi=f_top, resonances=res)


def zin_converter(vin, p_in):
    """Input impedance of the converter (Ω), `Vin² / Pin`, at the lowest input voltage and highest power."""
    return vin ** 2 / p_in


def limits(f, cls, det, table=None):
    """Limit (dBµV) at `f` Hz for class "A" / "B", detector "QP" / "AV" (indicative, `LIMITS_SOURCE`); at a band edge
    the lower limit applies. `table`: the user's limits {class: {detector: segments}} (`table_limit`), read instead."""
    if table is not None:
        return table_limit(f, table[cls][det])
    if not F_LO - 1e-6 <= f <= F_HI + 1e-6:
        raise ValueError(f"{f / 1e6:.3f} MHz outside the conducted band 0.15–30 MHz")
    col = {"QP": 0, "AV": 1}[det]
    if cls == "B" and f < 0.5e6:
        hi, lo = _B_LOW[0][col], _B_LOW[1][col]
        return hi - (hi - lo) * math.log10(f / F_LO) / math.log10(0.5 / 0.15)
    bands = {"A": _A, "B": _B}[cls]
    vals = [v[col] for (f0, f1), v in bands.items() if f0 - 1e-6 <= f <= f1 + 1e-6]
    return min(vals)                                       # at a band edge the lower limit applies


def spread_gain_db(f, delta, rbw=9e3):
    """ESTIMATE of the spread-spectrum gain (dB) of a line at `f` Hz, modulation ±`delta` (0.06 for ±6 %), receiver
    bandwidth `rbw`: (AV, QP); (0, 0) for `delta` 0. Never part of a verdict."""
    if delta == 0:
        return 0.0, 0.0
    av = max(0.0, 10 * math.log10(2 * delta * f / rbw))
    return av, av / 2


def spice_deck(vin, earthed, filt, freqs):
    """ngspice deck of the same network, 1 A AC drawn at A: per frequency of `freqs` one `ac` point and
    `print vm(rp) vm(rn)` (to compare with `transfer`)."""
    c = c_eff_at(filt, vin)
    freqs = [float(f) for f in freqs]
    lines_ = ["* LISN + input network, 1 A drawn at the converter input (generated by conducted_emi.spice_deck)",
              f"LP p 0 {LISN_L}", f"LN n 0 {LISN_L}", f"CP p rp {LISN_C}", f"RP rp 0 {R_RX}",
              f"CN n rn {LISN_C}", f"RN rn 0 {R_RX}", f"RD p x {filt['r_diode'] + filt.get('r_series', 0.0)}",
              f"CTVS1 p n {filt['c_tvs_connector']}", f"CTVS2 a n {filt['c_tvs_node']}"]
    if filt["l"] is None:
        lines_.append(f"LTR x a {filt['l_track']}")
    else:
        end = "a" if filt["bead"] is None else "m"
        lines_ += [f"LTR x b {filt['l_track']}", f"RL b bl {filt['dcr'] if filt['dcr'] > 0 else 1e-12}",
                   f"LF bl {end} {filt['l']}"]
        if filt["c_srf"] is not None:
            lines_.append(f"CSRF b {end} {filt['c_srf']}")
        if filt["bead"] is not None:
            lines_ += [f"LBEAD m a {filt['bead'][0]}", f"RBEAD m a {filt['bead'][1]}"]
        if filt["c_up"]:
            lines_ += [f"RESRU b yu {filt['esr']}", f"LESLU yu zu {filt['esl']}", f"CU zu n {c}"]
    for k in range(filt["n_cap"]):
        lines_ += [f"RESR{k} a y{k} {filt['esr']}", f"LESL{k} y{k} z{k} {filt['esl']}", f"CIN{k} z{k} n {c}"]
    if filt["damper"] is not None:
        lines_ += [f"RDMP a yd {filt['damper'][1]}", f"LDMP yd zd {filt['l_damper']}", f"CDMP zd n {filt['damper'][0]}"]
    if filt["c_supply_earth"] is not None:
        lines_ += [f"LCE p pe {filt['esl_supply_earth']}", f"CCE pe 0 {filt['c_supply_earth']}"]
    lines_.append(f"LB n 0 {filt['l_bond']}" if earthed else "RB n 0 1e12")
    lines_.append("I1 a n AC 1")
    lines_.append(".control")
    for f in freqs:
        lines_ += [f"ac lin 1 {f} {f}", "print vm(rp) vm(rn)"]
    lines_ += [".endc", ".end"]
    return "\n".join(lines_) + "\n"
