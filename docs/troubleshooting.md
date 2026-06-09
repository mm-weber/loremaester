# Troubleshooting

## Devcontainer Issues

### Devcontainer fails to start: `bind source path does not exist: /run/host-services/ssh-auth.sock` (macOS)

**Cause:** The macOS / Docker Desktop default `SSH_AUTH_SOCK` is a launchd socket that Docker Desktop's VM cannot bind-mount, so the devcontainer's SSH-agent forwarding mount fails. The fix is a one-time shell-init export that points the env var at the stable in-VM path Docker Desktop manufactures.

**Fix:** add the export to `~/.zshrc` (or your shell init) and launch VS Code from a terminal rather than the Dock / Spotlight, so the export is actually inherited:

```bash
# Add to ~/.zshrc on macOS
export SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
# Then, in a fresh terminal:
source ~/.zshrc && code .
```

See [the macOS preflight in quickstart.md](./quickstart.md#macos--docker-desktop-one-time-preflight) for the longer explanation.

### Devcontainer fails to start: empty or invalid mount source for SSH agent (Linux)

**Cause:** `${localEnv:SSH_AUTH_SOCK}` resolved to empty because no `ssh-agent` was running in the shell that launched the editor, so the devcontainer's SSH-agent mount has no source path.

**Fix (recommended):** start an ssh-agent before launching VS Code:

```bash
eval "$(ssh-agent)"
ssh-add ~/.ssh/id_ed25519   # or whichever key
code .                      # launch from this same shell
```

**Fix (no SSH at all):** if the host genuinely has no ssh-agent (Windows without one, fully headless boxes), delete the `"source=${localEnv:SSH_AUTH_SOCK},target=/ssh-agent,..."` line from `.devcontainer/devcontainer.json`'s `mounts` array AND the matching `"SSH_AUTH_SOCK": "/ssh-agent"` line from `containerEnv`. Use HTTPS plus a personal access token for git instead.

---

## Connection Issues

### "Connection refused" on `search_lore`

**Causes (three common):**

1. R2R is not running.
2. The MCP server is configured with the wrong URL (e.g., `localhost` instead of `host.docker.internal`).
3. **Linux only:** the R2R stack was started without `docker/compose.linux.yaml` layered in, so R2R is bound only on host loopback (`127.0.0.1`). The devcontainer reaches the host via the docker0 bridge gateway (typically `172.17.0.1`), which the loopback binding does not cover, so the connection from inside the devcontainer is refused.

**Fix:**

- Verify R2R is healthy on the host with `curl http://localhost:7272/v3/health`.
- Confirm `R2R_API_BASE` in your MCP settings uses `host.docker.internal`, not `localhost`. The devcontainer cannot reach the host's loopback interface directly.
- On Linux, restart the stack with the override layered in:
  ```bash
  docker compose -f docker/compose.yaml -f docker/compose.linux.yaml \
    --profile postgres --profile minio up -d
  ```
  Then, from inside the devcontainer, `curl http://host.docker.internal:7272/v3/health` should succeed. If it does not, you have hit cause #3. See [`quickstart.md`](./quickstart.md) Step 2 for the full explanation of the override pattern.

### `host.docker.internal` doesn't resolve

**Cause:** Linux hosts do not add the `host.docker.internal` DNS entry by default (macOS and Windows Docker Desktop do).

**Fix:** Add `"--add-host=host.docker.internal:host-gateway"` to the `runArgs` array in your `devcontainer.json`.

### Ollama connection refused from R2R

**Cause:** The R2R container cannot reach the Ollama process running on the host.

**Fix:** Verify `OLLAMA_API_BASE=http://host.docker.internal:11434` is set in `r2r-full.env`. Verify `ollama serve` is actually running on the host.

---

## MCP Server Issues

### MCP server shows as disconnected

**Cause:** The server path in `settings.json` is wrong, or required Python packages are missing.

**Fix:** Ensure all paths in `settings.json` are absolute. Verify the devcontainer has the required packages by running `python -c "import mcp, r2r"`.

### `ImportError: No module named 'r2r'`

**Cause:** The R2R SDK is not installed inside the devcontainer.

**Fix:** Install it with `uv pip install r2r` (or `pip install r2r --break-system-packages` if uv is unavailable).

---

## Ingestion Issues

### Search returns no results for an ingested book

**Cause:** The PDF is an image-only (or mixed) scan that was ingested **directly** (e.g. `r2r documents create` or the `r2r` MCP) in Light Mode, which has no server-side OCR — so its scanned pages produced no text.

**Fix:** Ingest it with `scripts/ingest_books.py` instead, which OCRs scanned pages client-side in *any* mode (it auto-routes image-only and mixed PDFs to the per-page hybrid). Or use Docker Full Mode, where Unstructured.io OCRs server-side. (If you already ingested an empty copy, delete it in R2R first — see the idempotency note in [quickstart.md](./quickstart.md).)

### Search returns garbled or nonsensical text

**Cause:** Poor OCR quality on the original scanned pages.

**Fix:** Re-ingest with a different OCR engine (delete the existing document in R2R first — otherwise the re-run is idempotent and the book is **SKIPPED**; see the idempotency note in [quickstart.md](./quickstart.md)). `scripts/ocr_extract.py` (driven via `scripts/ingest_books.py`) defaults to tesseract (CPU); for sharper results on noisy scans opt into EasyOCR (GPU via torch+CUDA — see the bulk-ingestion section of [quickstart.md](./quickstart.md)) by setting `OCR_ENGINE=easyocr`. Quality varies per engine — EasyOCR handles TTRPG scans well; tesseract is solid on clean text but can struggle on multi-column layouts. Set `OCR_LANGUAGE` to match the document (tesseract uses ISO 639-3, e.g. `eng`/`deu`; easyocr uses ISO 639-1, e.g. `en`/`de`).

### Image PDF ingested with no text / "easyocr produced no text"

**Cause:** `scripts/ocr_extract.py` renders each page with pypdfium2 and OCRs it per page. It does *not* silently return empty text — if *every* page comes back blank it raises a clear, document-identifying error naming the offending PDF. When this happens on the easyocr path it is almost always a GPU/torch problem: torch failed to initialize CUDA and the run produced nothing usable. (Before easyocr runs, the script prints a torch/CUDA banner — check it to confirm whether the GPU was actually picked up.)

**Fix:** First, fall back to the default tesseract backend, which is CPU-only and has no GPU dependency:

```bash
OCR_ENGINE=tesseract uv run --no-project --python 3.12 scripts/ingest_books.py <pdf-dir>
```

If you specifically need EasyOCR, fix the GPU/torch setup instead (see the torch/CUDA section below) and re-run with EasyOCR's deps added for the run via `--with`:

```bash
OCR_ENGINE=easyocr uv run --no-project --python 3.12 \
  --with easyocr --with 'torch==2.9.1+cu126' \
  --extra-index-url https://download.pytorch.org/whl/cu126 \
  --index-strategy unsafe-best-match \
  scripts/ingest_books.py <pdf-dir>
```

### Re-running ingest reports books as "skipped" (e.g. "0 succeeded, N skipped")
**Cause:** Not an error — `scripts/ingest_books.py` is idempotent. R2R refuses to re-create a
document that already exists, and the script reports those as **SKIPPED** (the summary counts
`succeeded / skipped / failed` separately). A re-run on an already-populated corpus correctly shows
everything skipped with **0 failed**.

**Fix:** Nothing — this is expected. To genuinely re-ingest (e.g. after changing the OCR engine),
delete the existing document(s) in R2R first (`r2r documents delete <id>`, or via the dashboard),
then re-run.

### `torch` warns `CUDA initialization: driver too old (found version 12080)`

**Cause:** The default PyPI `torch==2.9.1` wheel is built against CUDA 12.8 libs with a minimum-driver check that rejects even fresh CUDA-12.8 drivers (`12080`). After this warning fires, torch silently falls back to CPU and EasyOCR runs without GPU — an hour per book instead of minutes.

**Fix:** Pin the CUDA build on the EasyOCR opt-in run (`--with 'torch==2.9.1+cu126'`); uv only picks up the cu126 variant if you also point at PyTorch's own index:

```bash
OCR_ENGINE=easyocr uv run --no-project --python 3.12 \
  --with easyocr --with 'torch==2.9.1+cu126' \
  --extra-index-url https://download.pytorch.org/whl/cu126 \
  --index-strategy unsafe-best-match \
  scripts/ingest_books.py <pdf-dir>
```

If you already ran once without those flags, uv cached the cu128 build — invalidate it first:

```bash
uv cache clean torch nvidia-cusparselt-cu12 nvidia-nvshmem-cu12 nvidia-cufile-cu12
```

To confirm the GPU is actually engaged after the fix, run `nvidia-smi` in a second terminal during OCR — the spawned `python` process should hold GPU memory and GPU-Util should spike 30–100 %.

### `uv run` fails with `No solution found when resolving script dependencies`

**Cause:** You have a stray `UV_EXTRA_INDEX_URL` exported in your shell. uv's default index strategy refuses to look past the first index that names a given package, so an extra index can shadow PyPI and the PyTorch index and break torch resolution for the EasyOCR opt-in run.

**Fix:** Unset the env var (or use `env -u` for a one-shot):

```bash
unset UV_EXTRA_INDEX_URL
# or, per-command:
env -u UV_EXTRA_INDEX_URL uv run --no-project --python 3.12 ...
```

Check your `~/.zshrc` / `~/.bashrc` if the variable keeps coming back — an older setup step may have written an `export` line that's no longer needed.

### `detect_pdf_type.py` says "mixed"

**Cause:** The PDF contains a mix of text-native pages and image-only (scanned) pages.

**Fix:** No special handling needed — `scripts/ingest_books.py` auto-routes mixed PDFs to the per-page **hybrid** extractor, which keeps each page's text layer where it has one and OCRs only the scanned pages (and embedded figure regions) client-side. Docker Full Mode (server-side Unstructured.io) also handles both types.

### "No books found" from `list_books`

**Cause:** PDFs were ingested without the required `book_title` metadata field.

**Fix:** Re-ingest the documents with `book_title` included in the metadata dict. See the ingestion steps in the quickstart guide.

---

## Vault Graph Issues

### ".graph.json not found"

**Cause:** The vault graph has not been built yet.

**Fix:** Run `uv run --no-project scripts/build_vault_graph.py /workspace/vault` inside the devcontainer.

### "Note 'X' not found"

**Cause:** The graph file is stale — notes were added, renamed, or deleted since the graph was last built.

**Fix:** Call the `vault_rebuild_graph()` MCP tool — it re-parses the vault and reloads the cache in one step. Note: `vault_reload_cache()` only re-reads the existing JSON and will flag staleness in its response; use it after an external rebuild, not as a refresh.

---

## R2R Service Issues

> Commands below assume **Light Mode** (`docker/compose.yaml`, the recommended default). On Full Mode, substitute `-f docker/compose.full.yaml --profile postgres`.

### R2R container keeps restarting

**Cause:** A dependency service (Postgres or MinIO — or, in Full Mode, Hatchet/RabbitMQ) is not healthy or has crashed.

**Fix:** Check service status with `docker compose -f docker/compose.yaml --profile postgres --profile minio ps -a`. Inspect logs for the failing service with `docker compose -f docker/compose.yaml --profile postgres --profile minio logs <service>`.

### `wait-for-hatchet-grpc` times out (Full Mode)

**Cause:** In Full Mode, a short-lived `wait-for-hatchet-grpc` init container gates R2R startup on Hatchet's gRPC port (7077). If it exits with `TIMEOUT: hatchet gRPC not reachable after 300s`, hatchet-engine never bound the port in time — most often a stale `docker/env/hatchet.env` from before the `SERVER_GRPC_PORT=7077` fix landed.

**Fix:** Re-copy the template (`cp docker/env/hatchet.env.example docker/env/hatchet.env`), reset volumes with `docker compose -f docker/compose.full.yaml --profile postgres down -v`, then `up -d` again. If it still times out, check `docker compose -f docker/compose.full.yaml logs hatchet-engine` for the engine's own crash output.

### R2R starts but embeddings fail

**Cause:** The embedding model is not available, or the R2R config points at the wrong provider.

**Fix:** If using Ollama, verify `ollama list` shows `mxbai-embed-large`. Check R2R logs with `docker compose -f docker/compose.yaml logs r2r` for specific error messages.

---

## Multi-Instance Deployment

### Port conflict when starting a second instance

**Cause:** Both instances are trying to bind to the same host ports (e.g., 7272 for R2R API, 5432 for Postgres).

**Fix:** Check the `.env` file for each instance and ensure port assignments do not overlap. Each instance needs its own unique set of host-side ports.

### Instance can't reach Postgres

**Cause:** The shared infrastructure network (`r2r-infra`) is not running, or the instance's compose file is not configured to join it.

**Fix:** Ensure the `r2r-infra` network exists and the shared Postgres/infrastructure services are running. Verify the instance's compose file references the correct external network.

### Data leaking between instances

**Cause:** Multiple instances are using the same `R2R_PROJECT_NAME`, so they read and write to the same database schema.

**Fix:** Verify that `R2R_PROJECT_NAME` is set to a unique value in each instance's `.env` file. Each project name creates an isolated namespace within the shared database.

---

## Resetting the Database

> Commands assume **Light Mode** (`docker/compose.yaml`). On Full Mode, substitute `-f docker/compose.full.yaml --profile postgres`.

### Full Reset (nuclear option)

Stop all services and destroy all volumes:

```bash
docker compose -f docker/compose.yaml --profile postgres --profile minio down -v
```

The `-v` flag removes all named volumes. This deletes:
- All ingested documents, chunks, and vector embeddings (postgres_data)
- MinIO object storage
- (Full Mode only) Hatchet job history and RabbitMQ message queues

After reset, start fresh:

```bash
docker compose -f docker/compose.yaml --profile postgres --profile minio up -d
```

You will need to re-ingest all documents.

### Partial Reset (documents only)

To remove just the ingested documents (in Full Mode, without resetting Hatchet/orchestration):

```bash
# Delete the R2R postgres volume only
docker compose -f docker/compose.yaml --profile postgres --profile minio down
docker volume rm postgres_data
docker compose -f docker/compose.yaml --profile postgres --profile minio up -d
```
