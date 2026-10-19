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
