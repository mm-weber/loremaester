#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "r2r",
#   "pdfplumber",
#   "pypdfium2",
#   "pytesseract",
# ]
# ///
"""Bulk-ingest PDFs into R2R with sourcebook metadata.

Image-only and mixed PDFs are extracted client-side via `ocr_extract`'s
per-page hybrid (embedded text layer where present, pypdfium2-rendered
tesseract/easyocr where absent, plus figure-region OCR) to sidestep the
single-instance Unstructured container bottleneck. Text-native PDFs go
through R2R's native parsing so chunking metadata stays consistent.

OCR defaults to tesseract (CPU; needs only the system `tesseract` binary) —
robust, permissively licensed, dependency-light. Override via env:
    OCR_ENGINE    tesseract (default) | easyocr   (legacy KREUZBERG_OCR_ENGINE still honored)
    OCR_LANGUAGE  en (default). tesseract also accepts ISO 639-3 ("eng", "deu");
                  easyocr uses ISO 639-1 ("en", "de").

Set INGEST_DEBUG=1 to print a full traceback for each per-file failure
(otherwise failures are summarized to one line). For easyocr, a torch/CUDA
banner is printed up front so an empty-text result is diagnosable.

EasyOCR (GPU via torch+CUDA, sharper on noisy scans) is a heavier opt-in NOT in
this script's default deps — install it for the run with uv `--with` (it is
Apache-2.0; per-page OCR keeps it reliable):
    OCR_ENGINE=easyocr uv run --no-project --with easyocr --with 'torch==2.9.1+cu126' \\
        --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match \\
        scripts/ingest_books.py <folder>
(see docs/quickstart.md).
"""

import hashlib
import os
import sys
import tempfile
import traceback
from pathlib import Path

from r2r import R2RClient

from detect_pdf_type import analyze_pdf
from ocr_extract import extract_pdf, resolve_engine

R2R_BASE = "http://localhost:7272"
# OCR_ENGINE / OCR_LANGUAGE are canonical; the legacy KREUZBERG_* names are
# still honored as a fallback so older commands keep working.
OCR_ENGINE = os.environ.get("OCR_ENGINE", os.environ.get("KREUZBERG_OCR_ENGINE", "tesseract"))
OCR_LANGUAGE = os.environ.get("OCR_LANGUAGE", os.environ.get("KREUZBERG_OCR_LANGUAGE", "en"))


