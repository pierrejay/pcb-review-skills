"""Thermal bookkeeping around the solver `thermal2d` (numpy, scipy): power inventory, the three-h policy, JEDEC θ and
deduced θJB, junction temperatures and minimum h, board bookkeeping, and the loss formulas. Units: W, K, °C, °C/W,
W/m²K, mm for footprints and board sizes, m for the grid step.
"""
import numpy as np

import thermal2d as th

# The three exchange coefficients (W/m²K per face), always shown together: an in-house bracket (policy) from fitting
# the θJA / θJB of two packages (pessimistic = still air, optimistic = a package with a good board coupling),
# not a datasheet value; refit it on the parts of the board at hand.
H_BOUNDS = (5.8, 12.0, 21.0)
H_PROVENANCE = {
    5.8: "pessimistic, still air: fit of a small package (θJA 52, θJB 30 °C/W, 5 × 5 mm) → 5.77 W/m²K",
    12.0: "central: free air, natural convection and radiation (assumption between the two fits)",
    21.0: "optimistic: fit of an SoC (θJA 17.9, θJB 8.2 °C/W, 12 × 12 mm) → 20.96 W/m²K",
}
INVENTORY_TOL = 0.01
JEDEC_CENTER_MM = (57.15, 38.1)


# --- inventory ---------------------------------------------------------------------------------------------------
def inventory_balance(entering_w, placed_w, spread_w=0.0, offboard_w=0.0, tol=INVENTORY_TOL):
    """Checks that entering = Σ placed + spread + off-board within `tol` (relative), ValueError otherwise.
    `placed_w`: {reference: W}; `offboard_w`: W or {label: W}. Returns {"entering", "placed", "spread", "offboard",
    "dissipated" (placed + spread), "gap", "gap_rel"}."""
    entering = float(entering_w)
    placed = {k: float(v) for k, v in dict(placed_w).items()}
    spread = float(spread_w)
    off = dict(offboard_w) if isinstance(offboard_w, dict) else {"off-board": offboard_w}
    off = {k: float(v) for k, v in off.items()}
    total = sum(placed.values()) + spread + sum(off.values())
    gap = entering - total
    rel = gap / entering
    if abs(rel) > tol:
        raise ValueError(f"inventory does not balance: {entering:.3f} W enter, {total:.3f} W attributed "
                         f"({sum(placed.values()):.3f} placed + {spread:.3f} spread + {sum(off.values()):.3f} off-board), "
                         f"gap {gap:+.3f} W = {rel:+.1%} (tolerance {tol:.0%})")
    return {"entering": entering, "placed": placed, "spread": spread, "offboard": off,
            "dissipated": sum(placed.values()) + spread, "gap": gap, "gap_rel": rel}


# --- JEDEC model, θJB, junction ----------------------------------------------------------------------------------
def jedec_theta(h, footprint_mm, d=0.5e-3):
    """θ board → air (°C/W) of the JESD51-7 2s2p board under a footprint (w, l in mm) at its centre, h per face."""
    w, l = footprint_mm
    kt, mask, nx, ny = th.jedec_2s2p(d)
    return th.theta_board_ambient(kt, mask, d, h, (w, l), JEDEC_CENTER_MM)


def deduce_theta_jb(theta_ja, h, footprint_mm, d=0.5e-3):
    """θJB = θJA − θ board → air of the JEDEC model at the SAME h as the board run and the part's footprint."""
    theta = jedec_theta(h, footprint_mm, d)
    jb = theta_ja - theta
    if jb <= 0:
        raise ValueError(f"deduced θJB = {theta_ja} − {theta:.1f} = {jb:.1f} °C/W ≤ 0: check the footprint and θJA")
    return jb


def junction_rise(board_rise_k, p_w, theta_jb):
    """Tj rise = mean board rise under the footprint + P × θJB."""
    return board_rise_k + p_w * theta_jb


def admissible_ambient(tj_max_c, board_rise_k, p_w, theta_jb):
    """Maximum admissible ambient = Tj max − Tj rise."""
    return tj_max_c - junction_rise(board_rise_k, p_w, theta_jb)


def worst_h(tj_by_h):
    """From {h: {reference: Tj}}: {"per_part": {reference: h of its hottest junction}, "overall": (h, reference,
    Tj)}."""
    hs = list(tj_by_h)
    refs = set(tj_by_h[hs[0]])
    for h in hs:
        if set(tj_by_h[h]) != refs:
            raise ValueError(f"results at h = {h} do not list the same parts as at h = {hs[0]}")
    per_part = {r: max(hs, key=lambda h: tj_by_h[h][r]) for r in refs}
    worst = max(((h, r, tj_by_h[h][r]) for h in hs for r in refs), key=lambda t: t[2])
    return {"per_part": per_part, "overall": worst}


