# Architecture Decision: R2R + Claude Code MCP Integration

> **Status**: Beta — post-spike, pre-implementation
>
> **Date**: 2026-03-08
>
> **Context**: Synthesized from 3 independent architecture reviews and spike findings on R2R's native MCP implementation.

---

## 1. Context and Spike Findings

### Problem Statement

We need to integrate R2R (a RAG system) with Claude Code so that Claude can search, ingest, and manage documents in a knowledge base via MCP tools.

### Spike Result: R2R's Native MCP

R2R ships a built-in MCP server (`r2r.mcp`), but inspection reveals it covers approximately **~15% of our needs**:

- Exposes basic `search` and `ingest` tools
- No metadata filtering on search
- No `list_documents`, `list_collections`, or `delete_document` tools
- No control over `SearchSettings` (hybrid search, strategies, limits)
- No chunk metadata passthrough in responses
- Schema unstable between R2R versions

**Conclusion**: R2R's native MCP is insufficient for production use. A wrapper is required.

---

## 2. Options Evaluated

### Option A: Use R2R's Native MCP Directly

Connect Claude Code to R2R's built-in MCP server with zero custom code.

| Criteria | Rating |
|---|---|
| Implementation effort | Minimal |
| Tool coverage | ~15% of needs |
| Customizability | None |
| Maintenance burden | Low |
| Verdict | **Rejected** — tool surface too thin |

### Option B: Full Abstract RAG Gateway (500–1000 LOC)

Build a vendor-neutral `RAGBackend` abstraction layer with pluggable backends.

| Criteria | Rating |
|---|---|
| Implementation effort | High (2+ weeks) |
| Tool coverage | 100% |
| Customizability | Full |
| Maintenance burden | High |
| Verdict | **Deferred to v1.1** — premature abstraction for MVP |

### Option C: Thin FastMCP Wrapper (~50 LOC)

Minimal proxy forwarding calls to R2R's REST API with no added logic.

| Criteria | Rating |
|---|---|
| Implementation effort | Minimal |
| Tool coverage | ~60% (no metadata, no formatting) |
| Customizability | Limited |
| Maintenance burden | Low |
| Verdict | **Rejected** — doesn't address metadata or search settings |

### Option D: Curated FastMCP Wrapper (~150 LOC)

Purpose-built MCP wrapper using FastMCP that exposes exactly the tools we need, with proper parameter mapping to R2R's Python SDK.

| Criteria | Rating |
|---|---|
| Implementation effort | Low (2–3 days) |
| Tool coverage | 100% of Phase 1 needs |
| Customizability | Full control over tool signatures and response formatting |
| Maintenance burden | Low — single file, direct SDK calls |
| Verdict | **Recommended** |

---

## 3. Recommended Architecture: Curated FastMCP Wrapper

### System Diagram

```
Host / Separate Server                  Devcontainer (Claude Code)
+-------------------------------+       +----------------------------------+
| R2R Docker Stack              |       | Claude Code                      |
|  - R2R Server (:7272)         |       |  - MCP Client                    |
|  - Postgres + pgvector        |       |  - r2r_mcp_wrapper.py (~150 LOC) |
|  - Ollama (embeddings)        |<─HTTP─|  - Plugins / Skills              |
|  - Hatchet (optional)         |       |  - Git worktrees                 |
+-------------------------------+       +----------------------------------+
                                        | Terraform MCP (existing)         |
                                        +----------------------------------+
```

The devcontainer runs **only** the MCP wrapper (a lightweight Python script). R2R's full Docker stack runs externally with its own resources and internet access. This mirrors the existing Terraform MCP pattern.

### Why a Wrapper Instead of Native MCP

| Need | Native MCP | Curated Wrapper |
|---|---|---|
| `search` with filters, limits, strategies | Basic search only | Full `SearchSettings` passthrough |
| `list_documents` with collection filter | Not available | Implemented |
| `list_collections` | Not available | Implemented |
| `delete_document` | Not available | Implemented |
| Metadata in search results | Not formatted | Headers with source, type, date |
| Response formatting for Claude | Raw JSON | Structured text optimized for LLM |

---

## 4. The 6 MCP Tools

| # | Tool | SDK Method | Purpose |
|---|---|---|---|
| 1 | `search` | `client.retrieval.search()` | Query the knowledge base with filters and strategies |
| 2 | `ingest_document` | `client.documents.create()` | Add text/chunks to the knowledge base |
| 3 | `list_documents` | `client.documents.list()` | Browse documents, optionally filtered by collection |
| 4 | `delete_document` | `client.documents.delete()` | Remove a document |
| 5 | `list_collections` | `client.collections.list()` | Browse available collections |
| 6 | `get_document_chunks` | `client.documents.list_chunks()` | Inspect chunks of a specific document (Phase 2) |

Phase 1 delivers tools 1–5. Tool 6 is added in Phase 2.

