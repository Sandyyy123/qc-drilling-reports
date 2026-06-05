"""
LAS file parser using lasio.
Checks all required curves, detects flatlines, nulls, range anomalies.
"""
import lasio
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


REQUIRED_CURVES = ["GR", "RHOB", "NPHI", "DT", "RT", "CALI"]
CURVE_EXPECTED_RANGES = {
    "GR":   (0, 300),
    "RHOB": (1.5, 3.2),
    "NPHI": (-0.05, 0.60),
    "DT":   (40, 250),
    "RT":   (0.1, 50000),
    "CALI": (4, 30),
    "SP":   (-200, 100),
}
FLATLINE_WINDOW    = 10    # consecutive same-value steps = flatline
NULL_FRACTION_WARN = 0.20  # >20% null = warning


@dataclass
class CurveQC:
    name: str
    unit: str
    present: bool
    null_fraction: float = 0.0
    flatline_intervals: list = field(default_factory=list)  # list of (start_depth, end_depth)
    out_of_range_fraction: float = 0.0
    issues: list = field(default_factory=list)   # human-readable issue strings
    passed: bool = True


@dataclass
class LASParseResult:
    filename: str
    well_name: Optional[str]
    uwi: Optional[str]
    operator: Optional[str]
    rig_name: Optional[str]
    start_depth: Optional[float]
    stop_depth: Optional[float]
    depth_unit: Optional[str]
    depth_steps: int
    null_value: float
    curves: dict        # curve_name -> CurveQC
    missing_required: list
    header_dict: dict


def parse_las(filepath: str) -> LASParseResult:
    las = lasio.read(filepath)
    well = las.well

    def _get(section, key):
        try:   return section[key].value
        except Exception: return None

    well_name  = _get(well, "WELL")
    uwi        = _get(well, "UWI") or _get(well, "API")
    operator   = _get(well, "COMP")
    rig_name   = _get(well, "RIG")
    null_value = las.well["NULL"].value if "NULL" in well else -9999.25
    depth_unit = _get(las.well, "DUL") or "m"

    depths = las.index
    start_depth = float(depths[0])  if len(depths) else None
    stop_depth  = float(depths[-1]) if len(depths) else None
    depth_steps = len(depths)

    curves = {}
    for curve in las.curves:
        name = curve.mnemonic.upper()
        data = np.array(curve.data, dtype=float)
        null_mask = np.isclose(data, null_value) | np.isnan(data)
        null_frac = float(null_mask.sum()) / max(len(data), 1)
        clean = data[~null_mask]
        issues = []

        flatline_intervals = _detect_flatlines(clean, depths[~null_mask], FLATLINE_WINDOW)
        if flatline_intervals:
            issues.append(f"Flatline detected in {len(flatline_intervals)} interval(s)")

        oor_frac = 0.0
        if name in CURVE_EXPECTED_RANGES and len(clean):
            lo, hi = CURVE_EXPECTED_RANGES[name]
            oor_frac = float(((clean < lo) | (clean > hi)).sum()) / len(clean)
            if oor_frac > 0.05:
                issues.append(f"{oor_frac*100:.1f}% values outside expected range [{lo},{hi}] {curve.unit}")

        if null_frac > NULL_FRACTION_WARN:
            issues.append(f"High null fraction: {null_frac*100:.1f}%")

        curves[name] = CurveQC(
            name=name, unit=curve.unit, present=True,
            null_fraction=null_frac,
            flatline_intervals=flatline_intervals,
            out_of_range_fraction=oor_frac,
            issues=issues,
            passed=len(issues) == 0
        )

    missing_required = [c for c in REQUIRED_CURVES if c not in curves]

    return LASParseResult(
        filename=filepath,
        well_name=str(well_name) if well_name else None,
        uwi=str(uwi) if uwi else None,
        operator=str(operator) if operator else None,
        rig_name=str(rig_name) if rig_name else None,
        start_depth=start_depth,
        stop_depth=stop_depth,
        depth_unit=depth_unit,
        depth_steps=depth_steps,
        null_value=null_value,
        curves=curves,
        missing_required=missing_required,
        header_dict={item.mnemonic: item.value for item in well}
    )


def _detect_flatlines(data: np.ndarray, depths: np.ndarray, window: int) -> list:
    """Return list of (start_depth, end_depth) tuples where values repeat >= window steps."""
    intervals = []
    if len(data) < window:
        return intervals
    i = 0
    while i < len(data) - window:
        block = data[i:i+window]
        if np.all(block == block[0]):
            j = i + window
            while j < len(data) and data[j] == block[0]:
                j += 1
            intervals.append((float(depths[i]), float(depths[j-1])))
            i = j
        else:
            i += 1
    return intervals
