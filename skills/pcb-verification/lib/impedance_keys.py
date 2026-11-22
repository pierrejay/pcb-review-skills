"""Cross-section keys of the impedance check (`make_key`, `parse_key`), their reading as a `fieldsolver2d.Geometry` on
a stackup and a fabricator file, the cache signature, and the per-link judgement. Pure Python, any interpreter;
lengths in mm.
"""
import numbers
import hashlib
import json
import math
from pathlib import Path

KINDS = ("se", "diff", "se_np", "diff_np", "se_p2", "diff_p2")
NO_RETURN_OHM = 999.0        # sentinel of a single line in a cutout: no return path, a deviation by construction
COUPLE_MM = 0.5              # floor of the coupling limit over the adjacent plane (`reach_mm`); beyond it, a lone leg
FAR_COUPLE_MM = 3.0          # over a far plane two legs stay coupled far beyond COUPLE_MM: searched up to 3 mm
CUTOUT_GAP_CAP_MM = 1.5      # a pair without plane is solved at its real gap up to this; beyond, a lower bound
SIDE_REACH_MM = 0.6          # floor of the side-ground reach (`reach_mm`); ground beyond the reach is absent
COUPLE_H = 5.0               # coupling limit = 5 h: 2 × Z0 then overstates Zdiff by 1.7 to 2.3 % (`reach_mm`)
SIDE_REACH_H = 6.0           # side-ground reach = 6 h: a ground there moves Z0 by 0.04 to 0.1 % (`reach_mm`)
SIDE_STEP_MM = 0.01          # step of the side-ground walk over the plane
OFF_PLANE_GAP_STEP_MM = 0.05  # off the plane the side gap is rounded up to this (impedance varies slowly, solver costly)
FAR_GAP_H = 3.0              # beyond 3 h over the plane a gap moves Z slowly: coarser key (`coarsen_far`)
FAR_SIDE_STEP_MM = 0.05      # side gap beyond 3 h: nearest 0.05 mm (`coarsen_far`)
FAR_PAIR_STEP_MM = 0.02      # pair gap beyond 3 h: nearest 0.02 mm
TOL = 0.10                   # default tolerance when the link's datasheet or standard gives none
L_TRANS_MM = 3.0             # screening value: an out-of-tolerance run of at most this length is a local transition
NEIGHBOUR_MM = 0.25          # two sampled points (0.1 mm step) closer than this belong to the same run
HEAL_MM = 1.0                # screening value: conforming length that must pass before a run ends (`runs`)
LIMIT_EPS = 1e-9             # relative: a value on a tolerance limit, within floating-point roundoff, is on it
C_MM_PER_S = 299792458e3     # speed of light, mm/s (`delay_per_mm`)
FAB_KEYS = ("outer_copper_base", "outer_copper_finished", "inner_copper", "etch_top_width_reduction",
            "etch_tolerance_per_flank", "solder_mask_on_laminate", "solder_mask_on_copper", "solder_mask_er",
            "via_plating")


# --- keys -----------------------------------------------------------------------------------------------------------
def _finite_pos(v):
    return not isinstance(v, bool) and isinstance(v, numbers.Real) and math.isfinite(v) and v > 0


def _float_or_none(v):
    return None if v is None else float(v)


def out_of_tolerance(z, target, tol=TOL):
    """True when `z` lies outside [target · (1 − tol), target · (1 + tol)]; a value on a limit (within LIMIT_EPS,
    relative) is inside."""
    return abs(float(z) / float(target) - 1) > float(tol) + LIMIT_EPS


def round_gap_side(d_mm):
    """Side gap over the adjacent plane as the key keeps it: to 1 µm; None stays None."""
    return None if d_mm is None else round(float(d_mm), 3)


def coarsen_far(d_mm, h_mm, step_mm):
    """A gap over the adjacent plane as the key keeps it: unchanged under FAR_GAP_H × h_mm, else the nearest multiple
    of step_mm (FAR_SIDE_STEP_MM for a side gap, FAR_PAIR_STEP_MM for a pair gap); None stays None."""
    if d_mm is None:
        return None
    d, h, st = float(d_mm), float(h_mm), float(step_mm)
    return d if d < FAR_GAP_H * h else round(round(d / st) * st, 3)


