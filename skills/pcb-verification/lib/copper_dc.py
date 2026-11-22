"""DC resistance of printed-board copper: sheet, straight track, plated via barrel, temperature factor (pure Python).
Units: metres for thicknesses, millimetres where the name says `_mm`; nominal copper, uniform temperature.
"""
import math

RHO = 1.72e-8          # Ω·m, annealed copper at 20 °C (same constant as irdrop2d.py)
ALPHA_CU = 0.00393     # 1/K, temperature coefficient of copper resistance


def sheet_resistance(t_m, rho=RHO):
    """Ω per square of a copper sheet `t_m` thick."""
    return rho / t_m


def track_resistance(length_mm, width_mm, t_m, rho=RHO):
    """Ω of a straight track: sheet resistance × length / width."""
    return sheet_resistance(t_m, rho) * length_mm / width_mm


def slot_equivalent_drill_mm(w_mm, l_mm):
    """Round hole with the same wall length as a slot of width w and overall length l (perimeter / π)."""
    if l_mm < w_mm:
        raise ValueError("slot length %g mm is shorter than its width %g mm" % (l_mm, w_mm))
    return (math.pi * w_mm + 2 * (l_mm - w_mm)) / math.pi


def via_barrel_resistance(drill_mm, length_mm, plating_m, rho=RHO):
    """Ω of the plated barrel of a via between two layers `length_mm` apart: ρ L / (π (d + p) p); `plating_m` is the
    fabricator's plating thickness (m)."""
    d = drill_mm * 1e-3
    p = plating_m
    return rho * length_mm * 1e-3 / (math.pi * (d + p) * p)


def temperature_factor(t_c, alpha=ALPHA_CU, t_ref=20.0):
    """Multiplier on a resistance at `t_c` °C relative to `t_ref`."""
    return 1.0 + alpha * (float(t_c) - t_ref)
