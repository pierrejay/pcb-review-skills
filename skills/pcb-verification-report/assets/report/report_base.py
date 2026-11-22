"""Common base of the PDF verification reports, copied as is into <board>/verification/scripts/: matplotlib style,
numbers in the designer's language, computed verdicts (OK ACC RES NOK MES INC), rendering and PDF check. A template
displays a verdict only as verdict(vd["n"]); OK, NOK… only compare in it (printing one fails the rendering)."""
import base64
import datetime
import hashlib
import io
import math
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from jinja2 import Environment, FileSystemLoader, StrictUndefined  # noqa: E402

VERSION = "2026-11-13"


def _chrome():
    """$PCB_CHROME, else the first Chrome / Chromium found; resolved at rendering time."""
    env = os.environ.get("PCB_CHROME")
    if env:
        if Path(env).exists():
            return env
        raise RuntimeError(f"PCB_CHROME={env} does not exist")
    candidates = [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                                             "chrome")]
    candidates += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise RuntimeError("no Chrome / Chromium found to print the PDF: set PCB_CHROME to the executable")


# Palette of the reports: categorical colours C1…C5, CRIT for limits, INK/INK2 for text (rules of use: the
# skill's references/method.md § 5)
C1, C2, C3, C4, C5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
SERIES = [C1, C2, C3, C4, C5]
CRIT, INK, INK2, GRID = "#d03b3b", "#0b0b0b", "#52514e", "#dddcd8"