def reach_mm(h_mm):
    """(coupling limit, side-ground reach) in mm over the adjacent plane for a prepreg of h_mm:
    (max(COUPLE_MM, COUPLE_H × h), max(SIDE_REACH_MM, SIDE_REACH_H × h))."""
    h = float(h_mm)
    return round(max(COUPLE_MM, COUPLE_H * h), 4), round(max(SIDE_REACH_MM, SIDE_REACH_H * h), 4)


def check_sampled_h(sample, slab, tol_mm=0.0005):
    """Raise ValueError unless `sample` (`kicad_sampling.sample_link`) was sampled for the build `slab`: h_prepreg_mm
    equal to its prepreg, h_max_mm at least it. Returns the number of keys checked."""
    h, hmax = sample.get("h_prepreg_mm"), sample.get("h_max_mm")
    if h is None or hmax is None:
        raise ValueError("sample without h_prepreg_mm / h_max_mm: re-sample it with kicad_sampling")
    layers = sorted({parse_key(k)["layer"] for k in sample["bins"]})
    for layer in layers:
        hs = slab.h_prepreg(layer)
        if hs > float(hmax) + tol_mm:
            raise ValueError(f"sampled with the reach of a {hmax} mm prepreg; stackup {slab.name!r} has {hs} mm under "
                             f"{layer}: legs {reach_mm(hmax)[0]} to {reach_mm(hs)[0]} mm apart were counted 2 × Z0")
        if abs(hs - float(h)) > tol_mm:
            raise ValueError(f"sampled with h_prepreg_mm {h}; stackup {slab.name!r} has {hs} mm under {layer}: the "
                             "coarser rounding and the oblique gaps used another height, sample this build on its own")
    return len(sample["bins"])


def round_gap_off_plane(d_mm, reach_mm=SIDE_REACH_MM):
    """Side gap off the adjacent plane (cutout or far plane): rounded up to OFF_PLANE_GAP_STEP_MM, None beyond
    reach_mm."""
    if d_mm is None:
        return None
    d = float(d_mm)
    if d > reach_mm:
        return None
    return round(math.ceil(d / OFF_PLANE_GAP_STEP_MM - 1e-9) * OFF_PLANE_GAP_STEP_MM, 2)


def round_s(s_mm, situation):
    """Pair gap of a key, mm: to 10 µm over the plane; in a cutout (capped at CUTOUT_GAP_CAP_MM) and over a far plane,
    to 10 µm under COUPLE_MM and 0.1 mm above. situation: "plane", "cutout" or "far"."""
    s = float(s_mm)
    if situation == "plane":
        return round(s, 2)
    s = min(s, CUTOUT_GAP_CAP_MM) if situation == "cutout" else s
    return round(s, 2) if s < COUPLE_MM else round(round(s / 0.1) * 0.1, 1)


def make_key(situation, layer, w_mm, gaps, partner=None, ref_layer=None):
    """The key (JSON text) of one sampled point. situation: "plane" | "cutout" | "far"; partner: None for a single
    line, else (w_partner_mm, s_mm rounded by `round_s`); gaps: (g_left, g_right) in any order for a single line,
    (g_self, g_partner) for a pair; ref_layer: name of the far plane's layer, "far" only."""
    suffix = {"plane": "", "cutout": "_np", "far": "_p2"}[situation]
    w = round(float(w_mm), 3)
    if partner is None:
        g = sorted((round_gap_side(x) for x in gaps), key=lambda v: (v is None, v))
        key = ["se" + suffix, layer, w] + g
    else:
        wp, s = partner
        key = ["diff" + suffix, layer, w, round(float(wp), 3), float(s),
               round_gap_side(gaps[0]), round_gap_side(gaps[1])]
    if situation == "far":
        key.append(ref_layer)
    return json.dumps(key)


