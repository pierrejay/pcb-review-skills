"""Pull resistors, pin networks and decoupling capacitors seen from the pins of an IC, read with pcbnew (KiCad's
bundled Python), as assembled in the named assembly variant (`variant`: '' for the default; required when the board
has variants)."""
import re

import pcbnew as P

from values import ohms


def _real(net):
    return bool(net) and not net.startswith("unconnected-")


def _variant(board, variant):
    names = [v for v in board.GetVariantNamesForUI() if board.HasVariant(v)]
    if variant is None:
        if names:                                # each variant may fit other pulls: say which one is read
            raise ValueError(f"the board has assembly variants {names}: name the one to read (variant=…, '' for "
                             "the default)")
        return ""
    if variant and variant not in names:
        raise ValueError(f"no assembly variant {variant!r} on the board (variants: {names})")
    return variant


def read_pulls(board, pins, rails, series_max=100, variant=None):
    """pins: [(ref, pin)] → {(ref, pin): (net, [(ohms, rail), …] sorted, ["R12 2.49k → RAIL", …], [DNP refs],
    ["R7 10k → NET", …] to other nets)}, seen through series resistors ≤ series_max Ω. A pin on a rail gives
    [(0, rail)]; an empty list means no external pull; two equal resistors in parallel count twice."""
    v = _variant(board, variant)
    rails = set(rails)
    pads = {(f.GetReference(), p.GetNumber()): p for f in board.GetFootprints() for p in f.Pads()}
    missing = sorted(rails - {p.GetNetname() for p in pads.values()})
    if missing:                                  # a renamed rail would turn every pull to it into "no pull"
        raise ValueError(f"rails with no pad on the board: {missing}")
    by_net, refuse, dnp = {}, {}, {}             # net → [(ref, value, ohms, net of its other pad)]
    for f in board.GetFootprints():
        ref, nets = f.GetReference(), [p.GetNetname() for p in f.Pads()]
        value = f.GetFieldValueForVariant(v, "Value")
        up = ref.upper()
        is_r = up.startswith("R")
        reads_as_r = bool(re.search(r"[RkKMΩ]", value))
        if reads_as_r:                           # "0R", "10k": a resistance written on a part named otherwise
            try:
                ohms(value)
            except ValueError:
                reads_as_r = False
        off = f.GetDNPForVariant(v)
        excluded = f.GetExcludedFromBOMForVariant(v) or f.GetExcludedFromPosFilesForVariant(v)
        if up.startswith(("JP", "SJ")):
            why = "jumper or solder jumper: open or closed is not on the board"
        elif is_r and up.startswith(("RT", "RV")):
            why = "thermistor or varistor"
        elif is_r and len(nets) != 2:
            why = "resistor array or network"
        elif not is_r and len(nets) == 2 and reads_as_r:
            why = f"value {value!r} reads as a resistance but the reference is not R…"
        elif is_r and excluded and not off:
            why = "excluded from the BOM or the placement files but not DNP: assembled or not?"
        elif is_r:
            why = None
        else:
            continue
        if why:
            for n in nets:
                if _real(n):
                    refuse.setdefault(n, set()).add(f"{ref} ({why})")
            continue
        a, c = f.Pads()
        if off:                                  # not assembled: no pull, but said
            for n in (a.GetNetname(), c.GetNetname()):
                dnp.setdefault(n, set()).add(ref)
            continue
        if _real(a.GetNetname()) and _real(c.GetNetname()):   # a pad with no net connects nothing
            try:
                r = ohms(value)
            except ValueError as e:              # refused only where it is read
                for n in (a.GetNetname(), c.GetNetname()):
                    refuse.setdefault(n, set()).add(f"{ref} ({e})")
                continue
            by_net.setdefault(a.GetNetname(), []).append((ref, value, r, c.GetNetname()))
            by_net.setdefault(c.GetNetname(), []).append((ref, value, r, a.GetNetname()))
    out = {}
    for ref, pin in pins:
        net = pads[(ref, pin)].GetNetname()
        if not _real(net):
            out[(ref, pin)] = (net, [], [], [], [])
            continue
        if net in rails:                         # tied directly to a rail: a source of 0 Ω, never "no pull"
            out[(ref, pin)] = (net, [(0, net)], [f"direct → {net}"], [], [])
            continue
        nets, todo = {net}, [net]                # closure over small series resistors (a chain of 0 Ω included)
        while todo:
            for _, _, r, other in by_net.get(todo.pop(), []):
                if other not in rails and r <= series_max and other not in nets:
                    nets.add(other); todo.append(other)
        hit = sorted({r for n in nets for r in refuse.get(n, ())})
        if hit:
            raise ValueError(f"{ref}.{pin}: {hit} on a net read; handle this pin by hand")
        seen = [e for n in sorted(nets) for e in by_net.get(n, []) if e[3] in rails]
        aside = sorted({(e[0], e[1], e[3]) for n in nets for e in by_net.get(n, []) if e[3] not in rails | nets})
        out[(ref, pin)] = (net, sorted((r, rail) for _, _, r, rail in seen),
                           [f"{rr} {vv} → {rail}" for rr, vv, _, rail in seen],
                           sorted({r for n in nets for r in dnp.get(n, ())}),
                           [f"{rr} {vv} → {other}" for rr, vv, other in aside])
    return out