def file_sha1(path, chunk_size=1024 * 1024):
    """Full-file SHA1 digest. Streaming read so big PDFs don't blow memory."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def print_easyocr_diagnostics():
    """Print a torch/CUDA banner before easyocr runs.

    easyocr can finish without raising yet return no text — the usual cause is
    a GPU/runtime mismatch (e.g. the torch `cu126` wheel against an NVIDIA
    driver too old for CUDA 12.6). The extractor result alone doesn't reveal
    that, so surface the backend + device state up front. Best-effort: never
    let diagnostics abort the run.
    """
    if OCR_ENGINE != "easyocr":
        return
    print(f"easyocr diagnostics (language={OCR_LANGUAGE}):")
    try:
        import torch

        available = torch.cuda.is_available()
        print(
            f"  torch {torch.__version__} (built for CUDA {torch.version.cuda}); "
            f"torch.cuda.is_available()={available}"
        )
        if available:
            major, minor = torch.cuda.get_device_capability(0)
            arches = torch.cuda.get_arch_list()
            print(
                f"  GPU: {torch.cuda.get_device_name(0)} "
                f"(compute capability {major}.{minor} / sm_{major}{minor})"
            )
            print(f"  this torch wheel was built for: {arches}")

            # CUDA compatibility (NVIDIA's rules), so this doesn't false-alarm
            # on cards like the GTX 10-series:
            #  - sm_XY (SASS) runs on a device of the SAME major version with a
            #    minor <= the device's ("minor-version forward compat") — so a
            #    wheel with sm_60 DOES cover a 6.1 GPU.
            #  - compute_XY (PTX) JITs onto any device whose cc >= XY.
            # Only when nothing covers the device can CUDA kernels not run (then
            # easyocr tends to return empty text rather than raise).
            dev = (major, minor)

            def _cc(arch):
                tail = arch.rsplit("_", 1)[-1]
                return (int(tail) // 10, int(tail) % 10) if tail.isdigit() else None

            def _covers(arch):
                v = _cc(arch)
                if v is None:
                    return False
                if arch.startswith("sm_"):
                    return v[0] == dev[0] and v[1] <= dev[1]
                if arch.startswith("compute_"):
                    return v <= dev
                return False

            if not any(_covers(a) for a in arches):
                print(
                    f"  >> LIKELY CAUSE: this torch wheel has no kernels that run "
                    f"on sm_{major}{minor} (no matching sm_ SASS and no PTX that "
                    f"can JIT down), so easyocr's CUDA ops fail on your GPU — "
                    f"often silently, returning empty text. Fixes: use the "
                    f"default tesseract backend; force CPU with "
                    f"CUDA_VISIBLE_DEVICES=''; or install a torch build that "
                    f"covers sm_{major}{minor}."
                )
        else:
            print(
                "  >> No CUDA device visible. The cu126 wheel needs an NVIDIA "
                "driver new enough for CUDA 12.6; without one, easyocr can "
                "return empty text instead of erroring. Run `nvidia-smi` to "
                "check — or just use the default tesseract backend."
            )
    except Exception as e:
        print(f"  could not inspect torch: {type(e).__name__}: {e}")
    print()


def ingest_via_ocr(client, pdf_path, metadata):
    """Extract client-side with ocr_extract's per-page hybrid extract_pdf (embedded
    text layer where present, tesseract/easyocr where absent, plus figure-region OCR);
    ingest via a named temp .txt so R2R derives the title + default collection."""
    engine = resolve_engine(OCR_ENGINE)
    print(f"  Hybrid extract ({engine}): {pdf_path.name} — per-page (text layer where present, OCR + figure-region OCR where absent); this takes a while for big scans...")
    result = extract_pdf(str(pdf_path), engine=engine, language=OCR_LANGUAGE)
    with tempfile.TemporaryDirectory(prefix="ingest_books_") as tmp_dir:
        tmp_path = Path(tmp_dir) / f"{pdf_path.stem}.txt"
        tmp_path.write_text(result.content, encoding="utf-8")
        response = client.documents.create(file_path=str(tmp_path), metadata=metadata)
    doc_id = response.results.document_id
    print(f"  Ingested (OCR → {pdf_path.stem}.txt): {pdf_path.name} -> {doc_id}")
    return doc_id


def ingest_native(client, pdf_path, metadata):
    """Let R2R handle parsing via Unstructured."""
    response = client.documents.create(file_path=str(pdf_path), metadata=metadata)
    doc_id = response.results.document_id
    print(f"  Ingested (R2R native): {pdf_path.name} -> {doc_id}")
    return doc_id


def process_pdf(client, pdf):
    """Ingest one PDF; return 'succeeded' | 'skipped' | 'failed'.

    'skipped' = R2R already has this document (an idempotent re-run), detected
    by the 'already exists' message in R2R's rejection — not a real failure.
    """
    book_title = pdf.stem.replace("_", " ").replace("-", " ").title()
    metadata = {"book_title": book_title}
    print(f"[{book_title}]")
    try:
        if analyze_pdf(str(pdf)).classification == "text-native":
            ingest_native(client, pdf, metadata)
        else:
            ingest_via_ocr(client, pdf, metadata)
        return "succeeded"
    except Exception as e:
        if "already exists" in str(e):
            print(f"  SKIPPED: {pdf.name} — already in R2R")
            return "skipped"
        print(f"  FAILED: {pdf.name} — {type(e).__name__}: {e}")
        if os.environ.get("INGEST_DEBUG"):
            traceback.print_exc()
        return "failed"


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
    # subdirectory (/library/foo.pdf and /library/boxed-sets/foo.pdf) AND the
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

    print_easyocr_diagnostics()

    buckets = {"succeeded": [], "skipped": [], "failed": []}
    for pdf in pdfs:
        buckets[process_pdf(client, pdf)].append(pdf.name)

    print(
        f"\nDone. {len(buckets['succeeded'])} succeeded, "
        f"{len(buckets['skipped'])} skipped, {len(buckets['failed'])} failed."
    )
    if buckets["skipped"]:
        print("Skipped (already in R2R — re-run is idempotent):")
        for name in buckets["skipped"]:
            print(f"  - {name}")
    if buckets["failed"]:
        print("Failed files:")
        for name in buckets["failed"]:
            print(f"  - {name}")

    if OCR_ENGINE == "easyocr":
        print(
            "\nNote: easyocr/torch may print 'terminate called ...' as the "
            "process exits. That is a known native-teardown artifact (CUDA / "
            "thread-pool destructors at shutdown), not an ingestion error — the "
            "summary above is authoritative."
        )


if __name__ == "__main__":
    main()
