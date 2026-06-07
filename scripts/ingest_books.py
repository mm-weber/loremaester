#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "r2r",
#   "pdfplumber",
#   "kreuzberg>=4.5.0",
# ]
# ///
"""Bulk-ingest PDFs into R2R with sourcebook metadata.

Routes image-heavy PDFs through Kreuzberg (host-side OCR) to sidestep the
single-instance Unstructured container bottleneck. Text-native PDFs still
go through R2R's native parsing so chunking metadata stays consistent.

OCR defaults to tesseract (CPU; needs only the system `tesseract` binary) —
robust and dependency-light. Override the backend/language via env:
    KREUZBERG_OCR_ENGINE    tesseract (default) | easyocr | paddleocr
    KREUZBERG_OCR_LANGUAGE  en (default; "eng" also works for tesseract).
                            ISO 639-1 (en, de) for easyocr/paddleocr;
                            ISO 639-3 (eng, deu) for tesseract.

Set INGEST_DEBUG=1 to print a full traceback for each per-file failure
(otherwise failures are summarized to one line). For easyocr, a torch/CUDA
banner is printed up front so an empty-text result is diagnosable.

The neural backends are heavier opt-ins and are NOT in this script's default
deps — install them for the run with uv `--with`. EasyOCR (GPU via torch+CUDA,
sharper on noisy scans): set KREUZBERG_OCR_ENGINE=easyocr and add
`--with 'kreuzberg[easyocr]>=4.5.0' --with 'torch==2.9.1+cu126'` plus the
PyTorch cu126 index flags (see docs/quickstart.md). PaddleOCR: add
`--with 'kreuzberg[paddleocr]'` (+ paddlepaddle from its own index).
"""

import hashlib
import os
import sys
import tempfile
import traceback
from pathlib import Path

from r2r import R2RClient

from ocr_extract import ocr_pdf

R2R_BASE = "http://localhost:7272"
# <10% of pages with extractable text => treat as scanned/image-only
IMAGE_ONLY_THRESHOLD = 0.1
OCR_ENGINE = os.environ.get("KREUZBERG_OCR_ENGINE", "tesseract")
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


def describe_extraction(result):
    """Schema-tolerant one-line summary of a kreuzberg result, for diagnostics.

    Used when OCR returns no text: report what the backend *did* see (raw
    length, page/table/chunk counts, metadata) so 'empty result' is
    distinguishable from 'never processed a page'. All lookups are defensive
    so a result-schema change can't turn diagnostics into a second failure.
    """
    bits = [f"raw_len={len(getattr(result, 'content', '') or '')}"]
    for attr in ("tables", "chunks", "images"):
        value = getattr(result, attr, None)
        if value is not None:
            try:
                bits.append(f"{attr}={len(value)}")
            except TypeError:
                bits.append(f"{attr}=present")
    metadata = getattr(result, "metadata", None)
    if metadata is not None:
        bits.append((f"metadata={metadata!r}")[:200])
    return "; ".join(bits)


def ingest_via_ocr(client, pdf_path, metadata):
    """OCR client-side with ocr_extract (pypdfium2 + per-page tesseract/easyocr);
    ingest via a named temp .txt so R2R derives the title + default collection."""
    print(f"  OCR ({OCR_ENGINE}): {pdf_path.name} — per-page; this takes a while for big scans...")
    result = ocr_pdf(str(pdf_path), engine=OCR_ENGINE, language=OCR_LANGUAGE)
    with tempfile.TemporaryDirectory(prefix="ingest_books_") as tmp_dir:
        tmp_path = Path(tmp_dir) / f"{pdf_path.stem}.txt"
        tmp_path.write_text(result.content, encoding="utf-8")
        response = client.documents.create(file_path=str(tmp_path), metadata=metadata)
    doc_id = response.results.document_id
    print(f"  Ingested (OCR → {pdf_path.stem}.txt): {pdf_path.name} -> {doc_id}")
    return doc_id


def ingest_via_kreuzberg(client, pdf_path, metadata):
    """OCR client-side with Kreuzberg; ingest via a named temp .txt.

    We intentionally write the extracted text to a temp file and use
    `file_path=` instead of `raw_text=`. R2R only derives the document
    title from the filename and only auto-assigns the user's default
    collection on the file-path code path — both are lost if we pass
    raw_text directly.
    """
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
        raise RuntimeError(
            f"kreuzberg ({OCR_ENGINE}) returned empty text for {pdf_path.name} "
            f"[{describe_extraction(result)}] — the OCR backend ran without "
            f"raising but produced no text. For easyocr this usually means a "
            f"GPU/torch problem (see the diagnostics banner above); the same "
            f"PDF will typically OCR with the default tesseract backend."
        )

    # Temp .txt named after the PDF stem so R2R stamps title="<stem>.txt"
    # and assigns the doc to the user's default collection.
    with tempfile.TemporaryDirectory(prefix="ingest_books_") as tmp_dir:
        tmp_path = Path(tmp_dir) / f"{pdf_path.stem}.txt"
        tmp_path.write_text(result.content, encoding="utf-8")
        response = client.documents.create(file_path=str(tmp_path), metadata=metadata)
    doc_id = response.results.document_id
    print(f"  Ingested (kreuzberg → {pdf_path.stem}.txt): {pdf_path.name} -> {doc_id}")
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
            print(f"  FAILED: {pdf.name} — {type(e).__name__}: {e}")
            if os.environ.get("INGEST_DEBUG"):
                traceback.print_exc()
            failed.append(pdf.name)

    print(f"\nDone. {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed files:")
        for name in failed:
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