def min_h_holding(margin_fn, h_floor, h_top, samples=5, rel_tol=1e-3):
    """Smallest h in [h_floor, h_top] at which `margin_fn(h)` (smallest margin to Tj max over the parts, K, θJB frozen
    at the lowest h) is ≥ 0, by bisection. Returns {"status": "found" | "holds_at_floor" | "fails_at_top" (h None: a
    fail), "h", "margin_at_h", "h_floor", "h_top"}; ValueError if the margin does not increase with h."""
    lo, hi = float(h_floor), float(h_top)

    def margin(h):
        return float(margin_fn(h))

    hs = np.linspace(lo, hi, max(int(samples), 2))
    ms = [margin(h) for h in hs]
    if any(b <= a for a, b in zip(ms, ms[1:])):
        raise ValueError(f"the margin does not increase with h over [{lo}, {hi}] W/m²K: {np.round(ms, 2).tolist()}; "
                         "θJB must be frozen and only the board exchange may vary")
    if ms[-1] < 0:                               # a zero margin holds (Tj ≤ Tjmax is inclusive)
        return {"status": "fails_at_top", "h": None, "margin_at_h": ms[-1], "h_floor": lo, "h_top": hi}
    if ms[0] >= 0:
        return {"status": "holds_at_floor", "h": lo, "margin_at_h": ms[0], "h_floor": lo, "h_top": hi}
    a, b = lo, hi
    for _ in range(60):
        mid = 0.5 * (a + b)
        if margin(mid) >= 0:
            b = mid
        else:
            a = mid
        if (b - a) <= rel_tol * b:
            break
    return {"status": "found", "h": b, "margin_at_h": margin(b), "h_floor": lo, "h_top": hi}


# --- board bookkeeping around the solver --------------------------------------------------------------------------
def simplified_board(width_mm, length_mm, d=0.5e-3, outer_cover=0.05, inner_cover=1.0,
                     t_cu=(70e-6, 35e-6, 35e-6, 70e-6), t_fr4=1.6e-3):
    """(kt, mask) of a rectangular four-layer board with smeared copper fractions (`outer_cover`, `inner_cover`), the
    JEDEC layers by default, for a check with no export: not the real copper."""
    w, l = width_mm, length_mm
    nx, ny = int(round(w * 1e-3 / d)), int(round(l * 1e-3 / d))
    mask = np.ones((nx, ny), dtype=bool)
    cover = {"top": np.full((nx, ny), float(outer_cover)), "p1": np.full((nx, ny), float(inner_cover)),
             "p2": np.full((nx, ny), float(inner_cover)), "bot": np.full((nx, ny), float(outer_cover))}
    kt = th.sheet_kt(cover, {"top": t_cu[0], "p1": t_cu[1], "p2": t_cu[2], "bot": t_cu[3]}, t_fr4)
    return kt, mask


def footprint_cells(mask, d, center_mm, footprint_mm):
    """Bool array of the cells a footprint (w, l mm) centred at `center_mm` touches, by the rule of
    `thermal2d.cell_span`, within the board mask; ValueError if none."""
    nx, ny = mask.shape
    w, l = footprint_mm[0], footprint_mm[1]
    cx, cy = center_mm[0], center_mm[1]
    dm = d * 1e3
    ix, iy = th.cell_span(cx, w, dm, nx), th.cell_span(cy, l, dm, ny)
    cells = np.zeros((nx, ny), dtype=bool)
    if ix is not None and iy is not None:          # off the grid: no cell (a negative index would wrap around)
        cells[ix, iy] = True
    cells &= mask
    if not cells.any():
        raise ValueError(f"footprint {footprint_mm} mm at {center_mm} mm touches no cell of the board")
    return cells


def solve_board(kt, mask, d, h, sources, tol=1e-6):
    """One solve, `sources` = {reference: (cells, W)} spread uniformly over the cells, h on both faces; the energy
    balance is checked within `tol`. Returns {"rise" (K), "mean_under": {reference: K}, "board_mean", "board_max",
    "injected", "balance"}."""
    power = np.zeros(kt.shape)
    injected = 0.0
    for ref, (cells, w) in sources.items():
        n = int(np.count_nonzero(cells & mask))
        power[cells & mask] += w / n
        injected += w
    rise = th.solve(kt, mask, d, h, h, power)
    out = float(np.nansum(rise) * 2 * h * d * d)
    balance = abs(out - injected) / injected
    if balance > tol:
        raise ValueError(f"energy balance: {out:.6f} W leave for {injected:.6f} W injected ({balance:.1e} > {tol:.0e})")
    return {"rise": rise, "mean_under": {ref: float(np.nanmean(rise[c & mask])) for ref, (c, _) in sources.items()},
            "board_mean": float(np.nanmean(rise[mask])), "board_max": float(np.nanmax(rise[mask])),
            "injected": injected, "balance": balance}


