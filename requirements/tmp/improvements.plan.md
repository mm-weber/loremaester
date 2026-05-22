# Sourcebooks MCP Server — Design Review

## Overview

Deep review of `mcp-servers/sourcebooks/server.py` (126 lines, 3 tools) against the generic `r2r_mcp_wrapper.py` (244 lines, 5 tools) and `vault-graph/server.py` (214 lines, 5 tools).

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

Every tool call creates a new `R2RClient`. This pattern appears in **all three servers** (`r2r_mcp_wrapper.py:12`, `sourcebooks/server.py:12`, `vault-graph` doesn't use R2R). If `R2RClient` opens a TCP connection or does auth handshake, this adds latency per call.

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
