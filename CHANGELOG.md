# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0, the public surface
may still change between minor versions.

## [Unreleased]

## [0.1.0] - 2026-06-08

First public release.

### Added
- **MCP servers (3 servers, 14 tools):** `r2r` (search, ingest, list, delete, collections);
  `sourcebooks` (search_lore, list_books, get_chapter — with book/chapter/page citations);
  `vault-graph` (Obsidian `[[wikilink]]` graph navigation — 6 tools).
- **Claude Code skills (4):** worldbuilding, session-creation, chronik, vault-scout (in `skills/`),
  plus a with-skill/without-skill evaluation harness in `evals/`.
- **Client-side OCR + ingestion pipeline:** `detect_pdf_type.py` 3-tier classification; per-page
  hybrid extraction (`ocr_extract.py`) — embedded text layer where present, tesseract (default) or
  easyocr (GPU opt-in) where absent, plus region-targeted figure OCR; easyocr→tesseract auto-fallback;
  idempotent re-ingest and SHA1 dedup in `ingest_books.py`. Fully permissive (MIT/Apache/BSD) stack.
- **Deployment:** Docker Compose Light Mode (Postgres + MinIO + R2R + dashboard) and Full Mode
  (+ Unstructured.io, Hatchet); sandboxed VS Code devcontainer with an egress firewall.
- **Vault tooling:** `[[wikilink]]` graph builder (`build_vault_graph.py`) and post-ingestion checks
  (`verify_ingestion.py`).
- **Docs & demo:** quickstart, demo-walkthrough, design, troubleshooting; community-health files
  (Code of Conduct, Contributing, Security, Attribution, Third-Party Notices); a bundled TTRPG demo
  under `examples/ttrpg/`.

### Known limitations
- Linux/macOS hosts only (Windows unsupported); single-stack deployment is supported (the multi-instance
  variant ships but is unvalidated); the domain schema is TTRPG-specific. See
  `requirements/v0.2/requirements_v0.2.md` for the v0.2 backlog (R-3 collection support + the
  sourcebooks MCP design review).

[Unreleased]: https://github.com/mm-weber/R2R-ClaudeCode-integration/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mm-weber/R2R-ClaudeCode-integration/releases/tag/v0.1.0
