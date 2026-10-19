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
