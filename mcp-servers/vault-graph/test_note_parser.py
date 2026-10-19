"""Tests for note_parser (spec: specs/v0.2/surgical-search.md)."""

from note_parser import parse_note


def test_r16_frontmatter_needs_opening_and_closing_marker():
    note = parse_note("---\ntype: npc\naliases: [Ally]\n---\nBody text.\n")
    assert note.frontmatter == (1, 4)
    assert parse_note("---\ntype: npc\nno closing marker\n").frontmatter is None
    assert parse_note("Body first\n---\ntype: npc\n---\n").frontmatter is None


def test_r18_aliases_from_aliases_and_alias_keys():
    listed = parse_note("---\naliases:\n  - Ally\n  - The Captain\n---\n")
    assert listed.aliases == ["Ally", "The Captain"]
    assert parse_note("---\naliases: Ally\n---\n").aliases == ["Ally"]
    assert parse_note("---\nalias: [Old Name]\n---\n").aliases == ["Old Name"]


def test_r17_invalid_yaml_keeps_frontmatter_without_aliases():
    note = parse_note("---\naliases: [unclosed\ntype: npc\n---\nBody.\n")
    assert note.frontmatter == (1, 4)
    assert note.aliases == []


def test_r19_headings_only_outside_code_and_frontmatter():
    text = (
        "---\n"
        "# a YAML comment, not a heading\n"
        "---\n"
        "# Title\n"
        "#tag at the start of a line\n"
        "Underlined\n"
        "==========\n"
        "```\n"
        "# inside code\n"
        "```\n"
        "###\tDeep\n"
    )
    headings = parse_note(text).headings
    assert [(h.level, h.text, h.line) for h in headings] == [
        (1, "Title", 4),
        (3, "Deep", 11),
    ]
