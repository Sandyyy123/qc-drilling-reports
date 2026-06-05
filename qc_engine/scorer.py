"""
QC score calculator. Weights categories and computes 0-100 score.
"""
from .rubric import Finding, Severity

CATEGORY_WEIGHTS = {
    "Well Info Consistency":      0.20,
    "Required Fields Present":    0.18,
    "Header / Footer Consistency":0.12,
    "Depth / Date Continuity":    0.12,
    "LAS Curve Availability":     0.12,
    "LAS Curve Quality":          0.12,
    "Gas / Drilling Parameters":  0.14,
}
SEVERITY_PENALTY = {Severity.FAIL: 1.0, Severity.WARN: 0.4, Severity.REVIEW: 0.2, Severity.PASS: 0.0}


def compute_score(findings: list) -> dict:
    """Return dict with overall score, per-category scores, and counts."""
    category_findings = {}
    for f in findings:
        category_findings.setdefault(f.category, []).append(f)

    category_scores = {}
    for cat, cat_findings in category_findings.items():
        total = len(cat_findings)
        penalty = sum(SEVERITY_PENALTY[f.severity] for f in cat_findings)
        raw = max(0, (total - penalty) / total) if total else 1.0
        category_scores[cat] = round(raw * 100, 1)

    # Weighted overall score
    total_weight = 0.0
    weighted_sum = 0.0
    for cat, weight in CATEGORY_WEIGHTS.items():
        if cat in category_scores:
            weighted_sum += category_scores[cat] * weight
            total_weight += weight
    for cat, score in category_scores.items():
        if cat not in CATEGORY_WEIGHTS:
            weighted_sum += score * 0.02
            total_weight += 0.02

    overall = round(weighted_sum / total_weight, 1) if total_weight else 0.0

    counts = {s.value: sum(1 for f in findings if f.severity == s) for s in Severity}
    return {
        "overall": overall,
        "pass_label": _label(overall),
        "category_scores": category_scores,
        "counts": counts,
    }


def _label(score: float) -> str:
    if score >= 90: return "Pass"
    if score >= 75: return "Conditional Pass"
    if score >= 60: return "Requires Correction"
    return "Reject - Resubmit"
