# Architecture Review 2 of 3: R2R + Claude Code MCP Integration

> **Independent Review** — This is 2 of 3 redundant architecture reviews conducted in parallel by independent agents. Each agent explored the workspace, read the architecture proposal, and answered the same 5 questions without seeing other agents' work. See `ArchReview_1.md` and `ArchReview_3.md` for the other two reviews.

> **Agent Focus**: Agnostic RAG integration evaluation, MCP tool surface, dependency analysis, EPIC 5 role clarity

> **Date**: 2026-03-06

---

## Q1: Is the proposed architecture the best way to integrate an agnostic RAG system with Claude Code?

**No.** It is a reasonable starting point but not the best architecture. Three structural problems:

**1. R2R's built-in MCP server is too thin and too tightly coupled.** The tool surface (`search`, `ingest`, `list_documents`) is insufficient. Missing: collection management, document deletion/update, ingestion status polling, chunk-level inspection, configuration introspection. The proposal has zero abstraction between Claude Code and R2R's native MCP implementation, so any upstream change in R2R's MCP tool schemas breaks the integration.

**2. The "agnostic" claim does not hold.** Every EPIC uses R2R-specific terms (`unstructured_local`, R2R collections, R2R's HyDE config, `client.documents.create(chunks=[...])`). Swapping to LlamaIndex or Haystack would require rewriting EPICs 1-3 entirely. True agnosticism requires an abstraction layer defining a stable RAG interface (ingest, search, list, delete, configure) that maps to whichever backend is deployed.

**3. The recommended alternative is a custom MCP gateway.** A thin Python or Node.js MCP server (Docker-based, like the existing Terraform MCP server in `.claude/settings.json`) that wraps R2R's REST API. This gives full control over tool surface, enables backend swappability, allows adding caching/retries/schema validation, and buffers against R2R's MCP maturity issues.

---

## Q2: What needs to be improved?

**Missing architecturally:**
- A **RAG Gateway MCP server** as an abstraction layer (8+ tools: `rag_search`, `rag_ingest`, `rag_ingest_chunks`, `rag_list_documents`, `rag_delete_document`, `rag_list_collections`, `rag_create_collection`, `rag_status`)
- A **pluggable preprocessor framework** (not ad-hoc scripts per format)
- **Context budget management** -- with `top_k=6`, `chunk_size=1024`, and multi-query agents, RAG context accumulates to ~90KB over 5 turns with no truncation/summarization strategy
- **Model role clarity** -- R2R's LLM should handle HyDE only; Claude handles all reasoning; the `search` tool must return raw chunks, not LLM-synthesized answers
- **Observability** -- no ticket for logging, tracing, or debugging retrieval quality

**Over-engineered:**
- **EPIC 5 (Model Provider Abstraction)** -- LiteLLM handles this via env vars; custom fallback logic with 3 providers and 4 model roles is premature
- **AGT-03/04 (Agent Prompt Templates)** -- these belong in Claude Code's CLAUDE.md or plugin commands, not in R2R's agent framework
- **ING-02 (PDF Visual/VLM)** at MVP -- requires GPU infrastructure for a niche use case

**Wrong assumptions:**
- R2R's MCP server exposes all needed tools (it likely does not)
- HyDE is always beneficial (hurts on specific/technical queries; should be per-query)
- The agent layer lives in R2R (it should live in Claude Code)

---

## Q3: Can we adopt a plugin system for preprocessing?

**Yes, and this is the single most important architectural improvement.** The workspace's plugin system (12+ plugins in `/workspace/plugins/`) follows a consistent structure (`.claude-plugin/plugin.json`, `commands/`, `agents/`, `skills/`, `hooks/`, `.mcp.json`). The recommended design:

```
rag-ingest-plugin/
  .claude-plugin/plugin.json
  commands/ingest.md, ingest-status.md, list-preprocessors.md
  agents/ingest-orchestrator.md
  preprocessors/
    obsidian/preprocess.py + config.yaml
    scientific-pdf/preprocess.py + config.yaml
    audio/preprocess.py + config.yaml
    plain-pdf/preprocess.py + config.yaml
    code-repo/preprocess.py + config.yaml    # future
  .mcp.json                                   # bundles RAG Gateway MCP
  lib/pipeline.py, metadata.py
```

Each preprocessor implements a standard interface (`can_handle()`, `preprocess()`). New formats (Notion, Confluence, EPUB, code repos, Slack exports) are added by creating a new `preprocessors/` directory. The Claude Code agent auto-discovers preprocessors and routes files. **Preprocessing is compute work (Bash scripts) orchestrated by the plugin, NOT MCP tools** (too heavy for synchronous tool calls). Clean chunks are then pushed through `rag_ingest_chunks` MCP tool.

---

## Q4: MVP Roadmap

**Phase 0 (must add -- not in proposal):**
- **ARCH-01**: Build RAG Gateway MCP server skeleton (2 tools: `rag_search`, `rag_ingest`)

**Phase 1 -- Foundation (Week 1-2): "Ingest a PDF, search from Claude Code"**
- ING-04 (Metadata Schema) -> ING-01 (PDF Text) -> RET-01 (Chunk Size) + RET-02 (Embedding Config) -> MCP-03 (Connection Config)

**Phase 2 -- Quality (Week 3): "Quality search with source attribution"**
- RET-05 (Metadata Injection) -> RET-03 (HyDE) -> AGT-01 (API Contract) -> MCP-02 (Tool Manifest)

**Phase 3 -- Multi-modal (Week 4-5): "PDF + audio + Obsidian with collections"**
- ING-03 (Audio) -> ING-05 (Obsidian) -> AGT-02 (Collections) -> MCP-04 (Smoke Test)

**Deferred:** ING-02, ING-06, RET-04, AGT-03/04, entire EPIC 5 (MOD-01 through MOD-05)

---

## Q5: Technical Caveats

1. **Docker-in-Docker nesting**: R2R's Docker Compose stack inside the devcontainer's DinD creates triple nesting (host -> devcontainer -> DinD -> R2R containers). Volume mounts across layers are error-prone. Resource contention is real (8 CPU cap shared with Ollama + Postgres + R2R). **Recommendation: Run R2R on the host, connect via REST API over `--network host`.**

2. **No outbound internet**: The firewall allowlist does not include `ollama.ai`, `api.cohere.com`, or `unstructured.io`. Ollama model downloads, Cohere reranking, and cloud Unstructured API calls will all fail. **Recommendation: Pre-pull images/models before firewall activation, or run R2R infra outside the devcontainer.**

3. **R2R MCP server maturity**: Tool schemas may change between versions. Error handling is likely basic. Missing tools (deletion, collections). Stdio transport means cold-start on every Claude Code session (~30s to load embedding models). **Recommendation: The custom MCP gateway solves all of these.**

4. **Model role confusion**: If R2R's RAG pipeline synthesizes answers using its own LLM before returning results via MCP, Claude re-synthesizes on top -- wasting tokens and compounding hallucinations. MOD-05's fallback (Anthropic -> OpenAI -> Ollama) could silently route R2R's internal operations through Claude's own API, creating circular dependencies. **Recommendation: R2R search must return raw chunks; R2R's LLM is for HyDE only.**

5. **Context window pressure**: 6 chunks x 1024 tokens x 3 queries/turn x 5 turns = ~90K tokens of RAG context competing with code, files, and conversation history. No mitigation strategy exists in the proposal.

6. **Embedding model migration**: Switching from `mxbai-embed-large` to another model invalidates all existing vectors. Full re-ingestion required. No ticket addresses this. **Recommendation: Version-tag vectors, plan for parallel collections during migration.**

7. **Additional risks**: Obsidian graph structure loss on flat ingest; audio chunk boundary coherence; race conditions between concurrent ingestion and search; no R2R API authentication; no data persistence strategy for R2R volumes across devcontainer restarts; overlap with the sister `kali-claude-rag` project that should share architectural decisions.

---

## Detailed Analysis (Initial Deep-Dive)

### Executive Summary

The proposed architecture uses R2R's built-in MCP server as the sole integration point for Claude Code. While this approach has merits, it presents several **critical architectural risks** around coupling, agnosticity, and missing tool surface area. I recommend a **hybrid approach** with a thin custom MCP wrapper layer as the integration boundary.

---

### Integration Approach Evaluation

#### Current Proposal: Direct R2R MCP Server

**Architecture:**
```
Claude Code --(MCP)--> R2R's built-in MCP server --(internal)--> R2R core
```

**Strengths:**
- Simplest initial implementation
- Leverages R2R's existing infrastructure
- No duplication of MCP server code
- Works with default R2R deployment

**Critical Weaknesses:**

##### 1.1 Tight Coupling to R2R Internals
The integration **directly exposes R2R's MCP interface**, which is a **design artifact of R2R**, not a public contract. This creates tight coupling because:

- R2R's MCP tool naming, input schemas, and output formats are implementation details
- If R2R refactors its MCP interface (version bump, restructuring), Claude Code integration breaks
- The integration cannot add Claude Code-specific affordances without monkey-patching R2R

**Example of coupling problem:**
- If R2R's MCP tool is named `r2r_search()`, and its input schema is `{collection_id, query, top_k}`, Claude Code is locked into this interface
- If R2R later changes it to `search_documents()` with input `{scope, search_query, limit}`, all Claude Code tools must be updated
- There's no abstraction layer to handle version translation

##### 1.2 Zero Agnosticity
The "agnostic RAG system" claim is **undermined by the architecture**. Using R2R's MCP server directly creates:

- **Hard dependency on R2R's tool names and schemas** -- cannot swap LlamaIndex, Haystack, or Langchain without rewriting
- **R2R-specific configuration assumptions** -- the MCP tools expose R2R concepts (collections, R2R chunk metadata format) that other RAG systems don't share
- **No adaptation layer** -- a true "agnostic" integration would abstract the RAG system behind a vendor-neutral interface

**Real-world swap scenario:**
```
If you wanted to swap R2R -> LlamaIndex:
- LlamaIndex's MCP tools would have completely different names
- Input/output schemas would differ
- Metadata handling is different
- Claude Code tools that call r2r_search() would all break
- No way to gradually migrate without breaking live workflows
```

##### 1.3 Missing Tool Surface Area
The architecture lists only 3 MCP tools: `search`, `ingest`, `list_documents`. This is **insufficient** for a production RAG integration.

**Critical gaps:**

| Capability | Missing MCP Tool | Impact |
|---|---|---|
| Query analysis | `analyze_query()` | Can't understand what the agent wants before searching |
| Collection management | `create_collection()`, `delete_collection()`, `update_collection()` | No dynamic scoping during sessions |
| Metadata filtering | `search_with_filters()` | Can't scope search to date range, document type, source |
| Chunk inspection | `get_chunk_details()`, `list_chunks_in_collection()` | Can't validate what was ingested or debug search results |
| Multi-turn context | `set_session_context()`, `get_context_state()` | Can't maintain retrieval context across multi-turn conversations |
| Reranking/tuning | `rerank_results()`, `set_rerank_model()` | Can't optimize retrieval quality after deployment |
| Ingestion validation | `validate_ingest()`, `get_ingest_status()` | Can't confirm documents were processed correctly |
| Error recovery | `retry_failed_chunks()`, `get_ingest_errors()` | No way to diagnose and fix ingestion failures |

---

### Alternative Architectures

#### Option A: Thin Custom MCP Wrapper (RECOMMENDED)

```
Claude Code --(MCP)--> Custom RAG Adapter MCP Server
                           |
                           +--(REST API)--> R2R
                           +--(REST API)--> LlamaIndex
                           +--(REST API)--> Haystack
                           +--(REST API)--> [pluggable backends]
```

Create a lightweight MCP server that:
1. **Abstracts RAG providers** via REST API calls (not direct Python imports)
2. **Exposes Claude Code-optimized tool surface** (all ~15 tools listed above)
3. **Translates between Claude Code schemas and backend schemas**
4. **Handles version negotiation** with pluggable backends

**Key files:**
```
mcp-rag-adapter/
+-- mcp_server.py          # MCP protocol handler (stdio-based)
+-- backends/
|   +-- r2r_backend.py     # REST client for R2R
|   +-- llamaindex_backend.py
|   +-- haystack_backend.py
|   +-- backend_interface.py  # Abstract interface
+-- schemas/
|   +-- search_request.py   # Vendor-neutral request schema
|   +-- search_result.py
|   +-- chunk.py
+-- config.json             # Backend selection + routing
```

**Benefits:**
- True agnosticity -- swap `config.json` to change RAG provider
- Complete tool surface for Claude Code
- Insulates Claude Code from R2R API changes
- Enables vendor-specific optimizations
- Version negotiation built in
- Can route to multiple RAG systems in parallel (for comparison)
- Fits perfectly into Claude Code's MCP plugin model

**Configuration:**
```json
{
  "rag-adapter": {
    "command": "python",
    "args": ["-m", "mcp_rag_adapter"],
    "env": {
      "RAG_BACKEND": "r2r",
      "RAG_API_URL": "http://localhost:7272",
      "RAG_API_KEY": "${RAG_API_KEY}"
    }
  }
}
```

**Swap to LlamaIndex:**
```json
{
  "env": {
    "RAG_BACKEND": "llamaindex",
    "RAG_API_URL": "http://localhost:8000"
  }
}
```

---

### Agnosticity Assessment

#### The "Agnostic" Claim: Verdict = **MISLEADING**

The architecture claims to be "agnostic" to the RAG system, but this is **only true at the deployment level**, not the **integration level**.

**What Would Make It Truly Agnostic:**
1. Vendor-neutral request/response schemas
2. Pluggable backend abstraction
3. Version negotiation
4. Transparent failover
5. Unified metadata model

**What Currently Prevents Agnosticity:**

| Issue | Impact |
|---|---|
| **R2R-specific collection model** (EPIC-2, AGT-02) | LlamaIndex doesn't have "collections"; Haystack calls them "document stores" |
| **R2R metadata schema** (EPIC-1, ING-04) | Other systems use different metadata formats |
| **Reranking config** (EPIC-2, RET-04) | R2R uses Cohere; Haystack prefers BGE; LlamaIndex uses multiple providers |
| **Search strategy** (EPIC-2, RET-03) | HyDE is R2R-specific; LlamaIndex uses different strategies |
| **MCP tool naming** | R2R's `search()` vs LlamaIndex's `query_engine.query()` |

**Path to True Agnosticity:**

```python
# backends/base.py
class RAGBackend(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int, filters: Dict) -> List[Chunk]:
        """Vendor-neutral search interface"""

    @abstractmethod
    def ingest(self, documents: List[Document], metadata: Dict) -> IngestResult:
        """Vendor-neutral ingest interface"""

    @abstractmethod
    def get_collections(self) -> List[Collection]:
        """Vendor-neutral collections interface"""
```

**Without this abstraction, "agnostic" is marketing speak.**

---

### MCP Tool Surface Area Analysis

#### Current Proposal (3 tools):
- `search(query, top_k, collection_id)` -> returns List[Chunk]
- `ingest(file_path, document_type)` -> returns IngestStatus
- `list_documents()` -> returns List[Document]

#### Missing Critical Tools:

**Retrieval Quality & Debugging:**
```python
analyze_query(query: str) -> QueryAnalysis
get_chunk_details(chunk_id: str) -> ChunkDetails
list_chunks(collection_id: str, limit: int = 100) -> List[Chunk]
get_embedding_stats(collection_id: str) -> EmbeddingStats
```

**Collection Management:**
```python
create_collection(name: str, description: str) -> Collection
update_collection(collection_id: str, metadata: Dict) -> Collection
delete_collection(collection_id: str) -> bool
list_collections() -> List[Collection]
search_with_filters(query, collection_id, top_k, filters, metadata_required) -> List[Chunk]
```

**Multi-Turn Context (Critical for Agents):**
```python
set_session_context(conversation_id: str, context: Dict) -> bool
get_session_context(conversation_id: str) -> Dict
get_search_history(conversation_id: str) -> List[SearchQuery]
```

**Ingestion & Validation:**
```python
validate_document(file_path: str, document_type: str) -> ValidationResult
get_ingest_status(document_id: str) -> IngestStatus
retry_failed_chunks(document_id: str) -> RetryResult
list_failed_chunks(limit: int = 100) -> List[FailedChunk]
```

**Model Tuning (RET-02, RET-04):**
```python
get_embedding_config() -> EmbeddingConfig
set_embedding_model(model_name: str) -> bool
set_rerank_model(model_name: str) -> bool
get_rerank_config() -> RerankConfig
rerank_results(chunks: List[Chunk], query: str) -> List[Chunk]
```

---

### Dependency Map & Parallelization

#### Issues with Current Map:

**1. Implicit Ordering Creates Bottlenecks**

The sequential nature (ING -> RET -> AGT -> MCP) serializes ~25 story points worth of work that could be parallel.

**Recommendation:** Make the dependency map explicit with parallel tracks:

```
[Parallel Track 1: Retrieval Quality]
+-- RET-01: Chunk sizing (independent)
+-- RET-02: Embedding model selection (independent of ING)
+-- RET-03: HyDE (depends on RET-01, RET-02 only)
+-- RET-04: Reranking (depends on RET-01, RET-02)
+-- RET-05: Metadata injection (depends on RET-04, ING-04)

[Parallel Track 2: Ingestion]
+-- ING-04: Metadata schema (independent)
+-- ING-01: PDF text (depends on ING-04)
+-- ING-02: PDF visual (depends on ING-04)
+-- ING-03: Audio (depends on ING-04)

[Parallel Track 3: Agent/MCP Layer]
+-- AGT-01: Multi-turn API contract (can use mock R2R)
+-- AGT-02: Collection-based scoping (depends on ING or mock)
+-- AGT-03: Prompt templates (independent)
+-- AGT-04: Contradiction handling (independent)
+-- MCP-01, MCP-02, MCP-03: Integration (can use real R2R early)
+-- MCP-04: E2E smoke test (depends on all of above)

[Parallel Track 4: Model Provider Abstraction]
+-- MOD-01 -> MOD-02 -> MOD-03 -> MOD-04 -> MOD-05 (fully independent)
```

**2. Missing Dependencies: Model Provider Abstraction & Retrieval**

The Model Provider Abstraction (MOD-01 to MOD-05) is positioned as orthogonal work, but it has implicit dependencies:
```
ING-02 (PDF visual) -> depends on -> MOD-01 (VLM role defined)
AGT-04 (contradiction handling) -> depends on -> MOD-01 (REASONING_LLM role defined)
RET-04 (reranking) -> depends on -> MOD-01 (if using local reranker)
```

**3. The MCP-04 Smoke Test Is Under-Specified**

Current scope only validates single query, not multi-turn, collections, metadata, or error cases. Needs expansion.

---

### Model Provider Abstraction (EPIC 5) -- Role Confusion

#### Critical Issue: Why Is the RAG System Abstracting LLM Providers?

Claude Code IS already the LLM. When Claude Code agents use MCP tools to retrieve documents, the **agent itself** (which is Claude) reads the retrieved context.

**Where EPIC 5 makes sense:**
- R2R needs local LLMs for embedding (RET-02)
- R2R needs local LLMs for reranking (RET-04)

**Where EPIC 5 is redundant:**
- Routing the main agent LLM -- Claude Code is the LLM; there's nothing to route

**Reframed structure:**
```toml
[r2r.embeddings]
provider = "ollama"
model = "mxbai-embed-large"

[r2r.reranking]
provider = "ollama"
model = "bge-reranker-v2-m3"

[r2r.visual_processing]
provider = "ollama"
model = "llava"
```

---

### Workspace Patterns & Alignment

The R2R integration should follow the plugin-dev pattern:

```
plugins/r2r-rag/
+-- plugin.json                 # Plugin manifest
+-- .mcp.json                   # MCP server configuration
+-- mcp/
|   +-- server.py              # MCP protocol implementation (stdio)
|   +-- adapters/
|       +-- r2r_adapter.py
|       +-- llamaindex_adapter.py
|       +-- haystack_adapter.py
+-- commands/
|   +-- ingest.md
|   +-- search.md
|   +-- manage-collections.md
+-- agents/
|   +-- retrieval-agent.md
|   +-- citation-agent.md
+-- README.md
+-- examples/
    +-- basic-search.md
    +-- multi-turn-retrieval.md
```

---

### Key Recommendations Summary

#### Priority 1: Solve Agnosticity & Coupling

| Issue | Recommendation | Impact |
|---|---|---|
| **Direct R2R MCP server exposure** | Introduce thin MCP wrapper adapting to any RAG backend | True agnosticity, future-proof |
| **Missing tool surface area** | Add ~12 more MCP tools (analysis, collection mgmt, context, validation) | Agents can reason about retrieval |
| **No vendor-neutral schemas** | Define abstract `RAGBackend` interface in adapter | Swappable backends without code changes |
| **Version negotiation missing** | Add backend capability detection in adapter | Support multiple R2R versions |

#### Priority 2: Clarify Dependencies & Parallelization

| Issue | Recommendation | Impact |
|---|---|---|
| **Sequential epics block parallelization** | Map true dependencies; show parallel tracks | Faster delivery |
| **MCP-04 smoke test insufficient** | Expand to cover multi-turn, collections, metadata, error cases | Higher confidence |
| **Model provider role confusion** | Move EPIC 5 out of integration scope | Clearer architecture |

---

### Hybrid Recommendation: The Best Path Forward

**Do NOT commit to R2R's native MCP server directly. Instead:**

1. **Create a thin MCP wrapper** (~500-1000 LOC initially)
2. **Start with R2R as the first backend** via REST API
3. **Design for swap-ability from day 1** (abstract `RAGBackend` interface)
4. **Deploy as a Claude Code plugin** (follows existing patterns)

**Cost:** ~2-3 days initial development, ~1 day per additional backend.

**Benefit:** Actually agnostic (not just marketing speak), full tool surface, future-proof, publishable as reusable plugin.
