"""Tests for the vault-graph read tools and vault_mentions.

Spec: specs/v0.2/surgical-search.md.
"""

import importlib.util
import inspect
import re
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


def _labels(result):
    """Note paths of the excerpt labels, in response order."""
    return re.findall(r"^(.+?\.md):\d+", result, re.M)


def _mention_map(result):
    """(path, line) pairs listed in the map of a vault_mentions response."""
    parts = result.split("Not shown, pull with paths=[...]:", 1)
    pairs = set()
    if len(parts) == 2:
        for path, lines in re.findall(r"([^:·\n]+?\.md) L([\d,]+)", parts[1]):
            pairs |= {(path.strip(), int(line)) for line in lines.split(",")}
    return pairs


async def test_r64_every_mention_is_shown_or_mapped(vault):
    _write(vault, "NPCs/Mira.md")
    texts = {}
    for number in range(1, 9):
        rel = f"Log/s{number}.md"
        body = f"[[Mira]] m{number}a " + "x" * 300 + f"\n\n[[Mira]] m{number}b\n"
        _write(vault, rel, body)
        texts[(rel, 1)] = f"m{number}a "
        texts[(rel, 3)] = f"m{number}b"
    items = [f"- [[Mira]] cut{k:02d} " + "z" * 90 for k in range(25)]
    _write(vault, "Long.md", "## [[Mira]] list\n" + "\n".join(items) + "\n")
    texts[("Long.md", 1)] = "## [[Mira]] list"
    for k in range(25):
        texts[("Long.md", k + 2)] = f"cut{k:02d} "
    for budget in (1, 150, 600, 4000):
        for paths in (None, ["Log"], ["Long"]):
            result = await server.vault_mentions(
                "Mira", paths=paths, budget_tokens=budget
            )
            mapped = _mention_map(result)
            for key, text in texts.items():
                if paths and not key[0].startswith(paths[0]):
                    continue
                assert text in result or key in mapped, (budget, paths, key)


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


async def test_r52_unlinked_mode_lists_plain_text_mentions(vault):
    text = "---\naliases: [Old Guard]\n---\n# Captain Aldric\n"
    _write(vault, "NPCs/Captain Aldric.md", text)
    body = "The Captain Aldric arrived.\n\nThe Old Guard left.\n\nNobody else.\n"
    _write(vault, "Log.md", body)
    result = await server.vault_mentions("Captain Aldric", unlinked=True)
    title = "## Unlinked mentions: Captain Aldric (NPCs/Captain Aldric.md)"
    assert title in result
    assert "Log.md:1" in result and "Log.md:3" in result
    assert "Log.md:5" not in result
    assert "NPCs/Captain Aldric.md:" not in result


async def test_r05_configured_endings_extend_unlinked_matches(vault, monkeypatch):
    monkeypatch.setenv("VAULT_NAME_ENDINGS", "s,es")
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Log.md", "Miras hammer.\n\nMiraes ring.\n\nMirass oddity.\n")
    result = await server.vault_mentions("Mira", unlinked=True)
    assert "Log.md:1" in result and "Log.md:3" in result
    assert "Log.md:5" not in result


