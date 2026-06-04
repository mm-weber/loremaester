# Quickstart: Worldbuilding Assistant for Claude Code

> **First time here?** If you want to see the product work end-to-end against bundled demo content (3 sourcebooks, the `Grunvyr_Campaign` vault scaffold, all four GM skills) before configuring your own vault, run through [`demo-walkthrough.md`](./demo-walkthrough.md) first. This quickstart is the reference for setting up *your own* content.

Turn Claude Code into a worldbuilding collaborator that knows your Obsidian vault AND your sourcebooks.

Set up R2R semantic search with Ollama embeddings, ingest your PDF sourcebooks (including scanned/image PDFs), connect your vault, and run your first worldbuilding session — all in one guide.

---

## Architecture Overview

```
  HOST MACHINE                                    DEVCONTAINER
 +-------------------------------+              +------------------------------+
 |                               |              |  Claude Code                 |
 |  Ollama (:11434)              |              |    +- r2r MCP server         |
 |  +- mxbai-embed-large         |              |    +- sourcebooks MCP server  |
 |     (embedding model only)    |              |    +- vault-graph MCP server  |
 |                               |              |    +- worldbuilding skill     |
 |  R2R Server (:7272)           |<------------>|                              |
 |  +- PostgreSQL + pgvector     |  host.       |  Obsidian vault (bind mount) |
 |  +- Unstructured.io (OCR)    |  docker.     |  .graph.json                 |
 |  +- Hatchet (orchestration)  |  internal    |                              |
 |                               |  :7272       |                              |
 |  R2R Dashboard (:7273)        |              |                              |
 |                               |              |                              |
 |  PDF ingestion                |              |                              |
 |  (r2r CLI / SDK / scripts)   |              |                              |
 +-------------------------------+              +------------------------------+
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

### 2a. Docker Compose files and helper scripts

Everything needed to run R2R lives under `docker/` — you don't need to clone R2R separately.

| Path | What it is |
|------|------------|
| `docker/compose.full.yaml` | Single-instance full-mode stack — **used by this guide** |
| `docker/compose.yaml` | Light mode (R2R without Hatchet/Unstructured) — not covered here |
| `docker/compose.infra.yaml` + `docker/compose.app.yaml` | Multi-instance deployment path — see note at the end of this step |
| `docker/env/` | Env files that compose loads via `env_file:` directives (bootstrapped in Step 2c) |
| `docker/user_configs/` | R2R's TOML configuration, bind-mounted into the container at `/app/user_configs/` |
| `docker/scripts/` | Container-side init/startup scripts |

> **About `docker/scripts/`.** You don't invoke these yourself. Three of them — `create-hatchet-db.sh` (creates the Hatchet DB), `setup-token.sh` (generates the Hatchet API key), and `start-r2r.sh` (boots the R2R process) — are bind-mounted into the `hatchet-create-db`, `setup-token`, and `r2r` containers respectively and run as their entrypoints. The remaining two (`r2r-infra.sh`, `r2r-instance.sh`) are host-side helpers for the multi-instance deployment path and can be ignored for this guide.

### 2b. R2R Config (Embeddings Only)

Since Claude Code handles all reasoning, R2R only needs an embedding configuration. A ready-to-use config is provided at `docker/user_configs/r2r-ollama-embeddings.toml` — no changes needed.

The config sets up:
- `[embedding]` / `[completion_embedding]` — Tells R2R to use Ollama's `mxbai-embed-large` for converting text to vectors
- `[ingestion]` — Uses Unstructured.io (running as a Docker service) for PDF parsing, including OCR for scanned documents. `skip_document_summary` and `automatic_extraction` are set to disable LLM calls (we use Ollama for embeddings only, not completions)
- `[orchestration]` — Uses Hatchet for managing async ingestion jobs

The env var pointing R2R at this file (`R2R_CONFIG_PATH`) is pre-set in `r2r-full.env.example` — you only touch it if you want to swap in a different config.

### 2c. Bootstrap the environment files

`compose.full.yaml` loads per-service settings from files in `docker/env/`. Those `.env` files are **gitignored** (they typically hold service credentials), so the repo ships `*.env.example` templates you copy before starting the stack.

| Env file | Loaded by | Required for `--profile postgres`? |
|----------|-----------|------------------------------------|
| `r2r-full.env` | the `r2r` service | **Yes** |
| `postgres.env` | the `postgres` service | **Yes** — you passed `--profile postgres` |
| `hatchet.env` | all 7 `hatchet-*` services | **Yes** — Hatchet services have no profile and always start |
| `r2r-dashboard.env` | the `r2r-dashboard` service | **Yes** — dashboard needs the R2R and Hatchet URLs |
| `minio.env` | the `minio` service | No — only loaded with `--profile minio` |

Copy the templates:

```bash
cd docker/env/
cp postgres.env.example       postgres.env
cp hatchet.env.example        hatchet.env
cp r2r-full.env.example       r2r-full.env
cp r2r-dashboard.env.example  r2r-dashboard.env
cp minio.env.example          minio.env   # optional — only needed with --profile minio
cd -
```

The shipped defaults are safe for local, single-user development:
- Postgres credentials are `postgres`/`postgres`; Hatchet's are `hatchet_user`/`hatchet_password`.
- `OLLAMA_API_BASE=http://host.docker.internal:11434` — lets the R2R container reach Ollama running on your host.
- `R2R_CONFIG_PATH=/app/user_configs/r2r-ollama-embeddings.toml` — points at the TOML from Step 2b (`docker/user_configs/` is bind-mounted to `/app/user_configs/` inside the container).
- No provider API keys are populated; Claude Code handles all LLM work, so none are needed.

