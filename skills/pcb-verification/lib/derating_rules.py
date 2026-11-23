"""Derating rules of a BOM under the in-house policy (to be validated by the designer; not a derating standard):
catalogue-description parser, applied-voltage rule, resistor-between-two-signals rule and load formulas, one judge
per family returning {"state", "ratio", "deviations", "flags", "note"}, family and domain of a part, acceptances."""
import math
import re

from messages import Msg, record  # noqa: E402  (coded messages: the report renders them in its language)

# The ratios are the in-house policy (to be validated by the designer). `v_default` is a screening default for the net
# voltage of an undeclared net (3.3 V-class I/O with margin): declare the I/O voltage of every net that may exceed it.
POLICY = {"C_V": 0.80, "C_bias": 0.50, "R_P": 0.50, "D_V": 0.80, "L_I": 0.80, "FB_I": 0.50, "stock_min": 1000,
          "tvs_flag_margin": 0.10, "C_bias_min_f": 1e-6, "v_default": 3.6}
# The policy table, as data (the report prints it, labelled in-house).
FAMILY_RULES = (
    {"family": "capacitor", "deviation": "V > 80 % of rated voltage",
     "flag": "class 2 dielectric (X5R, X7R, Y5V…) of 1 µF or more above 50 % of rated voltage: effective capacitance to verify on "
             "the manufacturer's curve, unless a calculation already used the effective value (then a note names it)"},
    {"family": "resistor", "deviation": "P = V² / R > 50 % of rated power; V > rated voltage", "flag": "—"},
    {"family": "diode", "deviation": "reverse voltage > 80 % of VRRM (Schottky, rectifier, switching)", "flag": "—"},
    {"family": "protection", "deviation": "VRWM < permanent DC voltage (it would conduct)",
     "flag": "VRWM less than 10 % above it (leakage rises near VRWM)"},
    {"family": "inductor", "deviation": "peak current > 80 % of the lowest rated current of the description "
                                        "(saturation or heating)", "flag": "—"},
    {"family": "bead", "deviation": "current > 50 % of rated current", "flag": "—"},
    {"family": "every part", "deviation": "—", "flag": "maximum temperature ≤ ambient + board rise"},
    {"family": "sourcing", "deviation": "—", "flag": "assembly stock < 1 000; zero blocks an assembled order"},
)
# EIA-198 dielectric codes (indicative values commonly used, to be confirmed on the part's datasheet): class 2 =
# low-temperature letter, high-temperature digit, change letter; class 1 C0G (written NP0 too) from −55 to +125 °C.
_EIA_LOW = {"X": -55, "Y": -30, "Z": 10}
_EIA_HIGH = {"2": 45, "4": 65, "5": 85, "6": 105, "7": 125, "8": 150, "9": 200}
_CLASS2 = re.compile(r"[XYZ][2456789][PRSTUV]")
_CLASS1 = {"C0G": (-55, 125), "NP0": (-55, 125)}
_PREFIX = {"": 1.0, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6}
_UNITS = {"V": "v", "W": "w", "Ω": "ohm", "Ω": "ohm", "F": "f", "A": "a", "H": "h"}
_RATING = re.compile(r"(?<![A-Za-z0-9./])(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)([pnuµμmkM]?)(V|W|Ω|Ω|F|A|H)(?![A-Za-z])")
_TEMP = re.compile(r"(-?\d+)\s*℃\s*~\s*\+?(-?\d+)\s*℃")
_V_RANGE = re.compile(r"(?<![A-Za-z0-9./])(\d+(?:\.\d+)?)([pnuµμmkM]?)V\s*~\s*(\d+(?:\.\d+)?)([pnuµμmkM]?)V(?![A-Za-z])")
_TOL = re.compile(r"±\s*(\d+(?:\.\d+)?)\s*%")
_DIELECTRIC = re.compile(r"\b(" + _CLASS2.pattern + "|" + "|".join(_CLASS1) + r")\b")


