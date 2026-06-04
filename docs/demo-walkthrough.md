# Demo walkthrough

A 30-minute hands-on tour. By the end you will have:

- Booted the full R2R stack inside a devcontainer.
- Ingested three bundled sourcebooks — two text-native, one image-only (Unstructured.io OCRs that one server-side during ingest).
- Watched all four bundled GM skills work against the empty `Grunvyr_Campaign` scaffold: search sourcebooks, draft an NPC, prep a session, run a mechanical vault sweep, and update a campaign chronicle from player notes.

If you're here to set up your own vault and sourcebooks instead, skip this and go to [`quickstart.md`](./quickstart.md) — it's the configuration reference for own-content deployment. For component deep-dives see [`design.md`](./design.md); for known failure modes see [`troubleshooting.md`](./troubleshooting.md).

## What's bundled

| Path | What |
|---|---|
| `examples/ttrpg/sourcebooks/Grunvyr-Sourcebook.pdf` | Vol I — *The Hold, Its Crown & Its Grudges*. Text-native PDF, 19 pages. |
| `examples/ttrpg/sourcebooks/Grunvyr-Vol-II-Nethergloam.pdf` | Vol II — *Into the Nethergloam*. Text-native PDF, 17 pages. |
| `examples/ttrpg/sourcebooks/Grunvyr-Vol-III-ImageOnly.pdf` | Vol III — image-only PDF, 16 pages. This is your OCR exhibit. |
| `examples/ttrpg/skills/` | The four GM skills: `worldbuilding`, `session-creation`, `chronik`, `vault-scout`. |
| `examples/ttrpg/GM-Vault/` | Empty Grunvyr_Campaign vault scaffold + `templates/` + a stripped-down `CLAUDE.md`. |

## Host prerequisites

On the machine where you'll run the devcontainer:

| Requirement | Version / notes |
|---|---|
| **Docker** | Docker Desktop (macOS) or Docker Engine + Compose v2 (Linux). Needed for the outer container the devcontainer runs in. |
| **VS Code with Dev Containers extension** | Or the standalone `devcontainer` CLI. This is what opens the repo "in" the devcontainer. |
| **Ollama** | Running on the host (not inside the container) with `mxbai-embed-large` pulled. The devcontainer reaches it via `host.docker.internal:11434`. Install at <https://ollama.com>, then `ollama pull mxbai-embed-large`. |
| **Disk** | ~10 GB free (devcontainer image + R2R stack image layers + Postgres data + your PDFs) |
| **RAM** | 12 GB+ recommended. The R2R stack inside the devcontainer uses ~3-4 GB; Ollama on the host wants 2+ GB; remainder for headroom. |
| **Network** | Outbound HTTPS to github.com, mcr.microsoft.com, hub.docker.com, pypi.org, astral.sh during build. |

**Windows is not currently supported** — the Ollama install path and `host.docker.internal` networking differ from the configurations validated here. Linux and macOS hosts are the supported platforms for v0.1.

## Step-by-step

### 1. Clone the repo
```bash
git clone git@github.com:mm-weber/R2R-ClaudeCode-integration.git
cd R2R-ClaudeCode-integration
```

### 2. Open in the devcontainer
- **VS Code:** open the folder, then accept the prompt to "Reopen in Container" (or run `Dev Containers: Reopen in Container` from the command palette).
- **CLI:** `devcontainer up --workspace-folder .`

First build: 10-20 minutes (downloading the base image + apt packages + Python deps + Claude Code CLI). Cached rebuild: under 5 minutes.

### 3. Verify the in-container baseline
Once the container opens, in its integrated terminal:
```bash
docker --version                                            # DinD client
python3 --version                                           # ≥ 3.10
pip list | grep -E '^(mcp|r2r|pyyaml|kreuzberg|uv) '       # all 5 present
claude --version                                            # Claude Code CLI
tesseract --version                                         # OCR backend
curl -s http://host.docker.internal:11434/api/tags | head   # Ollama on host
```

