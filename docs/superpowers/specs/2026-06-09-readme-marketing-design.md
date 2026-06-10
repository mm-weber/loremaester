# README Marketing Design

> **Status:** Approved for implementation. All sections LOCKED 2026-06-07 through 2026-06-09.
> **Source:** [`tasks/readme-marketing-design.md`](../../../tasks/readme-marketing-design.md) (working brainstorm with full iteration history).
> **Style rule:** No em-dashes in the rendered README. Use commas, periods, parentheses, colons, or semicolons. (See [[feedback-no-em-dashes-in-writing]] in user memory.)

## 1. Overview

Defines a tight-conversion marketing rewrite of the existing `README.md` for the Worldbuilding Assistant for Claude Code (this repo). Replaces a documentation-shaped README with a marketing-shaped one that positions the project on architectural moat (agent-loop reasoning, retrieval as a leaf tool, write-back to vault) rather than feature stack comparison. Target length ~150 to 220 rendered lines.

## 2. Positioning decisions (locked)

1. **Primary audience:** TTRPG GM who codes. AI/portfolio readers are served by secondary sections layered below the fold; their needs do not override hero/CTA choices.
2. **Karpathy timeline:** subtle convergent-design note in the README. Full provenance lives in `ATTRIBUTION.md`.
3. **Length:** tight conversion (~150 to 220 lines).
4. **Comparison treatment:** No feature-stack comparison table. Replaced by a prose "techie section" with a positive architectural claim. `claude-obsidian` appears as a one-line footnote.
5. **Hero voice:** "Vault + Books" vivid hook, layered with workflow depth (Option A from the brainstorm).
6. **Search-tech framing:** mirror R2R's own README wording: "hybrid semantic + keyword search with reciprocal rank fusion (RRF)". The keyword leg is Postgres FTS (`tsvector` + `ts_rank`), not literal BM25; that distinction lives in `docs/design.md` for deep readers.
7. **No em-dashes anywhere in the final README.**

## 3. Voice / register rules

- Confident-but-credible. No hype words (*powerful*, *amazing*, *revolutionary*).
- Headlines bold-claim; body sentences ground each claim in a specific file, count, or behavior.
- Product-voice with strategic name anchors. Personal-voice ("I", "Mine") is OK in `ATTRIBUTION.md` but not in the README body.
- One emoji exception: the 🎩 hat-tip in the Karpathy related-work paragraph, mirroring `ATTRIBUTION.md`'s tone.
- Marketing copy avoids in-group jargon. Bullets and hero lines must be self-sufficient; never gesture at a concept like "named GM discipline" without proving it in the same sentence. (See [[feedback-marketing-no-unexplained-jargon]] in user memory.)
- Automation-momentum framing: state what the system does end-to-end, not a list of capabilities. Verbs like *auto-classifies*, *routes*, *walks*, *writes*, *refreshes*. Skills are agents that auto-trigger; the reader is not the agent.

## 4. Section outline

```
# Worldbuilding Assistant for Claude Code
  [hero block, locked]
  [30-min demo CTA blockquote, locked]

## What you get
  [5 sharp feature bullets, locked at iter-4]

## Retrieval is a tool here, not the product
  [techie section, locked; replaces the original "How this differs from related work" idea]
  [Karpathy + claude-obsidian related-work footnote lives at the end of this section]

## See it in 30 minutes
  [conversion bridge: bundled-demo pitch + 6-prompt table, locked]

## What's inside
  ### Architecture        [ASCII diagram + one-sentence rationale]
  ### 3 MCP servers, 14 tools  [table]
  ### 4 Claude Code skills [table]
  ### OCR pipeline        [prose]
  ### Hardened devcontainer [prose; tagged for v0.1 release-prep revisit]
  ### Multi-instance deployment [prose]

## Quickstart
  [5-step command sketch with host/devcontainer location annotations + reader-intent pointer]

## What's not included (yet)
  [3 honesty bullets: Windows, Non-TTRPG, Collection scoping]

## Contributing & community
  [4 governance link bullets]

## License
  [3 paragraphs: project's own MIT, permissive deps callout, THIRD_PARTY_NOTICES.md pointer]
```