def is_class2(dielectric):
    """True for an EIA class 2 dielectric code (X5R, X7R, Y5V…)."""
    return bool(dielectric) and _CLASS2.fullmatch(dielectric) is not None


def dielectric_range(dielectric):
    """Rated temperature range (t_min, t_max) °C of an EIA dielectric code, None if not one."""
    if dielectric in _CLASS1:
        return _CLASS1[dielectric]
    if is_class2(dielectric):
        return _EIA_LOW[dielectric[0]], _EIA_HIGH[dielectric[1]]
    return None


def parse_description(text):
    """Ratings from a one-line catalogue description: the FIRST value of each unit (V, W, Ω, F, H; every A value in
    "a"), a fraction "1/16W" read whole, "tol" from the first ±x %, t_min / t_max from "-55℃~+155℃" else from the
    dielectric code. Millivolts, a value at "@" and a range "a~b" ("v_range") are not the rated voltage. None if
    absent."""
    out = {"v": None, "w": None, "ohm": None, "f": None, "a": [], "h": None, "dielectric": None, "t_min": None,
           "t_max": None, "t_source": None, "v_range": None, "tol": None}
    m = _V_RANGE.search(text)
    if m:                                       # a supply range is not a rating: kept apart, not read as its lower end
        out["v_range"] = (float(m.group(1)) * _PREFIX[m.group(2)], float(m.group(3)) * _PREFIX[m.group(4)])
        text = text[:m.start()] + " " * (m.end() - m.start()) + text[m.end():]
    for match in _RATING.finditer(text):
        num, prefix, unit = match.groups()
        at = text[:match.start()].rstrip().endswith("@") or text[match.end():].lstrip().startswith("@")
        if "/" in num:                          # a fraction ("1/16W"), read whole: never its denominator alone
            a, b = (float(x) for x in num.split("/"))
            value = a / b * _PREFIX[prefix]
        else:
            value = float(num) * _PREFIX[prefix]
        key = _UNITS[unit]
        if key == "a":
            out["a"].append(value)
        elif key == "v" and (prefix == "m" or at):  # a forward voltage or a characteristic at a condition
            continue
        elif out[key] is None:                  # the FIRST value of each unit
            out[key] = value
    m = _TOL.search(text)
    if m:
        out["tol"] = float(m.group(1)) / 100
    m = _TEMP.search(text)
    if m:
        out["t_min"], out["t_max"], out["t_source"] = int(m.group(1)), int(m.group(2)), "description"
    m = _DIELECTRIC.search(text)
    if m:
        out["dielectric"] = m.group(1)
        if out["t_max"] is None:                # the code is the rated range; a range printed in the line wins
            (out["t_min"], out["t_max"]), out["t_source"] = dielectric_range(m.group(1)), f"dielectric {m.group(1)}"
    return out


def _finite(x, what):   # for values read from other checks' JSON: a NaN compares false and reads as "no deviation"
    if not math.isfinite(x):
        raise ValueError(f"{what} must be a finite number, got {x!r}")
    return float(x)


def _tol(x):            # 5 for 5 % would make the bound negative, and pass
    if not 0 <= x < 1:
        raise ValueError(f"resistance tolerance must be a fraction in [0, 1), got {x!r}")
    return float(x)


def check_policy(policy):
    """Returns the policy unchanged once its thresholds are checked: the ratios in ]0, 1], the others ≥ 0 (a ratio
    of 80 or a NaN would read as "no deviation")."""
    for k in ("C_V", "C_bias", "R_P", "D_V", "L_I", "FB_I"):
        if not 0 < policy[k] <= 1:
            raise ValueError(f"policy {k} must be a ratio in ]0, 1], got {policy[k]!r}")
    for k in ("tvs_flag_margin", "stock_min", "C_bias_min_f", "v_default"):
        if not policy[k] >= 0:
            raise ValueError(f"policy {k} must be a number ≥ 0, got {policy[k]!r}")
    return policy


