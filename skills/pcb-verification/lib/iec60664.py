"""IEC 60664-1 (ed. 3.0, Annex F) tables for the isolation barrier of a printed board, and their readings: F.2
(transient), F.8 case A (steady-state peak), F.5 (creepage), a distance against its uncertainty, the three-state
verdict. INDICATIVE values, to be confirmed in the edition that applies to the product; kV peak, V RMS, mm."""
import math

# Table F.2: (kV peak, mm). 17 rows, in increasing order (indicative values, to be confirmed in the applicable edition).
F2 = [(0.33, 0.01), (0.40, 0.02), (0.50, 0.04), (0.60, 0.06), (0.80, 0.10),
      (1.0, 0.15),
      (1.2, 0.25), (1.5, 0.5), (2.0, 1.0), (2.5, 1.5), (3.0, 2.0), (4.0, 3.0), (5.0, 4.0), (6.0, 5.5),
      (8.0, 8.0), (10.0, 11.0), (12.0, 14.0)]
F2_ROWS = 17                   # row count of the table: a regenerated table with a missing row fails at import
PD2_FLOOR_MM = 0.2             # pollution degree 2: minimum clearance whatever the voltage
PD1_COATED_FLOOR_MM = 0.04   # note c of F.2: a coated printed board takes the pollution-degree-1 values, not under 0.04 mm
# Table F.8 case A: (kV peak, mm), four rows (indicative values); the lowest (0.42 mm) is above the pollution-degree-2 floor.
F8_A = [(1.2, 0.42), (1.5, 0.76), (2.0, 1.27), (2.5, 1.80)]
# Table F.5, pollution degree 2: (V RMS working, printed-board reduced column mm, general column of group III mm).
F5_PD2 = [(25, 0.040, 0.50), (40, 0.040, 1.10), (50, 0.040, 1.20), (63, 0.063, 1.25), (100, 0.160, 1.40)]
COLUMNS = ("general", "printed board")
_EPS = 1e-9


def _check_tables():   # a transcription with a missing or swapped row stops at import
    if len(F2) != F2_ROWS:
        raise AssertionError(f"table F.2 holds {len(F2)} rows, the source has {F2_ROWS}")
    for name, rows in (("F.2", F2), ("F.8", F8_A), ("F.5", [(v, g) for v, _, g in F5_PD2])):
        for (v0, d0), (v1, d1) in zip(rows, rows[1:]):
            if not (v1 > v0 and d1 > d0):
                raise AssertionError(f"table {name}: rows ({v0}, {d0}) and ({v1}, {d1}) are not increasing")


_check_tables()


def _floor(pollution_degree):
    if pollution_degree == 2:
        return PD2_FLOOR_MM
    if pollution_degree == 1:
        return PD1_COATED_FLOOR_MM
    raise ValueError(f"pollution degree {pollution_degree!r}: only 1 (coated board, note c of F.2) and 2 are tabulated")


def rms_to_peak(kv_rms):
    """RMS → peak, × √2, unrounded."""
    return kv_rms * math.sqrt(2)


def clearance_f2(kv_peak, pollution_degree=2):
    """Clearance in air (mm) to withstand a transient overvoltage of `kv_peak`: first row of F.2 whose voltage
    ≥ kv_peak, with the floor of the pollution degree (2: 0.2 mm; 1, coated board: 0.04 mm). ValueError beyond the
    last row."""
    floor = _floor(pollution_degree)
    for v, d in F2:
        if v >= kv_peak - _EPS:
            return max(d, floor)
    raise ValueError(f"{kv_peak:.3f} kV peak is beyond table F.2 (last row {F2[-1][0]} kV)")


def withstand_f2(gap_mm, pollution_degree=2):
    """Reverse reading of F.2: highest transient withstand (kV peak) whose required clearance ≤ `gap_mm`; None when
    the gap is under the floor."""
    floor = _floor(pollution_degree)
    covered = [v for v, d in F2 if max(d, floor) <= gap_mm + _EPS]
    return max(covered) if covered else None


def clearance_f8(kv_peak, table=None):
    """Clearance in air (mm) to withstand a steady-state, temporary or recurring peak of `kv_peak` (a 60 s AC test, a
    DC withstand): table F.8 case A, interpolated between the rows; ValueError outside them (no extrapolation, no
    fallback on F.2). `table`: the rows [(kV peak, mm), …] of the applicable edition, used instead of the excerpt."""
    rows = F8_A if table is None else [(float(v), float(d)) for v, d in table]
    if any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(rows, rows[1:])):
        raise ValueError("F.8 rows must be in increasing voltage and non-decreasing distance")
    for (v0, d0), (v1, d1) in zip(rows, rows[1:]):
        if v0 - _EPS <= kv_peak <= v1 + _EPS:
            return d0 + (kv_peak - v0) / (v1 - v0) * (d1 - d0)
    raise ValueError(f"{kv_peak:.3f} kV peak is outside the rows of table F.8 given ({rows[0][0]} to {rows[-1][0]} "
                     "kV peak)")


