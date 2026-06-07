# Implementation Plan: Remove kreuzberg — permissive, per-page OCR pipeline

**Track ID:** remove-kreuzberg_20260606
**Spec:** [spec.md](./spec.md)
**Created:** 2026-06-06
**Status:** [ ] Not Started

## Overview
Introduce a shared, kreuzberg-free OCR module (`scripts/ocr_extract.py`) that renders with
`pypdfium2` and OCRs **per page** (tesseract default, easyocr GPU opt-in), then rewire the two
kreuzberg consumers, update tests and docs, and drop the dependency.

## Progress Summary
| Phase | Status | Progress |
| ----- | ------ | -------- |
| Phase 1: Shared OCR module | [x] Complete | 100% |
| Phase 2: Rewire ingest_books.py | [x] Complete | 100% |
| Phase 3: Rewire extract_text.py + tests | [ ] Not started | 0% |
| Phase 4: Docs, licenses, cleanup | [ ] Not started | 0% |

## Phase 1: Shared OCR module
Create `scripts/ocr_extract.py` — `ocr_pdf(path, engine="tesseract", language="eng", page_range=None)`.
Per-page by construction (never hands the whole document to one OCR call).

### Tasks
- [x] 1.1 Render pages via `pypdfium2` — `render_pages` (`RENDER_SCALE` ≈200 dpi, `page_range` support). (RED/GREEN-5)
- [x] 1.2 Per-page OCR: tesseract (`image_to_string` + dict-based confidence) and easyocr (one reused `Reader`, `readtext` per page). (RED/GREEN-2, -3)
- [x] 1.3 `ocr_pdf` orchestration: per-page loop, `[Page N]` concat in order, confidence aggregation (mean + low-confidence pages). (RED/GREEN-1, -4)
- [x] 1.4 Robustness: actionable `RuntimeError` for missing pypdfium2/tesseract/easyocr; document-identifying error when all pages OCR empty. (RED/GREEN-6, -7)
- [x] 1.5 (done in Phase 2) Diagnostics resolved: kept `print_easyocr_diagnostics` (torch/CUDA banner) in `ingest_books.py`; removed the kreuzberg-only `describe_extraction`.

### Verification
- [x] `python3 -m pytest scripts/test_ocr_extract.py -q` → **7 passed**; per-page proven (ocr_image called once per page; easyocr `Reader` built once).
- [x] Module imports + tests run without numpy/pandas/kreuzberg/tesseract/easyocr installed (all mocked); `py_compile` clean.
- [ ] Owner end-to-end (deferred to track end): real `uv run` on Vol III — tesseract ingests; easyocr per-page on the GTX 1060 (GPU memory across 16 pages).

### Checkpoint
`[remove-kreuzberg_20260606] checkpoint: phase 1 complete`

## Phase 2: Rewire ingest_books.py
### Tasks
- [x] 2.1 Replaced `ingest_via_kreuzberg` with `ingest_via_ocr` (calls `ocr_extract.ocr_pdf`); kept `is_image_pdf`, SHA1 dedup, temp-`.txt` `file_path` ingest; removed kreuzberg-only `describe_extraction`. (RED/GREEN P2-1 + cleanup)
- [x] 2.2 PEP 723: dropped `kreuzberg`; added `pypdfium2`, `pytesseract`; `easyocr`/`torch` remain `--with` opt-ins.
- [x] 2.3 Env: `OCR_ENGINE`/`OCR_LANGUAGE` canonical (legacy `KREUZBERG_*` honored as fallback); dropped `KREUZBERG_OCR_MODEL_TIER`.

### Verification
- [x] `python3 -m pytest scripts/test_ingest_books.py scripts/test_ocr_extract.py -q` → 8 passed; `import kreuzberg` / `ingest_via_kreuzberg` / `describe_extraction` gone from `ingest_books.py` (only the legacy `KREUZBERG_*` env-fallback strings remain).
- [ ] Owner end-to-end (deferred to track end): real `uv run` — tesseract ingests all 4 books incl. Vol III (image-only).

### Checkpoint
`[remove-kreuzberg_20260606] checkpoint: phase 2 complete`

## Phase 3: Rewire extract_text.py + tests
### Tasks
- [ ] 3.1 Replace `_do_extract` (kreuzberg, ~lines 22-29, 53-57) with `ocr_extract.ocr_pdf`; update
      PEP 723 deps; keep the argparse interface (`--engine`, `--language`, `--output`, `--ingest`, `--title`).
- [ ] 3.2 `test_extract_text.py`: mock `ocr_extract`; replace `test_kreuzberg_not_installed` with a backend-missing test.
- [ ] 3.3 Add `scripts/test_ocr_extract.py` mirroring `test_ocr_preprocess.py`.

### Verification
- [ ] `python -m pytest -q scripts/` green with `kreuzberg` NOT installed.

### Checkpoint
`[remove-kreuzberg_20260606] checkpoint: phase 3 complete`

## Phase 4: Docs, licenses, cleanup
### Tasks
- [ ] 4.1 Rewrite OCR sections: `docs/quickstart.md` (69-83, 324-340, 379-423),
      `docs/troubleshooting.md` (53-103), `docs/demo-walkthrough.md` (65, 111),
      `README.md` (78, 140), `docs/design.md` (136-138).
- [ ] 4.2 Update `THIRD_PARTY_LICENSES.md` (remove kreuzberg; list tesseract/easyocr/pypdfium2 as
      direct, permissive deps).
- [ ] 4.3 Cross-reference this track from `requirements/v0.2/requirements_v0.2.md` R-1; delete the moot
      `examples/ttrpg/sourcebooks/Grunvyr-Vol-III-fixedcover.pdf` **if present** (a local scratch artifact
      from the diagnostic script — NOT the `Grunvyr-Vol-III-ImageOnly.pdf` fixture, which stays).

### Verification
- [ ] `git grep -n kreuzberg` → no matches in `scripts/` + `docs/` (only the v0.2 evidence retains it, as history).

### Checkpoint
`[remove-kreuzberg_20260606] checkpoint: phase 4 complete (track done)`

## Final Verification
- [ ] All spec acceptance criteria met.
- [ ] tesseract: all books ingest; easyocr (per-page) OCRs Vol III — **owner validates** the 16-page GPU run on the GTX 1060.
- [ ] Test suite green without `kreuzberg`/`tesseract`/`easyocr`/`poppler`.
- [ ] Docs + licenses kreuzberg-free.

---
_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