If `curl` fails to reach Ollama, double-check it's running on the host and bound to the default `:11434`. The `--add-host=host.docker.internal:host-gateway` runArg in `devcontainer.json` handles the Linux side; on macOS Docker Desktop maps `host.docker.internal` automatically.

### 4. Stage env files
```bash
cd docker/env
cp postgres.env.example     postgres.env
cp r2r-full.env.example     r2r-full.env
cp r2r-dashboard.env.example r2r-dashboard.env
cp hatchet.env.example      hatchet.env
cp minio.env.example        minio.env
cd ../..
```
The defaults are usable for the first launch. See [`quickstart.md`](./quickstart.md) for which values you'd customize for a production deployment.

### 5. Bring up the R2R stack (inside DinD)

The compose project uses a `postgres` profile for the R2R database. Setting `COMPOSE_PROFILES` once means every subsequent compose command in the same shell picks it up without you having to pass `--profile postgres` each time:
```bash
export COMPOSE_PROFILES=postgres
docker compose -f docker/compose.full.yaml up -d
docker compose -f docker/compose.full.yaml ps
```
Expect 3-5 minutes on first start (Hatchet runs database migrations). A short-lived `wait-for-hatchet-grpc` init container runs in the middle to ensure Hatchet's gRPC port is bound before r2r tries to register its workflows — you'll see it as `Exited (0)` in `ps` after a few seconds, which is normal.

Health check:
```bash
curl http://localhost:7272/v3/health
```
Expected: `{"results":{"response":"ok"}}`.

The R2R dashboard is on http://localhost:7273 (auto-forwarded to your host via the `portsAttributes` setting in `.devcontainer/devcontainer.json` — VS Code should offer to open it when r2r-dashboard becomes ready).

### 6. Ingest the bundled sourcebooks
```bash
uv run scripts/detect_pdf_type.py examples/ttrpg/sourcebooks/
uv run scripts/ingest_books.py examples/ttrpg/sourcebooks/ --collection grunvyr
uv run scripts/verify_ingestion.py --collection grunvyr
```
`detect_pdf_type.py` will classify Vol I and Vol II as `text-native` and Vol III as `image-only`. The ingest script routes Vol I/II through R2R directly and OCRs Vol III via the Unstructured.io service running in the compose stack (this takes the longest — a couple of minutes for 16 image pages). When `verify_ingestion.py` completes you should see all three books with chunk counts > 0 and `Overall: PASS`.

> If you only see two books, the OCR ingestion of Vol III may still be running. Wait 60s and re-run `verify_ingestion.py` — or check progress with `docker compose -f docker/compose.full.yaml logs r2r --tail 50`.

### 7. Build the vault graph for `examples/ttrpg/GM-Vault/`

The Grunvyr_Campaign scaffold starts empty — no NPCs, no locations, no factions yet. Build the (empty) graph so the `vault-graph` MCP server has an index to load:

```bash
uv run scripts/build_vault_graph.py examples/ttrpg/GM-Vault
```

You should see `Graph built: 0 notes, 0 edges → examples/ttrpg/GM-Vault/.graph.json`. We'll populate the vault during Demos C and D — the graph rebuilds itself then.

### 8. Wire up the MCP servers and install the GM skills

#### a. Install the four bundled skills

Claude only auto-loads skills from a real `.claude/skills/` directory, so copy them into one:

```bash
# Project-local (recommended) — loads only when claude runs from examples/ttrpg/ or below
mkdir -p examples/ttrpg/.claude/skills
cp -r examples/ttrpg/skills/* examples/ttrpg/.claude/skills/
```

(Alternative: copy into `~/.claude/skills/` instead — loads every time you start claude anywhere.)

#### b. Configure the MCP servers to point at the bundled vault

Edit `.mcp.json` so all three servers point at the right paths (replace your repo path if it differs):

