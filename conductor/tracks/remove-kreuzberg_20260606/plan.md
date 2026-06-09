# Implementation Plan: Remove kreuzberg — permissive, per-page OCR pipeline

**Track ID:** remove-kreuzberg_20260606
**Spec:** [spec.md](./spec.md)
**Created:** 2026-06-06
**Status:** [x] Complete

## Overview
Introduce a shared, kreuzberg-free OCR module (`scripts/ocr_extract.py`) that renders with
`pypdfium2` and OCRs **per page** (tesseract default, easyocr GPU opt-in), then rewire the two
kreuzberg consumers, update tests and docs, and drop the dependency.

## Progress Summary
| Phase | Status | Progress |
| ----- | ------ | -------- |
| Phase 1: Shared OCR module | [x] Complete | 100% |
| Phase 2: Rewire ingest_books.py | [x] Complete | 100% |
| Phase 3: Rewire extract_text.py + tests | [x] Complete | 100% |
| Phase 4: Docs, licenses, cleanup | [x] Complete | 100% |

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
- [x] 3.1 `_do_extract` delegates to `ocr_extract.ocr_pdf`; removed the kreuzberg import block; PEP 723 deps kreuzberg → pypdfium2 + pytesseract; argparse `--engine` choices = tesseract|easyocr (dropped paddleocr); kept `--language`/`--output`/`--ingest`/`--title`. (RED/GREEN P3-1 + cleanup)
- [x] 3.2 `test_extract_text.py`: replaced `test_kreuzberg_not_installed` with `test_missing_backend_reported` (asserts the actionable RuntimeError surfaces); the 11 other tests (which mock `_do_extract`) are unaffected.
- [x] 3.3 `scripts/test_ocr_extract.py` — already created in Phase 1 (7 tests).

### Verification
- [x] `python3 -m pytest scripts/test_extract_text.py scripts/test_ingest_books.py scripts/test_ocr_extract.py -q` → **20 passed**; `kreuzberg` gone from `extract_text.py`. (Full `pytest scripts/` still errors collecting the pre-existing `test_ocr_preprocess.py`, which needs pandas — absent in this sandbox; unrelated to this track.)
- [ ] Owner end-to-end (deferred to track end): real `uv run` OCR with tesseract (and the easyocr opt-in).

### Checkpoint
`[remove-kreuzberg_20260606] checkpoint: phase 3 complete`

## Phase 4: Docs, licenses, cleanup
### Tasks
- [x] 4.1 OCR sections rewritten across `docs/quickstart.md`, `docs/troubleshooting.md`, `docs/demo-walkthrough.md`, `README.md`, `docs/design.md` → ocr_extract (pypdfium2 + per-page tesseract/easyocr); easyocr opt-in `--with easyocr`; `OCR_ENGINE` env (legacy `KREUZBERG_*` honored); paddleocr dropped. (3 parallel doc agents)
- [x] 4.2 `THIRD_PARTY_NOTICES.md`: removed the kreuzberg (Elastic-2.0) entry; OCR stack now listed as direct permissive deps (pypdfium2 / tesseract / pytesseract / easyocr / torch) + a "removed" note.
- [x] 4.3 Cross-referenced the track from `specs/v0.2` R-1 (marked ✅ DONE); `Grunvyr-Vol-III-fixedcover.pdf` is not in the repo (was a local scratch file) — nothing to delete. Added `ocr_extract.py` to the README/design file-trees.

### Verification
- [x] `git grep -niE kreuzberg -- scripts/ docs/` → only intentional refs remain (legacy `KREUZBERG_*` env fallback + `ocr_extract`'s "kreuzberg-free" explanatory comments); no imports, install commands, or "via kreuzberg" framing.

### Checkpoint
`[remove-kreuzberg_20260606] checkpoint: phase 4 complete (track done)`

## Final Verification
- [x] All spec acceptance criteria met (24 EARS criteria in spec.md — verified by the 20 unit tests + the kreuzberg sweep).
- [ ] tesseract: all books ingest; easyocr (per-page) OCRs Vol III — **owner validates** the real `uv run` + the 16-page GPU run on the GTX 1060. (Only step needing hardware; can't run in this sandbox.)
- [x] Test suite green without `kreuzberg`/`tesseract`/`easyocr`/`poppler` installed — 20 passed (all backends mocked).
- [x] Docs + licenses kreuzberg-free (only intentional legacy-fallback + history references remain).

---
_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
