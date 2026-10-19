"""Live index of a vault: notes parsed on demand, cached by file stat.

Requirement numbers refer to specs/v0.2/surgical-search.md.
"""

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from note_parser import ParsedNote, parse_note


def normalize(name: str) -> str:
    """Compare form of a name: NFC, lowercase, trimmed, no trailing .md (R32)."""
    name = unicodedata.normalize("NFC", name).strip().lower()
    return name.removesuffix(".md").strip()


def _depth_then_path(rel: str) -> tuple[int, str]:
    """Sort key: fewest path segments first, then alphabetical (R35, R38)."""
    return rel.count("/"), rel


def _term_pattern(terms: list[str]) -> re.Pattern[str]:
    """Whole-word, case-insensitive match of any term (R53)."""
    words = "|".join(
        re.escape(unicodedata.normalize("NFC", term))
        for term in sorted(terms, key=len, reverse=True)
    )
    return re.compile(rf"(?<!\w)(?:{words})(?!\w)", re.IGNORECASE)


@dataclass
class Note:
    path: str  # vault-relative POSIX path, with .md
    mtime_ns: int
    size: int
    parsed: ParsedNote


@dataclass(frozen=True)
class Resolution:
    name: str  # the name as requested
    path: str | None  # the note found, or None for an unwritten note
    alias: str | None = None  # the alias that matched (R36, R37)
    others: tuple[str, ...] = ()  # further matches (R38, R39)


class VaultIndex:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.notes: dict[str, Note] = {}
        self._by_name: dict[str, list[str]] = {}
        self._keys: dict[str, str] = {}

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
                    # realpath, as Path.resolve() raises RuntimeError on a symlink
                    # loop before Python 3.13; stat() then fails with OSError
                    if not Path(os.path.realpath(file)).is_relative_to(root):
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
        self._by_name = {}
        for rel in sorted(self.notes):
            self._by_name.setdefault(normalize(PurePosixPath(rel).stem), []).append(rel)
        self._keys = {rel: normalize(rel) for rel in sorted(self.notes)}

    def _candidates(self, key: str) -> list[str]:
        """Notes a normalized name matches: by file name, or by path when it has a
        slash (R32-R34)."""
        if "/" not in key:
            return list(self._by_name.get(key, []))
        exact = [rel for rel, rel_key in self._keys.items() if rel_key == key]
        return exact or [
            rel for rel, rel_key in self._keys.items() if rel_key.endswith("/" + key)
        ]

    def resolve_link(self, target: str, source: str) -> str | None:
        """The note a link in `source` points to, or None (R32-R35)."""
        matches = self._candidates(normalize(target))
        folder = PurePosixPath(source).parent
        same_folder = [rel for rel in matches if PurePosixPath(rel).parent == folder]
        ordered = sorted(same_folder or matches, key=_depth_then_path)
        return ordered[0] if ordered else None

    def resolve_note(self, name: str) -> Resolution:
        """The note a tool's `note` argument names: by file name or path, else by
        alias (R32, R36, R38, R39)."""
        key = normalize(name)
        matches = self._candidates(key)
        alias = None
        if not matches:
            matches = [
                rel
                for rel, note in self.notes.items()
                if key in {normalize(other) for other in note.parsed.aliases}
            ]
            alias = name.strip() if matches else None
        matches.sort(key=_depth_then_path)
        if not matches:
            return Resolution(name, None)
        return Resolution(name, matches[0], alias, tuple(matches[1:]))

    def linked_mentions(self, found: Resolution) -> dict[str, list[int]]:
        """Source note -> lines of its links to the note (R40-R42, R44)."""
        if found.path is None:
            names = {normalize(found.name)}  # R40: an unwritten note
        else:
            names = {
                normalize(alias) for alias in self.notes[found.path].parsed.aliases
            }
        mentions: dict[str, list[int]] = {}
        for rel, note in self.notes.items():
            if rel == found.path:
                continue  # R44
            for link in note.parsed.links:
                target = self.resolve_link(link.target, rel)
                if target is None:
                    hit = normalize(link.target) in names  # R42
                else:
                    hit = target == found.path
                if hit:
                    lines = mentions.setdefault(rel, [])
                    if link.line not in lines:
                        lines.append(link.line)
        return mentions

    def unlinked_mentions(self, found: Resolution) -> dict[str, list[int]]:
        """Source note -> lines that name the note in plain text (R52)."""
        if found.path is None:
            return {}
        terms = [PurePosixPath(found.path).stem, *self.notes[found.path].parsed.aliases]
        pattern = _term_pattern(terms)
        mentions: dict[str, list[int]] = {}
        for rel, note in self.notes.items():
            if rel == found.path:
                continue
            lines = [
                number
                for number, text in enumerate(note.parsed.lines, start=1)
                if pattern.search(unicodedata.normalize("NFC", text))
            ]
            if lines:
                mentions[rel] = lines
        return mentions

    def covered_by(self, entry: str) -> dict[str, str]:
        """Notes a `paths` entry covers, each with the normalized folder or note path
        it matched (spec 6.0 Path match)."""
        key = normalize(entry).removeprefix("./").strip("/")
        covered: dict[str, str] = {}
        if not key:
            return covered
        for rel, rel_key in self._keys.items():
            parts = rel_key.split("/")
            for depth in range(1, len(parts) + 1):
                candidate = "/".join(parts[:depth])
                if candidate == key or candidate.endswith("/" + key):
                    covered[rel] = candidate
                    break
        return covered