> **When would you edit these?** If you change Postgres credentials in `postgres.env`, update the matching `R2R_POSTGRES_*` vars in `r2r-full.env` so they stay in sync. `R2R_CONFIG_NAME` and `R2R_CONFIG_PATH` are **mutually exclusive** — if you switch to a built-in R2R config preset, clear `R2R_CONFIG_PATH` and set `R2R_CONFIG_NAME`. Ports are defined in `compose.full.yaml`, not the env files.

> **Security note.** The defaults in `*.env.example` are for local development only. Change every credential (Postgres passwords, RabbitMQ, the dashboard login) before exposing R2R on a shared network.

> **Not using this guide's compose file?** `docker/env/r2r.env` is for `compose.yaml` (light mode) and isn't created by this flow. Stick to the five files above for `compose.full.yaml`.

### 2d. Start the Full Stack

From the repository root:

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

> **Multi-instance deployment:** For running multiple R2R instances (e.g., separate vaults), see `docker/compose.infra.yaml` and `docker/compose.app.yaml` with per-instance configs in `docker/instances/`.

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
+-- Don't know
|   +-- Run: python scripts/detect_pdf_type.py /path/to/pdfs/
+-- Yes -- pick an OCR path:
|   +-- Server-side (Docker Full Mode): ingest the PDF *directly* so R2R/Unstructured.io OCRs it
|   |       e.g. r2r documents create book.pdf --metadata '{"book_title":"..."}'   (no client OCR deps)
|   +-- Client-side (any mode): scripts/ingest_books.py auto-OCRs image PDFs via Kreuzberg/EasyOCR
|           (EasyOCR needs torch+CUDA; set KREUZBERG_OCR_ENGINE=tesseract for CPU)
+-- No, they're text-native
    +-- Ingest directly, or via scripts/ingest_books.py (Step 4)
```

> **Which tool does which OCR?** If you ingest an image PDF **directly** (single-PDF `r2r documents create`, or the `r2r` MCP `ingest_document`) in Docker Full Mode, R2R/Unstructured.io OCRs it server-side. The bulk helper `scripts/ingest_books.py` instead OCRs image PDFs **client-side** via Kreuzberg (Step 4), in any mode — so you choose the OCR path by choosing the tool.

---

## Step 4 — Ingest Sourcebooks from a Folder

### Folder Structure

Drop your PDFs into a flat folder — no special directory hierarchy needed:

```
sourcebooks/
+-- Core_Rulebook_PF2e.pdf
+-- Lost_Omens_World_Guide.pdf
+-- Campaign_Setting_Boxed_Set.pdf
+-- Bestiary_PF2e.pdf
```

### Metadata Schema

Only `book_title` is required. The sourcebooks MCP server uses it for `search_lore`, `list_books`, and `get_chapter`.

| Field | Type | Required? | Example | Purpose |
|-------|------|-----------|---------|---------|
| `book_title` | string | **Yes** | `"Lost Omens World Guide"` | Filtering in `search_lore`, `list_books`, `get_chapter` |
| `page_range` | string | No | `"pp. 1-312"` | Display in search results |

> **Note:** The server also accepts `system`, `publisher`, `content_type`, and `chapter` if provided — they just aren't required.

### Single PDF

```bash
# Install the R2R CLI if not already available
uv pip install r2r

