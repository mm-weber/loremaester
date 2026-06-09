# Technology Stack

## Backend / Runtime

### Language
**Choice:** Python
**Version:** 3.10–3.12 (scripts pin `requires-python`; 3.12 is the tested default)

### Execution model
**Choice:** PEP 723 single-file scripts run via `uv run --no-project`
**Rationale:** Each script declares its own inline dependencies; no project-wide virtualenv to manage.

### Core services
- **R2R (SciPhi)** — RAG engine; runs host-side via Docker Compose (`docker/compose.yaml`,
  `docker/compose.full.yaml`). MIT.
- **Ollama** — local embeddings provider.
- **Postgres + pgvector, MinIO** — R2R's stack (loopback-bound; see `.devcontainer/SecurityReview.md`).

### MCP servers
**Choice:** FastMCP (Python). Three native servers: `r2r-wrapper` (generic CRUD + search),
`sourcebooks` (domain facade), `vault-graph` (Obsidian graph).

### OCR (image-only PDFs)
- **Current:** `kreuzberg` — *being removed* (see Decision Log).
- **Target:** `pypdfium2` (render) + `pytesseract` (default) / `easyocr` (GPU opt-in), **per page**.

## Development Tools

### Package Manager
**Choice:** `uv` (PEP 723 inline deps); `pip install --break-system-packages` where a global is needed.

### Testing
| Type | Tool | Coverage Target |
| ---- | ---- | --------------- |
| Unit | pytest (R2R + OCR backends mocked) | pragmatic; no hard gate |

### Infrastructure
- **Containers:** Docker Compose (host-side R2R); a locked-down release devcontainer for the agent.
- **CI:** pip + pytest.

## Decision Log

### Remove kreuzberg from the OCR path
**Date:** 2026-06-06
**Status:** Accepted — track `remove-kreuzberg_20260606`

**Context:**
kreuzberg's EasyOCR path proved functionally unreliable (empty on multi-page PDFs in 4.9.9; a
separate PDF-path bug in 4.5–4.8.x) and it is Elastic License 2.0 (source-available, non-OSI) —
even the tesseract path pulls it.

**Decision:**
Replace kreuzberg with a direct, per-page pipeline: `pypdfium2` render → per-page `pytesseract`
(default) / `easyocr` (GPU opt-in) → concatenate. EasyOCR itself is Apache-2.0; calling it per page
is permissive and sidesteps the multi-page bug.

**Consequences:**
- Fully permissive (MIT / Apache / BSD) OCR footprint.
- New dependency `pypdfium2`; `surya` / `pymupdf` / `paddleocr` excluded from the shipped path.
- Evidence: `specs/v0.2/specs_v0.2.md` R-1 / R-1E.

## Version Compatibility Matrix
| Component | Min | Notes |
| --------- | --- | ----- |
| Python | 3.10 | scripts cap some at `<3.13` |
| pypdfium2 | latest | Apache/BSD; pure-Python wheel, no system binary |
| tesseract | system | `apt install tesseract-ocr` / `brew install tesseract` |
| easyocr / torch | opt-in | Apache/BSD; GPU optional, CPU fallback |
