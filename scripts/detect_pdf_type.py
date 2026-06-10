# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pdfplumber",
# ]
# ///
"""Detect whether a PDF is text-native, image-only, or mixed."""

import sys
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass
class PdfReport:
    filename: str
    classification: str
    total_pages: int
    text_pages: int


def analyze_pdf(path: str) -> PdfReport:
    """Analyze a PDF file and return a classification report."""
    with pdfplumber.open(path) as pdf:
        total_pages = len(pdf.pages)
        text_pages = 0
        for page in pdf.pages:
            text = page.extract_text()
            if text and len(text) >= 50:
                text_pages += 1
    classification = classify_pdf_pages(text_pages, total_pages)
    return PdfReport(Path(path).name, classification, total_pages, text_pages)


def format_report(report: PdfReport) -> str:
    """Format a PdfReport as a human-readable string."""
    return (
        f"{report.filename}: {report.classification}\n"
        f"  {report.text_pages} of {report.total_pages} pages have extractable text"
    )


def classify_pdf_pages(text_pages: int, total_pages: int) -> str:
    """Classify a PDF based on the ratio of text pages to total pages."""
    if text_pages / total_pages >= 0.9:
        return "text-native"
    if text_pages / total_pages <= 0.1:
        return "image-only"
    return "mixed"


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: detect_pdf_type.py <pdf_file_or_directory> [...]", file=sys.stderr
        )
        sys.exit(1)
    for arg in sys.argv[1:]:
        target = Path(arg)
        paths = target.glob("*.pdf") if target.is_dir() else [target]
        for pdf_path in paths:
            report = analyze_pdf(str(pdf_path))
            print(format_report(report))


if __name__ == "__main__":
    main()