async def test_r06_empty_settings_skip_nothing_and_add_no_endings(vault, monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_FOLDERS", "")
    monkeypatch.setenv("VAULT_NAME_ENDINGS", " , ")
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Rules/Smithing.md", "[[Mira]]\n")
    _write(vault, "Log.md", "Miras hammer.\n\nMira sings.\n")
    assert "Rules/Smithing.md:1" in await server.vault_mentions("Mira")
    unlinked = await server.vault_mentions("Mira", unlinked=True)
    assert "Log.md:3" in unlinked and "Log.md:1" not in unlinked


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


async def test_r48_long_list_excerpt_keeps_its_mentions_and_their_items(vault):
    _write(vault, "NPCs/Mira.md")
    days = [f"  - day {n}: a forged seal " + "z" * 80 for n in range(1, 19)]
    lines = ["# Ledger", "- Market days with [[Mira]]:", *days, "  - day 19"]
    _write(vault, "Ledger.md", "\n".join([*lines, "    and [[Mira]] signs."]) + "\n")
    result = await server.vault_mentions("Mira")
    excerpt = "\n".join(
        [
            "- Market days with [[Mira]]:",
            "…",
            "  - day 19",
            "    and [[Mira]] signs.",
            "[trimmed to its mentions; the block runs L2-22]",
        ]
    )
    assert "Ledger.md:2" in result
    assert excerpt in result
    assert "Not shown" not in result


async def test_r91_long_line_shows_a_window_around_the_mention(vault):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Bo.md")
    _write(vault, "Saga.md", "Long ago [[Bo]] " + "w" * 2000 + " [[Mira]] arrived.\n")
    result = await server.vault_mentions("Mira")
    lines = [text for text in result.splitlines() if "[[Mira]] arrived." in text]
    assert len(lines) == 1
    assert lines[0].startswith("…") and len(lines[0]) <= 1500
    assert "[trimmed to its mentions; the block runs L1]" in result
    assert "Not shown" not in result


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


async def test_r02_a_note_beside_a_skipped_folder_is_listed(vault, monkeypatch):
    monkeypatch.setenv("VAULT_SKIP_FOLDERS", "Rules,Art/Prompts")
    _write(vault, "NPCs/Mira.md")
    for rel in ("Rules.md", "Rules/Smithing.md", "Art/Prompts.md"):
        _write(vault, rel, "[[Mira]]\n")
    result = await server.vault_mentions("Mira")
    assert "Rules.md:1" in result and "Art/Prompts.md:1" in result
    assert "Rules/Smithing.md" not in result
    by_parent = await server.vault_mentions("Mira", paths=["Art"])
    assert "Art/Prompts.md:1" in by_parent


async def test_r67_folders_take_turns_biggest_first(vault):
    _write(vault, "NPCs/Mira.md")
    for rel in (
        "Sessions/S1.md",
        "Sessions/S2.md",
        "Sessions/S3.md",
        "Places/A.md",
        "Places/B.md",
        "Hub.md",
    ):
        _write(vault, rel, "[[Mira]]\n")
    labels = _labels(await server.vault_mentions("Mira"))
    folders = [path.split("/")[0] if "/" in path else "(root)" for path in labels]
    assert folders == ["Sessions", "Places", "(root)", "Sessions", "Places", "Sessions"]


async def test_r68_notes_in_a_folder_come_in_reverse_natural_order(vault):
    _write(vault, "NPCs/Mira.md")
    for number in (2, 9, 10):
        _write(vault, f"Sessions/Session {number}/Log.md", "[[Mira]]\n")
    assert _labels(await server.vault_mentions("Mira")) == [
        "Sessions/Session 10/Log.md",
        "Sessions/Session 9/Log.md",
        "Sessions/Session 2/Log.md",
    ]


async def test_r58_only_excerpts_and_labels_count_toward_the_budget(vault):
    signature = inspect.signature(server.vault_mentions)
    assert signature.parameters["budget_tokens"].default == 4000
    _write(vault, "NPCs/Mira.md")
    _write(vault, "N/b.md", "[[Mira]] " + "b" * 31 + "\n")
    _write(vault, "N/a.md", "[[Mira]] " + "a" * 31 + "\n")
    result = await server.vault_mentions("Mira", budget_tokens=22)
    assert "N/b.md:1" in result
    assert "N/a.md:1" not in result
    assert "N/a.md L1" in result


async def test_r59_no_note_takes_more_than_a_quarter_when_not_all_fit(vault):
    _write(vault, "NPCs/Mira.md")
    heavy = "\n\n".join(f"[[Mira]] heavy{k} " + "h" * 100 for k in range(14))
    _write(vault, "Log/s9.md", heavy + "\n")
    for number in range(1, 4):
        _write(vault, f"Log/s{number}.md", f"[[Mira]] light{number}\n")
    result = await server.vault_mentions("Mira", budget_tokens=400)
    assert "heavy2 " in result
    assert "heavy3 " not in result
    assert all(f"light{number}" in result for number in range(1, 4))


async def test_r60_filling_stops_at_the_first_note_that_does_not_fit(vault):
    _write(vault, "NPCs/Mira.md")
    for number in range(2, 7):
        _write(vault, f"Log/s0{number}.md", "[[Mira]] " + "x" * 351 + "\n")
    _write(vault, "Log/s01.md", "[[Mira]] tiny.\n")
    result = await server.vault_mentions("Mira", budget_tokens=400)
    assert _labels(result) == ["Log/s06.md", "Log/s05.md", "Log/s04.md", "Log/s03.md"]


async def test_r61_at_least_one_excerpt_is_shown(vault):
    _write(vault, "NPCs/Mira.md")
    body = "[[Mira]] first " + "x" * 600 + "\n\n[[Mira]] second\n"
    _write(vault, "Log/s2.md", body)
    _write(vault, "Log/s1.md", "[[Mira]] other\n")
    result = await server.vault_mentions("Mira", budget_tokens=1)
    assert _labels(result) == ["Log/s2.md"]
    assert "[[Mira]] second" not in result


async def test_r62_r63_map_groups_by_folder_and_ends_with_pull_hints(vault):
    _write(vault, "NPCs/Mira.md")
    for rel in ("Sessions/S1.md", "Sessions/S2.md", "Places/Forge.md"):
        body = "[[Mira]] " + "x" * 2000 + "\n\n[[Mira]] " + "y" * 2000 + "\n"
        _write(vault, rel, body)
    result = await server.vault_mentions("Mira", budget_tokens=10)
    lines = result.split("Not shown, pull with paths=[...]:\n", 1)[1].splitlines()
    dot = " · "
    hints = f'More: paths=["<folder or note>"]{dot}budget_tokens=<n>{dot}unlinked=true'
    assert lines[-1] == hints
    groups = [re.match(r"^(\S+) \((\d+)\): (.+)$", line) for line in lines[:-1]]
    assert [group.group(1) for group in groups] == ["Sessions", "Places"]
    for group in groups:
        entries = group.group(3).split(dot)
        assert int(group.group(2)) == len(entries)
        for entry in entries:
            assert entry.startswith(group.group(1) + "/")
            assert re.search(r"\.md L[\d,]+$", entry)


async def test_r49_r51_overview_counts_folders_other_kind_and_excerpts(vault):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Sessions/S1.md", "[[Mira]] one\n")
    _write(vault, "Sessions/S2.md", "[[Mira]] two\n")
    _write(vault, "Places/Forge.md", "[[Mira]] three\n")
    _write(vault, "Gossip.md", "Mira is busy.\n")
    _write(vault, "Talk.md", "Mira again.\n")
    linked = await server.vault_mentions("Mira")
    assert "3 notes link here: Sessions 2 · Places 1" in linked
    assert "Unlinked: 2 notes name it without a link" in linked
    summary = r"^Excerpts for 3 notes \(~[\d.]+k? of ~[\d.]+k? tokens for all\)$"
    assert re.search(summary, linked, re.M)
    unlinked = await server.vault_mentions("Mira", unlinked=True)
    assert "2 notes name it: (root) 2" in unlinked
    assert "Linked: 3 notes link here" in unlinked


async def test_r49_r51_overview_figures_follow_listed_notes_and_budget(
    vault, monkeypatch
):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Sessions/S1.md", "[[Mira]] one\n")
    _write(vault, "Sessions/S2.md", "[[Mira]] two\n")
    tight = (await server.vault_mentions("Mira", budget_tokens=5)).splitlines()
    assert "Excerpts for 1 notes (~8 of ~16 tokens for all)" in tight
    monkeypatch.setenv("VAULT_SKIP_FOLDERS", "Rules")
    _write(vault, "Rules/R2.md", "Mira rules.\n")
    _write(vault, "Gossip.md", "Mira is busy.\n")
    skipped = (await server.vault_mentions("Mira")).splitlines()
    assert "Unlinked: 1 notes name it without a link" in skipped
    _write(vault, "NPCs/Hermit.md")
    alone = (await server.vault_mentions("Hermit")).splitlines()
    assert alone[2:] == [
        "0 notes link here",
        "Unlinked: 0 notes name it without a link",
        "Excerpts for 0 notes (~0 of ~0 tokens for all)",
    ]


async def test_r78_r79_unknown_names_get_close_names(vault):
    _write(vault, "NPCs/Captain Aldric.md", "---\naliases: [Aldric]\n---\nx\n")
    _write(vault, "NPCs/Mira.md")
    _write(vault, "NPCs/Miriam.md")
    note = (await server.vault_read_note("Mir")).splitlines()
    assert note[0] == "Error: no note matches 'Mir'. Close names: Mira, Miriam"
    section = (await server.vault_read_section("Captian Aldric", "x")).splitlines()
    close = "Close names: Captain Aldric, Aldric"
    assert section[0] == f"Error: no note matches 'Captian Aldric'. {close}"
    mentions = (await server.vault_mentions("Mirra")).splitlines()
    assert "No note matches 'Mirra'. Close names: Mira, Miriam" in mentions
    assert "No note matches" not in await server.vault_mentions("Mira")


async def test_r15_every_response_names_the_vault_root_once(vault):
    _write(vault, "NPCs/Mira.md", "# Mira\n## Gear\nhammer\n")
    _write(vault, "Log.md", "[[Mira]] and Mira\n")
    responses = [
        await server.vault_read_note("Mira"),
        await server.vault_read_section("Mira", "Gear"),
        await server.vault_mentions("Mira"),
        await server.vault_mentions("Mira", unlinked=True),
        await server.vault_read_note("Nobody"),
    ]
    for result in responses:
        assert result.count(str(vault)) == 1
        assert f"Vault: {vault}" in result.splitlines()


async def test_r80_missing_vault_root_is_an_error_naming_it(tmp_path, monkeypatch):
    file_root = _write(tmp_path, "file.md", "x")
    loop_root = tmp_path / "loop"
    loop_root.symlink_to(loop_root)
    for root in (tmp_path / "no-vault", file_root, loop_root):
        monkeypatch.setattr(server, "VAULT_PATH", str(root))
        expected = f"Error: vault root is missing or not a folder: {root}"
        assert await server.vault_read_note("x") == expected
        assert await server.vault_read_section("x", "y") == expected
        assert await server.vault_mentions("x") == expected


def test_r68_equal_natural_keys_still_order_one_way():
    tied = ["Sessions/Session 09.md", "Sessions/Session 9.md"]
    assert server._order(tied) == server._order(tied[::-1])


async def test_r59_fewer_than_four_notes_split_the_whole_budget(vault):
    _write(vault, "NPCs/Mira.md")
    for name in ("s1", "s2"):
        body = "\n\n".join(f"[[Mira]] {name}p{k} " + "h" * 100 for k in range(14))
        _write(vault, f"Log/{name}.md", body + "\n")
    result = await server.vault_mentions("Mira", budget_tokens=400)
    assert all(f"{name}p5 " in result for name in ("s1", "s2"))
    assert not any(f"{name}p6 " in result for name in ("s1", "s2"))


async def test_r48_long_callout_excerpt_keeps_its_first_line(vault):
    _write(vault, "NPCs/Mira.md")
    gossip = [f"> rumor {n}: the tides turn " + "q" * 80 for n in range(1, 19)]
    lines = ["> [!note] Harbor gossip", *gossip, "> [[Mira]] buys the ledger."]
    _write(vault, "Harbor.md", "\n".join(lines) + "\n")
    result = await server.vault_mentions("Mira")
    excerpt = "\n".join(
        [
            "> [!note] Harbor gossip",
            "…",
            "> [[Mira]] buys the ledger.",
            "[trimmed to its mentions; the block runs L1-20]",
        ]
    )
    assert excerpt in result


async def test_r48_long_property_excerpt_keeps_its_key_line(vault):
    _write(vault, "NPCs/Mira.md")
    contacts = [f'  - "[[Contact {n}]] ' + "c" * 80 + '"' for n in range(1, 19)]
    lines = ["---", "related:", *contacts, '  - "[[Mira]]"', "---", "Body."]
    _write(vault, "Guild.md", "\n".join(lines) + "\n")
    result = await server.vault_mentions("Mira")
    excerpt = "\n".join(
        [
            "related:",
            "…",
            '  - "[[Mira]]"',
            "[trimmed to its mentions; the block runs L2-21]",
        ]
    )
    assert excerpt in result


async def test_r90_too_long_trimmed_excerpt_comes_in_parts(vault):
    _write(vault, "NPCs/Mira.md")
    rows = [f"| [[Mira]] deal {n:02d} | " + "t" * 60 + " |" for n in range(1, 41)]
    head = ["| Deal | Terms |", "|---|---|"]
    _write(vault, "Deals.md", "\n".join([*head, *rows]) + "\n")
    result = await server.vault_mentions("Mira")
    parts = result.split("\n\nDeals.md:")[1:]
    assert len(parts) == 3
    for number, part in enumerate(parts, 1):
        assert part.split("\n")[1:3] == head
        marker = f"[part {number} of 3, trimmed to its mentions; the block runs L1-42]"
        assert marker in part
    assert all(f"deal {n:02d} " in result for n in range(1, 41))
    assert "Not shown" not in result


async def test_r91_long_line_window_finds_an_unlinked_mention(vault):
    _write(vault, "NPCs/Mira.md")
    _write(vault, "Saga.md", "Long ago " + "w" * 2000 + " Mira arrived.\n")
    result = await server.vault_mentions("Mira", unlinked=True)
    lines = [text for text in result.splitlines() if "Mira arrived." in text]
    assert len(lines) == 1 and lines[0].startswith("…")
    assert "Not shown" not in result


async def test_r59_a_negative_budget_without_mentions_still_answers(vault):
    _write(vault, "NPCs/Mira.md")
    result = await server.vault_mentions("Mira", budget_tokens=-1)
    assert "0 notes link here" in result


async def test_r91_a_window_finds_a_mention_after_decomposed_text(vault):
    _write(vault, "NPCs/Mira.md")
    accent = "e" + chr(0x301)  # NFD: e and a combining acute accent
    _write(vault, "Saga.md", "Long ago " + accent * 1000 + " Mira arrived.\n")
    result = await server.vault_mentions("Mira", unlinked=True)
    assert "Mira arrived." in result
