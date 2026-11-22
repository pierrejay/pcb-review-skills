"""Coded messages of the modules: `Msg` is the English text (a `str`) with a stable `code` and its `values`, which the
report renders in its own language (`report_base.msg`); `record` / `records` turn them into JSON dicts."""


class Msg(str):
    """English text + `code` + `values` (numbers as numbers, dates as ISO strings)."""

    def __new__(cls, text, code, **values):
        m = super().__new__(cls, text)
        m.code, m.values = code, dict(values)
        return m


def record(m):
    """Dict for a JSON result: {"text", "code", "values"}; a plain string gets code None."""
    return {"text": str(m), "code": getattr(m, "code", None), "values": dict(getattr(m, "values", {}))}


def records(ms):
    return [record(m) for m in ms]


def write_incomplete(out_path, exc):
    """Writes {"incomplete": message, "refusal": exception class} to `out_path` and returns it. The step's script
    calls it on a refusal of a `lib/` module (ValueError, `kicad_copper.Unsupported`), then exits 0: the report
    shows INC."""
    import json
    from pathlib import Path
    out = {"incomplete": str(exc), "refusal": type(exc).__name__}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out
