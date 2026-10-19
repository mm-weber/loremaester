# MCP Tools Reference

Loremaester exposes its retrieval backend and vault knowledge to Claude Code through **three MCP servers, 17 tools total**:

| Server | Tools | Role |
|---|---|---|
| [`r2r`](#r2r-server-5-tools) | 5 | Generic create / read / delete / search against the R2R backend. |
| [`sourcebooks`](#sourcebooks-server-3-tools) | 3 | Worldbuilding-aware lore queries with book / chapter / page citations. |
| [`vault-graph`](#vault-graph-server-9-tools) | 9 | Obsidian `[[wikilink]]` graph navigation and refresh, plus Linked Mentions-style excerpts and section reads straight from the vault. |

**How they're wired.** R2R runs on the host; the `r2r` and `sourcebooks` servers reach it over the docker bridge at `host.docker.internal:7272` (`R2R_API_BASE`). `vault-graph` runs entirely in the devcontainer, where the graph tools read a precomputed `.graph.json` index next to your vault and the mentions and read tools scan the vault live. Setup and configuration live in [`quickstart.md`](quickstart.md); this document is the per-tool reference.

This reference has two parts. **Part 1** is practical and use-facing: what each tool does, its parameters, and what it returns. **Part 2** covers internals (transport, env, underlying calls, data models, error model) for contributors. Tools return strings: Markdown-formatted for lists and search results, plain confirmations for writes and status.

---

## Part 1: Practical reference

### r2r server (5 tools)

Generic operations against R2R. Use these when you want direct control over the document store. For worldbuilding lore, prefer the `sourcebooks` tools, which add citations.

#### `search(query, collection_ids=None, filters=None, limit=5, search_mode="custom")`
General-purpose retrieval: find chunks matching `query`.

| Param | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | The search text. |
| `collection_ids` | `list[str]` | `None` | Restrict to these collections (added as an `$overlap` filter). |
| `filters` | `dict` | `None` | Raw R2R filter dict; merged with `collection_ids` when both are given. |
| `limit` | `int` | `5` | Maximum chunks returned. |
| `search_mode` | `str` | `"custom"` | R2R search mode. |

**Returns:** a Markdown list of scored chunks, each with its text and a source line (title, document type), plus a footer noting how many were returned.

**Notes:** default 5 results. On any failure returns an `Error: ...` string rather than raising. Wraps `retrieval.search`.

#### `ingest_document(raw_text=None, chunks=None, metadata=None, collection_ids=None, title=None)`
Add a document to R2R, from either raw text or pre-split chunks.

| Param | Type | Default | Description |
|---|---|---|---|
| `raw_text` | `str` | `None` | Full document text (R2R chunks it). |
| `chunks` | `list[str]` | `None` | Pre-chunked segments (use instead of `raw_text`). |
| `metadata` | `dict` | `None` | Arbitrary metadata; a `title` key here wins over the `title` arg. |
| `collection_ids` | `list[str]` | `None` | Collections to add the document to. |
| `title` | `str` | `None` | Display title (falls back to `Untitled`). |

**Returns:** a confirmation with the new document ID and title.

**Notes:** only non-`None` args are forwarded. Title precedence: `metadata["title"]`, then `title`, then `Untitled`. Wraps `documents.create`.

#### `list_documents(collection_id=None, offset=0, limit=20)`
List documents, optionally scoped to one collection.

| Param | Type | Default | Description |
|---|---|---|---|
| `collection_id` | `str` | `None` | Restrict to this collection. |
| `offset` | `int` | `0` | Pagination offset. |
| `limit` | `int` | `20` | Maximum documents. |

**Returns:** a numbered list (title, type, ingestion status, ID), or `No documents found.`

**Notes:** wraps `documents.list`, or `collections.list_documents` when `collection_id` is set.

#### `delete_document(document_id)`
Delete one document by ID.

| Param | Type | Default | Description |
|---|---|---|---|
| `document_id` | `str` | required | The document UUID. |

**Returns:** a success confirmation, or an `Error: ...` string.

**Notes:** wraps `documents.delete`.

#### `list_collections(offset=0, limit=20)`
List all R2R collections.

| Param | Type | Default | Description |
|---|---|---|---|
| `offset` | `int` | `0` | Pagination offset. |
| `limit` | `int` | `20` | Maximum collections. |

**Returns:** a numbered list (name, document count, created-at, ID), or `No collections found.`

**Notes:** wraps `collections.list`.

### sourcebooks server (3 tools)

The worldbuilding-aware layer over R2R. Every result carries citation metadata (book, chapter, page range). Reach for these for "what do the sourcebooks say about X" rather than the raw `r2r` search.

#### `search_lore(query, book=None, content_type=None, limit=5)`
Hybrid semantic + keyword search across ingested sourcebooks, with citations.

| Param | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Natural-language lore query. |
| `book` | `str` | `None` | Restrict to one book (exact `book_title` match). |
| `content_type` | `str` | `None` | Restrict to a category (e.g. `lore`, `bestiary`). |
| `limit` | `int` | `5` | Maximum chunks. |

**Returns:** ranked results; each is headed with its book title, chapter, page range, and relevance score, followed by the chunk text.

**Notes:** always hybrid (semantic + keyword with reciprocal rank fusion), requesting scores and metadata. `book` and `content_type` compose with AND. Missing metadata renders as `Unknown`. Default 5 results.

#### `list_books()`
Inventory of every ingested book. No parameters.

**Returns:** one line per book (title, publisher, system, content type, chapter count), or `No books found.`

**Notes:** groups documents by `book_title`; "chapters" is the document count per book. Scans up to 100 documents.

#### `get_chapter(book, chapter)`
Reassemble the full text of one chapter.

| Param | Type | Default | Description |
|---|---|---|---|
| `book` | `str` | required | Exact book title. |
| `chapter` | `str` | required | Chapter name or substring (case-insensitive). |

**Returns:** a header with the book and chapter, followed by the chapter's chunks concatenated in order; or `No content found for '<chapter>' in '<book>'.`

**Notes:** matches `book_title` exactly and `chapter` by case-insensitive substring; gathers up to 50 chunks. No per-chunk scores (unlike `search_lore`).

### vault-graph server (9 tools)

Navigation over your Obsidian vault. The six graph tools are served from a precomputed `.graph.json`: a snapshot, so after editing the vault, refresh it with `vault_reload_cache` or `vault_rebuild_graph`. The mentions and read tools (`vault_mentions`, `vault_read_note`, `vault_read_section`) scan the vault live through a per-file cache that re-reads only changed notes, so they are never stale. Note names are file stems (no `.md`).

#### `vault_graph(note, depth=2)`
Show a note's neighborhood: outgoing and incoming links, grouped by hop distance.

| Param | Type | Default | Description |
|---|---|---|---|
| `note` | `str` | required | Starting note name (file stem). |
| `depth` | `int` | `2` | Hops to traverse; clamped to 1 through 4. |

**Returns:** a header with the note's path and type, then per-depth lists of connected notes marked as outgoing or incoming. `No connections found` if the note is isolated.

**Notes:** breadth-first, dedupes visited notes. Broken ("ghost") wikilinks appear with `unknown` type.

#### `vault_backlinks(note)`
List only the notes that link **to** `note`.

| Param | Type | Default | Description |
|---|---|---|---|
| `note` | `str` | required | Target note name. |

**Returns:** one row per backlink (name, type, path), or `No backlinks found for '<note>'.`

**Notes:** incoming edges only (`linked_from`).

#### `vault_search_notes(name_pattern=None, tag=None, note_type=None, limit=20)`
Find notes by name substring, tag, and/or type (AND logic).

| Param | Type | Default | Description |
|---|---|---|---|
| `name_pattern` | `str` | `None` | Case-insensitive substring of the note name. |
| `tag` | `str` | `None` | Note must carry this tag. |
| `note_type` | `str` | `None` | Exact type match, case-insensitive (handles string or list `type`). |
| `limit` | `int` | `20` | Maximum results. |

**Returns:** matching notes (name, type, path, connection count), sorted by name; or a no-match message.

**Notes:** all supplied filters must match. With no filters, returns all notes up to `limit`.

#### `vault_central_notes(tag=None, limit=10)`
Rank the most-connected notes by degree centrality.

| Param | Type | Default | Description |
|---|---|---|---|
| `tag` | `str` | `None` | Restrict the ranking to notes with this tag. |
| `limit` | `int` | `10` | Top-N to return. |

**Returns:** notes ranked highest-degree first (name, connection count, type, path).

**Notes:** degree = outgoing + incoming links. Ties broken alphabetically.

#### `vault_reload_cache()`
Re-read `.graph.json` from disk into memory, without regenerating it. No parameters.

**Returns:** a count of notes and edges loaded, plus a `STALE: ...` warning if any `.md` file is newer than the index. Errors if the index is missing or malformed (and points you to `vault_rebuild_graph`).

**Notes:** use after the index was regenerated outside the server. Fast; does not parse the vault.

#### `vault_rebuild_graph()`
Regenerate `.graph.json` from the current vault, then reload it. No parameters.

**Returns:** the rebuilt note and edge counts, or an error if the builder cannot run.

**Notes:** the heavier of the two refresh tools: it re-parses every `.md` (wikilinks + frontmatter), writes the index, and reloads. Call it after creating or editing notes. The `worldbuilding` skill calls it automatically after writing canon.

#### `vault_mentions(note, unlinked=False, paths=None, budget_tokens=4000)`
Obsidian-style Linked Mentions: every link to `note` with the Markdown block around it (a paragraph; a list item with its sub-items and parent items; a table row with the header; a callout; a property; or a heading with the block below it).

| Param | Type | Default | Description |
|---|---|---|---|
| `note` | `str` | required | File name, vault path or alias. A name with no note lists the links to that unwritten note. |
| `unlinked` | `bool` | `False` | List plain-text mentions of the title and aliases instead (case-insensitive whole words, plus any `VAULT_NAME_ENDINGS`). |
| `paths` | `list[str]` | `None` | Only these folders or notes (a vault path, or the end of one). Entries that name a skipped folder include it. |
| `budget_tokens` | `int` | `4000` | Tokens of excerpts (text plus labels) to show. |

**Returns:** an overview (mentioning notes per top-level folder, the other kind's count, skipped folders, and excerpt tokens shown against all), the excerpts labelled `path:line › heading path`, then a map of every mention not shown (`path L12,40`, grouped by folder) and pull hints.

**Notes:** a mention is always either shown or in the map. Folders take turns, the folder with the most mentioning notes first; inside a folder, notes come in reverse natural order, so numbered sessions come newest first. While not everything fits, no note takes more than a quarter of the budget. An excerpt over 1,500 characters is cut, and its remaining mentions move to the map.

#### `vault_read_note(note)`
Read a note without guessing its size.

| Param | Type | Default | Description |
|---|---|---|---|
| `note` | `str` | required | File name, vault path or alias. |

**Returns:** the note whole when it is under about 2,000 tokens. Otherwise an outline: line count and size, the frontmatter and the lead (each up to 1,500 characters), and every heading with its line range and token estimate. A note with fewer than two headings says how else to get in.

#### `vault_read_section(note, headings)`
Read whole sections of a note.

| Param | Type | Default | Description |
|---|---|---|---|
| `note` | `str` | required | File name, vault path or alias. |
| `headings` | `str` or `list[str]` | required | Heading texts; case and `#` marks do not matter. |

**Returns:** every matching section in full, labelled `path:start-end › heading path`. A heading that matches nothing gets the note's heading list.

---

## Part 2: Internals

For contributors. The behavior above is the contract; this is how it is implemented. Source of truth: the three `mcp-servers/*/` entrypoints and `scripts/build_vault_graph.py`.

### Transport, startup, env
All three are **FastMCP** servers over **stdio**, launched as `python mcp-servers/<server>/<entry>.py`, registering tools with the `@mcp.tool()` decorator. They are wired in `.mcp.json` / `.claude/settings.json` (see quickstart).

| Server | Entrypoint | Env vars |
|---|---|---|
| r2r | `mcp-servers/r2r-wrapper/r2r_mcp_wrapper.py` | `R2R_API_BASE` (default `http://localhost:7272`), `R2R_TIMEOUT` (default `300`s) |
| sourcebooks | `mcp-servers/sourcebooks/server.py` | `R2R_API_BASE` (default `http://localhost:7272`) |
| vault-graph | `mcp-servers/vault-graph/server.py` | `VAULT_PATH` (graph tools read `<VAULT_PATH>/.graph.json`), plus `VAULT_SKIP_FOLDERS` and `VAULT_NAME_ENDINGS` (optional, comma-separated, for `vault_mentions`) |

In the devcontainer, `R2R_API_BASE` points at `http://host.docker.internal:7272` (R2R runs on the host), not `localhost`.

### Shared helpers
- **r2r / sourcebooks:** `_get_client()` builds a fresh `R2RClient(R2R_API_BASE)` per call (r2r also applies `R2R_TIMEOUT`). No connection pooling.
- **vault-graph:** `_load_graph()` loads the index into a module-level `_graph`; `_check_graph()` gates the four query tools and returns an error string if the graph is missing or empty; `_staleness_summary()` compares the `.graph.json` mtime against every `.md` file. The mentions and read tools use `_index()`, a module-level `vault_index.VaultIndex` refreshed on every call: it stats every `.md` file and re-parses only added or changed ones with `note_parser.parse_note`.

### Tool to underlying call
- **r2r:** `search` -> `retrieval.search`; `ingest_document` -> `documents.create`; `list_documents` -> `documents.list` (or `collections.list_documents`); `delete_document` -> `documents.delete`; `list_collections` -> `collections.list`.
- **sourcebooks:** all via `retrieval.search` except `list_books` -> `documents.list(limit=100)`. Search settings always set `use_semantic_search`, `use_hybrid_search`, `include_metadatas`, `include_scores`. Filters: `search_lore` -> `book_title $eq` and/or `content_type $eq`; `get_chapter` -> `book_title $eq` plus `chapter $ilike "%...%"`, query `"<book> <chapter>"`, `limit=50`.
- **vault-graph:** reads the in-memory `_graph`; `vault_rebuild_graph` calls `build_vault_graph.build_graph(VAULT_PATH)` in-process, writes `.graph.json`, then reloads; `vault_mentions`, `vault_read_note` and `vault_read_section` query the live `VaultIndex` and never touch `.graph.json`.

### sourcebooks metadata schema
Tools assume each ingested document carries:

| Field | Required | Used by |
|---|---|---|
| `book_title` | yes | filtering, grouping, citations |
| `chapter` | no | `get_chapter` filter, `search_lore` citation |
| `page_range` | no | `search_lore` citation |
| `content_type` | no | `search_lore` filter, `list_books` |
| `system` | no | `list_books` |
| `publisher` | no | `list_books` |

Missing optional fields render as `Unknown`. The bulk ingester (`scripts/ingest_books.py`) sets these.

### vault-graph data model
`.graph.json`, produced by `scripts/build_vault_graph.py`:
```json
{
  "nodes": {
    "<note stem>": {
      "path": "Folder/Note.md",
      "tags": ["..."],
      "type": "npc",
      "links_to": ["OtherNote"],
      "linked_from": ["SourceNote"]
    }
  },
  "edges": [ {"source": "...", "target": "..."} ],
  "metadata": { "vault_path": "...", "built_at": "ISO-8601", "note_count": 0, "edge_count": 0 }
}
```
- **Node:** one `.md` file; `type` and `tags` come from YAML frontmatter (defaults `type=None`, `tags=[]`).
- **Edge:** a `[[target]]` wikilink. The parser strips `#anchors` and `|aliases`. Ghost links (targets with no note) stay in `links_to` but are not reciprocated.
- **Degree centrality:** `len(links_to) + len(linked_from)` (undirected count). No eigenvector or betweenness measures.

**Live index (mentions and read tools).** `vault_index.py` keeps one entry per note (vault path, modification time in nanoseconds, size, parsed note) and resolves links the Obsidian way: a target without `/` matches a file name, one with `/` a path from the root or the end of a path; ties go to the linking note's folder, then to the fewest path segments. `note_parser.py` is a pure line scanner for frontmatter, headings, links and blocks.

### reload vs rebuild
- **`vault_reload_cache`** re-reads the existing `.graph.json` into memory. Cheap. Use it when the index was regenerated outside the server (for example, you ran `build_vault_graph.py` on the host).
- **`vault_rebuild_graph`** regenerates the index from the current vault, then reloads. Use it after editing notes. It is the only tool that writes `.graph.json`.

### Error model
- **r2r / sourcebooks:** every tool wraps its body in try/except and returns an `Error: ...` string rather than raising, so a backend hiccup surfaces in context instead of killing the call. Request timeouts are governed by `R2R_TIMEOUT` (raise it for very large ingests; see [`troubleshooting.md`](troubleshooting.md)).
- **vault-graph:** query tools short-circuit via `_check_graph()` with a clear message when the index is missing or empty; `vault_reload_cache` distinguishes "not found" from "malformed JSON"; `vault_rebuild_graph` reports a builder-import failure with the fallback command.
- **vault-graph mentions and read tools:** a missing vault root returns `Error: vault root is missing or not a folder: <path>`; an unknown note returns `Error: no note matches '<name>'` with up to five close names.
