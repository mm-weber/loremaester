# Worldbuilding Assistant — Design Document

## Project Vision

Tabletop RPG game masters maintain rich, interconnected worldbuilding wikis in Obsidian and own libraries of scanned source books (PDFs). Today these two knowledge bases are siloed — the vault is navigable but manual, and the source books are searchable only through clunky PDF readers.

The Worldbuilding Assistant bridges both sources through Claude Code. A GM opens their Obsidian vault as a workspace, and Claude can read, search, and write vault notes using its native file tools while simultaneously querying scanned source books via R2R semantic search. The result: Claude becomes a worldbuilding collaborator that knows the GM's canon *and* the published lore, and can generate new content that's consistent with both.

**Key constraint:** This project does NOT create an Obsidian vault. The GM brings their own vault — their existing worldbuilding is canon. We build the infrastructure around it.

---

## Architecture Overview

The system rests on three pillars:

### 1. Native Claude Tools → Obsidian Vault

Claude Code's built-in `Read`, `Write`, `Grep`, and `Glob` tools operate directly on the vault's markdown files. No middleware needed — the vault is just a directory of `.md` files with `[[wikilinks]]` and YAML frontmatter. A `CLAUDE.md` template (placed in the vault root) teaches Claude the vault's structure, conventions, and how to navigate it.

### 2. R2R Semantic Search → Scanned Source Books

Source books are scanned/image-based PDFs that can't be read with file tools. They're ingested into R2R (a RAG pipeline) for chunking and vector indexing; scanned pages are OCR'd to text first — client-side per-page by default (`scripts/ingest_books.py`, which also captures the scanned pages and figures of *mixed* PDFs), or server-side via Unstructured.io in Full Mode. Claude queries them through MCP tools that wrap R2R's Python SDK, getting back relevant passages with book/chapter/page metadata.

### 3. MCP Servers → Integration Layer

MCP (Model Context Protocol) servers connect Claude to both data sources beyond native file access. Three MCP servers provide structured tool interfaces:
- **R2R wrapper** — generic search/ingest/manage operations against R2R
- **Sourcebooks server** — worldbuilding-specific lore queries with domain language
- **Vault graph server** — wikilink graph navigation from pre-computed graph data

All servers use stdio transport, run as Python processes, and are registered in Claude Code's `settings.json`.

---

## Component Map

| # | Deliverable | Role |
|---|---|---|
| D1 | **Vault CLAUDE.md Template** | Teaches Claude how to read/write the GM's vault — frontmatter schemas, wikilink conventions, folder structure, search tips |
| D2 | **R2R MCP Wrapper** | General-purpose MCP server wrapping R2R's SDK — search, ingest, list, and delete documents and collections |
| D3 | **Sourcebooks MCP Server** | Worldbuilding-domain tools (`search_lore`, `list_books`, `get_chapter`) with TTRPG-aware metadata and hybrid search defaults |
| D4 | **Vault Graph Builder** | CLI script that parses `[[wikilinks]]` from all vault notes and outputs a `.graph.json` adjacency structure |
| D5 | **Vault Graph MCP Server** | MCP tools for navigating the wikilink graph — subgraph traversal, backlinks, centrality ranking, filtered search |
| D6 | **Settings Configuration** | Registers all MCP servers in `.claude/settings.json` with correct paths and environment variables |
| D7 | **Worldbuilding Plugin** | Claude Code skill that orchestrates the full worldbuilding workflow — gather context, search lore, generate, write back |

### How They Connect

