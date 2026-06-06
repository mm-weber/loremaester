# Python Style Guide

Conventions for this repo's Python (PEP 723 scripts + MCP servers).

## Scripts are PEP 723 single-file programs
- Each `scripts/*.py` declares its deps in a `# /// script` block and runs via `uv run --no-project`.
- Keep `requires-python` accurate; pin only what must be pinned.
- Neural / heavy deps (torch, easyocr) are opt-in via `uv run --with`, never in the default dep block.

## Dependencies
- Prefer the stdlib; add third-party only when it earns its keep.
- Permissive licenses only on the shipped path (MIT / Apache / BSD). No Elastic-2.0 / AGPL / GPL in
  defaults — flag anything copyleft in `THIRD_PARTY_LICENSES.md`.

## Defensive, honest code
- Use `getattr(obj, "attr", default)` against external SDK / result objects whose schema may drift.
- Never swallow a failure into a success or empty result — surface the cause (file, page, dependency).
- Gate verbose diagnostics behind an env flag (e.g. `INGEST_DEBUG`).

## Errors
- A missing optional dependency → exit with a message naming the package **and** its install command.
- Include identifying context in errors (filename, page number, backend).

## Testing
- Mock external services (the R2R client) and OCR backends / renderers so tests need no binaries or
  network. Mirror existing modules (`test_ocr_preprocess.py`, `test_extract_text.py`) for new code.

## Formatting
- 4-space indent; clear names; comments explain *why*, matching the surrounding density.
