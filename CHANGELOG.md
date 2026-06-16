# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0, the public surface
may still change between minor versions.

## [Unreleased]

### Security
- **`.devcontainer/init-firewall.sh`**: dropped `vscode.blob.core.windows.net`
  and `update.code.visualstudio.com` from the egress allowlist. The standard
  VS Code Desktop + Reopen-in-Container flow installs the VS Code Server via
  a client-side tunnel and handles version coordination, so the container
  itself needs neither direct CDN access nor an update-check endpoint.
  Narrowing the trust surface; re-add if an extension fails to fetch assets
  at runtime (symptom: denied iptables hits to the respective domain).
- **`.devcontainer/devcontainer.json`**: added
  `"telemetry.telemetryLevel": "off"` to `customizations.vscode.settings`.
  Stops VS Code Server's periodic POSTs to `mobile.events.data.microsoft.com`
  (which were continuously failing against the egress firewall and generating
  ongoing log noise). Aligned with the trust-narrowing posture above.

### Added
- **`R2R_TIMEOUT` env var (default 1800s)** for the ingest client. Large scanned
  box sets can take longer than the R2R SDK's 300s default to chunk+embed
  server-side; `scripts/ingest_books.py` now reads `R2R_TIMEOUT` and passes it to
  `R2RClient`, so big books no longer fail with `Request failed: timed out` (raise
  it further for very large corpora). The `r2r` MCP wrapper honors it too (default
  300s there, since search is fast). Documented in `docs/troubleshooting.md` and
  `docs/quickstart.md`. `UV_HTTP_TIMEOUT` is unrelated; it governs uv's package
  downloads only.
- **`ruff` (lint + format) gated in CI**: new
  `[tool.ruff]` config in `pyproject.toml` with the starter ruleset
  (E, W, F, I, B, UP, SIM, RUF), `target-version = "py310"`, line length 88.
  `.github/workflows/tests.yml` runs `ruff check .` and `ruff format --check .`
  before pytest as a merge gate. `ruff` added to `requirements-dev.txt`
  (`>= 0.7`). The starter ruleset includes `RUF013` (implicit-Optional),
  which catches the type-hint bugs corrected in the Fixed section below.
- **`requirements.txt`** and **`requirements-dev.txt`** (new files): single
  source of truth for Python runtime and test dependencies. `mcp` and `r2r`
  are pinned exactly (the volatile ones); test
  deps mix exact and floor pins. The Dockerfile, CI workflow, README,
  quickstart, troubleshooting, and CONTRIBUTING docs now all install via
  `pip install -r requirements*.txt`, replacing six divergent inline
  `pip install <bare list>` lines. The follow-up migration to a
  `pyproject.toml` `[project]` table is recorded as R-4 in
  `specs/v0.2/specs_v0.2.md`.
- **`.dockerignore`** (new file): pairs with the devcontainer build-context
  expansion below. Excludes `.git/`, `.pnpm-store/`, `node_modules/`,
  bundled-PDF fixtures, and `__pycache__` from the build context tarball so
  image builds stay quick.
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
- **`docs/demo-walkthrough.md`**: added a seventh demo, **Demo E**
  ("Worldbuilding skill mass-creates the wikilinked notes"), driven by the
  prompt "Create compact notes for all wikilinks mentioned." It sits between
  the session-prep demo (D) and the vault-scout sweep, exercising bulk creation
  of `NPC/`, `Locations/`, and `Factions/` notes from sourcebook research and
  seeding enough files for the Haiku-dispatched vault-scout demo that follows.
  The former vault-scout and chronik demos shift from E/F to F/G, and the
  step-9 heading ("A through G"), the Step 7 vault-population note, and the
  "What you just saw" table are renumbered to match.
- **`.devcontainer/devcontainer.json`**: SSH-agent mount source now reads
  `${localEnv:SSH_AUTH_SOCK_HOST:/run/host-services/ssh-auth.sock}`. The default
  is the path Docker Desktop forwards the host agent on, so **macOS / Docker
  Desktop works out of the box** (no shell-init export, and VS Code can launch
  from the Dock). **Linux** runs `export SSH_AUTH_SOCK_HOST="$SSH_AUTH_SOCK"`
  before launching the editor, because that default path does not exist outside
  Docker Desktop's VM. A dedicated variable is used (not `SSH_AUTH_SOCK`) because
  macOS keeps `SSH_AUTH_SOCK` set to an unmountable launchd socket that would
  shadow the default. Documented in `docs/quickstart.md`,
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
  artifacts that cite the v0.2 spec as evidence.
