# v0.2 Requirements

> Candidate requirements and improvements for the **next** iteration. Most of this document is a
> design review of the sourcebooks MCP server (the original v0.1-development seed); the **OCR &
> licensing follow-ups** identified during the v0.1 public-release prep are appended at the end.

## Sourcebooks MCP Server — Design Review

## Overview

Deep review of `mcp-servers/sourcebooks/server.py` (126 lines, 3 tools) against the generic `mcp-servers/r2r-wrapper/r2r_mcp_wrapper.py` (244 lines, 5 tools) and `vault-graph/server.py` (214 lines, 5 tools).

---

## Architecture Observations

`★ Insight ─────────────────────────────────────`
The sourcebooks server is a **domain facade** over the generic R2R wrapper. Both call the same `client.retrieval.search()` endpoint. The design question is: does the facade earn its keep, or is it a thin layer that duplicates the wrapper without adding enough value?
`─────────────────────────────────────────────────`

### What sourcebooks adds over the generic wrapper

| Aspect | Generic wrapper (`search`) | Sourcebooks (`search_lore`) |
|--------|---------------------------|----------------------------|
| Search mode | Caller chooses (`search_mode` param) | Hardcoded hybrid search |
| Filters | Caller builds filter dict | Domain params: `book=`, `content_type=` |
| Output format | Generic: title, type, score | Domain-aware: book_title, chapter, page_range |
| Tool surface | 5 tools (CRUD + search) | 3 tools (read-only search) |

**Verdict: The facade is justified.** Claude would need to know the filter syntax (`{"book_title": {"$eq": "..."}}`) and remember to enable hybrid search every time. The sourcebooks server encodes this knowledge once.

---

## Issues Found

### 1. CRITICAL — Client created per call, never reused

```python
def _get_client() -> R2RClient:
    base_url = os.environ.get("R2R_API_BASE", "http://localhost:7272")
    return R2RClient(base_url)
```

