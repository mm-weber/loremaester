# Third-Party Licenses & Attribution

The **Worldbuilding Assistant for Claude Code** is released under the MIT License (see
[`LICENSE`](LICENSE)). It does **not** vendor third-party source code — it *orchestrates and
depends on* the components below, each governed by its own license. This file documents those
components so users can comply with the relevant terms.

> Any usage restriction noted below applies to **that component**, not to this project's own
> MIT-licensed code. If you redistribute or host this project, review these terms — especially
> the **kreuzberg (Elastic License 2.0)** and **MinIO (AGPL-3.0)** entries.

## Core dependencies

### R2R — MIT License
- Upstream: <https://github.com/SciPhi-AI/R2R> (SciPhi AI)
- Role: retrieval engine — embeddings, vector search, document ingestion. Used via the `r2r`
  Python SDK and the `sciphiai/r2r` Docker image.
- Terms: MIT — permissive, no usage restrictions.

### kreuzberg — Elastic License 2.0 (ELv2) — *optional dependency*
- Upstream: <https://github.com/kreuzberg-dev/kreuzberg> (kreuzberg-dev)
- Role: **optional** client-side OCR for image-only PDFs (default backend: EasyOCR). Used by
  `scripts/ingest_books.py` and `scripts/extract_text.py`. It is **not** required for the core
  product — image PDFs can instead be OCR'd server-side by R2R/Unstructured.io in Docker Full Mode.
- Terms: **Elastic License 2.0 — source-available, NOT OSI open-source.** ELv2 notably forbids
  providing the software to third parties as a hosted/managed service and forbids removing or
  obscuring its licensing notices. See <https://www.elastic.co/licensing/elastic-license>.
- Note: kreuzberg ≤ 4.5.x was MIT-licensed and relicensed to ELv2 in later 4.x releases. This
  dependency is **flagged for re-evaluation/removal in v0.2** (see `requirements/v0.2/`): the OCR
  path used here (EasyOCR) can be invoked directly without kreuzberg.

### OCR backends (pulled via kreuzberg's extras / used by `ocr_preprocess.py`)
- EasyOCR — Apache-2.0 — <https://github.com/JaidedAI/EasyOCR>
- Tesseract / pytesseract — Apache-2.0 — <https://github.com/tesseract-ocr/tesseract>
- (surya, PaddleOCR are optional alternatives — consult their upstreams for terms.)

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
(e.g. kreuzberg), re-check the corresponding license.*
