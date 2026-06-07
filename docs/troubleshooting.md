# Troubleshooting

## Connection Issues

### "Connection refused" on `search_lore`

**Cause:** R2R is not running, or the MCP server is configured with the wrong URL (e.g., `localhost` instead of `host.docker.internal`).

**Fix:** Verify R2R is healthy on the host with `curl http://localhost:7272/v3/health`. Then confirm that `R2R_API_BASE` in your MCP settings uses `host.docker.internal`, not `localhost` — the devcontainer cannot reach the host's loopback interface.

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

**Cause:** The PDF is an image-only scan and was ingested in Light Mode, which cannot extract text from images.

**Fix:** Use Docker Full Mode (Unstructured.io handles OCR automatically) or preprocess the PDF on the host with `scripts/ocr_preprocess.py` before ingesting.

### Search returns garbled or nonsensical text

**Cause:** Poor OCR quality on the original scanned pages.

**Fix:** Re-ingest with a different OCR engine. `scripts/ocr_extract.py` (driven via `scripts/ingest_books.py`) defaults to tesseract (CPU); for sharper results on noisy scans opt into EasyOCR (GPU via torch+CUDA — see the bulk-ingestion section of [quickstart.md](./quickstart.md)) by setting `OCR_ENGINE=easyocr`. Quality varies per engine — EasyOCR handles TTRPG scans well; tesseract is solid on clean text but can struggle on multi-column layouts. Set `OCR_LANGUAGE` to match the document (tesseract uses ISO 639-3, e.g. `eng`/`deu`; easyocr uses ISO 639-1, e.g. `en`/`de`).

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

**Cause:** The PDF contains a mix of text-native pages and image-only pages.

**Fix:** Ingest in Docker Full Mode (Unstructured handles both types). Alternatively, preprocess just the image pages with `scripts/ocr_preprocess.py`.

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

### R2R container keeps restarting

**Cause:** A dependency service (Postgres, Hatchet, RabbitMQ) is not healthy or has crashed.

**Fix:** Check service status with `docker compose -f docker/compose.full.yaml --profile postgres ps -a`. Inspect logs for the failing service with `docker compose -f docker/compose.full.yaml --profile postgres logs <service>`.

### R2R starts but embeddings fail

**Cause:** The embedding model is not available, or the R2R config points at the wrong provider.

**Fix:** If using Ollama, verify `ollama list` shows `mxbai-embed-large`. Check R2R logs with `docker compose -f docker/compose.full.yaml logs r2r` for specific error messages.

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

### Full Reset (nuclear option)

Stop all services and destroy all volumes:

```bash
docker compose -f docker/compose.full.yaml --profile postgres down -v
```

The `-v` flag removes all named volumes. This deletes:
- All ingested documents, chunks, and vector embeddings (postgres_data)
- Hatchet job history and configuration
- RabbitMQ message queues
- MinIO object storage

After reset, start fresh:

```bash
docker compose -f docker/compose.full.yaml --profile postgres up -d
```

You will need to re-ingest all documents.

### Partial Reset (documents only)

To remove just the ingested documents without resetting Hatchet/orchestration:

```bash
# Delete the R2R postgres volume only
docker compose -f docker/compose.full.yaml --profile postgres down
docker volume rm postgres_data
docker compose -f docker/compose.full.yaml --profile postgres up -d
```