def parse_key(key):
    """Fields of a key (JSON text or list): {"kind", "situation", "layer", "w", "w_partner", "s", "gaps", "ref_layer",
    "pair"}. Keys: [kind, layer, w, g1, g2] for se, se_np, se_p2 and [kind, layer, w, w_partner, s, g_self, g_partner]
    for diff, diff_np, diff_p2, plus ref_layer for _p2 (over a far plane); _np: in a cutout; layers by KiCad name."""
    k = json.loads(key) if isinstance(key, str) else list(key)
    if not k or k[0] not in KINDS:
        raise ValueError(f"unknown key kind {k[:1]!r}: expected one of {KINDS}")
    kind = k[0]
    pair = kind.startswith("diff")
    far = kind.endswith("_p2")
    n = (7 if pair else 5) + (1 if far else 0)
    if len(k) != n:
        raise ValueError(f"key {key!r}: {len(k)} fields, {n} expected for {kind!r}")
    out = {"kind": kind, "pair": pair, "layer": k[1], "ref_layer": k[-1] if far else None,
           "situation": "far" if far else ("cutout" if kind.endswith("_np") else "plane")}
    if pair:
        out.update(w=float(k[2]), w_partner=float(k[3]), s=float(k[4]),
                   gaps=(_float_or_none(k[5]), _float_or_none(k[6])))
    else:
        out.update(w=float(k[2]), w_partner=None, s=None, gaps=(_float_or_none(k[3]), _float_or_none(k[4])))
    return out


def is_coupled(key):
    """True for a diff or diff_p2 key, or a diff_np key with s < COUPLE_MM."""
    f = parse_key(key)
    return f["pair"] and (f["kind"] != "diff_np" or f["s"] < COUPLE_MM - 1e-9)


def point_impedance(key, z, pair):
    """Impedance of a point from the cached value `z` of its key: in a pair, se and se_p2 keys count 2 × z."""
    kind = parse_key(key)["kind"]
    return 2 * z if pair and kind in ("se", "se_p2") else z


# --- stackup and fabricator ---------------------------------------------------------------------------------------
class Slab:
    """One stackup read from its JSON list (top to bottom: `Type` "Copper" or "Dielectric", `Thickness` mm,
    `Material.DielectricConstant`), with the distances a key needs; copper layers by KiCad name."""

    def __init__(self, layers, name=""):
        self.name = name
        self.layers = list(layers)
        if len(self.layers) < 3 or self.layers[0].get("Type") != "Copper" or self.layers[-1].get("Type") != "Copper":
            raise ValueError(f"stackup {name!r}: expected a list from outer copper to outer copper")
        for i, (a, b) in enumerate(zip(self.layers, self.layers[1:])):
            if a.get("Type") == b.get("Type") or a.get("Type") not in ("Copper", "Dielectric"):
                raise ValueError(f"stackup {name!r}: layers {i} and {i + 1} do not alternate copper / dielectric")
        self._copper = [i for i, lay in enumerate(self.layers) if lay["Type"] == "Copper"]

    @property
    def n_copper(self):
        return len(self._copper)

    def copper_index(self, layer_name):
        """Index (0 = top) of a copper layer by its KiCad name."""
        n = self.n_copper
        if layer_name == "F.Cu":
            return 0
        if layer_name == "B.Cu":
            return n - 1
        k = int(layer_name[2:-3])
        if not 1 <= k <= n - 2:
            raise ValueError(f"{layer_name} is not a copper layer of a {n}-layer stackup")
        return k

    def copper_mm(self, layer_name):
        return self.layers[self._copper[self.copper_index(layer_name)]]["Thickness"]

    def _outer(self, layer_name):
        i = self.copper_index(layer_name)
        if i not in (0, self.n_copper - 1):
            raise ValueError(f"{layer_name} is an inner layer: outer-layer microstrip only (a critical track on an "
                             "inner layer is reported, not computed)")
        return i

    def _prepreg(self, layer_name):
        i = self._outer(layer_name)
        return self.layers[1] if i == 0 else self.layers[-2]

    def h_prepreg(self, layer_name):
        """Thickness (mm) of the dielectric under an outer layer."""
        return self._prepreg(layer_name)["Thickness"]

    def er_prepreg(self, layer_name):
        return self._prepreg(layer_name)["Material"]["DielectricConstant"]

    def er_core(self, layer_name):
        """Permittivity of the dielectric that follows the prepreg of an outer layer, going inward."""
        i = self._outer(layer_name)
        d = [lay for lay in (self.layers if i == 0 else self.layers[::-1]) if lay["Type"] == "Dielectric"]
        return d[1]["Material"]["DielectricConstant"]

    def h_between(self, a, b):
        """Distance (mm) between two copper layers: the sum of everything strictly between them."""
        i, j = sorted((self._copper[self.copper_index(a)], self._copper[self.copper_index(b)]))
        return round(sum(lay["Thickness"] for lay in self.layers[i + 1:j]), 6)

    @property
    def slab_mm(self):
        """Outer copper to outer copper: the bare laminate of a cutout."""
        return self.h_between("F.Cu", "B.Cu")


