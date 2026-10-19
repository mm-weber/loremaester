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


def test_r21_link_forms_in_body_and_frontmatter():
    text = (
        "---\n"
        'faction: "[[Iron Guard]]"\n'
        "---\n"
        "Meets [[Captain Aldric]] and [[Mira|the smith]].\n"
        "| [[Old Mill\\|the mill]] | ruin |\n"
        "See [[Harbor#Docks]], [[Harbor#^dock-1]] and ![[Map Note]].\n"
    )
    assert [(link.target, link.line) for link in parse_note(text).links] == [
        ("Iron Guard", 2),
        ("Captain Aldric", 4),
        ("Mira", 4),
        ("Old Mill", 5),
        ("Harbor", 6),
        ("Harbor", 6),
        ("Map Note", 6),
    ]


def test_r20_no_links_inside_code():
    text = (
        "```\n"
        "[[In Fence]]\n"
        "```\n"
        "~~~\n"
        "[[In Tilde Fence]]\n"
        "~~~\n"
        "Text `[[In Inline Code]]` and [[Real Link]].\n"
    )
    assert [link.target for link in parse_note(text).links] == ["Real Link"]


def test_r22_heading_links_attachments_and_markdown_links_are_not_links():
    text = (
        "Jump to [[#Background]].\n"
        "Image ![[map.PNG]], [[handout.pdf]] and [[board.canvas]].\n"
        "A [markdown](Other%20Note.md) link.\n"
        "Keep [[Dr. Smith]] and [[Session 3.5]].\n"
    )
    assert [link.target for link in parse_note(text).links] == [
        "Dr. Smith",
        "Session 3.5",
    ]


def test_r30_section_runs_to_next_heading_with_same_or_fewer_hashes():
    note = parse_note("# Top\nintro\n## A\na\n### A1\na1\n## B\nb\n# Next\n")
    assert note.section(1) == (1, 8)
    assert note.section(3) == (3, 6)
    assert note.section(5) == (5, 6)
    assert note.section(7) == (7, 8)
    assert note.section(9) == (9, 9)


def test_r23_paragraph_block_is_the_run_of_plain_lines():
    text = (
        "# Title\n"
        "First line\n"
        "mentions [[X]]\n"
        "last line\n"
        "- list item\n"
        "\n"
        "Other paragraph\n"
        "---\n"
        "After break\n"
    )
    note = parse_note(text)
    assert note.block(3) == [2, 3, 4]
    assert note.block(7) == [7]
    assert note.block(9) == [9]


def test_r24_list_item_block_takes_its_deeper_lines():
    text = (
        "- first item\n"
        "- item with [[X]]\n"
        "  continued text\n"
        "\t- sub item\n"
        "- next item\n"
        "\n"
        "- lone item [[X]]\n"
        "  - child\n"
        "\n"
        "  after blank\n"
    )
    note = parse_note(text)
    assert note.block(2) == [2, 3, 4]
    assert note.block(3) == [2, 3, 4]
    assert note.block(7) == [7, 8]


def test_r25_nested_item_block_adds_ancestor_first_lines():
    text = (
        "- Faction\n"
        "  details\n"
        "  - Leaders\n"
        "    - [[X]] leads\n"
        "      since spring\n"
        "  - Members\n"
    )
    assert parse_note(text).block(4) == [1, 3, 4, 5]


def test_r26_table_row_block_keeps_header_and_separator():
    text = (
        "| Name | Role |\n"
        "|---|---|\n"
        "| Mira | smith |\n"
        "| [[X]] | captain |\n"
        "\n"
        "| no | separator |\n"
        "| [[X]] | row |\n"
    )
    note = parse_note(text)
    assert note.block(4) == [1, 2, 4]
    assert note.block(7) == [6, 7]
