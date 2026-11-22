"""Impedance seen from a supply pin: local capacitors in parallel with a path inductance to the bulk capacitors and the
regulator (numpy). Each capacitor is (C effective in F, ESL in H, ESR in Ω).
"""
import numpy as np

BANDS = [(1e4, 1e6), (1e6, 1e7), (1e7, 1e8), (1e8, 1e9)]


def _branch(f, c, l, r):
    w = 2 * np.pi * f
    return r + 1j * w * l + 1 / (1j * w * c)


def _par(*zs):
    # parallel combination; a branch of zero impedance shorts the others: 0 there
    zs = np.broadcast_arrays(*(np.asarray(z, dtype=complex) for z in zs))
    short = np.zeros(zs[0].shape, dtype=bool)
    for z in zs:
        short |= z == 0
    y = sum(np.divide(1, z, out=np.zeros_like(z), where=~short) for z in zs)
    return np.divide(1, y, out=np.zeros_like(y), where=~short)


def pin_impedance(f, local, path_h, bulk, reg_r=0.07, reg_l=0.1e-6):
    """|Z| (Ω) at f (Hz). local, bulk: [(C F, ESL H, ESR Ω), …]; path_h: inductance pin → bulk (H). `reg_r`, `reg_l`
    are estimates of the regulator's output resistance and loop inductance."""
    f = np.atleast_1d(np.asarray(f, dtype=float))
    w = 2 * np.pi * f
    far = _par(*(_branch(f, *c) for c in bulk), reg_r + 1j * w * reg_l)
    seen = far + 1j * w * path_h
    return np.abs(_par(seen, *(_branch(f, *c) for c in local))) if local else np.abs(seen)


def bands(f, z):
    """Maximum of |Z| (Ω) of `z` over each band of `BANDS` (f in Hz), keyed "a-b MHz"."""
    f, z = np.asarray(f, dtype=float), np.asarray(z, dtype=float)
    if not np.isfinite(z).all():
        raise ValueError("an impedance value is not finite")
    out = {}
    for a, b in BANDS:
        sel = (f >= a) & (f <= b)
        out[f"{a / 1e6:g}-{b / 1e6:g} MHz"] = float(z[sel].max())
    return out
