"""Clock edge on a lossless line as a ladder of L-C cells solved in state space (numpy, scipy): `Net` describes the
topology, `simulate` returns the response to a ramp at the probed nodes, `metrics` / `edges` read the edge and the
false edges at the receiver's thresholds. Units: Ω, s/mm, mm, F, H, s, V.
"""
import numpy as np
from scipy.signal import lsim


class Net:
    """Lumped network: a capacitance to ground per node, series R-L branches between nodes (node -1 = source).
    `tpd` in s/mm, `dseg` the cell length in mm."""
    def __init__(self, z0, tpd, dseg=0.5):               # Ω, s/mm, mm
        z0, tpd, dseg = float(z0), float(tpd), float(dseg)
        self.cap, self.br = [], []                       # C per node (F); branches (a, b, R, L)
        self.lseg, self.cseg, self.dseg = z0 * tpd * dseg, tpd * dseg / z0, dseg

    def node(self, c=0.0):
        self.cap.append(float(c))
        return len(self.cap) - 1

    def branch(self, a, b, r, l):
        n = len(self.cap)
        if not -1 <= a < n or not 0 <= b < n:     # a negative index would silently address another state
            raise ValueError(f"branch ({a!r}, {b!r}): node index in [-1, {n - 1}] for a, [0, {n - 1}] for b expected "
                             "(a = -1: the source)")
        self.br.append((a, b, float(r), float(l)))

    def line(self, a, length_mm, c_end=0.0):
        """Ladder of L-C cells from node a; returns the far-end node, loaded by c_end."""
        n = a
        for _ in range(max(1, round(length_mm / self.dseg))):
            m = self.node(self.cseg)
            self.branch(n, m, 0.0, self.lseg)
            n = m
        self.cap[n] += c_end
        return n


def simulate(net, probes, tr, vdd=3.3, t_end=12e-9, dt=1e-12):    # vdd: a 3.3 V example, pass the driver's supply
    """One rising edge of 10–90 % time `tr` from 1 ns. Returns (t, v) with one row of `v` per node of `probes`."""
    if any(not 0 <= p < len(net.cap) for p in probes):     # -1 would silently read a branch current
        raise ValueError(f"probes must be node indices in [0, {len(net.cap) - 1}], got {probes!r}")
    n, nb = len(net.cap), len(net.br)
    cap = np.array(net.cap)
    cap[cap == 0] = 1e-15                                # a node without capacitance would make A singular
    A, B = np.zeros((n + nb, n + nb)), np.zeros((n + nb, 1))
    for k, (a, b, r, l) in enumerate(net.br):
        i = n + k                                        # L di/dt = v_a − v_b − R i
        if a >= 0:
            A[a, i] -= 1 / cap[a]                        # C_a dv_a/dt = −i
            A[i, a] += 1 / l
        else:
            B[i, 0] += 1 / l                             # v_a is the source
        A[b, i] += 1 / cap[b]                            # C_b dv_b/dt = +i
        A[i, b] -= 1 / l
        A[i, i] -= r / l
    t = np.arange(0, t_end, dt)
    u = np.clip((t - 1e-9) / (tr / 0.8), 0, 1) * vdd     # ramp starting at 1 ns; its 10–90 % time is tr
    C = np.zeros((len(probes), n + nb))
    C[np.arange(len(probes)), probes] = 1
    _, y, _ = lsim((A, B, C, np.zeros((len(probes), 1))), u, t)
    return t, np.atleast_2d(y.T)


def _edge(x, lo, hi, back_max):
    """State of one rising crossing of the band lo-hi: no step back while crossing it, and no return once past hi."""
    i_l, i_h = int(np.argmax(x >= lo)), int(np.argmax(x >= hi))
    band = x[i_l:i_h + 1]
    back = float((np.maximum.accumulate(band) - band).max())      # non-monotonic inside the band
    dip = float(x[i_h:].min())                                    # lowest point once the upper threshold is passed
    if dip <= lo:                                                 # the band crossed again: before any step back
        return "false edge"
    return "band" if back > back_max or dip < hi else "clean"


def _wave(v, what):
    v = np.asarray(v, dtype=float)
    if v.ndim != 1:                                      # e.g. the whole 2-D output of `simulate`
        raise ValueError(f"{what} must be a 1-D sequence, got shape {v.shape}")
    return v


def edges(v, vil, vih, vdd=3.3, back_max=0.01):
    """States of the rising edge and of the falling one (mirror vdd − v: symmetrical driver assumed) at the thresholds
    VIL-VIH: 'clean', 'band' (a step back or a return inside the band: receiver-dependent) or 'false edge' (the band
    crossed again). `back_max` (V): step back ignored, a numerical tolerance, not a receiver hysteresis."""
    v = _wave(v, "waveform")
    if not 0 < vil < vih < vdd:
        raise ValueError(f"inconsistent thresholds: VIL {vil} V, VIH {vih} V, VDD {vdd} V")
    if v.max() < vih or (vdd - v).min() > vil:
        raise ValueError(f"edge does not complete: {v.min():.2f} to {v.max():.2f} V for {vil} / {vih} V")
    return _edge(v, vil, vih, back_max), _edge(v, vdd - vih, vdd - vil, back_max)   # the fall, seen on the mirror


def metrics(t, v, vil=0.6, vih=1.2, vdd=3.3, back_max=0.01):    # 3.3 V LVCMOS examples: replace by the datasheet's
    """Edge 10–90 % (ns), overshoot (% of vdd), ringback and the states of both edges (`edges`): {"tr_ns",
    "overshoot_pct", "ringback_min_V", "rising_edge", "falling_edge", "no_false_edge"}."""
    t, v = _wave(t, "times"), _wave(v, "waveform")

    def cross(level):                                    # first crossing, linear interpolation
        i = int(np.argmax(v >= level))
        if v[i] < level or i == 0:
            raise ValueError(f"level {level:.2f} V never reached")
        return t[i - 1] + (level - v[i - 1]) * (t[i] - t[i - 1]) / (v[i] - v[i - 1])
    t10, t90 = cross(0.1 * vdd), cross(0.9 * vdd)
    after = v[t >= t90]                                  # displayed only: lowest point once 90 % is reached
    rise, fall = edges(v, vil, vih, vdd, back_max)
    return {"tr_ns": float(t90 - t10) * 1e9, "overshoot_pct": float(100 * (v.max() - vdd) / vdd),
            "ringback_min_V": float(after.min()), "rising_edge": rise, "falling_edge": fall,
            "no_false_edge": rise == "clean" and fall == "clean"}
