# Track Registry

Registry of all development tracks. Each track is a distinct body of work with its own spec and plan.

## Status Legend
| Symbol | Status | Description |
| --- | --- | --- |
| `[ ]` | Pending | Not yet started |
| `[~]` | In Progress | Currently being worked on |
| `[x]` | Completed | Finished and verified |

## Active Tracks

### [~] idempotent-ingest_20260607: Idempotent ingest — skip already-ingested PDFs
**Description:** Treat R2R "already exists" as SKIPPED (not FAILED) on re-runs; report succeeded/skipped/failed separately.
**Priority:** Medium
**Folder:** [./tracks/idempotent-ingest_20260607/](./tracks/idempotent-ingest_20260607/)

---

## Completed Tracks

### [x] remove-kreuzberg_20260606: Remove kreuzberg — permissive, per-page OCR pipeline
**Description:** Replaced kreuzberg with a direct `pypdfium2` + per-page `tesseract`/`easyocr` OCR pipeline (TDD-built; 20 unit tests). **Completed 2026-06-06.**
**Folder:** [./tracks/remove-kreuzberg_20260606/](./tracks/remove-kreuzberg_20260606/)

## Archived Tracks
| Track ID | Type | Reason | Archived | Folder |
| -------- | ---- | ------ | -------- | ------ |

## Notes
- Track IDs: lowercase-hyphen + `_YYYYMMDD`.
- See `requirements/v0.2/requirements_v0.2.md` R-1 / R-1E for the kreuzberg evidence.