```
                    ┌─────────────────────────────────┐
                    │         Claude Code              │
                    │  (native Read/Write/Grep/Glob)   │
                    └──────┬──────────┬──────────┬─────┘
                           │          │          │
                    D1: CLAUDE.md     │          │
                    (vault guidance)  │          │
                           │          │          │
                      ┌────▼────┐ ┌───▼───┐ ┌───▼────┐
                      │ Vault   │ │Source- │ │ Vault  │
                      │ Files   │ │books  │ │ Graph  │
                      │ (direct)│ │MCP(D3)│ │MCP(D5) │
                      └─────────┘ └───┬───┘ └───┬────┘
                                      │         │
                                 ┌────▼───┐ ┌───▼──────┐
                                 │R2R MCP │ │.graph.json│
                                 │(D2)    │ │from D4    │
                                 └────┬───┘ └──────────┘
                                      │
                                 ┌────▼───┐
                                 │R2R     │
                                 │Server  │
                                 └────────┘
```

D7 (the worldbuilding plugin) sits at the top, orchestrating Claude's use of all these tools in a coherent workflow.

---

## Key Design Decisions

### Why separate R2R wrapper (D2) from Sourcebooks server (D3)?

D2 is a **generic, reusable** R2R integration — it exposes raw search, ingest, list, and delete operations with no domain knowledge. It could be used for any R2R-backed project.

D3 is **domain-specific** — it speaks worldbuilding language (`search_lore`, `list_books`, `get_chapter`), enforces a metadata schema for source books (book title, system, publisher, content type, chapter, page range), and defaults to hybrid search because that works best for TTRPG content. It lives in the workspace alongside the other worldbuilding infrastructure.

This separation means the generic R2R integration is reusable across projects, while worldbuilding opinions stay contained in D3.

### Why a pre-computed vault graph (D4) rather than runtime scanning?

Parsing `[[wikilinks]]` from every `.md` file on every query would be slow for large vaults and would make the MCP server complex with filesystem-scanning logic. Instead, D4 pre-computes a `.graph.json` file that D5 loads into memory on startup. This gives:

- **Fast queries** — graph traversal is in-memory dictionary lookups
- **Simple MCP server** — D5 just reads JSON, no filesystem parsing
- **Explicit rebuild cycle** — the GM (or Claude) triggers a rebuild after vault changes via `vault_rebuild_graph` (re-parses vault + reloads cache); `vault_reload_cache` is the cheaper "re-read JSON only" variant that flags staleness when the on-disk graph is behind the vault

### Why hybrid search as the default for lore queries?

Source books contain both natural-language lore and proper nouns (place names, character names, spell names). Pure semantic search misses exact keyword matches for proper nouns; pure keyword search misses conceptual relationships. Hybrid search (combining vector similarity and full-text matching) balances both, which is critical for TTRPG content where a query like "dwarven death rites" needs to match both the concept and specific named rituals.

### Why the GM brings their own vault?

The vault IS the GM's worldbuilding — it represents their canon. Creating a vault from scratch would impose structure that conflicts with how GMs actually organize their worlds. By requiring the GM to bring an existing vault (and customize the CLAUDE.md template for their structure), we respect their existing work and conventions. The assistant adapts to the vault, not the other way around.

### Why MCP as the integration pattern?

MCP is Claude Code's native extension mechanism — stdio-based, composable, and declarative. Each server is a standalone Python process registered in `settings.json`. This means:

- **No custom plugins or patches** — standard Claude Code configuration
- **Independent scaling** — each server can be developed, tested, and restarted independently
- **Composable** — Claude sees all tools from all servers in a unified namespace

---

## Repository Structure

This is a single self-contained repository. R2R is consumed as a Docker image (`sciphiai/r2r`) and pip package (`r2r` for the SDK client). No separate R2R fork or clone is needed.