def rail_spans(rails):
    """{net: V or (V low, V high)} → {net: (low, high)}: a supply is its range over its tolerances, a node held at
    one value (x, x); a single number is accepted for 0 V only (a ground). A NaN never becomes 0 V."""
    out = {}
    for net, value in rails.items():
        if isinstance(value, (tuple, list)):
            lo, hi = (_finite(v, f"rail {net!r}") for v in value)
            if lo > hi:
                raise ValueError(f"rail {net!r}: lowest {lo:g} V above highest {hi:g} V")
            out[net] = (lo, hi)
            continue
        if _finite(value, f"rail {net!r}") != 0:
            raise ValueError(f"rail {net!r} declared as the single value {value!r} V: declare a supply as its range "
                             f"(lowest, highest) over its tolerances, e.g. (21.6, 26.4) for 24 V ± 10 %, and a node "
                             f"held at one value as (x, x); a single number is accepted for 0 V only")
        out[net] = (0.0, 0.0)
    return out


def applied_voltage(nets, rails, v_default, forced=None, undeclared=None):
    """Largest possible DC difference (V) between the nets of a part, each pair taken at opposed corners: a rail is its
    range (`rail_spans`), an undeclared net [0, v_default] or its bound in `undeclared`; `forced` = (V, reason) wins.
    Returns {"v", "assumed" (an undeclared net took part), "basis"}."""
    nets = sorted(set(nets))
    if forced is not None:
        v, reason = forced
        if not reason or not reason.strip():
            raise ValueError("a forced voltage needs a reason")
        if _finite(v, "forced voltage") < 0:           # a negative stress would pass every rule
            raise ValueError(f"forced voltage {v!r}: give the largest difference between the nets, ≥ 0")
        return {"v": float(v), "assumed": False, "basis": f"forced: {reason}"}
    if len(nets) < 2:                                   # one net would read as 0 V
        raise ValueError(f"a voltage needs at least two nets, got {nets}")
    vd = _finite(v_default, "default I/O voltage")
    declared_spans = rail_spans(rails)
    bounds = {n: (0.0, vd) for n in nets if n not in declared_spans}
    for n in bounds:
        if n in (undeclared or {}):
            lo, hi = undeclared[n]
            bounds[n] = (float(lo), float(hi))
    spans, assumed = [], False
    for n in nets:
        if n in declared_spans:
            spans.append(declared_spans[n])
        else:
            spans.append(bounds[n])
            assumed = True
    best = 0.0
    for i, (lo_i, hi_i) in enumerate(spans):
        for lo_j, hi_j in spans[i + 1:]:
            best = max(best, hi_i - lo_j, hi_j - lo_i)
    declared = [n for n in nets if n in declared_spans]
    show = lambda lo, hi: f"{lo:g} V" if lo == hi else f"{lo:g} to {hi:g} V"   # noqa: E731
    basis = ("rails " + ", ".join(f"{n} {show(*declared_spans[n])}" for n in declared) if declared
             else "no declared net")
    if assumed:
        basis += "; undeclared net(s) between " + " / ".join(f"{lo:g} and {hi:g} V"
                                                             for lo, hi in sorted(set(bounds.values())))
    return {"v": best, "assumed": assumed, "basis": basis}


def declared_power(declaration):
    """(W, justification) → the same; a power that is not > 0 or an empty justification raises."""
    w, why = declaration
    if not why or not why.strip():
        raise ValueError("a declared power needs a non-empty justification")
    if not w > 0:
        raise ValueError(f"a declared power must be > 0, got {w!r}")
    return float(w), why