# --- language --------------------------------------------------------------------------------------------------
# Fixed texts of the base (cover, summary, annex, verdict labels), one entry per language.
TEXTS = {
    "en": {
        "dec_sep": ".", "date_fmt": "%Y-%m-%d", "html_lang": "en",
        "verdict_ok": "✔ Pass", "verdict_acc": "✔ Pass *", "verdict_res": "▲ Pass with reservation",
        "verdict_nok": "✖ Fail",
        "verdict_mes": "◷ To be measured",
        "verdict_inc": "◌ Incomplete",
        "report": "Verification report", "footer": "verification report", "page": "page",
        "board": "Board", "state": "State verified", "git_repo": "git repository", "stackup": "Stackup",
        "date": "Date", "reproduction": "Reproduction", "in_dir": "in",
        "nature": ("<b>Nature of the document.</b> Design review by calculation and simulation, made so as not to "
                   "arrive at the tests (EMC, CE marking) with an obvious defect; it is not a compliance test. "
                   "\"Pass\" means that the board passes the stated criterion, with the models and assumptions of "
                   "the chapter. For lack of published data, a value is estimated (neighbouring part, qualification "
                   "level, typical value with margin) rather than giving up the calculation: each estimate is "
                   "listed below with its basis, and the tests it touches carry its mark."),
        "scope": "Scope of use (the verdicts hold within this scope)",
        "scope_cols": ("Requirement", "Value retained", "Status"),
        "summary": "Summary", "summary_cols": ("#", "Test", "Criterion", "Result", "Verdict"),
        "accepted": "Deviations accepted by the designer",
        "accepted_cols": ("Mark", "Tests", "Rule", "Finding", "Effect", "Decision", "To be reviewed if"),
        "accepted_note": ("* A deviation from the rule exists and has been accepted by the designer: see "
                          "\"Deviations accepted by the designer\" below. \"Pass with reservation\": the criterion "
                          "passes, but an estimate or a point not yet arbitrated can flip the verdict. \"Fail\": "
                          "deviation from the rule, not arbitrated."),
        "estimates": "Stated estimates and shortcuts",
        "estimates_cols": ("Mark", "Subject", "Value retained", "Basis of the estimate", "Tests", "To confirm"),
        "open_points": "Open points and measurements on the prototype",
        "open_points_cols": ("Subject", "What", "Nature"),
        "recommendations": "Recommendations for a board revision",
        "recommendations_note": ("Computed improvements, without verdict: the board passes its criteria without them; "
                                 "the designer chooses."),
        "recommendations_cols": ("Where", "Now", "Recommended", "Computed gain"),
        "annex": "Annex — Assumptions, limits, traceability", "assumptions": "Model assumptions and limits",
        "traceability": "Traceability",
        "objective": "Objective", "method": "Method", "criterion": "Criterion",
        "no_commit": "no commit", "dirty": " (+ uncommitted changes)",
    },
    "fr": {
        "dec_sep": ",", "date_fmt": "%d/%m/%Y", "html_lang": "fr",
        "verdict_ok": "✔ Conforme", "verdict_acc": "✔ Conforme *", "verdict_res": "▲ Conforme avec réserve",
        "verdict_nok": "✖ Non conforme",
        "verdict_mes": "◷ À mesurer",
        "verdict_inc": "◌ Incomplet",
        "report": "Rapport de vérification", "footer": "rapport de vérification", "page": "page",
        "board": "Carte", "state": "État vérifié", "git_repo": "dépôt git", "stackup": "Stackup",
        "date": "Date", "reproduction": "Reproduction", "in_dir": "dans",
        "nature": ("<b>Nature du document.</b> Revue de conception par calcul et simulation, faite pour ne pas "
                   "arriver aux essais (CEM, marquage CE) avec un défaut évident ; ce n'est pas un essai de "
                   "conformité. « Conforme » signifie que la carte passe le critère indiqué, avec les modèles et "
                   "hypothèses du chapitre. Faute de donnée publiée, une valeur est estimée (référence voisine, "
                   "niveau de qualification, valeur typique majorée) plutôt que de renoncer au calcul : chaque "
                   "estimation est listée ci-dessous avec sa base, et les tests qu'elle touche portent son repère."),
        "scope": "Cadre d'emploi (les verdicts valent dans ce cadre)",
        "scope_cols": ("Exigence", "Valeur retenue", "Statut"),
        "summary": "Synthèse", "summary_cols": ("#", "Test", "Critère", "Résultat", "Verdict"),
        "accepted": "Écarts acceptés par le designer",
        "accepted_cols": ("Repère", "Tests", "Règle", "Constat", "Effet", "Décision", "À revoir si"),
        "accepted_note": ("* Un écart à la règle existe et a été accepté par le designer : voir « Écarts acceptés » "
                          "ci-dessous. « Conforme avec réserve » : le critère passe, mais une estimation ou un point "
                          "non arbitré peut faire basculer le verdict. « Non conforme » : écart à la règle, non "
                          "arbitré."),
        "estimates": "Estimations et raccourcis assumés",
        "estimates_cols": ("Repère", "Sujet", "Valeur retenue", "Base de l'estimation", "Tests", "Pour confirmer"),
        "open_points": "Points ouverts et mesures sur proto",
        "open_points_cols": ("Sujet", "Quoi", "Nature"),
        "recommendations": "Préconisations pour une révision de la carte",
        "recommendations_note": ("Améliorations chiffrées, sans verdict : la carte passe ses critères sans elles ; "
                                 "le designer choisit."),
        "recommendations_cols": ("Où", "Aujourd'hui", "Préconisé", "Gain calculé"),
        "annex": "Annexe — Hypothèses, limites, traçabilité", "assumptions": "Hypothèses de modèle et limites",
        "traceability": "Traçabilité",
        "objective": "Objectif", "method": "Méthode", "criterion": "Critère",
        "no_commit": "pas de commit", "dirty": " (+ modifications non commitées)",
    },
}
LANG = "en"
DEC_SEP = "."  # decimal separator of the designer's language ("." English, "," French); set by set_language()


def set_language(lang, dec_sep=None):
    """Language of the base texts and of the numbers ("en", "fr"); call it before building figures and rendering."""
    global LANG, DEC_SEP
    LANG = lang
    DEC_SEP = dec_sep or TEXTS[lang]["dec_sep"]


def T(key):
    """Base text in the current language."""
    return TEXTS[LANG][key]


def mm(*v):
    """Lengths in mm → unit imposed by matplotlib (figsize). The only place where the imperial unit exists."""
    t = tuple(x / 25.4 for x in v)
    return t[0] if len(t) == 1 else t


