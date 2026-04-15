# LLM Microservices: Specialist Model Pipeline for Worldbuilding

> **Date:** 2026-04-15
> **Context:** Research into decomposing the monolithic Claude Opus dependency into a pipeline of task-specific smaller models, analogous to the monolith-to-microservices evolution in backend architecture.

---

## Current Architecture: One Model Does Everything

The worldbuilding pipeline currently runs all reasoning through a single general-purpose LLM (Claude Opus/Sonnet). R2R contributes only one 670MB embedding model (`mxbai-embed-large`) for vector search — all intelligence lives in Claude.

A typical interaction ("Create an NPC tavern keeper for Ironhold") requires Claude to:

1. **Parse intent** → "worldbuilding creation request"
2. **Plan tool calls** → vault_search, vault_graph, search_lore
3. **Interpret results** → extract relevant facts from 5+ sources
4. **Synthesize context** → "what's established as canon"
5. **Generate content** → NPC description, personality, voice
6. **Format as vault note** → YAML frontmatter + markdown + wikilinks
7. **Decide file path** → correct folder based on note type
8. **Judge completeness** → "should I ask the GM or proceed?"

Each of these is a different cognitive task with different difficulty and model requirements.

---

## Model Demand Per Task

| Task | Capability needed | Minimum viable model | Difficulty |
|------|-------------------|---------------------|------------|
| Intent classification | Text classification | 0.6-1B | Trivial |
| Tool call planning | Tool selection from 13 options | 4B with tool-call tuning | Medium |
| Result interpretation | Extractive summarization | 7B | Medium |
| Multi-source synthesis | Cross-document reasoning | 14-32B | Hard |
| Creative writing | Voice matching, worldbuilding | 32B+ or fine-tuned | Hard |
| YAML/frontmatter generation | Structured output | 4B with constrained gen | Easy with guardrails |
| Wikilink generation | Recall from context | 14B+ | Medium-Hard |
| Judgment/escalation | Nuanced decision-making | 32B+ or Opus | Hard |

---

## Proposed Pipeline: Specialist Models

```
┌──────────────┐
│ ROUTER        │ Qwen 3 0.6B / Phi-4 mini
│ ~0.6B params  │ "What kind of request is this?"
│ <10ms         │ → classify: search-only | create-note | complex
└──────┬───────┘
       │
┌──────▼──────────┐
│ TOOL PLANNER     │ Qwen 3 4B / Gemma 4 4B
│ ~4B params       │ "Which MCP tools, in what order?"
│ Tool-call tuned  │ → [vault_search, vault_graph, search_lore]
└──────┬───────────┘
       │
┌──────▼──────────┐
│ CONTEXT DISTILLER│ Qwen 3 7B
│ ~7B params       │ "Summarize these 5 search results + 3 notes
│ Summarization    │  into a coherent context brief"
└──────┬───────────┘
       │
┌──────▼──────────┐
│ CREATIVE WRITER  │ Qwen 3.5 32B / Command R 35B
│ ~32B params      │ "Write an NPC that fits this context"
│ Fine-tuned on    │ → personality, voice, description
│ TTRPG content    │ (this is where quality MATTERS)
└──────┬───────────┘
       │
┌──────▼──────────┐
│ FORMATTER        │ Phi-4 3.8B / fine-tuned
│ ~4B params       │ "Convert to vault note with YAML frontmatter,
│ Constrained gen  │  wikilinks, correct folder path"
│ JSON/YAML mode   │ → structured output, deterministic
└──────┬───────────┘
       │
┌──────▼──────────┐
│ VALIDATOR        │ Rule-based (no model needed)
│ 0 params         │ "Is YAML valid? Do wikilinks reference real
│ Python code      │  notes? Is frontmatter schema correct?"
└─────────────────┘
```

---

## Resource Comparison

| Component | Model | VRAM | Latency | Cost per call |
|---|---|---|---|---|
| Router | Qwen 3 0.6B | 0.5 GB | ~10ms | ~free |
| Tool Planner | Qwen 3 4B | 3 GB | ~100ms | ~free |
| Context Distiller | Qwen 3 7B | 5 GB | ~500ms | ~free |
| Creative Writer | Qwen 3.5 32B | 20 GB | ~3-5s | ~free (local) |
| Formatter | Phi-4 3.8B | 3 GB | ~200ms | ~free |
| Validator | Python code | 0 | ~1ms | free |
| **Total** | | **~32 GB peak** | **~4-6s** | **$0.00** |

vs. current Opus: **$0.22/interaction, ~5-10s latency, zero local compute**

---

## Claude Tier Analysis (for comparison)

| Model | Cost/interaction | Creative quality | Tool routing | Best for |
|---|---|---|---|---|
| **Haiku 4.5** | ~$0.02 | Flat, functional | Unreliable with 13 tools | Search-only queries |
| **Sonnet 4.6** | ~$0.08 | Good, reasonable voice matching | Solid | 80% of worldbuilding requests |
| **Opus 4.6** | ~$0.22 | Best synthesis and judgment | Best | Complex multi-source creative work |

### Cascade pattern (hybrid)
```
Request → Haiku classifies complexity
  "simple lookup"  → Haiku handles it      (~$0.02)
  "create note"    → Sonnet handles it     (~$0.08)
  "complex synth"  → Opus handles it       (~$0.22)
```
Expected cost reduction: ~60% with maintained quality.

---

## Local Model Candidates (2026)