---

## 5. Why No `rag` Tool

A single `rag` tool that returns synthesized answers was explicitly rejected:

1. **Token math**: R2R's RAG endpoint generates a full LLM response (500–1000 tokens), which Claude then re-processes. This doubles token spend with zero quality gain.
2. **Hallucination compounding**: R2R's LLM may hallucinate in its synthesis → Claude treats that hallucination as ground truth → compounded errors.
3. **Model role confusion**: Claude Code **is** the LLM. R2R should provide raw retrieval results; Claude does the reasoning.
4. **Loss of control**: A `rag` tool hides which chunks were used, preventing source attribution and contradiction detection.

**Correct pattern**: `search` returns ranked chunks with metadata → Claude synthesizes the answer with full visibility into sources.

---

## 6. Key Architectural Decisions

### Preprocessing Location

All preprocessing (Obsidian wikilink resolution, scientific PDF parsing, audio transcription) runs **client-side** before calling `ingest_document`. The MCP wrapper receives clean text/chunks, not raw files.

Rationale: The devcontainer cannot access files on the R2R server's filesystem. `file_path` ingestion requires server-side access. For MVP, we use `raw_text` and `chunks` parameters only.

### SDK Import Strategy

```python
try:
    from r2r import R2RClient
except ImportError:
    import sys
    sys.path.insert(0, "/workspace/repos/R2R/main/py/")
    from r2r import R2RClient
```

This allows using either a pip-installed R2R SDK or the local fork. The fork path is a fallback for environments where `pip install` is restricted (e.g., the devcontainer's PEP 668 externally-managed Python).

### EPIC 5 Disposition

EPIC 5 (Model Provider Abstraction) is **almost entirely deferred**:

| Ticket | Disposition | Reason |
|---|---|---|
| MOD-01 | Deferred | LLM config is R2R's concern, not ours |
| MOD-02 | Deferred | Claude Code IS the Anthropic integration |
| MOD-03 | Deferred | No OpenAI needed |
| MOD-04 | **Keep** | Ollama embedding config needed for R2R server |
| MOD-05 | Deferred | Premature; single provider for MVP |

### `.claude/settings.json` Configuration

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

Transport: **stdio** (same as Terraform MCP). The wrapper reads from stdin and writes to stdout using FastMCP's stdio transport.

---

## 7. Tradeoffs Matrix

| Decision | Benefit | Cost | Accepted? |
|---|---|---|---|
| Curated wrapper over native MCP | Full tool coverage, formatted responses | ~150 LOC to maintain | Yes |
| R2R SDK dependency in devcontainer | Type-safe SDK calls, parameter validation | Must manage import path | Yes |
| `raw_text`/`chunks` only (no `file_path`) | No server filesystem dependency | Client must preprocess files | Yes (MVP) |
| `limit=5` default on search | Predictable context window usage (~5K tokens) | May miss relevant chunks | Yes (configurable) |
| No `rag` tool | No hallucination compounding, full source visibility | Claude must synthesize from chunks | Yes (by design) |
| No abstraction layer | Faster MVP, simpler code | Vendor lock-in to R2R | Yes (defer to v1.1) |
| Single embedding model (mxbai-embed-large) | No migration complexity | Locked until re-index | Yes (MVP) |
| Preprocessing client-side | Works without server file access | More complex client plugins | Yes |

---

## 8. Risk Register (Post-Reframing)

| Risk | Severity | Mitigation |
|---|---|---|
| R2R SDK/API breaking changes | HIGH | Pin R2R version; wrapper isolates Claude Code from changes |
| Model role confusion (R2R synthesizes answers) | HIGH | Configure R2R as retrieval-only; no agent/RAG endpoints |
| Context window pressure (18K+ tokens/turn) | MEDIUM-HIGH | Default `limit=5`; document guidance; track usage |
| Embedding model migration requires full re-index | MEDIUM | Freeze model for MVP; version-tag in metadata |
| Network connectivity devcontainer → R2R server | LOW | Use `host.docker.internal`; document firewall requirements |

### Eliminated Risks (by architectural reframing)

All three independent reviews originally rated these as CRITICAL. They are N/A because R2R runs externally:

- Docker-in-Docker nesting
- No outbound internet in devcontainer
- Ollama resource contention with Claude Code
- Postgres persistence on devcontainer rebuild

---

## Appendix: Source Reviews

- [ArchReview_1.md](./ArchReview_1.md) — MVP definition, technical caveats, phased roadmap
- [ArchReview_2.md](./ArchReview_2.md) — Agnosticity evaluation, MCP tool surface, dependency analysis
- [ArchReview_3.md](./ArchReview_3.md) — Plugin architecture, future-proofing, ING-05/ING-06 extensibility
- [ArchReviewComposite.md](./ArchReviewComposite.md) — Synthesized consensus from all three reviews
