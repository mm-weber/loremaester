# Requirements: R2R + Claude Code MCP Integration

> **Date**: 2026-03-08
>
> **Architecture**: See [ARCHITECHTURE_beta.md](./ARCHITECHTURE_beta.md)
>
> **Phase 1** tasks are detailed with SDK mappings, parameters, and acceptance criteria.
> **Phases 2–3** are at summary level.

---

## Phase 1: Core MVP — "Ingest, Search, Manage from Claude Code"

### P1-01: MCP Wrapper Skeleton

**Description**: Create `r2r_mcp_wrapper.py` with FastMCP boilerplate and R2R SDK client initialization.

**Implementation**:
- FastMCP server with stdio transport
- `R2RClient` configured from environment variables
- Import fallback for local fork

```python
# SDK import strategy
try:
    from r2r import R2RClient
except ImportError:
    import sys
    sys.path.insert(0, "/workspace/repos/R2R/main/py/")
    from r2r import R2RClient

# Client initialization
client = R2RClient(
    base_url=os.environ.get("R2R_API_BASE", "http://localhost:7272"),
    api_key=os.environ.get("R2R_API_KEY")
)
```

**Environment Variables**:
| Variable | Required | Default | Description |
|---|---|---|---|
| `R2R_API_BASE` | No | `http://localhost:7272` | R2R server base URL |
| `R2R_API_KEY` | No | `None` | API key for authenticated R2R instances |

**Dependencies**: None

**Size**: Small (~30 LOC)

**Acceptance Criteria**:
- [ ] `python r2r_mcp_wrapper.py` starts a stdio MCP server without errors
- [ ] FastMCP reports server name and version on startup
- [ ] `R2RClient` initializes from env vars (or defaults)
- [ ] Import fallback works when `r2r` is not pip-installed

---

### P1-02: `search` Tool

**Description**: Expose R2R's retrieval.search as an MCP tool with configurable search settings.

**SDK Method**: `client.retrieval.search(query, search_mode, search_settings)`

**SDK Types**:
```python
# SearchSettings fields to expose
SearchSettings(
    filters: dict,          # Metadata filter expressions
    limit: int,             # Max chunks returned (default=5)
    use_hybrid_search: bool,# Combine vector + keyword search
    search_strategy: str,   # "vanilla" | "hyde" | "query_fusion"
    include_metadatas: bool,# Return metadata with chunks (default=True)
    include_scores: bool    # Return relevance scores (default=True)
)
```

**Tool Parameters**:
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `str` | Yes | — | Natural language search query |
| `collection_ids` | `list[str]` | No | `None` | Scope search to specific collections |
| `filters` | `dict` | No | `None` | Metadata filter expressions (e.g., `{"source_type": {"$eq": "pdf"}}`) |
| `limit` | `int` | No | `5` | Maximum number of chunks to return |
| `search_mode` | `str` | No | `None` | Search mode passthrough to R2R |

**Response Format**:
```text
## Search Results for: "{query}"

### Result 1 (score: 0.87)
[Source: design-doc.pdf | Type: pdf | Date: 2026-03-01]
The authentication module uses JWT tokens with a 24-hour expiry...

### Result 2 (score: 0.72)
[Source: api-spec.md | Type: markdown | Date: 2026-02-15]
All API endpoints require Bearer token authentication...

---
Returned 2 of 2 chunks | Collection: default
```

**Dependencies**: P1-01

**Size**: Medium (~40 LOC)

**Acceptance Criteria**:
- [ ] Search returns ranked chunks with metadata headers
- [ ] `limit` parameter is respected (request 3, get ≤3)
- [ ] `collection_ids` filter scopes results correctly
- [ ] `filters` parameter passes through to `SearchSettings`
- [ ] No answer synthesis — returns raw chunks only
- [ ] Scores included in output when available

---

### P1-03: `ingest_document` Tool

**Description**: Ingest text or pre-chunked content into R2R with metadata.

**SDK Method**: `client.documents.create(file_path?, raw_text?, chunks?, s3_url?, id?, collection_ids?, metadata?, ingestion_mode?)`

