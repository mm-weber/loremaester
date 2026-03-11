"""Tests for the Worldbuilding Source Books MCP server (sourcebooks/server.py)."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure server module can be imported from this directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

import server  # noqa: E402
from server import search_lore, list_books, get_chapter  # noqa: E402


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_chunk(score=0.95, text="chunk text", metadata=None):
    """Create a mock search chunk with worldbuilding metadata."""
    chunk = MagicMock()
    chunk.score = score
    chunk.text = text
    chunk.metadata = metadata or {
        "book_title": "Dwarf Kingdoms",
        "chapter": "Chapter 3: The Deep Roads",
        "page_range": "pp. 45-52",
        "content_type": "lore",
    }
    return chunk


def _make_search_result(chunks):
    """Wrap chunks in .results.chunk_search_results"""
    result = MagicMock()
    result.results = MagicMock()
    result.results.chunk_search_results = chunks
    return result


def _make_doc(doc_id="doc-1", title="Book", metadata=None):
    """Create a mock document with worldbuilding metadata."""
    doc = MagicMock()
    doc.id = doc_id
    doc.title = title
    doc.metadata = metadata or {
        "book_title": "Dwarf Kingdoms",
        "system": "D&D 5e",
        "publisher": "WotC",
        "content_type": "lore",
        "chapter": "Chapter 3",
        "page_range": "pp. 45-52",
    }
    return doc


def _make_docs_response(docs):
    """Wrap docs in .results list"""
    result = MagicMock()
    result.results = docs
    return result


# ---------------------------------------------------------------------------
# TestSearchLore
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSearchLore:
    @patch("server.R2RClient")
    async def test_basic_search(self, mock_client_cls):
        """2 chunks with book metadata -> output contains header, book title, chapter, page range, score, text"""
        client = mock_client_cls.return_value
        chunks = [
            _make_chunk(score=0.95, text="Deep roads were carved by ancient dwarves"),
            _make_chunk(score=0.82, text="The forge halls echo with hammers", metadata={
                "book_title": "Dwarf Kingdoms",
                "chapter": "Chapter 4: The Forge",
                "page_range": "pp. 53-60",
                "content_type": "lore",
            }),
        ]
        client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))

        output = await search_lore(query="dwarven roads")

        assert "search_lore" in output.lower() or "Search" in output  # has a header
        assert "Dwarf Kingdoms" in output
        assert "Chapter 3" in output
        assert "pp. 45-52" in output
        assert "0.95" in output
        assert "Deep roads were carved" in output
        assert "Chapter 4" in output  # second result too

    @patch("server.R2RClient")
    async def test_hybrid_search_default(self, mock_client_cls):
        """SearchSettings called with use_hybrid_search=True"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await search_lore(query="test")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.use_hybrid_search is True

    @patch("server.R2RClient")
    async def test_filter_by_book(self, mock_client_cls):
        """book='Dwarf Kingdoms' -> filters contain book_title.$eq"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await search_lore(query="test", book="Dwarf Kingdoms")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.filters["book_title"] == {"$eq": "Dwarf Kingdoms"}

    @patch("server.R2RClient")
    async def test_filter_by_content_type(self, mock_client_cls):
        """content_type='lore' -> filters contain content_type.$eq"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await search_lore(query="test", content_type="lore")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.filters["content_type"] == {"$eq": "lore"}

    @patch("server.R2RClient")
    async def test_combined_filters(self, mock_client_cls):
        """book + content_type both set -> both filters present"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await search_lore(query="test", book="Dwarf Kingdoms", content_type="lore")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.filters["book_title"] == {"$eq": "Dwarf Kingdoms"}
        assert settings.filters["content_type"] == {"$eq": "lore"}

    @patch("server.R2RClient")
    async def test_default_limit_5(self, mock_client_cls):
        """No limit arg -> SearchSettings called with limit=5"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await search_lore(query="test")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.limit == 5

    @patch("server.R2RClient")
    async def test_custom_limit(self, mock_client_cls):
        """limit=10 -> SearchSettings called with limit=10"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await search_lore(query="test", limit=10)

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.limit == 10

    @patch("server.R2RClient")
    async def test_error_handling(self, mock_client_cls):
        """Client raises Exception -> output starts with 'Error:'"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(side_effect=Exception("Connection refused"))

        output = await search_lore(query="test")

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestListBooks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListBooks:
    @patch("server.R2RClient")
    async def test_basic_list(self, mock_client_cls):
        """3 docs, 2 same book_title -> output groups by book, shows publisher/system/content_type/count"""
        client = mock_client_cls.return_value
        docs = [
            _make_doc(doc_id="d1", title="Ch1", metadata={
                "book_title": "Dwarf Kingdoms", "system": "D&D 5e",
                "publisher": "WotC", "content_type": "lore",
                "chapter": "Ch 1", "page_range": "pp. 1-20",
            }),
            _make_doc(doc_id="d2", title="Ch2", metadata={
                "book_title": "Dwarf Kingdoms", "system": "D&D 5e",
                "publisher": "WotC", "content_type": "lore",
                "chapter": "Ch 2", "page_range": "pp. 21-40",
            }),
            _make_doc(doc_id="d3", title="ElvenLore", metadata={
                "book_title": "Elven Lore", "system": "Pathfinder",
                "publisher": "Paizo", "content_type": "bestiary",
                "chapter": "Ch 1", "page_range": "pp. 1-15",
            }),
        ]
        client.documents.list = MagicMock(return_value=_make_docs_response(docs))

        output = await list_books()

        assert "Dwarf Kingdoms" in output
        assert "Elven Lore" in output
        assert "WotC" in output or "wotc" in output.lower()
        assert "Paizo" in output or "paizo" in output.lower()
        # Dwarf Kingdoms should show 2 chapters
        assert "2" in output  # chapter count for Dwarf Kingdoms

    @patch("server.R2RClient")
    async def test_empty_list(self, mock_client_cls):
        """No docs -> output indicates no books found"""
        client = mock_client_cls.return_value
        client.documents.list = MagicMock(return_value=_make_docs_response([]))

        output = await list_books()

        assert "no" in output.lower() or "No" in output

    @patch("server.R2RClient")
    async def test_error_handling(self, mock_client_cls):
        """Client raises -> output starts with 'Error:'"""
        client = mock_client_cls.return_value
        client.documents.list = MagicMock(side_effect=Exception("API error"))

        output = await list_books()

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestGetChapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetChapter:
    @patch("server.R2RClient")
    async def test_basic_chapter(self, mock_client_cls):
        """Search returns 3 ordered chunks -> output contains concatenated text in order"""
        client = mock_client_cls.return_value
        chunks = [
            _make_chunk(text="Paragraph one of the chapter."),
            _make_chunk(text="Paragraph two continues."),
            _make_chunk(text="Paragraph three concludes."),
        ]
        client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))

        output = await get_chapter(book="Dwarf Kingdoms", chapter="Chapter 3")

        assert "Paragraph one" in output
        assert "Paragraph two" in output
        assert "Paragraph three" in output
        # Check order: one before two before three
        assert output.index("Paragraph one") < output.index("Paragraph two")
        assert output.index("Paragraph two") < output.index("Paragraph three")

    @patch("server.R2RClient")
    async def test_filter_construction(self, mock_client_cls):
        """book='X', chapter='Ch 3' -> filters: book_title.$eq + chapter.$ilike with %Ch 3%"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([_make_chunk()]))

        await get_chapter(book="Dwarf Kingdoms", chapter="Ch 3")

        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.filters["book_title"] == {"$eq": "Dwarf Kingdoms"}
        assert settings.filters["chapter"] == {"$ilike": "%Ch 3%"}

    @patch("server.R2RClient")
    async def test_no_results(self, mock_client_cls):
        """Empty search -> output indicates no content found"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([]))

        output = await get_chapter(book="Nonexistent", chapter="Ch 1")

        assert "no" in output.lower() or "No" in output or "not found" in output.lower()

    @patch("server.R2RClient")
    async def test_error_handling(self, mock_client_cls):
        """Client raises -> output starts with 'Error:'"""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(side_effect=Exception("Timeout"))

        output = await get_chapter(book="X", chapter="Y")

        assert output.startswith("Error:")


# ---------------------------------------------------------------------------
# TestServerSetup
# ---------------------------------------------------------------------------

class TestServerSetup:
    def test_server_name(self):
        """mcp.name == 'Worldbuilding Source Books'"""
        assert server.mcp.name == "Worldbuilding Source Books"

    def test_tools_registered(self):
        """All 3 tools registered"""
        tools = server.mcp._tool_manager._tools
        expected = {"search_lore", "list_books", "get_chapter"}
        assert expected == set(tools.keys())

    @patch.dict(os.environ, {"R2R_API_BASE": "http://custom:9999"})
    @patch("server.R2RClient")
    def test_client_uses_env_var(self, mock_client_cls):
        """Set R2R_API_BASE env -> _get_client() uses the env value"""
        from server import _get_client
        _get_client()
        mock_client_cls.assert_called_with("http://custom:9999")

    @patch.dict(os.environ, {}, clear=True)
    @patch("server.R2RClient")
    def test_client_default_url(self, mock_client_cls):
        """No env var -> _get_client() uses http://localhost:7272"""
        os.environ.pop("R2R_API_BASE", None)
        from server import _get_client
        _get_client()
        mock_client_cls.assert_called_with("http://localhost:7272")