def read_stackup(path):
    """`Slab` of a stackup JSON file (name = file stem)."""
    p = Path(path)
    return Slab(json.loads(p.read_text()), p.stem)


def read_fabricator(path, slab=None):
    """Fabricator dict of a JSON file (keys FAB_KEYS, units mm); with `slab`, its outer and inner copper must match
    every copper layer of the stackup within 1 µm (ValueError otherwise)."""
    fab = json.loads(Path(path).read_text())
    if fab.get("units") != "mm":
        raise ValueError(f"fabricator file {path}: units must be mm (convert at reading), got {fab.get('units')!r}")
    if slab is not None:
        n = slab.n_copper
        for i in range(n):
            layer = "F.Cu" if i == 0 else "B.Cu" if i == n - 1 else f"In{i}.Cu"
            key = "outer_copper_base" if i in (0, n - 1) else "inner_copper"
            got = slab.copper_mm(layer)
            if abs(fab[key] - got) > 1e-3 + 1e-9:
                raise ValueError(f"fabricator {key} = {fab[key]} mm, stackup {slab.name!r} has {got} mm on {layer}")
    return fab


# --- key → geometry -----------------------------------------------------------------------------------------------
def geometry_kwargs(key, slab, fab, dw=0.0):
    """Keyword arguments of `fieldsolver2d.Geometry` for a key (outer layers; se_np is not solved: NO_RETURN_OHM) on a
    stackup `Slab` and a fabricator dict. dw: etching excursion, mm: the tracks widen by dw, the pair gap narrows by dw
    and the side gaps by dw / 2."""
    f = parse_key(key)
    if f["kind"] == "se_np":
        raise ValueError("a single line in a cutout has no return path: not solved, impedance NO_RETURN_OHM")
    lay = f["layer"]
    w = (f["w"] + f["w_partner"]) / 2 if f["pair"] else f["w"]
    g_self, g_other = f["gaps"]
    dw = float(dw)
    edge = lambda g: None if g is None else g - dw / 2                      # noqa: E731
    g_self, g_other = edge(g_self), edge(g_other)
    w = w + dw
    kw = {"w": w, "s": f["s"] - dw if f["pair"] else 0.0, "t": fab["outer_copper_finished"],
          "w_top": w - fab["etch_top_width_reduction"], "c1": fab["solder_mask_on_laminate"],
          "c2": fab["solder_mask_on_copper"], "er_mask": fab["solder_mask_er"],
          "side_gap": g_self, "side_left": g_self is not None, "side_gap2": g_other if g_other is not None else 0.0}
    if (f["pair"] and kw["s"] <= 0) or any(g is not None and g <= 0 for g in (g_self, g_other)):
        raise ValueError(f"etch excursion {dw} mm closes a gap of {key}")
    if f["situation"] == "plane":
        kw.update(h=slab.h_prepreg(lay), er=slab.er_prepreg(lay), plane=True)
    elif f["situation"] == "cutout":
        kw.update(h=slab.slab_mm, er=slab.er_prepreg(lay), plane=False, h_top=slab.h_prepreg(lay), er_core=slab.er_core(lay))
    else:
        kw.update(h=slab.h_between(lay, f["ref_layer"]), er=slab.er_prepreg(lay), plane=True,
                  h_top=slab.h_prepreg(lay), er_core=slab.er_core(lay))
    if kw["w_top"] <= 0:
        raise ValueError(f"width {w} mm is smaller than the etch reduction {fab['etch_top_width_reduction']} mm")
    return kw


