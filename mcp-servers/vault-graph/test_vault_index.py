"""Tests for vault_index (spec: specs/v0.2/surgical-search.md)."""

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
