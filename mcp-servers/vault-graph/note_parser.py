"""Pure line scanner for Obsidian notes (spec: specs/v0.2/surgical-search.md)."""

from dataclasses import dataclass


@dataclass
class ParsedNote:
    lines: list[str]
    frontmatter: tuple[int, int] | None = None


def parse_note(text: str) -> ParsedNote:
    return ParsedNote(lines=[])
