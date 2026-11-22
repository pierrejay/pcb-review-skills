"""Derating engine of a board (`pcb-check-derating-sourcing`, method, "Algorithm"): `analyse` judges every
fitted footprint of the BOM with `derating_rules` against the board's configuration, `summary` gives the JSON.
Runs under KiCad's bundled Python (pcbnew)."""
import derating_rules as dr
from messages import Msg, records

CROSSED = ("R", "L", "FB", "D", "F")       # two-pad parts a DC level goes through (R, L, bead, diode, fuse)
CONNECTORS = ("J", "P", "X", "CN", "USB")  # reference prefixes of the parts through which a net leaves the board


def _prefix(ref):
    i = 0
    while i < len(ref) and ref[i].isalpha():
        i += 1
    return ref[:i].upper()


def _variant(board, variant):    # an unnamed or unknown variant would silently judge the default fit
    names = [v for v in board.GetVariantNamesForUI() if board.HasVariant(v)]
    if variant is None:
        if names:
            raise ValueError(f"the board has assembly variants {names}: name the one to judge (variant=…, '' for "
                             "the default)")
        return ""
    if variant and variant not in names:
        raise ValueError(f"no assembly variant {variant!r} on the board (variants: {names})")
    return variant


def _fitted(f, variant):         # neither DNP nor excluded from the BOM in that variant
    return not (f.GetDNPForVariant(variant) or f.GetExcludedFromBOMForVariant(variant))


def reach_spans(board, rails, v_default, crossed=CROSSED, variant=""):
    """{undeclared net: (V low, V high)}: [0, v_default] widened to every declared rail the net reaches through
    two-pad parts of the `crossed` prefixes not DNP in `variant`. A bound, not the operating voltage."""
    spans, adj = dr.rail_spans(rails), {}
    hi0 = float(v_default)
    for f in board.GetFootprints():
        pads = list(f.Pads())
        if len(pads) == 2 and _prefix(f.GetReference()) in crossed and not f.GetDNPForVariant(variant):
            a, b = pads[0].GetNetname(), pads[1].GetNetname()
            if a and b and a != b:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
    out = {}
    for net in adj:
        if net in spans:
            continue
        lo, hi, seen, todo = 0.0, hi0, {net}, [net]
        while todo:
            for n in adj.get(todo.pop(), ()):
                if n in spans:
                    lo, hi = min(lo, spans[n][0]), max(hi, spans[n][1])
                elif n not in seen:
                    seen.add(n)
                    todo.append(n)
        out[net] = (lo, hi)
    return out


OUTSIDE_POLICY = ("not judged: family outside the policy (integrated circuit, connector, LED, crystal…): temperature "
                  "and stock only")


def _stale(cfg, refs):
    keys = [k for t in ("currents", "no_current", "forced_voltages", "bias_done", "notes", "powers", "families")
            for k in cfg.get(t, {}) if k not in refs]
    if keys:
        raise ValueError(f"references declared by the board but not in the BOM analysed: {sorted(set(keys))}")


