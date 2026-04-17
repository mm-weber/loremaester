# `docker/user_configs/`

This directory holds R2R's TOML configuration. It's bind-mounted into the
R2R container at `/app/user_configs/`, and `R2R_CONFIG_PATH` in
`../env/r2r-full.env` points at a file here.

## What's in here

| File | Purpose |
|---|---|
| `r2r-ollama-embeddings.toml` | Embeddings-only R2R config used by `compose.full.yaml` — Ollama for embeddings, Unstructured.io for PDF parsing, Hatchet for orchestration, no completion/LLM provider (Claude Code does all reasoning). |

This is the config the quickstart ships. You don't need to edit it for
normal use.

## Using a different config

1. Drop your `.toml` in this directory.
2. Update `R2R_CONFIG_PATH` in `../env/r2r-full.env` to
   `/app/user_configs/<your-file>.toml`.
3. Restart the R2R service:
   ```bash
   docker compose -f docker/compose.full.yaml --profile postgres up -d r2r
   ```

Note: `R2R_CONFIG_NAME` and `R2R_CONFIG_PATH` are mutually exclusive — if
you switch to one of R2R's built-in config presets, clear
`R2R_CONFIG_PATH` in the env file and set `R2R_CONFIG_NAME` instead.

## Troubleshooting

If R2R fails to start with a config error:
- Confirm the filename in `R2R_CONFIG_PATH` matches what's in this dir
  (path is container-side: `/app/user_configs/<file>.toml`).
- `docker compose -f docker/compose.full.yaml logs r2r` will show the
  parsing error with a line number if the TOML is malformed.

See [../../docs/quickstart.md](../../docs/quickstart.md) Step 2 for the
broader R2R setup flow.
