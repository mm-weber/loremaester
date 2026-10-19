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
        """Index the vault's notes, re-reading only added or changed files (R7-R11)."""
        root = self.root.resolve()
        seen: set[str] = set()
        for folder, subfolders, files in os.walk(self.root):
            subfolders[:] = sorted(
                name for name in subfolders if not name.startswith(".")
            )
            for name in sorted(files):
                if name.startswith(".") or not name.endswith(".md"):
                    continue
                file = Path(folder, name)
                rel = file.relative_to(self.root).as_posix()
                try:
                    if not file.resolve().is_relative_to(root):
                        continue
                    stat = file.stat()
                    old = self.notes.get(rel)
                    if not old or (old.mtime_ns, old.size) != (
                        stat.st_mtime_ns,
                        stat.st_size,
                    ):
                        text = file.read_bytes().decode("utf-8-sig", errors="replace")
                        self.notes[rel] = Note(
                            rel, stat.st_mtime_ns, stat.st_size, parse_note(text)
                        )
                except OSError:
                    continue  # unreadable, or gone since the walk listed it
                seen.add(rel)
        for rel in set(self.notes) - seen:
            del self.notes[rel]  # R9: deleted since the last refresh
