# Architecture Review 1 of 3: R2R + Claude Code MCP Integration

> **Independent Review** — This is 1 of 3 redundant architecture reviews conducted in parallel by independent agents. Each agent explored the workspace, read the architecture proposal, and answered the same 5 questions without seeing other agents' work. See `ArchReview_2.md` and `ArchReview_3.md` for the other two reviews.

> **Agent Focus**: MVP definition, technical caveats, and phased roadmap

> **Date**: 2026-03-06

---

## Q1: Is the proposed architecture the best way to integrate an agnostic RAG system with Claude Code?

**No, but it is a reasonable starting point.** Three fundamental issues:

1. **R2R's built-in MCP server as the sole integration point is risky.** The tool surface (`search`, `ingest`, `list_documents`) is almost certainly insufficient for the features described in EPICs 2-3 (collection-scoped search, metadata filtering, HyDE configuration, reranking parameters). There is no verified evidence that R2R's MCP server exposes these capabilities.

2. **The architecture is not agnostic.** It is deeply coupled to R2R's APIs, config format, collection model, and LiteLLM integration. Swapping to LlamaIndex or Haystack would be a complete rewrite.

3. **I recommend a hybrid approach:** Use R2R's MCP for core search/list operations, but build a thin custom MCP sidecar for preprocessing pipelines, metadata enforcement, and any operations R2R's MCP does not cover. The MCP tool schemas should be owned by this project, not inherited from R2R.

---

## Q2: What needs to be improved?

**Missing:** An abstraction layer between Claude Code and the RAG backend; a unifying preprocessing pipeline architecture; error handling/observability; document lifecycle management (update/delete); context window management strategy.

**Over-engineered:** EPIC 5 (Model Provider Abstraction) conflates R2R's internal LLM roles with Claude Code's role as the reasoning LLM. Claude Code IS the LLM -- R2R should be retrieval-only. MOD-02, MOD-03, and MOD-05 are unnecessary. AGT-03/AGT-04 are prompt engineering tasks, not engineering tickets.

**Wrong assumptions:** (a) R2R's MCP server exposes all needed operations (unverified), (b) Claude Code will use R2R as its LLM for answers (it should not), (c) the devcontainer has outbound internet (it does not -- the firewall blocks it).

---

## Q3: Can we adopt a plugin system for preprocessing? How?

**Yes, absolutely.** After studying the plugin patterns in `/workspace/plugins/`, I recommend a three-layer architecture:

1. **Standalone Python pipeline** with a preprocessor registry (`registry.json` mapping file types to preprocessor scripts). New formats (Notion, Confluence, EPUB, code repos) are added by writing one script and adding one JSON entry.
2. **Custom MCP server** wrapping the pipeline, exposing `rag_ingest`, `rag_search`, etc. as tools.
3. **Claude Code plugin** providing `/ingest`, `/search` commands, a `rag-researcher` agent, and bundling the MCP server via `.mcp.json`.

The plugin structure follows existing conventions. Each preprocessor implements a common interface: `preprocess(input_path) -> list[Chunk]` with ING-04's metadata schema.

---

## Q4: MVP and phased roadmap

**Phase 0 (Spike, 1-2 days):** NEW ticket SPIKE-01 -- validate R2R's MCP server capabilities hands-on. This must happen before anything else.

**Phase 1 (Core MVP, 1 week):** ING-04, ING-01, RET-01, RET-02, MCP-01, MCP-03, MCP-04 (PDF-only smoke test). This gets "ingest PDF, search it from Claude Code" working.

**Phase 2 (Retrieval Quality, 1 week):** RET-03, RET-04, RET-05, AGT-01, AGT-02.

**Phase 3 (Extended Ingestion, 1-2 weeks):** ING-02, ING-03, ING-05, plugin scaffolding.

**Phase 4 (Polish, 1-2 weeks):** ING-06, MOD-01 (embedding+VLM only), MOD-04, MCP-02, AGT-03/04.

**Defer indefinitely:** MOD-02, MOD-03, MOD-05.

**Add:** SPIKE-01 (MCP validation), OPS-01 (Docker Compose for local stack), OPS-02 (firewall allowlist updates).

---

## Q5: Technical caveats

Nine risks identified, two are **CRITICAL**:

1. **No outbound internet (CRITICAL)** -- The devcontainer firewall blocks Ollama model downloads, Cohere API, HuggingFace, Mathpix, and everything else this proposal needs. Nearly every component requires network access that is unavailable.

2. **Docker-in-Docker nesting (CRITICAL)** -- R2R's Docker deployment inside DinD means double-nested containers competing for 8 capped CPUs, with storage/networking complexity. Consider running R2R natively via pip or on the host.

