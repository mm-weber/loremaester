"""
Verification tests for D2 (R2R MCP Wrapper).

Integration-style smoke tests covering:
- Full document lifecycle: ingest → list → search → delete → list
- Environment variable configuration (R2R_API_BASE)
- Edge cases: empty results, title precedence, title fallback
"""

import os

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from r2r_mcp_wrapper import (
    _get_client,
    delete_document,
    ingest_document,
    list_collections,
    list_documents,
    search,
)

DOC_UUID = UUID("aabbccdd-1122-3344-5566-778899aabbcc")


# ---------------------------------------------------------------------------
# TestSmokeFlow — full lifecycle
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
# TestEnvironmentConfig — R2R_API_BASE env var
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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
