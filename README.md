> **⚠️ Proprietary — All Rights Reserved.** © 2026 Sandeep Grover. This repository is licensed to Sandeep Grover and may **not** be used, run, copied, modified, distributed, or used to train models without prior written permission. Public visibility does not grant a license. See [LICENSE](LICENSE).

---

# DrillingQC Pro - Automated Report Validation Engine

Automated QC tool for oil & gas field reports. Parses daily report PDFs, mudlog PDFs, and LAS files; applies a rubric of 34+ checks; flags deficiencies; and generates a scored structured output for crew correction and supervisor review.

## Architecture

```
+------------------+     +------------------+     +-------------------+
|   Daily Report   |     |  5-inch Final    |     |    LAS File       |
|   PDF Upload     | --> |  Log PDF Upload  | --> |  Upload           |
+------------------+     +------------------+     +-------------------+
         |                        |                        |
         v                        v                        v
+-----------------------------------------------------------+
|              Extraction Layer                             |
|  pdfplumber (text) + PyMuPDF (OCR fallback) + lasio      |
+-----------------------------------------------------------+
         |
         v
+-----------------------------------------------------------+
|              QC Rubric Engine (34 checks)                  |
|  - Cross-file: UWI, well name, depth, mud weight, date    |
|  - Daily report: required fields, total gas, zeroed ROP   |
|  - LAS: required curves, flatlines, nulls, unit labels    |
|  - Log: footer coverage, header consistency               |
+-----------------------------------------------------------+
         |
         v
+-----------------------------------------------------------+
|           Scorer + Structured Output                       |
|  QC Score (0-100), PASS/WARN/FAIL/REVIEW per finding      |
|  JSON deficiency report -> React dashboard (Milestone 2)   |
+-----------------------------------------------------------+
```

## Quick Start

```bash
pip install -r requirements.txt

# Run QC on all three file types
python main.py --daily DailyReport_Jun4.pdf --log FinalLog.pdf --las WELL.las --out qc_report.json

# Daily report only
python main.py --daily DailyReport_Jun4.pdf --out qc_report.json

# LAS file only
python main.py --las WELL.las
```

## QC Checks Implemented

| Category | Check | Severity |
|----------|-------|----------|
| Cross-file | UWI consistency (daily vs LAS) | FAIL if mismatch |
| Cross-file | Well name consistency | FAIL if mismatch |
| Cross-file | Depth discrepancy (>5 m) | WARN |
| Cross-file | Mud weight discrepancy (>0.03 g/cc) | REVIEW |
| Cross-file | Report date mismatch | FAIL |
| Final Log | Footer absent from pages | FAIL/WARN |
| Daily Report | Missing required fields (well name, date, depth, operator) | FAIL |
| Daily Report | Total Gas field absent | FAIL |
| Daily Report | Zeroed drilling parameters | WARN |
| LAS | Missing required curves (GR, RHOB, NPHI, DT, RT, CALI) | FAIL |
| LAS | Curve flatlines (>=10 consecutive identical values) | FAIL |
| LAS | High null fraction (>20%) | WARN |
| LAS | Values outside expected range | WARN |
| LAS | Header fields missing (UWI, operator) | WARN |

## Output Format

```json
{
  "qc_score": 74.0,
  "pass_label": "Conditional Pass",
  "summary": {"PASS": 22, "WARN": 6, "FAIL": 4, "REVIEW": 2},
  "category_scores": {"Well Info Consistency": 60.0, ...},
  "findings": [
    {
      "check_id": "CROSS-001",
      "category": "Well Info Consistency",
      "severity": "FAIL",
      "title": "UWI mismatch between daily report and LAS header",
      "description": "...",
      "action": "Verify UWI in survey data..."
    }
  ]
}
```

## Roadmap

- **Milestone 1 (current):** QC engine + structured JSON output
- **Milestone 2:** React upload UI + Supabase auth + crew deficiency review interface
- **Milestone 3:** Supervisor dashboard, report history, low-score triage, PDF export

## Tech Stack

- `pdfplumber` - PDF text and table extraction
- `PyMuPDF (fitz)` - OCR fallback for image-heavy PDFs
- `lasio` - LAS 1.2 / 2.0 parsing
- `pandas` / `numpy` - LAS data analysis
- `FastAPI` - REST API wrapper (Milestone 2)
- `React` - Dashboard UI (Milestone 2)
- `Supabase` - Auth, file storage, report history (Milestone 2)

## Author

Dr. Sandeep Grover - Python / Data Engineering / PDF & LAS parsing specialist
