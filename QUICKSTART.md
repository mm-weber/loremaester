# Quickstart: Worldbuilding Assistant for Claude Code

Turn Claude Code into a worldbuilding collaborator that knows your Obsidian vault AND your sourcebooks.

Set up R2R semantic search, connect your vault, and run your first worldbuilding session — all in one guide.

---

## Architecture Overview

```
  HOST MACHINE                         DEVCONTAINER
 ┌──────────────────────┐            ┌──────────────────────────────┐
 │                      │            │  Claude Code                 │
 │  R2R Server (:7272)  │◄──────────►│    ├─ r2r MCP server         │
 │  PostgreSQL          │  host.     │    ├─ sourcebooks MCP server  │
 │  Embeddings (OpenAI  │  docker.   │    ├─ vault-graph MCP server  │
 │   or Ollama)         │  internal  │    └─ worldbuilding skill     │
 │                      │  :7272     │                              │
 │  PDF ingestion       │            │  Obsidian vault (bind mount) │
 │  (r2r CLI / SDK)     │            │  .graph.json                 │
 └──────────────────────┘            └──────────────────────────────┘
```

### Components

| # | Component | What it does |
|---|-----------|--------------|
| 1 | **Vault CLAUDE.md** | Teaches Claude your vault's structure, frontmatter schemas, wikilink conventions |
| 2 | **R2R MCP Wrapper** | Generic search/ingest/list/delete against R2R |
| 3 | **Sourcebooks MCP Server** | Worldbuilding-specific lore queries (`search_lore`, `list_books`, `get_chapter`) |
| 4 | **Vault Graph Builder** | Parses `[[wikilinks]]` into `.graph.json` |
| 5 | **Vault Graph MCP Server** | Graph traversal, backlinks, centrality ranking |
| 6 | **Worldbuilding Skill** | Orchestrates the full workflow: gather context, research lore, generate, write back |

> **Why does R2R live on the host?** R2R runs PostgreSQL with pgvector, an embedding pipeline, and optionally Unstructured.io for PDF parsing. These are heavy services that don't belong inside a devcontainer. The devcontainer talks to R2R over the Docker bridge network via `host.docker.internal:7272`.

---

## Prerequisites

- [ ] Claude Code running inside a devcontainer
- [ ] Python 3.10+ on the host machine
- [ ] An Obsidian vault with TTRPG worldbuilding notes
- [ ] PDF sourcebooks (optional — the system works with just the vault)
- [ ] Docker + Docker Compose on the host (for R2R full mode) OR just Python (for light mode)
- [ ] OpenAI API key OR local Ollama instance (for embeddings)

---

## Step 1 — Set Up R2R on the Host

Pick one path. Light mode gets you running fastest; Docker full mode gives better PDF parsing.

### Path A: Light Mode (quickest)

```bash
pip install r2r
# or: uv pip install r2r

export OPENAI_API_KEY=sk-...

r2r serve
```

Verify it's running:

```bash
curl http://localhost:7272/v3/health
```

You should see `{"results":{"response":"ok"}}`.

### Path B: Docker Full Mode (recommended for real use)

```bash
git clone https://github.com/SciPhi-AI/R2R.git
cd R2R

# Start R2R with PostgreSQL and Unstructured.io
docker compose -f compose.full.yaml up -d
```

**Why full mode?** The full stack includes [Unstructured.io](https://unstructured.io/), a document parsing library that understands complex PDF layouts. TTRPG sourcebooks have multi-column layouts, stat blocks, tables, and sidebars that confuse basic text extractors. Without Unstructured, columns mash together and stat blocks garble. With it, tables stay tabular and text flows correctly.

The tradeoff: requires Docker, uses more resources, and ingestion is slower — but the quality of extracted text is much higher for sourcebooks.

Verify:

```bash
curl http://localhost:7272/v3/health
```

---

## Step 2 — Ingest Your Sourcebooks

PDF ingestion happens on the **host** via the R2R CLI or SDK — not through the MCP server (the MCP wrapper only supports `raw_text`/`chunks`, not `file_path`).

### Metadata Schema

The sourcebooks MCP server expects these metadata fields. Include them during ingestion so `search_lore`, `list_books`, and `get_chapter` work correctly.

| Field | Type | Example | Used by |
|-------|------|---------|---------|
| `book_title` | string | `"Core Rulebook"` | `list_books()`, `search_lore(book=)` |
| `chapter` | string | `"Chapter 3"` | `get_chapter()` |
| `page_range` | string | `"pp. 45-52"` | search result display |
| `content_type` | string | `"lore"` / `"rules"` / `"bestiary"` | `search_lore(content_type=)` |
| `system` | string | `"Pathfinder 2e"` | `list_books()` display |
| `publisher` | string | `"Paizo"` | `list_books()` display |

### Single PDF

```bash
r2r documents create /path/to/book.pdf \
  --metadata '{"book_title": "Core Rulebook", "system": "Pathfinder 2e", "publisher": "Paizo", "chapter": "Chapter 3", "page_range": "pp. 45-52", "content_type": "lore"}'
```

### Bulk Ingestion Script

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
        print("Usage: python ingest_books.py <pdf_directory>")
        print("Directory structure: <pdf_directory>/<System>/<Publisher>/book.pdf")
        sys.exit(1)

    pdf_dir = Path(sys.argv[1])
    client = R2RClient(R2R_BASE)

    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) in {pdf_dir}\n")

    for pdf in pdfs:
        # Infer system/publisher from directory structure if present
        parts = pdf.relative_to(pdf_dir).parts
        system = parts[0] if len(parts) > 2 else "Unknown"
        publisher = parts[1] if len(parts) > 2 else "Unknown"
        book_title = pdf.stem.replace("_", " ").replace("-", " ").title()

        metadata = {
            "book_title": book_title,
            "system": system,
            "publisher": publisher,
            "content_type": "lore",
        }

        print(f"[{book_title}] system={system}, publisher={publisher}")
        ingest_pdf(client, pdf, metadata)

    print(f"\nDone. Ingested {len(pdfs)} book(s).")

