"""Pure line scanner for Obsidian notes (spec: specs/v0.2/surgical-search.md)."""

from dataclasses import dataclass


@dataclass
class ParsedNote:
    lines: list[str]
    frontmatter: tuple[int, int] | None = None


def parse_note(text: str) -> ParsedNote:
    """Parse a note's text. No file access: vault_index.py reads the files."""
    lines = text.splitlines()
    note = ParsedNote(lines=lines)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                note.frontmatter = (1, index + 1)  # R16
                break
    return note
