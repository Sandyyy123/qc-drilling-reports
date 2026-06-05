"""
PDF parser for drilling daily reports and mudlog PDFs.
Extracts text, tables, well header fields using pdfplumber.
Falls back to OCR (PyMuPDF) when text layer is sparse.
"""
import re
import pdfplumber
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WellHeader:
    well_name: Optional[str] = None
    uwi: Optional[str] = None
    operator: Optional[str] = None
    rig_name: Optional[str] = None
    report_date: Optional[str] = None
    depth_md: Optional[float] = None
    mud_weight: Optional[float] = None
    total_gas: Optional[float] = None


@dataclass
class PDFParseResult:
    filename: str
    page_count: int
    text_coverage: float          # fraction of pages with extractable text
    full_text: str
    pages_text: list              # per-page text
    header: WellHeader
    has_footer: dict              # page_num -> bool
    tables_raw: list


_WELL_NAME_RE  = re.compile(r'(?:well\s*name|well)[:\s]+([A-Z0-9\-]{3,30})', re.I)
_UWI_RE        = re.compile(r'(?:uwi|api|unique\s*well)[:\s]+([0-9\-/W]{10,30})', re.I)
_OPERATOR_RE   = re.compile(r'operator[:\s]+([A-Za-z0-9 &.,]+?)(?:\n|$)', re.I)
_RIG_RE        = re.compile(r'rig[:\s]+([A-Za-z0-9 #\-]+?)(?:\n|$)', re.I)
_DATE_RE       = re.compile(r'(?:date|report\s*date)[:\s]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', re.I)
_DEPTH_RE      = re.compile(r'(?:depth|md|measured\s*depth|bit\s*depth)[:\s]+(\d[\d,.]+)\s*(?:m|ft)', re.I)
_MW_RE         = re.compile(r'(?:mud\s*weight|mw)[:\s]+(\d+\.\d+)\s*(?:g/cc|pcf|ppg)', re.I)
_TG_RE         = re.compile(r'total\s*gas[:\s]+(\d+\.?\d*)\s*(?:units|%|ppm|u)?', re.I)
_FOOTER_RE     = re.compile(r'(?:page\s*\d+|\d+\s*of\s*\d+|confidential|company\s*name)', re.I)


def parse_pdf(filepath: str) -> PDFParseResult:
    """Parse a daily report or mudlog PDF. Returns structured result."""
    pages_text = []
    has_footer = {}
    tables_raw = []

    with pdfplumber.open(filepath) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_text.append(text)
            has_footer[i + 1] = bool(_FOOTER_RE.search(text[-300:] if len(text) > 300 else text))
            tbls = page.extract_tables()
            if tbls:
                tables_raw.extend(tbls)

    full_text = "\n".join(pages_text)
    text_coverage = sum(1 for t in pages_text if len(t.strip()) > 50) / max(page_count, 1)

    # OCR fallback for low-coverage PDFs
    if text_coverage < 0.5:
        full_text, pages_text = _ocr_fallback(filepath, page_count)

    header = _extract_header(full_text)
    return PDFParseResult(
        filename=filepath,
        page_count=page_count,
        text_coverage=text_coverage,
        full_text=full_text,
        pages_text=pages_text,
        header=header,
        has_footer=has_footer,
        tables_raw=tables_raw,
    )


def _ocr_fallback(filepath: str, page_count: int):
    """Use PyMuPDF text extraction as fallback when pdfplumber coverage is low."""
    doc = fitz.open(filepath)
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text("text"))
    return "\n".join(pages_text), pages_text


def _extract_header(text: str) -> WellHeader:
    h = WellHeader()
    if m := _WELL_NAME_RE.search(text):   h.well_name  = m.group(1).strip()
    if m := _UWI_RE.search(text):         h.uwi        = m.group(1).strip()
    if m := _OPERATOR_RE.search(text):    h.operator   = m.group(1).strip()
    if m := _RIG_RE.search(text):         h.rig_name   = m.group(1).strip()
    if m := _DATE_RE.search(text):        h.report_date = m.group(1).strip()
    if m := _DEPTH_RE.search(text):       h.depth_md   = float(m.group(1).replace(',',''))
    if m := _MW_RE.search(text):          h.mud_weight  = float(m.group(1))
    if m := _TG_RE.search(text):          h.total_gas   = float(m.group(1))
    return h