if __name__ == "__main__":
    main()
```

### Verify Ingestion

```bash
# List all documents
curl http://localhost:7272/v3/documents | python -m json.tool

# Or check the R2R dashboard (if running full mode)
# Open http://localhost:7273 in your browser
```

---

## Step 3 — Prepare Your Obsidian Vault

### 3a. Make the vault accessible inside the devcontainer

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

### 3b. Add a CLAUDE.md to your vault

Copy the template and fill in your details:

```bash
cp examples/vault-claude-md-template.md /workspace/vault/CLAUDE.md
```

Open `/workspace/vault/CLAUDE.md` and replace the placeholders:

- `YOUR_SYSTEM` — your game system (e.g., `Pathfinder 2e`, `D&D 5e`)
- `YOUR_WORLD` — your world name (e.g., `Golarion`, `Forgotten Realms`)
- `YOUR_CAMPAIGN` — your campaign name (e.g., `Kingmaker 2e`)
- Update the folder structure tree to match your vault layout

### 3c. Build the wikilink graph

Inside the devcontainer:

```bash
pip install pyyaml --break-system-packages

python scripts/build_vault_graph.py /workspace/vault
```

Expected output:

```
Graph built: 142 notes, 387 edges → /workspace/vault/.graph.json
```

The note and edge counts will vary based on your vault size.

---

## Step 4 — Configure Claude Code MCP Servers

### 4a. Install Python dependencies in the devcontainer

```bash
pip install mcp r2r pyyaml --break-system-packages
```

Or with a virtual environment:

```bash
python -m venv .venv && source .venv/bin/activate
pip install mcp r2r pyyaml
```

### 4b. Edit `.claude/settings.json`

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

`VAULT_PATH` must match the mount target from Step 3a.

### 4c. MCP Server Reference

| Server | Tools | Env Vars |
|--------|-------|----------|
| **r2r** | `search`, `ingest_document`, `list_documents`, `delete_document`, `list_collections` | `R2R_API_BASE`, `R2R_API_KEY` |
| **sourcebooks** | `search_lore`, `list_books`, `get_chapter` | `R2R_API_BASE` |
| **vault-graph** | `vault_graph`, `vault_backlinks`, `vault_search_notes`, `vault_central_notes`, `vault_reload_graph` | `VAULT_PATH` |

### 4d. Linux Networking Workaround

On Linux hosts, `host.docker.internal` may not resolve by default. Add this to your `devcontainer.json`:

```jsonc
{
  "runArgs": [
    "--add-host=host.docker.internal:host-gateway"
  ]
}
```

Then rebuild the container.

### 4e. Verify

Restart Claude Code, then run:

```
/mcp
```

You should see 3 servers connected with 13 tools total:
- `r2r` — 5 tools
- `sourcebooks` — 3 tools
- `vault-graph` — 5 tools

---

## Step 5 — Install the Worldbuilding Skill

Copy the skill into your Claude Code skills directory:

```bash
mkdir -p .claude/skills/worldbuilding
cp plugins/worldbuilding/SKILL.md .claude/skills/worldbuilding/SKILL.md
```

The skill auto-triggers on worldbuilding requests — creating NPCs, factions, locations, researching lore, or expanding your world. You don't need to invoke it manually.

---

## Step 6 — Your First Session

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
| "No books found" from `list_books` | PDFs not ingested with metadata | Re-ingest with `book_title` in the metadata dict (see Step 2) |
| `ImportError: No module named 'r2r'` | SDK not installed in devcontainer | `pip install r2r --break-system-packages` |
| `host.docker.internal` doesn't resolve | Linux without gateway config | Add `"--add-host=host.docker.internal:host-gateway"` to `runArgs` in `devcontainer.json` |

---

## Quick Reference

### Environment Variables

| Variable | Where | Value |
|----------|-------|-------|
| `R2R_API_BASE` | devcontainer (settings.json) | `http://host.docker.internal:7272` |
| `VAULT_PATH` | devcontainer (settings.json) | `/workspace/vault` (must match your bind mount) |
| `OPENAI_API_KEY` | host (for R2R embeddings) | Your OpenAI API key |
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

### Sourcebook Metadata Schema

```json
{
  "book_title": "Core Rulebook",
  "chapter": "Chapter 3",
  "page_range": "pp. 45-52",
  "content_type": "lore",
  "system": "Pathfinder 2e",
  "publisher": "Paizo"
}
```

Valid `content_type` values: `lore`, `rules`, `bestiary`, `adventure`, `setting`, `appendix`