| Model | Size | VRAM | Tool calling | Creative | RAG quality | Best for |
|---|---|---|---|---|---|---|
| **Qwen 3 30B-A3B** | 30B (3B active) | 16GB | Good | Good | Strong | Best bang/buck — MoE fits in 16GB |
| **Qwen 3.5 32B** | 32B | 24GB | Strong | Strong | Strong | Best overall local |
| **Gemma 4 27B** | 27B | 24GB | Built-in MCP | Good | Strong | Native MCP tool calling |
| **Llama 4 Scout** | 17B active / 109B total | 24-48GB | Good | Decent | Good | Overkill for this use case |
| **Command R 35B** | 35B | 24GB | Built-in citations | Decent | **Best** — inline source grounding | Only local model with citation grounding |
| **Phi-4 3.8B** | 3.8B | 3GB | Basic | Weak | Decent | Structured output / formatting only |

---

## Why This Is Viable Now (2026)

1. **MoE models** — Qwen 3 30B-A3B activates only 3B parameters per token but has 30B total knowledge. Fits in 16GB, thinks like 30B.
2. **Native tool calling** — Gemma 4, Qwen 3, Llama 4 all ship with tool-calling fine-tuning out of the box.
3. **Structured output guarantees** — Ollama and vLLM support constrained generation (JSON mode, grammar-guided). A 4B model generating YAML with grammar constraints never produces invalid YAML.
4. **Fine-tuning on consumer hardware** — QLoRA on 12GB VRAM. Fine-tune the Creative Writer on your vault's writing style with ~100 examples.
5. **Industry trend** — Organizations use task-specific AI models 3x more than general-purpose LLMs. Hybrid routing cuts costs 30-85% while maintaining quality.

---

## The Orchestrator Problem

In microservices you have API gateways and message queues. In LLM microservices, the orchestrator needs to route, plan, marshal context between specialists, validate outputs, and escalate failures.

| Approach | Pros | Cons |
|---|---|---|
| **Hardcoded pipeline** (Python) | Fast, predictable, no model | Rigid — can't adapt to novel requests |
| **Small model router** (0.6-4B) | Flexible, cheap | Can misroute — needs fallback |
| **Claude as orchestrator** (Sonnet) | Best judgment, handles edge cases | Defeats purpose if going local |
| **Hybrid: code + small model** | Route 90% by rules, 10% by model | Best practical approach |

---

## Mapping to Existing Architecture

The MCP architecture is already halfway there:

```
Current:
  Claude (monolith) → MCP tools → R2R / vault-graph / sourcebooks

Microservice evolution:
  Orchestrator (code + tiny model)
    → Tool Planner (4B) → MCP tools → R2R / vault-graph / sourcebooks
    → Context Distiller (7B) → summarize results
    → Creative Writer (32B) → generate content
    → Formatter (4B) → structure as vault note
    → Validator (code) → check output
```

The MCP servers don't change. R2R doesn't change. Only the "brain" gets decomposed.

---

## Pragmatic Implementation Path

**Phase 1 (today):** Sonnet default, Opus for complex. Zero infrastructure change.

**Phase 2 (low-hanging fruit):** Add a code-based validator for generated vault notes (valid YAML? wikilinks reference real notes? correct folder?). No model needed — just Python.

**Phase 3 (model router):** Qwen 3 0.6B classifies requests into tiers. Simple lookups go to local 7B. Creative generation stays with Sonnet/Opus. Cuts API costs ~60%.

**Phase 4 (full pipeline):** Replace creative writer with fine-tuned local 32B trained on vault's writing style (~100 example notes, QLoRA fine-tuning).

---

## Quality vs Cost Tradeoff

```
             Quality
                ▲
                │
     Opus ──────┤─────────── best creative output
                │
   Sonnet ──────┤─── good enough for 80% of tasks
                │
Local 32B ──────┤── decent, needs fine-tuning for voice
                │
Pipeline of ────┤── sum > parts, but orchestration
specialists     │   complexity is real
                │
Local 7B ───────┤── adequate for search/lookup only
                │
                └──────────────────────────────────► Cost
               $0                              $0.22/call
              (local)                          (Opus)
```

---

## Sources

- [Small Language Models: Complete Guide 2026](https://www.knolli.ai/post/small-language-models)
- [5 Patterns for Scalable LLM Service Integration](https://latitude-blog.ghost.io/blog/5-patterns-for-scalable-llm-service-integration/)
- [Intelligent LLM Routing: Multi-Model AI Cuts Costs by 85%](https://www.swfte.com/blog/intelligent-llm-routing-multi-model-ai)
- [Model Router: Running a Team of Local LLMs](https://medium.com/@michael.hannecke/the-model-router-running-a-team-of-local-llms-instead-of-one-big-one-fd75eeec9d39)
- [xRouter: Training Cost-Aware LLM Orchestration via RL](https://arxiv.org/html/2510.08439v1)
- [IBM Research: LLM Routing for Quality, Low-Cost Responses](https://research.ibm.com/blog/LLM-routers)
- [Fine-Tune Local LLMs 2026 Practical Guide](https://www.sitepoint.com/fine-tune-local-llms-2026/)
- [Best Ollama Models for RAG, Coding & Agents 2026](https://www.morphllm.com/best-ollama-models)
- [Best Local LLMs for RAG 2026](https://insiderllm.com/guides/best-local-llms-rag/)
- [Best Small AI Models for Ollama 2026](https://localaimaster.com/blog/small-language-models-guide-2026)
- [SLMs Win 2026 Efficiency Race](https://byteiota.com/small-language-models-win-2026-efficiency-race/)
- [Claude Model Selection Guide](https://www.sitepoint.com/claude-model-selection-framework/)
- [Gemma 4 vs Qwen 3.5 vs Llama 4 Benchmarks](https://ai.rs/ai-developer/gemma-4-vs-qwen-3-5-vs-llama-4-compared)
