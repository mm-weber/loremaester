"""Tests for the vault graph builder (scripts/build_vault_graph.py)."""

import json
import os
import sys
from pathlib import Path

import pytest
from build_vault_graph import build_graph, extract_wikilinks, main, parse_frontmatter

# Smoke-test target for TestRealVault. Defaults to the bundled example vault;
# set TEST_VAULT to point the smoke tests at your own vault instead.
REAL_VAULT = os.environ.get(
    "TEST_VAULT",
    str(Path(__file__).resolve().parent.parent / "examples" / "ttrpg" / "GM-Vault"),
)


def _create_vault(tmp_path, files: dict) -> Path:
    """Create a temp vault with given files. Keys are relative paths, values are content."""
    for rel_path, content in files.items():
        p = tmp_path / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Test Class 1: TestExtractWikilinks
# ---------------------------------------------------------------------------


class TestExtractWikilinks:
    def test_basic_wikilink(self):
        assert extract_wikilinks("Visit [[Ironhold]] now") == ["Ironhold"]

    def test_aliased_wikilink(self):
        assert extract_wikilinks("The [[Ironhold|great city]]") == ["Ironhold"]

    def test_multiple_wikilinks(self):
        assert extract_wikilinks("[[A]] and [[B]] and [[C]]") == ["A", "B", "C"]

    def test_no_wikilinks(self):
        assert extract_wikilinks("Plain text") == []

    def test_wikilink_with_spaces(self):
        assert extract_wikilinks("[[Iron Mountains]]") == ["Iron Mountains"]

    def test_anchor_link(self):
        assert extract_wikilinks("[[Session 1#Strong start]]") == ["Session 1"]

    def test_anchor_and_alias(self):
        assert extract_wikilinks("[[Land der Tiere#Brux|Brux]]") == ["Land der Tiere"]


# ---------------------------------------------------------------------------
# Test Class 2: TestParseFrontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        content = "---\ntype: location\ntags: [location, dwarf]\n---\n# Content"
        result = parse_frontmatter(content)
        assert result["type"] == "location"
        assert result["tags"] == ["location", "dwarf"]

    def test_no_frontmatter(self):
        result = parse_frontmatter("# Just a heading")
        assert result == {"type": None, "tags": []}

    def test_string_tags(self):
        content = "---\ntags: lore\n---"
        result = parse_frontmatter(content)
        assert result["tags"] == ["lore"]

    def test_broken_yaml(self):
        content = "---\n: invalid: yaml:\n---"
        result = parse_frontmatter(content)
        assert result == {"type": None, "tags": []}

    def test_empty_frontmatter(self):
        content = "---\n---\n# Content"
        result = parse_frontmatter(content)
        assert result == {"type": None, "tags": []}


