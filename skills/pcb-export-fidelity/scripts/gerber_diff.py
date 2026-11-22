"""Compare two Gerber sets (A: EasyEDA export, B: KiCad export) layer by layer, by rasterisation.

Usage: gerber_diff.py <folder_A> <folder_B> <output_folder> [--res 0.01] [--tol 0.05]
  --res  pixel size in mm (default 0.01 = 10 µm)
  --tol  side in mm of the square used for the morphological opening of the differences (default 0.05): slivers
         narrower than this are left out of the "only" areas and of the islands, and stay in the raw figures.
Environment: Python with gerbonara, numpy, pillow, scipy.
Both sets must share the same coordinate frame (KiCad: --use-drill-file-origin with the origin at the bottom-left
corner of the outline). The frame of the comparison is the union of the bounding boxes of the two outlines plus
1 mm; a compared layer with geometry outside that frame, on either side, makes the exit status non-zero (geometry
left out of the comparison is not "no difference"). Each pattern must match exactly one file per set: several
matches stop the script with the list (rename, or move the other revision away).
Layers compared: PAIRS below (file-name patterns of a 4-layer board; edit for another layer count).
Output, per layer: one printed line (area A, area B, A only, B only after opening, number of islands, raw
differences, all in mm²), <layer>.png (dark grey: common; red: A only; green: B only; pale tints: differences
removed by the opening), <layer>.npz (boolean rasters A and B), <layer>_islands.tsv (difference islands sorted by
area: side, mm2, x, y of the centroid in the Gerber frame, width, height).
Exit status: non-zero if a layer is missing on either side, or has geometry outside the frame (an incomplete
comparison is not a "no difference").
"""
import math
import sys
from pathlib import Path

import numpy as np
from gerbonara import GerberFile, ExcellonFile
import gerbonara.graphic_primitives as gp
from PIL import Image, ImageDraw
from scipy import ndimage

PAIRS = [  # (name, pattern A EasyEDA, pattern B KiCad)
    ("Edge", "*BoardOutline*", "*Edge_Cuts*"),
    ("F.Cu", "*TopLayer.GTL", "*F_Cu*"),
    ("In1.Cu", "*InnerLayer1*", "*In1_Cu*"),
    ("In2.Cu", "*InnerLayer2*", "*In2_Cu*"),
    ("B.Cu", "*BottomLayer.GBL", "*B_Cu*"),
    ("F.Mask", "*TopSolderMask*", "*F_Mask*"),
    ("B.Mask", "*BottomSolderMask*", "*B_Mask*"),
    ("F.Paste", "*TopPasteMask*", "*F_Paste*"),
    ("B.Paste", "*BottomPasteMask*", "*B_Paste*"),
    ("F.Silk", "*TopSilkscreen*", "*F_Silkscreen*"),
    ("B.Silk", "*BottomSilkscreen*", "*B_Silkscreen*"),
]


def arc_pts(p1, p2, c, cw, step=0.02):
    r = math.dist(p1, c)
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    if cw:
        sweep = (a1 - a2) % (2 * math.pi)
    else:
        sweep = (a2 - a1) % (2 * math.pi)
    if sweep < 1e-9:
        sweep = 2 * math.pi
    n = max(4, int(r * sweep / step))
    sgn = -1 if cw else 1
    return [(c[0] + r * math.cos(a1 + sgn * sweep * k / n), c[1] + r * math.sin(a1 + sgn * sweep * k / n))
            for k in range(1, n + 1)]


def outline(ap):
    pts = []
    for p1, p2, (cw, c) in ap.segments:
        pts.append(p1)
        if cw is not None:
            pts += arc_pts(p1, p2, c, cw)
    return pts


def render(path, bbox, res):
    """Raster of one Gerber file. Each object is drawn on its own local mask first (a primitive of the object's
    polarity marks it, one of the other polarity, the hole of an aperture, is TRANSPARENT: it removes the object's
    own copper only), then composed on the layer by the object's polarity (dark: added, clear: removed). Drawing the
    hole straight on the layer would erase copper drawn before it (a line inside the hole of a later flash: two
    files differing by 0.15 mm² of copper compared as identical)."""
    (x0, y0), (x1, y1) = bbox
    W, H = int((x1 - x0) / res) + 1, int((y1 - y0) / res) + 1
    layer = np.zeros((H, W), dtype=bool)
    tf = lambda p: ((p[0] - x0) / res, (y1 - p[1]) / res)
    g = GerberFile.open(path)
    for obj in g.objects:
        shapes = []
        for prim in obj.to_primitives(unit=gp.MM):
            if isinstance(prim, gp.Line) and math.isclose(prim.width, 0):
                continue
            if isinstance(prim, gp.Rectangle):  # gerbonara's to_arc_poly() ignores the rotation (bounding box)
                c, sn = math.cos(prim.rotation), math.sin(prim.rotation)
                pts = [tf((prim.x + u * c - v * sn, prim.y + u * sn + v * c))
                       for u, v in ((-prim.w / 2, -prim.h / 2), (prim.w / 2, -prim.h / 2),
                                    (prim.w / 2, prim.h / 2), (-prim.w / 2, prim.h / 2))]
            else:
                pts = [tf(p) for p in outline(prim.to_arc_poly())]
            if len(pts) >= 3:
                shapes.append((pts, prim.polarity_dark == obj.polarity_dark))
        if not shapes:
            continue
        xs = [x for pts, _ in shapes for x, _y in pts]
        ys = [y for pts, _ in shapes for _x, y in pts]
        c0, c1 = max(int(math.floor(min(xs))) - 1, 0), min(int(math.ceil(max(xs))) + 2, W)
        r0, r1 = max(int(math.floor(min(ys))) - 1, 0), min(int(math.ceil(max(ys))) + 2, H)
        if c1 <= c0 or r1 <= r0:
            continue                                     # outside the frame of the comparison
        local = Image.new("1", (c1 - c0, r1 - r0), 0)
        d = ImageDraw.Draw(local)
        for pts, on in shapes:                           # in drawing order: a hole clears what the object drew
            d.polygon([(x - c0, y - r0) for x, y in pts], fill=1 if on else 0)
        m = np.array(local, dtype=bool)
        if obj.polarity_dark:
            layer[r0:r1, c0:c1] |= m
        else:
            layer[r0:r1, c0:c1] &= ~m
    return layer


