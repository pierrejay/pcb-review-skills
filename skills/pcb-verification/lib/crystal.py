"""Crystal oscillator budget of a printed board: load seen, frequency shift and ppm budget, critical transconductance,
drive level, centring value. Units: pF, mm, pF/mm, Hz, Ω, V peak-to-peak, ppm, A/V, W; the defaults below are
estimates, to replace by the board's or the part's own values."""
import math

C_PER_MM_DEFAULT = 0.112    # pF/mm, estimate, order of magnitude for a 50 Ω track over a close plane; recompute it
C_PAD_DEFAULT = 0.3         # pF per pad, estimate
C_PIN_DEFAULT = 2.0         # pF per IC pin, estimate (5 to 6 pF on some parts)
C_PP_DEFAULT = 0.3          # pF between the two pins, estimate
C1_DEFAULT_PF = 0.004       # 4 fF, 3.2 × 2.5 mm fundamental crystal, estimate
C0G_SERIES_PF = (15, 18, 20, 22, 24, 27)
GAIN_MARGIN = 5             # rule of thumb from oscillator application notes, screening default


def side_capacitance(c_ext_pf, length_mm, c_per_mm=C_PER_MM_DEFAULT, c_pad=C_PAD_DEFAULT, c_pin=C_PIN_DEFAULT):
    """One side: C_ext + length × C' + C_pad + C_pin (pF). The length is the WHOLE net, branches included."""
    return float(c_ext_pf + length_mm * c_per_mm + c_pad + c_pin)


def load_seen(c_ext_a, len_a, c_ext_b, len_b, c_per_mm=C_PER_MM_DEFAULT, c_pad=C_PAD_DEFAULT, c_pin=C_PIN_DEFAULT,
              c_pp=C_PP_DEFAULT):
    """The two sides and CL_seen = C_a C_b / (C_a + C_b) + C_pp (pF). Returns {"side_a", "side_b", "cl_seen"}."""
    a = side_capacitance(c_ext_a, len_a, c_per_mm, c_pad, c_pin)
    b = side_capacitance(c_ext_b, len_b, c_per_mm, c_pad, c_pin)
    return {"side_a": a, "side_b": b, "cl_seen": a * b / (a + b) + c_pp}


def pulling_sensitivity(c1_pf, c0_pf, cl_pf):
    """S = C1 / (2 (C0 + CL)²) in ppm/pF, CL the crystal's specified load."""
    total = c0_pf + cl_pf
    return c1_pf / (2 * total * total) * 1e6


def frequency_shift(c1_pf, c0_pf, cl_pf, cl_seen_pf):
    """Δf/f in ppm = (C1 / 2) (1 / (C0 + CL_seen) − 1 / (C0 + CL)) × 1e6, positive when the crystal is under-loaded;
    the finite change, not the local slope S. |Δf/f| decreases as C0 grows."""
    return c1_pf / 2 * (1 / (c0_pf + cl_seen_pf) - 1 / (c0_pf + cl_pf)) * 1e6


def worst_shift(c1_pf, cl_pf, cl_seen_corners, c0_min_pf=0.0):
    """Largest |Δf/f| (ppm) over the load corners, at the MINIMUM C0 (0 when the datasheet publishes none).
    Returns {"shift_ppm" (signed), "cl_seen", "c0_pf"}."""
    c0 = float(c0_min_pf)
    shifts = [(frequency_shift(c1_pf, c0, cl_pf, cs), cs) for cs in cl_seen_corners]
    shift, cs = max(shifts, key=lambda x: abs(x[0]))
    return {"shift_ppm": shift, "cl_seen": float(cs), "c0_pf": c0}


def budget(tol_ppm, stab_ppm, shift_ppm, age_ppm):
    """Worst-case budget in ppm: tolerance + stability + |load shift| + ageing, arithmetic sum."""
    return float(tol_ppm + stab_ppm + abs(shift_ppm) + age_ppm)


