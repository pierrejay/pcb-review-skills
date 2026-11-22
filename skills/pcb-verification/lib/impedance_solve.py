"""Impedance of the keys of a board in the two passes of `pcb-check-impedance` (light, then fine near a limit), with
a bounded number of processes. Run with the venv; the board's solver script calls it under
`if __name__ == "__main__":` (processes are spawned on macOS).
"""
import os
from concurrent.futures import ProcessPoolExecutor

import impedance_keys as ik
from fieldsolver2d import default_step, solve

_SLABS, _FABS = {}, {}


def _init(slabs, fabs):
    _SLABS.update(slabs)
    _FABS.update(fabs)


def _z(task):
    key, st, factor, dw = task
    g, d = ik.geometry(key, _SLABS[st], _FABS[st], dw)
    step = (d or default_step(g)) * factor
    r = solve(g, d_fine=step)
    return key, st, factor, dw, float(r.get("zdiff", r.get("z0"))), float(r.get("er_eff_odd", r.get("er_eff")))


def targets_of(entries):
    """{key: [targets in the key's own terms]} from [(target Ω, pair, keys)] of every link: a single-line key used in a
    pair gets the pair's target / 2."""
    out = {}
    for target, pair, keys in entries:
        t = float(target)
        for k in keys:
            own = t / 2 if pair and not ik.parse_key(k)["pair"] else t
            out.setdefault(k, []).append(own)
    return out


def _run(tasks, workers):
    if not tasks:
        return []
    if workers == 1:
        return [_z(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(dict(_SLABS), dict(_FABS))) as ex:
        return list(ex.map(_z, tasks, chunksize=1))


def solve_keys(todo, slabs, fabs, targets, workers=2, tol=ik.TOL, band=ik.RICHARDSON_BAND, fine_all=False,
               corners=()):
    """Solve the (key, stackup name) pairs of `todo` (slabs {name: Slab}, fabs {name: fabricator dict}) at 2 × and 4 ×
    the fine step, extrapolated, then at the fine step where `needs_fine` against `targets` {key: [Ω]} (every value
    with fine_all), in at most `workers` processes. Returns {(key, stackup): {"z" (Zdiff for a pair key, else Z0),
    "pass", "er_eff"}}, plus "z_narrow", "z_wide" and their "pass_narrow", "pass_wide" for the keys of `corners`."""
    workers = min(int(workers), os.cpu_count() or 1)
    todo = list(dict.fromkeys((k, st) for k, st in todo))
    missing = sorted({st for _, st in todo if st not in slabs or st not in fabs})
    if missing:                                  # _SLABS keeps the stackups of an earlier call
        raise ValueError(f"stackups without a Slab or a fabricator dict: {missing}")
    _init(slabs, fabs)
    corners = set(corners)
    out, solvable = {}, []
    for k, st in todo:
        if ik.parse_key(k)["kind"] == "se_np":
            out[(k, st)] = {"z": ik.NO_RETURN_OHM, "pass": "none"}
            if k in corners:
                out[(k, st)].update(z_narrow=ik.NO_RETURN_OHM, pass_narrow="none", z_wide=ik.NO_RETURN_OHM,
                                    pass_wide="none")
        else:
            solvable.append((k, st))
    dws = {st: 2 * float(fabs[st]["etch_tolerance_per_flank"]) for st in {s for _, s in solvable}}
    # (field of the impedance, field of its pass, width excursion) of each section of a key: nominal, then corners
    sections = {(k, st): [("z", "pass", 0.0)] + ([("z_narrow", "pass_narrow", -dws[st]),
                                                  ("z_wide", "pass_wide", dws[st])] if k in corners else [])
                for k, st in solvable}
    tasks = [] if fine_all else [(k, st, f, dw) for (k, st), sec in sections.items() for _, _, dw in sec
                                 for f in (2, 4)]
    light = {}
    for k, st, f, dw, z, *er in _run(tasks, workers):        # er: εeff (absent from a stand-in that returns z only)
        light.setdefault((k, st, dw), {})[f] = (z, er[0] if er else None)
    fine, fine_fields = [], []
    for (k, st), sec in sections.items():
        e = out[(k, st)] = {}
        for zf, pf, dw in sec:
            if fine_all:
                e[zf], e[pf] = None, "fine"
            else:
                c = light[(k, st, dw)]
                e[zf], e[pf] = ik.richardson(c[2][0], c[4][0]), "light"
                if zf == "z" and c[2][1] is not None:
                    e["er_eff"] = c[2][1]
                if not ik.needs_fine(e[zf], targets.get(k, []), tol, band):
                    continue
            fine.append((k, st, 1, dw))
            fine_fields.append((zf, pf))
    for (zf, pf), (k, st, _, _, z, *er) in zip(fine_fields, _run(fine, workers)):
        out[(k, st)][zf], out[(k, st)][pf] = z, "fine"
        if zf == "z" and er:
            out[(k, st)]["er_eff"] = er[0]
    return out


def pending(cache, pairs, targets, corners=(), tol=ik.TOL, band=ik.RICHARDSON_BAND):
    """Pairs of `pairs` that `solve_keys` must still solve against `cache` {"<stackup>|<key>": entry}: no finite "z",
    a key of `corners` without its corners, or a light value that `needs_fine` now sends to the fine pass."""
    corners = set(corners)
    out = []
    for k, st in dict.fromkeys(pairs):
        e = cache.get(f"{st}|{k}")
        fields = [("z", "pass")] + ([("z_narrow", "pass_narrow"), ("z_wide", "pass_wide")] if k in corners else [])
        if not isinstance(e, dict) or not all(ik._finite_pos(e.get(zf)) for zf, _ in fields):
            out.append((k, st))
        elif any(e.get(pf, "light") == "light" and ik.needs_fine(e[zf], targets.get(k, []), tol, band)
                 for zf, pf in fields):
            out.append((k, st))
    return out
