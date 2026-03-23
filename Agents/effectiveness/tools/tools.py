"""
tools/tools.py

Individual extraction tool functions for CAPA Evidence Extraction.

Each function is a standalone tool responsible for one file format.
Called by evidence_extractor.py dispatcher.

Tools:
  - extract_pdf_digital        : pdfplumber for text-based PDFs
  - extract_pdf_ocr_tesseract  : Tesseract OCR for scanned PDFs
  - extract_docx               : python-docx for Word documents
  - extract_xlsx               : openpyxl for Excel files
  - extract_json               : built-in json for JSON files
  - extract_csv                : pandas for CSV files
  - extract_txt                : built-in decode for plain text

Installation:
  pip install pdfplumber pytesseract pdf2image pillow python-docx openpyxl pandas

  System:
    sudo apt install tesseract-ocr poppler-utils   # Linux
    brew install tesseract poppler                 # macOS
"""

import io
import json
import pdfplumber
import pytesseract
import pandas as pd
from PIL import Image
from pdf2image import convert_from_bytes
from docx import Document
from openpyxl import load_workbook
import logging

logger = logging.getLogger("effectiveness_agent")

# Tesseract config:
#   --oem 3 : LSTM neural net engine (highest accuracy)
#   --psm 6 : Assume uniform block of text (best for document pages)
TESSERACT_CONFIG = "--oem 3 --psm 6"


# ── Tool 1: PDF Digital Extraction ──────────────────────────────────────────

def extract_pdf_digital(file_bytes: bytes) -> str:
    """
    Tool: extract_pdf_digital

    Extracts text from digitally created PDFs using pdfplumber.

    Works for:
      - QMS-generated reports exported to PDF
      - Word/Excel documents saved as PDF
      - Electronic lab records, audit reports

    Does NOT work for:
      - Scanned physical documents (image-based PDFs)
      - Handwritten forms photographed as PDF

    Returns:
      Extracted plain text. Empty string if PDF is image-based.
    """
    extracted_parts = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"[TOOL:PDF-DIGITAL] Processing {total_pages} page(s)...")

        for page_num, page in enumerate(pdf.pages, 1):

            # Extract body text
            page_text = page.extract_text()
            if page_text and page_text.strip():
                extracted_parts.append(f"[Page {page_num}]\n{page_text.strip()}")

            # Extract tables (lab result tables, EM data grids, training logs)
            tables = page.extract_tables()
            for table_idx, table in enumerate(tables, 1):
                table_rows = []
                for row in table:
                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                    row_text  = " | ".join(filter(None, clean_row))
                    if row_text.strip():
                        table_rows.append(row_text)

                if table_rows:
                    extracted_parts.append(
                        f"[Page {page_num} - Table {table_idx}]\n" +
                        "\n".join(table_rows)
                    )

    result = "\n\n".join(extracted_parts)
    logger.info(f"[TOOL:PDF-DIGITAL] Extracted {len(result)} chars.")
    return result


# ── Tool 2: PDF OCR via Tesseract ────────────────────────────────────────────

def extract_pdf_ocr_tesseract(file_bytes: bytes) -> str:
    """
    Tool: extract_pdf_ocr_tesseract

    Extracts text from scanned PDFs using Tesseract OCR (open source, local).

    How it works:
      1. pdf2image converts each PDF page to a high-res PIL Image (300 DPI)
      2. PIL converts image to grayscale for better OCR accuracy
      3. pytesseract runs Tesseract LSTM engine on each page image
      4. Text from all pages is merged and returned

    Why Tesseract:
      - 100% open source (Apache 2.0 license)
      - Fully local — no cloud calls, no API keys, no cost
      - GxP air-gap compatible
      - Supports 100+ languages via tessdata packs

    Works for:
      - Scanned lab reports, physical inspection forms
      - Legacy paper-based CAPA records scanned to PDF
      - Printed environmental monitoring logs

    Limitations:
      - No native table structure (plain text only from scanned images)
      - Lower accuracy on handwriting vs printed text
      - Requires poppler (system dep) for pdf2image

    Returns:
      OCR-extracted plain text from all pages.
    """
    extracted_parts = []

    logger.info("[TOOL:TESSERACT] Converting PDF pages to images (300 DPI)...")

    # Convert all PDF pages to PIL Images at 300 DPI
    # 300 DPI is the minimum recommended for reliable OCR on printed text
    pages = convert_from_bytes(
        file_bytes,
        dpi=300,
        fmt="PNG"
    )

    logger.info(f"[TOOL:TESSERACT] {len(pages)} page(s) ready for OCR.")

    for page_num, page_image in enumerate(pages, 1):

        # Convert to grayscale — removes color noise, improves Tesseract accuracy
        gray_image = page_image.convert("L")

        # Run Tesseract OCR
        page_text = pytesseract.image_to_string(
            gray_image,
            config=TESSERACT_CONFIG,
            lang="eng"  # swap to "eng+fra" etc. for multilingual documents
        )

        if page_text.strip():
            extracted_parts.append(f"[Page {page_num}]\n{page_text.strip()}")
            logger.info(
                f"[TOOL:TESSERACT] Page {page_num}: {len(page_text.strip())} chars extracted."
            )
        else:
            logger.warning(
                f"[TOOL:TESSERACT] Page {page_num}: No text detected — "
                f"check image quality or DPI."
            )

    result = "\n\n".join(extracted_parts)
    logger.info(f"[TOOL:TESSERACT] OCR complete. Total: {len(result)} chars.")
    return result


