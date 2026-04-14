"""
Verification tests for D3 (Sourcebooks MCP Server).

Mock-based smoke/integration tests covering:
- Full lifecycle: list_books → search_lore → scoped search → get_chapter
- Edge cases: empty results, missing metadata, graceful fallbacks
- Environment variable configuration (R2R_API_BASE)
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import server  # noqa: E402
from server import search_lore, list_books, get_chapter, _get_client  # noqa: E402


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


def _make_search_result(chunks):
    """Wrap chunks in .results.chunk_search_results"""
    result = MagicMock()
    result.results = MagicMock()
    result.results.chunk_search_results = chunks
    return result


def _make_docs_response(docs):
    """Wrap docs in .results list"""
    result = MagicMock()
    result.results = docs
    return result


# ---------------------------------------------------------------------------
# TestSmokeFlow — full lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSmokeFlow:
    """End-to-end lifecycle: list_books → search_lore → scoped search → get_chapter."""

    @patch("server.R2RClient")
    async def test_lifecycle_list_search_scoped_search_chapter(self, mock_client_cls):
        client = mock_client_cls.return_value

        # -- 1. list_books: 2 books (3 docs) --
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
        # Dwarf Kingdoms has 2 chapters, Elven Lore has 1
        assert "Chapters: 2" in output
        assert "Chapters: 1" in output

        # -- 2. search_lore("dwarven customs") — 2 chunks --
        chunks = [
            _make_chunk(score=0.93, text="Dwarven customs dictate a strict hierarchy.", metadata={
                "book_title": "Dwarf Kingdoms",
                "chapter": "Chapter 5: Society",
                "page_range": "pp. 70-78",
                "content_type": "lore",
            }),
            _make_chunk(score=0.81, text="Clan elders adjudicate disputes by ancient law.", metadata={
                "book_title": "Dwarf Kingdoms",
                "chapter": "Chapter 6: Law",
                "page_range": "pp. 79-85",
                "content_type": "lore",
            }),
        ]
        client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))

        output = await search_lore(query="dwarven customs")
        assert "Dwarf Kingdoms" in output
        assert "Chapter 5" in output
        assert "pp. 70-78" in output
        assert "0.93" in output
        assert "Dwarven customs dictate" in output
        assert "Chapter 6" in output

        # -- 3. search_lore("dwarven customs", book="Dwarf Kingdoms") --
        # Same mock, but verify filter was applied
        client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))

        output = await search_lore(query="dwarven customs", book="Dwarf Kingdoms")

        # Verify the book filter was set
        call_kwargs = client.retrieval.search.call_args
        settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
        assert settings.filters["book_title"] == {"$eq": "Dwarf Kingdoms"}

        # Output still formatted correctly
        assert "Dwarf Kingdoms" in output
        assert "0.93" in output
        assert "Dwarven customs dictate" in output

        # -- 4. get_chapter("Dwarf Kingdoms", "Chapter 3") — 3 ordered chunks --
        chapter_chunks = [
            _make_chunk(text="The Deep Roads stretch beneath the mountains."),
            _make_chunk(text="Miners carved tunnels for generations."),
            _make_chunk(text="Today the roads serve as trade routes."),
        ]
        client.retrieval.search = MagicMock(return_value=_make_search_result(chapter_chunks))

        output = await get_chapter(book="Dwarf Kingdoms", chapter="Chapter 3")
        assert "The Deep Roads stretch" in output
        assert "Miners carved tunnels" in output
        assert "Today the roads serve" in output
        # Correct order
        assert output.index("Deep Roads stretch") < output.index("Miners carved")
        assert output.index("Miners carved") < output.index("Today the roads")
        # Header contains book and chapter
        assert "Dwarf Kingdoms" in output
        assert "Chapter 3" in output


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEdgeCases:
    """Edge-case coverage for empty results and missing metadata."""

    @patch("server.R2RClient")
    async def test_search_lore_zero_results(self, mock_client_cls):
        """Empty chunk list → header present, no result entries, no 'Error:'."""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([]))

        output = await search_lore(query="nonexistent topic")
        assert "Search Results" in output
        assert "Error" not in output

    @patch("server.R2RClient")
    async def test_list_books_empty(self, mock_client_cls):
        """Empty doc list → 'No books found.'."""
        client = mock_client_cls.return_value
        client.documents.list = MagicMock(return_value=_make_docs_response([]))

        output = await list_books()
        assert "No books found." in output

    @patch("server.R2RClient")
    async def test_get_chapter_not_found(self, mock_client_cls):
        """Empty chunk list → 'No content found for...'."""
        client = mock_client_cls.return_value
        client.retrieval.search = MagicMock(return_value=_make_search_result([]))

        output = await get_chapter(book="Nonexistent Book", chapter="Chapter 1")
        assert "No content found" in output

    @patch("server.R2RClient")
    async def test_search_lore_missing_metadata_fields(self, mock_client_cls):
        """Chunk with partial metadata (no page_range, no chapter) → graceful 'Unknown' fallback."""
        client = mock_client_cls.return_value
        chunk = _make_chunk(score=0.88, text="Some lore text.", metadata={
            "book_title": "Dwarf Kingdoms",
            # no chapter, no page_range
        })
        client.retrieval.search = MagicMock(return_value=_make_search_result([chunk]))

        output = await search_lore(query="test")
        assert "Unknown" in output  # fallback for missing chapter
        assert "Some lore text." in output
        assert "Error" not in output

    @patch("server.R2RClient")
    async def test_list_books_missing_metadata(self, mock_client_cls):
        """Doc with no book_title in metadata → groups under 'Unknown', doesn't crash."""
        client = mock_client_cls.return_value
        doc = _make_doc(doc_id="d1", title="Mystery", metadata={
            "system": "Generic",
            "publisher": "Indie",
            "content_type": "lore",
            # no book_title
        })
        client.documents.list = MagicMock(return_value=_make_docs_response([doc]))

        output = await list_books()
        assert "Unknown" in output
        assert "Error" not in output


# ---------------------------------------------------------------------------
# TestEnvironmentConfig
# ---------------------------------------------------------------------------


class TestEnvironmentConfig:
    """Verify _get_client reads R2R_API_BASE (not R2R_BASE_URL)."""

    @patch("server.R2RClient")
    def test_get_client_reads_R2R_API_BASE(self, mock_client_cls):
        """Set R2R_API_BASE env → client gets custom URL."""
        with patch.dict(os.environ, {"R2R_API_BASE": "http://custom-host:9999"}, clear=False):
            _get_client()
        mock_client_cls.assert_called_once_with("http://custom-host:9999")

    @patch("server.R2RClient")
    def test_get_client_default_url(self, mock_client_cls):
        """No env → http://localhost:7272."""
        env = os.environ.copy()
        env.pop("R2R_API_BASE", None)
        env.pop("R2R_BASE_URL", None)
        with patch.dict(os.environ, env, clear=True):
            _get_client()
        mock_client_cls.assert_called_once_with("http://localhost:7272")

    @patch("server.R2RClient")
    def test_old_env_var_ignored(self, mock_client_cls):
        """R2R_BASE_URL set but not R2R_API_BASE → falls back to default."""
        env = os.environ.copy()
        env.pop("R2R_API_BASE", None)
        env["R2R_BASE_URL"] = "http://old-host:1234"
        with patch.dict(os.environ, env, clear=True):
            _get_client()
        mock_client_cls.assert_called_once_with("http://localhost:7272")
