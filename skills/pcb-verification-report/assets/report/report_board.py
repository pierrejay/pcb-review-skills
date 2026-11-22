"""Verification report (PDF) of <board>: skeleton to copy into <board>/verification/scripts/report.py, next to
report_base.py / report_base.html / report_macros.html copied unchanged from the skill.
Usage: make report  (the last target of the Makefile);  python report.py --demo  → dummy data, to test the base."""
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from report_base import (C1, C2, CRIT, INK, W, OK, RES, NOK, MES, num, axis_num, mm, svg, load, git_info,  # noqa: F401
                         legend_below, limit_line, render, check_pdf, verdict_threshold, worst, set_language,
                         incomplete)

set_language("en")

V = Path(__file__).resolve().parents[1]
R = V / "results"
OUT = R / "report"
DEMO = "--demo" in sys.argv

FIXED = {
    "board": "[board]",
    "title": "[function of the board]",
    "source": "[source of the design, date]",
    "stackup": "[production and prototype stackups]",
    "reproduction": "make all",
    "scope": [  # (requirement, value retained, status: "declared (date)" or "assumption") — pcb-verification/references/scoping.md
        ("[power supply]", "[source, range, cable]", "assumption"),
    ],
    "open_points": [  # (subject, what, nature: prototype measurement / routing / software / documentary)
        ("[subject]", "[what remains to be lifted and how]", "prototype measurement"),
    ],
    # optional: computed improvements without verdict (e.g. decoupling rows of pcb-check-configuration step 6c)
    # (where, now, recommended, computed gain)
    "recommendations": [
        ("[IC.pin]", "[now]", "[remedy]", "[computed gain]"),
    ],
    # estimates made for lack of published data, stated and visible (cover + mark in the summary):
    # (mark, subject, value retained, basis of the estimate, [nos. of the tests touched], how to confirm it)
    "estimates": [
        ("E1", "[unpublished datum]", "[value retained]", "[neighbouring part, qualification, typical with margin…]",
         ["1"], "[prototype measurement / request to the manufacturer]"),
    ],
    "assumptions": [  # model assumptions (domain of validity, omitted elements), in the annex
        "[model assumption, domain of validity, what is omitted]",
    ],
}


def read(name):
    if DEMO:  # dummy data standing for timing_budget.json (pcb-check-timing), in the demo's own format
        return {"sync_budget": {f"D{i}": {"setup_margin_ns": 1.8 + 0.1 * i, "hold_margin_ns": 2.0 + 0.05 * i,
                                            "direction": "A→B", "length_mm": 20 + 3 * i} for i in range(4)}}
    return load(R, name)


# --- figures: one function per figure, data as argument, returns svg(fig) ---------------------------------------
def fig_margins(timing):
    """Demo figure: margin bars with a limit. Other figure types: references/method.md § 5."""
    b = timing["sync_budget"]
    names = list(b)
    fig, ax = plt.subplots(figsize=(W, mm(10 * len(names) + 23)))
    y = np.arange(len(names)); h = 0.36
    ax.barh(y - h / 2, [b[n]["setup_margin_ns"] for n in names], h, color=C1, label="setup margin")
    ax.barh(y + h / 2, [b[n]["hold_margin_ns"] for n in names], h, color=C2, label="hold margin")
    for i, n in enumerate(names):  # selective labels, text ink (never the colour of the series)
        ax.text(b[n]["setup_margin_ns"] + 0.03, i - h / 2, f"{num(b[n]['setup_margin_ns'])} ns", va="center",
                fontsize=7, color=INK)
    ax.set_yticks(y, [f"{n} ({num(b[n]['length_mm'], 1)} mm)" for n in names]); ax.invert_yaxis()
    ax.set_xlim(-0.2, 3); ax.set_xlabel("Margin (ns)"); ax.grid(axis="y", visible=False)
    limit_line(ax, 0, "limit: zero margin", axis="x")
    axis_num(ax.xaxis, 1)
    legend_below(ax, ncol=2, dy=-0.25)
    return svg(fig)


def main():
    timing = read("timing_budget.json")
    # (no., test, sourced criterion, numeric result, verdict computed with verdict_threshold / worst); the chapter
    # displays vd["n"]
    test1 = ("1", "Synchronous interface timing (demo)", "setup and hold of the receiver (datasheet [ref])")
    ctx = {"F": FIXED, "git": git_info(V.parent), "timing": timing}
    if incomplete(timing):  # the step wrote a refusal: INC with its message, nothing read from the missing result
        summary = [(*test1, timing["incomplete"], incomplete(timing))]
    else:
        setup_min = min(v["setup_margin_ns"] for v in timing["sync_budget"].values())
        hold_min = min(v["hold_margin_ns"] for v in timing["sync_budget"].values())
        summary = [(*test1, f"setup margins ≥ {num(setup_min)} ns, hold ≥ {num(hold_min)} ns",
                    worst(verdict_threshold(setup_min, 0, "min"), verdict_threshold(hold_min, 0, "min", reserve="E1")))]
        ctx.update(setup_min=setup_min, hold_min=hold_min, fig_margins=fig_margins(timing))
    ctx["summary"] = summary
    here = Path(__file__).resolve().parent
    template = here / "report_template.html" if (here / "report_template.html").exists() else here / "report_board.html"
    out = Path.cwd() / "demo_report" if DEMO else OUT
    pdf = render(template, ctx, out / "verification_report.html", (out if DEMO else V) / "verification_report.pdf")
    c = check_pdf(pdf, out)
    print("report:", pdf, f"({c['pages']} pages)")
    print("contact sheet:", c["sheet"])
    for a in c["alerts"]:
        print("  ALERT", a)


if __name__ == "__main__":
    main()
