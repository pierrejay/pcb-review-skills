"""Quantified effect of a routing deviation (estimates): return loss of one run (`return_loss_db`) or of a path of
sections (`return_loss_sections_db`), via loop inductance and its delay, P/N skew, useful frequency per link type.
Pure Python. Units: mm, Ω, Hz, s/mm (5.7 ps/mm = 5.7e-12 s/mm), nH, ps.
"""
import cmath
import math

MU0_OVER_PI_NH_PER_MM = 0.4      # µ0 / π = 4e-7 H/m = 0.4 nH/mm, the two-wire loop inductance per unit length factor

# Useful frequency per link type, Hz, with the reason: screening values that size the effect of a deviation. A new
# link type is added here with its reason, never typed in a board script; for any other link the caller passes a
# frequency of its own to the formulas.
USEFUL_FREQUENCY = {
    "USB high speed": (700e6, "USB 2.0 high speed: edges of the order of 0.5 ns (indicative), 0.35 / 0.5 ns"),
    "100BASE-TX": (100e6, "100BASE-TX: return loss commonly specified up to about 80 MHz (indicative); 100 MHz keeps a margin"),
    "10BASE-T1L": (20e6, "10BASE-T1L: return loss commonly specified up to about 20 MHz (indicative)"),
    "10BASE-T1S": (40e6, "10BASE-T1S: return loss commonly specified up to about 40 MHz (indicative)"),
}


def useful_frequency(link_type):
    """Useful frequency (Hz) of a link type of `USEFUL_FREQUENCY` (sizes the effect of a deviation, never the
    verdict)."""
    return USEFUL_FREQUENCY[link_type][0]


def return_loss_db(z_run, z0, length_mm, f_hz, tpd_s_per_mm):
    """Return loss (dB) of ONE lossless run `z_run` of `length_mm` in a matched lossless line `z0`, at `f_hz`;
    `math.inf` when matched. Separate runs of a link do not add up as one: use `return_loss_sections_db`."""
    gamma = (z_run - z0) / (z_run + z0)
    theta = 2 * math.pi * f_hz * length_mm * tpd_s_per_mm
    e = cmath.exp(-2j * theta)
    gin = gamma * (1 - e) / (1 - gamma * gamma * e)
    return math.inf if abs(gin) == 0 else -20 * math.log10(abs(gin))


def return_loss_sections_db(sections, z0, f_hz, tpd_s_per_mm):
    """Return loss (dB) at the input of ordered `sections` = [(z Ω, length mm), …] from the source to the load, in a
    lossless line `z0` matched at both ends, one delay per mm; `math.inf` when matched."""
    secs = list(sections)
    if not secs:                           # an empty path would read as matched
        raise ValueError("no section: a path has at least one")
    zl = complex(z0)
    for z, length in reversed(secs):
        g = (zl - z) / (zl + z) * cmath.exp(-4j * math.pi * f_hz * length * tpd_s_per_mm)
        zl = z * (1 + g) / (1 - g)
    gin = abs((zl - z0) / (zl + z0))
    return math.inf if gin == 0 else -20 * math.log10(gin)


def via_loop_inductance_nh(h_mm, d_mm, drill_mm, plating_mm=0.020):
    """Loop inductance (nH) of a signal via and its ground via, two barrels of length `h_mm` at centre distance `d_mm`
    (bounded below by 2 r, r = drill / 2 + plating): `0.4 · h · ln(d / r)`; planes ignored, an estimate."""
    r = drill_mm / 2 + plating_mm
    return MU0_OVER_PI_NH_PER_MM * h_mm * math.log(max(d_mm, 2 * r) / r)


def delay_ps(l_nh, z0):
    """Delay (ps) an inductance `l_nh` (nH) adds in a line of impedance `z0`: L / (2 · z0)."""
    return l_nh * 1e-9 / (2 * z0) * 1e12


def skew_ps(delta_mm, tpd_s_per_mm):
    """Skew (ps) of a P/N length mismatch `delta_mm` (sign kept); each leg counts, per via, the height between the two
    layers it joins (`kicad_routing.pad_path(..., via_layers=True)`)."""
    return delta_mm * tpd_s_per_mm * 1e12