def pin_networks(board, ref, near_mm=5, crowd=6, skip=("GND",), variant=None):
    """→ [(pin, net, [(part, value, other net, distance mm, dnp), …], parts on the net)] in pin order: the two-pad
    parts on each pin's net with the net of their other pad; past `crowd` parts, only those within near_mm."""
    v = _variant(board, variant)
    ic = board.FindFootprintByReference(ref)
    by_net = {}
    for f in board.GetFootprints():
        pads = f.Pads()
        if f.GetReference() == ref or len(pads) != 2:
            continue
        a, c = pads
        for x, y in ((a, c), (c, a)):
            if _real(x.GetNetname()):
                by_net.setdefault(x.GetNetname(), []).append(
                    (f.GetReference(), f.GetFieldValueForVariant(v, "Value"), y.GetNetname(), x.GetPosition(),
                     f.GetDNPForVariant(v)))
    out, done = [], set()
    key = lambda p: (int(p.GetNumber()) if p.GetNumber().isdigit() else 10 ** 6, p.GetNumber())  # noqa: E731
    for p in sorted(ic.Pads(), key=key):
        net = p.GetNetname()
        parts = by_net.get(net, [])
        if not _real(net) or net in skip or (net in done and len(parts) <= crowd):
            continue
        done.add(net)
        rows = [(r, val, other, round(P.ToMM((pos - p.GetPosition()).EuclideanNorm()), 1), dnp)
                for r, val, other, pos, dnp in parts]
        if len(rows) > crowd:
            rows = [x for x in rows if x[3] <= near_mm]
        out.append((p.GetNumber(), net, sorted(rows, key=lambda x: x[3]), len(parts)))
    return out


def decoupling_rows(board, ref, rails, grounds=("GND",), near_mm=5, bulk_F=1e-6, ferrite_bulk_F=10e-6, variant=None):
    """→ [(pin, net, "behind L1" or "", [(part, value, mm), …] capacitors to `grounds` within near_mm, state)] for
    the supply pins of `ref` (on a rail, or behind a ferrite or inductor from one); state "ok" or what the screening
    thresholds near_mm, bulk_F and ferrite_bulk_F flag."""
    from values import farads
    rails, grounds = set(rails), set(grounds)
    on_board = {p.GetNetname() for f in board.GetFootprints() for p in f.Pads()}
    if rails - on_board:                         # a renamed rail would silently skip its pins
        raise ValueError(f"rails with no pad on the board: {sorted(rails - on_board)}")
    out = []
    for pin, net, parts, _ in pin_networks(board, ref, near_mm=max(near_mm, 30), crowd=0, skip=tuple(grounds),
                                           variant=variant):
        behind = [r for r, v, other, d, dnp in parts if other in rails and r.upper().startswith(("L", "FB")) and not dnp]
        # behind an inductor only if the net is decoupled somewhere: a switch node (buck inductor) has no capacitor
        # to ground and is not a supply pin; a filtered supply with none at all stays visible in pin_networks
        if behind and not any(other in grounds and r.upper().startswith("C") for r, v, other, d, dnp in parts):
            behind = []
        if net not in rails and not behind:
            continue
        caps = [(r, v, d) for r, v, other, d, dnp in parts
                if other in grounds and r.upper().startswith("C") and not dnp and d <= near_mm]
        big = [c for c in caps if farads(c[1]) >= 0.999 * (ferrite_bulk_F if behind else bulk_F)]   # 10 µF ≥ 10 µF
        if not caps:
            state = f"no capacitor within {near_mm} mm"
        elif behind and not big:
            state = f"bulk after the ferrite under {ferrite_bulk_F * 1e6:g} µF"
        elif not big:
            state = f"no bulk ≥ {bulk_F * 1e6:g} µF within {near_mm} mm"
        else:
            state = "ok"
        out.append((pin, net, f"behind {behind[0]}" if behind else "", caps, state))
    return out

