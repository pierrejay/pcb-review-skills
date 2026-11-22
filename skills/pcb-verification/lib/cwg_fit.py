"""IEC 61000-4-5 combination wave generator: fit of a lumped model (Cc, Rs1, Rm, Lr, Rs2) on the 1.2/50 µs open-circuit
and 8/20 µs short-circuit waves (2 Ω); run as a script (venv) to write models/cwg_iec61000-4-5.lib, written only when
`tvs_fit.cwg_check` accepts the fit.
"""
from pathlib import Path

import numpy as np
from scipy.linalg import expm
from scipy.optimize import least_squares

from tvs_fit import cwg_check

HERE = Path(__file__).resolve().parent
T = np.linspace(0, 600e-6, 60001)
PARAMS = ("Cc", "Rs1", "Rm", "Lr", "Rs2")


def waves(p):
    cc, rs1, rm, lr, rs2 = p
    out = {}
    for mode in ("oc", "sc"):
        # states: [Va, IL]
        if mode == "oc":
            a = np.array([[-1 / (rs1 * cc), -1 / cc], [1 / lr, -(rm + rs2) / lr]])
        else:
            a = np.array([[-1 / (rs1 * cc), -1 / cc], [1 / lr, -rm / lr]])
        step = expm(a * (T[1] - T[0]))
        x = np.array([1.0, 0.0])
        y = np.empty_like(T)
        for i in range(len(T)):
            y[i] = x[1] * rs2 if mode == "oc" else x[1]
            x = step @ x
        out[mode] = y
    return out


def _cross(ym, level, start=0, rising=True):
    """Interpolated crossing time (smooth objective for the optimiser)."""
    seg = ym[start:]
    idx = np.argmax(seg >= level) if rising else np.argmax(seg <= level)
    if idx == 0 or (rising and not (seg >= level).any()) or (not rising and not (seg <= level).any()):
        return None
    i = start + idx
    y0, y1 = ym[i - 1], ym[i]
    return T[i - 1] + (level - y0) * (T[i] - T[i - 1]) / (y1 - y0)


def times(y, lo, hi, factor):
    """(front time = `factor` × time between the `lo` and `hi` crossings of the edge, duration from the virtual origin
    to the tail's 50 % crossing) in s, of a waveform sampled on `T`; a tail above 50 % to the end gives 2 × T[-1]."""
    y = np.asarray(y, dtype=float)
    if y.shape != T.shape:
        raise ValueError(f"waveform must be {T.size} samples, one per instant of T, got shape {y.shape}")
    ym = y / y.max()
    ip = int(ym.argmax())
    tlo, thi = _cross(ym, lo), _cross(ym, hi)
    o = tlo - lo * (thi - tlo) / (hi - lo)
    t50 = _cross(ym, 0.5, ip, rising=False)
    if t50 is None:  # never below 50 % within the window: penalise
        t50 = 2 * T[-1]
    return factor * (thi - tlo), t50 - o


def residual(logp):
    w = waves(np.exp(logp))
    t1o, t2o = times(w["oc"], 0.3, 0.9, 1.67)
    t1s, t2s = times(w["sc"], 0.1, 0.9, 1.25)
    z = w["oc"].max() / w["sc"].max()
    under = -w["sc"].min() / w["sc"].max()  # short-circuit current undershoot
    return [(t1o - 1.2e-6) / 1.2e-6, (t2o - 50e-6) / 50e-6, (t1s - 8e-6) / 8e-6,
            (t2s - 20e-6) / 20e-6, (z - 2.0) / 2.0, max(0.0, under - 0.25) * 4]


def main():
    best = None
    for start in ([20e-6, 4.0, 0.8, 10e-6, 26.0], [10e-6, 8.0, 1.0, 12e-6, 20.0], [30e-6, 3.0, 0.5, 8e-6, 30.0]):
        r = least_squares(residual, np.log(start), diff_step=1e-3)
        if best is None or r.cost < best.cost:
            best = r
    r = best
    cc, rs1, rm, lr, rs2 = np.exp(r.x)
    w = waves(np.exp(r.x))
    t1o, t2o = times(w["oc"], 0.3, 0.9, 1.67)
    t1s, t2s = times(w["sc"], 0.1, 0.9, 1.25)
    k = 1 / w["oc"].max()  # U0 per volt of open-circuit peak
    print(f"Cc={cc*1e6:.2f} µF Rs1={rs1:.2f} Ω Rm={rm:.3f} Ω Lr={lr*1e6:.2f} µH Rs2={rs2:.2f} Ω")
    print(f"OC {t1o*1e6:.2f}/{t2o*1e6:.1f} µs ; SC {t1s*1e6:.2f}/{t2s*1e6:.1f} µs ; Z={w['oc'].max()/w['sc'].max():.3f} Ω ; "
          f"SC undershoot {-100*w['sc'].min()/w['sc'].max():.0f} % ; U0/Ûoc={k:.4f}")
    z, under = w["oc"].max() / w["sc"].max(), -w["sc"].min() / w["sc"].max()
    try:                                # a generator outside the standard's tolerances is not published
        cwg_check(t1o * 1e6, t2o * 1e6, t1s * 1e6, t2s * 1e6, z, under)
    except ValueError as e:
        raise SystemExit(f"model not written: {e}")
    (HERE / "models" / "cwg_iec61000-4-5.lib").write_text(f"""* IEC 61000-4-5 combination wave generator (1.2/50 µs OC, 8/20 µs SC, 2 Ω), fitted by cwg_fit.py
* OC {t1o*1e6:.2f}/{t2o*1e6:.1f} µs ; SC {t1s*1e6:.2f}/{t2s*1e6:.1f} µs ; Ûoc/Îsc = {w['oc'].max()/w['sc'].max():.3f} Ω
* Usage: XCWG out ref CWG params: UPK=<open-circuit peak voltage, signed> TD=<delay>
.subckt CWG out ref params: UPK=1000 TD=1u
* before TD: Cc charged to U0 by Vchg (S1 closed), output isolated (S2 open); at TD: S1 opens, S2 closes
Vchg a ref {{UPK*{k:.6f}}}
S1 a nc c1 ref SWC
Vc1 c1 ref PWL(0 1 {{TD}} 1 {{TD+1n}} 0)
S2 nc nm c2 ref SWC
Vc2 c2 ref PWL(0 0 {{TD}} 0 {{TD+1n}} 1)
.model SWC SW(Ron=1m Roff=1e12 Vt=0.5 Vh=0)
Cc nc ref {cc:.6g}
Rs1 nc ref {rs1:.6g}
Rm nm nl {rm:.6g}
Lr nl out {lr:.6g}
Rs2 out ref {rs2:.6g}
.ends CWG
""")


if __name__ == "__main__":
    main()
