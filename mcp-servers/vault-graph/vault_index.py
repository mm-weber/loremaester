"""Live index of a vault: notes parsed on demand, cached by file stat.

Requirement numbers refer to specs/v0.2/surgical-search.md.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from note_parser import ParsedNote, parse_note


@dataclass
class Note:
    path: str  # vault-relative POSIX path, with .md
    mtime_ns: int
    size: int
    parsed: ParsedNote


class VaultIndex:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.notes: dict[str, Note] = {}

    def refresh(self) -> None:
        """Index the vault's .md files, re-reading only changed ones (R7, R8, R10)."""
        root = self.root.resolve()
        for folder, subfolders, files in os.walk(self.root):
            subfolders[:] = sorted(
                name for name in subfolders if not name.startswith(".")
            )
            for name in sorted(files):
                if name.startswith(".") or not name.endswith(".md"):
                    continue
                file = Path(folder, name)
                if not file.resolve().is_relative_to(root):
                    continue
                rel = file.relative_to(self.root).as_posix()
                stat = file.stat()
                old = self.notes.get(rel)
                if old and (old.mtime_ns, old.size) == (stat.st_mtime_ns, stat.st_size):
                    continue
                text = file.read_text(encoding="utf-8")
                self.notes[rel] = Note(
                    rel, stat.st_mtime_ns, stat.st_size, parse_note(text)
                )