def resistor_between_signals(r_ohm, p_rated_w, v_bound, limit=POLICY["R_P"], declared=None, *, tol):
    """Three-way rule for a resistor between two undeclared nets: the bound V² / (R (1 − tol)) (`v_bound` from
    `applied_voltage`, `tol` a fraction) is judged if ≤ limit × rated, else the `declared` (W, justification), else
    "not judged: power to determine". Returns {"state", "p_w", "bound_w", "ratio", "basis"}."""
    r, p_rated, vd, lim = float(r_ohm), float(p_rated_w), float(v_bound), float(limit)
    bound = vd * vd / (r * (1 - _tol(tol)))
    if bound <= lim * p_rated + 1e-12:
        return {"state": "judged", "p_w": bound, "bound_w": bound, "ratio": bound / p_rated,
                "basis": "worst case: opposed levels"}
    if declared is not None:
        w, why = declared_power(declared)
        return {"state": "judged", "p_w": w, "bound_w": bound, "ratio": w / p_rated, "basis": f"declared: {why}"}
    return {"state": Msg("not judged: power to determine (resistor between two signals)", "power_to_determine"),
            "p_w": None, "bound_w": bound,
            "ratio": None, "basis": f"bound {bound * 1e3:.1f} mW exceeds {lim:.0%} of {p_rated * 1e3:.1f} mW"}


def load_series_digital(c_f, v, f_hz, r_ohm, r_pull_ohm=None):
    """Series resistor on a digital line: C V² f (C downstream of the resistor, f the fastest clock) + the DC current of
    the smallest pull through it, (V / R_pull)² R. Returns {"p_w", "dynamic_w", "pull_w"}."""
    dyn = float(c_f) * float(v) ** 2 * float(f_hz)
    pull = 0.0 if r_pull_ohm is None else (v / float(r_pull_ohm)) ** 2 * float(r_ohm)
    return {"p_w": dyn + pull, "dynamic_w": dyn, "pull_w": pull}


def load_series_termination(v_pp_line, r_ohm, matched=False):
    """Series termination of a differential line driver, per resistor, line shorted (envelope): (V_pp / 2)² / R;
    `matched=True`: (V_pp / 4)² / R."""
    v = float(v_pp_line) / (4.0 if matched else 2.0)
    return v * v / float(r_ohm)


def load_parallel_termination(v_diff_peak, r_ohm, topology):
    """Parallel termination of a differential bus, per resistor, square wave: `topology` "across" (one resistor
    between the wires) → V² / R, "split" (two in series, midpoint to a capacitor) → (V / 2)² / R."""
    if topology not in ("across", "split"):
        raise ValueError(f"topology must be 'across' or 'split', got {topology!r}")
    v = float(v_diff_peak) / (1.0 if topology == "across" else 2.0)
    return v * v / float(r_ohm)


def load_usb_series(i_a, r_ohm):
    """Series resistor on a USB 2.0 pair: P = I² R, the high-speed driver current taken as permanent (an envelope)."""
    i = float(i_a)
    return i * i * float(r_ohm)


def load_crystal_series(drive_level_w, r_ohm, esr_ohm):
    """Series resistor of a crystal: P = drive level × R / ESR."""
    return float(drive_level_w) * float(r_ohm) / float(esr_ohm)


def load_button_series(v, r_pull_ohm, r_ohm):
    """Series resistor of a push-button or jumper: I = V / (R_pull + R), P = I² R."""
    i = float(v) / (float(r_pull_ohm) + float(r_ohm))
    return i * i * r_ohm


def judgement(state="judged", ratio=None, deviations=(), flags=(), note=None):
    return {"state": state, "ratio": ratio, "deviations": list(deviations), "flags": list(flags), "note": note}


def not_judged(reason):
    """A part listed but not judged, with its reason: state "not judged: <reason>"."""
    code = getattr(reason, "code", None)
    state = f"not judged: {reason}"
    return judgement(state=Msg(state, "not_judged", reason=record(reason)) if code else state)