# ---------------------------------------------------------------------------
# Test Class 3: TestBuildGraph
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_basic_graph(self, tmp_path):
        vault = _create_vault(
            tmp_path,
            {
                "NoteA.md": "Hello [[NoteB]]",
                "NoteB.md": "Back to [[NoteA]]",
            },
        )
        graph = build_graph(str(vault))
        assert "NoteA" in graph["nodes"]
        assert "NoteB" in graph["nodes"]
        assert "NoteB" in graph["nodes"]["NoteA"]["links_to"]
        assert "NoteB" in graph["nodes"]["NoteA"]["linked_from"]
        assert len(graph["edges"]) == 2

    def test_recursive_md_discovery(self, tmp_path):
        vault = _create_vault(
            tmp_path,
            {
                "World/Overview.md": "See [[Hero]]",
                "NPCs/Hero.md": "Lives in [[Overview]]",
            },
        )
        graph = build_graph(str(vault))
        assert "Overview" in graph["nodes"]
        assert "Hero" in graph["nodes"]

    def test_nonexistent_link_target(self, tmp_path):
        vault = _create_vault(
            tmp_path,
            {
                "NoteA.md": "Link to [[Ghost]]",
            },
        )
        graph = build_graph(str(vault))
        assert "Ghost" in graph["nodes"]["NoteA"]["links_to"]
        assert "Ghost" not in graph["nodes"]

    def test_metadata_fields(self, tmp_path):
        vault = _create_vault(
            tmp_path,
            {
                "NoteA.md": "[[NoteB]]",
                "NoteB.md": "Hello",
            },
        )
        graph = build_graph(str(vault))
        meta = graph["metadata"]
        assert meta["note_count"] == 2
        assert meta["edge_count"] == 1
        # built_at should be parseable ISO format
        from datetime import datetime

        datetime.fromisoformat(meta["built_at"])
        assert isinstance(meta["vault_path"], str)

    def test_frontmatter_in_nodes(self, tmp_path):
        vault = _create_vault(
            tmp_path,
            {
                "Ironhold.md": "---\ntype: location\ntags: [city]\n---\n# Ironhold",
            },
        )
        graph = build_graph(str(vault))
        node = graph["nodes"]["Ironhold"]
        assert node["type"] == "location"
        assert node["tags"] == ["city"]

    def test_non_utf8_file(self, tmp_path):
        p = tmp_path / "Brux.md"
        p.write_bytes(b"Br\xfcx the \xd6rc")
        graph = build_graph(str(tmp_path))
        assert "Brux" in graph["nodes"]

    def test_empty_vault(self, tmp_path):
        graph = build_graph(str(tmp_path))
        assert graph["nodes"] == {}
        assert graph["edges"] == []
        assert graph["metadata"]["note_count"] == 0
        assert graph["metadata"]["edge_count"] == 0

    def test_node_path_is_relative(self, tmp_path):
        vault = _create_vault(
            tmp_path,
            {
                "World/Overview.md": "# Overview",
            },
        )
        graph = build_graph(str(vault))
        assert graph["nodes"]["Overview"]["path"] == "World/Overview.md"


# ---------------------------------------------------------------------------
# Test Class 4: TestCLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_creates_graph_json(self, tmp_path, monkeypatch):
        vault = _create_vault(tmp_path, {"Note.md": "Hello"})
        monkeypatch.setattr(sys, "argv", ["build_vault_graph.py", str(vault)])
        main()
        assert (vault / ".graph.json").exists()

    def test_cli_output_is_valid_json(self, tmp_path, monkeypatch):
        vault = _create_vault(tmp_path, {"Note.md": "Hello"})
        monkeypatch.setattr(sys, "argv", ["build_vault_graph.py", str(vault)])
        main()
        graph_file = vault / ".graph.json"
        assert graph_file.exists(), ".graph.json was not created by main()"
        with open(graph_file) as f:
            data = json.load(f)
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data

    def test_cli_no_args(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["build_vault_graph.py"])
        with pytest.raises(SystemExit):
            main()


# ---------------------------------------------------------------------------
# Test Class 5: TestRealVault
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not Path(REAL_VAULT).exists(),
    reason=f"Vault not found at {REAL_VAULT}; set TEST_VAULT to override",
)
class TestRealVault:
    """Structural smoke tests against a real on-disk vault.

    Defaults to the bundled example vault; point TEST_VAULT at your own vault to
    validate it. Assertions are vault-agnostic (shape + invariants), so they hold
    for any vault, whether populated or empty.
    """

    def test_real_vault_parses(self):
        graph = build_graph(REAL_VAULT)
        assert isinstance(graph, dict)
        assert "nodes" in graph
        assert "edges" in graph
        assert "metadata" in graph

    def test_real_vault_note_count_is_nonnegative_int(self):
        graph = build_graph(REAL_VAULT)
        assert "note_count" in graph["metadata"], "metadata missing 'note_count'"
        assert isinstance(graph["metadata"]["note_count"], int)
        assert graph["metadata"]["note_count"] >= 0

    def test_real_vault_anchor_links_stripped(self):
        graph = build_graph(REAL_VAULT)
        for name in graph["nodes"]:
            assert "#" not in name, f"Node name contains #: {name}"
