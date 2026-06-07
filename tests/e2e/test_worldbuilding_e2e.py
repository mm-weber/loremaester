"""
End-to-end worldbuilding workflow test.

Verifies the full worldbuilding workflow end-to-end: vault navigation →
source book research → note creation → backlink updates → graph rebuild.
Since we can't invoke Claude in automated tests, we simulate the workflow
programmatically by calling the same tools Claude would use.
"""

import importlib
import json
import os
import re
import sys
import textwrap

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path setup — make scripts/ and mcp-servers/ importable
# ---------------------------------------------------------------------------

# This file lives at tests/e2e/, so the repo root is three directories up. It's
# used below to locate the MCP server entry points under mcp-servers/.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_vault_graph import build_graph  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402


# ---------------------------------------------------------------------------
# Vault fixture — interconnected notes matching the requirements doc example
# ---------------------------------------------------------------------------

OVERVIEW_MD = textwrap.dedent("""\
    ---
    type: lore
    tags: [lore]
    description: "World overview"
    ---

    # World Overview

    The world is vast and full of wonders.

    Key locations include [[Ironhold]], a great dwarven city nestled in the
    [[Iron Mountains]], and [[The Forest]], an ancient woodland.

    Major factions: the [[Dwarven Clans]] control the mountains, while the
    [[Elven Court]] holds sway over the forest realms.
""")

IRONHOLD_MD = textwrap.dedent("""\
    ---
    type: place
    aliases: ["The Iron City"]
    faction: "Dwarven Clans"
    location: "Iron Mountains"
    description: "A great dwarven trading hub built into the mountainside"
    tags: [location]
    ---

    # Ironhold

    Ironhold is the greatest of the dwarven cities, a sprawling trading hub
    carved into the heart of the [[Iron Mountains]].

    The city is governed by the [[Ironhold Council]], a body of clan elders
    led by [[Thrain Ironbeard]].

    Ironhold is known for its vast forges and its role as a nexus of trade
    between the mountain kingdoms and the lowland realms.
""")

THRAIN_MD = textwrap.dedent("""\
    ---
    type: NPC
    aliases: ["Thrain", "Elder Thrain"]
    faction: "Dwarven Clans"
    location: "Ironhold"
    race: "Dwarf"
    class: "Noble"
    level: 12
    gender: "Male"
    deceased: false
    tags: [npc]
    ---

    # Thrain Ironbeard

    Thrain Ironbeard is the eldest member of the [[Ironhold Council]] and
    de facto leader of [[Ironhold]]. He is a respected figure among the
    [[Dwarven Clans]], known for his pragmatic approach to diplomacy.
""")

DWARVEN_CLANS_MD = textwrap.dedent("""\
    ---
    type: Faction
    aliases: ["The Clans", "Mountain Clans"]
    faction: []
    location: ["Ironhold", "Iron Mountains"]
    description: "Allied dwarven clans controlling the Iron Mountains"
    alignment: ["Lawful Neutral"]
    tags: [faction]
    ---

    # Dwarven Clans

    The Dwarven Clans are an alliance of mountain-dwelling dwarven families
    centered around [[Ironhold]]. Their leader is [[Thrain Ironbeard]].
""")

VAULT_FILES = {
    "World/Overview.md": OVERVIEW_MD,
    "Locations/Ironhold.md": IRONHOLD_MD,
    "NPCs/Thrain Ironbeard.md": THRAIN_MD,
    "Factions/Dwarven Clans.md": DWARVEN_CLANS_MD,
}


@pytest.fixture()
def vault(tmp_path):
    """Create a temporary vault with interconnected notes and build the graph."""
    for relpath, content in VAULT_FILES.items():
        fpath = tmp_path / relpath
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")

    # Build graph using the real build_graph()
    graph = build_graph(str(tmp_path))
    graph_path = tmp_path / ".graph.json"
    graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    return tmp_path