```json
{
  "mcpServers": {
    "r2r": {
      "command": "python3",
      "args": ["/workspaces/R2R-ClaudeCode-integration/r2r_mcp_wrapper.py"],
      "env": {"R2R_API_BASE": "http://localhost:7272"}
    },
    "sourcebooks": {
      "command": "python3",
      "args": ["/workspaces/R2R-ClaudeCode-integration/mcp-servers/sourcebooks/server.py"],
      "env": {"R2R_API_BASE": "http://localhost:7272"}
    },
    "vault-graph": {
      "command": "python3",
      "args": ["/workspaces/R2R-ClaudeCode-integration/mcp-servers/vault-graph/server.py"],
      "env": {"VAULT_PATH": "/workspaces/R2R-ClaudeCode-integration/examples/ttrpg/GM-Vault"}
    }
  }
}
```

#### c. Launch Claude from inside the scaffold

```bash
cd examples/ttrpg
claude
```

The vault's `CLAUDE.md` (at `examples/ttrpg/GM-Vault/CLAUDE.md`) tells Claude the campaign layout, frontmatter schemas, and which skills are available. Run `/mcp` inside Claude to confirm all three servers are connected with 14 tools total (r2r: 5, sourcebooks: 3, vault-graph: 6).

### 9. The demo — A through F

Run these prompts in order. Each one demonstrates a different capability.

#### Demo A — Multi-book sourcebook search with citations

Prompt:

> List the books we've ingested. Then tell me what the sourcebooks say about the Emberdeeps.

**Expected**: Claude calls `sourcebooks.list_books()` and returns three entries (Vol I, Vol II, Vol III). Then `sourcebooks.search_lore(query="Emberdeeps")` returns chunks predominantly from Vol I, with `book_title` and `page_range` citations. The Emberdeeps are the magma-vein region beneath the Drakhammer Mountains; you'll see references to Grunvyr "holding" them.

**Proves**: R2R semantic search works across the ingested corpus and the `sourcebooks` MCP wraps it cleanly with citation metadata.

#### Demo B — OCR proof point

Prompt:

> Summarize what's in Volume III.

**Expected**: Coherent text content comes back — chapter titles, topic descriptions, named entities. Volume III is the image-only PDF; the fact that any meaningful text returns at all means Unstructured.io OCR'd the scanned pages during ingest and R2R chunked and embedded them.

**Proves**: Server-side OCR (Unstructured.io as part of Docker Full Mode) is wired correctly. No client-side OCR setup needed.

#### Demo C — Worldbuilding skill drafts a new NPC

Prompt:

> Create a new master-smith NPC for Grunvyr_Campaign who works under the current Stonecrown. Use the sourcebooks for context on the Reckoners' College and the Hold.

**Expected**: The `worldbuilding` skill triggers. You'll see Claude:
1. Run `vault_search_notes(note_type="NPC")` against your empty vault (no hits).
2. Call `search_lore(query="Stonecrown")` and `search_lore(query="Reckoners College Hold")` against the sourcebooks.
3. Draft a new NPC with full frontmatter matching `examples/ttrpg/GM-Vault/templates/NPC Template.md` — `type: NPC`, `world: Grunvyr`, `campaign: Grunvyr_Campaign`, `faction`, `level`, `race`, etc.
4. Ask before writing, then save to `examples/ttrpg/GM-Vault/Grunvyr_Campaign/NPC/<NPC Name>.md`.
5. Call `vault_rebuild_graph()` so the new NPC is in the index.

**Proves**: The worldbuilding skill synthesizes vault context + sourcebook research and writes structured notes correctly. Canon hierarchy (vault > sourcebooks) is respected — when the vault is empty, sourcebooks fill the gap; when the vault has canon, the vault wins.

#### Demo D — Session-creation skill drafts Session 1

Prompt:

> Prepare Session 1 for Grunvyr_Campaign. The Stonecrown succession crisis is breaking and the PCs have been summoned to the Hold. Use the 8 Steps of the Lazy DM.

