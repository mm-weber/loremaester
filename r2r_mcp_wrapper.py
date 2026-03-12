"""R2R MCP Wrapper — FastMCP server exposing R2R operations as tools."""

import os

from mcp.server.fastmcp import FastMCP

try:
    from r2r import R2RClient
    from shared.abstractions.search import SearchSettings
except ImportError:
    from r2r import R2RClient
    from shared.abstractions.search import SearchSettings

mcp = FastMCP("R2R")


def _get_client() -> R2RClient:
    """Get an R2R client instance."""
    base_url = os.environ.get("R2R_API_BASE", "http://localhost:7272")
    return R2RClient(base_url)


@mcp.tool()
async def search(
    query: str,
    collection_ids: list[str] | None = None,
    filters: dict | None = None,
    limit: int = 5,
    search_mode: str = "custom",
) -> str:
    """Search R2R for documents matching a query.

    Args:
        query: The search query string.
        collection_ids: Optional list of collection IDs to scope the search.
        filters: Optional filter dictionary for search settings.
        limit: Maximum number of results to return.
        search_mode: The search mode to use (default: "custom").

    Returns:
        Formatted markdown string with search results.
    """
    try:
        client = _get_client()

        effective_filters = filters or {}
        if collection_ids:
            effective_filters["collection_ids"] = {"$overlap": collection_ids}

        settings = SearchSettings(limit=limit, filters=effective_filters)

        result = client.retrieval.search(
            query=query,
            search_mode=search_mode,
            search_settings=settings,
        )

        chunks = result.results.chunk_search_results
        lines = [f'## Search Results for: "{query}"\n']

        for i, chunk in enumerate(chunks, 1):
            score = getattr(chunk, "score", 0.0)
            text = getattr(chunk, "text", str(chunk))
            metadata = getattr(chunk, "metadata", {}) or {}
            title = metadata.get("title", "Unknown")
            doc_type = metadata.get("document_type", "Unknown")

            lines.append(f"### Result {i} (score: {score:.2f})")
            lines.append(text)
            lines.append("")
            lines.append(f"[Source: {title} | Type: {doc_type}]")
            lines.append("")
            lines.append("---\n")

        lines.append(f"Returned {len(chunks)} of {len(chunks)} chunks (limit: {limit})")
        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def ingest_document(
    raw_text: str | None = None,
    chunks: list[str] | None = None,
    metadata: dict | None = None,
    collection_ids: list[str] | None = None,
    title: str | None = None,
) -> str:
    """Ingest a document into R2R.

    Args:
        raw_text: Raw text content to ingest.
        chunks: Pre-chunked text segments to ingest.
        metadata: Optional metadata dictionary for the document.
        collection_ids: Optional list of collection IDs to add the document to.
        title: Optional title for the document.

    Returns:
        Confirmation message with document ID and title.
    """
    try:
        client = _get_client()

        kwargs: dict = {}
        if raw_text is not None:
            kwargs["raw_text"] = raw_text
        if chunks is not None:
            kwargs["chunks"] = chunks
        if metadata is not None:
            kwargs["metadata"] = metadata
        if collection_ids is not None:
            kwargs["collection_ids"] = collection_ids

        result = client.documents.create(**kwargs)

        doc_id = result.results.document_id
        message = result.results.message

        display_title = (
            (metadata or {}).get("title")
            or title
            or "Untitled"
        )

        return (
            f"Document ingested successfully.\n"
            f"- **ID**: {doc_id}\n"
            f"- **Title**: {display_title}\n"
            f"- **Message**: {message}"
        )

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def list_documents(
    collection_id: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> str:
    """List documents in R2R, optionally filtered by collection.

    Args:
        collection_id: Optional collection ID to list documents from.
        offset: Pagination offset.
        limit: Maximum number of documents to return.

    Returns:
        Formatted list of documents with their metadata.
    """
    try:
        client = _get_client()

        if collection_id:
            result = client.collections.list_documents(
                collection_id, offset=offset, limit=limit
            )
        else:
            result = client.documents.list(offset=offset, limit=limit)

        docs = result.results

        if not docs:
            return "No documents found."

        lines = ["## Documents\n"]
        for i, doc in enumerate(docs, 1):
            title = getattr(doc, "title", "Untitled")
            doc_type = getattr(doc, "document_type", "Unknown")
            status = getattr(doc, "ingestion_status", "Unknown")
            doc_id = getattr(doc, "id", "Unknown")

            lines.append(f"{i}. **{title}**")
            lines.append(f"   - Type: {doc_type}")
            lines.append(f"   - Status: {status}")
            lines.append(f"   - ID: `{doc_id}`")
            lines.append("")

        lines.append(f"Showing {len(docs)} document(s) (offset: {offset}, limit: {limit})")
        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def delete_document(document_id: str) -> str:
    """Delete a document from R2R by its ID.

    Args:
        document_id: The ID of the document to delete.

    Returns:
        Confirmation message on success, or error message on failure.
    """
    try:
        client = _get_client()
        client.documents.delete(id=document_id)
        return f"Document `{document_id}` deleted successfully."

    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def list_collections(offset: int = 0, limit: int = 20) -> str:
    """List all collections in R2R.

    Args:
        offset: Pagination offset.
        limit: Maximum number of collections to return.

    Returns:
        Formatted list of collections with their metadata.
    """
    try:
        client = _get_client()
        result = client.collections.list(offset=offset, limit=limit)
        collections = result.results

        if not collections:
            return "No collections found."

        lines = ["## Collections\n"]
        for i, coll in enumerate(collections, 1):
            name = getattr(coll, "name", "Unnamed")
            doc_count = getattr(coll, "document_count", 0)
            created_at = getattr(coll, "created_at", "Unknown")
            coll_id = getattr(coll, "id", "Unknown")

            lines.append(f"{i}. **{name}**")
            lines.append(f"   - Documents: {doc_count}")
            lines.append(f"   - Created: {created_at}")
            lines.append(f"   - ID: `{coll_id}`")
            lines.append("")

        lines.append(
            f"Showing {len(collections)} collection(s) (offset: {offset}, limit: {limit})"
        )
        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
