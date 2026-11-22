"""Setup / hold budgets of synchronous interfaces with routed lengths: line delay, common-clock (RMII) margins, SPI
mode 0, serial memory, output-delay window of an unpublished controller (pure Python). Units: mm, ps/mm, pF/mm, Ω,
pF, ns, Hz; every returned time in ns; datasheet setup and hold times are signed and required (None is not 0).
"""
import math


def _time(x, what):
    """A datasheet time in ns; None (not published) is passed through."""
    return None if x is None else float(x)


def _duty(duty_min):
    if not 0 < duty_min <= 0.5:     # 0.6 typed for a 60 / 40 clock would overstate the shorter time
        raise ValueError(f"duty_min is the shorter of the high and low times over the period, in ]0, 0.5]; got "
                         f"{duty_min!r} (a clock of high / low ratio 90 / 10 has duty_min 0.1)")
    return float(duty_min)


def period_ns(f_hz):
    """1 / f in ns."""
    return 1e9 / f_hz


def rc_delay_factor(threshold):
    """Delay of a single RC, in RC, to the fraction `threshold` of the swing: −ln(1 − threshold) (a falling input
    reaches the fraction x after −ln(x) RC)."""
    return -math.log(1 - threshold)


def line_delay(length_mm, vias, board_mm, tpd_ps_per_mm, r_series, c_in_pf, c_per_mm, downstream_mm=None,
               vih=0.7, vil=0.3, clock=False):
    """Delay of one line (ns). `length_mm`: the TRACKS alone; `vias`: a count (each crossing 0 to `board_mm`) or the
    list of heights each via crosses (mm); RC = `r_series` × (`c_in_pf` + `c_per_mm` × `downstream_mm`, whole path when
    None); `vih`, `vil` fractions of the swing; `clock=True` takes the first RC crossing for the earliest arrival.
    Returns {"flight", "flight_min", "rc", "rc_min", "rc_low", "rc_high", "latest", "earliest", "length_mm",
    "length_min_mm"}, "min" with the vias at their smallest crossing."""
    tracks, board = float(length_mm), float(board_mm)
    if isinstance(vias, (list, tuple)):
        heights = list(vias)
        if any(h > board + 1e-9 for h in heights):
            raise ValueError(f"via heights {heights} mm: a via crosses at most the board thickness {board} mm")
        length = length_min = tracks + sum(heights)
    else:
        length, length_min = tracks + board * vias, tracks
    if downstream_mm is None:
        down, down_min = length, length_min
    else:
        down = down_min = downstream_mm
    if down > length + 1e-9:
        raise ValueError(f"downstream length {down} mm exceeds the path length {length} mm")
    if not vil < vih:
        raise ValueError(f"thresholds must satisfy 0 < vil < vih < 1 (fractions of the swing), got {vil!r}, {vih!r}")
    tpd = tpd_ps_per_mm
    flight, flight_min = length * tpd / 1000, length_min * tpd / 1000
    r, c_in = r_series, c_in_pf
    c_mm = c_per_mm
    rc, rc_min = r * (c_in + down * c_mm) / 1000, r * (c_in + down_min * c_mm) / 1000
    hi = max(rc_delay_factor(vih), -math.log(vil)) * rc          # last crossing, rising to VIH or falling to VIL
    lo = min(rc_delay_factor(vil), -math.log(vih)) * rc_min if clock else 0.0   # first crossing (clock only)
    return {"length_mm": length, "length_min_mm": length_min, "flight": flight, "flight_min": flight_min, "rc": rc,
            "rc_min": rc_min, "rc_low": lo, "rc_high": hi, "latest": flight + hi, "earliest": flight_min + lo}


def common_clock_margins(period, skew_to_receiver, d_max, d_min, t_out_min, t_out_max, t_su, t_h):
    """One data line of a common-clock interface: setup = T + skew − t_out_max − d_max − t_su, hold = t_out_min + d_min
    − skew − t_h; skew = clock delay at the receiver − at the transmitter. A None output delay gives a None margin.
    Returns {"setup", "hold", "window"}."""
    window = output_delay_window(period, skew_to_receiver, d_max, d_min, t_su, t_h)
    t, skew = float(period), float(skew_to_receiver)
    dmax, dmin, tsu, th = float(d_max), float(d_min), float(t_su), float(t_h)
    tmin, tmax = _time(t_out_min, "t_out,min"), _time(t_out_max, "t_out,max")
    if tmin is not None and tmax is not None and tmin > tmax + 1e-12:
        raise ValueError(f"t_out,min {tmin} > t_out,max {tmax}")
    setup = None if tmax is None else t + skew - tmax - dmax - tsu
    hold = None if tmin is None else tmin + dmin - skew - th
    return {"setup": setup, "hold": hold, "window": window}


