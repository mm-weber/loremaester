# extract_text.py — Standalone Image/Document Text Extraction Tool

> **Status:** Specification
> **Date:** 2026-03-20

---

## Purpose

Extract text from JPEG and other image documents using kreuzberg OCR. Optionally ingest extracted text into R2R for semantic search.

## Usage

```bash
python scripts/extract_text.py <file>...
python scripts/extract_text.py --output result.txt <file>...
python scripts/extract_text.py --ingest --title "Document Name" <file>...
python scripts/extract_text.py --engine paddleocr --language deu <file>...
```

## Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Accept one or more file paths as positional arguments | Must |
| FR-2 | Extract text from each file using `kreuzberg.extract_file_sync()` | Must |
| FR-3 | Print extracted text to stdout (default mode) | Must |
| FR-4 | `--output FILE` writes extracted text to a file instead of stdout | Must |
| FR-5 | `--ingest` pushes extracted text into R2R via `R2RClient.documents.create(raw_text=...)` | Must |
| FR-6 | `--title TEXT` sets document title for R2R metadata (default: filename stem, title-cased) | Must |
| FR-7 | `--engine ENGINE` selects OCR backend: `tesseract` (default), `easyocr`, `paddleocr` | Should |
| FR-8 | `--language LANG` sets OCR language (default: `eng`) | Should |
| FR-9 | Multiple files: process sequentially, separate output with `--- filename ---` headers | Must |
| FR-10 | Exit code 0 on success, 1 on any extraction failure | Must |
| FR-11 | Print extraction confidence score to stderr when available | Should |

## Supported Input Formats

- **Primary:** JPEG, PNG (the immediate use case)
- **Also works:** BMP, TIFF, WebP, GIF, PDF, DOCX, and anything kreuzberg supports
- No artificial format restriction — kreuzberg handles format detection

## Error Handling

| Condition | Behavior |
|---|---|
| File not found | Print error to stderr, skip file, continue with remaining files, exit code 1 |
| OCR extraction fails | Print error to stderr, skip file, continue, exit code 1 |
| kreuzberg not installed | Print install instructions to stderr, exit code 1 |
| `--ingest` but R2R unavailable | Print connection error to stderr, text still printed to stdout, exit code 1 |
| No files provided | Print usage help, exit code 2 |

## Dependencies

- `kreuzberg` (required)
- `tesseract-ocr` system package (required for the default engine)
- `r2r` SDK (required only when `--ingest` is used)

**Per-backend extras.** Kreuzberg bundles tesseract support out of the
box, but the other backends are opt-in:

- `--engine easyocr` → install `kreuzberg[easyocr]`, which pulls in
  `easyocr` and `torch`. GPU-accelerated if CUDA is available; see
  `docs/troubleshooting.md` for the torch cu126 pin used by
  `ingest_books.py`.
- `--engine paddleocr` → install `paddleocr` and `paddlepaddle-gpu`
  (the latter lives on PaddlePaddle's own index, not PyPI). Useful
  for languages where EasyOCR struggles; otherwise stick with the
  default.

## Output Format

**Multiple files (stdout):**
```
--- image1.jpeg ---
[extracted text from image1]

--- image2.png ---
[extracted text from image2]
```

**Single file (stdout):**
```
[extracted text — no header, just the text]
```

## Test Plan

| Test | Description |
|---|---|
| test_extract_single_jpeg | Extract text from a JPEG with known text content, verify non-empty output |
| test_extract_multiple_files | Process 2+ files, verify separator headers and per-file output |
| test_output_to_file | `--output` writes text to specified file path |
| test_ingest_calls_r2r | `--ingest` calls R2RClient.documents.create with correct raw_text and metadata |
| test_title_default | Without `--title`, metadata uses filename stem title-cased |
| test_title_override | `--title "Custom"` overrides metadata title |
| test_engine_selection | `--engine easyocr` passes correct backend to kreuzberg config |
| test_language_selection | `--language deu` passes correct language to OCR config |
| test_missing_file | Missing file prints error to stderr, returns exit code 1 |
| test_no_args | No arguments prints usage, returns exit code 2 |
| test_kreuzberg_not_installed | ImportError handled gracefully with install instructions |