# ── Tool 3: DOCX Extraction ──────────────────────────────────────────────────

def extract_docx(file_bytes: bytes) -> str:
    """
    Tool: extract_docx

    Extracts text from Microsoft Word (.docx) documents using python-docx.

    Captures:
      - All body paragraphs (headings, descriptions, findings)
      - Table cell content (common in CAPA reports, deviation logs)

    Works for:
      - CAPA action plan documents
      - SOP revision summaries
      - Inspection observation reports

    Returns:
      Plain text with paragraphs and table rows joined by newlines.
    """
    doc   = Document(io.BytesIO(file_bytes))
    parts = []

    # Body paragraphs
    para_count = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)
            para_count += 1

    # Table content
    table_count = 0
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(
                cell.text.strip()
                for cell in row.cells
                if cell.text.strip()
            )
            if row_text:
                parts.append(row_text)
                table_count += 1

    result = "\n".join(parts)
    logger.info(
        f"[TOOL:DOCX] Extracted {para_count} paragraphs, "
        f"{table_count} table rows, {len(result)} total chars."
    )
    return result


# ── Tool 4: XLSX Extraction ──────────────────────────────────────────────────

def extract_xlsx(file_bytes: bytes) -> str:
    """
    Tool: extract_xlsx

    Extracts cell data from Excel (.xlsx / .xls) files using openpyxl.

    Captures:
      - All sheets in the workbook
      - All non-empty cell values per row
      - Sheet name as section header

    Works for:
      - Environmental monitoring data grids
      - Training completion matrices
      - Water testing result logs
      - Multi-sheet audit tracking spreadsheets

    Returns:
      Plain text with sheet sections and pipe-delimited row values.
    """
    wb    = load_workbook(io.BytesIO(file_bytes), data_only=True)
    parts = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        parts.append(f"[Sheet: {sheet_name}]")

        row_count = 0
        for row in ws.iter_rows(values_only=True):
            row_values = [
                str(cell).strip()
                for cell in row
                if cell is not None and str(cell).strip()
            ]
            if row_values:
                parts.append(" | ".join(row_values))
                row_count += 1

        logger.info(f"[TOOL:XLSX] Sheet '{sheet_name}': {row_count} rows extracted.")

    result = "\n".join(parts)
    logger.info(f"[TOOL:XLSX] Total: {len(result)} chars across {len(wb.sheetnames)} sheet(s).")
    return result


# ── Tool 5: JSON Extraction ──────────────────────────────────────────────────

def extract_json(file_bytes: bytes) -> str:
    """
    Tool: extract_json

    Parses a JSON file and flattens all key-value pairs to readable text.
    Handles nested dicts and lists recursively.

    Works for:
      - QMS API exports (structured test results)
      - Instrument data exports in JSON format
      - Training database exports

    Returns:
      Flattened key: value lines joined by newlines.
    """
    data   = json.loads(file_bytes.decode("utf-8"))
    result = _flatten_json(data)
    logger.info(f"[TOOL:JSON] Flattened JSON to {len(result)} chars.")
    return result