def mesh_step(key, kw):
    """Fine mesh step (mm) for `fieldsolver2d.solve`: None (its default) over the adjacent plane,
    min(max(w, s, 0.05) / 80, 0.003) in a cutout, 0.004 over a far plane (can be coarser than the default: check
    the convergence of a new far-plane section)."""
    situation = parse_key(key)["situation"]
    if situation == "plane":
        return None
    if situation == "cutout":
        return min(max(kw["w"], kw["s"], 0.05) / 80, 0.003)
    return 0.004


def geometry(key, slab, fab, dw=0.0):
    """(`fieldsolver2d.Geometry`, d_fine) ready for `solve(geometry, d_fine=d_fine)`, at the etch excursion `dw`
    (`geometry_kwargs`). Imports the solver (numpy, scipy) lazily: the venv side only."""
    from fieldsolver2d import Geometry
    kw = geometry_kwargs(key, slab, fab, dw)
    return Geometry(**kw), mesh_step(key, kw)


def cache_signature(slabs, fab, extra=""):
    """Signature (16 hex characters) of everything but the key that sets an impedance: the text of this module, of
    fieldsolver2d.py and impedance_solve.py, the stackups ({name: Slab}), the fabricator values (FAB_KEYS), `extra`."""
    here = Path(__file__).resolve()
    parts = [here.read_text(), *[(here.parent / f).read_text() for f in ("fieldsolver2d.py", "impedance_solve.py")],
             json.dumps({name: slabs[name].layers for name in sorted(slabs)}, sort_keys=True),
             json.dumps({k: fab[k] for k in FAB_KEYS}, sort_keys=True), str(extra)]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


# --- per link: statistics, continuous runs, expected width ------------------------------------------------------
def link_stats(bins, zmap, target, pair, tol=TOL):
    """Length-weighted statistics of one link on one stackup. bins: {key: mm}; zmap: {key: cached impedance}; pair:
    lone legs count 2 × Z0. Returns {"z_min", "z_med", "z_max", "out_tol_mm", "out_15pct_mm", "length_mm",
    "uncoupled_mm"}."""
    missing = sorted(set(bins) - set(zmap))
    if missing:
        raise ValueError(f"{len(missing)} key(s) missing from the impedance cache, e.g. {missing[0]}")
    bad = sorted(k for k in bins if not _finite_pos(zmap[k]))
    if bad:
        raise ValueError(f"{len(bad)} key(s) with an impedance that is not a finite positive number, "
                         f"e.g. {bad[0]}: {zmap[bad[0]]!r} Ω")
    items = sorted((point_impedance(k, zmap[k], pair), L) for k, L in bins.items())
    tot = sum(L for _, L in items)
    acc, med = 0.0, None
    for z, L in items:
        acc += L
        if med is None and acc >= tot / 2 - 1e-12:
            med = z
    return {"z_min": items[0][0], "z_med": med, "z_max": items[-1][0],
            "out_tol_mm": round(sum(L for z, L in items if out_of_tolerance(z, target, tol)), 3),
            "out_15pct_mm": round(sum(L for z, L in items if out_of_tolerance(z, target, 0.15)), 3),
            "length_mm": round(tot, 3),
            "uncoupled_mm": round(sum(L for k, L in bins.items() if pair and not is_coupled(k)), 3)}


def delay_per_mm(bins, emap):
    """Delay per mm (s/mm) of a link: the length-weighted mean of √εeff / c over its solved keys (se_np left out).
    bins: {key: mm}; emap: {key: "er_eff" of its cache entry}."""
    solved = {k: L for k, L in bins.items() if parse_key(k)["kind"] != "se_np"}
    missing = sorted(set(solved) - set(emap))
    if missing:
        raise ValueError(f"{len(missing)} key(s) missing from the εeff map (the cache's \"er_eff\"), e.g. {missing[0]}")
    return sum(L * math.sqrt(emap[k]) for k, L in solved.items()) / sum(solved.values()) / C_MM_PER_S