def withstand_f8(gap_mm):
    """Reverse reading of F.8 case A: steady-state peak voltage (kV peak) covered by `gap_mm`, interpolated; None
    outside the rows (below 0.42 mm or above 1.80 mm)."""
    for (v0, d0), (v1, d1) in zip(F8_A, F8_A[1:]):
        if d0 - _EPS <= gap_mm <= d1 + _EPS:
            return v0 + (gap_mm - d0) / (d1 - d0) * (v1 - v0)
    return None


def material_group(cti_v):
    """Material group ("I", "II", "IIIa", "IIIb") from the comparative tracking index (V) of the exact laminate;
    ValueError under 100 V."""
    if cti_v >= 600:
        return "I"
    if cti_v >= 400:
        return "II"
    if cti_v >= 175:
        return "IIIa"
    if cti_v >= 100:
        return "IIIb"
    raise ValueError(f"comparative tracking index {cti_v} V is below 100 V: no material group of IEC 60664-1")


def creepage_required(working_v_rms, required_air_mm, column="general", group=None):
    """Creepage required (mm) on an outer surface at the RMS working voltage (a DC voltage counts for its value):
    F.5, general column or `column="printed board"` (needs `group` "I", "II" or "IIIa"), never below `required_air_mm`,
    the clearance of the most demanding targeted withstand. ValueError beyond the rows (100 V)."""
    air = float(required_air_mm)
    if column not in COLUMNS:
        raise ValueError(f"column {column!r}: expected one of {COLUMNS}")
    if column == "printed board" and group not in ("I", "II", "IIIa"):
        raise ValueError(f"printed-board column needs a documented material group other than IIIb, got {group!r}")
    for v_row, pcb_mm, general_mm in F5_PD2:
        if v_row >= working_v_rms - _EPS:
            return max(pcb_mm if column == "printed board" else general_mm, air)
    raise ValueError(f"{working_v_rms:.1f} V RMS is beyond the rows of table F.5 given (last row {F5_PD2[-1][0]} V)")


def creepage_covered_general(gap_mm):
    """Reading aid, general column only: highest working voltage (V RMS) of F.5 whose general value ≤ `gap_mm`;
    None when no row is covered."""
    covered = [v for v, _, g in F5_PD2 if g <= gap_mm + _EPS]
    return max(covered) if covered else None


def distance_ok(measured_mm, required_mm, uncertainty_mm):
    """A measured distance against a required one, with the uncertainty of the measurement: True / False when it
    passes / misses by more than the uncertainty, None in between (put it in `missing` of `verdict`). Compare
    unrounded values."""
    m, r, u = measured_mm, required_mm, uncertainty_mm
    if m - u >= r - _EPS:
        return True
    if m + u < r - _EPS:
        return False
    return None


def solid_insulation_rule(target_peak_kv):
    """Screening rule for inner layers and between layers (solid insulation, no table of the standard applies): the F.2
    clearance of the targeted peak, floor included. A distance below it is flagged, not a fail."""
    return clearance_f2(target_peak_kv, pollution_degree=2)


def verdict(judged, missing=None, not_applicable=None):
    """Three-state verdict of the chapter: {"verdict": "fail" | "incomplete" | "pass", "decided_by", "missing",
    "not_applicable"}. `judged` {criterion: True | False}; `missing` and `not_applicable` {criterion: reason}. Fail if
    one judged criterion fails; else incomplete if one is missing or nothing was judged; else pass."""
    missing = dict(missing or {})
    not_applicable = dict(not_applicable or {})
    for name, ok in judged.items():
        if not isinstance(ok, bool):                # None would read as a fail, not as missing
            raise ValueError(f"criterion {name!r}: a judged value is True or False, got {ok!r} (use `missing`)")
    failed = [name for name, ok in judged.items() if not ok]
    if failed:
        state = "fail"
    elif missing or not judged:
        state = "incomplete"
        if not judged and not missing:
            missing = {"(all)": "no criterion was judged"}
    else:
        state = "pass"
    return {"verdict": state, "decided_by": failed, "missing": missing, "not_applicable": not_applicable}