- **`.devcontainer/Dockerfile`** and **`.devcontainer/devcontainer.json`**:
  build context expanded to the repo root via `"context": ".."` so the
  Dockerfile can `COPY requirements.txt requirements-dev.txt /tmp/` at
  image-build time. The two existing context-relative `COPY` directives
  (`init-firewall.sh`, `entrypoint.sh`) are now prefixed with
  `.devcontainer/`. The pip-install step at line 64 reads from
  `requirements-dev.txt` instead of an inline package list; `uv` is
  installed as a separate step (it is a tool, not a runtime dep).
- **`docs/quickstart.md`**: removed the `uv pip install pdfplumber` host
  prereq and the matching install line in the OCR System Requirements
  block. The PEP 723 scripts that need `pdfplumber` declare it inline and
  `uv run --no-project` resolves it per invocation, so the manual host
  install was redundant.
- **`mcp-servers/r2r-wrapper/r2r_mcp_wrapper.py`** — defensive attribute
  access dropped: `search`, `list_documents`, and
  `list_collections` now use bare attribute access (`chunk.score`,
  `doc.title`, `coll.name`, etc.) instead of
  `getattr(obj, "...", default)`. This matches the sourcebooks server's
  style and intentionally chooses fail-loud-on-schema-drift over
  silent-default-fallback. Rationale: the R2R dep may be replaced in
  the future, and defensive getattrs only hide drift that we'd
  otherwise want to discover and adapt to immediately. The wrapper's
  unit tests already set every attribute explicitly on the test mocks,
  so they continue to pass.

### Fixed
- **Light Mode embedding sized for small or shared GPUs.**
  `docker/user_configs/r2r-light.toml` lowers `[embedding]`/`[completion_embedding]`
  `batch_size` 128 -> 32 and `concurrent_request_limit` 8 -> 2 (peak in-flight texts
  to Ollama is `batch_size * concurrent_request_limit`), and `scripts/ocr_extract.py`
  now frees easyocr's GPU memory after each book (`torch.cuda.empty_cache()`).
  Together these stop Ollama failing with `model failed to load` (resource
  limitations) when a big book is OCR'd on the same GPU Ollama embeds on. See
  docs/troubleshooting.md.
- **Light Mode chunk size capped to fit the embedding context window.**
  `docker/user_configs/r2r-light.toml` now sets `[ingestion] chunk_size = 512`
  (characters), `chunk_overlap = 64`, `chunking_strategy = "recursive"`. Light
  Mode's built-in `r2r` parser ignores Unstructured's
  `max_characters`/`new_after_n_chars` (those apply only to Full Mode's
  `unstructured_local` provider) and was running on the 1024-char default, so a
  dense OCR chunk could exceed mxbai-embed-large's 512-token window and fail
  ingestion with `input length exceeds the context length` (the Ollama embedding
  path does not truncate oversized inputs). Restart R2R to reload the config,
  then re-ingest the affected book.
- **Implicit-Optional type hints in three MCP tool signatures**:
  `mcp-servers/sourcebooks/server.py:18` (`search_lore`'s `book` and
  `content_type` params), `mcp-servers/vault-graph/server.py:169`
  (`vault_central_notes`'s `tag` param), and
  `mcp-servers/vault-graph/server.py:196` (`vault_search_notes`'s
  `name_pattern`, `tag`, `note_type` params). Each `X: str = None` rewritten
  as `X: str | None = None`. These signatures are exposed to Claude as MCP
  tool schemas, so the fix corrects the schema the model sees as well as
  satisfying ruff's `RUF013`.
- **Dead `"{n} of {n} chunks"` output in `r2r_mcp_wrapper.search()`**:
  the trailing summary line read
  `f"Returned {len(chunks)} of {len(chunks)} chunks (limit: {limit})"` —
  both halves of "of" were the same variable, so it always printed
  `Returned N of N chunks`. The original intent was clearly "actual vs
  requested"; rewritten as `Returned {n} chunk(s); requested up to {limit}`
  to restate that without the duplication. Test assertions updated to
  match.

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

[Unreleased]: https://github.com/mm-weber/loremaester/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mm-weber/loremaester/releases/tag/v0.1.0
