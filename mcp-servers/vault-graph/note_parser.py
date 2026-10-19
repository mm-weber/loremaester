"""Pure line scanner for Obsidian notes (spec: specs/v0.2/surgical-search.md)."""

from dataclasses import dataclass, field

import yaml


@dataclass
class ParsedNote:
    lines: list[str]
    frontmatter: tuple[int, int] | None = None
    aliases: list[str] = field(default_factory=list)


def _aliases(frontmatter: str) -> list[str]:
    """Aliases from the `aliases` and `alias` keys, each a list or one string (R18)."""
    data = yaml.safe_load(frontmatter)
    if not isinstance(data, dict):
        return []
    found = []
    for key in ("aliases", "alias"):
        value = data.get(key)
        for alias in value if isinstance(value, list) else [value]:
            if isinstance(alias, str) and alias.strip():
                found.append(alias.strip())
    return found


def parse_note(text: str) -> ParsedNote:
    """Parse a note's text. No file access: vault_index.py reads the files."""
    lines = text.splitlines()
    note = ParsedNote(lines=lines)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                note.frontmatter = (1, index + 1)  # R16
                note.aliases = _aliases("\n".join(lines[1:index]))
                break
    return note