def judge_capacitor(v_applied, v_rated, c_f=None, dielectric=None, bias_done=None, policy=POLICY):
    """Capacitor: deviation above C_V × rated voltage; flag "effective capacitance to verify" for a class 2 dielectric
    of C_bias_min_f or more above C_bias × rated, unless `bias_done` names the calculation that used the effective
    value."""
    check_policy(policy)
    if v_rated is None:
        return not_judged(Msg("rating not read in the description (voltage)", "rating_not_read", what="voltage"))
    v, vr = float(v_applied), float(v_rated)
    ratio = v / vr
    j = judgement(ratio=ratio)
    if ratio > policy["C_V"] + 1e-12:
        j["deviations"].append(Msg(f"{v:.2f} V on {vr:g} V rated: {ratio:.0%} > {policy['C_V']:.0%}", "cap_voltage",
                                   v=v, rated=vr, ratio=ratio, limit=policy["C_V"]))
    class2 = is_class2(dielectric) and c_f is not None and c_f >= policy["C_bias_min_f"]
    if class2 and ratio > policy["C_bias"] + 1e-12:
        if bias_done:
            j["note"] = f"effective capacitance under bias already used: {bias_done}"
        else:
            j["flags"].append(Msg(f"{dielectric} at {ratio:.0%} of rated voltage: effective capacitance to verify",
                                  "cap_bias", dielectric=dielectric, ratio=ratio))
    return j


def judge_resistor(v_applied, r_ohm, p_rated_w, v_rated=None, p_w=None, policy=POLICY, tol=None):
    """Resistor: deviation when P = V² / (R (1 − tol)), or the given `p_w`, exceeds R_P × rated, or V the rated
    voltage; a 0 Ω link is not judged; a missing tolerance or rated voltage leaves it "not judged: rating not read"."""
    check_policy(policy)
    if p_rated_w is None:
        return not_judged(Msg("rating not read in the description (power)", "rating_not_read", what="power"))
    if r_ohm == 0:
        return not_judged(Msg("no voltage across it (0 Ω link)", "zero_ohm_link"))
    v, r, pr = float(v_applied), float(r_ohm), float(p_rated_w)
    missing = []
    if p_w is not None:
        p = float(p_w)
    elif tol is None:
        p, missing = None, ["tolerance"]
    else:
        p = v * v / (r * (1 - _tol(tol)))
    j = judgement(ratio=None if p is None else p / pr)
    if p is not None and p > policy["R_P"] * pr + 1e-12:
        j["deviations"].append(Msg(f"{p * 1e3:.2f} mW on {pr * 1e3:g} mW rated: {p / pr:.0%} > {policy['R_P']:.0%}",
                                   "res_power", p_w=p, rated_w=pr, ratio=p / pr, limit=policy["R_P"]))
    if v_rated is None:
        missing.append("voltage")
    elif v > v_rated + 1e-12:
        j["deviations"].append(Msg(f"{v:.2f} V above the rated voltage {v_rated:g} V", "res_voltage", v=v, rated=v_rated))
    if missing:
        j["state"] = not_judged(Msg(f"rating not read in the description ({missing[0]})", "rating_not_read",
                                    what=missing[0]))["state"]
    return j


def judge_diode(v_reverse, vrrm, description="", policy=POLICY):
    """Diode judged on its reverse voltage (deviation above D_V × VRRM) only when the description says Schottky,
    Rectifier or Switching; otherwise not judged (LED, Zener)."""
    check_policy(policy)
    if not re.search(r"Schottky|Rectifier|Switching", description or "", re.I):
        return not_judged(Msg("no reverse voltage to judge (LED, Zener)", "no_reverse_voltage"))
    if vrrm is None:
        return not_judged(Msg("rating not read in the description (reverse voltage)", "rating_not_read",
                              what="reverse voltage"))
    v, vr = float(v_reverse), float(vrrm)
    j = judgement(ratio=v / vr)
    if v > policy["D_V"] * vr + 1e-12:
        j["deviations"].append(Msg(f"{v:.2f} V reverse on {vr:g} V VRRM: {v / vr:.0%} > {policy['D_V']:.0%}",
                                   "diode_reverse", v=v, rated=vr, ratio=v / vr, limit=policy["D_V"]))
    return j