## 5. Section bodies (implementation-ready)

### 5.1. Hero block

```markdown
# Worldbuilding Assistant for Claude Code

**Half your canon is on a shelf of scanned PDFs you can't search.
The other half is in an Obsidian vault Claude can't fully navigate.
This fixes both.**

A Claude Code setup that turns your Obsidian campaign vault and your
TTRPG sourcebooks (yes, scanned ones) into a single, citable,
wikilink-walkable knowledge base, then ships four GM-workflow skills
that use it: `worldbuilding`, `session-creation`, `chronik`,
`vault-scout`.

> **Run the 30-minute demo on the bundled Grunvyr campaign** →
> [docs/demo-walkthrough.md](docs/demo-walkthrough.md)
```

### 5.2. "What you get" (5 bullets)

```markdown
## What you get

1. **Cross-reference your vault and your scanned sourcebooks in one prompt, end-to-end.** Claude walks your wikilink graph via the `vault-graph` MCP server, queries sourcebooks via hybrid semantic + keyword search, drafts a new NPC / location / session with correct frontmatter and `[[wikilinks]]`, writes it to the right vault folder, and refreshes the graph. No tool switching, no copy-pasting.

2. **Four opinionated GM skills (`worldbuilding`, `session-creation`, `chronik`, `vault-scout`) that auto-trigger on your prompts**, driving 14 MCP tools (`vault_graph`, `search_lore`, …) to draft Sessions, Locations, and NPCs that stay consistent with your campaign history.

3. **Drop a folder of PDFs (text-native, mixed, or image-only) and walk away.** The bulk ingester auto-classifies each PDF, routes text-native straight to R2R, OCRs scanned ones per-page with `pypdfium2` + `tesseract` (CPU default) or opt-in **EasyOCR on CUDA** (auto-falls back if no GPU), and skips books already ingested. Stored in PostgreSQL + pgvector; retrieved via R2R's **hybrid semantic + keyword search with reciprocal rank fusion (RRF)**. Every result carries book / chapter / page citations.

4. **Ships in a hardened devcontainer.** Default-DROP egress firewall with a small allowlist (GitHub, PyPI, Anthropic, VS Code telemetry), Docker-default seccomp, no Docker-in-Docker, agent runs unprivileged. Threat model and design rationale: [`.devcontainer/SecurityReview.md`](.devcontainer/SecurityReview.md).

5. **Bring your own Obsidian vault, or start with the bundled `Grunvyr_Campaign` scaffold.** The 30-minute [demo walkthrough](docs/demo-walkthrough.md) ships three sourcebooks (one image-only as the OCR exhibit), an empty campaign vault, and six prompts that exercise every layer end-to-end.
```

### 5.3. Techie section: "Retrieval is a tool here, not the product"

```markdown
## Retrieval is a tool here, not the product

Most RAG systems make the LLM a prisoner of the retriever. **The Worldbuilding Assistant makes retrieval a tool the LLM chooses to use.**

Classic RAG caps answer quality at whatever the embedding model coughs up in one shot. If the search misses, the generator hallucinates confidently over bad context. The LLM has no agency over what it sees.

Here, it flips. Claude Code sits above the retrieval layer as planner, reasoner, and writer. R2R is a leaf tool it calls, alongside direct file reads (`Grep`/`Read` over the GM's vault canon) and a human-authored wikilink graph. The agent decides when to search, what to search, and whether the result is good enough. It can pull from the vault graph, ask a clarifying question, write a new canonical note, and rebuild the graph.

Retrieval recall stops being the ceiling. Reasoning is. And the system gets more trustworthy over time: every synthesis loop writes structured, human-reviewed canon back into the vault. The knowledge base compounds instead of drifting.

Vector search is necessary. It was never sufficient. This is what it looks like to treat it that way.

> For the broader "persistent-wiki" pattern that names this neighborhood, see Andrej Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). This repo is an independent, domain-specific implementation that predates it; see [ATTRIBUTION.md](ATTRIBUTION.md) for the full provenance. A general-purpose agent-loop sibling in adjacent territory: [`claude-obsidian`](https://github.com/AgriciDaniel/claude-obsidian). 🎩
```