def analyse(board, cache, cfg, supplier_field="Supplier Part", variant=None):
    """One row per footprint fitted in `variant` ("" the default; required when the board has variants), each "judged"
    or "not judged: <reason>". `cache` {supplier part: {"description", "mpn", "stock", "read_on", "category"}}; `cfg`
    the board table of the method, plus `t_max` {mpn: (°C, source)}, `families` {ref: (family or None, reason)},
    `connectors` (reference prefixes) when needed; a `powers` value is (W or a function R → W,
    justification)."""
    dr.rail_spans(cfg["rails"])
    var = _variant(board, variant)
    on_board = {q.GetNetname() for f in board.GetFootprints() for q in f.Pads()}
    stale = sorted(set(cfg["rails"]) - on_board) + sorted(set(cfg.get("domains", {})) - on_board)
    if stale:                                   # a renamed rail would fall back to v_default, a domain to "main"
        raise ValueError(f"nets of `rails` / `domains` with no pad on the board: {stale}")
    undeclared = reach_spans(board, cfg["rails"], cfg["v_default"], variant=var)
    off_board = {q.GetNetname() for f in board.GetFootprints() if _prefix(f.GetReference()) in
                 tuple(cfg.get("connectors", CONNECTORS)) for q in f.Pads() if q.GetNetname()}
    pads_by_net = {}            # net → [(ref, pad number)]: a resistor in series with a pin
    for f in board.GetFootprints():
        for q in f.Pads():
            if q.GetNetname():
                pads_by_net.setdefault(q.GetNetname(), []).append((f.GetReference(), q.GetNumber()))
    rows, missing, powers_used = [], [], set()
    for f in board.GetFootprints():
        ref = f.GetReference()
        if not _fitted(f, var):
            continue
        code = f.GetFieldValueForVariant(var, supplier_field).strip()     # the part the variant fits
        info = cache.get(code)
        if not info:
            missing.append(f"{ref} ({code or 'no supplier part number'})")
            continue
        desc = info.get("description") or ""
        rating = dr.parse_description(desc)
        if rating["t_max"] is None and info.get("mpn") in cfg.get("t_max", {}):
            t, src = cfg["t_max"][info["mpn"]]
            rating["t_max"], rating["t_source"] = t, "datasheet: " + src
        sources = {}
        for key, table in (("v", "v_rated"), ("tol", "r_tol")):   # a rating the description does not print
            if rating[key] is None and info.get("mpn") in cfg.get(table, {}):
                rating[key], src = cfg[table][info["mpn"]]
                sources[key] = "datasheet: " + src
        fam = dr.family_of(desc, info.get("mpn"), cfg["vrwm"], ref)
        if ref in cfg.get("families", {}):           # a family read wrong from the description (an IC with "ESD")
            fam = {"family": cfg["families"][ref][0], "disagrees": False}
        family = fam["family"]
        r = {"ref": ref, "value": f.GetFieldValueForVariant(var, "Value"), "mpn": info.get("mpn"),
             "supplier_part": code, "stock": info.get("stock"), "read_on": info.get("read_on"),
             "category": info.get("category"), "family": family, "t_max": rating["t_max"],
             "t_source": rating["t_source"], "deviations": [], "flags": []}
        if fam["disagrees"]:
            r["family_disagrees"] = True
        if sources:
            r["rating_source"] = sources
        r["flags"] += dr.judge_stock(info.get("stock"), info.get("read_on"))
        r["flags"] += dr.judge_temperature(rating["t_max"], cfg["ta_max"], cfg["dT_board"])
        nets = sorted({q.GetNetname() for q in f.Pads()
                       if q.GetNetname() and not q.GetNetname().startswith("unconnected")})
        j = None
        if len(nets) >= 2 and (family == "protection" or (len(nets) <= 3 and family is not None)):
            r["nets"] = nets
            _, crossing = dr.domains_of(nets, cfg.get("domains", {}))
            leaving = sorted(n for n in nets if n in off_board and n not in cfg["rails"]
                             and ref not in cfg.get("forced_voltages", {}))
            if crossing:
                r["note"] = crossing
                j = dr.not_judged(Msg("crosses a barrier (isolation, chassis)", "crosses_barrier"))
            elif leaving:
                j = dr.not_judged(Msg(f"off-board net not declared ({', '.join(leaving)}): declare its range",
                                      "off_board_undeclared", nets=leaving))
            else:
                forced = cfg.get("forced_voltages", {}).get(ref)
                av = dr.applied_voltage(nets, cfg["rails"], cfg["v_default"], forced, undeclared)
                v = av["v"]
                if forced:
                    r["v_case"] = forced[1]
                r.update(v_applied=round(v, 3), v_assumed=av["assumed"])
                two_signals = forced is None and sum(n not in cfg["rails"] for n in nets) >= 2
                if family == "protection":
                    r["rating"] = {"vrwm": cfg["vrwm"].get(info.get("mpn"))}
                    j = dr.judge_protection(r["rating"]["vrwm"], v, info.get("mpn") or "")
                elif family == "capacitor":
                    r["rating"] = {"v": rating["v"]}
                    j = dr.judge_capacitor(v, rating["v"], rating["f"], rating["dielectric"],
                                           cfg.get("bias_done", {}).get(ref))
                elif family == "resistor":
                    p_w = None
                    if two_signals and rating["ohm"] and rating["w"] and rating["tol"] is None:
                        if ref in cfg.get("powers", {}):     # not judged for its tolerance: the declaration waits
                            powers_used.add(ref)
                    elif two_signals and rating["ohm"] and rating["w"]:
                        decl = cfg.get("powers", {}).get(ref)
                        if decl is not None:
                            w, why = decl
                            decl = (w(rating["ohm"]) if callable(w) else w, why)
                        rb = dr.resistor_between_signals(rating["ohm"], rating["w"], v,
                                                         dr.POLICY["R_P"], decl, tol=rating["tol"])
                        declared = decl is not None and rb["basis"].startswith("declared")
                        r["p_case"] = "worst case: opposed levels of the two signals" \
                            if rb["basis"].startswith("worst") else (decl[1] if decl else None)
                        if rb["p_w"] is None or declared:
                            r["p_bound_w"] = round(rb["bound_w"], 6)
                            alone = [o[0] for n in nets if len(nets) == 2
                                     for o in [[x for x in pads_by_net[n] if x[0] != ref]] if len(o) == 1]
                            if alone:
                                r["series_pin"] = " or ".join(f"{c}.{num}" for c, num in alone)
                        if declared:
                            r["p_declared"] = True
                            powers_used.add(ref)
                        if rb["state"] != "judged":         # a coded "not judged: power to determine": kept coded
                            j = (dr.judgement(state=rb["state"]) if getattr(rb["state"], "code", None)
                                 else dr.not_judged(rb["state"].split(": ", 1)[1]))
                        p_w = rb["p_w"]
                    r["rating"] = {"ohm": rating["ohm"], "w": rating["w"], "v": rating["v"], "tol": rating["tol"]}
                    if j is None:
                        j = dr.judge_resistor(v, rating["ohm"] if rating["ohm"] is not None else 0, rating["w"],
                                              rating["v"], p_w, tol=rating["tol"]) \
                            if rating["ohm"] is not None or rating["w"] is None else \
                            dr.not_judged(Msg("rating not read in the description (power)", "rating_not_read",
                                              what="power"))
                elif family == "diode":
                    r["rating"] = {"vrrm": rating["v"]}
                    j = dr.judge_diode(v, rating["v"], desc)
        if family in ("inductor", "bead", "common_mode"):
            i, src = cfg.get("currents", {}).get(ref, (None, None))
            no_current = cfg.get("no_current", {}).get(ref)
            if i is not None:
                r["i_peak_a"], r["i_source"] = i, src
            r["rating"] = {"a": rating["a"]}
            if family == "bead":
                j = dr.judge_bead(i, min(rating["a"]) if rating["a"] else None, no_current)
            elif no_current:
                j = dr.not_judged(no_current)
            else:
                j = dr.judge_inductor(i, rating["a"])
            if i is None and not no_current:
                r["flags"].append(Msg("current not declared by the board (`currents` or `no_current`): not judged",
                                      "current_not_declared"))
        if ref in cfg.get("notes", {}):
            r["note"] = cfg["notes"][ref]
        if j is not None:
            r["ratio"] = None if j["ratio"] is None else round(j["ratio"], 4)
            r["deviations"] += j["deviations"]
            r["flags"] += j["flags"]
            if r.get("v_assumed") and j["state"] == "judged" and j["ratio"] is not None and j["ratio"] > 0.5:
                r["flags"].append(Msg(f"judged on an assumed voltage at {j['ratio']:.0%} of its rating: declare its "
                                      "nets", "assumed_near_rating", ratio=j["ratio"]))
            if j["note"]:
                r["note"] = j["note"]
        r["state"] = j["state"] if j else OUTSIDE_POLICY
        rows.append(r)
    if missing:
        raise ValueError(f"{len(missing)} part(s) of the BOM without catalogue data: {', '.join(missing)} "
                         "(complete the cache)")
    _stale(cfg, {r["ref"] for r in rows})
    unused = sorted(set(cfg.get("powers", {})) - powers_used)
    if unused:
        raise ValueError(f"declared power without object (resistor judged without it): {unused}; remove it")
    acc = dr.apply_acceptances({r["ref"]: {"deviations": r["deviations"], "mpn": r["mpn"]} for r in rows},
                               cfg.get("accepted_deviations", {}))
    for r in rows:
        if r["ref"] in acc["accepted_by_ref"]:
            r["accepted"] = acc["accepted_by_ref"][r["ref"]][0]
    return rows


