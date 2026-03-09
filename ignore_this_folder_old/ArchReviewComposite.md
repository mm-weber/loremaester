# Architecture Review Composite: R2R + Claude Code MCP Integration

> **Synthesized from 3 independent architecture reviews** conducted in parallel by separate agents. Each reviewed the same proposal and answered 5 questions without seeing the others' work.
>
> **Critical correction applied**: All three reviews assumed R2R runs *inside* the devcontainer. In reality, **R2R runs externally** (host or separate server) and Claude Code connects to it as one MCP server among others -- exactly like the existing Terraform MCP pattern. This eliminates the DinD and internet caveats that all 3 reviews ranked as #1 and #2.
>
> **Date**: 2026-03-06

---

## Section 1: Architectural Reframing

### The Core Misunderstanding

All three independent reviews made the same false assumption: that R2R's Docker stack (Postgres, Hatchet, R2R server, Ollama) would run *inside* the devcontainer's Docker-in-Docker environment. This led all three to rank DinD nesting and internet restrictions as CRITICAL blockers.

**The corrected architecture:**

```
Host / Separate Server              Devcontainer (Claude Code)
+--------------------------+        +---------------------------+
| R2R Docker Stack         |        | Claude Code               |
|  - R2R Server            |        |  - MCP Client             |
|  - Postgres + pgvector   |<--MCP--|  - Plugins                |
|  - Ollama (embeddings)   |        |  - Git worktrees          |
|  - Hatchet (optional)    |        |                           |
+--------------------------+        +---------------------------+
                                    | Terraform MCP Server      |
                                    | (existing, same pattern)  |
                                    +---------------------------+
```

Claude Code is a **client** connecting to R2R over MCP -- the same relationship it has with the Terraform MCP server already configured in `.claude/settings.json`.

### Assumption Correction Table

| Original Assumption (all 3 reviews) | Corrected Reality |
|---|---|
| R2R Docker stack runs inside devcontainer DinD | R2R runs externally; Claude Code connects via MCP |
| Internet restrictions block Ollama model downloads | Ollama runs on the host/server with full internet access |
| 8 CPU cap shared between R2R + Ollama + Postgres + Claude Code | R2R infra has its own resources; devcontainer only runs Claude Code |
| Docker-in-Docker triple nesting (host -> devcontainer -> DinD -> R2R) | Single-level: R2R runs natively or in Docker on host |
| Postgres persistence lost on devcontainer rebuild | Postgres runs externally; data persists independently |
| Need firewall allowlist tickets for `ghcr.io`, `ollama.ai`, etc. | External R2R server has unrestricted internet |
| `pip install r2r` needed inside devcontainer | No R2R SDK needed in devcontainer; MCP is the interface |
| Docker Compose orchestration inside devcontainer | Docker Compose runs on host if used at all |

### Existing Precedent: Terraform MCP Server

The workspace already has an external MCP server configured in `.claude/settings.json`:

```json
{
  "mcpServers": {
    "terraform": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "host",
        "hashicorp/terraform-mcp-server"
      ],
      "env": {}
    }
  }
}
```

### Projected R2R MCP Configuration