### 5.4. "See it in 30 minutes"

```markdown
## See it in 30 minutes

You don't need your own vault or sourcebook collection to evaluate this. The repo ships a complete working demo: three Grunvyr sourcebooks (one image-only as the OCR proof point), an empty `Grunvyr_Campaign` vault scaffold, and six demo prompts that exercise every layer of the system. **From `git clone` to ready-to-play session prep in your vault: about 30 minutes. The assistant does the toil; you review and run the table.**

What the six prompts prove:

| # | Prompt | What it proves |
|---|---|---|
| A | List the books, then search the Emberdeeps. | Multi-book hybrid search with `book_title` + `page_range` citations. |
| B | Summarize Volume III. | OCR ingestion of the image-only sourcebook (per-page hybrid, pypdfium2 + tesseract). |
| C | Draft a master-smith NPC for `Grunvyr_Campaign`. | The `worldbuilding` skill fuses vault canon + sourcebook research and writes a frontmatter-correct note. |
| D | Prepare Session 1 using the 8 Steps of the Lazy DM. | `session-creation` orchestrates vault + sourcebook + brainstorming into a Lazy-DM session folder. |
| E | Tabulate every NPC by name, faction, level. | `vault-scout` dispatches Haiku for the mechanical sweep so the main agent stays on judgment work. |
| F | Update the Campaign Chronicle from player notes. | `chronik` preserves who-told-whom-what across NPC interactions (information-exchange matrix). |

Full walk-through, including host prereqs and verification steps: [`docs/demo-walkthrough.md`](docs/demo-walkthrough.md).
```

### 5.5. "What's inside"

```markdown
## What's inside

### Architecture

```
  HOST MACHINE                                    DEVCONTAINER (hardened)
 ┌───────────────────────────────────┐           ┌────────────────────────────────┐
 │                                   │           │  Claude Code                   │
 │  Ollama (:11434)                  │           │    ├─ r2r MCP server           │
 │  └─ mxbai-embed-large             │           │    ├─ sourcebooks MCP server   │
 │                                   │           │    ├─ vault-graph MCP server   │
 │  R2R Server (:7272)               │◄─────────►│    └─ 4 GM skills              │
 │  ├─ PostgreSQL + pgvector         │  host.    │       (worldbuilding,          │
 │  ├─ Unstructured.io (Full Mode)   │  docker.  │        session-creation,       │
 │  └─ Hatchet (Full Mode)           │  internal │        chronik, vault-scout)   │
 │                                   │           │                                │
 │  R2R Dashboard (:7273)            │           │  Obsidian vault (bind mount)   │
 └───────────────────────────────────┘           │  .graph.json                   │
                                                 └────────────────────────────────┘
