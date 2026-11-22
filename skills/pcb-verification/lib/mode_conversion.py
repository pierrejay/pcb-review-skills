"""Passive network of a PHY port: mode conversion, return loss (fixed or ladder topology), selection ranges, conducted
common-mode emission and injection, user limit tables (`table_limit`). Pure Python: KiCad's Python 3.9 or the venv.
"""
import math

_TWO_PI = 2 * math.pi


def _coupling(coupling):
    # only sources referenced to ground behind rs are modelled; a transformer winding is not two resistors to ground
    if coupling != "capacitor":
        raise ValueError(f"coupling {coupling!r}: only 'capacitor' is modelled (sources referenced to ground behind "
                         "rs); a transformer-coupled port is not (report the conversion as incomplete)")


def conversion(f, ca, cb, rs=50.0, dr=0.0, z_cm=150.0, coupling="capacitor"):
    """Mode-conversion ratio `k = |V_cm| / |V_dm|` of the port at `f` Hz: `ca`, `cb` each line's capacitance to ground
    (F), series resistors `rs·(1 + dr)` and `rs·(1 − dr)`, `z_cm` the cable's common-mode impedance (100 Ω
    differential). Closed form: exactly 0 for a symmetric port."""
    _coupling(coupling)
    w = _TWO_PI * f
    g_a, g_b = 1 / (rs * (1 + dr)), 1 / (rs * (1 - dr))
    g_l, g_m = 1 / 50.0, 1 / (z_cm - 25.0)
    ya, yb = g_a + 1j * w * ca + g_l, g_b + 1j * w * cb + g_l
    s = 2 * g_l + g_m
    rhs = g_a / (2 * ya) - g_b / (2 * yb)                       # exactly 0 when the two lines are identical
    v_sum = rhs / (1 - g_l * g_l / s * (1 / ya + 1 / yb))
    v_m = g_l * v_sum / s
    v_a = (g_a / 2 + g_l * v_m) / ya
    v_b = (-g_b / 2 + g_l * v_m) / yb
    v_dm = abs(v_a - v_b)
    return abs(v_sum / 2) / v_dm


def conversion_db(f, ca, cb, rs=50.0, dr=0.0, z_cm=150.0, coupling="capacitor"):
    """`−20·log10(conversion(...))` in dB (the larger, the better); `math.inf` for an exactly symmetric port."""
    k = conversion(f, ca, cb, rs, dr, z_cm, coupling)
    return math.inf if k == 0 else -20 * math.log10(k)


def return_loss_db(f, r_tx, c_array, c_couple, l_leak_half, c_shunt, zref=50.0):
    """Return loss (dB) at `f` Hz of the half circuit of a capacitor-coupled pair seen from the connector: `r_tx` ∥
    `c_array`, then `c_couple` and HALF the choke's leakage `l_leak_half` in series, ∥ `c_shunt`; 0 for an absent
    capacitor or leakage; `zref` = Zdiff / 2."""
    w = _TWO_PI * f
    z = r_tx
    if c_array > 0:
        z = 1 / (1 / z + 1j * w * c_array)
    z = z + 1 / (1j * w * c_couple) + 1j * w * l_leak_half
    if c_shunt > 0:
        z = 1 / (1 / z + 1j * w * c_shunt)
    gamma = abs((z - zref) / (z + zref))
    return math.inf if gamma == 0 else -20 * math.log10(gamma)


def ladder_impedance(f, ladder):
    """Impedance (complex, Ω) at `f` Hz of a half circuit built from the IC outwards. `ladder` = [(kind, connection,
    value), …]: kind "R" (Ω), "L" (H), "C" (F) with connection "series" or "shunt", or ("T", "ideal", n) an ideal
    transformer, n = cable-side / IC-side turns, referring what precedes it to the cable side. Half-circuit values: an
    element between the two lines enters at half its R or L, twice its C; a shunt C of 0 is skipped."""
    w = _TWO_PI * f
    z = None
    for element in ladder:
        kind, conn, value = element
        if kind == "T":
            z = z * value ** 2
            continue
        if kind == "R":
            ze = float(value)
        elif kind == "L":
            ze = 1j * w * value
        elif kind == "C":
            if conn == "shunt" and value == 0:
                continue
            ze = 1 / (1j * w * value)
        else:
            raise ValueError(f"unknown element kind {kind!r} (R, L or C)")
        if conn == "series":
            z = ze if z is None else z + ze
        elif conn == "shunt":
            y = 1 / z + 1 / ze
            z = 1 / y
        else:
            raise ValueError(f"unknown connection {conn!r} (series or shunt)")
    return z


def ladder_return_loss_db(f, ladder, zref=50.0):
    """Return loss (dB) of the half circuit `ladder` (`ladder_impedance`) against `zref` = Zdiff / 2."""
    z = ladder_impedance(f, ladder)
    gamma = abs((z - zref) / (z + zref))
    return math.inf if gamma == 0 else -20 * math.log10(gamma)


def in_range(nominal, low, high, component_max=None):
    """Selection range judged on the NOMINAL value, an upper bound also on `component_max` (datasheet maximum) when
    given; a None bound is open. Returns (nominal_ok, guaranteed_ok)."""

    def ok(x):
        return (low is None or x >= low) and (high is None or x <= high)

    return ok(nominal), ok(component_max if component_max is not None else nominal)


