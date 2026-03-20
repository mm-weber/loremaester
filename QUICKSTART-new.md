# Quickstart: Worldbuilding Assistant for Claude Code

Turn Claude Code into a worldbuilding collaborator that knows your Obsidian vault AND your sourcebooks.

Set up R2R semantic search with Ollama embeddings, ingest your PDF sourcebooks (including scanned/image PDFs), connect your vault, and run your first worldbuilding session — all in one guide.

---

## Architecture Overview

```
  HOST MACHINE                                    DEVCONTAINER
 ┌───────────────────────────────┐              ┌──────────────────────────────┐
 │                               │              │  Claude Code                 │
 │  Ollama (:11434)              │              │    ├─ r2r MCP server         │
 │  └─ mxbai-embed-large         │              │    ├─ sourcebooks MCP server  │
 │     (embedding model only)    │              │    ├─ vault-graph MCP server  │
 │                               │              │    └─ worldbuilding skill     │
 │  R2R Server (:7272)           │◄────────────►│                              │
 │  ├─ PostgreSQL + pgvector     │  host.       │  Obsidian vault (bind mount) │
 │  ├─ Unstructured.io (OCR)    │  docker.     │  .graph.json                 │
 │  └─ Hatchet (orchestration)  │  internal    │                              │
 │                               │  :7272       │                              │
 │  R2R Dashboard (:7273)        │              │                              │
 │                               │              │                              │
 │  PDF ingestion                │              │                              │
 │  (r2r CLI / SDK / scripts)   │              │                              │
 └───────────────────────────────┘              └──────────────────────────────┘
```

### Key Architecture Point

R2R is used **only for search and ingestion** — embedding, vector storage, and retrieval. All reasoning and generation is handled by Claude Code via MCP servers. No completion/LLM models are needed in R2R or Ollama. You only need an **embedding model** (`mxbai-embed-large`).

### Components

| # | Component | What it does |
|---|-----------|--------------|
| 1 | **Ollama** | Runs the embedding model (`mxbai-embed-large`) locally — no API keys needed |
| 2 | **R2R (Docker Full Mode)** | Search, ingestion, PostgreSQL + pgvector, Unstructured.io for PDF OCR |
| 3 | **Vault CLAUDE.md** | Teaches Claude your vault's structure, frontmatter schemas, wikilink conventions |
| 4 | **R2R MCP Wrapper** | Generic search/ingest/list/delete against R2R |
| 5 | **Sourcebooks MCP Server** | Worldbuilding-specific lore queries (`search_lore`, `list_books`, `get_chapter`) |
| 6 | **Vault Graph Builder** | Parses `[[wikilinks]]` into `.graph.json` |
| 7 | **Vault Graph MCP Server** | Graph traversal, backlinks, centrality ranking |
| 8 | **Worldbuilding Skill** | Orchestrates the full workflow: gather context, research lore, generate, write back |

> **Why does R2R live on the host?** R2R runs PostgreSQL with pgvector, an embedding pipeline, and Unstructured.io for PDF parsing. These are heavy services that don't belong inside a devcontainer. The devcontainer talks to R2R over the Docker bridge network via `host.docker.internal:7272`.

> **Why Ollama instead of OpenAI?** Ollama runs entirely on your machine — no API keys, no per-token costs, no data leaving your network. The `mxbai-embed-large` model produces 1024-dimensional embeddings that work well for TTRPG sourcebook content.

---

## Prerequisites

