"""Tests for the vault-graph read tools and vault_mentions.

Spec: specs/v0.2/surgical-search.md.
"""

import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load_server():
    """Load this folder's server.py under its own name (sourcebooks has one too)."""
    spec = importlib.util.spec_from_file_location(
        "vault_graph_server", HERE / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server()


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("VAULT_SKIP_FOLDERS", raising=False)
    monkeypatch.delenv("VAULT_NAME_ENDINGS", raising=False)
    return tmp_path


def _write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


async def test_r69_small_note_comes_back_whole(vault):
    _write(vault, "NPCs/Mira.md", "---\ntype: npc\n---\nMira forges blades.\n")
    result = await server.vault_read_note("Mira")
    assert "NPCs/Mira.md" in result
    assert "whole" in result
    assert result.endswith("---\ntype: npc\n---\nMira forges blades.")


async def test_r70_r71_large_note_comes_back_as_outline_with_lead(vault):
    body = "x" * 3000
    text = (
        "---\ntype: npc\naliases: [Aldric]\n---\n"
        "# Captain Aldric\n"
        "Captain of the north gate.\n"
        "\n"
        "## Background\n"
        f"{body}\n"
        "### Youth\n"
        f"{body}\n"
        "## Rivals\n"
        f"{body}\n"
    )
    _write(vault, "NPCs/Captain Aldric.md", text)
    result = await server.vault_read_note("Captain Aldric")
    assert body not in result
    assert "## Outline: NPCs/Captain Aldric.md (13 lines, ~2.3k tokens)" in result
    assert "Frontmatter, L1-4:\n  type: npc\n  aliases: [Aldric]\n" in result
    assert "Lead, L6-6:\n  Captain of the north gate.\n" in result
    assert "  L5-13  # Captain Aldric  ~2.3k" in result
    assert "  L8-11    ## Background  ~1.5k" in result
    assert "  L10-11      ### Youth  ~753" in result
    assert "  L12-13    ## Rivals  ~753" in result


async def test_r72_outline_without_sections_says_how_to_get_in(vault):
    _write(vault, "Players/Notes.md", "# Notes\n" + "word " * 2000 + "\n")
    result = await server.vault_read_note("Notes")
    assert "No sections to pick from (one heading)." in result
    assert 'vault_mentions("<name>", paths=["Players/Notes.md"])' in result
    assert "For all of it: Read the file." in result
    assert "Headings:" not in result
    assert "[cut at 1,500 characters; the lead ends at L2]" in result


async def test_r38_r39_ambiguous_note_picks_shallowest_and_names_others(vault):
    _write(vault, "Archive/Old/Mira.md", "old")
    _write(vault, "NPCs/Mira.md", "current")
    _write(vault, "Zeta/Mira.md", "zeta")
    result = await server.vault_read_note("Mira")
    assert result.endswith("current")
    assert "Other matches: Zeta/Mira.md, Archive/Old/Mira.md" in result


async def test_r36_r37_note_argument_matches_aliases_and_says_so(vault):
    text = "---\naliases: [Aldric]\n---\nGate captain.\n"
    _write(vault, "NPCs/Captain Aldric.md", text)
    result = await server.vault_read_note("aldric")
    assert result.endswith("Gate captain.")
    assert 'Found by alias "aldric" of NPCs/Captain Aldric.md' in result


async def test_r73_r75_read_section_returns_each_matching_section_labelled(vault):
    text = (
        "# Session 12\n"
        "## Log\n"
        "Fought the troll.\n"
        "## Open Threads\n"
        "- Who sent it?\n"
        "## Day 2\n"
        "### Log\n"
        "Rested.\n"
    )
    path = "Sessions/Session 12/Session 12.md"
    _write(vault, path, text)
    result = await server.vault_read_section("Session 12", ["Log", "Open Threads"])
    sep = " \u203a "
    assert f"## {path}:2-3{sep}Session 12{sep}Log (~" in result
    assert f"## {path}:4-5{sep}Session 12{sep}Open Threads (~" in result
    assert f"## {path}:7-8{sep}Session 12{sep}Day 2{sep}Log (~" in result
    for line in ("Fought the troll.", "- Who sent it?", "Rested."):
        assert line in result


async def test_r74_heading_match_ignores_case_whitespace_and_hashes(vault):
    _write(vault, "Note.md", "# Top\n## Open Threads\nthread one\n")
    result = await server.vault_read_section("Note", "  ## open threads ")
    assert "## Note.md:2-3" in result
    assert "thread one" in result


async def test_r76_sections_are_never_truncated(vault):
    long_text = "\n".join(f"line {n:03d} " + "y" * 90 for n in range(200))
    _write(vault, "Big.md", f"# Big\n## Part\n{long_text}\n## End\n")
    result = await server.vault_read_section("Big", "Part")
    assert long_text in result


async def test_r77_unmatched_heading_lists_the_notes_headings(vault):
    _write(vault, "Note.md", "# Top\n## Log\nentry\n### Detail\n")
    result = await server.vault_read_section("Note", ["Log", "Missing"])
    assert "## Note.md:2-4" in result
    expected = 'No section matches "Missing". Headings: # Top, ## Log, ### Detail'
    assert expected in result