**Note**: `file_path` requires server-side filesystem access. For MVP, only `raw_text` and `chunks` are supported. File-based ingestion is a Phase 3 concern (via client-side preprocessing).

**Tool Parameters**:
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `raw_text` | `str` | No* | — | Plain text content to ingest |
| `chunks` | `list[str]` | No* | — | Pre-chunked text segments |
| `metadata` | `dict` | No | `{}` | Document metadata (see P1-07 schema) |
| `collection_ids` | `list[str]` | No | `None` | Collections to add the document to |
| `title` | `str` | No | `None` | Human-readable document title |

\* At least one of `raw_text` or `chunks` must be provided.

**Response Format**:
```text
Document ingested successfully.
  ID: 3fa85f64-5717-4562-b3fc-2c963f66afa6
  Title: "Design Document v2"
  Status: processing
  Collections: [default]
```

**Dependencies**: P1-01

**Size**: Medium (~35 LOC)

**Acceptance Criteria**:
- [ ] Ingest raw text → document appears in `list_documents`
- [ ] Ingest pre-chunked content → chunks preserved as-is
- [ ] Metadata attached to document
- [ ] Returns document ID and ingestion status
- [ ] Error on missing both `raw_text` and `chunks`

---

### P1-04: `list_documents` Tool

**Description**: List documents in the knowledge base, optionally filtered by collection.

**SDK Method**: `client.documents.list(ids?, offset?, limit?)` or `client.collections.list_documents(id, offset?, limit?)`

**Tool Parameters**:
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `collection_id` | `str` | No | `None` | Filter to a specific collection |
| `offset` | `int` | No | `0` | Pagination offset |
| `limit` | `int` | No | `20` | Maximum documents to return |

**Response Format**:
```text
## Documents (showing 1–3 of 12)

1. **Design Document v2** (3fa85f64...)
   Type: pdf | Chunks: 47 | Ingested: 2026-03-01 | Status: completed

2. **API Specification** (7cb91a22...)
   Type: markdown | Chunks: 23 | Ingested: 2026-02-15 | Status: completed

3. **Meeting Notes Q1** (9de42b11...)
   Type: text | Chunks: 8 | Ingested: 2026-03-05 | Status: completed
```

**Dependencies**: P1-01

**Size**: Small (~25 LOC)

**Acceptance Criteria**:
- [ ] Returns document IDs, titles, metadata, and ingestion status
- [ ] `collection_id` filter returns only documents in that collection
- [ ] Pagination works (`offset` + `limit`)
- [ ] Empty collection returns empty list (not error)

---

### P1-05: `delete_document` Tool

**Description**: Delete a document from the knowledge base.

**SDK Method**: `client.documents.delete(id)`

**Tool Parameters**:
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `document_id` | `str` | Yes | — | UUID of the document to delete |

**Response Format**:
```text
Document deleted successfully.
  ID: 3fa85f64-5717-4562-b3fc-2c963f66afa6
```

**Dependencies**: P1-01

**Size**: Small (~15 LOC)

**Acceptance Criteria**:
- [ ] Document removed from knowledge base
- [ ] `list_documents` no longer shows deleted document
- [ ] Search no longer returns chunks from deleted document
- [ ] Error message on non-existent document ID

---

### P1-06: `list_collections` Tool

**Description**: List available collections in the knowledge base.

**SDK Method**: `client.collections.list(ids?, offset?, limit?)`

**Tool Parameters**:
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `offset` | `int` | No | `0` | Pagination offset |
| `limit` | `int` | No | `20` | Maximum collections to return |

**Response Format**:
```text
## Collections (showing 1–2 of 2)

1. **default** (a1b2c3d4...)
   Documents: 12 | Created: 2026-02-01

2. **research-papers** (e5f6g7h8...)
   Documents: 34 | Created: 2026-03-01
```

**Dependencies**: P1-01

**Size**: Small (~20 LOC)

**Acceptance Criteria**:
- [ ] Returns collection names, IDs, and document counts
- [ ] Pagination works (`offset` + `limit`)
- [ ] Newly created collections appear in list

---

### P1-07: ING-04 Chunk Metadata Schema

