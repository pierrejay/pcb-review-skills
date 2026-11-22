#!/usr/bin/env python3
"""Applies the zone settings measured for a board to every copper zone of a KiCad project.

Clearance, minimum width, thermal gap and spoke width live in each (zone ...) block of the .kicad_pcb, not in
Board Setup: "Import Settings from Another Board" does not carry them over.

Usage:
    ./apply_zone_settings.py <project|file.kicad_pcb> [--dry-run]
    ./apply_zone_settings.py my-project --clearance 0.254 --thermal-gap 0.254

Defaults: clearance and thermal gap 0.254 mm (the EasyEDA Pro values, measured on its exports), minimum width
0.127 mm, spoke width 0.3 mm; replace them by the values measured for the board (cleanup-steps.md, section 6).
Rule areas (zones with a (keepout ...) child) and zones without a copper layer are left untouched; text inside
quoted strings (zone names, board texts) is not read as a token. A value that is not a finite number, a negative
clearance or thermal gap, or a minimum width or spoke width that is not positive stops the script before anything is
written.
Stops, writing nothing, if a *.lck file is in the folder of the PCB (KiCad open: it rewrites the .kicad_pcb when
it quits), or if the folder given holds no .kicad_pcb or several.
Backup: the PCB is copied, before writing, to <project>/_pre_import_backup/before_zone_settings.kicad_pcb (the
folder of the cleanup snapshots; created if missing). An existing snapshot is kept, never overwritten, so that a
re-run does not replace the pre-step file with an already modified one (--backup-dir to put it elsewhere).
Afterwards, open the PCB and press B to refill, otherwise the stored fill remains the previous one.
"""
import argparse, math, re, shutil, sys
from pathlib import Path

CU_RE = re.compile(r'^(F|B|In\d+)\.Cu$')


def zone_layers(blk: str) -> list:
    """All the layers of a zone, read from its own (layer ...) or (layers ...) child. The block can be single- or
    multi-layer:
        (layer "F.Cu")
        (layers "F.Cu" "B.Cu" "In1.Cu" "In2.Cu")
    Beware: "Edge.Cuts" contains the substring "Cu", hence the exact match."""
    for tag, a, b in children(blk):
        if tag in ('layer', 'layers'):
            toks = re.findall(r'"((?:[^"\\]|\\.)*)"|([^\s()"]+)', blk[a + 1:b - 1])
            return [q or w for q, w in toks[1:]]
    return []


def find_pcb(target: Path) -> Path:
    if target.is_file() and target.suffix == '.kicad_pcb':
        return target
    if target.is_dir():
        pcbs = sorted(target.glob('*.kicad_pcb'))
        if len(pcbs) == 1:
            return pcbs[0]
        if not pcbs:
            sys.exit(f"no .kicad_pcb in {target}")
        sys.exit(f"several .kicad_pcb in {target}, specify the file")
    sys.exit(f"not found: {target}")


def string_end(s: str, start: int) -> int:
    """Index just after the closing quote of the string opened at s[start] == '"' (backslash escapes skipped)."""
    i, n = start + 1, len(s)
    while i < n and s[i] != '"':
        i += 2 if s[i] == '\\' else 1
    if i >= n:
        raise ValueError(f"unclosed string at character {start}")
    return i + 1


def block_end(s: str, start: int) -> int:
    """Index just after the parenthesis closing the block opened at s[start]; quoted strings are skipped, so a
    parenthesis inside a zone name or a net name does not break the count (same rule as scripts/sexp.py)."""
    depth, i, n = 0, start, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            i = string_end(s, i)
            continue
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unclosed block")


def blocks(s: str, tag: str):
    """Iterator over the (tag ...) blocks, as (start, end). The scan skips the quoted strings from the start of the
    file and resumes after the end of each block found, so a "(zone" inside a string is never taken for a block."""
    pat, pos = re.compile(r'"|\(' + re.escape(tag) + r'(?=[\s()])'), 0
    while True:
        m = pat.search(s, pos)
        if not m:
            return
        if m.group() == '"':
            pos = string_end(s, m.start())
            continue
        end = block_end(s, m.start())
        yield m.start(), end
        pos = end


