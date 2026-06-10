# README Marketing Design (Working Draft)

> **Status:** in-progress brainstorm. Hero and "What you get" are LOCKED;
> comparison table and other sections pending. Iterating section-by-section with user.
> Not committed. Promote to `docs/superpowers/specs/2026-06-07-readme-marketing-design.md`
> when all sections are locked.
>
> **Style rule for this entire doc and the final README:** no em-dashes. Use commas,
> periods, parentheses, colons, or semicolons. See [[feedback-no-em-dashes-in-writing]].

## Decisions locked

1. **Primary audience:** TTRPG GM who codes. AI/portfolio readers served by secondary sections layered below the fold.
2. **Karpathy timeline:** subtle convergent-design note in the README; full provenance story lives in [`ATTRIBUTION.md`](../ATTRIBUTION.md).
3. **Length:** tight conversion (~150 to 220 lines).
4. **Comparison treatment:** named factual table for `claude-obsidian`; prose footnote for Karpathy (a pattern, not a product, so it doesn't belong in a feature table).
5. **Hero voice:** Option A, the "Vault + Books" vivid hook with layered workflow depth.

## Section outline (working)

```
# Worldbuilding Assistant for Claude Code
  [hero paragraph (Option A)]
  [30-min demo CTA blockquote]

## What you get                                ← 5 sharp feature bullets (LOCKED iter-4)
## Retrieval is a tool here, not the product   ← LOCKED techie section (replaces comparison table)
## See it in 30 minutes                        ← bundled-demo conversion pitch
## What's inside
   ### Architecture                            ← ASCII diagram (sharpened)
   ### 3 MCP servers, 14 tools                 ← table
   ### 4 Claude Code skills                    ← table (new; currently under-marketed)
   ### OCR pipeline                            ← pypdfium2 + per-page hybrid + figure regions
   ### Hardened devcontainer                   ← NEW: surface the security work
   ### Multi-instance Docker Compose           ← short blurb
## Quickstart                                  ← 6-line command sketch + link to full guide
## What's not included (yet)                   ← honesty signal; v0.2 roadmap, brief
## Related work                                ← Karpathy + claude-obsidian footnote
## Contributing & community
## License
```

## Hero block (LOCKED 2026-06-07)

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

## "What you get": 5 bullets (LOCKED at iter-4)

### User's draft (with fact-check annotations)

1. *Cross-reference your library of PDF sourcebooks and your personal campaign notes inside your Obsidian vault for the most consistent-in-itself worldbuilding session ever seen to date.*
   - ⚠ "most consistent-in-itself...ever seen to date": hype, unprovable, cut.

2. *Leverage four opinionated GM skills (worldbuilding, session-creation, chronik, vault-scout) and 13 MCP tools (vault_graph, search_lore...) to create Sessions, Locations and NPCs that are consistent with your campaign history.*
   - ⚠ "13 MCP tools": actual count is **14** (5+3+6).

3. *Ingest Text, Hybrid and Image-Only PDF documents using GPU powered EASYOCR, uses Hybrid BM25+vector search to search your RAG.*
   - ⚠ "Text, Hybrid and Image-Only": actual classification is **text-native / mixed / image-only**. "Hybrid" is the OCR routing approach, not a doc type.
   - ⚠ "GPU powered EASYOCR" as default: actually **tesseract (CPU) is default**; EasyOCR (GPU) is opt-in with auto-fallback.
   - ⚠ "BM25+vector": overclaims specificity; R2R hybrid is semantic + keyword via pgvector + PostgreSQL FTS, not literal BM25.

4. *Ships as a best-practice setup: Claude Code runs inside a hardened devcontainer that separates Claude's work from your host system and uses a firewall to forbid access to unwanted locations on the internet.*
   - ✓ True, but **understates**. The firewall is **default-DROP with an allowlist**, not just "forbid unwanted." Also: DinD removed for security, agent runs unprivileged, full security review in `.devcontainer/SecurityReview.md`.

5. *Bring your own already existing Obsidian vault or start fresh. Use the 30 min demo to jump right in and start your worldbuilding excellence today.*
   - ✓ Core claim true.
   - ⚠ "worldbuilding excellence today": hype, cut.

### Locked rewrite (iter-4)

1. **Cross-reference your vault and your scanned sourcebooks in one prompt, end-to-end.** Claude walks your wikilink graph via the `vault-graph` MCP server, queries sourcebooks via hybrid semantic + keyword search, drafts a new NPC / location / session with correct frontmatter and `[[wikilinks]]`, writes it to the right vault folder, and refreshes the graph. No tool switching, no copy-pasting.

2. **Four opinionated GM skills (`worldbuilding`, `session-creation`, `chronik`, `vault-scout`) that auto-trigger on your prompts**, driving 14 MCP tools (`vault_graph`, `search_lore`, …) to draft Sessions, Locations, and NPCs that stay consistent with your campaign history.

3. **Drop a folder of PDFs (text-native, mixed, or image-only) and walk away.** The bulk ingester auto-classifies each PDF, routes text-native straight to R2R, OCRs scanned ones per-page with `pypdfium2` + `tesseract` (CPU default) or opt-in **EasyOCR on CUDA** (auto-falls back if no GPU), and skips books already ingested. Stored in PostgreSQL + pgvector; retrieved via R2R's **hybrid semantic + keyword search with reciprocal rank fusion (RRF)**. Every result carries book / chapter / page citations.

4. **Ships in a hardened devcontainer.** Default-DROP egress firewall with a small allowlist (GitHub, PyPI, Anthropic, VS Code telemetry), Docker-default seccomp, no Docker-in-Docker, agent runs unprivileged. Threat model and design rationale: [`.devcontainer/SecurityReview.md`](.devcontainer/SecurityReview.md).

5. **Bring your own Obsidian vault, or start with the bundled `Grunvyr_Campaign` scaffold.** The 30-minute [demo walkthrough](docs/demo-walkthrough.md) ships three sourcebooks (one image-only as the OCR exhibit), an empty campaign vault, and six prompts that exercise every layer end-to-end.

### Iteration log

- **Iter 1, rejected.** B1 missed the vault-graph MCP path (said "Claude reads the vault natively"; incomplete, the wikilink graph navigation is MCP-mediated). B2 introduced "named GM discipline", in-group jargon that confuses cold readers. Lesson saved to memory as [[feedback-marketing-no-unexplained-jargon]].
- **Iter 2, partial accept.** B1 named the `vault-graph` MCP server alongside native file tools. B2 adopted user's tighter framing and corrected 13 to 14 tool count. B3 led with "GPU OCR shipped" + RRF framing. User then asked for *automation momentum* in B1/B2/B3; the previous wording read passive and list-y, not end-to-end.
- **Iter 3, partial accept.** Shifted B1/B2/B3 from feature-exhaustion to end-to-end-action framing:
  - **B1:** added the write-back + graph-refresh half of the loop (5 chained actions, not 3 actions + a consequence)
  - **B2:** made the skills the agent (*auto-trigger on your prompts, driving 14 MCP tools*) instead of the reader being the agent (*leverage*)
  - **B3:** foregrounded the hands-off bulk ingest (*drop a folder and walk away*); surfaced auto-classify, auto-route, auto-fallback, and idempotent skip, all already in the codebase but invisible in iter-2's wording
- **Iter 4, accepted.** Em-dashes purged from B1 and B3 per user style preference (B2/B4/B5 were already clean). Saved as memory [[feedback-no-em-dashes-in-writing]] for future writing work. Em-dash replacements: comma for "in one prompt, end-to-end"; period + paired coda "No tool switching, no copy-pasting"; parentheses for the PDF-type list; period before "Every result carries…".

### Search-tech fact-check (resolves the "BM25 vs RRF" question)

User intuition was BM25 + vector. Verification trail:

- **Repo code only sets `use_hybrid_search=True`** in `mcp-servers/sourcebooks/server.py:31,103`. No algorithm selection. So the algorithm is whatever R2R's server does internally.
- **R2R's own README** (`https://github.com/SciPhi-AI/R2R`) marketing copy says verbatim: *"Hybrid Search: Semantic + keyword search with reciprocal rank fusion"*. No BM25 mention.
- **R2R SDK installed:** `3.6.6`; server image: `sciphiai/r2r:latest`. Server source not grep-able from inside this devcontainer (GitHub code search requires auth not wired here; raw URL guesses 404'd).
- **claude-obsidian's docs** (already fetched) explicitly use BM25: *"BM25 sparse + optional contextual-prefix + cosine rerank"*. So the comparison-table contrast actually becomes sharper using R2R's own framing.

**Conclusion:** Mirror R2R's framing → "hybrid semantic + keyword search with reciprocal rank fusion (RRF)". This is exactly as defensible as R2R itself markets it (and RRF is the more sophisticated-sounding signal vs. BM25 anyway).

### Status: LOCKED at iter-4 (accepted 2026-06-07)

## Techie section (LOCKED 2026-06-09): "Retrieval is a tool here, not the product"

> **Status:** Replaces the comparison table from the earlier draft. Positioning angle is
> Angle A (positive architectural claim, no feature-stack comparison). User-authored prose,
> tightened by Claude across two iterations.

### Section header (suggested)
*Retrieval is a tool here, not the product*

### Section body

> Most RAG systems make the LLM a prisoner of the retriever. **The Worldbuilding Assistant makes retrieval a tool the LLM chooses to use.**
>
> Classic RAG caps answer quality at whatever the embedding model coughs up in one shot. If the search misses, the generator hallucinates confidently over bad context. The LLM has no agency over what it sees.
>
> Here, it flips. Claude Code sits above the retrieval layer as planner, reasoner, and writer. R2R is a leaf tool it calls, alongside direct file reads (`Grep`/`Read` over the GM's vault canon) and a human-authored wikilink graph. The agent decides when to search, what to search, and whether the result is good enough. It can pull from the vault graph, ask a clarifying question, write a new canonical note, and rebuild the graph.
>
> Retrieval recall stops being the ceiling. Reasoning is. And the system gets more trustworthy over time: every synthesis loop writes structured, human-reviewed canon back into the vault. The knowledge base compounds instead of drifting.
>
> Vector search is necessary. It was never sufficient. This is what it looks like to treat it that way.

### Related-work footnote (sits after the section body)

> For the broader "persistent-wiki" pattern that names this neighborhood, see Andrej Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). This repo is an independent, domain-specific implementation that predates it; see [ATTRIBUTION.md](ATTRIBUTION.md) for the full provenance. A general-purpose agent-loop sibling in adjacent territory: [`claude-obsidian`](https://github.com/AgriciDaniel/claude-obsidian). 🎩

### Iteration trail (for future reference)

- **Original user draft:** 5 paragraphs, ~270 words, first-person voice (*Mine* / *I flipped it* / *ask me*), 4 em-dashes.
- **Iter 1 (Claude):** em-dashes purged, one hedge cut (*and crucially*), light tightening. ~225 words.
- **Iter 2 (Claude):** product-voice coupling (anchor name = "Loremaester" experimentally), further tightening. ~192 words.
- **Iter 3 (LOCKED):** anchor name swapped back to "The Worldbuilding Assistant" per user direction (Loremaester rename deferred to a separate task). Brand anchor used **once** in para 1 thesis; *"Here, it flips"* and *"the system"* carry the other reference points. Saves the prose from name-heaviness.

### Search-tech wording (locked at iter-4 in bullets, holds here too)

Mirror R2R's own framing: "hybrid semantic + keyword search with reciprocal rank fusion (RRF)". The keyword leg under the hood is Postgres FTS (`tsvector` + `ts_rank`), not literal BM25; `design.md` lines 135-144 carries that distinction for technical readers who want the detail.

## "Contributing & community" + "License" closing block (LOCKED 2026-06-09)

> **Status:** Tightened existing README copy. Em-dashes purged (4 in Contributing, 2 in License); `THIRD_PARTY_LICENSES.md` reference corrected to `THIRD_PARTY_NOTICES.md` per commit `f308474`; Attribution bullet expanded to reinforce the Karpathy convergent-design footnote.

### Section bodies

> ## Contributing & community
>
> - **[Contributing guide](CONTRIBUTING.md):** workflow, testing standards, what we will and won't merge.
> - **[Code of Conduct](CODE_OF_CONDUCT.md):** Contributor Covenant v2.1.
> - **[Security policy](SECURITY.md):** how to report a vulnerability privately.
> - **[Attribution](ATTRIBUTION.md):** credits for the software this project builds on, plus the convergent-design note on Karpathy's LLM Wiki pattern.
>
> ## License
>
> This project's own code is released under the **MIT License**. See [LICENSE](LICENSE).
>
> It orchestrates third-party components that retain their own licenses, notably [R2R](https://github.com/SciPhi-AI/R2R) (MIT). The client-side OCR stack is fully permissive: tesseract/pytesseract (Apache-2.0), pypdfium2 (Apache-2.0/BSD-3), and the optional GPU path easyocr (Apache-2.0) with torch (BSD-3).
>
> See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for full attribution and important usage notes before redistributing or hosting this project.

## "Quickstart" section (LOCKED 2026-06-09)

> **Status:** Adapted from existing README's quickstart. Added `(on the host)` / `(inside the devcontainer)` location annotations to each step; replaced existing em-dash; combined trailing pointers into one reader-intent-framed line.

### Section body

> ### Quickstart
>
> ```bash
> # 1. Pull the embedding model and start Ollama (on the host)
> ollama pull mxbai-embed-large && ollama serve
>
> # 2. Start R2R in Light Mode (Full Mode + Unstructured.io: see docs/quickstart.md)
> docker compose -f docker/compose.yaml --profile postgres --profile minio up -d
>
> # 3. Build your vault graph (inside the devcontainer)
> uv run --no-project scripts/build_vault_graph.py /path/to/vault
>
> # 4. Install MCP dependencies (inside the devcontainer)
> pip install mcp r2r pyyaml
>
> # 5. Configure MCP servers in .claude/settings.json (see docs/quickstart.md)
> ```
>
> Full setup with your own vault and sourcebooks: [`docs/quickstart.md`](docs/quickstart.md). Or run the [bundled demo](docs/demo-walkthrough.md) first if you want to see it work end-to-end (about 30 minutes).

## "What's not included (yet)" section (LOCKED 2026-06-09)

> **Status:** 3-bullet honesty section. Multi-instance validation gap intentionally lives only in `docs/demo-walkthrough.md`'s "Out of scope for v0.1" list, not duplicated here, so the README doesn't argue with its own "What's inside / Multi-instance deployment" subsection. Sharp readers going deep get the nuance; skim readers get a coherent surface.

### Section body

> ### What's not included (yet)
>
> This is a v0.1 release. The honest gaps:
>
> - **Windows hosts.** Linux and macOS are the supported and validated platforms for v0.1. The Ollama install path and `host.docker.internal` networking diverge on Windows and haven't been tested.
> - **Non-TTRPG domain adaptation.** The `sourcebooks` MCP server's metadata schema (`book_title` / `chapter` / `page_range`) and the worldbuilding skill template assume TTRPG vocabulary. Adapting to other domains (legal, engineering, academic) is on the v0.2 roadmap.
> - **End-to-end collection scoping.** The generic `r2r` MCP wrapper supports `collection_ids`, but the `sourcebooks` server and the `ingest_books.py` / `verify_ingestion.py` CLIs don't yet scope by collection. Per-corpus isolation needs this wiring; tracked as R-3 in [`specs/v0.2/specs_v0.2.md`](specs/v0.2/specs_v0.2.md).

### Sourcing trail

- **Windows hosts:** `docs/demo-walkthrough.md` host-prereqs table ("Windows is not currently supported") + "Out of scope for v0.1" list.
- **Non-TTRPG adaptation:** `docs/demo-walkthrough.md` "Out of scope for v0.1" item 1.
- **End-to-end collection scoping:** `specs/v0.2/specs_v0.2.md` R-3 (status "Open" / v0.2).

## "What's inside" section (LOCKED 2026-06-09)

> **Status:** All six subsections drafted and signed off. The **Hardened devcontainer** subsection is tagged for a v0.1 release-prep revisit (per user note 2026-06-09: "chore for v0.1 release"). Wording is fine for now; the revisit will check copy against any late-cycle security-review updates before tagging v0.1.

### Section body

> ## What's inside
>
> ### Architecture
>
> ```
>   HOST MACHINE                                    DEVCONTAINER (hardened)
>  ┌───────────────────────────────────┐           ┌────────────────────────────────┐
>  │                                   │           │  Claude Code                   │
>  │  Ollama (:11434)                  │           │    ├─ r2r MCP server           │
>  │  └─ mxbai-embed-large             │           │    ├─ sourcebooks MCP server   │
>  │                                   │           │    ├─ vault-graph MCP server   │
>  │  R2R Server (:7272)               │◄─────────►│    └─ 4 GM skills              │
>  │  ├─ PostgreSQL + pgvector         │  host.    │       (worldbuilding,          │
>  │  ├─ Unstructured.io (Full Mode)   │  docker.  │        session-creation,       │
>  │  └─ Hatchet (Full Mode)           │  internal │        chronik, vault-scout)   │
>  │                                   │           │                                │
>  │  R2R Dashboard (:7273)            │           │  Obsidian vault (bind mount)   │
>  └───────────────────────────────────┘           │  .graph.json                   │
>                                                  └────────────────────────────────┘
> ```
>
> R2R runs on the host (heavy services: pgvector, optionally Unstructured.io + Hatchet for Full Mode); Claude Code runs in a hardened devcontainer with MCP servers reaching R2R over the docker bridge via `host.docker.internal:7272`. Full component rationale in [`docs/design.md`](docs/design.md).
>
> ### 3 MCP servers, 14 tools
>
> | Server | Tools | Role |
> |---|---|---|
> | **`r2r`** | `search`, `ingest_document`, `list_documents`, `delete_document`, `list_collections` | Generic CRUD + search against R2R. |
> | **`sourcebooks`** | `search_lore`, `list_books`, `get_chapter` | Worldbuilding-aware lore queries with `book_title` / `chapter` / `page_range` citations. |
> | **`vault-graph`** | `vault_graph`, `vault_backlinks`, `vault_search_notes`, `vault_central_notes`, `vault_reload_cache`, `vault_rebuild_graph` | Obsidian `[[wikilink]]` graph navigation and refresh. |
>
> ### 4 Claude Code skills
>
> | Skill | What it does | When it fires |
> |---|---|---|
> | **`worldbuilding`** | Gathers vault context + sourcebook lore, drafts a new NPC / location / faction with correct frontmatter and `[[wikilinks]]`, writes it back, rebuilds the graph. Vault canon outranks sourcebook lore. | Any "create X" / "add Y" worldbuilding request. |
> | **`session-creation`** | Orchestrates a Lazy DM session prep using the 8 Steps + Situations Checklist per scene. Writes a session folder with the main note and per-scene Encounter notes. | "Prepare Session N…" |
> | **`chronik`** | Updates the Campaign Chronicle from player notes, preserving a who-told-whom-what exchange matrix so the campaign record stays auditable. | "Update the chronicle from session N's notes." |
> | **`vault-scout`** | Dispatches mechanical sweeps (frontmatter collection, tabulation, scans) to Haiku, keeping the main agent on judgment work and token cost low. | "Tabulate every NPC by faction and level." |
>
> Each skill auto-triggers on matching prompts and orchestrates the MCP tools above. No manual invocation.
>
> ### OCR pipeline
>
> `scripts/ingest_books.py` auto-classifies each PDF (text-native / mixed / image-only via `detect_pdf_type.py`) and routes by type. Text-native goes straight to R2R. Mixed and image-only run through `scripts/ocr_extract.py`: per-page hybrid extraction with `pypdfium2` for page rendering, then `tesseract` (CPU default) or opt-in `EasyOCR` on CUDA (with auto-fallback to tesseract if no usable GPU is present). Embedded figure regions are OCR'd separately and appended to the page text. Already-ingested books are reported SKIPPED, so re-runs are safe and idempotent.
>
> ### Hardened devcontainer
>
> `.devcontainer/init-firewall.sh` configures a default-DROP egress firewall with a small allowlist (GitHub, npm, PyPI/uv, Anthropic, VS Code telemetry); host access is scoped to the docker-bridge gateway on ports `7272` (R2R) and `11434` (Ollama) only. Docker-in-Docker was deliberately removed (incompatible with the host-R2R networking AND it would gut the sandbox); the only Linux capability granted is `NET_ADMIN`, used by the firewall, not Docker. The agent shell runs as the unprivileged `node` user; PID 1 runs as root only long enough to apply iptables rules. Full threat model and design rationale: [`.devcontainer/SecurityReview.md`](.devcontainer/SecurityReview.md).
>
> ### Multi-instance deployment
>
> Run multiple isolated R2R instances on one host (e.g., one for your campaign vault, one for a coding-research vault) via `docker/scripts/r2r-infra.sh` (shared Postgres + MinIO) and `docker/scripts/r2r-instance.sh <name> up` (per-vault R2R + dashboard). Each instance gets its own Postgres schema, port range, and TOML config. See `docker/instances/` for examples.

## "See it in 30 minutes" section (LOCKED 2026-06-09)

> **Status:** Conversion bridge between the techie section and the deep "What's inside" subsections. Concrete proof of the architectural claim, hand-off to `docs/demo-walkthrough.md` for deep readers.

### Section body

> ### See it in 30 minutes
>
> You don't need your own vault or sourcebook collection to evaluate this. The repo ships a complete working demo: three Grunvyr sourcebooks (one image-only as the OCR proof point), an empty `Grunvyr_Campaign` vault scaffold, and six demo prompts that exercise every layer of the system. **From `git clone` to ready-to-play session prep in your vault: about 30 minutes. The assistant does the toil; you review and run the table.**
>
> What the six prompts prove:
>
> | # | Prompt | What it proves |
> |---|---|---|
> | A | List the books, then search the Emberdeeps. | Multi-book hybrid search with `book_title` + `page_range` citations. |
> | B | Summarize Volume III. | OCR ingestion of the image-only sourcebook (per-page hybrid, pypdfium2 + tesseract). |
> | C | Draft a master-smith NPC for `Grunvyr_Campaign`. | The `worldbuilding` skill fuses vault canon + sourcebook research and writes a frontmatter-correct note. |
> | D | Prepare Session 1 using the 8 Steps of the Lazy DM. | `session-creation` orchestrates vault + sourcebook + brainstorming into a Lazy-DM session folder. |
> | E | Tabulate every NPC by name, faction, level. | `vault-scout` dispatches Haiku for the mechanical sweep so the main agent stays on judgment work. |
> | F | Update the Campaign Chronicle from player notes. | `chronik` preserves who-told-whom-what across NPC interactions (information-exchange matrix). |
>
> Full walk-through, including host prereqs and verification steps: [`docs/demo-walkthrough.md`](docs/demo-walkthrough.md).

### Iteration note

- Original opener: *"From git clone to a Claude-drafted NPC saved into the vault: about 30 minutes."* Reframed by user to point at *session prep* (Demo D's deliverable), not just an NPC, and to surface the toil-handling value claim.
- Final opener uses a two-sentence structure with the GM-aware *"run the table"* role-split closer. The role-split construction (*"the assistant does X; you do Y"*) follows the durable Stripe/Copilot pattern: preserve the user's authorship, offload only the labor.

## Deltas from current README

- **ADD:** bold hero rewrite (problem-first, vivid)
- **ADD:** "What you get" 5-bullet block
- **ADD:** "How this differs from related work" section with named table
- **ADD:** "See it in 30 minutes" demo-callout section (currently buried in Documentation list)
- **ADD:** dedicated "4 Claude Code skills" subsection (currently mentioned but not pitched)
- **ADD:** "Hardened devcontainer" subsection (currently invisible in README)
- **ADD:** "What's not included (yet)" honesty section (v0.2 backlog from `requirements_v0.2.md`)
- **ADD:** "Related work" footnote
- **KEEP:** architecture diagram (sharpen labels slightly)
- **KEEP:** MCP servers table (move under "What's inside")
- **KEEP:** quickstart + multi-instance mention (terser)
- **CUT:** the long PEP 723 "Running the scripts" paragraph (belongs in `docs/quickstart.md`)
- **CUT:** full "Project Structure" tree (belongs in `docs/design.md`; replace with one-line callout for browsers)

## Voice / register

Confident-but-credible. No hype words ("powerful", "amazing", "revolutionary"). No em-dashes (commas, periods, parentheses, colons, or semicolons instead). No emoji except the one 🎩 hat-tip in the related-work paragraph (mirrors `ATTRIBUTION.md`'s existing tone). Headlines bold-claim; body sentences ground each claim in a specific file, count, or behavior.

## Open topics (next on the list)

- ~~Comparison table per-row finalization~~. **MOOT**: replaced by the LOCKED techie section above (Angle A).
- ~~Related work footnote phrasing~~. **LOCKED** as the trailing paragraph inside the techie section.
- ~~"See it in 30 minutes" demo-callout phrasing~~. **LOCKED** 2026-06-09.
- ~~"What's inside" subsections~~. **LOCKED** 2026-06-09. (Hardened devcontainer subsection tagged for a v0.1 release-prep revisit: copy is fine, will recheck against any late-cycle security-review updates before tagging v0.1.)
- ~~"What's not included (yet)" honesty section~~. **LOCKED** 2026-06-09 (3 bullets: Windows, Non-TTRPG, Collection scoping).
- ~~"Quickstart" section~~. **LOCKED** 2026-06-09 (5-step command sketch with host/devcontainer location annotations + reader-intent-framed trailing pointer).
- "Contributing & community" + "License" closing block (next; tighten existing README bullets and license blurb, drop em-dashes, fix the stale `THIRD_PARTY_LICENSES.md` → `THIRD_PARTY_NOTICES.md` link from the recent rename commit)
- "What's not included (yet)" section content: which v0.2 items to surface
- Quickstart sketch (6 commands?) and what to defer to `docs/quickstart.md`
- License section phrasing
- Architecture diagram refinement (current ASCII is solid, minor label tweaks only)
- **Deferred (separate task):** project rename to "Loremaester" (will touch hero H1, bullets header, `ATTRIBUTION.md`, existing README body, design doc).