**Description**: Define the metadata schema applied to all ingested documents via the `metadata` parameter on `documents.create()`.

**Required Fields**:
| Field | Type | Description | Example |
|---|---|---|---|
| `source_type` | `str` | Format of the original document | `"pdf"`, `"markdown"`, `"text"`, `"audio"` |
| `title` | `str` | Human-readable document title | `"Design Document v2"` |

**Optional Fields**:
| Field | Type | Description | Example |
|---|---|---|---|
| `source_url` | `str` | Original location of the document | `"https://example.com/doc.pdf"` |
| `author` | `str` | Document author | `"Jane Smith"` |
| `created_at` | `str` | Document creation date (ISO 8601) | `"2026-03-01T00:00:00Z"` |
| `tags` | `list[str]` | Categorization tags | `["architecture", "v2"]` |
| `page_count` | `int` | Number of pages (for PDFs) | `42` |

**Example Metadata**:
```json
{
  "source_type": "pdf",
  "title": "System Architecture v2",
  "author": "Jane Smith",
  "created_at": "2026-03-01T00:00:00Z",
  "tags": ["architecture", "design"],
  "page_count": 15
}
```

**Dependencies**: None (foundational — blocks all ingestion work)

**Size**: Small (documentation + validation logic in ingest tool)

**Acceptance Criteria**:
- [ ] Schema documented in this file (done)
- [ ] `ingest_document` tool accepts metadata conforming to this schema
- [ ] Search results surface metadata fields in chunk headers
- [ ] Missing required fields produce a clear error message
- [ ] Optional fields are truly optional (no error when absent)

---

### P1-08: MCP-03 Claude Code Connection Config

**Description**: Add R2R MCP entry to `.claude/settings.json` alongside the existing Terraform entry.

**Configuration**:
```json
{
  "mcpServers": {
    "terraform": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "--network", "host", "hashicorp/terraform-mcp-server"],
      "env": {}
    },
    "r2r": {
      "command": "python",
      "args": ["/workspace/repos/R2R-ClaudeCode-integration/initial-commit/r2r_mcp_wrapper.py"],
      "env": {
        "R2R_API_BASE": "http://host.docker.internal:7272",
        "R2R_API_KEY": "${R2R_API_KEY}"
      }
    }
  }
}
```

**Environment Variables**:
| Variable | Source | Description |
|---|---|---|
| `R2R_API_BASE` | Hardcoded in config | Points to external R2R server |
| `R2R_API_KEY` | Shell environment | API key (optional for local R2R) |

**Dependencies**: P1-01 (wrapper must exist)

**Size**: Small (config change only)

**Acceptance Criteria**:
- [ ] Claude Code discovers 5+ R2R tools on startup
- [ ] Tools appear in `/mcp` or tool listing
- [ ] No conflict with existing Terraform MCP entry
- [ ] Wrapper starts via stdio transport without manual intervention

---

### P1-09: MCP-04 End-to-End Smoke Test

**Description**: Manual or scripted test procedure validating the full ingest → search → delete lifecycle.

**Test Procedure**:

| Step | Action | Tool | Expected Result |
|---|---|---|---|
| 1 | Ingest sample text | `ingest_document` | Returns document ID, status: processing/completed |
| 2 | List documents | `list_documents` | New document appears in list |
| 3 | Search for content | `search` | Returns chunks from ingested document with metadata |
| 4 | Delete document | `delete_document` | Returns success |
| 5 | Confirm deletion | `list_documents` | Document no longer appears |

**Sample Test Data**:
```python
# Ingest
ingest_document(
    raw_text="The devcontainer uses Docker-in-Docker for isolated builds. "
             "SSH agent forwarding provides git authentication. "
             "Go, Node.js, Python, and Terraform are pre-installed.",
    metadata={
        "source_type": "text",
        "title": "Devcontainer Overview"
    },
    title="Devcontainer Overview"
)

# Search
search(query="What tools are available in the devcontainer?", limit=3)

# Expected: chunk containing "Go, Node.js, Python, and Terraform"
```

**Dependencies**: P1-01 through P1-07 (all tools must work)

**Size**: Small (test script or manual checklist)

