# Worldbuilding Assistant — Review Summary & Recommendations

## Overall take

A genuinely strong hobby project with a clear product idea and unusually good
documentation. The core architecture is sound — this is textbook RAG done right.
The weaknesses are almost entirely **hygiene and consistency**, not design.

**Verdict:** *Good project, a weekend of cleanup from being something I'd trust to
set up.*

## What's right

- **The embedding/reasoning split is excellent** — the local model does embeddings
  only, Claude does all reasoning. The right line in the right place; I'd leave it
  untouched.
- **Local embedding is the correct default** for this use case (bulk ingestion is
  free/unmetered, and copyrighted sourcebooks never leave the machine), and the
  **hybrid-search default** smartly compensates for embedding weakness on TTRPG
  proper nouns.
- **Docs are top-tier** — README, quickstart, design.md, troubleshooting. The
  architecture diagram and tools table make the system legible fast.
- **Clean MCP code** with a consistent `try/except → "Error: …"` pattern (correct
  for MCP — the model needs to *see* errors), plus thoughtful touches (graph
  staleness warnings, fail-soft builder import, reload-vs-rebuild distinction).

## Suggested improvements (ordered by value / effort)

### Repo hygiene — do first, cheap & high-impact

1. Delete `ignore_this_folder_old/` (committed cruft, also a typo'd filename).
2. Gitignore the generated eval outputs under
   `plugins/worldbuilding-workspace/**/outputs/`.
3. Remove the committed `requirements/tmp/improvements.plan.md`.
4. Rename or fold in `test_verification_d2/d3/d4.py` — the opaque names read like
   leftover scaffolding.
5. Rename `requirements/` → `specs/` (it holds EARS specs, not pip deps — a
   guaranteed double-take in a Python repo).

### Dependencies & CI

6. **Pin dependencies in one source of truth** (`pyproject.toml` or
   `requirements.txt`). Today deps live only as inline `pip install` lines in the
   README + CI — and they already differ. `r2r`/`mcp` move fast; this *will* break
   silently.
7. Add `ruff`/`black` to CI — would auto-catch the type-hint issues below.

### Code consistency

8. Fix the type hints that lie: `book: str = None` → `str | None = None` in the
   `sourcebooks` and `vault-graph` servers (the wrapper already does it right; this
   also affects the generated tool schemas).
9. Unify the three servers' **search settings** behind a shared helper —
   `sourcebooks` uses hybrid search, the generic wrapper doesn't, against the same
   R2R.
10. Standardize defensiveness — the wrapper uses `getattr(...)`, while `sourcebooks`
    does bare `chunk.metadata` / `.score` on the same object.
11. Dead output: `r2r_mcp_wrapper.py:70` prints `"{n} of {n} chunks"` — always
    X of X.

### Product-level

12. **Document the embedding model as an explicit knob** with a loud warning that
    swapping it requires a full re-ingest (it's the one cheap lever for retrieval
    quality, and the lock-in isn't currently called out). Offer a commercial /
    `bge-m3` "higher quality" option for GPU / no-cost-concern users.
13. Decide what "License: Private repository" should actually say for a project
    you're sharing.

## What I would *not* change

The embedding/reasoning split, the local-first default, the pre-computed graph
design, and the generic-vs-domain MCP server separation are all well-reasoned.
Don't let cleanup tempt you into re-architecting — the bones are good.

---

## Feature roadmap — bigger swings (beyond cleanup)

These go past hygiene into new capability. Roughly ordered by leverage. ⭐ = the
two I'd build first.

### Close the biggest gap

**R1. ⭐ Make the GM's own vault semantically searchable.** *(high value, medium
effort)* Today vault access is native file tools + the wikilink graph — so finding
canon relies on `grep` for exact strings and following explicit `[[links]]`. But
the GM's canon is exactly what you most need to search *by meaning*: "have I
established anything about how magic works in the north?" misses the note titled
"The Frostbinding" that never says those literal words. **Fix:** ingest the vault
into R2R as a *second collection* and add a `vault_semantic_search` tool. This turns
the system from "searchable sourcebooks + navigable vault" into "semantically
searchable everything," and it unlocks R2 and R5 below. Build this first.

### Enforce the principles the project already states

**R2. Automated contradiction detection.** *(medium)* The skill's #1 rule is "never
contradict canon" — but it's enforced by hope, not tooling. Add a tool that takes
draft content, semantically retrieves the most-related canon (needs R1), and asks
Claude to flag conflicts before writing: "You describe Lord Aldric as alive, but
`Session-14.md` records his death." Makes the canon-hierarchy principle *real*.

**R4. Provenance back-links.** *(low–medium)* When Claude generates content
"inspired by" a sourcebook, record the book + page in the new note's frontmatter
(`inspired_by: "Lost Omens p.124"`). Verifiable lineage, and it makes the
"adapt, don't copy" rule auditable.

### Cheap wins over the existing graph

**R5. Orphan & dead-link detection.** *(low)* Surface notes nobody links to
(forgotten lore) and `[[wikilinks]]` pointing at notes that don't exist (stubs the
GM meant to write). Trivial over the existing `.graph.json`, immediately useful.

### Killer GM-experience features

**R8. ⭐ Session-prep mode.** *(medium)* "I'm running tonight, the party is heading
to Ironhold." → assembles a one-page briefing: NPCs they'll likely meet (with
current state), open plot threads touching that location, relevant rules/lore,
recent session callbacks. This is the feature a GM would open the tool for *every
week* — most everything else is plumbing that serves it.

**R9. Spoiler / knowledge-tier separation.** *(medium)* Tag content as GM-secret vs
player-known. Then "generate a handout for my players about the Ironhold Council"
produces something safe to share — no hidden agendas leaked. A genuine
differentiator; no Obsidian plugin does this well.