W = mm(170)  # usable width of an A4 page with 15 mm margins (in figsize units)

plt.rcParams.update({"font.family": ["Helvetica Neue", "DejaVu Sans"], "font.size": 8.5, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
                     "axes.spines.right": False, "lines.linewidth": 2, "legend.frameon": False,
                     "svg.fonttype": "none", "axes.axisbelow": True})


# verdicts: (CSS class, icon + label) — never colour alone. v[0] = class, v[1] = label in the current language.
class Verdict:
    __slots__ = ("css",)

    def __init__(self, css):
        self.css = css

    @property
    def label(self):
        return T("verdict_" + self.css)

    def __getitem__(self, i):
        return (self.css, self.label)[i]

    def __iter__(self):
        return iter((self.css, self.label))

    def __repr__(self):
        return f"Verdict({self.css!r})"


class _Drawn:
    """A verdict drawn from the summary (vd["n"]), the only kind verdict() displays; compares as its verdict."""
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __getitem__(self, i):
        return self.v[i]

    def __iter__(self):
        return iter(self.v)

    def __getattr__(self, name):
        return getattr(self.v, name)

    def __eq__(self, other):
        return self.v is (other.v if isinstance(other, (_Drawn, _Kind)) else other)

    def __hash__(self):
        return id(self.v)


class _Kind:
    """OK, NOK… as the template sees them: they compare, and fail the rendering when printed or displayed."""
    __slots__ = ("v", "name")

    def __init__(self, v, name):
        self.v, self.name = v, name

    def __eq__(self, other):
        return (other.v if isinstance(other, (_Drawn, _Kind)) else other) is self.v

    def __hash__(self):
        return id(self.v)

    def _refuse(self, *_):
        raise ValueError(f"{self.name} written in the template: a verdict is displayed with verdict(vd[\"n\"]), "
                         "computed in the script; the names only compare")

    __str__ = __getitem__ = __iter__ = _refuse

    def __repr__(self):
        return self.name

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        self._refuse()


def _show(v):
    if not isinstance(v, _Drawn):
        raise ValueError(f"verdict({v!r}): only a verdict drawn from the summary is displayed; use verdict(vd[\"n\"]), "
                         "computed in the script")
    return f'<span class="verdict v-{v.css}">{v.label}</span>'


OK, ACC, RES, NOK, MES = Verdict("ok"), Verdict("acc"), Verdict("res"), Verdict("nok"), Verdict("mes")
INC = Verdict("inc")   # a criterion that applies could not be judged (input missing, geometry outside the domain)
VERDICTS = {"OK": OK, "ACC": ACC, "RES": RES, "NOK": NOK, "MES": MES, "INC": INC}
_SEVERITY = [OK, ACC, RES, MES, INC, NOK]  # from best to worst: an incomplete check is never reported as compliant
_RESERVES = set()  # marks passed to verdict_threshold(reserve=… or screening=…): checked by render() against
                   # FIXED["estimates"]
_ACCEPTED = {}     # (mark, test) → value passed to accept() / accept_estimate(): checked by render() against
                   # FIXED["accepted_deviations"]


def _finite(x, name):   # no verdict on a lost value
    if x is None or not math.isfinite(x):
        raise ValueError(f"verdict impossible: {name} = {x!r} (result missing or not finite)")
    return x


def verdict_threshold(value, limit, sense="max", reserve=None, resolution=None, screening=None):
    """Computed verdict: sense 'max' met if value ≤ limit, 'min' if value ≥ limit. Met → OK, or RES with `reserve` (mark
    of the deciding estimate in FIXED["estimates"]); not met → NOK, or RES within `resolution` (how finely the value is
    known, needs `reserve`). `screening` (an estimate's mark; not with `reserve`): met → RES, not met → MES."""
    _finite(value, "value"); _finite(limit, "limit")
    if sense not in ("max", "min"):
        raise ValueError(f"sense = {sense!r}: 'max' or 'min'")
    if screening:
        if reserve or resolution is not None:
            raise ValueError("screening with reserve or resolution: a screening limit already makes the verdict a "
                             "reservation (met) or a measurement (not met)")
        _RESERVES.add(screening)
        met = value <= limit if sense == "max" else value >= limit
        return RES if met else MES
    if resolution is not None:
        if not reserve:
            raise ValueError("a resolution without reserve: a deviation within it is a reservation on the estimate "
                             "that carries it; name that estimate (reserve='E…')")
    if reserve:
        _RESERVES.add(reserve)
    deviation = value - limit if sense == "max" else limit - value
    if deviation <= 0:
        return RES if reserve else OK
    return RES if resolution is not None and deviation <= resolution else NOK


