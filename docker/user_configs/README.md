# `docker/user_configs/`

This directory holds R2R's TOML configuration. It's bind-mounted into the
R2R container at `/app/user_configs/`, and `R2R_CONFIG_PATH` in the active env
file points at a file here — `../env/r2r.env` for **Light Mode** (`compose.yaml`),
`../env/r2r-full.env` for **Full Mode** (`compose.full.yaml`).

## What's in here

| File | Purpose |
|---|---|
| `r2r-light.toml` | **Default (Light Mode, `compose.yaml`).** Ollama embeddings, R2R's built-in parser (no Unstructured), in-process orchestration (no Hatchet). No completion/LLM provider — Claude Code does all reasoning. |
| `r2r-ollama-embeddings.toml` | Full Mode (`compose.full.yaml`). Ollama embeddings, Unstructured.io for PDF parsing, Hatchet for orchestration. No completion/LLM provider. |

These are the configs the quickstart ships. You don't need to edit them for
normal use.

## Using a different config

1. Drop your `.toml` in this directory.
2. Update `R2R_CONFIG_PATH` in the active env file (`../env/r2r.env` for Light
   Mode, `../env/r2r-full.env` for Full Mode) to `/app/user_configs/<your-file>.toml`.
3. Restart the R2R service:
   ```bash
   # Light Mode
   docker compose -f docker/compose.yaml --profile postgres --profile minio up -d r2r
   # Full Mode
   docker compose -f docker/compose.full.yaml --profile postgres up -d r2r
   ```

Note: `R2R_CONFIG_NAME` and `R2R_CONFIG_PATH` are mutually exclusive — if
you switch to one of R2R's built-in config presets, clear
`R2R_CONFIG_PATH` in the env file and set `R2R_CONFIG_NAME` instead.

## Troubleshooting

If R2R fails to start with a config error:
- Confirm the filename in `R2R_CONFIG_PATH` matches what's in this dir
  (path is container-side: `/app/user_configs/<file>.toml`).
- `docker compose -f docker/compose.yaml logs r2r` (Light) or
  `-f docker/compose.full.yaml logs r2r` (Full) shows the parsing error with a
  line number if the TOML is malformed.

See [../../docs/quickstart.md](../../docs/quickstart.md) Step 2 for the
broader R2R setup flow.
