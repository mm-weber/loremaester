"""Tests for vault_index (spec: specs/v0.2/surgical-search.md)."""

import os
import unicodedata

from vault_index import VaultIndex


def _write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_r07_index_has_every_md_file_outside_dot_folders(tmp_path):
    for rel in (
        "Home.md",
        "NPCs/Mira.md",
        "Deep/Er/Note.md",
        "notes.txt",
        ".obsidian/workspace.md",
        ".trash/Old.md",
        "NPCs/.draft.md",
    ):
        _write(tmp_path, rel)
    index = VaultIndex(tmp_path)
    index.refresh()
    assert sorted(index.notes) == ["Deep/Er/Note.md", "Home.md", "NPCs/Mira.md"]


def test_r08_symlink_out_of_the_vault_is_not_read(tmp_path):
    vault = tmp_path / "vault"
    outside = _write(tmp_path, "outside/Secret.md", "secret text")
    _write(vault, "Inside.md")
    (vault / "Leak.md").symlink_to(outside)
    (vault / "LeakDir").symlink_to(outside.parent, target_is_directory=True)
    index = VaultIndex(vault)
    index.refresh()
    assert sorted(index.notes) == ["Inside.md"]


def test_r09_refresh_reflects_added_changed_and_deleted_notes(tmp_path):
    _write(tmp_path, "Keep.md", "old text")
    _write(tmp_path, "Gone.md")
    index = VaultIndex(tmp_path)
    index.refresh()
    _write(tmp_path, "Keep.md", "new text, longer")
    _write(tmp_path, "New.md")
    (tmp_path / "Gone.md").unlink()
    index.refresh()
    assert sorted(index.notes) == ["Keep.md", "New.md"]
    assert index.notes["Keep.md"].parsed.lines == ["new text, longer"]


def test_r10_unchanged_stat_means_no_reread(tmp_path):
    path = _write(tmp_path, "Note.md", "alpha")
    index = VaultIndex(tmp_path)
    index.refresh()
    before = path.stat()
    path.write_text("omega", encoding="utf-8")  # same size
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    index.refresh()
    assert index.notes["Note.md"].parsed.lines == ["alpha"]


def test_r11_invalid_utf8_bytes_are_replaced(tmp_path):
    (tmp_path / "Broken.md").write_bytes(b"caf\xe9 [[Link]]\n")
    index = VaultIndex(tmp_path)
    index.refresh()
    note = index.notes["Broken.md"].parsed
    assert note.lines == ["caf\ufffd [[Link]]"]
    assert [link.target for link in note.links] == ["Link"]


def test_rf2_unreadable_or_vanished_files_are_skipped(tmp_path):
    _write(tmp_path, "Good.md", "fine")
    (tmp_path / "Broken.md").symlink_to(tmp_path / "Missing.md")
    (tmp_path / "Loop.md").symlink_to(tmp_path / "Loop.md")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert sorted(index.notes) == ["Good.md"]


def test_rf3_byte_order_mark_and_crlf_keep_the_frontmatter(tmp_path):
    (tmp_path / "Win.md").write_bytes(
        b"\xef\xbb\xbf---\r\naliases: [Ally]\r\n---\r\nBody [[Link]]\r\n"
    )
    index = VaultIndex(tmp_path)
    index.refresh()
    note = index.notes["Win.md"].parsed
    assert note.frontmatter == (1, 3)
    assert note.aliases == ["Ally"]
    assert note.lines[3] == "Body [[Link]]"


def test_rf4_names_with_regex_characters_match_literally(tmp_path):
    _write(tmp_path, "NPCs/Mira (Elder).md", "---\naliases: [C++ Guild]\n---\n")
    text = "Mira (Elder) spoke.\n\nThe C++ Guild met.\n\nMira Elder left.\n"
    _write(tmp_path, "Log.md", text)
    index = VaultIndex(tmp_path)
    index.refresh()
    found = index.resolve_note("Mira (Elder)")
    assert index.unlinked_mentions(found) == {"Log.md": [1, 3]}


def test_r33_target_without_slash_matches_file_name(tmp_path):
    _write(tmp_path, "Sessions/Log.md", "[[Mira]]")
    _write(tmp_path, "NPCs/Mira.md")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.resolve_link("Mira", "Sessions/Log.md") == "NPCs/Mira.md"
    assert index.resolve_link("Nobody", "Sessions/Log.md") is None


def test_r32_names_compare_after_nfc_lowercase_trim_and_md(tmp_path):
    cafe = unicodedata.normalize("NFD", "Café.md")
    _write(tmp_path, cafe)
    _write(tmp_path, "NPCs/Mira.md")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.resolve_link(" mira.MD ", "Home.md") == "NPCs/Mira.md"
    assert index.resolve_link("CAFÉ", "Home.md") == cafe
    assert index.resolve_note("café").path == cafe