**Expected**: The `session-creation` skill triggers. You'll see:
1. Vault graph queries (mostly empty) to find related notes.
2. Sourcebook research on the succession crisis, the Stonecrown, the Hold.
3. Brainstorming through the 8 Steps (Review Characters, Strong Start, Scenes, Secrets & Clues, Fantastic Locations, Important NPCs, Monsters, Loot).
4. The Situations Checklist applied per scene (Location + Inhabitants + Goal minimum). 5RD offered as an option.
5. Files written to `examples/ttrpg/GM-Vault/Grunvyr_Campaign/Sessions/Session 1/` — a main `YYYY-MM-DD Session 1.md` and per-scene Encounter notes. The smith from Demo C should appear as a referenced NPC if relevant.

**Proves**: The session-creation skill orchestrates vault + sourcebook + brainstorming into a structured Lazy-DM session prep. It composes with `worldbuilding` (calls it for new NPC/location creation as needed).

#### Demo E — Vault-scout's Haiku-dispatched mechanical sweep

Prompt:

> Find every NPC note in the vault and tabulate name, faction, and level.

**Expected**: The `vault-scout` skill dispatches a Haiku subagent with a narrow prompt. Haiku scans `examples/ttrpg/GM-Vault/Grunvyr_Campaign/NPC/`, extracts frontmatter from each `.md` file, and returns a table — probably one row (the smith from Demo C). The main-agent context stays clean; you don't see Haiku's intermediate file reads.

**Proves**: The vault-scout primitive works as designed — main agent stays Opus-priced for judgment work, mechanical sweeps go to Haiku.

#### Demo F — Chronik skill updates the Campaign Chronicle

First, give the chronik skill something to chronicle. Drop this fake Session 1 player log into `examples/ttrpg/GM-Vault/Grunvyr_Campaign/PC/PlayerNotes/Session-1.md`:

```markdown
# Session 1 — Player Notes

We arrived at the Hold three days late, weather slowed us. A Warden met us at the Sealing Door and walked us in. Met the master-smith — he asked about our route. We told him we came up the river road past Vendholm. We did NOT mention the dwarven envoy we passed on the way; we agreed in advance that's the Stonecrown's business and not ours to share.

The smith offered to forge a replacement for [[PC Two]]'s broken axe in exchange for word on what we saw at the river ford. We took the deal. He let slip that the Reckoners' College has been silent on the succession for two months — longer than the usual deliberation — and that the youngest claimant has gone missing from the Hold entirely. We had not known that before.

He asked us, as we left, whether we knew anyone who had seen anything strange in the Nethergloam. We said no. (We saw the gloamkin tracks at the third cairn on the way in but agreed to keep that out of the conversation.)
```

Then prompt:

> Update the Campaign Chronicle from Session 1 PlayerNotes.

**Expected**: The `chronik` skill triggers and:
1. Reads the PlayerNotes file you just dropped in.
2. Builds an information-exchange matrix per scene: what each side **shared**, what was **withheld**, what each side **learned**.
3. Writes `examples/ttrpg/GM-Vault/Grunvyr_Campaign/PC/Campaign_Chronicle.md` with the entry in chronicle format — bold section markers (`**What [PC] shared:**`, `**What [NPC] learned:**`, `**What [PC] did NOT share:**`) preserve every exchange.

**Proves**: The chronik skill's discipline — preserving who-told-whom-what across an arbitrary number of NPC interactions — produces a record that survives the cardinal rule ("for every NPC interaction, can you answer what each party knows now that they didn't before?").

## What you just saw

| Demo | Capability proven |
|---|---|
| A | Multi-book semantic search across the ingested corpus with citation metadata, via the `sourcebooks` MCP. |
| B | Server-side OCR through Unstructured.io for image-only PDFs — no client-side OCR setup needed in Docker Full Mode. |
| C | The `worldbuilding` skill synthesizes vault canon + sourcebook research into a new note with correct frontmatter, asks before writing, refreshes the graph. |
| D | The `session-creation` skill orchestrates the 8 Steps of the Lazy DM + Situations Checklist into a fully structured session folder. |
| E | The `vault-scout` skill dispatches mechanical sweeps to Haiku, keeping main-agent context clean and token costs low. |
| F | The `chronik` skill preserves precise information-exchange details across every NPC interaction — the campaign record stays auditable. |

