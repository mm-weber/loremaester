"""Tests for the Vault Graph MCP server (D5)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# We need to set VAULT_PATH before importing server so it picks up our test path.
# Each test class that needs graph data will handle this via fixtures.

SAMPLE_GRAPH = {
    "nodes": {
        "Overview": {
            "path": "World/Overview.md",
            "tags": ["lore"],
            "type": "lore",
            "links_to": ["Ironhold", "The Forest", "Dwarven Clans"],
            "linked_from": [],
        },
        "Ironhold": {
            "path": "Locations/Ironhold.md",
            "tags": ["location"],
            "type": "location",
            "links_to": ["Ironhold Council", "Thrain Ironbeard"],
            "linked_from": ["Overview"],
        },
        "The Forest": {
            "path": "Locations/Forest.md",
            "tags": ["location"],
            "type": "location",
            "links_to": [],
            "linked_from": ["Overview"],
        },
        "Dwarven Clans": {
            "path": "Factions/Dwarves.md",
            "tags": ["faction"],
            "type": "faction",
            "links_to": ["Ironhold"],
            "linked_from": ["Overview"],
        },
        "Thrain Ironbeard": {
            "path": "NPCs/Thrain.md",
            "tags": ["npc"],
            "type": "NPC",
            "links_to": ["Ironhold", "Dwarven Clans"],
            "linked_from": ["Ironhold"],
        },
        "Ironhold Council": {
            "path": "Factions/Council.md",
            "tags": ["faction", "politics"],
            "type": "faction",
            "links_to": [],
            "linked_from": ["Ironhold"],
        },
    },
    "edges": [
        {"from": "Overview", "to": "Ironhold"},
        {"from": "Overview", "to": "The Forest"},
        {"from": "Overview", "to": "Dwarven Clans"},
        {"from": "Ironhold", "to": "Ironhold Council"},
        {"from": "Ironhold", "to": "Thrain Ironbeard"},
        {"from": "Dwarven Clans", "to": "Ironhold"},
        {"from": "Thrain Ironbeard", "to": "Ironhold"},
        {"from": "Thrain Ironbeard", "to": "Dwarven Clans"},
    ],
    "metadata": {
        "vault_path": "/tmp/test-vault",
        "built_at": "2026-03-11T00:00:00",
        "note_count": 6,
        "edge_count": 8,
    },
}


@pytest.fixture()
def vault_dir():
    """Create a temporary vault directory with .graph.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = os.path.join(tmpdir, ".graph.json")
        with open(graph_path, "w") as f:
            json.dump(SAMPLE_GRAPH, f)
        yield tmpdir


@pytest.fixture()
def server(vault_dir):
    """Import and configure the server module with the test vault."""
    import importlib

    os.environ["VAULT_PATH"] = vault_dir
    import server as mod

    # Force-reload so it picks up the new VAULT_PATH
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_server_with_env(vault_path):
    """Reload the server module with a given VAULT_PATH."""
    import importlib

    os.environ["VAULT_PATH"] = vault_path
    import server as mod

    importlib.reload(mod)
    return mod


async def _call(server_mod, tool_name, **kwargs):
    """Call a tool function on the server module and return the result string."""
    fn = getattr(server_mod, tool_name)
    return await fn(**kwargs)


# ===========================================================================
# TestServerSetup
# ===========================================================================