def junction_table(kt, mask, d, h, parts, powers, ambient_c, theta_jb_override=None):
    """One block (h, scenario): `parts` = {reference: {"cells", "theta_ja", "theta_jb" (None: deduced at this h),
    "tj_max", "footprint_mm"}}, `powers` = {reference: W}, `theta_jb_override` = {reference: frozen θJB}. Returns
    {"h", "board_mean", "board_max", "injected", "parts": {reference: {"p", "board_rise", "theta_jb",
    "theta_jb_source", "tj_rise", "tj", "tj_max", "admissible_ambient", "margin"}}}."""
    sources = {ref: (parts[ref]["cells"], p) for ref, p in powers.items()}
    sol = solve_board(kt, mask, d, h, sources)
    rows = {}
    for ref, p in powers.items():
        part = parts[ref]
        if theta_jb_override and ref in theta_jb_override:
            jb, src = float(theta_jb_override[ref]), "frozen"
        elif part.get("theta_jb") is not None:
            jb, src = float(part["theta_jb"]), "published"
        else:
            jb, src = deduce_theta_jb(part["theta_ja"], h, part["footprint_mm"], d), f"deduced at h = {h:g}"
        br = sol["mean_under"][ref]
        rise = junction_rise(br, p, jb)
        tj_max = float(part["tj_max"])
        rows[ref] = {"p": float(p), "board_rise": br, "theta_jb": jb, "theta_jb_source": src, "tj_rise": rise,
                     "tj": ambient_c + rise, "tj_max": tj_max,
                     "admissible_ambient": admissible_ambient(tj_max, br, p, jb),
                     "margin": tj_max - ambient_c - rise}
    return {"h": h, "board_mean": sol["board_mean"], "board_max": sol["board_max"], "injected": sol["injected"],
            "parts": rows}


# --- losses -------------------------------------------------------------------------------------------------------
def _rms2_triangle(i, di_pp):
    # squared RMS of a triangle of mean i and peak-to-peak di_pp: I² + ΔI² / 12
    return i * i + di_pp ** 2 / 12.0


def buck_loss(i_out_a, duty, rds_high_ohm, rds_low_ohm, p_fixed_w=0.04, *, di_pp_a=None):
    """Buck IC loss (W): Irms² × (D × RDS(on) high + (1 − D) × RDS(on) low), Irms² = I² + ΔI² / 12 (`di_pp_a`, the ΔI
    of `power_sequence.inductor_ripple`, required), + `p_fixed_w` (switching and control, a screening estimate)."""
    i, d = i_out_a, duty
    if not 0.0 <= d <= 1.0:
        raise ValueError(f"duty cycle {d} outside [0, 1]")
    r_mean = d * rds_high_ohm + (1 - d) * rds_low_ohm
    return _rms2_triangle(i, di_pp_a) * r_mean + p_fixed_w


def inductor_loss(i_a, dcr_ohm, p_core_w=0.0, *, di_pp_a=None):
    """Inductor loss (W): Irms² × DCR (`di_pp_a` as in `buck_loss`, required) + `p_core_w` (an estimate)."""
    return _rms2_triangle(i_a, di_pp_a) * dcr_ohm + p_core_w


def efficiency_split(p_out_w, eta, ic_share=0.8):
    """(total, IC, inductor) loss (W) of a converter from its efficiency `eta` (fraction): P out × (1 / η − 1), split
    by `ic_share` (an assumption)."""
    p = p_out_w
    if not eta <= 1.0:
        raise ValueError(f"efficiency {eta} outside (0, 1]")
    if not ic_share <= 1.0:
        raise ValueError("IC share outside [0, 1]")
    loss = p * (1.0 / eta - 1.0)
    return loss, loss * ic_share, loss * (1.0 - ic_share)


def diode_loss(vf_v, i_a):
    """Series diode loss (W): VF at the current × the current."""
    return vf_v * i_a


def switch_loss(i_a, r_on_ohm):
    """Power mux or load switch loss (W): I² × on-resistance."""
    return i_a * i_a * r_on_ohm


def ldo_loss(vin_v, vout_v, i_a, i_gnd_a):
    """Linear regulator loss (W): (Vin − Vout) × I + Vin × Ignd, at the maximum of the source; `i_gnd_a`: datasheet
    ground current at that input, load and temperature."""
    vin, vout = vin_v, vout_v
    if vin < vout:
        raise ValueError(f"Vin {vin} V below Vout {vout} V")
    return (vin - vout) * i_a + vin * i_gnd_a


def ldo_dropout_margin(v_source_min, i_a, r_series_ohm, vout_v, dropout_v, dropout_at_a=None, *, i_gnd_a=None,
                       i_other_a=0.0):
    """(Vin at the regulator, dropout margin) in V at the minimum of the source: the series resistance carries
    I + Ignd + `i_other_a` (`i_gnd_a` required); the dropout `dropout_v` is at the output current, or scaled from
    `dropout_at_a` when given (estimate)."""
    vs, i, r = v_source_min, i_a, r_series_ohm
    vout, dv = vout_v, dropout_v
    i_in = i + i_gnd_a + i_other_a
    if dropout_at_a is not None:
        dv = dv * i / dropout_at_a
    vin = vs - i_in * r
    return vin, vin - vout - dv


def soc_rail_split(p_total_w, fractions):
    """{rail: W} of a processor's total split by the caller's assumed `fractions` {rail: share} (Σ = 1)."""
    p = p_total_w
    fr = dict(fractions)
    if abs(sum(fr.values()) - 1.0) > 1e-6:
        raise ValueError(f"shares sum to {sum(fr.values()):.4f}, not 1")
    return {k: p * v for k, v in fr.items()}