def frequency_budget(tol_ppm, stab_ppm, age_ppm, req_ppm, c1_pf, cl_pf, cl_seen_corners, c0_max_pf, c0_min_pf=0.0):
    """Budget against the requirement ±`req_ppm` at the minimum C0. "verdict": "pass", "fail", or "unpublished_c0"
    (fails only at the C0 of 0 taken for an unpublished minimum, passes at `c0_max_pf`); "c0_needed_pf": the smallest
    C0 that would pass, None when it passes or when even `c0_max_pf` fails."""
    fixed = tol_ppm + stab_ppm + age_ppm
    c0_max = float(c0_max_pf)
    corners = list(cl_seen_corners)                 # walked three times
    w = worst_shift(c1_pf, cl_pf, corners, c0_min_pf)
    if c0_max < w["c0_pf"]:                         # minimum and maximum swapped: the budget would take the maximum
        raise ValueError(f"maximum C0 {c0_max} pF below the minimum {w['c0_pf']} pF")
    total = budget(tol_ppm, stab_ppm, w["shift_ppm"], age_ppm)
    at_max = budget(tol_ppm, stab_ppm, worst_shift(c1_pf, cl_pf, corners, c0_max)["shift_ppm"], age_ppm)
    out = dict(w, budget_ppm=total, budget_c0_max_ppm=at_max, c0_needed_pf=None, c0_max_passes=at_max <= req_ppm)
    out["pass"] = total <= req_ppm
    out["verdict"] = ("pass" if out["pass"] else "unpublished_c0" if out["c0_max_passes"] and w["c0_pf"] == 0
                      else "fail")
    if out["pass"] or not out["c0_max_passes"]:
        return out
    room, c1, cl, need = req_ppm - fixed, float(c1_pf), float(cl_pf), w["c0_pf"]
    for cs in map(float, corners):   # room > 0 here: C0 max passes, so the fixed terms leave some
        k = c1 / 2 * abs(cl - cs) * 1e6 / room
        need = max(need, (-(cs + cl) + math.sqrt((cl - cs) ** 2 + 4 * k)) / 2)
    out["c0_needed_pf"] = min(need, c0_max)
    return out


def gm_crit(esr_ohm, r_s_ohm, f_hz, c0_pf, side_a_pf, side_b_pf, c_pp_pf=C_PP_DEFAULT):
    """Critical transconductance (A/V) of a Pierce oscillator, sides kept apart, C0 at its MAXIMUM: (ESR + R_s) ω²
    (Ca Cb + C0' (Ca + Cb))² / (Ca Cb), C0' = C0 + C_pp; R_s the series resistor on the output side (0 when absent)."""
    w = 2 * math.pi * f_hz
    a, b = side_a_pf, side_b_pf
    c0 = c0_pf + c_pp_pf
    k = (a * b + c0 * (a + b)) ** 2 / (a * b) * 1e-24
    return (esr_ohm + r_s_ohm) * w * w * k


def worst_gm_crit(esr_ohm, r_s_ohm, f_hz, c0_pf, sides_a_pf, sides_b_pf, c_pp_pf=C_PP_DEFAULT):
    """Largest `gm_crit` over the values each side can take (`sides_a_pf`, `sides_b_pf`: lists of pF, e.g. the ends
    of each range), at a corner, not necessarily the largest load. Returns {"gm_crit", "side_a", "side_b"}."""
    return max(({"gm_crit": gm_crit(esr_ohm, r_s_ohm, f_hz, c0_pf, a, b, c_pp_pf), "side_a": float(a),
                 "side_b": float(b)} for a in sides_a_pf for b in sides_b_pf), key=lambda x: x["gm_crit"])


def gm_margin5(esr_ohm, r_s_ohm, f_hz, c0_pf, side_a_pf, side_b_pf, c_pp_pf=C_PP_DEFAULT):
    """gm needed for a gain margin of 5 (A/V): 5 × gm_crit (a screening default)."""
    return GAIN_MARGIN * gm_crit(esr_ohm, r_s_ohm, f_hz, c0_pf, side_a_pf, side_b_pf, c_pp_pf)


def drive_level(f_hz, c0_pf, cl_seen_pf, v_pp, esr_ohm):
    """Crystal current I = ω (C0 + CL_seen) V_pp / (2 √2) (A RMS) and drive level P = ESR I² (W), C0 at its maximum.
    Returns {"i_a", "p_w"}."""
    w = 2 * math.pi * f_hz
    c = (c0_pf + cl_seen_pf) * 1e-12
    i = w * c * v_pp / (2 * math.sqrt(2))
    return {"i_a": i, "p_w": esr_ohm * i * i}


def centring_value(cl_pf, len_a, len_b, c_per_mm=C_PER_MM_DEFAULT, c_pad=C_PAD_DEFAULT, c_pin=C_PIN_DEFAULT,
                   c_pp=C_PP_DEFAULT, series=C0G_SERIES_PF):
    """Among `series` (standard C0G values), the value that, fitted on BOTH sides, brings CL_seen closest to CL
    (information, not a correction). Returns {"value_pf", "cl_seen"}."""
    best = None
    for value in series:
        seen = load_seen(value, len_a, value, len_b, c_per_mm, c_pad, c_pin, c_pp)["cl_seen"]
        if best is None or abs(seen - cl_pf) < abs(best["cl_seen"] - cl_pf):
            best = {"value_pf": value, "cl_seen": seen}
    return best