def runs(points, test, neighbour_mm=NEIGHBOUR_MM, heal_mm=HEAL_MM):
    """Continuous runs of the points that satisfy `test`, along the path: `points` in path order ([x_mm, y_mm,
    length_mm, key]); consecutive points on one layer closer than neighbour_mm chain, and a run ends after more than
    heal_mm of points that fail. Returns [{"mm", "x", "y" (centroid), "pts"}], longest first."""
    groups, open_, gap, prev, prev_layer = [], False, 0.0, None, None
    for q in points:
        layer = parse_key(q[3])["layer"]
        chained = (prev is not None and layer == prev_layer
                   and (q[0] - prev[0]) ** 2 + (q[1] - prev[1]) ** 2 <= neighbour_mm ** 2)
        if not chained:
            open_, gap = False, 0.0
        if test(q):
            if open_ and gap <= heal_mm + 1e-9:
                groups[-1].append(q)
            else:
                groups.append([q])
            open_, gap = True, 0.0
        elif open_:
            gap += q[2]
            if gap > heal_mm + 1e-9:
                open_ = False
        prev, prev_layer = q, layer
    out = [{"mm": round(sum(q[2] for q in g), 3), "x": round(sum(q[0] for q in g) / len(g), 3),
            "y": round(sum(q[1] for q in g) / len(g), 3), "pts": g} for g in groups]
    return sorted(out, key=lambda t: -t["mm"])


def net_classes(pro):
    """Net classes of a .kicad_pro dict: {name: {"name", "track_width", "pair_width", "pair_gap"}} in mm, None when
    the class does not set it."""
    classes = pro["net_settings"]["classes"]
    out = {c["name"]: {"name": c["name"], "track_width": c.get("track_width"), "pair_width": c.get("diff_pair_width"),
                       "pair_gap": c.get("diff_pair_gap")} for c in classes}
    return out


def expected_width(key, pair, cls):
    """Width (mm) the net class `cls` intends for a point, or None when not judged: coupled → pair width; lone leg of a
    pair → track width if it differs from the pair width; single line → track width."""
    if is_coupled(key):
        if cls.get("pair_width") is None:
            raise ValueError(f"class {cls.get('name')!r} has no pair width: a coupled run cannot be judged")
        return cls["pair_width"]
    if cls.get("track_width") is None:
        raise ValueError(f"class {cls.get('name')!r} has no track width")
    if pair:
        pw = cls.get("pair_width")
        return cls["track_width"] if pw is None or abs(cls["track_width"] - pw) > 1e-4 else None
    return cls["track_width"]


RICHARDSON_BAND = 0.01      # screening value: band around a limit where the fine pass takes over (`needs_fine`)


def richardson(z2, z4):
    """Richardson extrapolation from solves at mesh × 2 and × 4 the default step: (4·z2 − z4) / 3."""
    a, b = float(z2), float(z4)
    return (4 * a - b) / 3


def needs_fine(z, targets, tol=TOL, band=RICHARDSON_BAND):
    """True when `z` lies within `band` (relative) of a tolerance limit of one of `targets` (Ω): the light method
    cannot decide its side, the section is solved at the default mesh."""
    z, tol, band = float(z), float(tol), float(band)
    return any(abs(abs(z / float(t) - 1) - tol) < band for t in targets)


def check_link(link):
    """Raise ValueError unless `link` carries the fields `judge_corners` reads ("points", "unreferenced_runs" with
    "mm" and a "span" of point indices, "skipped_mm"), as `kicad_sampling.sample_link` writes them."""
    for field in ("points", "unreferenced_runs", "skipped_mm"):
        if field not in link:
            raise ValueError(f"link without {field}: sample it again with the current `sample_link`")
    n = len(link["points"])
    for r in link["unreferenced_runs"]:
        if "mm" not in r or not (isinstance(r.get("span"), list) and 0 <= r["span"][0] <= r["span"][1] < n):
            raise ValueError(f"unreferenced run {r!r}: needs 'mm' and a 'span' within the {n} points")


def corner_keys(links, zmaps=None, tol=TOL, l_trans_mm=L_TRANS_MM):
    """Keys to solve at the etching corners, from links [(link, pair)] longer than l_trans_mm (each checked by
    `check_link`). Without zmaps: the main key of each (the most length). With zmaps {"nominal", "narrow", "wide"}
    holding those at their corners: every key of each link without a nominal deviation whose nominal values, scaled
    by the corner excursion of its main key, show one (the corners can change its verdict)."""
    out = set()
    for link, pair in links:
        check_link(link)
        pts = link["points"]
        if sum(q[2] for q in pts) <= l_trans_mm:
            continue
        k = max(sorted({q[3] for q in pts}), key=lambda key: sum(q[2] for q in pts if q[3] == key))
        zn = (zmaps or {}).get("nominal")
        if zn is None:
            out.add(k)
        elif not judge_link(link, zn, pair, tol, l_trans_mm)["deviations_z"] and any(
                judge_link(link, {q[3]: zn[q[3]] * zmaps[c][k] / zn[k] for q in pts}, pair, tol,
                           l_trans_mm)["deviations_z"] for c in ("narrow", "wide")):
            out.update(q[3] for q in pts)
    return out


