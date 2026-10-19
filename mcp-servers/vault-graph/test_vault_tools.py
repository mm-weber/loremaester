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


async def test_r41_lists_every_link_to_the_note(vault):
    _write(vault, "NPCs/Mira.md", "Smith.")
    text = "Met [[Mira]] at dawn.\n\nLater [[NPCs/Mira|she]] left.\n"
    _write(vault, "Sessions/Log.md", text)
    _write(vault, "Places/Forge.md", "- run by [[mira]]\n")
    _write(vault, "Places/Other.md", "No link here.\n")
    result = await server.vault_mentions("Mira")
    assert "Sessions/Log.md:1" in result and "Met [[Mira]] at dawn." in result
    assert "Sessions/Log.md:3" in result and "Later [[NPCs/Mira|she]] left." in result
    assert "Places/Forge.md:1" in result and "- run by [[mira]]" in result
    assert "Places/Other.md" not in result


async def test_r44_links_from_the_note_to_itself_are_not_listed(vault):
    _write(vault, "NPCs/Mira.md", "See [[Mira#Gear]] below.\n")
    _write(vault, "Log.md", "Met [[Mira]].\n")
    result = await server.vault_mentions("Mira")
    assert "Log.md:1" in result
    assert "NPCs/Mira.md:1" not in result


async def test_r42_links_naming_an_alias_count_for_the_aliased_note(vault):
    text = "---\naliases: [Aldric]\n---\nCaptain.\n"
    _write(vault, "NPCs/Captain Aldric.md", text)
    _write(vault, "Log.md", "Saw [[Aldric]] at the gate.\n")
    result = await server.vault_mentions("Captain Aldric")
    assert "Log.md:1" in result


async def test_r43_unwritten_note_lists_its_recorded_links(vault):
    _write(vault, "Log.md", "Heard of [[Ghost Ship]].\n")
    result = await server.vault_mentions("Ghost Ship")
    assert "## Linked mentions: Ghost Ship (no note yet)" in result
    assert "Log.md:1" in result


async def test_r31_r45_excerpt_label_has_path_line_and_heading_path(vault):
    _write(vault, "NPCs/Mira.md")
    text = "# Session 1\n## Scenes\n### Arrival\nMeet [[Mira]].\n"
    _write(vault, "Sessions/S1.md", text)
    result = await server.vault_mentions("Mira")
    sep = " \u203a "
    label = f"Sessions/S1.md:4{sep}Session 1{sep}Scenes{sep}Arrival"
    assert f"{label}\nMeet [[Mira]]." in result


async def test_r46_blocks_sharing_a_line_form_one_excerpt(vault):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Log.md", "First [[Mira]] line\nsecond [[Mira]] line\n")
    result = await server.vault_mentions("Mira")
    assert result.count("Log.md:") == 1
    assert "Log.md:1\nFirst [[Mira]] line\nsecond [[Mira]] line" in result


async def test_r47_skipped_lines_show_as_a_gap_marker(vault):
    _write(vault, "NPCs/Mira.md")
    text = "| Name | Role |\n|---|---|\n| Bo | cook |\n| [[Mira]] | smith |\n"
    _write(vault, "Gate.md", text)
    result = await server.vault_mentions("Mira")
    expected = "| Name | Role |\n|---|---|\n…\n| [[Mira]] | smith |"
    assert expected in result


async def test_r48_long_excerpt_is_cut_with_a_marker(vault):
    _write(vault, "NPCs/Mira.md")
    items = [f"- [[Mira]] item {n:02d} " + "z" * 80 for n in range(30)]
    _write(vault, "List.md", "## [[Mira]] notes\n" + "\n".join(items) + "\n")
    result = await server.vault_mentions("Mira")
    assert "- [[Mira]] item 13 " in result
    assert "- [[Mira]] item 14 " not in result
    marker = (
        "[cut at 1,500 characters; the block ends at L31; 16 mentions moved to the map]"
    )
    assert marker in result


