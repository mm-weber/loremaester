# Testing Report — R2R Worldbuilding Assistant

**Date:** 2026-06-07 → 2026-06-09
**Tester:** Dustin (with Claude Code)
**Goal:** Stand up the worldbuilding assistant from scratch and validate it end-to-end on **macOS / Docker Desktop**.
**Result:** ✅ **Working end-to-end.** All core capabilities verified live. Three macOS-specific blockers were found and fixed (without them, the devcontainer does not run on Docker Desktop).

---

## 1. Environment

| | |
|---|---|
| Host OS | macOS (Apple Silicon), Docker Desktop |
| Branch | `add-release-devcontainer-and-quickstart` → work committed on `setup-validation-macos` |
| R2R mode | **Light Mode** (`docker/compose.yaml`, `--profile postgres --profile minio`) — Postgres + MinIO + R2R + dashboard; in-process orchestration (no Hatchet/Unstructured) |
| Embeddings | Ollama `mxbai-embed-large` (1024-dim) on the host — embeddings only; Claude does all reasoning |
| Devcontainer | Custom build (Claude Code CLI, tesseract, MCP deps baked in) + egress firewall |
| Content | Bundled demo: 3 Grunvyr sourcebooks + `Grunvyr_Campaign` scaffold + 4 GM skills |

Architecture: heavy services (R2R, Postgres, Ollama) run on the **host**; Claude Code + the 3 MCP servers run **in the devcontainer** and reach the host via `host.docker.internal:7272` (R2R) and `:11434` (Ollama).

---

## 2. Setup performed (host)

1. Installed `uv`; pulled `mxbai-embed-large` (Ollama already present).
2. Brought up R2R **Light Mode**; verified health `{"results":{"message":"ok"}}` on `localhost:7272`.
3. Ingested the 3 bundled sourcebooks and verified:

| Book | Type | Ingest path | Chunks | Verify |
|---|---|---|---|---|
| Grunvyr Sourcebook (Vol I) | text-native | R2R native | 63 | PASS |
| Grunvyr Vol II — Nethergloam | text-native | R2R native | 66 | PASS |
| Grunvyr Vol III — ImageOnly | **image-only** | **client-side OCR (tesseract)** | 59 | PASS |

`verify_ingestion.py --all` → **3 passed, 0 warned, 0 failed.** Search coherence 0.66–0.73.

4. Built the demo vault graph; built + launched the devcontainer (`npx @devcontainers/cli up`).

---

## 3. Bugs found & fixed

### Already fixed by the branch (confirmed real — both are `latest`-image time-bombs)
- **Hatchet gRPC port** — engine defaults `grpcPort` to 7070 while everything else uses 7077 → r2r crash-loops. Branch sets `SERVER_GRPC_PORT=7077` **and** adds a `wait-for-hatchet-grpc` init container. *(Only relevant to Full Mode.)*
- **R2R API port** — `sciphiai/r2r:latest` now defaults `R2R_PORT=8000`, but compose maps/health-checks 7272. Branch pins `R2R_PORT=7272`.

### NEW — macOS / Docker Desktop blockers (fixed this session; see `setup-validation-macos`)
1. **`compose.yaml` `172.17.0.1:7272:7272` bind** errors on Docker Desktop ("cannot assign requested address"). → drop the line on macOS.
2. **`devcontainer.json` SSH mount** uses `${localEnv:SSH_AUTH_SOCK}` (a macOS launchd socket Docker Desktop **cannot bind-mount**) → container fails to start. → mount `/run/host-services/ssh-auth.sock`.
3. **`init-firewall.sh` allowlists only the default-route gateway** on 7272/11434. On Docker Desktop `host.docker.internal` is a *separate* address (`192.168.65.254`), so the egress firewall **silently dropped every MCP→R2R/Ollama call** — `/mcp` could connect but all searches/embeds failed. → also resolve `host.docker.internal` (IPv4) and allow it on the same two ports. **This fix is cross-platform safe and should be upstreamed unconditionally.**

