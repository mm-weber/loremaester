#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["r2r", "pdfplumber", "kreuzberg", "paddleocr", "paddlepaddle-gpu"]
# ///
"""Bulk-ingest PDFs into R2R with sourcebook metadata.

Routes image-heavy PDFs through Kreuzberg (host-side OCR) to sidestep the
single-instance Unstructured container bottleneck. Text-native PDFs still
go through R2R's native parsing so chunking metadata stays consistent.

OCR engine / language can be overridden via env:
    KREUZBERG_OCR_ENGINE   tesseract (default) | easyocr | paddleocr
    KREUZBERG_OCR_LANGUAGE eng (default) — Kreuzberg language code
"""

import os
import sys
from pathlib import Path

from r2r import R2RClient

R2R_BASE = "http://localhost:7272"
# <10% of pages with extractable text => treat as scanned/image-only
IMAGE_ONLY_THRESHOLD = 0.1
OCR_ENGINE = os.environ.get("KREUZBERG_OCR_ENGINE", "paddleocr")
OCR_LANGUAGE = os.environ.get("KREUZBERG_OCR_LANGUAGE", "eng")


def is_image_pdf(pdf_path):
    """Return True if <10% of pages in the PDF have extractable text."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        if total == 0:
            return False
        with_text = sum(1 for p in pdf.pages if (p.extract_text() or "").strip())
        return (with_text / total) < IMAGE_ONLY_THRESHOLD


def ingest_via_kreuzberg(client, pdf_path, metadata):
    """OCR client-side with Kreuzberg, ingest extracted text as raw_text."""
    from kreuzberg import ExtractionConfig, OcrConfig, extract_file_sync

    print(f"  OCR (kreuzberg, {OCR_ENGINE}): {pdf_path.name} — this takes a while for big scans...")
    config = ExtractionConfig(ocr=OcrConfig(backend=OCR_ENGINE, language=OCR_LANGUAGE))
    result = extract_file_sync(str(pdf_path), config=config)
    if not result.content.strip():
        raise RuntimeError(f"kreuzberg returned empty text for {pdf_path.name}")

    response = client.documents.create(raw_text=result.content, metadata=metadata)
    doc_id = response.results.document_id
    print(f"  Ingested (kreuzberg → raw_text): {pdf_path.name} -> {doc_id}")
    return doc_id


def ingest_native(client, pdf_path, metadata):
    """Let R2R handle parsing via Unstructured."""
    response = client.documents.create(file_path=str(pdf_path), metadata=metadata)
    doc_id = response.results.document_id
    print(f"  Ingested (R2R native): {pdf_path.name} -> {doc_id}")
    return doc_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest_books.py <folder_of_pdfs>")
        sys.exit(1)

    pdf_dir = Path(sys.argv[1])
    client = R2RClient(R2R_BASE)

    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) in {pdf_dir}\n")

    succeeded = []
    failed = []

    for pdf in pdfs:
        book_title = pdf.stem.replace("_", " ").replace("-", " ").title()
        metadata = {"book_title": book_title}

        print(f"[{book_title}]")
        try:
            if is_image_pdf(pdf):
                ingest_via_kreuzberg(client, pdf, metadata)
            else:
                ingest_native(client, pdf, metadata)
            succeeded.append(pdf.name)
        except Exception as e:
            print(f"  FAILED: {pdf.name} — {e}")
            failed.append(pdf.name)

    print(f"\nDone. {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed files:")
        for name in failed:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