def judge_protection(vrwm, v_applied, mpn="", policy=POLICY):
    """TVS or ESD part: deviation when VRWM < the permanent DC voltage, flag when VRWM is less than `tvs_flag_margin`
    above it. A missing VRWM (None) raises: type it from the datasheet."""
    check_policy(policy)
    if vrwm is None:
        raise ValueError(f"protection {mpn or '?'} has no stand-off voltage (VRWM) entry: type it from its datasheet")
    vr, v = float(vrwm), float(v_applied)
    j = judgement(ratio=v / vr)
    if vr < v - 1e-12:
        j["deviations"].append(Msg(f"VRWM {vr:g} V < {v:.2f} V permanent", "vrwm_below", vrwm=vr, v=v))
    elif vr < v * (1 + policy["tvs_flag_margin"]) - 1e-12:
        j["flags"].append(Msg(f"VRWM {vr:g} V only {(vr - v) / v:.0%} above {v:.2f} V: leakage rises near the stand-off",
                              "vrwm_close", vrwm=vr, v=v, margin=(vr - v) / v))
    return j


def judge_inductor(i_peak_a, currents_a, policy=POLICY):
    """Power inductor: peak current against the LOWEST of the `…A` values of the description, deviation above L_I;
    `i_peak_a` None → not judged, with a flag."""
    check_policy(policy)
    if i_peak_a is None:
        j = not_judged(Msg("current not declared", "current_not_declared"))
        j["flags"].append(Msg("inductor without a declared current", "inductor_no_current"))
        return j
    if not currents_a:
        return not_judged(Msg("rating not read in the description (current)", "rating_not_read", what="current"))
    rated = float(min(currents_a))
    i = _finite(i_peak_a, "peak current")
    j = judgement(ratio=i / rated)
    if i > policy["L_I"] * rated + 1e-12:
        j["deviations"].append(Msg(f"{i:.2f} A peak on {rated:g} A rated: {i / rated:.0%} > {policy['L_I']:.0%}",
                                   "inductor_current", i=i, rated=rated, ratio=i / rated, limit=policy["L_I"]))
    return j


def judge_bead(i_a, rated_a, no_current=None, policy=POLICY):
    """Ferrite bead: current against FB_I × rated; `no_current` (a reason: signal line) → not judged with it; neither
    current nor reason → not judged, with a flag."""
    check_policy(policy)
    if no_current:
        return not_judged(no_current)
    if i_a is None:
        j = not_judged(Msg("current not declared", "current_not_declared"))
        j["flags"].append(Msg("bead without a declared current", "bead_no_current"))
        return j
    if rated_a is None:
        return not_judged(Msg("rating not read in the description (current)", "rating_not_read", what="current"))
    i, r = _finite(i_a, "current"), float(rated_a)
    j = judgement(ratio=i / r)
    if i > policy["FB_I"] * r + 1e-12:
        j["deviations"].append(Msg(f"{i:.2f} A on {r:g} A rated: {i / r:.0%} > {policy['FB_I']:.0%}", "bead_current",
                                   i=i, rated=r, ratio=i / r, limit=policy["FB_I"]))
    return j


def judge_temperature(t_max, ta_max, dt_board):
    """Every part: list of flags; flagged when the maximum operating temperature ≤ ambient + board rise, or not read
    (None)."""
    limit = _finite(ta_max, "ambient") + _finite(dt_board, "board rise")
    if t_max is None:
        return [Msg("maximum temperature not read in the description", "t_max_not_read")]
    return ([Msg(f"rated to {t_max:g} °C for {limit:g} °C of ambient + board rise", "t_max_low", t_max=float(t_max),
                 limit=limit)] if float(t_max) <= limit else [])


def judge_stock(stock, read_on, policy=POLICY):
    """Sourcing flags: stock under `stock_min`, zero blocking, None "stock unknown"; `read_on` (ISO date) required."""
    check_policy(policy)
    if not read_on:
        raise ValueError("a stock figure must carry the date it was read")
    if stock is None:
        return [Msg(f"stock unknown on {read_on}", "stock_unknown", date=read_on)]
    _finite(stock, "stock")
    if stock <= 0:
        return [Msg(f"zero stock on {read_on}: blocks an assembled order", "stock_zero", date=read_on)]
    if stock < policy["stock_min"]:
        return [Msg(f"stock {stock} < {policy['stock_min']} on {read_on}", "stock_low", stock=stock,
                    minimum=policy["stock_min"], date=read_on)]
    return []