def output_delay_window(period, skew_to_receiver, d_max, d_min, t_su, t_h):
    """Admissible output delay of an unpublished controller: {"min": t_h − d_min + skew, "max": T + skew − d_max −
    t_su}."""
    t = float(period)
    skew = float(skew_to_receiver)
    dmax, dmin = float(d_max), float(d_min)
    if dmin > dmax + 1e-12:
        raise ValueError(f"d_min {dmin} > d_max {dmax}")
    return {"min": float(t_h) - dmin + skew, "max": t + skew - dmax - float(t_su)}


def via_transit(depth_mm, tpd_ps_per_mm):
    """Flight (ps) through one via: the height it really crosses between its two layers, not the board thickness."""
    return float(depth_mm) * float(tpd_ps_per_mm)


def centred_window_margins(window, offset, t_su, t_h):
    """A line launched at the middle of its valid `window`, captured by a clock or strobe; `offset` = clock arrival −
    line arrival (signed), same unit throughout. Returns {"setup", "hold", "balancing_offset" (offset equalising the
    two margins), "share" (|offset| / free window)}."""
    w = float(window)
    off = float(offset)
    tsu, th = float(t_su), float(t_h)
    free = w - tsu - th
    if free <= 0:
        raise ValueError(f"no free window: {w} for setup {tsu} and hold {th}")
    return {"setup": w / 2 + off - tsu, "hold": w / 2 - off - th, "balancing_offset": (tsu - th) / 2, "share": abs(off) / free}


def byte_lane_wiring(lanes, lane_of_net):
    """Byte lanes of a parallel memory bus: `lanes` {controller lane: nets}, `lane_of_net(net)` → memory lane of its
    pin. Returns {"mapping": {controller lane: memory lane}, "errors": [(controller lane, net or None, lane found, lane
    of the group)]}, net None: two controller lanes on one memory lane."""
    if not lanes:
        raise ValueError(f"lanes must be a non-empty dict {{controller lane: nets}}, got {lanes!r}")
    mapping, errors = {}, []
    for lane, nets in lanes.items():
        found = {n: lane_of_net(n) for n in nets}
        if None in found.values():
            raise ValueError(f"lane {lane}: net not found on the memory: {[n for n, m in found.items() if m is None]}")
        values = list(found.values())
        target = max(values, key=values.count)
        mapping[lane] = target
        errors += [(lane, n, m, target) for n, m in found.items() if m != target]
    for lane, target in mapping.items():
        if list(mapping.values()).count(target) > 1:
            errors.append((lane, None, target, target))
    return {"mapping": mapping, "errors": errors}


def pulse_width_margins(f_hz, duty_min, t_high_min, t_low_min):
    """High and low times at a receiver against its minimum high and low times: t_w = `duty_min` × T (the shorter of
    the source's two times, ≤ 0.5); a None minimum gives None. Returns {"t_w", "high", "low"}."""
    tw = _duty(duty_min) * period_ns(f_hz)
    hi = None if t_high_min is None else tw - t_high_min
    lo = None if t_low_min is None else tw - t_low_min
    return {"t_w": tw, "high": hi, "low": lo}


def rmii_margins(period, t_clk_phy, t_clk_mac, phy_to_mac, mac_to_phy):
    """RMII both directions, Δ = t_clk_mac − t_clk_phy (positive: the MAC sees the clock later). `phy_to_mac`,
    `mac_to_phy`: lists of {"name", "d_max", "d_min", "t_out_min", "t_out_max", "t_su", "t_h"}. Returns {"skew",
    "phy_to_mac", "mac_to_phy"}, rows of `common_clock_margins` with their name."""
    skew = float(t_clk_mac) - float(t_clk_phy)
    out = {"skew": skew, "phy_to_mac": [], "mac_to_phy": []}
    for direction, lines, s in (("phy_to_mac", phy_to_mac, skew), ("mac_to_phy", mac_to_phy, -skew)):
        for line in lines:
            row = common_clock_margins(period, s, line["d_max"], line["d_min"], line.get("t_out_min"),
                                       line.get("t_out_max"), line["t_su"], line["t_h"])
            row["name"] = line.get("name", "")
            out[direction].append(row)
    return out