def _value(value, mark):
    if value is None or (isinstance(value, float) and not math.isfinite(value)) or value == "":
        raise ValueError(f"accepted deviation {mark}: the value the decision was taken on is missing ({value!r})")
    return value


def accept(verdict, mark, test, value):
    """Deviation accepted by the designer: NOK becomes ACC ("Pass *"); any other verdict raises. `mark` (e.g. "A1") and
    `test` (e.g. "19") name the decision listed in FIXED["accepted_deviations"]; `value`, the result judged now (rounded
    as the finding prints it), must equal the value listed there (render() checks)."""
    if verdict is NOK:
        _ACCEPTED[(mark, str(test))] = _value(value, mark)
        return ACC
    raise ValueError(f"accepted deviation {mark} has no object: the criterion gives {verdict.label!r}; remove it")


def accept_estimate(verdict, mark, test, value):
    """Partial data accepted by the designer: RES becomes ACC ("Pass *"); any other verdict raises. Arguments as for
    accept()."""
    if verdict is RES:
        _ACCEPTED[(mark, str(test))] = _value(value, mark)
        return ACC
    raise ValueError(f"partial data {mark} has no object: the criterion gives {verdict.label!r} (accept_estimate() "
                     "takes a pass on an estimate; a fail is accepted with accept())")


def incomplete(result):
    """INC when a step wrote a refusal instead of its result ({"incomplete": message}, `messages.write_incomplete`),
    else None."""
    return INC if isinstance(result, dict) and result.get("incomplete") else None


def worst(*verdicts):
    """Verdict of a test with several criteria: the most unfavourable (NOK > INC > MES > RES > ACC > OK)."""
    return max(verdicts, key=_SEVERITY.index)


# --- numbers ---------------------------------------------------------------------------------------------------
def num(x, n=2):
    """Number with n decimals and the separator of the language (DEC_SEP). Jinja filter: {{ x|num(1) }}."""
    return f"{x:.{n}f}".replace(".", DEC_SEP)


def numg(x):
    """Number without useless zeros (0.12 → 0.12; 0.136 → 0.136). Jinja filter: {{ x|numg }}."""
    return f"{x:g}".replace(".", DEC_SEP)


def pct(x, n=0):
    """Ratio as a percentage in the language: pct(0.875) → "88 %" (fr) / "88%" (en)."""
    return num(100 * x, n) + ("\u202f%" if LANG == "fr" else "%")


def date_txt(iso):
    """ISO date (YYYY-MM-DD) in the language's format."""
    return datetime.date.fromisoformat(str(iso)[:10]).strftime(T("date_fmt"))


