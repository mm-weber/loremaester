"""Worldbuilding Source Books MCP server — lore-aware search tools wrapping R2R."""

import os
import sys
from collections import defaultdict

from mcp.server.fastmcp import FastMCP

try:
    from r2r import R2RClient
    from shared.abstractions.search import SearchSettings
except ImportError:
    sys.path.insert(0, "/workspace/repos/R2R/main/py/")
    from r2r import R2RClient
    from shared.abstractions.search import SearchSettings

mcp = FastMCP("Worldbuilding Source Books")


def _get_client() -> R2RClient:
    base_url = os.environ.get("R2R_API_BASE", "http://localhost:7272")
    return R2RClient(base_url)


@mcp.tool()
async def search_lore(query: str, book: str = None, content_type: str = None, limit: int = 5) -> str:
    """Search worldbuilding lore across source books."""
    try:
        client = _get_client()
        filters = {}
        if book:
            filters["book_title"] = {"$eq": book}
        if content_type:
            filters["content_type"] = {"$eq": content_type}

        settings = SearchSettings(
            filters=filters,
            limit=limit,
            use_hybrid_search=True,
            use_semantic_search=True,
            include_metadatas=True,
            include_scores=True,
        )

        result = client.retrieval.search(query=query, search_settings=settings)
        chunks = result.results.chunk_search_results

        lines = [f"## Search Results for: {query}\n"]
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.metadata
            book_title = meta.get("book_title", "Unknown")
            chapter = meta.get("chapter", "Unknown")
            page_range = meta.get("page_range", "")
            score = chunk.score
            text = chunk.text
            lines.append(f"### {i}. {book_title} — {chapter} ({page_range}) [{score:.2f}]")
            lines.append(text)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def list_books() -> str:
    """List all worldbuilding source books in the library."""
    try:
        client = _get_client()
        result = client.documents.list(limit=100)
        docs = result.results

        if not docs:
            return "No books found."

        groups = defaultdict(list)
        for doc in docs:
            title = doc.metadata.get("book_title", "Unknown")
            groups[title].append(doc)

        lines = ["## Source Books\n"]
        for i, (title, book_docs) in enumerate(groups.items(), 1):
            first = book_docs[0]
            meta = first.metadata
            publisher = meta.get("publisher", "Unknown")
            system = meta.get("system", "Unknown")
            content_type = meta.get("content_type", "Unknown")
            chapter_count = len(book_docs)
            lines.append(
                f"{i}. **{title}** — Publisher: {publisher}, System: {system}, "
                f"Type: {content_type}, Chapters: {chapter_count}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_chapter(book: str, chapter: str) -> str:
    """Retrieve the full text of a specific chapter from a source book."""
    try:
        client = _get_client()
        filters = {
            "book_title": {"$eq": book},
            "chapter": {"$ilike": f"%{chapter}%"},
        }
        settings = SearchSettings(
            filters=filters,
            limit=50,
            use_hybrid_search=True,
            use_semantic_search=True,
            include_metadatas=True,
        )

        result = client.retrieval.search(query=f"{book} {chapter}", search_settings=settings)
        chunks = result.results.chunk_search_results

        if not chunks:
            return f"No content found for '{chapter}' in '{book}'."

        lines = [f"## {book} — {chapter}\n"]
        for chunk in chunks:
            lines.append(chunk.text)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
