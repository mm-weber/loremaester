# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0, the public surface
may still change between minor versions.

## [Unreleased]

### Added
- **`docker/compose.linux.yaml`** (new file): Linux-only port override that
  adds a second binding for the `r2r` service on the docker0 bridge gateway
  (typically `172.17.0.1:7272:7272`). Compose merges `ports` arrays by
  concatenation, so layering this file on top of either `compose.yaml` or
  `compose.full.yaml` produces a dual binding. Documented in
  `docs/quickstart.md` Step 2 (both Light and Full Mode invocations),
  `docs/demo-walkthrough.md` Step 5, and a new `docs/troubleshooting.md`
  entry covering the silent-refused symptom on Linux when the override is
  skipped.

### Changed
- **`.devcontainer/devcontainer.json`**: SSH-agent mount source restored to
  `${localEnv:SSH_AUTH_SOCK}`. The macOS-validation pass had hardcoded it to
  Docker Desktop's `/run/host-services/ssh-auth.sock`, which made the devcontainer
  fail to start on Linux hosts (`bind source path does not exist`). macOS users
  now run a one-time shell-init `export SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock`
  and launch VS Code from a terminal, documented in `docs/quickstart.md`,
  `docs/demo-walkthrough.md`, and `docs/troubleshooting.md`.
- **`docker/compose.yaml`** and **`docker/compose.full.yaml`**: the r2r
  service's Linux-only `172.17.0.1:7272:7272` binding has moved out of the
  base files into the new `docker/compose.linux.yaml` override. Both compose
  entry points are now cross-platform safe by default (loopback-only).
  Replaces the previous "delete the 172.17.0.1 line manually on macOS"
  callout in the docs.
- **Renamed `requirements/` to `specs/`** (and the inner
  `requirements_v0.2.md` to `specs_v0.2.md`) to remove the
  Python-pip-deps double-take. Documentation only; no code paths or
  tooling read from the directory. References updated in `README.md`,
  `docs/design.md`, `THIRD_PARTY_NOTICES.md`, and the four conductor
  artifacts that cite the v0.2 spec as evidence. `REVIEW.md` is left
  untouched as a frozen review snapshot.

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
  `specs/v0.2/specs_v0.2.md` for the v0.2 backlog (R-3 collection support + the
  sourcebooks MCP design review).

[Unreleased]: https://github.com/mm-weber/R2R-ClaudeCode-integration/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mm-weber/R2R-ClaudeCode-integration/releases/tag/v0.1.0