To replace the Grunvyr_Campaign demo content with your own vault and sourcebooks, see [`quickstart.md`](./quickstart.md).

## When something doesn't work

- **Port 7272 already in use when bringing up R2R** — if `docker compose up -d` fails with "port is already allocated" / "bind: address already in use", a VS Code Server process inside the devcontainer is holding the port. This happens when an older `devcontainer.json` used `forwardPorts: [7272, 7273]` (eager binding) instead of `portsAttributes` (lazy, on-listen). Fix: rebuild the devcontainer (`Dev Containers: Rebuild Container`) to pick up the current `devcontainer.json`. Quick workaround without rebuilding: open VS Code's Ports panel (View → Ports), right-click 7272 → "Stop Forwarding Port", repeat for 7273 if needed, then retry the `docker compose` command.
- **`docker compose … ps` says "depends on undefined service postgres: invalid compose project"** — the `postgres` service is scoped to the `postgres` profile in `compose.full.yaml`. Either run `export COMPOSE_PROFILES=postgres` once in your shell (recommended), or pass `--profile postgres` on every compose invocation (`ps`, `logs`, `down`, etc.).
- **`wait-for-hatchet-grpc` exits with `TIMEOUT: hatchet gRPC not reachable after 300s`** — hatchet-engine never bound port 7077 in time. The most common cause is a stale `docker/env/hatchet.env` from before the `SERVER_GRPC_PORT=7077` fix landed — re-copy `hatchet.env.example` over your `hatchet.env` and `docker compose -f docker/compose.full.yaml down -v` to reset volumes, then `up -d` again. If it still times out, check `docker compose logs hatchet-engine` for the engine's own crash output.
- **`curl http://localhost:7272/v3/health` returns `curl: (56) Recv failure: Connection reset by peer`** — r2r isn't actually ready. Run `docker compose -f docker/compose.full.yaml ps`: if r2r is `restarting`, `health: starting`, or has a much lower uptime than the rest of the stack, run `docker compose -f docker/compose.full.yaml logs r2r --tail 100` and look at the last error. Common remaining causes are Postgres auth misconfig (check `docker/env/r2r-full.env`), Ollama unreachable from inside the container (check `host.docker.internal:11434` is responding on the host), or an OCR-pipeline import failure.
- **Vol III ingestion stuck for 5+ minutes** — Unstructured.io is OCRing 16 image pages and the GPU isn't available, so it's CPU-bound. This is normal. Check `docker compose logs unstructured --tail 30` to confirm progress. The other two books should already show `ingestion: success` in `verify_ingestion.py`.
- **Devcontainer build fails on pip install** — usually a network issue. Verify outbound HTTPS to pypi.org works from the host; try rebuilding (`Dev Containers: Rebuild Container`).
- **R2R container can't reach Ollama** — verify the host can reach itself at `host.docker.internal:11434` from inside Docker. On Linux, the `--add-host=host.docker.internal:host-gateway` runArg in `devcontainer.json` handles this; on macOS, Docker Desktop maps it automatically.
- **`/mcp` shows 0 servers** — check that the paths in your `.mcp.json` resolve inside the container. The workspace is mounted at `/workspaces/R2R-ClaudeCode-integration/` (not `/workspace/`).

For a fuller list of known failure modes and workarounds, see [`troubleshooting.md`](./troubleshooting.md).

## Out of scope for v0.1

- **Non-TTRPG domain adaptation** — the `sourcebooks` server's metadata schema (book/chapter/page) and the worldbuilding skill template assume TTRPG vocabulary. Adapting to other domains (legal, engineering, academic, etc.) is on the v0.2 roadmap.
- **Multi-instance deployment** — the single-stack `compose.full.yaml` is the supported v0.1 path. The shared-infra + per-vault-instance variant (`compose.infra.yaml` + `compose.app.yaml`) ships but is not formally validated at v0.1.
- **Windows hosts** — see the prerequisites table.