# Coded messages of the modules (lib/messages.py), per language: code → text built from its values (used by msg()).
_MSG = {
    "fr": {
        "not_judged": lambda v: "non jugé : " + msg(v["reason"]),
        "rating_not_read": lambda v: "valeur assignée non lue dans la description (" + {
            "voltage": "tension", "power": "puissance", "reverse voltage": "tension inverse",
            "current": "courant", "tolerance": "tolérance"}[v["what"]] + ")",
        "zero_ohm_link": lambda v: "aucune tension à ses bornes (liaison 0 Ω)",
        "no_reverse_voltage": lambda v: "pas de tension inverse à juger (LED, Zener)",
        "current_not_declared": lambda v: "courant non déclaré",
        "power_to_determine": lambda v: "non jugé : puissance à déterminer (résistance entre deux signaux)",
        "cap_voltage": lambda v: f"{num(v['v'])} V pour {numg(v['rated'])} V assignés : {pct(v['ratio'])} > {pct(v['limit'])}",
        "cap_bias": lambda v: f"{v['dielectric']} à {pct(v['ratio'])} de sa tension assignée : capacité effective à vérifier",
        "res_power": lambda v: (f"{num(v['p_w'] * 1e3)} mW pour {numg(v['rated_w'] * 1e3)} mW assignés : "
                                f"{pct(v['ratio'])} > {pct(v['limit'])}"),
        "res_voltage": lambda v: f"{num(v['v'])} V au-dessus de la tension assignée {numg(v['rated'])} V",
        "diode_reverse": lambda v: (f"{num(v['v'])} V en inverse pour VRRM {numg(v['rated'])} V : {pct(v['ratio'])} > "
                                    f"{pct(v['limit'])}"),
        "vrwm_below": lambda v: f"VRWM {numg(v['vrwm'])} V < {num(v['v'])} V permanents",
        "vrwm_close": lambda v: (f"VRWM {numg(v['vrwm'])} V seulement {pct(v['margin'])} au-dessus de {num(v['v'])} V : "
                                 f"la fuite monte près de la tension de veille"),
        "inductor_no_current": lambda v: "inductance sans courant déclaré",
        "bead_no_current": lambda v: "perle sans courant déclaré",
        "inductor_current": lambda v: (f"{num(v['i'])} A crête pour {numg(v['rated'])} A assignés : {pct(v['ratio'])} > "
                                       f"{pct(v['limit'])}"),
        "bead_current": lambda v: f"{num(v['i'])} A pour {numg(v['rated'])} A assignés : {pct(v['ratio'])} > {pct(v['limit'])}",
        "t_max_not_read": lambda v: "température maximale non lue dans la description",
        "t_max_low": lambda v: f"tenue jusqu'à {numg(v['t_max'])} °C pour {numg(v['limit'])} °C d'ambiante + échauffement de carte",
        "stock_unknown": lambda v: f"stock inconnu au {date_txt(v['date'])}",
        "stock_zero": lambda v: f"stock nul au {date_txt(v['date'])} : bloque une commande assemblée",
        "stock_low": lambda v: f"stock {v['stock']} < {v['minimum']} au {date_txt(v['date'])}",
        "crosses": lambda v: "traverse " + " ↔ ".join(v["domains"]) + " : jugé aux chapitres isolement / ESD / choc",
        "crosses_barrier": lambda v: "traverse une barrière (isolement, châssis)",
        "off_board_undeclared": lambda v: ("net hors carte non déclaré (" + ", ".join(v["nets"])
                                           + ") : déclarer sa plage"),
        "assumed_near_rating": lambda v: (f"jugé sur une tension supposée à {pct(v['ratio'])} de sa valeur assignée : "
                                          "déclarer ses nets"),
        "series_flat": lambda v: f"série dans {pct(v['band'])}",
        "series_two_readings": lambda v: (f"deux lectures à {pct(v['spread'], 1)} l'une de l'autre : un troisième "
                                          f"maillage est nécessaire pour voir les écarts diminuer"),
        "series_last_step": lambda v: f"dernier pas {pct(v['step'], 1)} > {pct(v['limit'])}",
        "series_not_shrinking": lambda v: ("écarts qui ne diminuent pas : rapport "
                                           + ("indéfini" if v["ratio"] is None else num(v["ratio"]))
                                           + f" > {num(v['limit'], 1)}"),
        "series_richardson": lambda v: f"monotone, rapport {num(v['ratio'])} : Richardson avec le rapport observé",
        "series_oscillating": lambda v: "oscillante et amortie : dernière valeur",
    },
}