After (3), connectivity from inside the container was verified: R2R health OK, Ollama models listed, live search returned cited chunks — all under the locked-down firewall.

### Doc nits
- Health check returns `{"results":{"message":"ok"}}`, but quickstart §2e / demo-walkthrough §5 still say `{"results":{"response":"ok"}}`.
- demo-walkthrough §7 says `build_vault_graph.py` prints `0 notes` for the empty scaffold; it actually reports **8** (it indexes `CLAUDE.md` + the 7 `templates/`).

---

## 4. Live demo results (A–F, run in-container)

Full transcript: `demo-session.jsonl` / `demo-session.pretty.json` (50 tool calls captured) / `demo-session.md` (readable).

| Demo | Capability | Result | Evidence |
|---|---|---|---|
| **A** | Multi-book semantic search + citations | ✅ Pass | "Emberdeeps" answered from Vol II Ch. III + Sourcebook, with book/page citations and a pulled quote |
| **B** | OCR of image-only PDF → searchable | ✅ Pass | Vol III (image-only) summarized coherently — chapters, factions, D.R. 1622 dating; Claude flagged "minor scanning artifacts" |
| **C** | `worldbuilding` skill → new NPC | ✅ Pass | `Vorn Hearthoath.md` written; frontmatter matched `NPC Template.md`; graph 8→9 |
| **D** | `session-creation` skill → full session | ✅ Pass | Asked 3 framing questions, wrote 11 files (Session 1 main + 5 scenes + 4 locations + 1 NPC), added a backlink to Vorn; **composed with `worldbuilding`**; graph 9→20 |
| **E** | `vault-scout` Haiku dispatch | ⚠️ Partial | Correct table produced, but with only 2 NPC notes the agent inlined the read instead of dispatching Haiku — primitive **unproven, not broken** |
| **F** | `chronik` → campaign chronicle | ✅ Pass | `Campaign_Chronicle.md` written from player notes; **withheld vs shared info preserved** (Vendholm letter, "Vorn doesn't know the siphon is a person", "Skardi doesn't know they're crown-commissioned"); graph 20→22 |

**Net:** every layer proven for real — host R2R + Ollama embeddings, client-side OCR ingestion, three MCP servers reaching the host from inside a hardened devcontainer, and all four GM skills (including skill composition).

---

## 5. Vault artifacts produced by the demo

```
Grunvyr_Campaign/
├── NPC/        Vorn Hearthoath.md, Halda Truetally.md
├── Locations/  The Hold.md, The Sunlit Gate.md, The King's Forge.md, The Vaults.md
├── Sessions/Session 1/  2026-06-09 Session 1.md + 5 scene files
└── PC/         Campaign_Chronicle.md, PlayerNotes/Session-1.md
```
Final graph: **22 notes, 185 edges.** (All untracked demo artifacts, not committed.)

---

## 6. Recommendations (for the maintainer)

1. **Upstream the firewall fix** (§3.3) — it's a no-op on Linux and unblocks all Mac users.
2. Add a short **"macOS / Docker Desktop"** subsection to the quickstart + demo-walkthrough covering §3.1–3.2 (compose bind, SSH socket) so Mac users aren't blocked at the devcontainer step.
3. Fix the two **doc nits** (§3, health string + graph-build count).
4. Consider the broader items in `REVIEW.md` (dependency pinning, type hints, etc.).

---

## 7. Files in this bundle

| File | What |
|---|---|
| `TESTING-REPORT.md` | This report |
| `demo-session.jsonl` | Full native session transcript (every event, raw) |
| `demo-session.pretty.json` | Same data, indented array — easiest for inspecting tool calls |
| `demo-session.md` | Human-readable transcript (prompts + Claude prose + tool-call markers) |

The macOS edits were refined on the branch to stay **cross-platform** (Linux unaffected). The full applied fixes and the broader code/architecture review (`REVIEW.md`) live on branch **`setup-validation-macos`**.
