# R2R-ClaudeCode-integration
Integrating R2R-RAG with ClaudeCode via MCP

## Technical Requirements — R2R RAG System

---

### EPIC 1 — File Ingestion

**ING-01 — PDF Text Ingestion**
Configure R2R `unstructured_local` provider for pure-text PDFs. Validate page boundaries and section headings are preserved in chunk metadata.

**ING-02 — PDF Visual Ingestion**
Enable `hi-res` ingestion mode. Wire `vlm` config to a configurable model endpoint. Validate tables, figures, and mixed-layout pages produce meaningful text output.

**ING-03 — Audio Ingestion Pipeline**
Build a pre-ingestion script using `faster-whisper` that transcribes `.mp3` files into timestamped chunks and pushes them to R2R via `client.documents.create(chunks=[...])`. Model size must be configurable (`base` → `large-v3-turbo`).

**ING-04 — Chunk Metadata Schema**
Define and enforce a shared metadata schema applied to all ingested chunks regardless of source type:
```text
source_file, source_type, page_or_timestamp, section_title, ingest_date, doc_version
```
All ingestion tasks (ING-01 → ING-03) must conform to this schema.

**ING-05 — Obsidian Vault Pre-Processor**

Strip/resolve [[wikilinks]], parse frontmatter YAML as metadata, convert to clean markdown before ingestion. Tools: obsidian-export or a small custom script.

This is non-trivial because Obsidian's graph structure (linked notes) is meaningful — a flat ingest loses the relationship between notes. You may want to preserve link context in chunk metadata.


**ING-06 — Scientific PDF Math/Formula Handling**

For papers with heavy LaTeX, consider mathpix API or nougat (Meta's scientific PDF parser) as a pre-processor before R2R ingestion. Otherwise equations become noise in your chunks.


---

### EPIC 2 — Retrieval Quality

**RET-01 — Chunk Size Tuning**
Set `chunk_size = 1024`, `chunk_overlap = 100` as baseline. Document the config location and make values env-var overridable.

**RET-02 — Embedding Model Configuration**
Expose embedding provider and model as env vars. Default to `ollama/mxbai-embed-large`. Ensure switching to another provider requires no code changes.

**RET-03 — HyDE Search Strategy**
Enable `search_strategy = "hyde"` in R2R config. Write an integration test that confirms HyDE is active and returns results for a sample query.

**RET-04 — Reranking Integration**
Integrate a reranker (default: `cohere-rerank` or `bge-reranker-v2-m3` via Ollama). Set `num_results = 20` pre-rerank, `top_k = 6` post-rerank. Reranker must be swappable via config.

**RET-05 — Metadata Injection into Context**
Ensure retrieved chunks passed to the LLM include inline metadata headers:
```text
[Source: {source_file} | Type: {source_type} | Date: {ingest_date}]
{chunk_text}
```
This enables the model to reason about recency and authority.

---

### EPIC 3 — Agent / Multi-Retrieval Interface

**AGT-01 — Multi-Turn Retrieval API Contract**
Define the R2R search endpoint contract (input params, response schema) that agents will call repeatedly. Document `collection_id`, `query`, `top_k`, `filters` as supported parameters.

**AGT-02 — Collection-Based Document Scoping**
Implement R2R collections for logical document grouping (e.g. `audio`, `pdf-text`, `pdf-visual`). Agents must be able to scope a search to one or multiple collections per query.

**AGT-03 — Agent Prompt Template for Multi-Retrieval**
Provide a system prompt template instructing the agent to:
- Issue multiple targeted R2R queries rather than one broad query
- Explicitly reconcile contradictions found across retrieved chunks
- State uncertainty when retrieved context is insufficient

**AGT-04 — Contradiction Handling Instruction**
Add explicit system prompt instruction:
```text
If retrieved sources contradict each other, state the contradiction,
identify the most recent or authoritative source, and qualify your answer.
```
Validate with a test case using two documents containing conflicting facts.

---

### EPIC 4 — MCP Server / Claude Code Integration

**MCP-01 — R2R MCP Server Setup**
Deploy and validate R2R's built-in MCP server. Confirm tool exposure: `search`, `ingest`, `list_documents` are accessible from Claude Code.

**MCP-02 — MCP Tool Manifest Validation**
Document all MCP tools exposed by R2R, their input/output schemas, and which agent tasks map to which tools. Acts as the interface contract between Claude Code and R2R.

**MCP-03 — Claude Code Connection Config**
Provide a checked-in `.mcp.json` / `claude_desktop_config.json` config snippet pointing to the R2R MCP server. Must work with default R2R local deployment.

**MCP-04 — End-to-End MCP Smoke Test**
A single test: ingest one PDF and one `.mp3` → query via MCP from Claude Code → verify both sources appear in the response context. Acts as the integration gate for all prior epics.

---

### EPIC 5 — Model Provider Abstraction

**MOD-01 — LLM Provider Config Schema**
Define a single `config.toml` / `.env` section for all four model roles:
```text
FAST_LLM, QUALITY_LLM, VLM_LLM, REASONING_LLM
```
Each accepts a `provider/model-name` string. No hardcoded model names in code.

**MOD-02 — Anthropic Claude API Integration**
Validate that setting any model role to `anthropic/claude-*` routes correctly through LiteLLM. Document required env var: `ANTHROPIC_API_KEY`.

**MOD-03 — OpenAI API Integration**
Validate that setting any model role to `openai/gpt-*` routes correctly through LiteLLM. Document required env var: `OPENAI_API_KEY`.

**MOD-04 — Ollama Local Model Integration**
Validate that setting any model role to `ollama/...` routes correctly through LiteLLM with a local Ollama instance. Document `OLLAMA_BASE_URL` env var. Covers both LLM and embedding roles.

**MOD-05 — Provider Fallback Strategy**
Define and document the fallback order if a provider is unavailable:
```text
Anthropic → OpenAI → Ollama
```
Implement via LiteLLM fallback config. No silent failures — log provider switches.

---

### Dependency Map

```text
ING-04 ──────────────────────────────────────┐
ING-01, ING-02, ING-03 ── depend on ── ING-04 │
                                              ↓
RET-01, RET-02 ── feed into ── RET-03, RET-04
                                              ↓
                              RET-05 (metadata injection)
                                              ↓
              AGT-01, AGT-02, AGT-03, AGT-04 (agent layer)
                                              ↓
                         MCP-01, MCP-02, MCP-03
                                              ↓
                              MCP-04 (smoke test — final gate)

MOD-01 → MOD-02, MOD-03, MOD-04 → MOD-05
MOD-* can proceed in parallel with all other epics
```

---

### What Is Explicitly Left Open

| Decision | Deferred To |
|---|---|
| Specific model names | MOD-01 env vars at deploy time |
| Cloud vs local deployment | Ops/infra decision |
| Diarization (speaker ID in audio) | Post-MVP — extend ING-03 |
| UI / frontend | Out of scope |
| Auth / multi-tenancy | Out of scope |