def msg(m):
    """A coded message of a module (a `messages.Msg`, or its record read from a JSON) in the report's language; English
    and a record without a code keep their text. A code missing from _MSG raises. Jinja filter: {{ row.flag|msg }}."""
    if isinstance(m, dict):
        text, code, values = m.get("text", ""), m.get("code"), m.get("values", {})
    else:
        text, code, values = str(m), getattr(m, "code", None), getattr(m, "values", {})
    if code is None or LANG == "en":
        return text
    return _MSG[LANG][code](values)


def axis_num(axis, n=1):
    """Tick labels of an axis with the separator of the language: axis_num(ax.xaxis, 1)."""
    axis.set_major_formatter(FuncFormatter(lambda v, _: num(v, n)))


# --- figures ---------------------------------------------------------------------------------------------------
def svg(fig):
    """Figure → inline SVG (text kept, sharp in print). Closes the figure."""
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    s = buf.getvalue()
    return s[s.index("<svg"):]


def png_b64(path):
    """Existing image (voltage-drop map, 3D render…) → data URI."""
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def legend_below(ax_or_fig, ncol=3, dy=-0.2, fontsize=7.5, **kw):
    """Legend under the plot: never hides a curve. For a figure with several axes, pass the figure."""
    if hasattr(ax_or_fig, "axes") and not hasattr(ax_or_fig, "plot"):  # Figure
        h, l = ax_or_fig.axes[0].get_legend_handles_labels()
        return ax_or_fig.legend(h, l, ncol=ncol, loc="upper center", bbox_to_anchor=(0.5, -0.01),
                                fontsize=fontsize, **kw)
    return ax_or_fig.legend(ncol=ncol, loc="upper center", bbox_to_anchor=(0.5, dy), fontsize=fontsize, **kw)


def limit_line(ax, v, text, axis="y", pos=None, style="--"):
    """Limit line (red CRIT) with its label; axis='y' → horizontal, 'x' → vertical."""
    if axis == "y":
        ax.axhline(v, color=CRIT, linewidth=1.3, linestyle=style)
        x = pos if pos is not None else ax.get_xlim()[0]
        ax.text(x, v, " " + text, color=CRIT, fontsize=7, va="bottom")
    else:
        ax.axvline(v, color=CRIT, linewidth=1.3, linestyle=style)
        y = pos if pos is not None else -0.75
        ax.text(v, y, " " + text, color=CRIT, fontsize=7)


# --- data ------------------------------------------------------------------------------------------------------
def load(results_dir, name):
    """Reads results/<name>."""
    return json.loads((Path(results_dir) / name).read_text())


def fingerprints(board_dir):
    """Short fingerprint (SHA-256, 8 characters) of the schematic and PCB verified: identifies the exact state even
    when changes are not committed."""
    out = []
    for ext, name in ((".kicad_sch", "sch"), (".kicad_pcb", "pcb")):
        for f in sorted(Path(board_dir).glob(f"*{ext}")):
            out.append(f"{name} {hashlib.sha256(f.read_bytes()).hexdigest()[:8]}")
    return " · ".join(out)


def git_info(board_dir, ignore=("verification/verification_report.pdf",)):
    """Hash + date of the last commit, uncommitted changes flagged (the report PDF ignored), fingerprints of the
    schematic and PCB."""
    try:
        h = subprocess.run(["git", "-C", str(board_dir), "log", "-1", "--format=%h %ad", "--date=short"],
                           capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(board_dir), "status", "--porcelain", "--", "."]
                               + [f":(exclude){x}" for x in ignore], capture_output=True, text=True).stdout.strip()
        state = (h or T("no_commit")) + (T("dirty") if dirty else "")
    except Exception:
        state = "?"
    e = fingerprints(board_dir)
    return f"{state} ; {e}" if e else state


# --- rendering -------------------------------------------------------------------------------------------------
def _scratch(tmp, prefix):
    """A new folder under `tmp` (created if needed), for one browser or pdftoppm run."""
    Path(tmp).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=tmp))


