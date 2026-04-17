#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "r2r",
#   "pdfplumber",
#   "kreuzberg[easyocr]>=4.5.0",
#   "torch==2.9.1+cu126",
# ]
# ///
"""Bulk-ingest PDFs into R2R with sourcebook metadata.

Routes image-heavy PDFs through Kreuzberg (host-side OCR) to sidestep the
single-instance Unstructured container bottleneck. Text-native PDFs still
go through R2R's native parsing so chunking metadata stays consistent.

OCR engine / language can be overridden via env:
    KREUZBERG_OCR_ENGINE    easyocr (default, GPU via torch+CUDA) | tesseract (CPU only) | paddleocr
    KREUZBERG_OCR_LANGUAGE  en (default) — Kreuzberg language code. Two-letter
                            (ISO 639-1) for easyocr/paddleocr, three-letter
                            (ISO 639-3, e.g. "eng") for tesseract.

PaddleOCR note — the paddleocr backend requires extra deps not pinned here
(paddleocr + paddlepaddle-gpu from the PaddlePaddle index). Tesseract is
CPU-only; there is no GPU build. For GPU OCR, stick with easyocr.
"""

import hashlib
import os
import sys
from pathlib import Path

from r2r import R2RClient

R2R_BASE = "http://localhost:7272"
# <10% of pages with extractable text => treat as scanned/image-only
IMAGE_ONLY_THRESHOLD = 0.1
OCR_ENGINE = os.environ.get("KREUZBERG_OCR_ENGINE", "easyocr")
OCR_LANGUAGE = os.environ.get("KREUZBERG_OCR_LANGUAGE", "en")
# Only consulted when OCR_ENGINE == "paddleocr". "server" = ~172 MB GPU-optimized;
# "mobile" = ~21 MB CPU. Kreuzberg defaults to "mobile" otherwise.
OCR_MODEL_TIER = os.environ.get("KREUZBERG_OCR_MODEL_TIER", "server")


def file_sha1(path, chunk_size=1024 * 1024):
    """Full-file SHA1 digest. Streaming read so big PDFs don't blow memory."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


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

    ocr_kwargs = {"backend": OCR_ENGINE, "language": OCR_LANGUAGE}
    if OCR_ENGINE == "paddleocr":
        # PaddleOcrConfig isn't registered as a pyo3 class in kreuzberg 4.8.x
        # despite the .pyi stub — the kwarg is serde-deserialized, so pass a dict.
        ocr_kwargs["paddle_ocr_config"] = {"model_tier": OCR_MODEL_TIER}
        tier_suffix = f", tier={OCR_MODEL_TIER}"
    else:
        tier_suffix = ""

    print(f"  OCR (kreuzberg, {OCR_ENGINE}{tier_suffix}): {pdf_path.name} — this takes a while for big scans...")
    config = ExtractionConfig(ocr=OcrConfig(**ocr_kwargs))
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

    all_pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not all_pdfs:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)

    # Dedupe by SHA1 content hash. Catches the same book mirrored in a
    # subdirectory (/library/foo.pdf and /library/Planescape/foo.pdf) AND the
    # same bytes under different filenames. First occurrence in sort order
    # wins; later copies are logged and skipped.
    print(f"Found {len(all_pdfs)} PDF path(s) in {pdf_dir}. Hashing for dedup...")
    seen_hashes = {}  # sha1 -> Path (the kept copy)
    pdfs = []
    dupes = []  # list of (dupe_path, original_path)
    for pdf in all_pdfs:
        sha = file_sha1(pdf)
        if sha in seen_hashes:
            dupes.append((pdf, seen_hashes[sha]))
            continue
        seen_hashes[sha] = pdf
        pdfs.append(pdf)

    print(f"  {len(pdfs)} unique book(s).")
    if dupes:
        print(f"Skipping {len(dupes)} duplicate(s) (same SHA1 as the kept copy):")
        for dupe, original in dupes:
            print(f"  - {dupe.relative_to(pdf_dir)}  (same content as {original.relative_to(pdf_dir)})")
    print()

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