```
R2R-ClaudeCode-integration/
├── docker/                    # Docker Compose deployment configs
│   ├── compose.yaml           # Light mode (recommended): R2R + Postgres + MinIO
│   ├── compose.infra.yaml     # Shared infrastructure (postgres, hatchet, minio)
│   ├── compose.app.yaml       # Per-instance R2R app (parameterized)
│   ├── compose.full.yaml      # Full mode (all-in-one): + Unstructured.io, Hatchet
│   ├── instances/             # Per-deployment configs (.env, user_configs/)
│   └── env/                   # Environment variable files
├── mcp-servers/
│   ├── r2r-wrapper/           # D2: Generic R2R MCP server (search/ingest/list)
│   ├── sourcebooks/           # D3: Worldbuilding lore search
│   └── vault-graph/           # D5: Wikilink graph navigation
├── scripts/
│   ├── build_vault_graph.py   # D4: Parse [[wikilinks]] → .graph.json
│   ├── detect_pdf_type.py     # Classify PDFs as text-native / image-only / mixed
│   ├── ingest_books.py        # Bulk-ingest PDFs (auto-routes text-native→R2R native, image-only|mixed→ocr_extract hybrid)
│   ├── ocr_preprocess.py      # Standalone OCR via pytesseract/surya (non-ingesting)
│   ├── extract_text.py        # Standalone OCR text extraction (pypdfium2 + tesseract/easyocr)
│   ├── ocr_extract.py         # Shared OCR engine: pypdfium2 render + per-page tesseract/easyocr
│   └── verify_ingestion.py    # Post-ingestion quality checks against R2R
├── plugins/                   # D7: Worldbuilding skill
├── examples/                  # D1: Vault CLAUDE.md template
├── docs/                      # Documentation
├── requirements/              # EARS specifications
└── .github/workflows/         # CI/CD
```

---

## Workflow

A typical worldbuilding session follows this flow:

### 1. Gather Vault Context
Claude uses native tools to understand what already exists:
- `Grep` the vault for mentions of the topic
- `Read` primary notes and follow 1-2 levels of `[[wikilinks]]`
- Use `vault_graph` (D5) to explore the connection neighborhood
- Note what's established as canon

### 2. Search Source Books
Claude queries R2R for published lore:
- `search_lore` (D3) with the topic, optionally scoped by book or content type
- `get_chapter` (D3) for full chapter text when deeper context is needed
- Cross-reference multiple source books for richer inspiration

### 3. Generate Content
Claude synthesizes both sources:
- Vault canon takes priority — never contradict established worldbuilding
- Source book lore is inspiration — adapt and integrate, don't copy verbatim
- New content follows the vault's frontmatter schema, tag conventions, and voice
- `[[Wikilinks]]` are created to connect new content to existing notes

### 4. Write to Vault
Claude writes the results back:
- New notes placed in the correct vault folder
- Frontmatter matches the vault's schema (type, tags)
- Related existing notes updated with backlinks to the new content
- Summary presented to the GM for review

### 5. Graph Rebuild
After vault changes, the graph is rebuilt:
- Call `vault_rebuild_graph` (D5) — re-parses the vault and reloads the in-memory cache in one step, no server restart needed. (The bare `build_vault_graph.py` CLI still works for external automation.)

---

## Verification Strategy

### Unit: Vault Graph (D4 + D5)
Create a small test vault with known `[[wikilinks]]`, run the graph builder, and verify the JSON structure. Start the vault graph MCP server and confirm tools return correct subgraphs, backlinks, and centrality rankings. No external dependencies — pure filesystem and JSON.

### Smoke: R2R Integration (D2 + D3)
With R2R running, exercise the full document lifecycle through the MCP wrapper: ingest a test document, list it, search for it, then delete it. For the sourcebooks server, verify that `search_lore` returns results with correct book/chapter/page metadata and that `list_books` groups documents properly.

### End-to-End: Worldbuilding Session
Mount a vault, start all MCP servers, and run a complete worldbuilding interaction:
1. Ask about an existing topic — verify Claude reads the vault and follows wikilinks
2. Ask for source book research — verify Claude uses `search_lore`
3. Ask Claude to create a new note — verify correct folder placement, frontmatter, wikilinks, and backlink updates
4. Rebuild the graph — verify the new note appears in the graph with correct connections