def judge_corners(link, zmaps, pair, tol=TOL, l_trans_mm=L_TRANS_MM, impedance_control=False):
    """Verdict of a link. zmaps: {"nominal": {key: Ω}, "narrow", "wide": the keys of `corner_keys` at dw = ∓ 2 ×
    etch_tolerance_per_flank (a key without them is at nominal, "at_nominal" True), optionally "no_plane": {key: Ω
    without the adjacent plane}}. A plane-edge run (unreferenced, longer than l_trans_mm) lies between its full-plane
    value (its key) and "no_plane": a reservation naming both unless both are in tolerance. Returns {"verdict": "fail" |
    "incomplete" | "reservation" | "pass", "why", "at_nominal", "nominal", "narrow", "wide"} (`judge_link` results,
    corners None for fail and incomplete); impedance_control=True lifts a corner reservation."""
    check_link(link)
    zn, pts, target = zmaps["nominal"], link["points"], link["target"]
    nominal = judge_link(link, zn, pair, tol, l_trans_mm)
    keys = {q[3] for q in pts if parse_key(q[3])["kind"] != "se_np"}
    out = {"nominal": nominal, "narrow": None, "wide": None,
           "at_nominal": any(k not in zmaps.get(c, {}) for c in ("narrow", "wide") for k in keys)}
    edge = [r for r in link["unreferenced_runs"] if r["mm"] > l_trans_mm]
    if nominal["deviations_z"] and (not edge or _off_edge_deviations(link, edge, zn, pair, tol, l_trans_mm)):
        return {**out, "verdict": "fail", "why": "nominal out of tolerance"}
    skipped = [f"not judged: {mm} mm on {lay}, layer not handled" for lay, mm in sorted(link["skipped_mm"].items())
               if mm > 0]
    if skipped:
        return {**out, "verdict": "incomplete", "why": "; ".join(skipped)}
    no_return = {q[3]: NO_RETURN_OHM for q in pts if parse_key(q[3])["kind"] == "se_np"}
    why = []
    for c in ("narrow", "wide"):
        out[c] = judge_link(link, {**zn, **zmaps.get(c, {}), **no_return}, pair, tol, l_trans_mm)
        if out[c]["out_tol_run_mm"] > nominal["out_tol_run_mm"] and not impedance_control:
            why.append(f"{c} etching corner: {out[c]['out_tol_run_mm']} mm out of tolerance")
    no_plane = zmaps.get("no_plane", {})
    for r in edge:
        run = pts[r["span"][0]:r["span"][1] + 1]
        lo = [point_impedance(q[3], zn[q[3]], pair) for q in run]
        hi = [point_impedance(q[3], no_plane[q[3]], pair) for q in run if q[3] in no_plane]
        if len(hi) < len(run) or any(out_of_tolerance(z, target, tol) for z in lo + hi):
            why.append(f"plane edge within 3 widths, {r['mm']} mm at ({r['x']}, {r['y']}): {min(lo):.1f}–{max(lo):.1f}"
                       " Ω over the full plane, " + (f"{min(hi):.1f}–{max(hi):.1f} Ω without it" if len(hi) == len(run)
                                                    else "not solved without it"))
    if nominal["out_tol_total_mm"] > max(l_trans_mm, 0.1 * sum(q[2] for q in pts)):
        why.append(f"{nominal['out_tol_total_mm']} mm out of tolerance in short runs")
    out.update(verdict="reservation" if why else "pass", why="; ".join(why) or None)
    return out


