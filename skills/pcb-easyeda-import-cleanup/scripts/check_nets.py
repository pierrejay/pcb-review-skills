"""Connectivity check during cleanup: nothing must move electrically.

Compares, independently of net names, the pin groups (schematic) and pad groups (PCB) against the reference saved
with --save (on the renamed import, junctions restored: cleanup-steps.md, step J). Run it with KiCad's bundled
Python (it needs the pcbnew module):
  check_nets.py [<project>] --save     takes the reference (schematic + PCB)
  check_nets.py [<project>]            compares the current state against the reference (exit code 1 if different)

<project> is the board folder (files <folder>/<name>.kicad_sch and <name>.kicad_pcb, <name> = folder name, or the
single .kicad_pcb found there) or the .kicad_pcb itself. Without it, the script is assumed to have been copied
into <project>/_cleanup/ and the project is its parent folder.
The reference is stored in reference_nets.json, next to this script when no <project> is given, otherwise in
<project>/_cleanup/.
kicad-cli: environment variable KICAD_CLI, else the one found in PATH, else the standard macOS location.

Intended differences are declared in EXPECTED below, or (so that this file stays generic) in
check_nets_expected.json, in the same folder as the reference, with the same two keys.
Stops (exit code 1, nothing saved) when the netlist export fails (non-zero status or no file), when its output is
not a netlist it can read, when an extraction holds no net of two pins or more, and when a side of a comparison
holds no pin: an empty extraction is a failed one, not "IDENTICAL".
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KCLI = (os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")
        or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")

# Pins or pads that may legitimately change group. Empty by default: any difference is reported.
#   sch_merge: schematic pins allowed to change group, e.g. the pin of a net that an EasyEDA "Short" tied to a rail
#              and that the cleanup merges into that rail: [("U_MCU", "1")]
#   new_refs:  reference designators added by the cleanup, ignored on both sides, e.g. test points created for
#              free pads, a symbol excluded from the board: ["TP1", "TP2", "R_OPT"]; "?" ignores unannotated
#              symbols
# References starting with "#" (power symbols, PWR_FLAG) and free pads without a reference are always ignored.
EXPECTED = {"sch_merge": [], "new_refs": []}


def locate(arg):
    """Project folder, base name of its files, folder of the reference."""
    if arg is None:
        prj, work = HERE.parent, HERE
    else:
        p = Path(arg).resolve()
        prj = p.parent if p.suffix == ".kicad_pcb" else p
        work = prj / "_cleanup"
        if p.suffix == ".kicad_pcb":
            return prj, p.stem, work
    if (prj / f"{prj.name}.kicad_pcb").exists():
        return prj, prj.name, work
    pcbs = sorted(prj.glob("*.kicad_pcb"))
    if len(pcbs) != 1:
        sys.exit(f"{prj}: {len(pcbs)} .kicad_pcb file(s), give the file itself")
    return prj, pcbs[0].stem, work


def sch_groups(prj, name):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "n.net"
        r = subprocess.run([KCLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out),
                            str(prj / f"{name}.kicad_sch")], capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            sys.exit(f"netlist export failed ({KCLI}, exit status {r.returncode})\n{r.stderr}")
        s = out.read_text()
    return _require_pins(netlist_groups(s), "schematic netlist")


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


def _parse(s):
    """S-expression text -> nested lists of strings, independently of indentation and line breaks."""
    stack, i, n = [[]], 0, len(s)
    while True:
        m = _TOKEN.match(s, i)
        if not m:
            if s[i:].strip():
                sys.exit(f"netlist unreadable at character {i}: {s[i:i + 40]!r}")
            break
        i = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            if len(stack) == 1:
                sys.exit(f"netlist unreadable: unbalanced ')' at character {i}")
            blk = stack.pop()
            stack[-1].append(blk)
        else:
            stack[-1].append(re.sub(r"\\(.)", r"\1", m.group(3)) if m.group(3) is not None else m.group(4))
        if i >= n:
            break
    if len(stack) != 1:
        sys.exit("netlist unreadable: unclosed block")
    return stack[0]


def _field(node, key):
    """Value of the child (key value) of a node, or None."""
    return next((c[1] for c in node[1:] if isinstance(c, list) and len(c) > 1 and c[0] == key), None)


def netlist_groups(text):
    """{net name: sorted ["REF.pin", ...]} of a kicadsexpr netlist, read as S-expressions (layout-independent)."""
    root = [b for b in _parse(text) if isinstance(b, list) and b and b[0] == "export"]
    if len(root) != 1:
        sys.exit("netlist unreadable: no single (export ...) block")
    nets = [c for c in root[0][1:] if isinstance(c, list) and c and c[0] == "nets"]
    if len(nets) != 1:
        sys.exit(f"netlist unreadable: {len(nets)} (nets ...) sections")
    groups = {}
    for net in nets[0][1:]:
        if not (isinstance(net, list) and net and net[0] == "net"):
            continue
        name = _field(net, "name")
        if name is None:
            sys.exit(f"netlist unreadable: a net without a name ({net[:3]})")
        if name in groups:
            sys.exit(f"netlist unreadable: net {name!r} listed twice")
        pins = []
        for node in net[1:]:
            if isinstance(node, list) and node and node[0] == "node":
                ref, pin = _field(node, "ref"), _field(node, "pin")
                if ref is None or pin is None:
                    sys.exit(f"netlist unreadable: net {name!r} has a node without ref or pin")
                pins.append(f"{ref}.{pin}")
        groups[name] = sorted(pins)
    return groups


def _require_pins(groups, what, least=2):
    """The groups, or exit when no net holds `least` pins: an extraction of a board without a single net of two pins
    or more (least=2), or a side of a comparison without any pin (least=1), is a failed extraction."""
    if not any(len(set(pins)) >= least for pins in groups.values()):
        sys.exit(f"{what}: no net of {least} pin(s) or more ({len(groups)} net(s)): extraction failed, "
                 "nothing compared")
    return groups


def pcb_groups(prj, name):
    import pcbnew as P
    b = P.LoadBoard(str(prj / f"{name}.kicad_pcb"))
    groups = {}
    for f in b.GetFootprints():
        ref = f.GetReference() or f"@{f.GetPosition().x // 1000},{f.GetPosition().y // 1000}"
        for p in f.Pads():
            if p.GetNetname():
                groups.setdefault(p.GetNetname(), set()).add(f"{ref}.{p.GetNumber()}")
    return _require_pins({k: sorted(v) for k, v in groups.items()}, "PCB")


def _skipped(pin, skip_refs):
    """Pin "REF.n" ignored: reference listed in new_refs, unannotated reference ("R?") when "?" is listed, power
    symbols and flags ("#…"), free pads identified by position ("@…")."""
    ref = pin.split(".")[0]
    return (ref in skip_refs or ("?" in skip_refs and ref.endswith("?")) or pin.startswith(("#", "@")))


def partition(groups, skip_refs=(), skip_pins=frozenset()):
    """Pin groups of a netlist, the skipped references and pins removed BEFORE a single-pin group is dropped (so both
    sides drop the same groups)."""
    out = set()
    for pins in groups.values():
        g = frozenset(p for p in pins if not _skipped(p, skip_refs) and p not in skip_pins)
        if len(g) > 1:  # a single-pad net (free pin named "unconnected-…" by F8) connects nothing
            out.add(g)
    return out


def compare(label, ref, cur, skip_refs=(), merge=()):
    _require_pins(ref, f"{label.strip()} reference", 1)
    _require_pins(cur, f"{label.strip()} current state", 1)
    m = frozenset(f"{r}.{p}" for r, p in merge)   # pins allowed to change group: removed from both sides first
    a, b = partition(ref, skip_refs, m), partition(cur, skip_refs, m)
    only_a, only_b = a - b, b - a
    ok = not only_a and not only_b
    print(f"{label}: {'IDENTICAL' if ok else 'DIFFERENT'} ({len(b)} groups)")
    for g in sorted(only_a, key=sorted)[:10]:
        print("   reference only:", sorted(g)[:8])
    for g in sorted(only_b, key=sorted)[:10]:
        print("   current only:  ", sorted(g)[:8])
    return ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    prj, name, work = locate(args[0] if args else None)
    ref_file = work / "reference_nets.json"
    s, p = sch_groups(prj, name), pcb_groups(prj, name)
    if "--save" in sys.argv:
        ref_file.parent.mkdir(exist_ok=True)
        ref_file.write_text(json.dumps({"sch": s, "pcb": p}, indent=0))
        print(f"reference saved: {len(s)} schematic nets, {len(p)} PCB nets")
        return
    if not ref_file.exists():
        sys.exit(f"no reference ({ref_file}): run with --save on the raw import first")
    expected = dict(EXPECTED)
    exp_file = work / "check_nets_expected.json"
    if exp_file.exists():
        expected.update(json.loads(exp_file.read_text()))
    ref = json.loads(ref_file.read_text())
    skip = set(expected["new_refs"])
    ok1 = compare("schematic", ref["sch"], s, skip, [tuple(m) for m in expected["sch_merge"]])
    # PCB: free pads without a reference designator are keyed by their position ("@…") and ignored, like "#…"
    ok2 = compare("PCB      ", ref["pcb"], p, skip)
    sys.exit(0 if ok1 and ok2 else 1)


if __name__ == "__main__":
    main()