3. **R2R MCP maturity (HIGH)** -- No SemVer guarantees, limited documentation, unknown tool parameter support.

4. **Model role confusion (HIGH)** -- R2R's LLM and Claude Code must NOT both generate answers. R2R must be retrieval-only. HyDE should use a cheap local model, not a second Claude call.

5. **Context window pressure (MEDIUM)** -- Multi-retrieval at 6K tokens per query can consume 18K+ tokens per turn. Needs explicit token budgets.

6. **Embedding model migration (MEDIUM)** -- Changing models invalidates all vectors. No migration strategy documented.

7-9. Postgres persistence, MCP lifecycle/health, API key management (LOW-MEDIUM).

---

## Detailed Analysis (Initial Deep-Dive)

### MVP Definition & Scope

#### Recommended MVP Ticket Set (9 tickets)

**Core ingestion (2 tickets):**
- **ING-04** -- Chunk Metadata Schema (must be first; blocks all others)
- **ING-01** -- PDF Text Ingestion (pure text PDFs, no visual complexity yet)

**Retrieval quality (2 tickets):**
- **RET-01** -- Chunk Size Tuning (1024/100 baseline, env-var configurable)
- **RET-02** -- Embedding Model Configuration (Ollama mxbai-embed-large default)

**Agent interface (2 tickets):**
- **AGT-01** -- Multi-Turn Retrieval API Contract (define R2R search endpoint contract)
- **AGT-03** -- Agent Prompt Template for Multi-Retrieval (system prompt that uses R2R search)

**MCP Integration (2 tickets):**
- **MCP-03** -- Claude Code Connection Config (.mcp.json snippet for R2R server)
- **MCP-04** -- End-to-End MCP Smoke Test (ingest 1 PDF -> query via MCP -> verify sources in response)

**Model provider abstraction (1 ticket):**
- **MOD-04** -- Ollama Local Model Integration (self-contained; all others use local Ollama)

#### Deferred to v1.1 (8 tickets)

- **ING-02** (PDF Visual/VLM) -- Adds rendering complexity; skip for MVP
- **ING-03** (Audio) -- Faster-whisper + chunking is a moving-parts minefield for first release
- **RET-03** (HyDE) -- Nice-to-have; basic BM25+vector search sufficient for smoke test
- **RET-04** (Reranking) -- Complexity without proportional MVP value; retrieve top 10 is fine
- **RET-05** (Metadata injection) -- Defer until AGT-01 contract clarifies where metadata flows
- **AGT-02** (Collections) -- Scoping to single default collection is fine; multi-collection in v1.1
- **AGT-04** (Contradiction handling) -- Add test after system prompt works
- **MOD-01, MOD-02, MOD-03, MOD-05** (LiteLLM/Anthropic/OpenAI/Fallback) -- Ollama-only for MVP; add provider abstraction in v1.1

#### MVP Phased Approach

**Phase 1 (Days 1-3): Setup + Single Ingest Path**
1. ING-04: Define metadata schema in R2R config (yaml: source_file, source_type, page_or_timestamp, section_title, ingest_date, doc_version)
2. ING-01: Wire R2R's `unstructured_local` provider; test with 2-3 sample PDFs
3. RET-01, RET-02: Configure chunk_size/overlap + Ollama embedding model in R2R config

**Phase 2 (Days 4-5): Agent + MCP Wiring**
4. AGT-01: Write R2R search API contract doc (input schema: {collection_id, query, top_k, filters}, output: {chunks[], scores, metadata[]})
5. AGT-03: Write system prompt template that issues targeted R2R queries
6. MCP-03: Generate `.mcp.json` config for R2R MCP server (stdio-based, Docker or local)

**Phase 3 (Days 6-7): Integration Test**
7. MOD-04: Ensure Ollama running locally, all models accessible
8. MCP-04: End-to-end test: ingest PDF -> ask Claude via MCP -> verify source metadata in answer

#### Should you start with R2R's built-in MCP or custom wrapper?

**Answer: R2R's built-in MCP (if mature enough), else custom thin wrapper.**

- **R2R's built-in**: Lower lift, battle-tested by R2R team. But verify: Does it expose all needed tools? Does it handle auth/lifecycle well in a devcontainer?
- **Custom thin wrapper**: If R2R's MCP is flaky or missing tools, write a 50-line Node.js/Python MCP server that wraps R2R's HTTP API. Less risk than full implementation.
- **Recommendation**: Start by evaluating R2R's MCP maturity. If it's solid, use it. If not, spend 2 hours building a stdio MCP wrapper around R2R's Python client library.