def _off_edge_deviations(link, edge, zmap, pair, tol, l_trans_mm):
    """True when a nominal deviation run remains on the points a fail can rest on: those outside the plane-edge runs
    `edge`, and those inside whose full-plane impedance is above the upper limit (a lower bound there)."""
    pts, target = link["points"], link["target"]
    inside = {i for r in edge for i in range(r["span"][0], r["span"][1] + 1)}
    certain = set()
    for i, q in enumerate(pts):
        z = point_impedance(q[3], zmap[q[3]], pair)
        if out_of_tolerance(z, target, tol) and (i not in inside or z > target):
            certain.add(id(q))
    return any(r["mm"] > l_trans_mm for r in runs(pts, lambda q: id(q) in certain))


def judge_link(link, zmap, pair, tol=TOL, l_trans_mm=L_TRANS_MM, neighbour_mm=NEIGHBOUR_MM):
    """Impedance and width judged per continuous run on one stackup. link: {"points", "target", "cls"} (cls from
    `net_classes`); zmap: {key: cached impedance}; a run longer than l_trans_mm is a deviation, a shorter one a
    transition. Returns {"out_tol_run_mm", "out_tol_total_mm", "deviations_z": [{mm, x, y, z_min, z_max}],
    "transitions_z", "transition_z_max_mm", "width_deviation_mm", "deviations_width": [{mm, x, y, widths, expected}],
    "transitions_width", "lone_width_in_class"}."""
    target = link["target"]
    cls = link["cls"]
    pts = link["points"]
    if not pts:
        raise ValueError("empty link: no sampled point")
    missing = sorted({q[3] for q in pts} - set(zmap))
    if missing:
        raise ValueError(f"{len(missing)} key(s) missing from the impedance cache, e.g. {missing[0]}")
    bad = sorted({q[3] for q in pts if not _finite_pos(zmap[q[3]])})
    if bad:
        raise ValueError(f"{len(bad)} key(s) with a non-finite or non-positive impedance, e.g. {bad[0]}: "
                         f"{zmap[bad[0]]!r}")

    def z(q):
        return point_impedance(q[3], zmap[q[3]], pair)

    def wrong_width(q):
        e = expected_width(q[3], pair, cls)
        return e is not None and abs(parse_key(q[3])["w"] - e) > 1e-3 + 1e-9

    capped = [q for q in pts if parse_key(q[3])["kind"] == "diff_np"
              and parse_key(q[3])["s"] >= CUTOUT_GAP_CAP_MM - 1e-9 and z(q) / target - 1 <= tol + LIMIT_EPS]
    if capped:
        raise ValueError(f"{len(capped)} point(s) of a pair without plane whose partner is {CUTOUT_GAP_CAP_MM} mm away "
                         f"or more (first at {capped[0][0]}, {capped[0][1]}): solved at {CUTOUT_GAP_CAP_MM} mm, a lower "
                         f"bound under the upper limit {target * (1 + tol):.1f} Ω, which cannot be judged")
    hz = runs(pts, lambda q: out_of_tolerance(z(q), target, tol), neighbour_mm)
    hw = runs(pts, wrong_width, neighbour_mm)
    ez = [t for t in hz if t["mm"] > l_trans_mm]
    ew = [t for t in hw if t["mm"] > l_trans_mm]
    tw, pw = cls.get("track_width"), cls.get("pair_width")
    return {"out_tol_run_mm": round(sum(t["mm"] for t in ez), 3),
            "out_tol_total_mm": round(sum(t["mm"] for t in hz), 3),
            "deviations_z": [{"mm": t["mm"], "x": t["x"], "y": t["y"], "z_min": round(min(z(q) for q in t["pts"]), 1),
                              "z_max": round(max(z(q) for q in t["pts"]), 1)} for t in ez],
            "transitions_z": len(hz) - len(ez),
            "transition_z_max_mm": max((t["mm"] for t in hz if t["mm"] <= l_trans_mm), default=0.0),
            "width_deviation_mm": round(sum(t["mm"] for t in ew), 3),
            "deviations_width": [{"mm": t["mm"], "x": t["x"], "y": t["y"],
                                  "widths": sorted({parse_key(q[3])["w"] for q in t["pts"]}),
                                  "expected": sorted({expected_width(q[3], pair, cls) for q in t["pts"]})} for t in ew],
            "transitions_width": len(hw) - len(ew),
            "lone_width_in_class": (not pair) or (tw is not None and (pw is None or abs(tw - pw) > 1e-4))}