def render(template, ctx, html_out, pdf_out, tmp=None):
    """Renders the jinja template (extending report_base.html) and prints the PDF with headless Chrome in a new folder
    under `tmp` (default: tmp/ beside `pdf_out`); returns the PDF path. `ctx`: "F" (FIXED), "summary" [(no., test,
    criterion, result, verdict)] and the template's variables; FIXED["estimates"] = [(mark, subject, value, basis,
    [tests], to confirm)], FIXED["accepted_deviations"] = [(mark, [tests], rule, finding, effect, decision, to be
    reviewed if, {test: value accepted})]. Raises on any inconsistency between them, the verdicts and accept() calls."""
    template = Path(template)
    F = ctx.get("F", {})
    summary = ctx.get("summary", [])
    vd = {}
    for n, _t, _c, _r, v in summary:
        if not any(v is x for x in VERDICTS.values()):
            raise ValueError(f"summary, test {n}: unknown verdict {v!r}")
        if n in vd:
            raise ValueError(f"summary: test {n} listed twice")
        vd[n] = v
    refs = {}
    for e in F.get("estimates", []):
        for n in e[4]:
            if n not in vd:
                raise ValueError(f"estimate {e[0]}: test {n} absent from the summary")
            refs.setdefault(n, []).append(e[0])
    # reservations: every mark passed to verdict_threshold exists, every "with reservation" test cites an estimate
    unknown = sorted(_RESERVES - {e[0] for e in F.get("estimates", [])})
    if unknown:
        raise ValueError(f"reservation(s) {unknown} passed to verdict_threshold but absent from FIXED[\"estimates\"]")
    orphans = [n for n, v in vd.items() if v == RES and n not in refs]
    if orphans:
        raise ValueError(f"test(s) {orphans} \"Pass with reservation\" cited by no estimate in FIXED[\"estimates\"]")
    # accepted deviations: FIXED["accepted_deviations"] = [(mark, [test nos.], rule, finding, effect, decision,
    # to be reviewed if, {test no.: value accepted})]
    acc = {}
    for e in F.get("accepted_deviations", []):
        if len(e) != 8 or not isinstance(e[7], dict) or {str(n) for n in e[7]} != {str(n) for n in e[1]}:
            raise ValueError(f"accepted deviation {e[0]}: (mark, [tests], rule, finding, effect, decision, to be "
                             "reviewed if, {test: value accepted}), a value for each of its tests")
        for n in e[1]:
            if n not in vd:
                raise ValueError(f"accepted deviation {e[0]}: test {n} absent from the summary")
            if vd[n] is OK:
                raise ValueError(f"accepted deviation {e[0]}: test {n} passes without deviation; remove the decision")
            acc.setdefault(n, []).append(e[0])
    orphans = [n for n, v in vd.items() if v is ACC and n not in acc]
    if orphans:
        raise ValueError(f"test(s) {orphans} are \"Pass *\" with no decision listed in FIXED[\"accepted_deviations\"]")
    # every accept() call names a listed decision, for a test the decision lists; every listed decision is used
    listed = {(e[0], str(n)): v for e in F.get("accepted_deviations", []) for n, v in e[7].items()}
    wrong = sorted(set(_ACCEPTED) - set(listed))
    if wrong:
        raise ValueError(f"accept() with (decision, test) {wrong} not listed in FIXED[\"accepted_deviations\"]")
    moved = sorted(f"{m} test {t}: accepted {listed[(m, t)]!r}, now {v!r}" for (m, t), v in _ACCEPTED.items()
                   if v != listed[(m, t)])
    if moved:
        raise ValueError(f"accepted deviation(s) taken on another value: {'; '.join(moved)}: re-decide with the "
                         "designer")
    unused = sorted({m for m, _ in listed} - {m for m, _ in _ACCEPTED})
    if unused:
        raise ValueError(f"accepted deviation(s) {unused} listed but never applied with accept()")
    not_called = sorted(n for n, v in vd.items() if v is ACC and not any(t == str(n) for _, t in _ACCEPTED))
    if not_called:
        raise ValueError(f"test(s) {not_called} are \"Pass *\" without an accept() call naming them")
    ctx = {**ctx, "vd": {n: _Drawn(v) for n, v in vd.items()}, "est_refs": refs, "acc_refs": acc, "L": TEXTS[LANG],
           "DEC_SEP": DEC_SEP}
    env = Environment(loader=FileSystemLoader([str(template.parent), str(Path(__file__).resolve().parent)]),
                      undefined=StrictUndefined, autoescape=False)
    for name, f in (("num", num), ("numg", numg), ("msg", msg), ("pct", pct)):
        env.filters[name] = f
    env.globals["L"] = TEXTS[LANG]  # also visible from the imported macros (crit)
    env.globals["show_verdict"] = _show   # used by the verdict() macro
    base = {"date": datetime.date.today().strftime(T("date_fmt")), **{k: _Kind(v, k) for k, v in VERDICTS.items()}}
    html = env.get_template(template.name).render(**{**base, **ctx})
    html_out = Path(html_out)
    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.write_text(html)
    pdf_out = Path(pdf_out)
    chrome = _chrome()
    work = _scratch(tmp or pdf_out.parent / "tmp", "chrome_")
    (work / "tmp").mkdir()
    r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
                        "--no-default-browser-check", f"--user-data-dir={work / 'profile'}",
                        f"--disk-cache-dir={work / 'cache'}", f"--print-to-pdf={pdf_out}", html_out.as_uri()],
                       capture_output=True, text=True, errors="replace",
                       env={**os.environ, "TMPDIR": str(work / "tmp"), "TMP": str(work / "tmp"),
                            "TEMP": str(work / "tmp")})
    if r.returncode != 0:
        raise RuntimeError(f"{chrome} failed (status {r.returncode}) printing {pdf_out}; its profile and temporary "
                           f"files are kept in {work}: {r.stderr.strip()[-400:]}")
    shutil.rmtree(work)
    return pdf_out