def env(x):
    """Envelope of |sinc(x)|, `sinc(x) = sin(πx) / (πx)`: sinc up to x = 0.5, `1 / (πx)` beyond; env(0) = 1."""
    if x == 0:
        return 1.0
    if x <= 0.5:
        return math.sin(math.pi * x) / (math.pi * x)
    return 1 / (math.pi * x)


def density_dbuv(v_rms, t_symbol, rbw):
    """Density (dBµV) of a random line code, RMS `v_rms` (V), symbol period `t_symbol` (s), in `rbw` (Hz):
    `10·log10(2·V²·T·RBW)`."""
    return 10 * math.log10(2 * v_rms ** 2 * t_symbol * rbw) + 120


def density_flat_dbuv(v_rms, bandwidth, rbw):
    """Order of magnitude (dBµV) of a signal spread evenly over `bandwidth` (Hz): `10·log10(V²·RBW / bandwidth)`."""
    return 10 * math.log10(v_rms ** 2 * rbw / bandwidth) + 120


def cm_level_dbuv(f, v_rms, t_symbol, conversion_db_, rbw=9e3, qp_db=7.0):
    """Conducted common-mode level (dBµV) of the port at `f` Hz: `density_dbuv + 20·log10(env(f·T)) + qp_db −
    conversion_db_` (`qp_db`: quasi-peak ESTIMATE of a noise-like signal); None when `conversion_db_` is `math.inf`."""
    if conversion_db_ == math.inf:
        return None
    return density_dbuv(v_rms, t_symbol, rbw) + 20 * math.log10(env(f * t_symbol)) + qp_db \
        - conversion_db_


CM_LIMIT_SOURCE = {"B": "CISPR 32 class B, common-mode voltage of a network port, quasi-peak, cross-checked",
                   "A": "CISPR 32 class A, common-mode voltage of a network port, quasi-peak: indicative, to be confirmed in the applicable edition"}
_CM = {"B": (84.0, 74.0), "A": (97.0, 87.0)}             # dBµV at 0.15 MHz, then from 0.5 to 30 MHz


def table_limit(f, segments):
    """Limit (dB) at `f` Hz from a user table `segments` = [(f_lo Hz, f_hi Hz, dB at f_lo, dB at f_hi), …], linear in
    log f inside a segment; at a frequency shared by two segments the lower value applies."""
    segs = []
    for s in segments:
        lo, hi = float(s[0]), float(s[1])
        a, b = float(s[2]), float(s[3])
        segs.append((lo, hi, a, b))
    segs.sort()
    for s1, s2 in zip(segs, segs[1:]):
        if s2[0] < s1[1]:
            raise ValueError(f"overlapping limit segments {s1[:2]} and {s2[:2]} Hz")
    tol = 1e-9 * f
    vals = [a + (b - a) * min(1.0, max(0.0, math.log10(f / lo) / math.log10(hi / lo)))
            for lo, hi, a, b in segs if lo - tol <= f <= hi + tol]
    if not vals:
        raise ValueError(f"{f / 1e6:.3f} MHz outside the limit table ({segs[0][0] / 1e6:g}–{segs[-1][1] / 1e6:g} MHz)")
    return min(vals)


def cm_limit_dbuv(f, cls, table=None):
    """Common-mode voltage limit (dBµV, quasi-peak) of a network port at `f` Hz, class "A" / "B" (indicative,
    `CM_LIMIT_SOURCE`; only on cables longer than 3 m). `table`: the user's limits {class: segments}, read instead."""
    if table is not None:
        return table_limit(f, table[cls])
    if not 0.15e6 - 1e-6 <= f <= 30e6 + 1e-6:
        raise ValueError(f"{f / 1e6:.3f} MHz outside 0.15–30 MHz")
    hi, lo = _CM[cls]
    if f >= 0.5e6:
        return lo
    return hi - (hi - lo) * math.log10(f / 0.15e6) / math.log10(0.5 / 0.15)


def injection(f, ca, cb, rs=50.0, dr=0.0, z_cm=150.0, coupling="capacitor"):
    """Reverse excitation: 1 V EMF at the cable's midpoint behind `z_cm − 25 Ω`, the PHY side terminated as in
    `conversion`. Returns {"v_dm", "v_cm_phy" (per volt of EMF), "ratio_phy", "v_a", "v_b"}; not the DM → CM ratio."""
    _coupling(coupling)
    w = _TWO_PI * f
    gl, gm = 1 / 50.0, 1 / (z_cm - 25)
    ya, yb = 1 / (rs * (1 + dr)) + 1j * w * ca + gl, 1 / (rs * (1 - dr)) + 1j * w * cb + gl
    vm = gm / (2 * gl + gm - gl * gl * (1 / ya + 1 / yb))
    va, vb = gl * vm / ya, gl * vm / yb
    vdm = abs(gl * vm * (1 / ya - 1 / yb))                 # exactly 0 when the two sides are equal
    vcm = abs((va + vb) / 2)
    return {"v_dm": vdm, "v_cm_phy": vcm, "ratio_phy": vdm / vcm, "v_a": va, "v_b": vb}


def differential_noise(v_emf_rms, f, ca, cb, rs=50.0, dr=0.0, z_cm=150.0, coupling="capacitor"):
    """Differential noise at the PHY lines from a common-mode injection of EMF `v_emf_rms` (`injection`): {"v_dm",
    "v_cm_phy"} in V RMS. An estimate, not a verdict."""
    v = v_emf_rms
    r = injection(f, ca, cb, rs, dr, z_cm, coupling)
    return {"v_dm": v * r["v_dm"], "v_cm_phy": v * r["v_cm_phy"]}
