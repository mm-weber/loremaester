# Track Registry

Registry of all development tracks. Each track is a distinct body of work with its own spec and plan.

## Status Legend
| Symbol | Status | Description |
| --- | --- | --- |
| `[ ]` | Pending | Not yet started |
| `[~]` | In Progress | Currently being worked on |
| `[x]` | Completed | Finished and verified |

## Active Tracks

_None currently in progress._

---

## Completed Tracks

### [x] ocr-hybrid-routing_20260607: OCR routing — per-page hybrid + region-targeted figure OCR
**Description:** Per-page hybrid (text-layer + OCR) for image-only & mixed PDFs; region-targeted figure OCR; easyocr→tesseract fallback. text-native stays on R2R native. TDD-built (routing rewired to the 3-tier classifier, dead `is_image_pdf` removed; 88 unit tests green). **Completed 2026-06-07.**
**Folder:** [./tracks/ocr-hybrid-routing_20260607/](./tracks/ocr-hybrid-routing_20260607/)

### [x] idempotent-ingest_20260607: Idempotent ingest — skip already-ingested PDFs
**Description:** R2R "already exists" is now reported as SKIPPED (not FAILED) on re-runs; summary counts succeeded/skipped/failed (TDD-built; 4 unit tests). **Completed 2026-06-07.**
**Folder:** [./tracks/idempotent-ingest_20260607/](./tracks/idempotent-ingest_20260607/)

### [x] remove-kreuzberg_20260606: Remove kreuzberg — permissive, per-page OCR pipeline
**Description:** Replaced kreuzberg with a direct `pypdfium2` + per-page `tesseract`/`easyocr` OCR pipeline (TDD-built; 20 unit tests). **Completed 2026-06-06.**
**Folder:** [./tracks/remove-kreuzberg_20260606/](./tracks/remove-kreuzberg_20260606/)

## Archived Tracks
| Track ID | Type | Reason | Archived | Folder |
| -------- | ---- | ------ | -------- | ------ |

## Notes
- Track IDs: lowercase-hyphen + `_YYYYMMDD`.
- See `requirements/v0.2/requirements_v0.2.md` R-1 / R-1E for the kreuzberg evidence.
