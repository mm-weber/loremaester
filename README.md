# Worldbuilding Assistant for Claude Code

Turn Claude Code into a worldbuilding collaborator that knows your Obsidian vault AND your TTRPG sourcebooks. Claude reads and writes vault notes natively while querying scanned sourcebooks via R2R semantic search — generating new content that's consistent with your canon and published lore.

## Architecture

```
  HOST MACHINE                                    DEVCONTAINER
 ┌───────────────────────────────────┐           ┌────────────────────────────────┐
 │                                   │           │  Claude Code                   │
 │  Ollama (:11434)                  │           │    ├─ r2r MCP server           │
 │  └─ mxbai-embed-large             │           │    ├─ sourcebooks MCP server   │
 │                                   │           │    ├─ vault-graph MCP server   │
 │  R2R Server (:7272)               │◄─────────►│    └─ worldbuilding skill      │
 │  ├─ PostgreSQL + pgvector         │  host.    │                                │
 │  ├─ Unstructured.io (PDF/OCR)     │  docker.  │  Obsidian vault (bind mount)   │
 │  └─ Hatchet (orchestration)       │  internal │  .graph.json                   │
 │                                   │           │                                │
 │  R2R Dashboard (:7273)            │           │                                │
 └───────────────────────────────────┘           └────────────────────────────────┘
```

R2R handles **embedding and retrieval only** — all reasoning is done by Claude Code. You only need a local embedding model (`mxbai-embed-large` via Ollama), no API keys required.

## Features

**3 MCP Servers, 14 Tools:**

| Server | Tools | Purpose |
|--------|-------|---------|
| **r2r** | `search`, `ingest_document`, `list_documents`, `delete_document`, `list_collections` | Generic R2R operations |
| **sourcebooks** | `search_lore`, `list_books`, `get_chapter` | Worldbuilding-aware lore search with book/chapter/page citations |
| **vault-graph** | `vault_graph`, `vault_backlinks`, `vault_search_notes`, `vault_central_notes`, `vault_reload_cache`, `vault_rebuild_graph` | Obsidian `[[wikilink]]` graph navigation |

**Plus:**
- Docker Compose deployment (single-stack or multi-instance)
- PDF ingestion with OCR support (via Unstructured.io)
- Vault wikilink graph builder
- Worldbuilding skill that orchestrates the full workflow

## Quick Start

```bash
# 1. Pull the embedding model
ollama pull mxbai-embed-large && ollama serve

# 2. Start R2R
docker compose -f docker/compose.full.yaml --profile postgres up -d

# 3. Build your vault graph
uv run --no-project scripts/build_vault_graph.py /path/to/vault

# 4. Install MCP dependencies
pip install mcp r2r pyyaml

# 5. Configure MCP servers in .claude/settings.json (see docs/quickstart.md)
```

See [docs/quickstart.md](docs/quickstart.md) for the full setup guide.

## Project Structure

```
├── docker/                        # Docker Compose deployment
│   ├── compose.yaml               # Light mode (recommended): R2R + Postgres + MinIO
│   ├── compose.full.yaml          # Full mode: + Unstructured.io, Hatchet, RabbitMQ
│   ├── compose.infra.yaml         # Shared infrastructure (multi-instance)
│   ├── compose.app.yaml           # Per-instance R2R app
│   ├── instances/                 # Per-deployment .env configs
│   ├── env/                       # Environment variable files
│   └── scripts/                   # Container startup scripts
├── mcp-servers/
│   ├── r2r-wrapper/               # Generic R2R MCP server (search/ingest/list)
│   ├── sourcebooks/               # Worldbuilding lore search MCP server
│   └── vault-graph/               # Wikilink graph navigation MCP server
├── scripts/                       # CLI tools
│   ├── build_vault_graph.py       # Parse [[wikilinks]] → .graph.json
│   ├── extract_text.py            # OCR text extraction (kreuzberg)
│   ├── detect_pdf_type.py         # Classify PDFs (text-native vs image)
│   ├── ingest_books.py            # Bulk PDF ingestion
│   └── verify_ingestion.py        # Post-ingestion quality checks
├── plugins/
│   └── worldbuilding/             # Claude Code worldbuilding skill
├── examples/
│   └── vault-claude-md-template.md
├── docs/                          # Documentation
│   ├── demo-walkthrough.md        # 30-min hands-on demo with bundled content
│   ├── quickstart.md              # Full setup guide for your own vault
│   ├── design.md                  # Architecture and design decisions
│   └── troubleshooting.md         # Common issues and fixes
├── requirements/                  # v0.2 requirements & design notes
├── .github/workflows/tests.yml    # CI/CD pipeline
└── pyproject.toml                 # Pytest configuration
```

## Documentation

- **[Demo walkthrough](docs/demo-walkthrough.md)** — 30-minute hands-on tour using bundled sourcebooks and the `Grunvyr_Campaign` scaffold. Best starting point if you want to see the product work before configuring your own content.
- **[Quickstart](docs/quickstart.md)** — Full setup: Ollama, R2R, vault prep, MCP config, first session — for wiring up your own vault and sourcebooks.
- **[Design](docs/design.md)** — Architecture decisions, component map, workflow
- **[Troubleshooting](docs/troubleshooting.md)** — Common issues, database resets, multi-instance debugging
- **[Requirements](requirements/)** — v0.2 requirements and design-review notes (sourcebooks MCP review + OCR/licensing follow-ups)

## Multi-Instance Deployment

Run separate R2R instances for different vaults or projects on the same server:

```bash
# Start shared infrastructure (once)
docker/scripts/r2r-infra.sh up

# Start per-vault instances
docker/scripts/r2r-instance.sh ttrpg up
docker/scripts/r2r-instance.sh coding up
```

Each instance gets its own Postgres schema (`R2R_PROJECT_NAME`), port range, and R2R config. See `docker/instances/` for examples.

## Development

```bash
# Run tests
pytest -v --tb=short

# Build vault graph
uv run --no-project scripts/build_vault_graph.py /path/to/vault

# Classify PDFs before ingestion
uv run --no-project scripts/detect_pdf_type.py /path/to/pdfs/
```

> **Running the scripts.** The `scripts/` are standalone [PEP 723](https://peps.python.org/pep-0723/) scripts — each declares its own dependencies inline, so `uv run --no-project scripts/<name>.py` fetches them into a throwaway environment automatically. The `--no-project` flag is required: `pyproject.toml` here configures pytest only (no `[project]` table), so a bare `uv run scripts/<name>.py` errors with *"No `project` table found"*. (If the dependencies are already installed in your environment, plain `python scripts/<name>.py` works too.) The OCR scripts (`extract_text.py`, `ocr_preprocess.py`) additionally need the system `tesseract`/`poppler` binaries, and `ingest_books.py` needs the PyTorch cu126 index for GPU OCR — see [docs/quickstart.md](docs/quickstart.md).

## License

This project's own code is released under the **MIT License** — see [LICENSE](LICENSE).

It orchestrates third-party components under their own licenses — notably
[R2R](https://github.com/SciPhi-AI/R2R) (MIT) and, for *optional* client-side OCR,
[kreuzberg](https://github.com/kreuzberg-dev/kreuzberg) (Elastic License 2.0, source-available).
See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for full attribution and important usage
notes before redistributing or hosting this project.
