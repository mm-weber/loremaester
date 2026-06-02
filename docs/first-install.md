# First-install guide

The fastest path from "clone the repo" to "first search query answered by Claude with sourcebook citations." Targets a fresh machine, devcontainer-only install. For deeper detail on individual components, see [`quickstart.md`](./quickstart.md) and [`design.md`](./design.md); for known failure modes, see [`troubleshooting.md`](./troubleshooting.md).

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
```bash
docker compose -f docker/compose.full.yaml --profile postgres up -d
docker compose -f docker/compose.full.yaml ps
```
Expect 3-5 minutes on first start (Hatchet runs database migrations). Health check:
```bash
curl http://localhost:7272/v3/health
```
Should return `{"status":"ok"}` or equivalent.

The R2R dashboard is on http://localhost:7273 (forwarded to your host via the `forwardPorts` setting).

### 6. Ingest a small PDF corpus
Put 3-5 PDFs at `/workspaces/R2R-ClaudeCode-integration/test-pdfs/` (or any path inside the workspace mount). Mix at least one text-native and one scanned/image PDF to exercise both ingestion paths.
```bash
uv run scripts/detect_pdf_type.py test-pdfs/
uv run scripts/ingest_books.py test-pdfs/ --collection my-test
uv run scripts/verify_ingestion.py --collection my-test
```
The image PDFs route through Kreuzberg + EasyOCR/PaddleOCR; the verify script reports document and chunk counts.

### 7. Build the vault graph
Copy a small Obsidian-style vault (markdown notes with `[[wikilinks]]`) to `/workspaces/R2R-ClaudeCode-integration/test-vault/`. A copy is fine — the system reads but does not modify the vault.
```bash
uv run scripts/build_vault_graph.py test-vault
```
This writes `test-vault/.graph.json` — a pre-computed wikilink graph that the `vault-graph` MCP server loads at startup.

### 8. Wire up MCP and launch Claude
Configure the MCP servers. The repo ships a `.mcp.json` example; copy or edit so the three servers point at your paths:
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
      "env": {"VAULT_PATH": "/workspaces/R2R-ClaudeCode-integration/test-vault"}
    }
  }
}
```
Launch Claude Code in the devcontainer terminal:
```bash
claude
```
Inside Claude, run `/mcp`. You should see **three servers connected** (`r2r`, `sourcebooks`, `vault-graph`) with **14 tools total** (5 + 3 + 6).

### 9. First query
Prompt Claude with something like:
> "Search our sourcebooks for content about [some topic you ingested]."

Claude will call `sourcebooks.search_lore`, return ranked chunks with `book_title`, `chapter`, and `page_range` citations, and synthesize an answer.

Try also:
- "List the books we've ingested." → `sourcebooks.list_books`
- "Show me the most-connected notes in the vault." → `vault-graph.vault_central_notes`
- "Which vault notes link to [some central note]?" → `vault-graph.vault_backlinks`

If all three respond with cited results, the install is verified.

## When something doesn't work

- **Port 7272 already in use when bringing up R2R** — if `docker compose up -d` fails with "port is already allocated" / "bind: address already in use", a VS Code Server process inside the devcontainer is holding the port. This happens when an older `devcontainer.json` used `forwardPorts: [7272, 7273]` (eager binding) instead of `portsAttributes` (lazy, on-listen). Fix: rebuild the devcontainer (`Dev Containers: Rebuild Container`) to pick up the current `devcontainer.json`. Quick workaround without rebuilding: open VS Code's Ports panel (View → Ports), right-click 7272 → "Stop Forwarding Port", repeat for 7273 if needed, then retry the `docker compose` command.
- **Devcontainer build fails on pip install** — usually a network issue. Verify outbound HTTPS to pypi.org works from the host; try rebuilding (`Dev Containers: Rebuild Container`).
- **R2R container can't reach Ollama** — verify the host can reach itself at `host.docker.internal:11434` from inside Docker. On Linux, the `--add-host=host.docker.internal:host-gateway` runArg in `devcontainer.json` handles this; on macOS, Docker Desktop maps it automatically.
- **`/mcp` shows 0 servers** — check that the paths in your `.mcp.json` resolve inside the container. The workspace is mounted at `/workspaces/R2R-ClaudeCode-integration/` (not `/workspace/`).
- **Ingestion times out on image PDFs** — large scans can take several minutes. Increase the upload cap (`R2R` server config) and check the ingest log via `docker compose -f docker/compose.full.yaml logs r2r --tail 100`.

For a fuller list of known failure modes and workarounds, see [`troubleshooting.md`](./troubleshooting.md).

## Out of scope for v0.1

- **Non-TTRPG domain adaptation** — the `sourcebooks` server's metadata schema (book/chapter/page) and the `worldbuilding` skill template assume TTRPG vocabulary. Adapting to other domains (legal, engineering, academic, etc.) is on the v0.2 roadmap.
- **Worldbuilding orchestration skill** — the four-step workflow (gather context → research books → generate with canon priority → write back + rebuild graph) is encoded in `plugins/worldbuilding/SKILL.md`. v0.1 validates the underlying infrastructure; the skill itself is documented but not part of the first-install acceptance criteria.
- **Multi-instance deployment** — the single-stack `compose.full.yaml` is the supported v0.1 path. The shared-infra + per-vault-instance variant (`compose.infra.yaml` + `compose.app.yaml`) ships but is not formally validated at v0.1.
- **Windows hosts** — see the prerequisites table.