---

### Technical Caveats (Detailed)

#### CRITICAL

**1. No Outbound Internet -- Severity: CRITICAL**
- **Issue**: The workspace CLAUDE.md explicitly states "No outbound internet". This breaks:
  - Model API calls (Anthropic, OpenAI) -- R2R needs an LLM for HyDE/query rewriting
  - pip/npm installs for R2R and dependencies
  - Any external embedding model endpoints
- **Impact**: MVP fails immediately if R2R tries to call external APIs
- **Mitigation**:
  - Run everything locally via Ollama for embeddings and any R2R-side LLM calls
  - Pre-stage all Python dependencies (R2R, unstructured, etc.) in the devcontainer Dockerfile or use offline wheels
  - Document which R2R features require external APIs and disable them (MOD-04 explicitly uses Ollama-only)
  - Test offline mode thoroughly in Phase 1

**2. Docker Nesting in DinD -- Severity: CRITICAL**
- **Issue**: Devcontainer uses Docker-in-Docker (DinD). R2R runs as a Docker stack (Postgres+pgvector, Hatchet, R2R server). Nesting DinD inside DinD is tricky.
- **Impact**: R2R container might not start, networking might break, volumes might not mount correctly
- **Mitigation**:
  - **Option A (Recommended)**: Run R2R components directly in the devcontainer (no Docker), using:
    - Postgres locally (apt install postgres)
    - pgvector extension (compile or pre-install)
    - Hatchet task queue as optional feature (might not be needed for MVP)
    - R2R Python SDK directly (pip install)
  - **Option B**: Docker-in-DinD with host network forwarding (`docker run --network host`), but this is fragile
  - **Decision**: **Strongly recommend Option A** -- run R2R natively inside the devcontainer, avoid Docker nesting
  - **Action**: Update CLAUDE.md with R2R setup instructions (Postgres, Python SDK, Ollama)

**3. R2R MCP Server Maturity Risk -- Severity: HIGH**
- **Issue**: R2R's MCP support is relatively new. Risk of:
  - Incomplete tool coverage (missing `ingest`, `search`, or `list_documents`)
  - Auth/lifecycle bugs in MCP layer
  - Protocol version mismatches with Claude Code's MCP implementation
- **Impact**: MCP-01/02/03/04 fail silently, discovery nightmare
- **Mitigation**:
  - **Spike task (Day 1)**: Clone R2R repo, inspect `/mcp` or MCP server code, verify tool coverage
  - Ensure docs match reality (MCP server might be undocumented)
  - Build fallback path: custom thin MCP wrapper around R2R Python SDK
  - Test tool discovery early: `/mcp` command in Claude Code must show R2R tools
  - Keep custom wrapper code trivial (< 100 lines) to stay maintainable

#### HIGH

**4. Context Window Pressure -- Severity: HIGH**
- **Issue**: If RAG retrieves 6 chunks of 1024 tokens each (~6K tokens) per query, and you have 3-turn conversation, that's 18K tokens of context just for RAG, leaving ~82K for conversation history in Claude 3.5 Sonnet. Compounds quickly with follow-ups.
- **Impact**: Expensive API calls, truncation of older context, user confusion about what's in scope
- **Mitigation**:
  - **For MVP**: Use RET-01 baseline (1024 tokens) but set `top_k = 3` (not 6) to keep per-query overhead ~3K
  - Implement a "context budget" in AGT-03 system prompt: "Only retrieve from RAG if query needs external knowledge; use conversation history first"
  - Document token usage in agent prompt: "Be aware of context window; summarize long retrieved docs"
  - Track context consumption: Add logging to measure actual token usage
  - **For v1.1**: Implement query-aware top_k (simple question -> 2 chunks, complex question -> 5 chunks)

**5. Embedding Model Migration -- Severity: HIGH**
- **Issue**: If you embed 1000 PDFs with `mxbai-embed-large`, then later switch to a different model (e.g., `nomic-embed-text`), old embeddings become incompatible. Reindexing is expensive.
- **Impact**: Breaking change; all old documents become unsearchable
- **Mitigation**:
  - **Document embedding model decision**: In RET-02, record which embedding model is frozen for production
  - Implement versioning in metadata: Add `embedding_model` field to chunk metadata (ING-04 schema)
  - Plan migration path: If you must switch, write a script to re-embed and re-store all chunks
  - **For MVP**: Pick Ollama `mxbai-embed-large` and stick with it for the release cycle; document as "frozen"