async def test_r65_paths_limit_mentions_to_matching_folders_and_notes(vault):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Sessions/Session 36/Prep.md", "[[Mira]] prep\n")
    _write(vault, "Sessions/Session 37/Prep.md", "[[Mira]] later\n")
    _write(vault, "Places/Forge.md", "[[Mira]] works\n")
    entries = ["Session 36", "places/forge.md"]
    result = await server.vault_mentions("Mira", paths=entries)
    assert "Sessions/Session 36/Prep.md:1" in result
    assert "Places/Forge.md:1" in result
    assert "Session 37" not in result


async def test_r66_paths_entry_without_matches_is_reported(vault):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Log.md", "[[Mira]]\n")
    result = await server.vault_mentions("Mira", paths=["Sesions", "Log"])
    assert 'No note or folder matches paths entry "Sesions".' in result
    assert "Log.md:1" in result


async def test_rf5_paths_entries_tolerate_slashes_and_dot_slash(vault):
    _write(vault, "NPCs/Mira.md")
    for rel in ("Sessions/S1.md", "Places/Forge.md", "Other/X.md"):
        _write(vault, rel, "[[Mira]]\n")
    result = await server.vault_mentions("Mira", paths=["/Sessions/", "./Places"])
    assert "Sessions/S1.md:1" in result and "Places/Forge.md:1" in result
    assert "Other/X.md" not in result
    assert "No note or folder matches" not in result


async def test_r12_argument_paths_are_never_opened(vault, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    _write(outside, "Secret.md", "secret [[Mira]] text")
    _write(vault, "NPCs/Mira.md", "home")
    escape = f"../{outside.name}/Secret"
    for name in (escape, str(outside / "Secret.md")):
        assert (await server.vault_read_note(name)).startswith("Error: no note matches")
    result = await server.vault_mentions("Mira", paths=[escape, str(outside)])
    assert "secret" not in result


async def test_r02_r50_skipped_folders_are_counted_not_listed(vault, monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_FOLDERS", "Rules, Art/Prompts")
    _write(vault, "NPCs/Mira.md")
    for rel in (
        "Log.md",
        "Rules/Smithing.md",
        "Rules/Deep/Forging.md",
        "Art/Prompts/Mira portrait.md",
        "Art/Gallery.md",
    ):
        _write(vault, rel, "[[Mira]]\n")
    result = await server.vault_mentions("Mira")
    assert "Log.md:1" in result and "Art/Gallery.md:1" in result
    for hidden in ("Rules/Smithing.md", "Rules/Deep/Forging.md", "Art/Prompts/"):
        assert hidden not in result
    assert "Skipped folders: Rules 2 · Art/Prompts 1" in result


async def test_r03_paths_reaching_into_a_skipped_folder_list_it(vault, monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_FOLDERS", "Rules,Art/Prompts")
    _write(vault, "NPCs/Mira.md")
    for rel in (
        "Rules/Smithing.md",
        "Rules/Deep/Forging.md",
        "Art/Prompts/Portrait.md",
        "Art/Gallery.md",
    ):
        _write(vault, rel, "[[Mira]]\n")
    by_folder = await server.vault_mentions("Mira", paths=["Rules"])
    assert "Rules/Smithing.md:1" in by_folder
    assert "Rules/Deep/Forging.md:1" in by_folder
    by_note = await server.vault_mentions("Mira", paths=["Rules/Deep/Forging"])
    assert "Rules/Deep/Forging.md:1" in by_note
    by_parent = await server.vault_mentions("Mira", paths=["Art"])
    assert "Art/Gallery.md:1" in by_parent
    assert "Art/Prompts/Portrait.md:1" not in by_parent


async def test_r04_read_tools_open_notes_in_skipped_folders(vault, monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_FOLDERS", "Rules")
    _write(vault, "Rules/Smithing.md", "# Smithing\n## Steel\nFold it.\n")
    assert (await server.vault_read_note("Smithing")).endswith("Fold it.")
    assert "Fold it." in await server.vault_read_section("Smithing", "Steel")