### Engineering investments that de-risk everything above

**R11. Turn the existing eval harness into a CI retrieval regression test.**
*(medium)* There's already a `with_skill` / `without_skill` eval structure sitting
unused in `plugins/worldbuilding-workspace/`. Promote it: a small golden set of
queries with expected-relevant chunks, run recall@k in CI. Then "I changed chunking
/ swapped the embedding model — did retrieval get worse?" becomes a number, not a
vibe. This is what makes R1 and any embedding change *safe to ship*.

**R12. Ship it as a one-command Claude Code plugin.** *(medium)* It's already
structured under `plugins/`. The 8-step manual setup is the single biggest adoption
barrier (the quickstart's own macOS/Docker-Desktop friction, documented below,
proves it). A marketplace-installable plugin that registers the 3 MCP servers + the
skill in one step would 10× who can actually use this.

**Suggested build order** (all eight are worth doing — this just sequences them by
dependency and payoff):

1. **R11** first — stand up the eval-in-CI harness so every later change is measured,
   not guessed. Cheap insurance that makes everything else safe to ship.
2. **R1** next — semantic vault search is the foundation; R2 and R5 build directly on
   it, and it's the single biggest capability gap.
3. **R5 + R4** — quick wins riding on the existing graph / R1 (low effort, immediate
   value).
4. **R2** — contradiction detection, once R1's canon index exists.
5. **R8** — session-prep mode, the feature that earns weekly use (leans on R1 + the
   graph).
6. **R9 + R12** — spoiler tiers and one-command install; ship these as the
   product-polish pass that makes it shareable.

---

## Implementation notes — setup validation (2026-06-08)

Stood the whole system up from scratch on **macOS / Docker Desktop**, following
the `add-release-devcontainer-and-quickstart` branch: **Light Mode** + the
bundled demo content (`docs/demo-walkthrough.md`). End-to-end verified — all
three bundled sourcebooks ingested (incl. the image-only Vol III OCR'd
client-side via tesseract: 59 clean chunks), `verify_ingestion.py --all` = 3/3
PASS, semantic search returns cited chunks, and the devcontainer's MCP path to
host R2R/Ollama works under the locked-down egress firewall.

### The branch already fixes the two worst `latest`-image time-bombs

Confirms the dependency-pinning concern (#6 above) was real. Both surfaced as
hard failures on a clean Full-Mode start, and the branch already pins them:

- **Hatchet gRPC port** — `hatchet-engine` defaults `grpcPort` to 7070, but the
  broadcast address + compose mapping use 7077, so r2r crash-loops registering
  ingestion workflows. Branch sets `SERVER_GRPC_PORT=7077` **and** adds a
  `wait-for-hatchet-grpc` init container (the engine's `/live` healthcheck only
  proves HTTP is up, not gRPC).
- **R2R API port** — the `sciphiai/r2r:latest` image now defaults `R2R_PORT`
  to 8000, but compose maps/health-checks 7272. Branch pins `R2R_PORT=7272`.

### NEW — macOS / Docker Desktop blockers the branch does NOT handle

The devcontainer + Light-Mode compose are effectively Linux-only as shipped. On
Docker Desktop you hit three blockers in sequence (all fixed locally this
session; see the preceding commit):

1. **`compose.yaml` `172.17.0.1:7272:7272` bind** errors on Docker Desktop
   ("cannot assign requested address" — that bridge IP doesn't exist on the
   Mac host). The demo-walkthrough mentions deleting it; the quickstart doesn't.
   *Fix:* drop the line on macOS. *Recommend:* a `compose.override.yaml` or a
   documented one-liner so it isn't a manual edit to a tracked file.
2. **`devcontainer.json` SSH mount** uses `${localEnv:SSH_AUTH_SOCK}`, which on
   macOS is a launchd socket Docker Desktop **cannot bind-mount** → the
   container fails to start before you ever reach a terminal. *Fix:* mount
   Docker Desktop's `/run/host-services/ssh-auth.sock` instead. *Recommend:*
   make the SSH mount OS-conditional (or document the swap).
3. **`init-firewall.sh` allowlists only the default-route gateway** on
   7272/11434. On Docker Desktop `host.docker.internal` is a *separate* address
   (`192.168.65.254`), not the gateway — so the egress firewall silently drops
   every MCP→R2R/Ollama call. `/mcp` may even connect, but all `search_lore` /
   embedding calls fail. *Fix (already cross-platform safe):* also resolve
   `host.docker.internal` (IPv4) and allow it on the same two ports.
   **Recommend upstreaming this one unconditionally** — it's a no-op on Linux.

Also added `examples/ttrpg/.mcp.json` (the demo MCP server config per
`docs/demo-walkthrough.md`) so the bundled example is runnable out of the box.

### Doc nits found while validating

- Health check returns `{"results":{"message":"ok"}}`, but quickstart §2e and
  demo-walkthrough §5 still say `{"results":{"response":"ok"}}`.
- demo-walkthrough §7 says `build_vault_graph.py` prints `0 notes, 0 edges` for
  the empty scaffold, but it reports **8 notes / 17 edges** — it indexes
  `CLAUDE.md` + the 7 files under `templates/`. Either exclude `templates/` from
  the graph or update the expected output.

**Net:** the core works and is genuinely pleasant to set up *on Linux*. A short
"macOS / Docker Desktop" subsection in the quickstart + demo-walkthrough (items
1–2) plus upstreaming the firewall fix (item 3) would make it work out-of-the-box
for Mac users, who are otherwise blocked at the devcontainer step.
