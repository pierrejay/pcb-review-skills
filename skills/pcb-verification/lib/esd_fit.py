"""IEC 61000-4-2 ESD generator: fit of a two-branch lumped model (Cs 150 pF / Rs 330 Ω / Ls, fast branch Cf / Rf / Lf)
on the standard's analytical waveform into 2 Ω; run as a script (venv) to write models/esd_iec61000-4-2.lib, written
only when the fit meets the standard's tolerances.
"""
from pathlib import Path

import numpy as np
from scipy.linalg import expm
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
CS, RS, RLOAD = 150e-12, 330.0, 2.0
T = np.linspace(0, 150e-9, 3001)
PARAMS = ("Cf", "Rf", "Lf", "Ls")


def heidler_ref(t, kv=1.0):
    """Reference current (A) of the IEC 61000-4-2 contact-discharge waveform at `t` (s, scalar or array), scaled
    linearly from its 4 kV parameters to `kv`."""
    t = np.asarray(t, dtype=float)
    i1, i2, t1, t2, t3, t4, n = 16.6, 9.3, 1.1e-9, 2e-9, 12e-9, 37e-9, 1.8
    k1 = np.exp(-(t1 / t2) * (n * t2 / t1) ** (1 / n))
    k2 = np.exp(-(t3 / t4) * (n * t4 / t3) ** (1 / n))
    i = (i1 / k1 * (t / t1) ** n / (1 + (t / t1) ** n) * np.exp(-t / t2)
         + i2 / k2 * (t / t3) ** n / (1 + (t / t3) ** n) * np.exp(-t / t4))
    return (i * kv / 4.0)[()]


def model_current(p, v0=1000.0, rload=RLOAD):
    """Output current (A) of the model on `T`, Cs and Cf charged to `v0` (V), into `rload` (Ω); p = (Cf, Rf, Lf, Ls)."""
    cf, rf, lf, ls = p
    # states: [Vcs, Vcf, iLs, iLf]; output: v_out = rload * (iLs + iLf)
    a = np.array([
        [0, 0, -1 / CS, 0],
        [0, 0, 0, -1 / cf],
        [1 / ls, 0, -(RS + rload) / ls, -rload / ls],
        [0, 1 / lf, -rload / lf, -(rf + rload) / lf],
    ])
    step = expm(a * (T[1] - T[0]))
    x = np.array([v0, v0, 0.0, 0.0])
    out = np.empty_like(T)
    for k in range(len(T)):
        out[k] = x[2] + x[3]
        x = step @ x
    return out


def criteria(i, t=T):
    """(first peak A, 10–90 % rise time s, current at 30 ns A, current at 60 ns A) of a trace `i` sampled on `t`."""
    i, t = np.asarray(i, dtype=float), np.asarray(t, dtype=float)
    ip = i.max()
    if t[0] > 30e-9 or t[-1] < 60e-9:
        raise ValueError(f"time axis {t[0]:g} to {t[-1]:g} s does not contain 30 and 60 ns: the currents there are "
                         "not in the trace")
    if i[0] >= 0.1 * ip:
        raise ValueError(f"first current sample {i[0]:g} A is not under 10 % of the peak {ip:g} A: the rise is not "
                         "in the trace")
    k = int(i.argmax())
    t10 = np.interp(0.1 * ip, i[:k + 1], t[:k + 1])
    t90 = np.interp(0.9 * ip, i[:k + 1], t[:k + 1])
    return ip, t90 - t10, np.interp(30e-9, t, i), np.interp(60e-9, t, i)


def residual(logp):
    i = model_current(np.exp(logp))
    ref = heidler_ref(T)
    ip, tr, i30, i60 = criteria(i)
    shape = (i - ref) / ref.max()
    return np.concatenate([shape[::10], [(ip - 3.75) / 3.75 * 3, (tr - 0.8e-9) / 0.8e-9,
                                         (i30 - 2.0) / 2.0 * 3, (i60 - 1.0) / 1.0 * 3]])


def main():
    ref = heidler_ref(T)
    print("Annex B reference (per kV): Ip {:.2f} A, tr {:.2f} ns, I30 {:.2f} A, I60 {:.2f} A".format(
        *[v * (1e9 if j == 1 else 1) for j, v in enumerate(criteria(ref))]))
    best = None
    for start in ([5e-12, 60.0, 20e-9, 400e-9], [10e-12, 30.0, 10e-9, 800e-9], [3e-12, 100.0, 5e-9, 200e-9]):
        r = least_squares(residual, np.log(start), diff_step=1e-3)
        if best is None or r.cost < best.cost:
            best = r
    cf, rf, lf, ls = np.exp(best.x)
    ip, tr, i30, i60 = criteria(model_current(np.exp(best.x)))
    ok = [abs(ip - 3.75) <= 0.15 * 3.75, abs(tr - 0.8e-9) <= 0.25 * 0.8e-9,
          abs(i30 - 2) <= 0.3 * 2, abs(i60 - 1) <= 0.3 * 1]
    print(f"Model: Cf={cf*1e12:.2f} pF Rf={rf:.1f} Ω Lf={lf*1e9:.2f} nH Ls={ls*1e9:.1f} nH")
    print(f"Model (per kV, 2 Ω target): Ip {ip:.2f} A, tr {tr*1e9:.2f} ns, I30 {i30:.2f} A, I60 {i60:.2f} A ; "
          f"criteria {'all met' if all(ok) else 'NOT met ' + str(ok)}")
    if not all(ok):                     # a generator outside the standard's tolerances is not published
        raise SystemExit("annex B criteria not met: model not written")
    (HERE / "models" / "esd_iec61000-4-2.lib").write_text(f"""* IEC 61000-4-2 ESD generator (contact), fitted by esd_fit.py on annex B of the standard
* 2 Ω target, per kV: Ip {ip:.2f} A, tr {tr*1e9:.2f} ns, I30 {i30:.2f} A, I60 {i60:.2f} A
* Usage: XESD out ref ESDGUN params: VCH=<charge voltage, signed>; ".tran ... uic" analysis mandatory
* Cs and Cf start charged to VCH (initial condition): the discharge starts at t = 0.
.subckt ESDGUN out ref params: VCH=4000
Cs ns ref 150p IC={{VCH}}
Cf nf ref {cf:.6g} IC={{VCH}}
Rs ns ls1 330
Ls ls1 out {ls:.6g}
Rf nf lf1 {rf:.6g}
Lf lf1 out {lf:.6g}
.ends ESDGUN
""")


if __name__ == "__main__":
    main()