# --- check -----------------------------------------------------------------------------------------------------
_SUSPECT = re.compile(r"\b(nan|NaN|None|inf|Undefined)\b")      # a value lost in the data, not a style rule


def check_pdf(pdf, folder=None, sheet=True, dpi=40, columns=5):
    """Re-reads the PDF: pages, values lost in the data (nan, None, inf, Undefined), PNG contact sheet. Returns {"pdf",
    "pages", "alerts", "sheet"}; raises if pdftotext fails or extracts nothing."""
    pdf = Path(pdf)
    r = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True)
    txt = r.stdout
    if r.returncode != 0 or not txt.strip():  # failed extraction = no check at all: do not conclude "zero alerts"
        raise RuntimeError(f"pdftotext failed on {pdf} (code {r.returncode}): {r.stderr.strip()[:200]}")
    pages = txt.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    alerts = []
    for i, p in enumerate(pages, 1):
        for m in _SUSPECT.finditer(p):
            alerts.append(f"p. {i}: suspect value \"{m.group()}\"")
    out = {"pdf": str(pdf), "pages": len(pages), "alerts": alerts}
    if sheet:
        out["sheet"] = str(contact_sheet(pdf, folder or pdf.parent, dpi=dpi, columns=columns))
    return out


def contact_sheet(pdf, folder, dpi=40, columns=5, tmp=None):
    """All pages as thumbnails on one image, <folder>/<pdf>_sheet.png; page images in a new folder under `tmp`."""
    pdf = Path(pdf)
    work = _scratch(tmp or Path(folder) / "tmp", "sheet_")   # fresh folder: no pages from a previous rendering
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(work / "p")], check=True,
                   env={**os.environ, "TMPDIR": str(work)})
    imgs = sorted(work.glob("p-*.png"))
    rows = -(-len(imgs) // columns)
    fig, axs = plt.subplots(rows, columns, figsize=mm(columns * 53, rows * 75), squeeze=False)
    for ax in axs.flat:
        ax.axis("off")
    for k, (ax, f) in enumerate(zip(axs.flat, imgs), 1):
        ax.imshow(plt.imread(f)); ax.set_title(str(k), fontsize=8)
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False, edgecolor=GRID))
    fig.tight_layout()
    out = Path(folder) / f"{pdf.stem}_sheet.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    shutil.rmtree(work)
    return out