def pick(folder, pattern):
    m = sorted(Path(folder).glob(pattern))
    if len(m) > 1:
        sys.exit(f"{folder}: {len(m)} files match {pattern}: {', '.join(p.name for p in m)}")
    return m[0] if m else None


def extent(path):
    """Bounding box in mm of a Gerber file, None when it draws nothing."""
    g = GerberFile.open(path)
    return g.bounding_box(unit=gp.MM) if g.objects else None


def main():
    a_dir, b_dir, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    res = float(sys.argv[sys.argv.index("--res") + 1]) if "--res" in sys.argv else 0.01
    tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 0.05
    out.mkdir(parents=True, exist_ok=True)
    ea, eb = (pick(d, p) for d, p in ((a_dir, PAIRS[0][1]), (b_dir, PAIRS[0][2])))
    if not ea or not eb:
        sys.exit(f"outline missing ({ea}, {eb}): no frame for the comparison")
    (ax0, ay0), (ax1, ay1) = extent(ea)
    (bx0, by0), (bx1, by1) = extent(eb)
    bbox = ((min(ax0, bx0) - 1.0, min(ay0, by0) - 1.0), (max(ax1, bx1) + 1.0, max(ay1, by1) + 1.0))
    print(f"frame {bbox[0][0]:.2f} {bbox[0][1]:.2f} to {bbox[1][0]:.2f} {bbox[1][1]:.2f} mm")
    outside = []
    k = max(1, int(round(tol / res)))
    struct = np.ones((k, k), bool)
    rows, missing = [], []
    for name, pa, pb in PAIRS:
        fa, fb = pick(a_dir, pa), pick(b_dir, pb)
        if not fa or not fb:
            print(f"{name}: missing file ({fa}, {fb})")
            missing.append(name)  # incomplete comparison: fails at the end of the script, not a "zero deviation"
            continue
        for side, f in (("A", fa), ("B", fb)):
            e = extent(f)
            if e and (e[0][0] < bbox[0][0] or e[0][1] < bbox[0][1] or e[1][0] > bbox[1][0] or e[1][1] > bbox[1][1]):
                print(f"{name}: {side} has geometry outside the frame, {e}")
                outside.append(f"{name} ({side})")
        A, B = render(fa, bbox, res), render(fb, bbox, res)
        rawA, rawB = (A & ~B).sum() * res * res, (B & ~A).sum() * res * res  # raw difference, before filtering
        onlyA = ndimage.binary_opening(A & ~B, structure=struct)
        onlyB = ndimage.binary_opening(B & ~A, structure=struct)
        px = res * res
        rows.append((name, A.sum() * px, B.sum() * px, onlyA.sum() * px, onlyB.sum() * px))
        np.savez_compressed(out / f"{name}.npz", A=A, B=B)
        # image: dark grey = common, red = A only (EasyEDA), green = B only (KiCad)
        rgb = np.full(A.shape + (3,), 255, np.uint8)
        rgb[A & B] = (60, 60, 60)
        rgb[A & ~B] = (255, 170, 170)
        rgb[B & ~A] = (170, 230, 170)
        rgb[onlyA] = (220, 0, 0)
        rgb[onlyB] = (0, 160, 0)
        Image.fromarray(rgb).save(out / f"{name}.png")
        blobs = []
        for tag, M in (("EasyEDA only", onlyA), ("KiCad only", onlyB)):
            lab, n = ndimage.label(M)
            if n == 0:
                continue
            areas = ndimage.sum(M, lab, range(1, n + 1)) * px
            coms = ndimage.center_of_mass(M, lab, range(1, n + 1))
            sl = ndimage.find_objects(lab)
            for ar, (r, c), s in zip(areas, coms, sl):
                x, y = bbox[0][0] + c * res, bbox[1][1] - r * res
                w, h = (s[1].stop - s[1].start) * res, (s[0].stop - s[0].start) * res
                blobs.append((tag, ar, x, y, w, h))
        blobs.sort(key=lambda b: -b[1])
        with open(out / f"{name}_islands.tsv", "w") as f:
            f.write("side\tmm2\tx\ty\twidth\theight\n")
            for b in blobs:
                f.write(f"{b[0]}\t{b[1]:.4f}\t{b[2]:.2f}\t{b[3]:.2f}\t{b[4]:.2f}\t{b[5]:.2f}\n")
        print(f"{name:8s} A {rows[-1][1]:9.2f}  B {rows[-1][2]:9.2f}  A only {rows[-1][3]:7.3f}  B only {rows[-1][4]:7.3f}"
              f"  islands {len(blobs)}  (raw: A only {rawA:7.3f}, B only {rawB:7.3f})", flush=True)
    if missing or outside:
        sys.exit(f"incomplete comparison, missing layers: {', '.join(missing) or 'none'}; geometry outside the "
                 f"frame: {', '.join(outside) or 'none'}")


if __name__ == "__main__":
    main()