The R2R MCP entry would follow the identical pattern:

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
      "args": ["-m", "r2r.mcp"],
      "env": {
        "R2R_API_URL": "http://host.docker.internal:7272",
        "R2R_API_KEY": "${R2R_API_KEY}"
      }
    }
  }
}
```

The exact `command` and `args` depend on what we find when inspecting the R2R fork's MCP implementation (Action Item #2). R2R may use `uvx`, a Docker image, or a direct Python module. The transport could be stdio (like Terraform) or SSE.

### Impact on Risk Rankings

| Risk | Original Rating (all 3 reviews) | Corrected Rating | Reason |
|---|---|---|---|
| Docker-in-Docker nesting | CRITICAL | **N/A** | R2R doesn't run in DinD |
| No outbound internet | CRITICAL | **N/A** | R2R server has its own internet |
| Ollama resource contention | HIGH (Review 3) | **N/A** | Ollama runs on R2R's server |
| Postgres persistence | MEDIUM (Reviews 1,3) | **N/A** | Postgres runs externally |
| Firewall allowlist updates | Proposed new ticket | **N/A** | Not needed |
| Docker Compose for local stack | Proposed new ticket | **N/A** | Not a devcontainer concern |

---

## Section 2: Consensus Matrix

### What All 3 Agents Agreed On

| Topic | Consensus |
|---|---|
| **R2R's MCP server is too thin** | All 3: tool surface (`search`, `ingest`, `list_documents`) is insufficient for production |
| **Architecture is not truly agnostic** | All 3: deeply coupled to R2R APIs, config, collection model |
| **EPIC 5 is over-engineered** | All 3: Claude Code IS the LLM; R2R should be retrieval-only; MOD-02/03/05 unnecessary |
| **Plugin system for preprocessing** | All 3: Yes, using BasePreprocessor + auto-discovery registry |
| **Three-layer architecture** | All 3: Plugin (UX) + MCP (integration) + Standalone pipeline (reuse) |
| **Phase 0 spike needed** | All 3: Must inspect R2R MCP before committing to implementation path |
| **Metadata schema (ING-04) is foundational** | All 3: Must be first ticket; blocks all ingestion work |
| **Context window pressure is real** | All 3: Multi-retrieval accumulates 18K+ tokens; needs budgeting |
| **Model role confusion must be resolved** | All 3: R2R returns raw chunks; Claude generates answers |

### Key Divergences and Resolution

| Topic | Review 1 | Review 2 | Review 3 | Composite Resolution |
|---|---|---|---|---|
| **Wrapper size** | "50-line thin wrapper" or use R2R's MCP | "500-1000 LOC gateway with abstract backend" | "Custom MCP wrapper following Terraform pattern" | **Start with R2R's native MCP (inspect fork first). Build thin wrapper only if gaps found. Defer full abstraction layer to v1.1.** |
| **Agnosticity priority** | Low (practical MVP first) | High (vendor-neutral schemas day 1) | Medium (abstract interface, but R2R first) | **Acknowledge coupling; design for future abstraction but don't build it yet. True agnosticity is a v2 goal.** |
| **EPIC 5 disposition** | Defer MOD-02/03/05; keep MOD-01/04 | Defer entire EPIC 5 | Collapse to single `.env` config ticket | **Keep MOD-04 (Ollama config) for R2R server setup. Defer everything else. R2R's LLM config is its own concern, not ours.** |
| **MVP ticket count** | 9 tickets (ING-04, ING-01, RET-01, RET-02, AGT-01, AGT-03, MOD-04, MCP-03, MCP-04) | 7 tickets + ARCH-01 gateway skeleton | 10 tickets + Docker Compose + firewall | **9 tickets (see Section 5). Docker Compose and firewall tickets removed per reframing.** |
| **RET-05 in MVP** | Deferred | Phase 2 | MVP | **Include in MVP -- metadata injection into context is essential for source attribution** |
| **AGT-01 in MVP** | Yes (API contract) | Phase 2 | Deferred | **Include -- defines the contract between Claude Code and R2R search results** |

---

## Section 3: Corrected Technical Risk Register

### N/A (Formerly CRITICAL) -- Eliminated by Reframing

| Risk | Original | Why N/A |
|---|---|---|
| Docker-in-Docker nesting | CRITICAL (all 3) | R2R runs externally, not in devcontainer |
| No outbound internet | CRITICAL (all 3) | R2R server has unrestricted internet |
| Ollama resource contention | HIGH (Review 3) | Ollama runs on R2R's server with dedicated resources |
| Postgres persistence | MEDIUM (Reviews 1,3) | Postgres runs externally; not ephemeral |

### HIGH

**1. R2R MCP Server Maturity** (all 3 reviews agree)
- Tool surface may be incomplete or unstable
- Schema may change between R2R versions
- Error handling likely basic
- Cold-start latency unknown
- **Mitigation**: SPIKE-01 -- inspect fork's MCP implementation before committing

**2. Model Role Confusion** (all 3 reviews agree)
- R2R has its own LLM (for HyDE, summarization, query rewriting)
- If R2R synthesizes answers before returning via MCP, Claude re-synthesizes = token waste + compounded hallucination
- **Mitigation**: Configure R2R as retrieval-only; disable agent/RAG answer generation; return raw chunks

### MEDIUM-HIGH

**3. Context Window Pressure** (all 3 reviews agree)
- 6 chunks x 1024 tokens x 3 queries/turn = ~18K tokens per turn
- Accumulates over multi-turn conversations
- No mitigation strategy in original proposal
- **Mitigation**: Start with `top_k=3`; implement context budget in agent prompt; track token usage

### MEDIUM

**4. Embedding Model Migration** (all 3 reviews agree)
- Switching models invalidates all existing vectors
- Full re-ingestion required
- Effectively irreversible without planning
- **Mitigation**: Freeze model choice for MVP (`mxbai-embed-large`); version-tag vectors in metadata

### LOW (Resolved or Manageable)

**5. Auth between Claude Code and R2R** -- Use API key in MCP env config (standard pattern)

**6. Incremental Sync** -- Not needed for MVP; document update workflow in v1.1

**7. Tool Surface Gaps** -- Resolved by inspecting the R2R fork's actual MCP implementation (Action Item #2). If gaps exist, thin wrapper addresses them.

---

## Section 4: Synthesized Q1-Q5 Answers

### Q1: Is the proposed architecture the best way to integrate an agnostic RAG system with Claude Code?

**Not the best, but workable -- evaluate R2R's native MCP first, then decide.**

All three reviews agreed the architecture is reasonable as a starting point but not optimal. The key issues (R2R MCP surface, tight coupling, false agnosticity claim) remain valid after reframing. However, the severity is lower now that DinD/internet are non-issues.

**Corrected recommendation:**
1. **Inspect the R2R fork's MCP implementation** (SPIKE-01) to determine actual tool surface, schemas, and transport
2. If R2R's MCP covers core operations (search with filters, ingest, list, delete) -- use it directly
3. If gaps exist -- build a thin wrapper (< 200 LOC) that adds missing tools while proxying to R2R's REST API
4. Defer the full abstract `RAGBackend` interface (Review 2's recommendation) to v1.1 -- it's the right long-term architecture but premature for MVP

The `r2r` entry in `.claude/settings.json` is the integration point. No R2R code runs in the devcontainer.

### Q2: What needs to be improved?

**Missing abstraction + preprocessor pipeline; EPIC 5 over-engineered; assumptions corrected.**

**Still valid after reframing:**
- Missing: abstraction layer, preprocessing pipeline, context budget, observability, document lifecycle (update/delete)
- Over-engineered: EPIC 5 (collapse to MOD-04 only), AGT-03/04 (prompt tuning, not engineering)
- R2R's MCP tool surface unverified (SPIKE-01 resolves this)

**Invalidated by reframing:**
- "Firewall blocks everything" -- N/A (R2R server has internet)
- "Need Docker Compose inside devcontainer" -- N/A
- "pip install R2R in devcontainer" -- N/A (MCP is the interface)
- "faster-whisper impractical on CPU-only devcontainer" -- N/A (runs on R2R server)

**Added by reframing:**
- Need R2R connection config (URL, API key) in `.claude/settings.json`
- Need to inspect fork to determine MCP transport (stdio vs SSE) and available tools
- Network connectivity between devcontainer and R2R server must be verified

### Q3: Can we adopt a plugin system for preprocessing?

**Yes -- BasePreprocessor + auto-discovery registry + three-layer architecture.**

All three reviews converged on the same design:

1. **BasePreprocessor interface**: `detect()`, `preprocess()`, `normalize()` methods
2. **PreprocessorRegistry**: Auto-discovers preprocessors from a directory; runs all detectors in parallel; picks highest confidence
3. **Three-layer architecture**:
   - **Layer 1 (Plugin)**: Claude Code commands (`/ingest`, `/search`), agents (format-detector, orchestrator), skills
   - **Layer 2 (MCP)**: Tools for heavy operations (format detection, preprocessing, ingestion)
   - **Layer 3 (Standalone)**: Python package usable in CI/CD, scripts, testing

**Reframing impact**: Preprocessing runs on the R2R server side (or a companion service), not in the devcontainer. The MCP server handles orchestration. Claude Code sends file paths or content via MCP tools; the server-side pipeline does the heavy lifting.

Adding new formats (Notion, Confluence, EPUB, code repos) = one Python file implementing BasePreprocessor, placed in `preprocessors/` directory. No manifest changes, no restarts.

### Q4: MVP and phased roadmap

**Phase 0 (Spike) -> Phase 1 (PDF pipeline) -> Phase 2 (Quality) -> Phase 3 (Extended ingestion).**

**Phase 0: SPIKE-01 (1-2 days)**
- Clone R2R fork (done -- `/workspace/repos/R2R/main/`)
- Locate MCP implementation: find tool definitions, schemas, transport mechanism
- Catalog available tools vs. needed tools
- Determine: use native MCP directly, or build thin wrapper?
- Test connectivity: can Claude Code's MCP client reach the R2R server?

**Phase 1: Core MVP -- "Ingest PDF, search from Claude Code" (1 week)**
- ING-04: Chunk metadata schema
- ING-01: PDF text ingestion
- RET-01: Chunk size tuning (1024/100 baseline)
- RET-02: Embedding model config (Ollama mxbai-embed-large)
- MCP-03: Claude Code connection config (`.claude/settings.json` entry)
- MCP-04: End-to-end smoke test (ingest 1 PDF -> query via MCP -> verify sources)

**Phase 2: Retrieval Quality (1 week)**
- RET-05: Metadata injection into context (source attribution)
- AGT-01: Multi-turn retrieval API contract
- RET-03: HyDE (optional, evaluate benefit vs. latency)
- RET-04: Reranking (if quality insufficient without it)

**Phase 3: Extended Ingestion + Plugin System (1-2 weeks)**
- ING-05: Obsidian vault preprocessor
- ING-06: Scientific PDF (math/formula handling)
- Plugin scaffolding: BasePreprocessor, registry, auto-discovery
- ING-02: PDF visual/VLM (if R2R server has GPU)

### Q5: Technical caveats

**See Section 3 (Corrected Risk Register).** Summary:
- 4 formerly-CRITICAL risks eliminated by architectural reframing
- 2 HIGH risks remain: MCP maturity, model role confusion
- 1 MEDIUM-HIGH: context window pressure
- 1 MEDIUM: embedding model migration
- 3 LOW: auth, incremental sync, tool surface (resolved by fork inspection)

---

## Section 5: Corrected MVP Scope

### Removed (per reframing)

| Removed Item | Why |
|---|---|
| Docker Compose inside devcontainer | R2R runs externally |
| Firewall allowlist tickets (OPS-02) | External server has internet |
| Native-vs-Docker decision for devcontainer | Not applicable |
| `pip install r2r` in devcontainer | MCP is the interface |
| Postgres volume mapping for DinD | External Postgres |
| CPU resource allocation planning | Separate servers |

### Added (per reframing)

| Added Item | Why |
|---|---|
| R2R connection config (URL + API key) | Must point to external R2R server |
| Fork inspection task (SPIKE-01) | Must understand actual MCP implementation before building |
| Network connectivity verification | Devcontainer must reach R2R server |

### MVP Ticket Table

| Ticket | Name | Phase | Dependencies | Notes |
|---|---|---|---|---|
| **SPIKE-01** | Inspect R2R fork MCP implementation | 0 | None | **New.** Locate tools, schemas, transport. Decide native vs wrapper. |
| **ING-04** | Chunk Metadata Schema | 1 | SPIKE-01 | Foundation; blocks all ingestion |
| **ING-01** | PDF Text Ingestion | 1 | ING-04 | Pure text PDFs; no VLM |
| **RET-01** | Chunk Size Tuning | 1 | ING-04 | 1024/100 baseline, configurable |
| **RET-02** | Embedding Model Configuration | 1 | None | Ollama mxbai-embed-large on R2R server |
| **MCP-03** | Claude Code Connection Config | 1 | SPIKE-01 | `.claude/settings.json` entry for R2R |
| **MCP-04** | End-to-End Smoke Test | 1 | All Phase 1 | Ingest PDF -> query -> verify sources |
| **RET-05** | Metadata Injection into Context | 2 | ING-04, AGT-01 | Source attribution in retrieved chunks |
| **AGT-01** | Multi-Turn Retrieval API Contract | 2 | SPIKE-01 | Defines search input/output schemas |

### Example `.claude/settings.json` Entry

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
      "args": ["-m", "r2r.mcp"],
      "env": {
        "R2R_API_URL": "http://host.docker.internal:7272",
        "R2R_API_KEY": "${R2R_API_KEY}"
      }
    }
  }
}
```