- [ ] Claude Code running inside a devcontainer
- [ ] Python 3.10+ on the host machine
- [ ] [`uv`](https://docs.astral.sh/uv/) for Python package management: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] An Obsidian vault with TTRPG worldbuilding notes
- [ ] PDF sourcebooks (optional — the system works with just the vault)
- [ ] Docker + Docker Compose on the host (**required** for R2R Full Mode)
- [ ] `pdfplumber` on the host for PDF type detection: `uv pip install pdfplumber`
- [ ] (Optional) For client-side OCR without Docker Full Mode: `tesseract-ocr`, `poppler-utils`

### System Requirements for OCR Tools (Optional)

If you plan to use client-side OCR preprocessing (for users who can't use Docker Full Mode for image PDFs):

```bash
# Debian/Ubuntu
sudo apt install tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler

# Python packages
uv pip install pdfplumber pdf2image Pillow pytesseract
# Optional: uv pip install surya-ocr  (Python-native OCR, no system deps)
```

> **Note:** If you're running Docker Full Mode (recommended), Unstructured.io handles OCR server-side and you don't need these system packages.

---

## Step 1 — Set Up Ollama for Embeddings

Ollama provides the embedding model that R2R uses to convert your sourcebook text into searchable vectors. You only need an embedding model — Claude Code handles all reasoning and generation.

### 1a. Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS — download from https://ollama.com/download
```

### 1b. Pull the Embedding Model

```bash
ollama pull mxbai-embed-large
```

This downloads `mxbai-embed-large` (~670 MB), a 1024-dimensional embedding model. No LLM/completion model is needed.

### 1c. Start Ollama

```bash
ollama serve
```

Ollama runs on port `11434` by default. Leave this terminal open or run it as a background service.

### 1d. Verify

```bash
ollama list
```

You should see `mxbai-embed-large` in the output:

```
NAME                       ID            SIZE    MODIFIED
mxbai-embed-large:latest   ...           670 MB  ...
```

---

## Step 2 — Start R2R with Docker Full Mode

Docker Full Mode gives you PostgreSQL + pgvector for vector storage, Unstructured.io for PDF parsing (including OCR for scanned/image PDFs), and Hatchet for orchestration.

### 2a. Clone the R2R Repository

```bash
git clone https://github.com/SciPhi-AI/R2R.git
cd R2R
```

### 2b. Create a Custom R2R Config (Embeddings Only)

Since Claude Code handles all reasoning, R2R only needs an embedding configuration. Create a minimal TOML config:

```bash
mkdir -p docker/user_configs
```

Save the following as `docker/user_configs/r2r-ollama-embeddings.toml`:

```toml
# R2R config: Ollama embeddings only.
# No completion/LLM config — Claude Code handles all reasoning via MCP servers.

[embedding]
provider = "ollama"
base_model = "mxbai-embed-large"
base_dimension = 1_024
batch_size = 32
concurrent_request_limit = 2

[completion_embedding]
provider = "ollama"
base_model = "mxbai-embed-large"
base_dimension = 1_024
batch_size = 32
concurrent_request_limit = 2

[ingestion]
provider = "unstructured_local"
strategy = "auto"
chunking_strategy = "by_title"
new_after_n_chars = 384
max_characters = 512
combine_under_n_chars = 128
overlap = 20
skip_document_summary = true
automatic_extraction = false

[orchestration]
provider = "hatchet"

[app]
# Default PDF upload limit is 30MB — TTRPG sourcebooks regularly exceed this.
max_upload_size_by_type = { pdf = 300_000_000 }
```

> **What each section does:**
> - `[embedding]` / `[completion_embedding]` — Tells R2R to use Ollama's `mxbai-embed-large` for converting text to vectors
> - `[ingestion]` — Uses Unstructured.io (running as a Docker service) for PDF parsing, including OCR for scanned documents. `skip_document_summary` and `automatic_extraction` are set to disable LLM calls (we use Ollama for embeddings only, not completions)
> - `[orchestration]` — Uses Hatchet for managing async ingestion jobs

### 2c. Configure Environment Variables

Edit `docker/env/r2r-full.env` — this is the env file loaded by `compose.full.yaml`.

Two variables need changing:

| Variable | Default | Change to | Why |
|----------|---------|-----------|-----|
| `R2R_CONFIG_NAME` | `full` | *(clear it — leave empty)* | `R2R_CONFIG_NAME` and `R2R_CONFIG_PATH` are mutually exclusive. We need `R2R_CONFIG_PATH` for our custom config. |
| `R2R_CONFIG_PATH` | *(empty)* | `/app/user_configs/r2r-ollama-embeddings.toml` | Points to the custom config created in Step 2b. The `docker/user_configs/` directory is mounted into the container at `/app/user_configs/`. |

```bash
# In docker/env/r2r-full.env, find and change these two lines:
R2R_CONFIG_NAME=
R2R_CONFIG_PATH=/app/user_configs/r2r-ollama-embeddings.toml
```

All other defaults are fine for local development:
- `OLLAMA_API_BASE` is already `http://host.docker.internal:11434` (reaches Ollama on your host)
- API keys (OpenAI, Anthropic, etc.) are empty — not needed since Claude Code handles all LLM work
- Postgres credentials default to `postgres`/`postgres` — fine for local use

> **Note:** Don't edit `docker/env/r2r.env` — that file is for `compose.yaml` (basic mode). Our guide uses `compose.full.yaml`, which loads `r2r-full.env`.

### 2d. Start the Full Stack

```bash
docker compose -f docker/compose.full.yaml --profile postgres up -d
```

This starts the following services:

| Service | Port | Purpose |
|---------|------|---------|
| **postgres** | 5432 | PostgreSQL with pgvector for vector storage |
| **r2r** | 7272 | R2R API server — search, ingest, document management |
| **r2r-dashboard** | 7273 | Web UI for browsing documents and testing search |
| **unstructured** | (internal) | PDF/document parsing with OCR for scanned documents |
| **hatchet-engine** | 7077 | Async job orchestration for ingestion pipelines |
| **hatchet-dashboard** | 7274 | Hatchet job monitoring UI |
| **minio** | 9000/9001 | Object storage (if using the minio profile) |
| **graph_clustering** | 7276 | Graph-based document clustering |

> **First start takes a while.** Docker needs to pull several images. Subsequent starts are fast.

### 2e. Verify R2R is Running

```bash
curl http://localhost:7272/v3/health
```

Expected: `{"results":{"response":"ok"}}`

You can also open the R2R dashboard at [http://localhost:7273](http://localhost:7273) in your browser. The default login credentials are `admin@example.com` / `change_me_immediately` — change these for any non-local deployment.

### 2f. Check Logs if Something Goes Wrong

```bash
# All services
docker compose -f docker/compose.full.yaml logs -f

# Just R2R
docker compose -f docker/compose.full.yaml logs -f r2r

# Just Unstructured
docker compose -f docker/compose.full.yaml logs -f unstructured
```

---

## Step 3 — Classify Your PDFs

Before ingesting, determine which of your PDFs are text-native (purchased digitally) vs. image-only (scanned). This matters because image PDFs require OCR to extract text.

### 3a. Run the Detection Script

```bash
python scripts/detect_pdf_type.py /path/to/your/sourcebooks/
```

Output:

```
Players_Handbook.pdf       text-native  (318 of 320 pages have extractable text)
Monster_Manual.pdf         image-only   (0 of 320 pages have extractable text)
Old_Campaign_Guide.pdf     mixed        (200 of 400 pages have extractable text)
```

**Classification logic:**

| Result | Meaning | Ingestion path |
|--------|---------|----------------|
| `text-native` | >= 90% of pages have extractable text | Direct ingestion (Step 4) |
| `image-only` | >= 90% of pages have no extractable text | Needs OCR (see decision tree below) |
| `mixed` | Some pages have text, some don't | Treat as image-only for best results |

### 3b. Choose Your Ingestion Path

```
Are your PDFs scanned (image-only or mixed)?
├── Don't know
│   └── Run: python scripts/detect_pdf_type.py /path/to/pdfs/
├── Yes, and I'm running Docker Full Mode (Step 2)
│   └── Just ingest normally — Unstructured.io handles OCR server-side automatically
├── Yes, and I'm NOT running Docker Full Mode
│   └── Preprocess first: python scripts/ocr_preprocess.py /path/to/book.pdf --book-title "..."
└── No, they're text-native
    └── Ingest directly (Step 4)
```

> **Docker Full Mode users:** You don't need to do anything special for image PDFs. Unstructured.io performs OCR automatically during ingestion. Just follow Step 4 as normal.

---

## Step 4 — Ingest Sourcebooks from a Folder

### Folder Structure

Drop your PDFs into a flat folder — no special directory hierarchy needed:

```
sourcebooks/
├── Core_Rulebook_PF2e.pdf
├── Lost_Omens_World_Guide.pdf
├── Planescape_Campaign_Setting.pdf
└── Bestiary_PF2e.pdf
```

### Metadata Schema

Only `book_title` is required. The sourcebooks MCP server uses it for `search_lore`, `list_books`, and `get_chapter`.

| Field | Type | Required? | Example | Purpose |
|-------|------|-----------|---------|---------|
| `book_title` | string | **Yes** | `"Lost Omens World Guide"` | Filtering in `search_lore`, `list_books`, `get_chapter` |
| `page_range` | string | No | `"pp. 1-312"` | Display in search results |

> **Note:** The server also accepts `system`, `publisher`, `content_type`, and `chapter` if provided — they just aren't required.

### Ingesting Text-Native PDFs (and Image PDFs in Docker Full Mode)

For text-native PDFs — or any PDFs when running Docker Full Mode (Unstructured.io handles OCR automatically) — use the bulk ingestion script.

#### Single PDF

```bash
# Install the R2R CLI if not already available
uv pip install r2r

r2r documents create /path/to/book.pdf \
  --metadata '{"book_title": "Core Rulebook"}'
```

#### Bulk Ingestion Script

Save this as `ingest_books.py` and run it on the host:

```python
#!/usr/bin/env python3
"""Bulk-ingest PDFs into R2R with sourcebook metadata."""

import sys
from pathlib import Path
from r2r import R2RClient

R2R_BASE = "http://localhost:7272"

def ingest_pdf(client, pdf_path, metadata):
    result = client.documents.create(file_path=str(pdf_path), metadata=metadata)
    doc_id = result.results.document_id
    print(f"  Ingested: {pdf_path.name} -> {doc_id}")
    return doc_id

def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest_books.py <folder_of_pdfs>")
        sys.exit(1)

    pdf_dir = Path(sys.argv[1])
    client = R2RClient(R2R_BASE)

    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) in {pdf_dir}\n")

    succeeded = []
    failed = []

    for pdf in pdfs:
        book_title = pdf.stem.replace("_", " ").replace("-", " ").title()
        metadata = {"book_title": book_title}

        print(f"[{book_title}]")
        try:
            ingest_pdf(client, pdf, metadata)
            succeeded.append(pdf.name)
        except Exception as e:
            print(f"  FAILED: {pdf.name} — {e}")
            failed.append(pdf.name)

    print(f"\nDone. {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed files:")
        for name in failed:
            print(f"  - {name}")

if __name__ == "__main__":
    main()
```

```bash
python ingest_books.py /path/to/sourcebooks/
```

### Ingesting Image PDFs Without Docker Full Mode

If you're running R2R in Light Mode and have scanned/image PDFs, preprocess them with client-side OCR first:

```bash
# Using Tesseract (fast, requires system packages)
python scripts/ocr_preprocess.py /path/to/scanned_book.pdf \
    --book-title "Monster Manual" \
    --engine tesseract

# Using Surya (no system deps, Python-native, slower)
python scripts/ocr_preprocess.py /path/to/scanned_book.pdf \
    --book-title "Monster Manual" \
    --engine surya
```

The script extracts text via OCR page-by-page, then ingests the resulting text into R2R with proper metadata.

**Output:**

```
Ingested: Monster Manual
  Document ID: 7a3f...
  Pages processed: 320
  Average confidence: 0.87
  Low-confidence pages: 12, 45, 201
```

### Verify Ingestion

After ingesting, verify that the text was extracted correctly:

```bash
# Single document by title
python scripts/verify_ingestion.py --book-title "Core Rulebook"

# Single document by ID
python scripts/verify_ingestion.py --document-id 7a3f...

# All ingested documents
python scripts/verify_ingestion.py --all
```

**Output:**

```
Verification: Core Rulebook (ID: 7a3f...)
  [PASS] Document exists: status: success
  [PASS] Chunk count: 847 chunks
  [PASS] Text quality: 840/847 chunks clean
  [PASS] Search coherence: avg score 0.72 across 5 results
Overall: PASS
```

If a document is still being processed, you'll see a warning instead of a crash:

```
Verification: Monster Manual (ID: 9b2e...)
  [PASS] Document exists: status: chunking
  [WARN] Ingestion status: ingestion still in progress (chunking) — chunk checks skipped
Overall: WARN
```

You can also verify from the command line or the dashboard:

```bash
# List all documents
curl http://localhost:7272/v3/documents | python -m json.tool

# Or open the R2R dashboard: http://localhost:7273
```

---

## Step 5 — Prepare Your Obsidian Vault

### 5a. Make the vault accessible inside the devcontainer

Add a bind mount in your `devcontainer.json`:

```jsonc
{
  "mounts": [
    "source=/path/to/your/obsidian/vault,target=/workspace/vault,type=bind"
  ]
}
```

Or, if your vault is already somewhere under `/workspace/`, no mount is needed.

After changing `devcontainer.json`, rebuild the container for the mount to take effect.

### 5b. Add a CLAUDE.md to your vault

Copy the template and fill in your details:

```bash
cp examples/vault-claude-md-template.md /workspace/vault/CLAUDE.md
```

Open `/workspace/vault/CLAUDE.md` and replace the placeholders:

- `YOUR_SYSTEM` — your game system (e.g., `Pathfinder 2e`, `D&D 5e`)
- `YOUR_WORLD` — your world name (e.g., `Golarion`, `Forgotten Realms`)
- `YOUR_CAMPAIGN` — your campaign name (e.g., `Kingmaker 2e`)
- Update the folder structure tree to match your vault layout

### 5c. Build the wikilink graph

Inside the devcontainer:

```bash
uv pip install pyyaml

python scripts/build_vault_graph.py /workspace/vault
```

Expected output:

```
Graph built: 142 notes, 387 edges → /workspace/vault/.graph.json
```

The note and edge counts will vary based on your vault size.

---

## Step 6 — Configure Claude Code MCP Servers

### 6a. Install Python dependencies in the devcontainer

```bash
uv pip install mcp r2r pyyaml
```

Or with a virtual environment:

```bash
uv venv .venv && source .venv/bin/activate
uv pip install mcp r2r pyyaml
```

### 6b. Edit `.claude/settings.json`

Add the `mcpServers` block to your Claude Code settings. Replace `/path/to/repo` with the absolute path where you cloned this repository.

```json
{
  "mcpServers": {
    "r2r": {
      "command": "python",
      "args": ["/path/to/repo/r2r_mcp_wrapper.py"],
      "env": {
        "R2R_API_BASE": "http://host.docker.internal:7272",
        "R2R_API_KEY": "${R2R_API_KEY}"
      }
    },
    "sourcebooks": {
      "command": "python",
      "args": ["/path/to/repo/mcp-servers/sourcebooks/server.py"],
      "env": {
        "R2R_API_BASE": "http://host.docker.internal:7272"
      }
    },
    "vault-graph": {
      "command": "python",
      "args": ["/path/to/repo/mcp-servers/vault-graph/server.py"],
      "env": {
        "VAULT_PATH": "/workspace/vault"
      }
    }
  }
}
```

**Critical**: `R2R_API_BASE` must be `http://host.docker.internal:7272`, **not** `http://localhost:7272`. Inside the devcontainer, `localhost` refers to the container itself. `host.docker.internal` bridges to the host machine where R2R is running.

`VAULT_PATH` must match the mount target from Step 5a.

### 6c. MCP Server Reference

| Server | Tools | Env Vars |
|--------|-------|----------|
| **r2r** | `search`, `ingest_document`, `list_documents`, `delete_document`, `list_collections` | `R2R_API_BASE`, `R2R_API_KEY` |
| **sourcebooks** | `search_lore`, `list_books`, `get_chapter` | `R2R_API_BASE` |
| **vault-graph** | `vault_graph`, `vault_backlinks`, `vault_search_notes`, `vault_central_notes`, `vault_reload_graph` | `VAULT_PATH` |

### 6d. Linux Networking Workaround

On Linux hosts, `host.docker.internal` may not resolve by default. Add this to your `devcontainer.json`:

```jsonc
{
  "runArgs": [
    "--add-host=host.docker.internal:host-gateway"
  ]
}
```

Then rebuild the container.

### 6e. Verify

Restart Claude Code, then run:

```
/mcp
```

You should see 3 servers connected with 13 tools total:
- `r2r` — 5 tools
- `sourcebooks` — 3 tools
- `vault-graph` — 5 tools

---

## Step 7 — Install the Worldbuilding Skill

Copy the skill into your Claude Code skills directory:

```bash
mkdir -p .claude/skills/worldbuilding
cp plugins/worldbuilding/SKILL.md .claude/skills/worldbuilding/SKILL.md
```

The skill auto-triggers on worldbuilding requests — creating NPCs, factions, locations, researching lore, or expanding your world. You don't need to invoke it manually.

---

## Step 8 — Your First Session

Try these three prompts in order. Each tests a different layer of the system.

### Test 1: Research (sourcebooks MCP)

```
What do my source books say about dwarven society?
```

**Expected**: Claude calls `search_lore(query="dwarven society")` and returns passages from your ingested PDFs with book/chapter/page citations. If you haven't ingested any PDFs yet, you'll get "No results" — that's fine, the connection is working.

### Test 2: Vault Exploration (vault-graph MCP)

```
Show me everything connected to [a well-linked note in your vault]
```

**Expected**: Claude calls `vault_graph(note="Note Name", depth=2)` and shows the connection neighborhood — which notes link to it, which it links to, across 2 hops. It then reads the most relevant connected notes.

### Test 3: Full Workflow (everything together)

```
Create a new NPC tavern keeper for [a location in your vault].
Check my existing notes and source books for context first.
Save the result to my vault.
```

**Expected**: Claude follows the full worldbuilding workflow:
1. Searches the vault graph for the location and related notes
2. Reads existing notes to understand what's established
3. Queries sourcebooks for relevant lore
4. Generates an NPC with correct frontmatter, wikilinks, and voice
5. Writes the note to the correct vault folder
6. Updates related notes with backlinks
7. Calls `vault_reload_graph()` to refresh the graph

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Connection refused" on `search_lore` | R2R not running or wrong URL | Verify `curl http://localhost:7272/v3/health` on host; check that `R2R_API_BASE` uses `host.docker.internal`, not `localhost` |
| ".graph.json not found" | Graph not built | Run `python scripts/build_vault_graph.py /workspace/vault` |
| "Note 'X' not found" | Stale graph after vault edits | Call `vault_reload_graph()` or re-run `build_vault_graph.py` |
| MCP server shows as disconnected | Wrong path in settings.json | Paths must be absolute; verify `python -c "import mcp, r2r"` succeeds in the devcontainer |
| "No books found" from `list_books` | PDFs not ingested with metadata | Re-ingest with `book_title` in the metadata dict (see Step 4) |
| `ImportError: No module named 'r2r'` | SDK not installed in devcontainer | `uv pip install r2r` |
| `host.docker.internal` doesn't resolve | Linux without gateway config | Add `"--add-host=host.docker.internal:host-gateway"` to `runArgs` in `devcontainer.json` |
| Search returns no results for an ingested book | Image PDF ingested without OCR (Light Mode) | Use Docker Full Mode (Unstructured.io handles OCR) or preprocess with `scripts/ocr_preprocess.py` |
| Search returns garbled/nonsensical text | Poor OCR quality on scanned pages | Re-ingest with a different OCR engine, or check original scan quality |
| `detect_pdf_type.py` says "mixed" | PDF has some text pages and some image pages | Ingest in Docker Full Mode (Unstructured handles both), or preprocess image pages with `ocr_preprocess.py` |
| Ollama connection refused from R2R | R2R container can't reach host Ollama | Verify `OLLAMA_API_BASE=http://host.docker.internal:11434` in `r2r-full.env`; verify `ollama serve` is running on host |
| R2R starts but embeddings fail | Wrong config or Ollama model not pulled | Verify `ollama list` shows `mxbai-embed-large`; check R2R logs with `docker compose -f docker/compose.full.yaml logs r2r` |
| R2R container keeps restarting | Dependency service not healthy | Check `docker compose -f docker/compose.full.yaml --profile postgres ps -a` for crashed services; check logs with `docker compose ... logs <service>` |

---

## Resetting the Database

To completely wipe all R2R data (documents, vectors, users, job history) and start fresh:

### Full Reset (nuclear option)

```bash
# Stop all services and destroy all volumes
docker compose -f docker/compose.full.yaml --profile postgres down -v
```

The `-v` flag removes all named volumes. This deletes:
- All ingested documents, chunks, and vector embeddings (postgres_data)
- Hatchet job history and configuration
- RabbitMQ message queues
- MinIO object storage

After reset, start fresh:

```bash
docker compose -f docker/compose.full.yaml --profile postgres up -d
```

You'll need to re-ingest all documents (Step 4).

### Partial Reset (documents only)

To remove just the ingested documents without resetting Hatchet/orchestration:

```bash
# Delete the R2R postgres volume only
docker compose -f docker/compose.full.yaml --profile postgres down
docker volume rm postgres_data
docker compose -f docker/compose.full.yaml --profile postgres up -d
```

---

## Quick Reference

### Environment Variables

| Variable | Where | Value |
|----------|-------|-------|
| `R2R_API_BASE` | devcontainer (settings.json) | `http://host.docker.internal:7272` |
| `VAULT_PATH` | devcontainer (settings.json) | `/workspace/vault` (must match your bind mount) |
| `R2R_CONFIG_NAME` | host (r2r-full.env) | *(empty — cleared to avoid conflict with `R2R_CONFIG_PATH`)* |
| `R2R_CONFIG_PATH` | host (r2r-full.env) | `/app/user_configs/r2r-ollama-embeddings.toml` |
| `OLLAMA_API_BASE` | host (r2r-full.env) | `http://host.docker.internal:11434` |
| `R2R_API_KEY` | devcontainer (settings.json) | R2R auth key (if configured) |

### All 13 MCP Tools

**r2r** (generic R2R operations):
- `search` — Search R2R documents by query with optional filters
- `ingest_document` — Ingest raw text or pre-chunked content into R2R
- `list_documents` — List documents, optionally filtered by collection
- `delete_document` — Delete a document by ID
- `list_collections` — List all R2R collections

**sourcebooks** (worldbuilding-specific):
- `search_lore` — Hybrid search across sourcebooks, filterable by book and content type
- `list_books` — List all ingested sourcebooks with system/publisher info
- `get_chapter` — Retrieve full chapter text from a specific book

**vault-graph** (Obsidian wikilink navigation):
- `vault_graph` — BFS traversal from a note, showing connections up to N hops
- `vault_backlinks` — List all notes that link to a given note
- `vault_search_notes` — Search notes by name pattern, tag, or type
- `vault_central_notes` — Rank notes by connection count (degree centrality)
- `vault_reload_graph` — Reload `.graph.json` from disk without restarting

### Scripts Reference

| Script | Purpose | Runs on |
|--------|---------|---------|
| `scripts/detect_pdf_type.py` | Classify PDFs as text-native, image-only, or mixed | Host |
| `scripts/ocr_preprocess.py` | Client-side OCR for image PDFs (Tesseract or Surya engine) | Host |
| `scripts/verify_ingestion.py` | Post-ingestion quality check (chunk count, text quality, search coherence) | Host |
| `scripts/build_vault_graph.py` | Parse `[[wikilinks]]` into `.graph.json` | Devcontainer |
| `ingest_books.py` | Bulk-ingest PDFs with folder-based metadata inference | Host |

### Sourcebook Metadata Schema

```json
{
  "book_title": "Core Rulebook"
}
```

> Optional fields: `page_range`, `system`, `publisher`, `content_type`, `chapter` — accepted if provided, gracefully ignored if missing.
