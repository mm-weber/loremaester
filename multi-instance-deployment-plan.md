# Multi-Instance R2R Deployment Plan

## Context

Running `compose.full.yaml` for the TTRPG Obsidian vault works, but we want to run additional R2R integrations (other vaults, projects) on the same server without duplicating the entire 12-service stack per purpose.

## Recommended Approach: Split Infrastructure from Application

Split the current monolithic compose into two layers:

1. **Infrastructure layer** (one compose project, runs once): postgres, hatchet-*, minio
2. **Application layer** (one compose project per purpose): r2r, unstructured, graph_clustering, r2r-dashboard

This works because:
- **R2R_PROJECT_NAME** creates a separate Postgres schema per instance — multiple R2R processes safely share one postgres
- **Hatchet** workers register with unique names — multiple R2R instances share one hatchet engine
- **unstructured** and **graph_clustering** are stateless — can be shared or isolated per preference
- **MCP wrapper** already reads `R2R_API_BASE` from env — just point each wrapper at the right port

### Resource savings vs fully duplicated stacks

| | 2x full stacks | Shared infra + 2 apps |
|---|---|---|
| postgres instances | 2 | 1 |
| hatchet services | 14 (7x2) | 7 |
| rabbitmq instances | 2 | 1 |
| Estimated RAM | ~5-7 GB | ~3-4 GB |

---

## Implementation

### Step 1: Create `compose.infra.yaml`

Extract from `compose.full.yaml`. Includes:
- `postgres` (pgvector:pg16) — port 5432
- `hatchet-postgres`, `hatchet-rabbitmq`, `hatchet-create-db`, `hatchet-migration`, `hatchet-setup-config`, `hatchet-engine`, `hatchet-dashboard`, `setup-token`
- `minio` (optional profile)

Add an explicit named network that app stacks join:
```yaml
networks:
  r2r-infra:
    name: r2r-infra
    driver: bridge
```

All services attach to `r2r-infra`. Volumes keep their current names.

**Source file:** `docker/compose.full.yaml` (in the R2R cc-integration worktree)

### Step 2: Create `compose.app.yaml` (parameterized template)

Per-instance services only:
```yaml
services:
  unstructured:
    image: ragtoriches/unst-prod
    networks: [r2r-infra]
    # no host port needed — accessed via docker network

  graph_clustering:
    image: ragtoriches/cluster-prod
    ports: ["${GRAPH_CLUSTERING_PORT:-7276}:7276"]
    networks: [r2r-infra]

  r2r:
    image: sciphiai/r2r:latest
    ports: ["${R2R_PORT:-7272}:${R2R_PORT:-7272}"]
    environment:
      - R2R_PROJECT_NAME=${R2R_PROJECT_NAME}
      - R2R_POSTGRES_HOST=postgres          # shared infra
      - HATCHET_CLIENT_TLS_STRATEGY=none
      - UNSTRUCTURED_SERVICE_URL=http://unstructured:7275
      - CLUSTERING_SERVICE_URL=http://graph_clustering:7276
      # ... (other env vars from r2r-full.env)
    volumes:
      - ./instances/${INSTANCE}/user_configs:/app/user_configs
      - hatchet_api_key:/hatchet_api_key:ro
    networks: [r2r-infra]

  r2r-dashboard:
    image: sciphiai/r2r-dashboard:1.0.3
    ports: ["${DASHBOARD_PORT:-7273}:3000"]
    environment:
      - NEXT_PUBLIC_R2R_DEPLOYMENT_URL=http://localhost:${R2R_PORT:-7272}
    networks: [r2r-infra]

networks:
  r2r-infra:
    external: true

volumes:
  hatchet_api_key:
    external: true
```

**Key:** unstructured/graph_clustering service names are scoped to the compose project, so no collisions. R2R references them by service name within the same project.

### Step 3: Per-instance directories

```
docker/instances/
  ttrpg/
    .env                                    # COMPOSE_PROJECT_NAME=r2r-ttrpg, R2R_PORT=7272, ...
    user_configs/r2r-ollama-embeddings.toml # existing TTRPG config (copy from current)
  coding/
    .env                                    # COMPOSE_PROJECT_NAME=r2r-coding, R2R_PORT=8272, ...
    user_configs/config.toml                # different embedding model, chunking, etc.
```

**Port allocation table:**

| Instance | R2R API | Dashboard | Graph Clustering |
|----------|---------|-----------|------------------|
| ttrpg    | 7272    | 7273      | 7276             |
| coding   | 8272    | 8273      | 8276             |
| (next)   | 9272    | 9273      | 9276             |

### Step 4: MCP wiring

Each R2R instance gets its own MCP server entry — no code changes to `r2r_mcp_wrapper.py`:

```json
"r2r-ttrpg": {
  "command": "python",
  "args": ["r2r_mcp_wrapper.py"],
  "env": { "R2R_API_BASE": "http://host.docker.internal:7272" }
},
"r2r-coding": {
  "command": "python",
  "args": ["r2r_mcp_wrapper.py"],
  "env": { "R2R_API_BASE": "http://host.docker.internal:8272" }
}
```

Enable/disable per project context via `enabledMcpServers` in project-level settings.

### Step 5: Management scripts

```bash
# Start shared infra (once)
docker compose -f docker/compose.infra.yaml -p r2r-infra up -d --profile postgres

# Start/stop individual instances
docker compose -f docker/compose.app.yaml --env-file docker/instances/ttrpg/.env up -d
docker compose -f docker/compose.app.yaml --env-file docker/instances/coding/.env up -d

# Restart just one instance's R2R without affecting anything else
docker compose -f docker/compose.app.yaml --env-file docker/instances/ttrpg/.env restart r2r
```

---

## Files to create/modify

| File | Action |
|------|--------|
| `docker/compose.infra.yaml` | **Create** — infra services extracted from compose.full.yaml |
| `docker/compose.app.yaml` | **Create** — parameterized per-instance template |
| `docker/instances/ttrpg/.env` | **Create** — TTRPG instance config |
| `docker/instances/ttrpg/user_configs/` | **Copy** existing `r2r-ollama-embeddings.toml` |
| `scripts/r2r-infra.sh` | **Create** — infra management helper |
| `scripts/r2r-instance.sh` | **Create** — instance management helper |

No changes to: `r2r_mcp_wrapper.py`, existing compose files (kept as-is for reference).

## Verification

1. `docker compose -f compose.infra.yaml -p r2r-infra up -d --profile postgres` — all infra services healthy
2. `docker compose -f compose.app.yaml --env-file instances/ttrpg/.env up -d` — R2R responds on :7272
3. `docker compose -f compose.app.yaml --env-file instances/coding/.env up -d` — R2R responds on :8272
4. Both MCP wrappers connect and `search`/`ingest_document` work independently
5. Data ingested in one instance is NOT visible in the other (schema isolation via R2R_PROJECT_NAME)

## Risks

| Risk | Mitigation |
|------|------------|
| Hatchet worker name collision | R2R uses project_name in worker registration; verify at deploy |
| Shared postgres SPOF | Acceptable — same as today; add pg_dump cron |
| Port conflict on new instance | Strict port table above; enforced via .env |