**6. Model Confusion: R2R LLM vs Claude LLM -- Severity: HIGH**
- **Issue**: The architecture mentions "R2R routing LLM calls via LiteLLM", but Claude Code IS the LLM. When does R2R need its own LLM?
  - HyDE (RET-03) requires an LLM to generate hypothetical documents before search
  - Query rewriting might need an LLM
  - But the final answer generation is Claude (via MCP)
- **Clarification**:
  - **R2R LLM role**: Only for retrieval enhancement (HyDE, reranking prompts). This is deferred to v1.1 (RET-03 not in MVP)
  - **Claude LLM role**: Final answer generation from retrieved chunks
  - **For MVP**: Disable R2R's LLM features; use simple BM25+vector search (no HyDE)
  - **Action**: Document this split explicitly in AGT-01 API contract: "R2R returns chunks only; Claude generates final answer"

#### MEDIUM

**7. Audio Pipeline Complexity -- Severity: MEDIUM** (deferred to v1.1)
- **Issue**: ING-03 requires: faster-whisper + timestamped chunking + R2R document API. Each component has failure modes.
- **Mitigation**: Defer to v1.1; test Whisper model pre-caching; build standalone script first

**8. Reranking Integration -- Severity: MEDIUM** (deferred)
- **Issue**: RET-04 wants a reranker. Local reranker models are large (~200MB+), adds extra inference pass.
- **Mitigation**: MVP: Skip reranking. v1.1: Add only if user feedback shows low quality with simple ranking

**9. Metadata Injection into Context -- Severity: MEDIUM**
- **Issue**: RET-05 wants to inject metadata headers into retrieved chunks before passing to LLM.
- **Mitigation**: MVP: Skip. v1.1: Implement in AGT-03 system prompt template.

#### LOW

**10. Collection Scoping (AGT-02)** -- Single default collection for MVP; multi-collection in v1.1.
**11. Contradiction Handling (AGT-04)** -- Document requirement; implement in v1.1.
**12. Provider Fallback (MOD-05)** -- Ollama-only for MVP; add fallback in v1.1.

---

### Key Decisions to Make Before Implementation

| Decision | Recommendation | Rationale |
|----------|---|---|
| **Native R2R or Docker** | Native (Postgres + Python SDK) in devcontainer | Avoid DinD nesting; simpler debugging |
| **Ollama vs cloud embeddings** | Ollama mxbai-embed-large | No internet; control model lifecycle |
| **R2R's MCP or custom wrapper** | Evaluate R2R's MCP first; fallback to custom | De-risk tool coverage gaps; keep wrapper < 100 LOC |
| **Context window strategy** | Query-aware top_k (start with 3) + prompt budgeting | Prevent truncation; manage costs |
| **Embedding model frozen** | Yes, freeze in MVP; document breaking change cost for migration | Prevent silent failure; plan v1.1 migration |
| **HyDE in MVP** | No, defer to v1.1 | Adds LLM complexity; skip for MVP baseline |
| **Collections scoping** | Single default collection; multi-collection in v1.1 | Simplify agent logic; scope clarity in v1.1 |

---

### Phased Roadmap

**MVP (Weeks 1-2)**: Ingest 1 PDF, query via Claude Code + MCP, get RAG-augmented answer.
- Tickets: ING-04, ING-01, RET-01, RET-02, AGT-01, AGT-03, MOD-04, MCP-03, MCP-04
- Success Criteria: MCP-04 smoke test passes, offline environment, Ollama running, embeddings in Postgres

**v1.1 (Weeks 3-4)**: Multi-document ingestion, better retrieval quality, multiple collections.
- Add: ING-02, RET-03, RET-04, RET-05, AGT-02, AGT-04, MOD-01, MOD-02, MOD-03, MOD-05

**v1.2 (Future)**: Audio, diarization, advanced features.
- Add: ING-03, advanced caching, UI/frontend

---

### Implementation Checklist

- [ ] **Day 1**: Spike R2R MCP maturity; decide native vs Docker; design metadata schema (ING-04)
- [ ] **Day 2-3**: Setup Postgres + pgvector + R2R Python SDK locally; ingest sample PDF (ING-01)
- [ ] **Day 3**: Configure Ollama embeddings; test retrieval (RET-01, RET-02)
- [ ] **Day 4**: Write R2R search API contract (AGT-01); draft system prompt (AGT-03)
- [ ] **Day 5**: Configure R2R MCP server; test tool discovery in Claude Code (MCP-03)
- [ ] **Day 6-7**: Build + run smoke test (MCP-04); debug integration failures
- [ ] **Final**: Document offline setup; add to workspace CLAUDE.md
