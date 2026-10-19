"""Live index of a vault: notes parsed on demand, cached by file stat.

Requirement numbers refer to specs/v0.2/surgical-search.md.
"""

from dataclasses import dataclass
from pathlib import Path

from note_parser import ParsedNote, parse_note


@dataclass
class Note:
    path: str  # vault-relative POSIX path, with .md
    parsed: ParsedNote


class VaultIndex:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.notes: dict[str, Note] = {}

    def refresh(self) -> None:
        """Index every .md file outside dot folders (R7)."""
        self.notes = {}
        for file in sorted(self.root.rglob("*.md")):
            rel = file.relative_to(self.root).as_posix()
            if any(part.startswith(".") for part in rel.split("/")):
                continue
            text = file.read_text(encoding="utf-8")
            self.notes[rel] = Note(rel, parse_note(text))