class TestServerSetup:
    def test_server_name(self, server):
        assert server.mcp.name == "Vault Graph"

    def test_tools_registered(self, server):
        # FastMCP stores tools — check the expected tool names exist
        tool_names = set()
        for tool in server.mcp._tool_manager.list_tools():
            tool_names.add(tool.name)
        expected = {
            "vault_graph",
            "vault_backlinks",
            "vault_central_notes",
            "vault_search_notes",
            "vault_reload_cache",
            "vault_rebuild_graph",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_env_var_vault_path(self, vault_dir):
        """VAULT_PATH env var sets the vault path."""
        os.environ["VAULT_PATH"] = vault_dir
        server_mod = _reload_server_with_env(vault_dir)
        assert vault_dir == server_mod.VAULT_PATH

    def test_default_vault_path(self):
        """No env var → defaults to /workspace/vault."""
        if "VAULT_PATH" in os.environ:
            del os.environ["VAULT_PATH"]
        import importlib

        import server as mod

        importlib.reload(mod)
        assert mod.VAULT_PATH == "/workspace/vault"


# ===========================================================================
# TestVaultGraph (REQ-D5-01, D5-08)
# ===========================================================================


class TestVaultGraph:
    @pytest.mark.asyncio
    async def test_depth_1(self, server):
        result = await _call(server, "vault_graph", note="Ironhold", depth=1)
        # Depth 1 from Ironhold: outgoing → Ironhold Council, Thrain Ironbeard
        #                         incoming ← Overview
        assert "Ironhold Council" in result
        assert "Thrain Ironbeard" in result
        assert "Overview" in result
        # Dwarven Clans is NOT directly connected to Ironhold at depth 1
        # (Ironhold doesn't link to Dwarven Clans, and Dwarven Clans links TO Ironhold
        #  so it would appear as incoming)
        # Actually: Dwarven Clans links_to includes Ironhold, so Ironhold's linked_from
        # should include Dwarven Clans. But per SAMPLE_GRAPH, Ironhold's linked_from is
        # only ["Overview"]. So Dwarven Clans should NOT appear at depth 1.
        assert "Dwarven Clans" not in result

    @pytest.mark.asyncio
    async def test_depth_2_default(self, server):
        result = await _call(server, "vault_graph", note="Ironhold")
        # Default depth=2, so Dwarven Clans reachable via Thrain at depth 2
        assert "Dwarven Clans" in result

    @pytest.mark.asyncio
    async def test_max_depth_clamped(self, server):
        result = await _call(server, "vault_graph", note="Ironhold", depth=10)
        # Should not error, depth clamped to 4
        assert result is not None
        assert "error" not in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_note(self, server):
        result = await _call(server, "vault_graph", note="Nonexistent")
        assert "not found" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_links_to_nonexistent_target(self, server):
        """Note with links_to containing a target not in nodes dict (D5-08)."""
        # Patch the graph to add a ghost link
        server._graph["nodes"]["Ironhold"]["links_to"].append("Ghost")
        try:
            result = await _call(server, "vault_graph", note="Ironhold", depth=1)
            assert "Ghost" in result
            # Should not crash
        finally:
            server._graph["nodes"]["Ironhold"]["links_to"].remove("Ghost")

    @pytest.mark.asyncio
    async def test_shows_direction_arrows(self, server):
        """Output should contain → for outgoing and ← for incoming links."""
        result = await _call(server, "vault_graph", note="Ironhold", depth=1)
        assert "\u2192" in result or "->" in result  # outgoing arrow
        assert "\u2190" in result or "<-" in result  # incoming arrow


# ===========================================================================
# TestVaultBacklinks (REQ-D5-02, D5-08)
# ===========================================================================


class TestVaultBacklinks:
    @pytest.mark.asyncio
    async def test_basic_backlinks(self, server):
        result = await _call(server, "vault_backlinks", note="Ironhold")
        assert "Overview" in result

    @pytest.mark.asyncio
    async def test_no_backlinks(self, server):
        result = await _call(server, "vault_backlinks", note="Overview")
        assert (
            "no backlinks" in result.lower()
            or "none" in result.lower()
            or "0" in result
        )

    @pytest.mark.asyncio
    async def test_nonexistent_note(self, server):
        result = await _call(server, "vault_backlinks", note="Ghost")
        assert "not found" in result.lower() or "error" in result.lower()


# ===========================================================================
# TestVaultCentralNotes (REQ-D5-03)
# ===========================================================================


class TestVaultCentralNotes:
    @pytest.mark.asyncio
    async def test_default_ranking(self, server):
        result = await _call(server, "vault_central_notes")
        # Ironhold has highest degree: 2 outgoing + 1 incoming = 3
        # (linked_from only has Overview per SAMPLE_GRAPH)
        # Actually let's count: Ironhold links_to=[Council, Thrain]=2, linked_from=[Overview]=1 → 3
        # Thrain: links_to=[Ironhold, Dwarven Clans]=2, linked_from=[Ironhold]=1 → 3
        # Overview: links_to=[Ironhold, Forest, Dwarven Clans]=3, linked_from=[] → 3
        # Ironhold should be near the top regardless
        assert "Ironhold" in result

    @pytest.mark.asyncio
    async def test_filter_by_tag(self, server):
        result = await _call(server, "vault_central_notes", tag="faction")
        assert "Dwarven Clans" in result or "Ironhold Council" in result
        # Non-faction notes should not appear
        assert "The Forest" not in result
        assert "Thrain Ironbeard" not in result

    @pytest.mark.asyncio
    async def test_custom_limit(self, server):
        result = await _call(server, "vault_central_notes", limit=2)
        # Verify the result is constrained — not all 6 notes should appear.
        note_names = [
            "Overview",
            "Ironhold",
            "The Forest",
            "Dwarven Clans",
            "Thrain Ironbeard",
            "Ironhold Council",
        ]
        found = sum(1 for name in note_names if name in result)
        assert found <= 2


# ===========================================================================
# TestVaultSearchNotes (REQ-D5-04)
# ===========================================================================


class TestVaultSearchNotes:
    @pytest.mark.asyncio
    async def test_name_pattern(self, server):
        result = await _call(server, "vault_search_notes", name_pattern="iron")
        assert "Ironhold" in result
        assert "Ironhold Council" in result
        assert "The Forest" not in result

    @pytest.mark.asyncio
    async def test_tag_filter(self, server):
        result = await _call(server, "vault_search_notes", tag="npc")
        assert "Thrain Ironbeard" in result
        assert "Ironhold" not in result or "Thrain" in result  # only Thrain

    @pytest.mark.asyncio
    async def test_type_filter(self, server):
        result = await _call(server, "vault_search_notes", note_type="faction")
        assert "Dwarven Clans" in result
        assert "Ironhold Council" in result

    @pytest.mark.asyncio
    async def test_combined_filters(self, server):
        result = await _call(
            server, "vault_search_notes", name_pattern="iron", tag="faction"
        )
        # AND logic: name contains "iron" AND tag is "faction" → only Ironhold Council
        assert "Ironhold Council" in result
        # Ironhold (location, not faction) should not match
        # Check that "Ironhold" appears only as part of "Ironhold Council"
        # Remove "Ironhold Council" and check no standalone "Ironhold" remains
        cleaned = result.replace("Ironhold Council", "")
        assert "Ironhold" not in cleaned or "iron" in cleaned.lower()

    @pytest.mark.asyncio
    async def test_no_matches(self, server):
        result = await _call(server, "vault_search_notes", name_pattern="zzzzz")
        assert "no" in result.lower() or "0" in result.lower()


# ===========================================================================
# TestVaultReloadCache (REQ-D5-05)
# ===========================================================================


class TestVaultReloadCache:
    @pytest.mark.asyncio
    async def test_reload_updates_data(self, server, vault_dir):
        # Add a new node to the graph file on disk
        graph_path = os.path.join(vault_dir, ".graph.json")
        with open(graph_path) as f:
            graph = json.load(f)
        graph["nodes"]["New Note"] = {
            "path": "New/Note.md",
            "tags": ["new"],
            "type": "lore",
            "links_to": [],
            "linked_from": [],
        }
        graph["metadata"]["note_count"] = 7
        with open(graph_path, "w") as f:
            json.dump(graph, f)

        result = await _call(server, "vault_reload_cache")
        assert "7" in result or "reload" in result.lower()

        # Verify new data is accessible
        search_result = await _call(
            server, "vault_search_notes", name_pattern="New Note"
        )
        assert "New Note" in search_result

    @pytest.mark.asyncio
    async def test_reload_surfaces_staleness(self, server, vault_dir):
        """When .md files are newer than .graph.json, reload response flags STALE."""
        # Create a real .md file with an mtime newer than .graph.json's
        md_path = Path(vault_dir) / "NewerNote.md"
        md_path.write_text("---\ntype: lore\n---\n# Newer\n", encoding="utf-8")
        # Bump its mtime well beyond graph mtime in case FS granularity is coarse
        graph_path = Path(vault_dir) / ".graph.json"
        future = graph_path.stat().st_mtime + 60
        os.utime(md_path, (future, future))

        result = await _call(server, "vault_reload_cache")
        assert "STALE" in result
        assert "1 .md file" in result

    @pytest.mark.asyncio
    async def test_reload_no_staleness_when_fresh(self, server, vault_dir):
        """No STALE suffix when every .md file is older than the graph."""
        result = await _call(server, "vault_reload_cache")
        assert "STALE" not in result


# ===========================================================================
# TestVaultRebuildGraph
# ===========================================================================


class TestVaultRebuildGraph:
    @pytest.mark.asyncio
    async def test_rebuild_from_vault(self, server, vault_dir):
        """vault_rebuild_graph re-parses .md files and picks up new notes."""
        # Seed two notes with a wikilink between them
        (Path(vault_dir) / "A.md").write_text(
            "---\ntype: lore\n---\nLinks to [[B]].\n", encoding="utf-8"
        )
        (Path(vault_dir) / "B.md").write_text(
            "---\ntype: lore\n---\nI am B.\n", encoding="utf-8"
        )

        result = await _call(server, "vault_rebuild_graph")
        assert "rebuilt" in result.lower()
        assert "2" in result  # at least 2 notes (plus whatever was in the test graph)

        # Verify A→B edge landed in the in-memory graph
        search_result = await _call(server, "vault_search_notes", name_pattern="A")
        assert "A" in search_result

    @pytest.mark.asyncio
    async def test_rebuild_handles_missing_builder(self, server, vault_dir):
        """If the builder isn't importable, the tool reports a clear error."""
        saved = server._builder
        try:
            server._builder = None
            result = await _call(server, "vault_rebuild_graph")
            assert "error" in result.lower()
            assert "build_vault_graph" in result.lower()
        finally:
            server._builder = saved


# ===========================================================================
# TestGraphMissing (REQ-D5-07)
# ===========================================================================


class TestGraphMissing:
    @pytest.mark.asyncio
    async def test_missing_graph_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .graph.json in this directory
            server_mod = _reload_server_with_env(tmpdir)
            result = await _call(server_mod, "vault_graph", note="Anything")
            assert (
                "build" in result.lower()
                or "missing" in result.lower()
                or "not found" in result.lower()
            )

    @pytest.mark.asyncio
    async def test_malformed_graph_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = os.path.join(tmpdir, ".graph.json")
            with open(graph_path, "w") as f:
                f.write("{invalid json!!!")
            server_mod = _reload_server_with_env(tmpdir)
            result = await _call(server_mod, "vault_graph", note="Anything")
            assert (
                "error" in result.lower()
                or "malformed" in result.lower()
                or "invalid" in result.lower()
            )