def summary(rows, cfg):
    """The JSON of the result: policy, rules, scope, rails, parts (messages as records), counts of deviations, flags
    and states, accepted deviations, declared powers, `to_determine`."""
    counted = [r for r in rows if r["deviations"] and not r.get("accepted")]
    accepted = [r for r in rows if r["deviations"] and r.get("accepted")]
    states = {}
    for r in rows:
        states[r["state"]] = states.get(r["state"], 0) + 1
    parts = [{**r, "deviations": records(r["deviations"]), "flags": records(r["flags"]),
              **({"note": records([r["note"]])[0]} if r.get("note") else {})} for r in rows]
    return {"policy": dr.POLICY, "rules": dr.FAMILY_RULES,
            "scope": {"ta_max": cfg["ta_max"], "dT_board": cfg["dT_board"], "v_default": cfg["v_default"]},
            "rails": cfg["rails"], "parts": parts, "deviations": sum(len(r["deviations"]) for r in counted),
            "flags": sum(len(r["flags"]) for r in rows),
            "accepted_deviations": [{"ref": r["ref"], "mpn": r["mpn"], "mark": r["accepted"],
                                     "deviations": records(r["deviations"])} for r in accepted],
            "assumed": sum(1 for r in rows if r.get("v_assumed")), "states": states,
            "declared_powers": [{"ref": r["ref"], "value": r["value"], "ratio": r.get("ratio"), "p_case": r["p_case"]}
                                for r in rows if r.get("p_declared")],
            "to_determine": [{"ref": r["ref"], "value": r["value"], "nets": r["nets"], "p_bound_w": r["p_bound_w"],
                              "rated_w": r["rating"]["w"], "series_pin": r.get("series_pin")}
                             for r in rows if r["state"].startswith("not judged: power to determine")]}