def family_of(description, mpn=None, vrwm_mpns=(), ref=""):
    """Family from the catalogue description FIRST, the reference prefix (C, R, D, L, FB) only as a last resort.
    Returns {"family", "from": "description" | "reference", "disagrees": bool}."""
    d = description or ""
    found = None
    if (mpn and mpn in set(vrwm_mpns)) or re.search(r"\bTVS\b|\bESD\b", d):
        found = "protection"
    elif re.search(r"Common.Mode", d, re.I):
        found = "common_mode"
    elif re.search(r"Ferrite", d, re.I):
        found = "bead"
    elif re.search(r"Inductor", d, re.I):
        found = "inductor"
    elif re.search(r"Schottky|Rectifier|Switching|Diode", d, re.I):
        found = "diode"
    elif re.search(r"Capacitor", d, re.I):
        found = "capacitor"
    elif re.search(r"Resistor", d, re.I):
        found = "resistor"
    prefix = re.match(r"[A-Za-z]+", ref or "")
    by_ref = {"C": "capacitor", "R": "resistor", "D": "diode", "L": "inductor", "FB": "bead"}.get(
        prefix.group(0) if prefix else "")
    if found:
        return {"family": found, "from": "description", "disagrees": bool(by_ref) and by_ref != found}
    return {"family": by_ref, "from": "reference" if by_ref else None, "disagrees": False}


def domains_of(nets, domains, default="main"):
    """Domains spanned by a part ({net: domain}, `default` for the others): (sorted domains, note or None); more
    than one → a note "crosses A ↔ B", the part is not judged here."""
    seen = sorted({domains.get(n, default) for n in nets})
    if len(seen) > 1:
        return seen, Msg("crosses " + " ↔ ".join(seen) + ": judged by the isolation / ESD / surge chapters", "crosses",
                         domains=seen)
    return seen, None


def apply_acceptances(rows, accepted):
    """`rows` {ref: {"deviations", "mpn"}}; `accepted` {ref: {"mark", "mpn", "deviations": [texts, verbatim]}}.
    An accepted part's deviations are moved apart only while its part number and deviations are exactly the ones
    accepted; anything else raises. Returns {"counted", "accepted", "accepted_by_ref": {ref: (mark, deviations)}}."""
    accepted = dict(accepted or {})
    missing = sorted(set(accepted) - set(rows))
    if missing:
        raise ValueError(f"accepted deviations name references not on the board: {missing}")
    out, counted = {}, 0
    for ref, row in rows.items():
        devs = list(row.get("deviations", []))
        if ref not in accepted:
            counted += len(devs)
            continue
        dec = accepted[ref]
        if not isinstance(dec, dict) or not dec.get("mark") or not dec.get("deviations"):
            raise ValueError(f"{ref}: an acceptance is the mark of the designer's decision AND the accepted texts, "
                             "{'mark': 'A1', 'mpn': ..., 'deviations': [...]}; a bare mark would survive a change of "
                             "the stress")
        if not dec.get("mpn") or not row.get("mpn"):
            raise ValueError(f"{ref}: the acceptance {dec['mark']} and the judged row must both carry the part number "
                             "(a decision on one part does not cover its replacement)")
        if dec["mpn"] != row["mpn"]:
            raise ValueError(f"{ref}: part changed since the decision {dec['mark']} ({dec['mpn']} → {row['mpn']}): "
                             "re-decide with the designer")
        if not devs:
            raise ValueError(f"{ref} is declared accepted ({dec['mark']}) but no longer deviates: remove the acceptance")
        if sorted(devs) != sorted(dec["deviations"]):
            raise ValueError(f"{ref}: the deviation changed since the decision {dec['mark']} (accepted "
                             f"{sorted(dec['deviations'])}, now {sorted(devs)}): re-decide with the designer")
        out[ref] = (dec["mark"], devs)
    return {"counted": counted, "accepted": sum(len(d) for _, d in out.values()), "accepted_by_ref": out}


def count_states(rows):
    """{state: count} over the rows."""
    counts = {}
    for row in rows.values():
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return counts
