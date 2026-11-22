"""Runs an ngspice netlist and returns its measures only from a run that reached its stop time."""
import math
import re
import shutil
import subprocess
from pathlib import Path

RETRY = {"fast": [{}, {"abstol": "1n"}], "slow": [{}, {"gmin": "1e-10", "rshunt": "1e9"}], "once": [{}]}
TIMEOUT = {"fast": 60.0, "slow": 300.0, "once": 60.0}
TLAST = "spicerun_tlast"
# the deck is wrong whatever the options
_HARD = re.compile(r"fatal|unknown|can't find|could not find|not found|ignored|undefined", re.I)
_NUMERIC = re.compile(r"timestep too small|simulation\(s\) aborted|stepping failed|iteration limit|singular matrix|"
                      r"op failed|failed to converge", re.I)
_DECK = re.compile(r"\berror\b|warning|ignored|can't|could not|cannot|unable|unknown|not found|fatal|failed", re.I)
# notes, the title line, measure values, and the operating point's search when the run went through
_BENIGN = re.compile(r"^\s*(note|circuit):|^\s*\w+\s*=\s*[-+.\d]|stepping|singular matrix", re.I)
_MEAS = re.compile(r"^\s*(\w+)\s*=\s*(\S+)", re.M)
_SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12,
           "mil": 25.4e-6}
_NUM = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)(meg|mil|[fpnumkgt])?[a-z]*$", re.I)


class SpiceError(RuntimeError):
    pass


def number(text):
    """A SPICE number: '20n' → 2e-8, '1meg' → 1e6, '10ns' → 1e-8."""
    m = _NUM.match(text.strip())
    if not m:
        raise ValueError("not a SPICE number: %r (write the .tran with numbers)" % text)
    return float(m.group(1)) * _SUFFIX.get((m.group(2) or "").lower(), 1.0)


def _tstop(lines):
    found = [ln for ln in lines if re.match(r"\s*\.tran\b", ln, re.I)]
    if len(found) > 1:
        raise SpiceError("one .tran line per deck, found %d" % len(found))
    return number(found[0].split()[2]) if found else None


def _deck(lines, extra, tstop):
    lines = list(lines)
    if tstop is not None:
        end = max((k for k, ln in enumerate(lines) if re.match(r"\s*\.end\s*$", ln, re.I)), default=len(lines))
        lines.insert(end, ".meas tran %s MAX time" % TLAST)
    if extra:
        at = next((k for k, ln in enumerate(lines) if re.match(r"\s*\.tran\b", ln, re.I)), len(lines))
        lines.insert(at, ".options " + " ".join("%s=%s" % kv for kv in extra.items()))
    return "\n".join(lines) + "\n"


def _once(text, cir, workdir, limit, tstop, measures):
    """("ok", measures, output) or (outcome, reason, output), outcome "numeric" or "deck"."""
    cir.write_text(text, encoding="utf-8")
    try:
        p = subprocess.run(["ngspice", "-b", str(cir)], cwd=str(workdir), capture_output=True, text=True,
                           timeout=limit, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "numeric", "no end in %.0f s" % limit, ""
    out = p.stdout + "\n" + p.stderr
    got = {}
    for m in _MEAS.finditer(p.stdout):
        try:
            got[m.group(1).lower()] = float(m.group(2))
        except ValueError:
            got[m.group(1).lower()] = math.nan
    bad = [ln.strip() for ln in out.splitlines() if _DECK.search(ln) and not _BENIGN.search(ln)]
    hard = [ln for ln in bad if _HARD.search(ln)]
    if hard:
        return "deck", hard[0][:160], out
    if tstop is not None and not got.get(TLAST, -math.inf) >= tstop * (1 - 1e-6):
        hit = [ln.strip() for ln in out.splitlines() if _NUMERIC.search(ln)]
        if hit or TLAST in got:
            return "numeric", (hit[0] if hit else "stopped at %.4g s before %.4g s" % (got[TLAST], tstop))[:160], out
        return "deck", (bad[0] if bad else "exit status %d, no stop time printed" % p.returncode)[:160], out
    if bad:
        return "deck", bad[0][:160], out
    if p.returncode:
        return "deck", "exit status %d" % p.returncode, out
    for k in measures:
        if not math.isfinite(got.get(k, math.nan)):
            return "deck", "measure %s %s" % (k, "not printed" if k not in got else "not finite"), out
    got.pop(TLAST, None)
    return "ok", got, out


def run(deck, kind, name, workdir, measures=(), timeout=None):
    """Writes <workdir>/<name>.cir, runs `ngspice -b` and returns {"measures", "options", "note", "output"}; raises
    SpiceError on an error of the deck or a run that does not converge. `kind`: "fast" (ns events; retry abstol=1n),
    "slow" (surge, hot-plug, rail transients; retry gmin, rshunt), "once" (op, AC, DC sweep; no retry)."""
    if kind not in RETRY:
        raise ValueError("kind is one of %s, got %r" % (sorted(RETRY), kind))
    if not shutil.which("ngspice"):
        raise SpiceError("ngspice not found on PATH (pcb-verification, references/toolchain.md)")
    measures = [m.lower() for m in measures]
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    lines = deck.splitlines()
    tstop = _tstop(lines)
    reasons = []
    for extra in RETRY[kind]:
        outcome, got, out = _once(_deck(lines, extra, tstop), workdir / ("%s.cir" % name), workdir,
                                  float(timeout or TIMEOUT[kind]), tstop, measures)
        if outcome == "deck":
            raise SpiceError("%s: %s (%s; an error of the deck)" % (name, got, workdir / ("%s.cir" % name)))
        if outcome == "ok":
            note = " ".join("%s=%s" % kv for kv in extra.items()) or "as written"
            if reasons:
                note += " (as written: %s)" % reasons[0]
            return {"measures": got, "options": dict(extra), "note": note, "output": out}
        reasons.append(got)
    raise SpiceError("%s did not converge: %s" % (name, "; ".join(reasons)))
