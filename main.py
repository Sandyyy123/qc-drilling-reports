#!/usr/bin/env python3
"""
DrillingQC Pro - QC Engine CLI
Usage:
  python main.py --daily DailyReport.pdf [--log FinalLog.pdf] [--las WELL.las] [--out qc_report.json]
"""
import argparse
import json
import sys
from pathlib import Path

from qc_engine.parsers.pdf_parser import parse_pdf
from qc_engine.parsers.las_parser import parse_las
from qc_engine.rubric import run_rubric, Severity
from qc_engine.scorer import compute_score


def main():
    parser = argparse.ArgumentParser(description="DrillingQC Pro - Automated report validator")
    parser.add_argument("--daily", help="Daily report PDF path")
    parser.add_argument("--log",   help="1-inch or 5-inch final log PDF path")
    parser.add_argument("--las",   help="LAS file path")
    parser.add_argument("--out",   help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    if not any([args.daily, args.log, args.las]):
        parser.print_help()
        sys.exit(1)

    daily_result = parse_pdf(args.daily) if args.daily else None
    log_result   = parse_pdf(args.log)   if args.log   else None
    las_result   = parse_las(args.las)   if args.las   else None

    findings = run_rubric(daily_result, log_result, las_result)
    score_data = compute_score(findings)

    # Build structured output
    output = {
        "qc_score": score_data["overall"],
        "pass_label": score_data["pass_label"],
        "summary": score_data["counts"],
        "category_scores": score_data["category_scores"],
        "findings": [
            {
                "check_id": f.check_id,
                "category": f.category,
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description,
                "files_affected": f.files_affected,
                "action": f.action,
            }
            for f in findings
        ],
        "files_processed": {
            "daily_report": {"path": args.daily, "pages": daily_result.page_count,
                             "text_coverage": round(daily_result.text_coverage, 3)} if daily_result else None,
            "final_log":    {"path": args.log,   "pages": log_result.page_count,
                             "text_coverage": round(log_result.text_coverage, 3)} if log_result else None,
            "las_file":     {"path": args.las, "depth_steps": las_result.depth_steps,
                             "curves": list(las_result.curves.keys())} if las_result else None,
        }
    }

    # Print summary to console
    print(f"\n=== DrillingQC Pro ===")
    print(f"QC Score: {score_data['overall']}/100  ({score_data['pass_label']})")
    counts = score_data["counts"]
    print(f"PASS: {counts.get('PASS',0)}  WARN: {counts.get('WARN',0)}  FAIL: {counts.get('FAIL',0)}  REVIEW: {counts.get('REVIEW',0)}")
    print()

    failures = [f for f in findings if f.severity == Severity.FAIL]
    if failures:
        print("--- FAILURES (must fix before submission) ---")
        for f in failures:
            print(f"  [{f.check_id}] {f.title}")
            if f.action:
                print(f"    Action: {f.action}")
    print()

    result_json = json.dumps(output, indent=2)
    if args.out:
        Path(args.out).write_text(result_json)
        print(f"Full report saved to: {args.out}")
    else:
        print(result_json)


if __name__ == "__main__":
    main()
