# Loremaester: Design Document

## Project Vision

Tabletop RPG game masters maintain rich, interconnected worldbuilding wikis in Obsidian and own libraries of scanned source books (PDFs). Today these two knowledge bases are siloed — the vault is navigable but manual, and the source books are searchable only through clunky PDF readers.

Loremaester bridges both sources through Claude Code. A GM opens their Obsidian vault as a workspace, and Claude can read, search, and write vault notes using its native file tools while simultaneously querying scanned source books via R2R semantic search. The result: Claude becomes a worldbuilding collaborator that knows the GM's canon *and* the published lore, and can generate new content that's consistent with both.

**Key constraint:** This project does NOT create an Obsidian vault. The GM brings their own vault — their existing worldbuilding is canon. We build the infrastructure around it.

---

## Architecture Overview

The system rests on three pillars:

### 1. Native Claude Tools → Obsidian Vault

Claude Code's built-in `Read`, `Write`, `Grep`, and `Glob` tools operate directly on the vault's markdown files. No middleware needed — the vault is just a directory of `.md` files with `[[wikilinks]]` and YAML frontmatter. A `CLAUDE.md` template (placed in the vault root) teaches Claude the vault's structure, conventions, and how to navigate it.

### 2. R2R Semantic Search → Scanned Source Books

Source books are scanned/image-based PDFs that can't be read with file tools. They're ingested into R2R (a RAG engine, used here for retrieval only) for chunking and vector indexing; scanned pages are OCR'd to text first — client-side per-page by default (`scripts/ingest_books.py`, which also captures the scanned pages and figures of *mixed* PDFs), or server-side via Unstructured.io in Full Mode. Claude queries them through MCP tools that wrap R2R's Python SDK, getting back relevant passages with book/chapter/page metadata.

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

### Why retrieval-only (R2R), not classic RAG?

Classic RAG is a pipeline that owns both halves — retrieve *and* generate — with an LLM wired inside it (R2R's `/rag` endpoint, had we set a `[completion]` provider). We deliberately split them: **R2R retrieves; Claude Code reasons.** Retrieval is one tool in an agent loop that also reads/writes the vault and walks the wikilink graph.

```
Classic RAG:  query → [ embed → search → stuff prompt → GENERATOR LLM ] → answer   (LLM lives inside R2R)

Ours:         Claude Code (planner + reasoner + writer)
                 ├─ search_lore ─► R2R /retrieval/search ─► ranked chunks + book/ch/page
                 ├─ Read / Grep ─► vault files (the GM's canon)
                 ├─ vault_graph ─► wikilink graph (human-authored)
                 └─ synthesize → ask user → Write note → rebuild graph
              (R2R is a leaf tool; Claude is the brain, above and outside it)
```

| | Classic RAG | Ours (retrieval-only + agent) |
|---|---|---|
| Synthesis | an LLM inside R2R | Claude Code (the host agent) |
| LLMs to run | ≥1 generator in R2R (+ maybe a reranker) | none in R2R; one reasoner (Claude) |
| Sources fused | one corpus | sourcebooks + vault canon + wikilink graph |
| Output | an answer string (+citations) | new content written back to the vault |
| Query expansion / rerank | pipeline stages (HyDE, RAG-fusion, rerank) | the agent re-queries and filters itself |
| Cost / latency | per-query generation; low, predictable | embeddings free; higher, variable (tool loop) |
| Best for | scalable, cited Q&A over a corpus | single-user, multi-source, write-back reasoning |

Two things make the split decisive here:
1. **Multi-source fusion with a priority rule** — vault canon outranks sourcebook lore. Weighing two sources by precedence is per-request reasoning the agent does; a single-corpus retrieve→generate has nowhere to put that rule.
2. **Action, not Q&A** — the deliverable is a frontmatter-correct note saved to the right folder and a refreshed graph. A RAG pipeline returns text; it can't *do* the work.

Trade-offs we accept: more tokens/latency per task than one tight generate, less determinism, and no turnkey `/rag` endpoint — citation discipline lives in the skills, not a tuned pipeline. If the goal were scalable, low-latency, multi-tenant *"chat with your sourcebooks,"* classic RAG (enable R2R's `[completion]` + `/rag`, add a reranker) would be the better tool. Skipping GraphRAG follows the same logic — the human-authored vault graph already supplies relationship-aware context without LLM extraction.

### Why hybrid search as the default for lore queries?

Source books contain both natural-language lore and proper nouns (place names, character names, spell names). Pure semantic search misses exact keyword matches for proper nouns; pure keyword search misses conceptual relationships. Hybrid search (combining vector similarity and full-text matching) balances both, which is critical for TTRPG content where a query like "dwarven death rites" needs to match both the concept and specific named rituals.

**What R2R offers vs. what we use.** R2R can search by semantic (pgvector) similarity, full-text (Postgres `tsvector`) matching, **hybrid** (both, fused via Reciprocal Rank Fusion), or a knowledge graph; and it can run retrieval-only (`/retrieval/search`), retrieval + LLM (`/retrieval/rag`), or agentic RAG. We use **retrieval-only, chunk-level search**: the `sourcebooks` server defaults to **hybrid** (`search_lore`, `get_chapter`); the generic `r2r-wrapper` does **semantic** by default. R2R never runs an LLM here — no completion provider is configured, so Claude Code is the sole reasoner. Knowledge-graph search is off (`automatic_extraction = false`, and extraction would itself need an LLM); HyDE / RAG-fusion query strategies and rerankers are likewise unused.

**Lexical leg: Postgres full-text, not Okapi BM25.** R2R's hybrid keyword side runs on Postgres' built-in full-text search (`tsvector` + `ts_rank`/`ts_rank_cd`), not a dedicated **BM25** engine. The dense leg is identical to a "BM25 hybrid" (pgvector + mxbai-embed-large), so only the keyword leg differs:

| | Our hybrid | "BM25 hybrid" |
|---|---|---|
| Keyword leg | Postgres `tsvector` + `ts_rank`/`ts_rank_cd` | Okapi BM25 (OpenSearch, or ParadeDB `pg_search`) |
| Term-rarity weighting (IDF) | none | yes — rare names count for more |
| TF saturation / length norm | optional, coarse | built-in (`k1`, `b`) |
| Infrastructure | reuses the Postgres already running for pgvector | extra service, or a Postgres extension |

For a single-user, modest, proper-noun-heavy corpus the Postgres-FTS hybrid is the right trade-off. RRF fuses on *rank*, not absolute lexical score, so `ts_rank`'s missing IDF rarely changes the final order; and the keyword leg's main job here — exact name matches like "Stonecrown" — is served by `tsvector` regardless. BM25's advantages (IDF on mixed queries, length normalization, multi-keyword precision) widen with corpus size, so BM25 is worth adopting only once the library grows large/heterogeneous or keyword-heavy queries dominate. Because R2R's hybrid is wired to native Postgres full-text, that switch is an **architectural change** (R2R support, or a custom retrieval path via `pg_search`) — not a config flag — and is tracked as a **v0.2 option**. The first-order win is adding *any* keyword leg to pure-vector search, which is already captured; BM25 would be a second-order refinement.

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
loremaester/
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
├── skills/                    # D7: Claude Code skills (worldbuilding, session-creation, chronik, vault-scout)
├── evals/                     # D7: skill evaluation harness (with-skill vs without-skill)
├── examples/                  # D1: Vault CLAUDE.md template + bundled TTRPG demo (examples/ttrpg/)
├── docs/                      # Documentation
├── specs/                     # EARS specifications
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