```

R2R runs on the host (heavy services: pgvector, optionally Unstructured.io + Hatchet for Full Mode); Claude Code runs in a hardened devcontainer with MCP servers reaching R2R over the docker bridge via `host.docker.internal:7272`. Full component rationale in [`docs/design.md`](docs/design.md).

### 3 MCP servers, 14 tools

| Server | Tools | Role |
|---|---|---|
| **`r2r`** | `search`, `ingest_document`, `list_documents`, `delete_document`, `list_collections` | Generic CRUD + search against R2R. |
| **`sourcebooks`** | `search_lore`, `list_books`, `get_chapter` | Worldbuilding-aware lore queries with `book_title` / `chapter` / `page_range` citations. |
| **`vault-graph`** | `vault_graph`, `vault_backlinks`, `vault_search_notes`, `vault_central_notes`, `vault_reload_cache`, `vault_rebuild_graph` | Obsidian `[[wikilink]]` graph navigation and refresh. |

### 4 Claude Code skills

| Skill | What it does | When it fires |
|---|---|---|
| **`worldbuilding`** | Gathers vault context + sourcebook lore, drafts a new NPC / location / faction with correct frontmatter and `[[wikilinks]]`, writes it back, rebuilds the graph. Vault canon outranks sourcebook lore. | Any "create X" / "add Y" worldbuilding request. |
| **`session-creation`** | Orchestrates a Lazy DM session prep using the 8 Steps + Situations Checklist per scene. Writes a session folder with the main note and per-scene Encounter notes. | "Prepare Session N…" |
| **`chronik`** | Updates the Campaign Chronicle from player notes, preserving a who-told-whom-what exchange matrix so the campaign record stays auditable. | "Update the chronicle from session N's notes." |
| **`vault-scout`** | Dispatches mechanical sweeps (frontmatter collection, tabulation, scans) to Haiku, keeping the main agent on judgment work and token cost low. | "Tabulate every NPC by faction and level." |

Each skill auto-triggers on matching prompts and orchestrates the MCP tools above. No manual invocation.

### OCR pipeline

`scripts/ingest_books.py` auto-classifies each PDF (text-native / mixed / image-only via `detect_pdf_type.py`) and routes by type. Text-native goes straight to R2R. Mixed and image-only run through `scripts/ocr_extract.py`: per-page hybrid extraction with `pypdfium2` for page rendering, then `tesseract` (CPU default) or opt-in `EasyOCR` on CUDA (with auto-fallback to tesseract if no usable GPU is present). Embedded figure regions are OCR'd separately and appended to the page text. Already-ingested books are reported SKIPPED, so re-runs are safe and idempotent.

### Hardened devcontainer

`.devcontainer/init-firewall.sh` configures a default-DROP egress firewall with a small allowlist (GitHub, npm, PyPI/uv, Anthropic, VS Code telemetry); host access is scoped to the docker-bridge gateway on ports `7272` (R2R) and `11434` (Ollama) only. Docker-in-Docker was deliberately removed (incompatible with the host-R2R networking AND it would gut the sandbox); the only Linux capability granted is `NET_ADMIN`, used by the firewall, not Docker. The agent shell runs as the unprivileged `node` user; PID 1 runs as root only long enough to apply iptables rules. Full threat model and design rationale: [`.devcontainer/SecurityReview.md`](.devcontainer/SecurityReview.md).

### Multi-instance deployment

Run multiple isolated R2R instances on one host (e.g., one for your campaign vault, one for a coding-research vault) via `docker/scripts/r2r-infra.sh` (shared Postgres + MinIO) and `docker/scripts/r2r-instance.sh <name> up` (per-vault R2R + dashboard). Each instance gets its own Postgres schema, port range, and TOML config. See `docker/instances/` for examples.
```

### 5.6. Quickstart

````markdown
## Quickstart

```bash
# 1. Pull the embedding model and start Ollama (on the host)
ollama pull mxbai-embed-large && ollama serve

# 2. Start R2R in Light Mode (Full Mode + Unstructured.io: see docs/quickstart.md)
docker compose -f docker/compose.yaml --profile postgres --profile minio up -d

# 3. Build your vault graph (inside the devcontainer)
uv run --no-project scripts/build_vault_graph.py /path/to/vault

# 4. Install MCP dependencies (inside the devcontainer)
pip install mcp r2r pyyaml

# 5. Configure MCP servers in .claude/settings.json (see docs/quickstart.md)
```

Full setup with your own vault and sourcebooks: [`docs/quickstart.md`](docs/quickstart.md). Or run the [bundled demo](docs/demo-walkthrough.md) first if you want to see it work end-to-end (about 30 minutes).
````