**Acceptance Criteria**:
- [ ] All 5 steps pass in sequence
- [ ] Search results include metadata headers from the ingested document
- [ ] No orphaned data after deletion
- [ ] Test is reproducible (can be run multiple times)

---

### P1-10: RET-01/RET-02 R2R Server Configuration Documentation

**Description**: Document recommended R2R server-side configuration. This is documentation only — no wrapper code changes.

**Recommended `r2r.toml` Settings**:

```toml
[ingestion]
chunk_size = 1024
chunk_overlap = 100

[embedding]
provider = "ollama"
base_model = "mxbai-embed-large"
base_dimension = 1024

[database]
provider = "postgres"
```

**Embedding Model Selection Rationale**:
- `mxbai-embed-large`: Strong performance on MTEB benchmarks, runs locally via Ollama
- 1024-dimension vectors balance quality vs. storage/speed
- Switching models requires full re-ingestion (all vectors invalidated)

**Chunk Size Rationale**:
- 1024 tokens: fits ~4 chunks in a single search result within context budget
- 100-token overlap: prevents information loss at chunk boundaries
- Configurable via `r2r.toml` on the R2R server (not via MCP)

**Dependencies**: None (server-side only)

**Size**: Small (documentation)

**Acceptance Criteria**:
- [ ] Settings documented in this file (done)
- [ ] R2R server operator can configure from this documentation
- [ ] Chunk size and embedding model choices are justified

---

## Phase 2: Retrieval Quality and Contracts (Summary)

| Task | Description | Key SDK/Config |
|---|---|---|
| **P2-01** | Add `search_mode`/`search_strategy` passthrough | `SearchSettings(search_strategy="hyde"\|"query_fusion")` |
| **P2-02** | RET-05: Format chunks with inline metadata headers for source attribution | Inject `[Source: ... \| Type: ... \| Date: ...]` headers |
| **P2-03** | AGT-01: Document tool input/output contract for multi-turn retrieval | Define search request/response schemas |
| **P2-04** | Add `get_document_chunks` tool | `client.documents.list_chunks(id, limit?)` |
| **P2-05** | Context window budgeting — enforce `limit=5` default, document guidance for multi-query turns | Token tracking, agent prompt guidance |

---

## Phase 3: Extended Ingestion and Plugin System (Summary)

| Task | Description | Notes |
|---|---|---|
| **P3-01** | ING-05: Obsidian vault preprocessor | Strip `[[wikilinks]]`, parse YAML frontmatter, preserve link context in metadata → feed to `ingest_document` |
| **P3-02** | ING-06: Scientific PDF preprocessor | Use nougat or mathpix for LaTeX/formula extraction → feed to `ingest_document` |
| **P3-03** | `BasePreprocessor` interface + registry | `detect()`, `preprocess()`, `normalize()` methods; auto-discovery from `preprocessors/` directory |
| **P3-04** | Claude Code plugin/skill scaffolding | `/ingest` and `/search` commands; format auto-detection; orchestrator agent |

---

## Dependency Graph

```
P1-07 (metadata schema) ─────────────────────┐
                                              │
P1-01 (skeleton) ──┬── P1-02 (search)        │
                   ├── P1-03 (ingest) ◄───────┘
                   ├── P1-04 (list docs)
                   ├── P1-05 (delete doc)
                   └── P1-06 (list collections)
                              │
P1-08 (config) ◄──────── P1-01
                              │
P1-09 (smoke test) ◄──── ALL P1 tasks
                              │
P1-10 (server docs) ──── independent
                              │
                        ┌─────┴─────┐
                     Phase 2     Phase 3
```

---

## Out of Scope

| Item | Reason |
|---|---|
| `rag` tool (synthesized answers) | Hallucination compounding; Claude is the LLM |
| EPIC 5 MOD-01/02/03/05 | Model provider abstraction deferred to v1.1 |
| `file_path` ingestion | Requires server-side filesystem access |
| Audio ingestion (ING-03) | Requires `faster-whisper` on R2R server |
| UI / frontend | Out of scope entirely |
| Auth / multi-tenancy | Out of scope for MVP |
| Vendor-neutral abstraction layer | Deferred to v1.1 |
