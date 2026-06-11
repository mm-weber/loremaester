# Third-Party Notices

**Loremaester** is released under the MIT License (see
[`LICENSE`](LICENSE)). It does **not** vendor third-party source code — it *orchestrates and
depends on* the components below, each governed by its own license. This file documents those
components so users can comply with the relevant terms.

> Any usage restriction noted below applies to **that component**, not to this project's own
> MIT-licensed code. If you redistribute or host this project, review these terms — especially
> the **MinIO (AGPL-3.0)** entry.

## Core dependencies

### R2R — MIT License
- Upstream: <https://github.com/SciPhi-AI/R2R> (SciPhi AI)
- Role: retrieval engine — embeddings, vector search, document ingestion. Used via the `r2r`
  Python SDK and the `sciphiai/r2r` Docker image.
- Terms: MIT — permissive, no usage restrictions.

### Client-side OCR — all permissive (MIT / Apache-2.0 / BSD)
Image-only PDFs are OCR'd client-side by `scripts/ocr_extract.py` (used by `scripts/ingest_books.py`
and `scripts/extract_text.py`): each page is rendered with **pypdfium2** and OCR'd per page with
**tesseract** (default) or **easyocr** (GPU opt-in). None of this is required for the core product —
image PDFs can instead be OCR'd server-side by R2R/Unstructured.io in Docker Full Mode.
- pypdfium2 — Apache-2.0 / BSD-3 (pdfium) — <https://github.com/pypdfium2-team/pypdfium2>
- Tesseract / pytesseract — Apache-2.0 — <https://github.com/tesseract-ocr/tesseract>
- EasyOCR — Apache-2.0 (GPU opt-in) — <https://github.com/JaidedAI/EasyOCR>
- PyTorch (`torch`, pulled by the EasyOCR opt-in) — BSD-3-Clause — <https://github.com/pytorch/pytorch>

> **Removed during v0.1 prep:** the earlier `kreuzberg` OCR wrapper (Elastic License 2.0,
> source-available) was dropped — it was both a functional liability (multi-page EasyOCR returned
> empty text) and a non-permissive dependency. The OCR stack is now fully permissive. History:
> `specs/v0.2/specs_v0.2.md` (R-1 / R-1E) and Conductor track `remove-kreuzberg_20260606`.

The one-off `scripts/ocr_preprocess.py` helper (NOT on the default ingest path) instead uses
`pdf2image` (MIT — requires the system **poppler** tool, GPL) with `pytesseract`/`surya`; surya is
copyleft — consult its upstream if you use that helper.

### Other Python libraries
Permissively-licensed libraries used directly: `mcp` (Model Context Protocol SDK), `pdfplumber`,
`pydantic`, `pyyaml`, `pytest` / `pytest-asyncio`. Consult each project for its exact license.

## Docker images (orchestrated at runtime — pulled as-is, not modified or redistributed)
The Compose stack (`docker/compose.full.yaml`, `compose.app.yaml`) pulls these images unchanged.
Each is governed by its own upstream license; consult the upstream for authoritative terms:

| Image / component | License (per upstream) | Upstream |
|---|---|---|
| `sciphiai/r2r`, `sciphiai/r2r-dashboard` | MIT | <https://github.com/SciPhi-AI/R2R> |
| PostgreSQL + `pgvector` | PostgreSQL License | <https://github.com/pgvector/pgvector> |
| MinIO | **AGPL-3.0** (network-use copyleft) | <https://github.com/minio/minio> |
| Hatchet | MIT | <https://github.com/hatchet-dev/hatchet> |
| RabbitMQ | MPL-2.0 | <https://github.com/rabbitmq/rabbitmq-server> |
| Unstructured.io | Apache-2.0 (core) | <https://github.com/Unstructured-IO/unstructured> |

## Models
- `mxbai-embed-large` (embeddings, served via Ollama) — consult the model card for its license.

---
*This attribution reflects the dependencies at the time of writing. If you change pinned versions
(e.g. `torch` for the EasyOCR opt-in), re-check the corresponding license.*