### 5.7. "What's not included (yet)"

```markdown
## What's not included (yet)

This is a v0.1 release. The honest gaps:

- **Windows hosts.** Linux and macOS are the supported and validated platforms for v0.1. The Ollama install path and `host.docker.internal` networking diverge on Windows and haven't been tested.
- **Non-TTRPG domain adaptation.** The `sourcebooks` MCP server's metadata schema (`book_title` / `chapter` / `page_range`) and the worldbuilding skill template assume TTRPG vocabulary. Adapting to other domains (legal, engineering, academic) is on the v0.2 roadmap.
- **End-to-end collection scoping.** The generic `r2r` MCP wrapper supports `collection_ids`, but the `sourcebooks` server and the `ingest_books.py` / `verify_ingestion.py` CLIs don't yet scope by collection. Per-corpus isolation needs this wiring; tracked as R-3 in [`specs/v0.2/specs_v0.2.md`](specs/v0.2/specs_v0.2.md).
```

### 5.8. Contributing & community

```markdown
## Contributing & community

- **[Contributing guide](CONTRIBUTING.md):** workflow, testing standards, what we will and won't merge.
- **[Code of Conduct](CODE_OF_CONDUCT.md):** Contributor Covenant v2.1.
- **[Security policy](SECURITY.md):** how to report a vulnerability privately.
- **[Attribution](ATTRIBUTION.md):** credits for the software this project builds on, plus the convergent-design note on Karpathy's LLM Wiki pattern.
```

### 5.9. License

```markdown
## License

This project's own code is released under the **MIT License**. See [LICENSE](LICENSE).

It orchestrates third-party components that retain their own licenses, notably [R2R](https://github.com/SciPhi-AI/R2R) (MIT). The client-side OCR stack is fully permissive: tesseract/pytesseract (Apache-2.0), pypdfium2 (Apache-2.0/BSD-3), and the optional GPU path easyocr (Apache-2.0) with torch (BSD-3).

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for full attribution and important usage notes before redistributing or hosting this project.
```

## 6. Deltas from the existing README

| Action | Item | Notes |
|---|---|---|
| **ADD** | Bold hero block (problem-first, vivid) | Replaces the existing 2-line intro paragraph. |
| **ADD** | "What you get" 5-bullet block | New section after hero. |
| **ADD** | "Retrieval is a tool here, not the product" prose section | Replaces the originally-planned comparison table. |
| **ADD** | "See it in 30 minutes" conversion section | Was previously buried under the Documentation list. |
| **ADD** | "4 Claude Code skills" subsection table | Skills are currently mentioned but not pitched. |
| **ADD** | "Hardened devcontainer" subsection | Surfaces the security work that is currently invisible in the README. |
| **ADD** | "What's not included (yet)" honesty section | Sourced from `specs/v0.2/` and `docs/demo-walkthrough.md`. |
| **ADD** | Related-work paragraph inside the techie section | Karpathy convergent-design + claude-obsidian sibling line. |
| **KEEP** | Architecture ASCII diagram | Sharpened: shows all 4 skills, marks devcontainer as hardened. |
| **KEEP** | 3 MCP servers table | Moved under "What's inside", "Purpose" relabeled "Role", lightly tightened. |
| **KEEP** | Multi-instance deployment paragraph | Lightly tightened. |
| **KEEP** | Contributing & community bullets | Em-dashes purged, ATTRIBUTION bullet extended. |
| **KEEP** | License section | Em-dashes purged, `orchestrates` framing preserved, notices rename applied. |
| **REVISE** | Quickstart code block | Added `(on the host)` and `(inside the devcontainer)` location annotations to each step; removed em-dash from step 2; combined trailing pointers into one reader-intent-framed line. |
| **REVISE** | License section notices link | `THIRD_PARTY_LICENSES.md` → `THIRD_PARTY_NOTICES.md` (per commit `f308474` 2026-06-07). |
| **CUT** | Long PEP 723 "Running the scripts" paragraph | Move to `docs/quickstart.md` if not already there. |
| **CUT** | Full "Project Structure" tree | Move to `docs/design.md`; replace in README with a one-line callout for browsers if at all. |
| **CUT** | Per-row feature comparison table (never actually written) | Replaced architecturally by the techie section. |

