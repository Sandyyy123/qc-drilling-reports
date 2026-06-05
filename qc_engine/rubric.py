"""
QC rubric engine: 34 checks applied to parsed PDF and LAS results.
Returns a list of Finding objects with severity, category, description, and action.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    FAIL   = "FAIL"
    WARN   = "WARN"
    REVIEW = "REVIEW"
    PASS   = "PASS"


@dataclass
class Finding:
    check_id: str
    category: str
    severity: Severity
    title: str
    description: str
    files_affected: list
    action: Optional[str] = None
    field_value_a: Optional[str] = None
    field_value_b: Optional[str] = None


def run_rubric(daily_result=None, log_result=None, las_result=None) -> list:
    """Run all applicable QC checks given parsed file results. Returns list of Finding."""
    findings = []

    # --- Cross-file checks (require at least 2 files) ---
    if daily_result and las_result:
        findings += _check_uwi_consistency(daily_result, las_result)
        findings += _check_well_name_consistency(daily_result, las_result)
        findings += _check_depth_consistency(daily_result, las_result)

    if daily_result and log_result:
        findings += _check_mud_weight_consistency(daily_result, log_result)
        findings += _check_date_consistency(daily_result, log_result)
        findings += _check_footer_coverage(log_result)

    # --- Single-file daily report checks ---
    if daily_result:
        findings += _check_required_daily_fields(daily_result)
        findings += _check_total_gas_present(daily_result)
        findings += _check_zeroed_rop(daily_result)
        findings += _check_well_name_daily(daily_result)

    # --- LAS checks ---
    if las_result:
        findings += _check_required_curves(las_result)
        findings += _check_las_curve_quality(las_result)
        findings += _check_las_header_fields(las_result)

    return findings


# ---------- check implementations ----------

def _check_uwi_consistency(daily, las):
    da = daily.header.uwi
    la = las.uwi
    if da and la:
        if da.strip() != la.strip():
            return [Finding(
                check_id="CROSS-001", category="Well Info Consistency",
                severity=Severity.FAIL,
                title="UWI mismatch between daily report and LAS header",
                description=f"Daily report UWI: {da}. LAS header UWI: {la}.",
                files_affected=[daily.filename, las.filename],
                action="Verify correct UWI in survey data; correct whichever file is wrong.",
                field_value_a=da, field_value_b=la
            )]
        return [Finding(check_id="CROSS-001", category="Well Info Consistency",
                        severity=Severity.PASS, title="UWI consistent across files",
                        description="UWI matches in daily report and LAS header.",
                        files_affected=[daily.filename, las.filename])]
    return []


def _check_well_name_consistency(daily, las):
    da = daily.header.well_name
    la = las.well_name
    if da and la:
        if da.upper().strip() != la.upper().strip():
            return [Finding(check_id="CROSS-002", category="Well Info Consistency",
                            severity=Severity.FAIL,
                            title="Well name mismatch across files",
                            description=f"Daily: {da} | LAS: {la}",
                            files_affected=[daily.filename, las.filename],
                            action="Reconcile well name; all files must match exactly.")]
        return [Finding(check_id="CROSS-002", category="Well Info Consistency",
                        severity=Severity.PASS, title="Well name consistent",
                        description=f"Well name '{da}' matches in all files.",
                        files_affected=[daily.filename, las.filename])]
    return []


def _check_depth_consistency(daily, las):
    dd = daily.header.depth_md
    ld = las.stop_depth
    if dd and ld:
        diff = abs(dd - ld)
        if diff > 5:
            return [Finding(check_id="CROSS-003", category="Depth / Date Continuity",
                            severity=Severity.WARN,
                            title=f"Depth discrepancy between daily report and LAS ({diff:.1f} m)",
                            description=f"Daily report MD: {dd} m. LAS stop depth: {ld} m.",
                            files_affected=[daily.filename, las.filename],
                            action="Confirm which depth is authoritative; note any back-drilling.")]
        return [Finding(check_id="CROSS-003", category="Depth / Date Continuity",
                        severity=Severity.PASS, title="Depth consistent across files",
                        description=f"Daily MD ({dd} m) and LAS stop depth ({ld} m) agree within 5 m.",
                        files_affected=[daily.filename, las.filename])]
    return []


def _check_mud_weight_consistency(daily, log):
    da = daily.header.mud_weight
    la = log.header.mud_weight
    if da and la:
        diff = abs(da - la)
        if diff > 0.03:
            return [Finding(check_id="CROSS-004", category="Drilling Parameters",
                            severity=Severity.REVIEW,
                            title=f"Mud weight discrepancy: daily={da} g/cc vs log header={la} g/cc",
                            description="Difference exceeds 0.03 g/cc threshold.",
                            files_affected=[daily.filename, log.filename],
                            action="Supervisor to confirm authoritative value and annotate discrepancy.")]
    return []


def _check_date_consistency(daily, log):
    dd = daily.header.report_date
    ld = log.header.report_date
    if dd and ld and dd.strip() != ld.strip():
        return [Finding(check_id="CROSS-005", category="Depth / Date Continuity",
                        severity=Severity.FAIL,
                        title="Report date mismatch between daily report and final log",
                        description=f"Daily: {dd} | Log: {ld}",
                        files_affected=[daily.filename, log.filename],
                        action="Correct date in whichever file has the error.")]
    return []


def _check_footer_coverage(log):
    if not log.has_footer:
        return []
    missing_pages = [p for p, has in log.has_footer.items() if not has]
    total = len(log.has_footer)
    if missing_pages:
        pct = len(missing_pages) / total * 100
        sev = Severity.FAIL if pct > 20 else Severity.WARN
        return [Finding(check_id="LOG-001", category="Header / Footer Consistency",
                        severity=sev,
                        title=f"Footer absent on {len(missing_pages)} of {total} pages ({pct:.0f}%)",
                        description=f"Pages without footer: {missing_pages[:10]}{'...' if len(missing_pages)>10 else ''}",
                        files_affected=[log.filename],
                        action="Re-export PDF from logging software; confirm footer on all pages.")]
    return [Finding(check_id="LOG-001", category="Header / Footer Consistency",
                    severity=Severity.PASS, title="Footer present on all log pages",
                    description="", files_affected=[log.filename])]


def _check_required_daily_fields(daily):
    findings = []
    required = {"well_name": "Well name", "report_date": "Report date",
                "depth_md": "Measured depth", "operator": "Operator"}
    for attr, label in required.items():
        val = getattr(daily.header, attr, None)
        if val is None:
            findings.append(Finding(
                check_id=f"DAILY-{attr.upper()}", category="Required Fields Present",
                severity=Severity.FAIL,
                title=f"Missing required field: {label}",
                description=f"Could not extract '{label}' from daily report.",
                files_affected=[daily.filename],
                action=f"Ensure '{label}' appears in the report header in a standard format."))
        else:
            findings.append(Finding(check_id=f"DAILY-{attr.upper()}", category="Required Fields Present",
                                    severity=Severity.PASS, title=f"{label} present",
                                    description=str(val), files_affected=[daily.filename]))
    return findings


def _check_total_gas_present(daily):
    if daily.header.total_gas is None:
        return [Finding(check_id="DAILY-TG", category="Gas / Drilling Parameters",
                        severity=Severity.FAIL,
                        title="Total Gas field absent from daily report",
                        description="No Total Gas value found in gas section. Required field.",
                        files_affected=[daily.filename],
                        action="Back-calculate TG from component gases or retrieve from mud log.")]
    return [Finding(check_id="DAILY-TG", category="Gas / Drilling Parameters",
                    severity=Severity.PASS, title="Total Gas present",
                    description=f"TG = {daily.header.total_gas}", files_affected=[daily.filename])]


def _check_zeroed_rop(daily):
    # Heuristic: look for "0.0" repeated in tables (drilling param rows)
    zero_count = daily.full_text.count("0.0") + daily.full_text.count("0.00")
    if zero_count > 10:
        return [Finding(check_id="DAILY-ROP", category="Gas / Drilling Parameters",
                        severity=Severity.WARN,
                        title="Possible zeroed drilling parameter values detected",
                        description=f"Found {zero_count} zero values in report text. Check ROP/WOB/RPM columns.",
                        files_affected=[daily.filename],
                        action="Review drilling parameter table; add operations notes for any zero-ROP periods.")]
    return []


def _check_well_name_daily(daily):
    if not daily.header.well_name:
        return [Finding(check_id="DAILY-WNAME", category="Well Info Consistency",
                        severity=Severity.FAIL,
                        title="Well name not found in daily report header",
                        description="Could not extract well name from report.",
                        files_affected=[daily.filename],
                        action="Ensure well name is in standard header position.")]
    return []


def _check_required_curves(las):
    if las.missing_required:
        return [Finding(check_id="LAS-CURVES", category="LAS Curve Availability",
                        severity=Severity.FAIL,
                        title=f"Missing required LAS curves: {', '.join(las.missing_required)}",
                        description="Required curves not found in CURVE section.",
                        files_affected=[las.filename],
                        action="Deliver complete LAS with all required curves; check logging program coverage.")]
    return [Finding(check_id="LAS-CURVES", category="LAS Curve Availability",
                    severity=Severity.PASS, title="All required LAS curves present",
                    description=f"Curves present: {', '.join(las.curves.keys())}",
                    files_affected=[las.filename])]


def _check_las_curve_quality(las):
    findings = []
    for name, cqc in las.curves.items():
        if cqc.issues:
            sev = Severity.FAIL if any("Flatline" in i or "out of range" in i for i in cqc.issues) else Severity.WARN
            findings.append(Finding(
                check_id=f"LAS-{name}", category="LAS Curve Quality",
                severity=sev,
                title=f"Curve {name}: {len(cqc.issues)} issue(s)",
                description=" | ".join(cqc.issues),
                files_affected=[las.filename],
                action="Investigate sensor data; splice corrected data or flag bad intervals."))
        else:
            findings.append(Finding(check_id=f"LAS-{name}", category="LAS Curve Quality",
                                    severity=Severity.PASS,
                                    title=f"Curve {name} passed all checks",
                                    description=f"Unit: {cqc.unit}", files_affected=[las.filename]))
    return findings


def _check_las_header_fields(las):
    findings = []
    for attr, label in [("well_name","Well name"),("uwi","UWI"),("operator","Operator")]:
        val = getattr(las, attr)
        if not val:
            findings.append(Finding(check_id=f"LAS-HDR-{attr.upper()}",
                                    category="Required Fields Present",
                                    severity=Severity.WARN,
                                    title=f"LAS ~WELL section missing: {label}",
                                    description="",
                                    files_affected=[las.filename],
                                    action=f"Populate {label} in LAS ~WELL section."))
        else:
            findings.append(Finding(check_id=f"LAS-HDR-{attr.upper()}",
                                    category="Required Fields Present",
                                    severity=Severity.PASS,
                                    title=f"LAS header {label} present: {val}",
                                    description="", files_affected=[las.filename]))
    return findings