def test_r34_target_with_slash_matches_root_path_or_path_end(tmp_path):
    _write(tmp_path, "World/NPCs/Mira.md")
    _write(tmp_path, "Old/Mira.md")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.resolve_link("World/NPCs/Mira", "Home.md") == "World/NPCs/Mira.md"
    assert index.resolve_link("NPCs/Mira", "Home.md") == "World/NPCs/Mira.md"
    assert index.resolve_link("rld/NPCs/Mira", "Home.md") is None


def test_r35_link_prefers_same_folder_then_fewest_segments(tmp_path):
    for rel in ("A/Deep/X.md", "B/X.md", "Z/X.md"):
        _write(tmp_path, rel)
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.resolve_link("X", "Z/Log.md") == "Z/X.md"
    assert index.resolve_link("X", "C/Log.md") == "B/X.md"


def test_r40_links_to_unwritten_notes_are_recorded(tmp_path):
    text = "Heard of [[Ghost Ship]].\n\nAgain [[ghost ship]].\n\n[[Other Ghost]]\n"
    _write(tmp_path, "Log.md", text)
    index = VaultIndex(tmp_path)
    index.refresh()
    found = index.resolve_note("Ghost Ship")
    assert found.path is None
    assert index.linked_mentions(found) == {"Log.md": [1, 3]}


def test_r53_unlinked_matching_is_case_insensitive_whole_words(tmp_path):
    _write(tmp_path, "NPCs/Mira.md")
    text = "mira smiled.\nMiranda left.\n_Mira_ hid.\nÉmira passed.\nMIRA!\n"
    _write(tmp_path, "Log.md", text)
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.unlinked_mentions(index.resolve_note("Mira")) == {"Log.md": [1, 5]}


def test_r54_titles_and_aliases_under_three_characters_are_ignored(tmp_path):
    _write(tmp_path, "NPCs/Al.md", "---\naliases: [Big Al, Al]\n---\n")
    _write(tmp_path, "Log.md", "Al waved.\n\nBig Al laughed.\n")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.unlinked_mentions(index.resolve_note("Al")) == {"Log.md": [3]}


def test_r54_only_names_shorter_than_three_characters_are_ignored(tmp_path):
    _write(tmp_path, "NPCs/Al.md")
    _write(tmp_path, "NPCs/Jax.md")
    _write(tmp_path, "Log.md", "Al waved.\n\nJax waved.\n")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.unlinked_mentions(index.resolve_note("Al")) == {}
    assert index.unlinked_mentions(index.resolve_note("Jax")) == {"Log.md": [3]}


def test_r55_unlinked_matching_skips_frontmatter_code_links_and_urls(tmp_path):
    _write(tmp_path, "NPCs/Mira.md")
    text = (
        "---\n"
        "owner: Mira\n"
        "---\n"
        "```\n"
        "Mira in code\n"
        "```\n"
        "Use `Mira` inline.\n"
        "See [[Mira Notes]] and [Mira](https://x.test/mira).\n"
        "Visit https://mira.example/Mira today.\n"
        "Mira in prose.\n"
    )
    _write(tmp_path, "Log.md", text)
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.unlinked_mentions(index.resolve_note("Mira")) == {"Log.md": [10]}


def test_r56_blocks_that_link_the_note_hold_no_unlinked_mentions(tmp_path):
    _write(tmp_path, "NPCs/Mira.md")
    _write(tmp_path, "Log.md", "[[Mira]] arrived.\nMira sat down.\n\nMira left.\n")
    index = VaultIndex(tmp_path)
    index.refresh()
    assert index.unlinked_mentions(index.resolve_note("Mira")) == {"Log.md": [4]}


def test_r57_unwritten_note_uses_the_requested_name(tmp_path):
    _write(tmp_path, "Log.md", "The ghost ship sails.\n\n[[Ghost Ship]] docked.\n")
    index = VaultIndex(tmp_path)
    index.refresh()
    found = index.resolve_note("Ghost Ship")
    assert index.unlinked_mentions(found) == {"Log.md": [1]}


def test_r05_configured_endings_still_match_the_bare_term(tmp_path):
    _write(tmp_path, "NPCs/Mira.md")
    _write(tmp_path, "Log.md", "Mira sings.\n\nMiras hammer.\n")
    index = VaultIndex(tmp_path)
    index.refresh()
    found = index.resolve_note("Mira")
    assert index.unlinked_mentions(found, ("s", "es")) == {"Log.md": [1, 3]}