def children(blk: str):
    """Direct children of the block blk ("(tag ...)"), as (tag, start, end) in blk; quoted strings skipped."""
    out, i, n = [], 1, len(blk) - 1
    while i < n:
        c = blk[i]
        if c == '"':
            i = string_end(blk, i)
        elif c == '(':
            end = block_end(blk, i)
            out.append((re.match(r'\(\s*([^\s()"]*)', blk[i:end]).group(1), i, end))
            i = end
        else:
            i += 1
    return out


def _setting(positive: bool):
    """argparse type: a finite length in mm, > 0 (positive) or >= 0; NaN and infinities refused."""
    def parse(text: str) -> float:
        try:
            v = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
        if not math.isfinite(v) or v < 0 or (positive and v == 0):
            raise argparse.ArgumentTypeError(f"{text!r}: a finite length {'> 0' if positive else '>= 0'} mm expected")
        return v
    return parse


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('project', help='project folder or .kicad_pcb file')
    p.add_argument('--clearance', type=_setting(False), default=0.254)
    p.add_argument('--min-thickness', type=_setting(True), default=0.127)
    p.add_argument('--thermal-gap', type=_setting(False), default=0.254)
    p.add_argument('--thermal-bridge', type=_setting(True), default=0.3)
    p.add_argument('--backup-dir', default='_pre_import_backup',
                   help='folder of the backup, relative to the PCB (default: _pre_import_backup)')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()

    pcb = find_pcb(Path(a.project))
    if list(pcb.parent.glob('*.lck')):
        sys.exit(f"KiCad has the project open ({pcb.parent}): close it first")

    s = pcb.read_text()
    out, last, done, skipped = [], 0, [], []

    for start, end in blocks(s, 'zone'):
        blk = s[start:end]
        layers = zone_layers(blk)
        cu = [l for l in layers if CU_RE.match(l)]
        label = '+'.join(layers) if layers else '?'
        # A keepout has no fill: clearance/thermal/min_thickness
        # make no sense there and touching them would change its behaviour.
        if any(tag == 'keepout' for tag, _, _ in children(blk)):
            skipped.append(f'keepout({label})')
            continue
        if not cu:
            skipped.append(label)
            continue
        layer = '+'.join(cu)
        parts = re.split(r'("(?:[^"\\]|\\.)*")', blk)     # odd items: quoted strings, left as they are
        for key, val in (('clearance', a.clearance),
                         ('min_thickness', a.min_thickness),
                         ('thermal_gap', a.thermal_gap),
                         ('thermal_bridge_width', a.thermal_bridge)):
            # any number KiCad may have written (sign, exponent); the new value in plain decimals, never 1e-05
            pat = re.compile(r'\(' + key + r' [-+0-9.eE]+\)')
            if not any(pat.search(t) for t in parts[::2]):
                sys.exit(f"zone on {layer}: no ({key} …) found to set; nothing written")
            parts[::2] = [pat.sub(f'({key} {val:.6f}'.rstrip('0').rstrip('.') + ')', t) for t in parts[::2]]
        new = ''.join(parts)
        if new != blk:
            done.append(layer)
        out.append(s[last:start])
        out.append(new)
        last = end
    out.append(s[last:])

    print(f"project: {pcb}")
    print(f"  copper zones modified : {len(done)}  {dict((l, done.count(l)) for l in set(done))}")
    print(f"  zones left untouched  : {len(skipped)}  {dict((l, skipped.count(l)) for l in set(skipped))}")
    print(f"  values: clearance={a.clearance} min_thickness={a.min_thickness} "
          f"thermal_gap={a.thermal_gap} thermal_bridge={a.thermal_bridge}")

    if a.dry_run:
        print("  (dry-run, nothing written)")
        return 0

    backup_dir = pcb.parent / a.backup_dir
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / 'before_zone_settings.kicad_pcb'
    if backup.exists():
        print(f"  backup kept as is: {backup} (snapshot of the first run)")
    else:
        shutil.copy2(pcb, backup)
        print(f"  backup: {backup}")
    pcb.write_text(''.join(out))
    print("  written. -> open the PCB and press B to refill")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
