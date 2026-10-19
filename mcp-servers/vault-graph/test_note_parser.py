"""Tests for note_parser (spec: specs/v0.2/surgical-search.md)."""

from note_parser import parse_note


def test_r16_frontmatter_needs_opening_and_closing_marker():
    note = parse_note("---\ntype: npc\naliases: [Ally]\n---\nBody text.\n")
    assert note.frontmatter == (1, 4)
    assert parse_note("---\ntype: npc\nno closing marker\n").frontmatter is None
    assert parse_note("Body first\n---\ntype: npc\n---\n").frontmatter is None