Note: The exact command, args, and env will be determined by SPIKE-01 after inspecting the fork's MCP server code. The above is a projection based on standard MCP patterns.

---

## Section 6: Action Items

1. **Clone R2R fork** -- Done. Available at `/workspace/repos/R2R/main/`.

2. **Inspect R2R MCP implementation** (SPIKE-01):
   - Locate MCP server entry point (likely in `py/` or `services/`)
   - Catalog all exposed tools and their input/output schemas
   - Determine transport: stdio, SSE, or HTTP
   - Check: does it support `search`, `ingest`, `delete`, `list_documents`, `list_collections`?
   - Check: does it support metadata filtering on search?
   - Check: what auth mechanism does it use?

3. **Decide: use R2R's native MCP vs. thin wrapper**
   - If native MCP covers >= 80% of needed tools with stable schemas -> use directly
   - If significant gaps -> build thin wrapper (< 200 LOC) around R2R REST API
   - If fundamentally insufficient -> build full MCP gateway (Review 2's Option A)

4. **Configure `.claude/settings.json` with R2R MCP entry**
   - Based on findings from step 2
   - Test tool discovery: Claude Code must see R2R tools via `/mcp` or equivalent

5. **Begin Phase 1 implementation**
   - ING-04 (metadata schema) first
   - ING-01 + RET-01 + RET-02 in parallel
   - MCP-03 + MCP-04 to close the loop

---

## Section 7: Appendix -- Review Divergences

| Topic | Review 1 (MVP Focus) | Review 2 (Agnosticity) | Review 3 (Plugin Architecture) | Composite Resolution |
|---|---|---|---|---|
| **Primary concern** | MCP maturity + offline constraints | Coupling + missing abstraction layer | Plugin extensibility + preprocessing | MCP maturity (after reframing eliminates offline concerns) |
| **DinD severity** | CRITICAL | CRITICAL | CRITICAL | **N/A** (R2R external) |
| **Internet severity** | CRITICAL | CRITICAL | CRITICAL (showstopper) | **N/A** (R2R external) |
| **Wrapper recommendation** | 50-line fallback if R2R MCP flaky | 500-1000 LOC gateway with abstract backend | Custom MCP wrapper, Terraform-style | Inspect fork first; thin wrapper only if needed |
| **Agnosticity stance** | "Not agnostic" but pragmatic | "Misleading" -- needs vendor-neutral schemas | "False" -- deeply coupled | Acknowledged; defer abstraction to v1.1 |
| **EPIC 5 verdict** | Defer MOD-02/03/05; keep MOD-01/04 | Defer entire EPIC | Collapse to single config ticket | Keep MOD-04 only (Ollama on R2R server) |
| **Plugin system** | Three-layer: pipeline + MCP + plugin | Plugin with .mcp.json bundling MCP server | Three-layer: plugin + MCP + standalone | Three-layer consensus; preprocessing runs server-side |
| **MVP ticket count** | 9 | 7 + ARCH-01 | 10 + ops tickets | 9 (ops tickets removed per reframing) |
| **RET-05 in MVP** | No (v1.1) | No (Phase 2) | Yes | Yes (Phase 2 of MVP, essential for attribution) |
| **AGT-03/04** | In MVP | Premature | Deferred | Deferred -- prompt tuning, not architecture |
| **Phase 0 spike** | SPIKE-01: validate MCP hands-on | ARCH-01: build gateway skeleton | Not explicit (implied) | SPIKE-01: inspect fork, then decide |
| **Custom MCP tools proposed** | `rag_ingest`, `rag_search` | 15+ tools (analysis, context, validation) | 4 tools (detect, preprocess, validate, ingest) | Start with R2R's native tools; add as needed |
| **Context window strategy** | top_k=3, prompt budgeting | Flagged as critical, no specific fix | 18K/turn accumulation, no fix | top_k=3 default; budget in agent prompt; track usage |

---

## Source Reviews

- [ArchReview_1.md](./ArchReview_1.md) -- Agent 1: MVP definition, technical caveats, phased roadmap
- [ArchReview_2.md](./ArchReview_2.md) -- Agent 2: Agnosticity evaluation, MCP tool surface, dependency analysis
- [ArchReview_3.md](./ArchReview_3.md) -- Agent 3: Plugin architecture, future-proofing, ING-05/ING-06 extensibility