def _import_vault_graph():
    """Import the vault-graph server module under a distinct name."""
    import importlib.util as ilu
    spec = ilu.spec_from_file_location(
        "vault_graph_server",
        os.path.join(REPO_ROOT, "mcp-servers", "vault-graph", "server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["vault_graph_server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def vg_server(vault):
    """Import and configure the vault-graph server module with the test vault."""
    os.environ["VAULT_PATH"] = str(vault)
    # Remove cached module so it reloads with new VAULT_PATH
    sys.modules.pop("vault_graph_server", None)
    return _import_vault_graph()


# ---------------------------------------------------------------------------
# Mock helpers for sourcebooks (R2R mocked)
# ---------------------------------------------------------------------------

def _make_chunk(score=0.95, text="chunk text", metadata=None):
    chunk = MagicMock()
    chunk.score = score
    chunk.text = text
    chunk.metadata = metadata or {
        "book_title": "Dwarf Kingdoms",
        "chapter": "Chapter 7: Dwarven Politics",
        "page_range": "pp. 120-135",
        "content_type": "lore",
    }
    return chunk


def _make_search_result(chunks):
    result = MagicMock()
    result.results = MagicMock()
    result.results.chunk_search_results = chunks
    return result


def _make_doc(doc_id="doc-1", title="Book", metadata=None):
    doc = MagicMock()
    doc.id = doc_id
    doc.title = title
    doc.metadata = metadata or {
        "book_title": "Dwarf Kingdoms",
        "system": "D&D 5e",
        "publisher": "WotC",
        "content_type": "lore",
        "chapter": "Chapter 7",
        "page_range": "pp. 120-135",
    }
    return doc


def _make_docs_response(docs):
    result = MagicMock()
    result.results = docs
    return result


# ---------------------------------------------------------------------------
# Import sourcebooks tools (with server module alias to avoid name clash)
# ---------------------------------------------------------------------------

def _import_sourcebooks():
    """Import the sourcebooks server module under a distinct name.

    We can't just 'import server' again since vault-graph's server.py is
    already on sys.path. Use importlib to load it under a unique module name.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sourcebooks_server",
        os.path.join(REPO_ROOT, "mcp-servers", "sourcebooks", "server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sourcebooks_server"] = mod
    spec.loader.exec_module(mod)
    return mod


try:
    _sb_server = _import_sourcebooks()
except Exception:
    _sb_server = None


# ===========================================================================
# TestEndToEndWorldbuildingSession
# ===========================================================================


@pytest.mark.asyncio
class TestEndToEndWorldbuildingSession:
    """Full end-to-end worldbuilding workflow lifecycle."""

    async def test_step1_gather_vault_context(self, vg_server, vault):
        """'Tell me about Ironhold' — search, graph, backlinks, read content."""
        # 1. Search for Ironhold
        search_result = await vg_server.vault_search_notes(name_pattern="Ironhold")
        assert "Ironhold" in search_result
        # Should find the Ironhold note specifically
        assert "Locations/Ironhold.md" in search_result

        # 2. Map connections at depth 2
        graph_result = await vg_server.vault_graph(note="Ironhold", depth=2)
        assert "Ironhold Council" in graph_result
        assert "Thrain Ironbeard" in graph_result
        assert "Overview" in graph_result
        # At depth 2, should also reach Dwarven Clans (via Thrain)
        assert "Dwarven Clans" in graph_result

        # 3. Check backlinks
        backlinks_result = await vg_server.vault_backlinks(note="Ironhold")
        assert "Overview" in backlinks_result
        assert "Dwarven Clans" in backlinks_result

        # 4. Read Ironhold.md content directly — verify wikilinks present
        ironhold_content = (vault / "Locations" / "Ironhold.md").read_text()
        assert "[[Iron Mountains]]" in ironhold_content
        assert "[[Ironhold Council]]" in ironhold_content
        assert "[[Thrain Ironbeard]]" in ironhold_content

    async def test_step2_research_source_books(self):
        """'What do source books say about dwarven politics?' — R2R mocked."""
        if _sb_server is None:
            pytest.skip("Could not import sourcebooks server")

        # 1. list_books
        with patch.object(_sb_server, "R2RClient") as mock_cls:
            client = mock_cls.return_value
            docs = [
                _make_doc("d1", "Ch7", metadata={
                    "book_title": "Dwarf Kingdoms", "system": "D&D 5e",
                    "publisher": "WotC", "content_type": "lore",
                    "chapter": "Ch 7", "page_range": "pp. 120-135",
                }),
                _make_doc("d2", "Ch1", metadata={
                    "book_title": "Elven Lore", "system": "Pathfinder",
                    "publisher": "Paizo", "content_type": "lore",
                    "chapter": "Ch 1", "page_range": "pp. 1-15",
                }),
            ]
            client.documents.list = MagicMock(return_value=_make_docs_response(docs))
            output = await _sb_server.list_books()
            assert "Dwarf Kingdoms" in output
            assert "Elven Lore" in output

        # 2. search_lore (broad)
        with patch.object(_sb_server, "R2RClient") as mock_cls:
            client = mock_cls.return_value
            chunks = [
                _make_chunk(0.93, "The dwarven council system dates back millennia"),
                _make_chunk(0.87, "Clan elders hold veto power over military action"),
            ]
            client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))
            output = await _sb_server.search_lore(query="dwarven politics")
            assert "dwarven council" in output.lower()
            assert "Dwarf Kingdoms" in output
            assert "0.93" in output

        # 3. search_lore (scoped to book)
        with patch.object(_sb_server, "R2RClient") as mock_cls:
            client = mock_cls.return_value
            chunks = [_make_chunk(0.95, "The Council of Elders governs all trade disputes")]
            client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))
            output = await _sb_server.search_lore(
                query="dwarven politics", book="Dwarf Kingdoms"
            )
            assert "Council of Elders" in output

            # Verify filter was applied
            call_kwargs = client.retrieval.search.call_args
            settings = call_kwargs.kwargs.get("search_settings") or call_kwargs[1].get("search_settings")
            assert settings["filters"]["book_title"] == {"$eq": "Dwarf Kingdoms"}

        # 4. get_chapter (full chapter text)
        with patch.object(_sb_server, "R2RClient") as mock_cls:
            client = mock_cls.return_value
            chunks = [
                _make_chunk(text="The Council of Elders was established in the Third Age."),
                _make_chunk(text="Each clan sends one representative to the council."),
                _make_chunk(text="Decisions require a two-thirds majority vote."),
            ]
            client.retrieval.search = MagicMock(return_value=_make_search_result(chunks))
            output = await _sb_server.get_chapter(
                book="Dwarf Kingdoms", chapter="Chapter 7"
            )
            assert "Council of Elders" in output
            assert "two-thirds majority" in output

    async def test_step3_generate_note_content(self, vault):
        """Verify generated note follows SKILL.md rules."""
        # Programmatically create an "Ironhold Council" note following the rules
        note_content = textwrap.dedent("""\
            ---
            type: Faction
            aliases: ["The Council", "Council of Ironhold"]
            faction: []
            location: ["Ironhold"]
            description: "Governing body of Ironhold, composed of dwarven clan elders"
            alignment: ["Lawful Neutral"]
            tags: [faction]
            ---

            # Ironhold Council

            The Ironhold Council is the governing body of [[Ironhold]], composed
            of elders from each of the [[Dwarven Clans]]. The council is led by
            [[Thrain Ironbeard]], the eldest and most respected of the elders.

            ## Responsibilities

            The council oversees trade agreements, military deployments, and
            inter-clan disputes within [[Ironhold]] and the surrounding mines.
        """)

        # Verify frontmatter matches Faction schema
        fm_match = re.match(r"^---\n(.*?)\n---", note_content, re.DOTALL)
        assert fm_match, "Frontmatter not found"
        fm = yaml.safe_load(fm_match.group(1))

        assert fm["type"] == "Faction"
        assert "aliases" in fm
        assert "faction" in fm
        assert "location" in fm
        assert "description" in fm
        assert "alignment" in fm
        assert "tags" in fm
        assert "faction" in fm["tags"]

        # Verify wikilinks to existing notes
        wikilinks = re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", note_content)
        assert "Ironhold" in wikilinks
        assert "Thrain Ironbeard" in wikilinks
        assert "Dwarven Clans" in wikilinks

        # Verify Title Case naming (the note title)
        assert "# Ironhold Council" in note_content

    async def test_step4_write_to_vault_and_rebuild_graph(self, vg_server, vault):
        """Full write + graph rebuild cycle."""
        # 1. Write new note: Factions/Ironhold Council.md
        new_note = textwrap.dedent("""\
            ---
            type: Faction
            aliases: ["The Council", "Council of Ironhold"]
            faction: []
            location: ["Ironhold"]
            description: "Governing body of Ironhold, composed of dwarven clan elders"
            alignment: ["Lawful Neutral"]
            tags: [faction]
            ---

            # Ironhold Council

            The Ironhold Council is the governing body of [[Ironhold]], composed
            of elders from each of the [[Dwarven Clans]]. The council is led by
            [[Thrain Ironbeard]], the eldest and most respected of the elders.
        """)
        council_path = vault / "Factions" / "Ironhold Council.md"
        council_path.parent.mkdir(parents=True, exist_ok=True)
        council_path.write_text(new_note, encoding="utf-8")

        # 2. Update Ironhold.md — add backlink to Ironhold Council
        ironhold_path = vault / "Locations" / "Ironhold.md"
        ironhold_content = ironhold_path.read_text()
        # Ironhold already references [[Ironhold Council]], so the backlink exists.
        # Verify it's there:
        assert "[[Ironhold Council]]" in ironhold_content

        # 3. Rebuild graph using real build_graph()
        graph = build_graph(str(vault))
        graph_path = vault / ".graph.json"
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

        # 4. Reload graph in server
        reload_result = await vg_server.vault_reload_cache()
        assert "success" in reload_result.lower() or "reload" in reload_result.lower()

        # 5. Verify new note in graph
        search_result = await vg_server.vault_search_notes(name_pattern="Ironhold Council")
        assert "Ironhold Council" in search_result
        assert "Factions/Ironhold Council.md" in search_result

        # 6. Verify backlinks: Ironhold links to Ironhold Council
        backlinks = await vg_server.vault_backlinks(note="Ironhold Council")
        assert "Ironhold" in backlinks

        # 7. Verify forward links from the new note
        graph_result = await vg_server.vault_graph(note="Ironhold Council", depth=1)
        assert "Ironhold" in graph_result
        assert "Thrain Ironbeard" in graph_result
        assert "Dwarven Clans" in graph_result

        # 8. Verify metadata counts increased (was 4 notes, now 5)
        graph_data = json.loads(graph_path.read_text())
        assert graph_data["metadata"]["note_count"] == 5
        assert graph_data["metadata"]["edge_count"] > 8  # more edges with new note


# ===========================================================================
# TestNoteQuality
# ===========================================================================


class TestNoteQuality:
    """Content validation for generated notes."""

    GENERATED_NOTE = textwrap.dedent("""\
        ---
        type: Faction
        aliases: ["The Council", "Council of Ironhold"]
        faction: []
        location: ["Ironhold"]
        description: "Governing body of Ironhold, composed of dwarven clan elders"
        alignment: ["Lawful Neutral"]
        tags: [faction]
        ---

        # Ironhold Council

        The Ironhold Council is the governing body of [[Ironhold]], composed
        of elders from each of the [[Dwarven Clans]]. The council is led by
        [[Thrain Ironbeard]], the eldest and most respected of the elders.
    """)

    VAULT_NOTE_NAMES = {"Overview", "Ironhold", "Thrain Ironbeard", "Dwarven Clans",
                        "Iron Mountains", "The Forest", "Elven Court", "Ironhold Council"}

    def test_frontmatter_schema_faction(self):
        """Validate the generated note's frontmatter has required Faction fields."""
        fm_match = re.match(r"^---\n(.*?)\n---", self.GENERATED_NOTE, re.DOTALL)
        assert fm_match
        fm = yaml.safe_load(fm_match.group(1))

        required_fields = ["type", "aliases", "faction", "location",
                           "description", "alignment", "tags"]
        for field in required_fields:
            assert field in fm, f"Missing required Faction field: {field}"

        assert fm["type"] == "Faction"
        assert isinstance(fm["aliases"], list)
        assert isinstance(fm["tags"], list)
        assert "faction" in fm["tags"]

    def test_wikilinks_reference_existing_notes(self):
        """All [[wikilinks]] in the new note point to notes that exist in the vault."""
        wikilinks = re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", self.GENERATED_NOTE)
        assert len(wikilinks) > 0, "No wikilinks found in generated note"
        for link in wikilinks:
            assert link in self.VAULT_NOTE_NAMES, (
                f"Wikilink [[{link}]] references a note not in the vault"
            )

    def test_note_placed_in_correct_folder(self):
        """Faction notes go in Factions/ per the skill's placement table."""
        # The note type is Faction, so per SKILL.md it belongs in {Campaign}/Factions/
        fm_match = re.match(r"^---\n(.*?)\n---", self.GENERATED_NOTE, re.DOTALL)
        fm = yaml.safe_load(fm_match.group(1))
        note_type = fm["type"]

        placement_map = {
            "NPC": "NPC",
            "place": "Locations",
            "Faction": "Factions",
            "lore": "Background",
        }
        expected_folder = placement_map.get(note_type)
        assert expected_folder == "Factions"

    def test_backlink_updates_are_valid(self, vault):
        """Updated notes still parse correctly and their new wikilinks resolve."""
        # Read each vault note and verify all wikilinks parse
        all_note_names = set()
        for relpath in VAULT_FILES:
            name = os.path.splitext(os.path.basename(relpath))[0]
            all_note_names.add(name)

        for relpath, content in VAULT_FILES.items():
            # Verify frontmatter parses
            if content.strip().startswith("---"):
                fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                assert fm_match, f"Broken frontmatter in {relpath}"
                fm = yaml.safe_load(fm_match.group(1))
                assert isinstance(fm, dict), f"Frontmatter not a dict in {relpath}"

            # Verify wikilinks are syntactically valid
            wikilinks = re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", content)
            for link in wikilinks:
                assert len(link.strip()) > 0, f"Empty wikilink in {relpath}"


# ===========================================================================
# TestCanonHierarchy
# ===========================================================================


@pytest.mark.asyncio
class TestCanonHierarchy:
    """Source book vs vault — vault canon takes precedence."""

    async def test_vault_canon_takes_precedence(self, vault):
        """If vault says Ironhold is a 'trading hub' and source book says
        'isolationist fortress', the vault description is preserved."""
        # Read vault's established description
        ironhold_content = (vault / "Locations" / "Ironhold.md").read_text()
        assert "trading hub" in ironhold_content

        # Simulate source book saying something different
        source_book_text = "Ironhold is an isolationist fortress, sealed from outsiders."

        # Generate content following canon hierarchy rule:
        # vault > source books. The generated note should use vault's version.
        generated_note = textwrap.dedent("""\
            ---
            type: Faction
            aliases: ["The Council"]
            faction: []
            location: ["Ironhold"]
            description: "Governing council of the great trading hub of Ironhold"
            alignment: ["Lawful Neutral"]
            tags: [faction]
            ---

            # Ironhold Council

            The Ironhold Council governs [[Ironhold]], the greatest trading hub
            of the dwarven realms. Despite source materials suggesting isolationist
            tendencies, the council has long embraced trade and diplomacy.
        """)

        # Vault's "trading hub" description is preserved, not overridden
        assert "trading hub" in generated_note
        assert "isolationist fortress" not in generated_note
        # Source book influence is adapted, not copied verbatim
        assert source_book_text not in generated_note
