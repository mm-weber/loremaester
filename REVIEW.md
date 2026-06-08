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