def _flatten_json(obj, prefix: str = "") -> str:
    """Recursively flatten nested JSON object to key: value lines."""
    lines = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            lines.append(_flatten_json(value, prefix=full_key))

    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            full_key = f"{prefix}[{idx}]"
            lines.append(_flatten_json(item, prefix=full_key))

    else:
        lines.append(f"{prefix}: {obj}")

    return "\n".join(filter(None, lines))


# ── Tool 6: CSV Extraction ───────────────────────────────────────────────────

def extract_csv(file_bytes: bytes) -> str:
    """
    Tool: extract_csv

    Extracts rows from CSV files — handles two formats:

    Format A — Clean uniform CSV (single header row, consistent columns):
      Standard export from QMS, lab instrument, or database.
      Parsed with pandas normally.

    Format B — Multi-section CSV (section headers, blank rows, uneven columns):
      Evidence reports with multiple tables in one file.
      e.g. "SECTION 1: CA-01 ...", blank rows between sections,
      varying column counts per section.
      Parsed line-by-line to avoid pandas tokenization errors.

    Auto-detects which format to use based on column consistency.

    Returns:
      Plain text with all rows and section headers preserved.
    """
    raw_text = file_bytes.decode("utf-8", errors="replace")
    lines    = raw_text.splitlines()

    # ── Auto-detect format ────────────────────────────────────────────────────
    # Count commas per non-empty line — if highly inconsistent = multi-section
    comma_counts = [
        line.count(",")
        for line in lines
        if line.strip()
    ]

    if comma_counts:
        min_commas = min(comma_counts)
        max_commas = max(comma_counts)
        is_multi_section = (max_commas - min_commas) > 2
    else:
        is_multi_section = False

    # ── Format B: Multi-section line-by-line parser ───────────────────────────
    if is_multi_section:
        logger.info("[TOOL:CSV] Multi-section format detected — using line-by-line parser.")
        parts      = []
        row_count  = 0

        for line in lines:
            stripped = line.strip()

            # Skip fully empty lines
            if not stripped:
                continue

            # Clean up the line — split by comma, strip each cell
            cells = [cell.strip() for cell in stripped.split(",")]

            # Remove trailing empty cells
            while cells and not cells[-1]:
                cells.pop()

            if not cells:
                continue

            # Join non-empty cells with pipe separator
            row_text = " | ".join(cells)
            parts.append(row_text)
            row_count += 1

        result = "\n".join(parts)
        logger.info(
            f"[TOOL:CSV] Multi-section extracted {row_count} rows, "
            f"{len(result)} total chars."
        )
        return result

    # ── Format A: Clean uniform CSV — pandas parser ───────────────────────────
    logger.info("[TOOL:CSV] Uniform format detected — using pandas parser.")
    try:
        df    = pd.read_csv(io.BytesIO(file_bytes))
        parts = []

        parts.append(f"Columns: {', '.join(df.columns.tolist())}")
        parts.append(f"Total Rows: {len(df)}")
        parts.append("")

        for _, row in df.iterrows():
            row_text = " | ".join(
                f"{col}={val}"
                for col, val in row.items()
                if pd.notna(val) and str(val).strip()
            )
            if row_text:
                parts.append(row_text)

        result = "\n".join(parts)
        logger.info(
            f"[TOOL:CSV] Uniform extracted {len(df)} rows, "
            f"{len(df.columns)} columns, {len(result)} total chars."
        )
        return result

    except Exception as e:
        # Pandas failed even on detected uniform format — fall back to line-by-line
        logger.warning(
            f"[TOOL:CSV] Pandas parse failed ({str(e)}) — "
            f"falling back to line-by-line parser."
        )
        parts     = []
        row_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            cells    = [c.strip() for c in stripped.split(",") if c.strip()]
            row_text = " | ".join(cells)
            if row_text:
                parts.append(row_text)
                row_count += 1
        result = "\n".join(parts)
        logger.info(f"[TOOL:CSV] Fallback extracted {row_count} rows.")
        return result


# ── Tool 7: TXT Extraction ───────────────────────────────────────────────────

def extract_txt(file_bytes: bytes) -> str:
    """
    Tool: extract_txt

    Decodes a plain text file to string.

    Works for:
      - Raw instrument output logs
      - Simple evidence notes exported as .txt
      - Analyst observation text files

    Returns:
      Decoded plain text string.
    """
    result = file_bytes.decode("utf-8", errors="replace").strip()
    logger.info(f"[TOOL:TXT] Decoded {len(result)} chars from text file.")
    return result