Every tool call creates a new `R2RClient`. This pattern appears in **all three servers** (`mcp-servers/r2r-wrapper/r2r_mcp_wrapper.py:12`, `mcp-servers/sourcebooks/server.py:12`, `vault-graph` doesn't use R2R). If `R2RClient` opens a TCP connection or does auth handshake, this adds latency per call.

**Trade-off:** Creating per-call is safe (no stale connections, no thread safety concerns) but wasteful. The MCP server is a single-threaded stdio process — a module-level client would be fine.

**Decision point:** Should `_get_client()` cache the client instance (e.g., module-level singleton), or is per-call simplicity worth the overhead? Consider: does `R2RClient.__init__` do network I/O, or is it just storing the URL?

### 2. IMPORTANT — `list_books` has a hard limit of 100

```python
result = client.documents.list(limit=100)
```

If you ingest >100 documents (chapters), `list_books` silently truncates. There's no pagination and no warning. With TTRPG sourcebooks that have 20-30 chapters each, 4-5 books would hit this ceiling.

**Fix options:**
- Paginate internally (loop until exhausted)
- Expose `limit` as a tool parameter
- At minimum: add a warning when results are truncated

### 3. IMPORTANT — `get_chapter` uses search, not retrieval

```python
result = client.retrieval.search(query=f"{book} {chapter}", search_settings=settings)
```

`get_chapter` is semantically "give me this specific chapter" but it's implemented as a search query with the book+chapter as the query string. This means:
- Results are ranked by relevance, not by page order
- The 50-chunk limit may miss parts of long chapters
- The query `f"{book} {chapter}"` biases results toward chunks that mention the book/chapter names rather than the chapter's actual content

**A more precise approach:** Use `client.documents.list_chunks()` with a filter on `book_title` and `chapter`, returning chunks in their natural order. This would give deterministic, complete chapter content instead of search-ranked fragments.

**Trade-off:** R2R's `list_chunks` API may not support metadata filtering directly. The search-based approach works but is lossy for long chapters.

### 4. MODERATE — No empty-result message in `search_lore`

```python
lines = [f"## Search Results for: {query}\n"]
for i, chunk in enumerate(chunks, 1):
    ...
return "\n".join(lines)
```

If `chunks` is empty, this returns just the header `## Search Results for: query` with no indication that nothing was found. Compare with `get_chapter` which correctly returns `"No content found for..."` and `list_books` which returns `"No books found."`.

### 5. MODERATE — Inconsistent attribute access patterns

The generic wrapper uses defensive `getattr`:
```python
score = getattr(chunk, "score", 0.0)
text = getattr(chunk, "text", str(chunk))
```

The sourcebooks server accesses attributes directly:
```python
score = chunk.score
text = chunk.text
```

Both call the same R2R API. If one needs defensive access, both do. If neither does (because the response schema is guaranteed), the `getattr` in the wrapper is noise.

### 6. MINOR — `search_lore` is async but uses sync `R2RClient`

All three tools are `async def` but call `client.retrieval.search()` synchronously. R2R provides `R2RAsyncClient` for async usage. In an MCP stdio server processing one request at a time, this doesn't matter — but it's a mismatched pattern.

### 7. MINOR — Tool docstrings are minimal

```python
async def search_lore(query: str, book: str = None, content_type: str = None, limit: int = 5) -> str:
    """Search worldbuilding lore across source books."""
```

MCP tools expose their docstrings to Claude as tool descriptions. Richer descriptions help Claude use the tools correctly. Compare: "Search worldbuilding lore across source books" doesn't tell Claude that `book` should match a `book_title` from `list_books`, or that `content_type` accepts values like `lore`, `rules`, `bestiary`.

---

## Comparison with vault-graph server

The vault-graph server is notably more robust:
- **Input validation**: `depth = max(1, min(depth, 4))` — clamps depth
- **Error state handling**: `_check_graph()` returns specific error messages for missing/malformed data
- **Graceful empty states**: "No connections found", "No backlinks found", etc.
- **Reload capability**: `vault_reload_graph` allows live updates

The sourcebooks server lacks equivalent robustness — no input validation, partial empty-state handling, no R2R health check.

---

## Structural Improvements to Consider

### A. Shared client management

All R2R-based servers duplicate `_get_client()`. A shared `r2r_utils.py` could provide a cached client:

```python
# r2r_utils.py
_client = None
def get_client():
    global _client
    if _client is None:
        _client = R2RClient(os.environ.get("R2R_API_BASE", "http://localhost:7272"))
    return _client
```

### B. Shared response formatting

Both `r2r_mcp_wrapper.search()` and `sourcebooks/search_lore()` format chunk results into markdown. The formatting logic is duplicated — different format strings but same pattern (iterate chunks, extract metadata, build lines).

### C. Tool description enrichment

```python
@mcp.tool()
async def search_lore(
    query: str,
    book: str = None,
    content_type: str = None,
    limit: int = 5,
) -> str:
    """Search worldbuilding lore across ingested source books.

    Uses hybrid search (semantic + keyword) optimized for TTRPG content.
    Results include book title, chapter, page range, and relevance score.

    Args:
        query: Natural language search query (e.g., "dwarven death rites")
        book: Filter to a specific book title (must match a title from list_books)
        content_type: Filter by type: "lore", "rules", "bestiary", "adventure", "setting"
        limit: Max results to return (default 5, max 50)
    """
```

---

## Summary

| Severity | Count | Issues |
|----------|-------|--------|
| Critical | 1 | Client created per call (all servers) |
| Important | 2 | list_books 100-doc ceiling; get_chapter uses search not retrieval |
| Moderate | 2 | No empty-result message in search_lore; inconsistent getattr patterns |
| Minor | 2 | async/sync mismatch; minimal tool docstrings |

**Recommended priority:**
1. Fix empty-result message in `search_lore` (trivial)
2. Add limit parameter or pagination to `list_books`
3. Enrich tool docstrings for better Claude tool selection
4. Investigate client caching (profile `R2RClient.__init__` first)
5. Consider `list_chunks` for `get_chapter` (requires R2R API investigation)

---

## OCR & Licensing Follow-ups (added during v0.1 release prep)

### R-1 — Remove the kreuzberg dependency (functional liability + license footprint) — ✅ DONE (v0.1)

> **Status: Implemented during v0.1 release prep** via Conductor track `remove-kreuzberg_20260606`.
> OCR now lives in `scripts/ocr_extract.py` (pypdfium2 render → per-page tesseract/easyocr, TDD-built);
> `ingest_books.py` and `extract_text.py` no longer import kreuzberg; deps, docs, and
> `THIRD_PARTY_LICENSES.md` are updated to the fully-permissive stack. The text below is retained as
> the original rationale/record.

`kreuzberg` powers the client-side OCR path in `scripts/ingest_books.py` and `scripts/extract_text.py`
(image-only PDFs route through `kreuzberg.extract_file_sync`; default backend is **tesseract**, with
**EasyOCR**/PaddleOCR as opt-ins). v0.1 release-prep testing found kreuzberg's OCR layer
**functionally unreliable for the path it exists to serve**, on top of its non-permissive license.
Recommendation upgraded from *"evaluate"* to **remove** (v0.2; possibly v0.1 — see Effort).

**Two independent kreuzberg OCR breakages were observed inside the supported version range** (full
evidence in R-1E):

1. **EasyOCR-on-PDF broken in kreuzberg 4.5–4.8.x.** The EasyOCR backend declared it could process a
   PDF directly (`supports_document_processing() == True`) but relied on an **undeclared**
   `pdf2image`/`pymupdf` dependency, so every image-only PDF failed —
   `ParsingError: All OCR pipeline backends failed`, or silently empty. Fixed only in **4.9.3**.
2. **EasyOCR still broken for multi-page PDFs in kreuzberg 4.9.9 (latest stable).** A *single-page*
   PDF OCRs correctly, but any multi-page document returns **empty text** (verified at 8 and 16
   pages) with **no error raised**. tesseract through the same kreuzberg path is unaffected, and
   **standalone EasyOCR reads the very same rendered pages correctly** — so the fault is in
   kreuzberg's multi-page EasyOCR execution, not EasyOCR, torch, CUDA, the GPU, or the documents.

**License:** kreuzberg (≥ 4.6) is **Elastic License 2.0** — source-available, *not* OSI open-source
(see [`THIRD_PARTY_LICENSES.md`](../../THIRD_PARTY_LICENSES.md)). Removing it returns the OCR stack
to a fully permissive (MIT/Apache) footprint.

**Requirement:** Drop kreuzberg from `scripts/ingest_books.py`, `scripts/extract_text.py`, and
`scripts/test_extract_text.py`. Replace it with a direct OCR pipeline:

- Render image-only PDF pages with a **permissively-licensed** renderer — `pypdfium2` (Apache/BSD,
  pdfium) is ideal; `pdf2image`+poppler (already used by `scripts/ocr_preprocess.py`) also works.
  **Avoid `pymupdf` in the shipped path — it is AGPL-3.0**, which would re-introduce a copyleft
  footprint (the diagnostic probes used it for convenience only).
- OCR **per page** with **tesseract** (default, CPU, permissive) and optionally **EasyOCR** (CUDA),
  concatenating per-page text. Per-page OCR also **sidesteps the kreuzberg multi-page bug by
  construction** (single-page EasyOCR is proven to work).
- `scripts/ocr_preprocess.py` already demonstrates the kreuzberg-free pattern
  (`pdf2image` + `pytesseract`/`surya`); consolidate onto it (see R-2).

**Effort:** Modest. The building blocks already exist and are proven (the R-1E probes render with a
PDF library and call EasyOCR/tesseract directly, successfully). What kreuzberg contributed —
multi-format ingestion and a unified multi-engine config — is **not needed** for the PDF-only
sourcebook corpus. The work is a small `render → per-page OCR → join` helper plus updating two
scripts and one test. Cheap enough that a direct EasyOCR+CUDA path could land in **v0.1** if desired.

#### R-1E — Evidence: kreuzberg EasyOCR investigation (v0.1 release prep, 2026-06)
Environment: kreuzberg **4.9.9**, torch **2.9.1+cu126**, easyocr **1.7.2**, Python 3.12, NVIDIA
GTX 1060 (compute capability 6.1 / `sm_61`, 6 GB), Linux. Subject:
`examples/ttrpg/sourcebooks/Grunvyr-Vol-III-ImageOnly.pdf` — 16 pages, each a single full-page RGB
raster (~200 dpi, FlateDecode; **no exotic codec**), 15 normal dark-on-light pages + 1 dark/inverted
cover.

Layers eliminated, in order:

| Layer | Test | Result |
|---|---|---|
| torch / CUDA | fp32 matmul; `get_arch_list()` vs device cc | ✅ fine — `sm_60` covers `sm_61` (CUDA minor forward-compat) |
| EasyOCR engine | `readtext` on synthetic **and** real rendered pages, GPU + CPU | ✅ reads them (cover p0 = 23 boxes, interior p3 = 93 boxes) |
| kreuzberg version | `==4.7.0` vs `>=4.9.3` | 4.7.0 → *"All OCR pipeline backends failed"*; 4.9.3 PDF fix present but… |
| document content | dark/inverted cover | ❌ not the cause — cover-only via kreuzberg = 236 chars; inverting it doesn't help |
| **page count** | single- vs multi-page via kreuzberg+EasyOCR | **single-page works (p0 = 236, p3 = 1302 chars); 8 pp = 0; 16 pp = 0** |
| tesseract | same multi-page doc via kreuzberg | ✅ works (ingests all 16 pages) |

Conclusion: **kreuzberg+EasyOCR returns empty for multi-page PDFs while succeeding on single pages**
— a clean, non-erroring failure isolated to kreuzberg's multi-page OCR path. With the earlier 4.5–4.8
regression and the Elastic-2.0 license, kreuzberg is a net liability for this project's OCR needs.

Minimal upstream repro (kreuzberg 4.9.9): `extract_file_sync(<1-page image PDF>,
ExtractionConfig(ocr=OcrConfig(backend="easyocr")))` returns text; the identical call on an 8- or
16-page image PDF returns empty. File against `kreuzberg-dev/kreuzberg`.

### R-2 — Consolidate the three overlapping OCR code paths
There are three OCR entry points with overlapping responsibility: `ingest_books.py` (kreuzberg,
tesseract default, bulk-ingest), `extract_text.py` (kreuzberg, tesseract default, standalone), and
`ocr_preprocess.py` (pytesseract/surya, no kreuzberg). v0.2 should consolidate these behind a
single OCR module with a pluggable backend — the kreuzberg-free direct-OCR helper from **R-1** is
the natural consolidation target.

### R-3 — End-to-end collection support (optional)
The generic `r2r` MCP wrapper supports `collection_ids`, but the `sourcebooks` MCP server and the
`ingest_books.py` / `verify_ingestion.py` CLIs do not scope by collection. If per-corpus isolation
is desired, add a `--collection` option to the ingest/verify scripts **and** collection filtering
to the sourcebooks server so retrieval honors it. (v0.1 docs intentionally omit `--collection`
because it is not wired end-to-end.)