r2r documents create /path/to/book.pdf \
  --metadata '{"book_title": "Core Rulebook"}'
```

### Bulk Ingestion Script

The repo ships `scripts/ingest_books.py`, a PEP 723-style single-file script
that bulk-ingests a folder of PDFs with automatic image-vs-text routing,
SHA1 content-hash deduplication, and client-side OCR for scanned books:

- **Text-native PDFs** → forwarded to R2R via `documents.create(file_path=…)`.
  In Docker Full Mode this means Unstructured.io parses them server-side.
- **Image-only PDFs** (detected by pdfplumber: <10% of pages have extractable
  text) → OCR'd client-side via [Kreuzberg](https://kreuzberg.dev/) with
  EasyOCR as the default backend (GPU-accelerated via torch+CUDA), then
  pushed to R2R as `raw_text`.

Run it with `uv run` — the script declares its own dependencies inline:

```bash
uv run --no-project --python 3.12 \
  --extra-index-url https://download.pytorch.org/whl/cu126 \
  --index-strategy unsafe-best-match \
  scripts/ingest_books.py /path/to/sourcebooks/
```

The two uv flags are needed because the script pins `torch==2.9.1+cu126`, a
local-version variant only published on PyTorch's own index. Skip them and
uv won't find the CUDA-bound wheel. (See Troubleshooting if you hit
`driver too old` or dependency-resolution errors.)

#### OCR backend selection

The default (`easyocr`) runs on GPU via torch+CUDA and needs no extra
system packages. Two env-var overrides if you want to swap backends:

```bash
# Tesseract — CPU only. Requires `apt install tesseract-ocr tesseract-ocr-eng`
KREUZBERG_OCR_ENGINE=tesseract KREUZBERG_OCR_LANGUAGE=eng \
  uv run --no-project --python 3.12 scripts/ingest_books.py <pdf-dir>

# PaddleOCR — needs paddlepaddle-gpu from PaddlePaddle's own index (not pinned
# here because it doesn't live on PyPI). Only worth the trouble for languages
# EasyOCR doesn't cover well.
```

Note the language code difference: `easyocr`/`paddleocr` take ISO 639-1
two-letter codes (`en`, `de`), tesseract takes ISO 639-3 three-letter
codes (`eng`, `deu`).

### Ingesting Image PDFs Without Docker Full Mode

`scripts/ingest_books.py` OCRs scanned books **client-side** via Kreuzberg in
any R2R mode, so it works even in Light Mode (no Unstructured.io needed). If you'd
rather OCR server-side, ingest image PDFs directly in Docker Full Mode (see Step 3b).

For one-off OCR experiments outside the ingestion flow (e.g., extracting
text from a single image or PDF without pushing to R2R),
`scripts/ocr_preprocess.py` wraps pytesseract/surya-ocr as an
alternative — see its `--help` for flags.

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
      "args": ["/path/to/repo/mcp-servers/r2r-wrapper/r2r_mcp_wrapper.py"],
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
| **vault-graph** | `vault_graph`, `vault_backlinks`, `vault_search_notes`, `vault_central_notes`, `vault_reload_cache`, `vault_rebuild_graph` | `VAULT_PATH` |

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

You should see 3 servers connected with 14 tools total:
- `r2r` — 5 tools
- `sourcebooks` — 3 tools
- `vault-graph` — 6 tools

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
7. Calls `vault_rebuild_graph()` to re-parse the vault and refresh the graph