def spi_mode0_margins(f_hz, t_c, miso, mosi=None, duty_min=0.5, sample_half_period_later=False):
    """SPI mode 0 at `f_hz`, `t_c` the SCLK delay to the peripheral (ns). `miso` = {"d_max", "d_min", "t_dv", "t_su",
    "t_h"}; `mosi` = {"d_max", "d_min", "t_c_min", "t_v", "t_su", "t_h"} or None; t_w = `duty_min` × T (the shorter
    high or low time). Returns {"period", "t_w", "miso": {"setup", "hold", "terms"}, "mosi", "limit_hz",
    "duty_min_holding"}."""
    t = period_ns(f_hz)
    tc = float(t_c)
    tw = _duty(duty_min) * t
    dmax = float(miso["d_max"])
    dmin = float(miso.get("d_min", 0.0))
    if dmin > dmax + 1e-12:
        raise ValueError(f"MISO d_min {dmin} > d_max {dmax}")
    tdv = float(miso["t_dv"])
    tsu, th = float(miso["t_su"]), float(miso["t_h"])
    consumed = tc + tdv + dmax + tsu
    if sample_half_period_later:
        setup, hold = t - consumed, tc + dmin - th
        terms = {"period": t, "clock_path": -tc, "t_dv": -tdv, "return_path": -dmax, "t_su": -tsu}
    else:
        setup, hold = tw - consumed, tw + tc + dmin - th
        terms = {"t_w": tw, "clock_path": -tc, "t_dv": -tdv, "return_path": -dmax, "t_su": -tsu}
    out = {"period": t, "t_w": tw, "miso": {"setup": setup, "hold": hold, "terms": terms},
           "limit_hz": (1.0 if sample_half_period_later else duty_min) / consumed * 1e9 if consumed > 0 else None,
           "duty_min_holding": consumed / t, "mosi": None}
    if mosi is not None:
        md = float(mosi["d_max"])
        mn = float(mosi.get("d_min", 0.0))
        if mn > md + 1e-12:
            raise ValueError(f"MOSI d_min {mn} > d_max {md}")
        tcmin = float(mosi.get("t_c_min", 0.0))
        if tcmin > tc + 1e-12:
            raise ValueError(f"earliest clock delay t_c_min {tcmin} > clock delay t_c {tc}")
        tv = float(mosi["t_v"])
        msu, mh = float(mosi["t_su"]), float(mosi["t_h"])
        out["mosi"] = {"setup": tw - tv - (md - tcmin) - msu, "hold": tw + (mn - tc) - mh}
    return out


def serial_memory_margins(f_hz, t_c, d_max, d_min, tdvch, tchdx, tclqv, tclqx, t_period_min_ns=None):
    """Serial memory on an SoC, mode 0, single data rate: write setup / hold at the memory on T/2, read window at the
    SoC sampled on the next rising or falling edge; `t_c` the clock delay to the memory. Returns {"period", "write":
    {"setup", "hold", "duty_zero"}, "read": {"t_open", "window", "rising_setup", "falling_setup", "falling_hold",
    "limit_rising_hz"}, "period_ok"}."""
    t = period_ns(f_hz)
    tc = float(t_c)
    dmax, dmin = float(d_max), float(d_min)
    if dmin > dmax + 1e-12:
        raise ValueError(f"d_min {dmin} > d_max {dmax}")
    a, b, v, x = (float(tdvch), float(tchdx), float(tclqv), float(tclqx))
    if x > v:
        raise ValueError(f"tCLQX {x} > tCLQV {v}: outputs cannot hold longer than they take to become valid")
    t_open = tc + dmax + v
    return {"period": t,
            "write": {"setup": t / 2 - (dmax - tc) - a, "hold": t / 2 + (dmin - tc) - b,
                      "duty_zero": ((dmax - tc) + a) / t},
            "read": {"t_open": t_open, "window": t - (v - x) - (dmax - dmin), "rising_setup": t / 2 - t_open,
                     "falling_setup": t - t_open, "falling_hold": tc + dmin + x,
                     "limit_rising_hz": 1e9 / (2 * t_open) if t_open > 0 else None},
            "period_ok": None if t_period_min_ns is None else t >= t_period_min_ns - 1e-12}