## 7. Open follow-up tasks (deferred from this spec)

1. **Project rename to "Loremaester."** Will touch hero H1, iter-4 bullet B2 / B3 references, `ATTRIBUTION.md`, the existing `docs/design.md`, and any README body references. Tracked as a separate task; do not couple to this README rewrite.
2. **Hardened devcontainer subsection revisit at v0.1 release prep.** Copy is correct as of 2026-06-09; recheck against any late-cycle changes to `.devcontainer/SecurityReview.md` or `init-firewall.sh` before tagging v0.1.
3. **OCR EasyOCR docs hook.** The `What's inside / OCR pipeline` paragraph names CUDA EasyOCR as opt-in; the deeper install incantation (uv `--with`, CUDA wheel index) lives in `docs/quickstart.md` and should stay there.

## 8. Self-review

### 8.1. Placeholder scan

No `TBD`, `TODO`, or `???` strings. All section bodies are concrete and ready to apply. Search-tech wording locked at *"hybrid semantic + keyword search with reciprocal rank fusion (RRF)"* throughout (bullets 3, comparison row that no longer exists, techie section, design.md citation). Tool count locked at 14. Skill count locked at 4. Tested both via `grep` on `mcp-servers/*/server.py` (5 + 3 + 6 = 14) and skill folder count in `skills/`.

### 8.2. Internal consistency

- **Multi-instance:** "What's inside / Multi-instance deployment" describes it as a working feature; "What's not included (yet)" does NOT list it. The validation-gap nuance lives only in `docs/demo-walkthrough.md`'s "Out of scope for v0.1" list. Deliberate trade-off documented in section §5 of the working brainstorm. README does not contradict itself.
- **Search-tech wording:** mirrored across all four touch points (bullet 3 retrieval framing, techie section "Claude Code sits above the retrieval layer" framing, `docs/design.md` lines 129-144 deep dive citation in implementation notes, R2R README quote in the brainstorm fact-check). No conflict.
- **Project name:** all sections use "the Worldbuilding Assistant" or implicit pronouns; the Loremaester rename is deferred and not partially applied anywhere.
- **Em-dashes:** verified zero in this spec via `grep -P '\x{2014}|\x{2013}'` (PCRE Unicode codepoint syntax; the byte syntax `\xE2\x80\x94` fails silently in UTF-8 locales and produces false negatives). The implementation plan and the final README must re-verify with the same correct pattern.

### 8.3. Scope check

This is one README rewrite, single implementation plan. Bounded, not decomposed into sub-projects. Implementation is a straight `Edit`-pass against the existing `README.md` with the section bodies in §5 of this spec.

### 8.4. Ambiguity check

- **Section header for the techie section:** locked at *"Retrieval is a tool here, not the product"*. No ambiguity.
- **Related-work paragraph placement:** lives at the *end* of the techie section, as a blockquote. Not a standalone H2.
- **Hardened devcontainer subsection:** wording is locked but tagged for one more review pre-v0.1. The pre-v0.1 review is OUT of scope for this spec; the words in §5.5 are what ship in this rewrite.
- **Bundled-demo time bound:** "about 30 minutes" referenced in hero CTA blockquote, "See it in 30 minutes" header, and bullet 5. All three say the same thing.

No remaining ambiguity.

## 9. Hand-off

After user approves this spec, the next step per the brainstorming workflow is to invoke the `writing-plans` skill to create a detailed implementation plan for the README rewrite. The implementation itself is a single `Edit` pass against the current `README.md` plus a notices-link rename verification.
