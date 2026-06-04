"""
Tests for the R2R MCP wrapper (mcp-servers/r2r/r2r_mcp_wrapper.py).

Unit tests for each tool (search, ingest, list documents, delete document,
list collections) and MCP server setup, plus integration-style coverage: a
full document lifecycle, R2R_API_BASE env configuration, and edge cases
(empty results, title precedence/fallback).
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

import r2r_mcp_wrapper
from r2r_mcp_wrapper import (
    _get_client,
    delete_document,
    ingest_document,
    list_collections,
    list_documents,
    mcp,
    search,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOC_UUID = UUID("12345678-1234-1234-1234-123456789abc")
COL_UUID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _make_chunk(score=0.95, text="chunk text", title="Doc", doc_type="pdf"):
    chunk = MagicMock()
    chunk.score = score
    chunk.text = text
    chunk.metadata = {"title": title, "document_type": doc_type}
    return chunk


def _make_search_result(chunks):
    result = MagicMock()
    result.results = MagicMock()
    result.results.chunk_search_results = chunks
    return result


def _make_doc(title="Doc1", doc_type="pdf", status="success", doc_id=None):
    doc = MagicMock()
    doc.title = title
    doc.document_type = doc_type
    doc.ingestion_status = status
    doc.id = doc_id or DOC_UUID
    return doc


def _make_collection(name="Col1", doc_count=5, created="2024-01-01", col_id=None):
    col = MagicMock()
    col.name = name
    col.document_count = doc_count
    col.created_at = created
    col.id = col_id or COL_UUID
    return col


# ---------------------------------------------------------------------------
# TestSearch — REQ-D2-01, REQ-D2-06, REQ-D2-09
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearch:
    """Tests for the search MCP tool."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_basic(self, mock_client_cls):
        client = mock_client_cls.return_value
        chunks = [_make_chunk(), _make_chunk()]
        client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))

        output = await search(query="test query")

        assert '## Search Results for: "test query"' in output
        assert "### Result 1 (score: 0.95)" in output
        assert "[Source: Doc | Type: pdf]" in output
        assert "chunk text" in output
        assert "Returned 2 of 2 chunks" in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_default_limit_is_5(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(
            return_value=_make_search_result([_make_chunk()])
        )

        await search(query="test")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get(
            "search_settings", call_kwargs[1].get("search_settings")
        )
        assert settings["limit"] == 5

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_custom_limit(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(
            return_value=_make_search_result([_make_chunk()])
        )

        await search(query="test", limit=3)

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get(
            "search_settings", call_kwargs[1].get("search_settings")
        )
        assert settings["limit"] == 3

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_with_filters(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(
            return_value=_make_search_result([_make_chunk()])
        )
        filters = {"book_title": {"$eq": "Foo"}}

        await search(query="test", filters=filters)

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get(
            "search_settings", call_kwargs[1].get("search_settings")
        )
        assert settings["filters"]["book_title"] == {"$eq": "Foo"}

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_with_collection_ids(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(
            return_value=_make_search_result([_make_chunk()])
        )

        await search(query="test", collection_ids=["abc-123"])

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get(
            "search_settings", call_kwargs[1].get("search_settings")
        )
        assert settings["filters"]["collection_ids"] == {"$overlap": ["abc-123"]}

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_with_search_mode(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(
            return_value=_make_search_result([_make_chunk()])
        )

        await search(query="test", search_mode="basic")

        call_kwargs = client.retrieval.search.call_args
        assert (
            call_kwargs.kwargs.get("search_mode", call_kwargs[1].get("search_mode"))
            == "basic"
        )

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_error(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(
            side_effect=Exception("Connection refused")
        )

        output = await search(query="test")

        assert output == "Error: Connection refused"


# ---------------------------------------------------------------------------
# TestIngestDocument — REQ-D2-02, REQ-D2-06
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIngestDocument:
    """Tests for the ingest_document MCP tool."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_ingest_raw_text(self, mock_client_cls):
        client = mock_client_cls.return_value
        result = MagicMock()
        result.results = MagicMock()
        result.results.document_id = DOC_UUID
        result.results.message = "ok"
        client.documents.create = MagicMock(return_value=result)

        output = await ingest_document(raw_text="hello", title="Test Doc")

        assert "Document ingested successfully" in output
        assert "12345678-1234-1234-1234-123456789abc" in output
        assert "Test Doc" in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_ingest_chunks(self, mock_client_cls):
        client = mock_client_cls.return_value
        result = MagicMock()
        result.results = MagicMock()
        result.results.document_id = DOC_UUID
        result.results.message = "ok"
        client.documents.create = MagicMock(return_value=result)

        await ingest_document(chunks=["c1", "c2"])

        call_kwargs = client.documents.create.call_args
        chunks_arg = call_kwargs.kwargs.get("chunks", call_kwargs[1].get("chunks"))
        assert chunks_arg == ["c1", "c2"]

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_ingest_with_metadata_and_collections(self, mock_client_cls):
        client = mock_client_cls.return_value
        result = MagicMock()
        result.results = MagicMock()
        result.results.document_id = DOC_UUID
        result.results.message = "ok"
        client.documents.create = MagicMock(return_value=result)

        await ingest_document(
            raw_text="text",
            metadata={"key": "val"},
            collection_ids=["col1"],
        )

        call_kwargs = client.documents.create.call_args
        assert call_kwargs.kwargs.get(
            "metadata", call_kwargs[1].get("metadata")
        ) == {"key": "val"}
        assert call_kwargs.kwargs.get(
            "collection_ids", call_kwargs[1].get("collection_ids")
        ) == ["col1"]

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_ingest_error(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.documents.create = MagicMock(
            side_effect=Exception("Ingest failed")
        )

        output = await ingest_document(raw_text="hello")

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestListDocuments — REQ-D2-03, REQ-D2-06, REQ-D2-09
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListDocuments:
    """Tests for the list_documents MCP tool."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_documents_basic(self, mock_client_cls):
        client = mock_client_cls.return_value
        docs = [_make_doc(title="Doc1"), _make_doc(title="Doc2")]
        paginated = MagicMock()
        paginated.results = docs
        client.documents.list = MagicMock(return_value=paginated)

        output = await list_documents()

        assert "1." in output
        assert "2." in output
        assert "Doc1" in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_documents_default_limit_20(self, mock_client_cls):
        client = mock_client_cls.return_value
        paginated = MagicMock()
        paginated.results = []
        client.documents.list = MagicMock(return_value=paginated)

        await list_documents()

        client.documents.list.assert_called_once_with(offset=0, limit=20)

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_documents_by_collection(self, mock_client_cls):
        client = mock_client_cls.return_value
        paginated = MagicMock()
        paginated.results = [_make_doc()]
        client.collections.list_documents = MagicMock(return_value=paginated)
        client.documents.list = MagicMock()

        await list_documents(collection_id="abc-123")

        client.collections.list_documents.assert_called_once_with(
            "abc-123", offset=0, limit=20
        )
        client.documents.list.assert_not_called()

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_documents_error(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.documents.list = MagicMock(
            side_effect=Exception("List failed")
        )

        output = await list_documents()

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestDeleteDocument — REQ-D2-04, REQ-D2-06
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeleteDocument:
    """Tests for the delete_document MCP tool."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_delete_success(self, mock_client_cls):
        client = mock_client_cls.return_value
        result = MagicMock()
        result.results = {"message": "ok"}
        client.documents.delete = MagicMock(return_value=result)

        output = await delete_document(
            document_id="12345678-1234-1234-1234-123456789abc"
        )

        assert "deleted successfully" in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_delete_error(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.documents.delete = MagicMock(
            side_effect=Exception("Delete failed")
        )

        output = await delete_document(document_id="bad-id")

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestListCollections — REQ-D2-05, REQ-D2-06, REQ-D2-09
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListCollections:
    """Tests for the list_collections MCP tool."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_collections_basic(self, mock_client_cls):
        client = mock_client_cls.return_value
        cols = [_make_collection(name="Col1"), _make_collection(name="Col2")]
        paginated = MagicMock()
        paginated.results = cols
        client.collections.list = MagicMock(return_value=paginated)

        output = await list_collections()

        assert "1." in output
        assert "2." in output
        assert "Col1" in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_collections_default_limit_20(self, mock_client_cls):
        client = mock_client_cls.return_value
        paginated = MagicMock()
        paginated.results = []
        client.collections.list = MagicMock(return_value=paginated)

        await list_collections()

        client.collections.list.assert_called_once_with(offset=0, limit=20)

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_collections_error(self, mock_client_cls):
        client = mock_client_cls.return_value
        client.collections.list = MagicMock(
            side_effect=Exception("Collections failed")
        )

        output = await list_collections()

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestServerSetup — REQ-D2-07, REQ-D2-08
# ---------------------------------------------------------------------------


class TestServerSetup:
    """Tests for MCP server configuration."""

    def test_mcp_server_is_fastmcp(self):
        from mcp.server.fastmcp import FastMCP

        assert isinstance(r2r_mcp_wrapper.mcp, FastMCP)

    def test_server_name(self):
        assert r2r_mcp_wrapper.mcp.name == "R2R"

    def test_all_five_tools_registered(self):
        tools = r2r_mcp_wrapper.mcp._tool_manager._tools
        expected = {
            "search",
            "ingest_document",
            "list_documents",
            "delete_document",
            "list_collections",
        }
        assert expected == set(tools.keys())


# ---------------------------------------------------------------------------
# TestSmokeFlow — full document lifecycle (integration-style)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSmokeFlow:
    """End-to-end lifecycle: ingest → list → search → delete → list."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_lifecycle_ingest_list_search_delete(self, mock_client_cls):
        client = mock_client_cls.return_value

        # -- 1. ingest_document --
        ingest_result = MagicMock()
        ingest_result.results.document_id = DOC_UUID
        ingest_result.results.message = "Document created"
        client.documents.create = MagicMock(return_value=ingest_result)

        output = await ingest_document(raw_text="Mithril veins run deep beneath Ironhold.", title="Ironhold Lore")
        assert "Document ingested successfully" in output
        assert str(DOC_UUID) in output
        assert "Ironhold Lore" in output

        # -- 2. list_documents (doc present) --
        doc_mock = MagicMock()
        doc_mock.title = "Ironhold Lore"
        doc_mock.document_type = "txt"
        doc_mock.ingestion_status = "success"
        doc_mock.id = DOC_UUID
        list_result = MagicMock()
        list_result.results = [doc_mock]
        client.documents.list = MagicMock(return_value=list_result)

        output = await list_documents()
        assert "Ironhold Lore" in output

        # -- 3. search --
        chunk = MagicMock()
        chunk.score = 0.91
        chunk.text = "Mithril veins run deep beneath Ironhold."
        chunk.metadata = {"title": "Ironhold Lore", "document_type": "txt"}
        search_result = MagicMock()
        search_result.results.chunk_search_results = [chunk]
        client.retrieval.search = MagicMock(return_value=search_result)

        output = await search(query="mithril mining")
        assert "mithril mining" in output.lower() or "Mithril" in output
        assert "0.91" in output
        assert "Returned 1 of 1 chunks" in output

        # -- 4. delete_document --
        client.documents.delete = MagicMock(return_value=MagicMock())

        output = await delete_document(document_id=str(DOC_UUID))
        assert "deleted successfully" in output

        # -- 5. list_documents (empty) --
        empty_result = MagicMock()
        empty_result.results = []
        client.documents.list = MagicMock(return_value=empty_result)

        output = await list_documents()
        assert "No documents found." in output


# ---------------------------------------------------------------------------
# TestEnvironmentConfig — R2R_API_BASE env var (sync: tests _get_client only)
# ---------------------------------------------------------------------------


class TestEnvironmentConfig:
    """Verify _get_client reads R2R_API_BASE (not R2R_BASE_URL)."""

    @patch("r2r_mcp_wrapper.R2RClient")
    def test_get_client_reads_R2R_API_BASE(self, mock_client_cls):
        with patch.dict(os.environ, {"R2R_API_BASE": "http://custom-host:9999"}, clear=False):
            _get_client()
        mock_client_cls.assert_called_once_with("http://custom-host:9999")

    @patch("r2r_mcp_wrapper.R2RClient")
    def test_get_client_default_url(self, mock_client_cls):
        env = os.environ.copy()
        env.pop("R2R_API_BASE", None)
        env.pop("R2R_BASE_URL", None)
        with patch.dict(os.environ, env, clear=True):
            _get_client()
        mock_client_cls.assert_called_once_with("http://localhost:7272")

    @patch("r2r_mcp_wrapper.R2RClient")
    def test_old_env_var_R2R_BASE_URL_is_ignored(self, mock_client_cls):
        env = os.environ.copy()
        env.pop("R2R_API_BASE", None)
        env["R2R_BASE_URL"] = "http://old-host:1234"
        with patch.dict(os.environ, env, clear=True):
            _get_client()
        mock_client_cls.assert_called_once_with("http://localhost:7272")


# ---------------------------------------------------------------------------
# TestEdgeCases — zero results, empty lists, title logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEdgeCases:
    """Edge-case coverage for search, list, and ingest title logic."""

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_search_zero_results(self, mock_client_cls):
        client = mock_client_cls.return_value
        search_result = MagicMock()
        search_result.results.chunk_search_results = []
        client.retrieval.search = MagicMock(return_value=search_result)

        output = await search(query="nonexistent")
        assert "Returned 0 of 0 chunks" in output
        assert "Error" not in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_documents_empty(self, mock_client_cls):
        client = mock_client_cls.return_value
        paginated = MagicMock()
        paginated.results = []
        client.documents.list = MagicMock(return_value=paginated)

        output = await list_documents()
        assert output == "No documents found."

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_list_collections_empty(self, mock_client_cls):
        client = mock_client_cls.return_value
        paginated = MagicMock()
        paginated.results = []
        client.collections.list = MagicMock(return_value=paginated)

        output = await list_collections()
        assert output == "No collections found."

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_ingest_title_from_metadata_takes_precedence(self, mock_client_cls):
        client = mock_client_cls.return_value
        result = MagicMock()
        result.results.document_id = DOC_UUID
        result.results.message = "ok"
        client.documents.create = MagicMock(return_value=result)

        output = await ingest_document(
            raw_text="text",
            metadata={"title": "Metadata Title"},
            title="Param Title",
        )
        assert "Metadata Title" in output
        assert "Param Title" not in output

    @patch("r2r_mcp_wrapper.R2RClient")
    async def test_ingest_title_fallback_to_untitled(self, mock_client_cls):
        client = mock_client_cls.return_value
        result = MagicMock()
        result.results.document_id = DOC_UUID
        result.results.message = "ok"
        client.documents.create = MagicMock(return_value=result)

        output = await ingest_document(raw_text="text")
        assert "Untitled" in output
