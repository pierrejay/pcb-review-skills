"""Component values read from text: `ohms` and `farads`. The whole string must be recognised; an ambiguous or
unreadable value raises ValueError instead of being guessed."""
import re

_OHMS = re.compile(r"\s*(\d+(?:[.,]\d+)?)\s*(?:([kKmMR])(\d*))?\s*(?:Ω|ohms?)?\s*")


def ohms(value):
    """'2.49k', '2K49', '4.7kΩ', '22R', '0R' → ohms, rounded to 1 Ω (pulls and links, not shunts: a value under
    1 Ω other than 0 raises). '1,000', '4.700' and a lower-case 'm' raise as ambiguous."""
    m = _OHMS.fullmatch(value)
    if not m:
        raise ValueError(f"unreadable resistor value: {value!r}")
    if re.fullmatch(r"\d+[.,]\d{3}", m.group(1)) and not m.group(2):
        raise ValueError(f"ambiguous resistor value {value!r}: thousands separator or decimal separator?")
    if m.group(2) == "m":
        raise ValueError(f"ambiguous resistor value {value!r}: 'm' may be milli or mega; write k, M or R")
    x = float(f"{m.group(1)}.{m.group(3)}") if m.group(3) else float(m.group(1).replace(",", "."))   # 2K49
    x *= {"k": 1e3, "K": 1e3, "M": 1e6}.get(m.group(2), 1)
    if 0 < x < 1:                                     # rounded to 0 it would pass for a 0 Ω link: refused instead
        raise ValueError(f"resistor value {value!r} under 1 Ω: a shunt or sense resistor, not a pull or a 0 Ω link")
    return round(x)


_FARADS = re.compile(r"\s*(\d+(?:[.,]\d+)?)\s*([pnuµμm])(\d*)\s*F?\s*")
_MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3}


def farads(value):
    """'100nF', '4.7uF', '4u7', '2.2µF', '15pF', '1u' → farads; a value without a multiplier ('100', '10k') raises."""
    m = _FARADS.fullmatch(value)
    if not m:
        raise ValueError(f"unreadable capacitor value: {value!r}")
    x = float(f"{m.group(1)}.{m.group(3)}") if m.group(3) else float(m.group(1).replace(",", "."))
    return x * _MULT[m.group(2)]

