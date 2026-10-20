"""Live index of a vault: notes parsed on demand, cached by file stat.

Requirement numbers refer to specs/v0.2/surgical-search.md.
"""

import difflib
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from note_parser import ParsedNote, link_spans, parse_note


def normalize(name: str) -> str:
    """Compare form of a name: NFC, lowercase, trimmed, no trailing .md (R32)."""
    name = unicodedata.normalize("NFC", name).strip().lower()
    return name.removesuffix(".md").strip()


def _depth_then_path(rel: str) -> tuple[int, str]:
    """Sort key: fewest path segments first, then alphabetical (R35, R38)."""
    return rel.count("/"), rel


def _term_pattern(terms: list[str], endings: tuple[str, ...] = ()) -> re.Pattern[str]:
    """Whole-word, case-insensitive match of any term, plus at most one of the
    configured endings (R5, R53)."""
    words = "|".join(
        re.escape(unicodedata.normalize("NFC", term))
        for term in sorted(terms, key=len, reverse=True)
    )
    suffix = ""
    if endings:
        suffix = "(?:" + "|".join(re.escape(ending) for ending in endings) + ")?"
    return re.compile(rf"(?<!\w)(?:{words}){suffix}(?!\w)", re.IGNORECASE)


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

    def _link_names(self, found: Resolution) -> set[str]:
        """Names an unresolved link may use for the note: its aliases, or the
        requested name of an unwritten note (R40, R42)."""
        if found.path is None:
            return {normalize(found.name)}  # R40: an unwritten note
        return {normalize(alias) for alias in self.notes[found.path].parsed.aliases}

    def _links_to(
        self, found: Resolution, names: set[str], target: str, source: str
    ) -> bool:
        """Whether a link target written in `source` points to the note (R40-R42)."""
        resolved = self.resolve_link(target, source)
        if resolved is None:
            return normalize(target) in names  # R42
        return resolved == found.path

    def linked_mentions(self, found: Resolution) -> dict[str, list[int]]:
        """Source note -> lines of its links to the note (R40-R42, R44)."""
        names = self._link_names(found)
        mentions: dict[str, list[int]] = {}
        for rel, note in self.notes.items():
            if rel == found.path:
                continue  # R44
            for link in note.parsed.links:
                if self._links_to(found, names, link.target, rel):
                    lines = mentions.setdefault(rel, [])
                    if link.line not in lines:
                        lines.append(link.line)
        return mentions

    def mention_column(
        self,
        found: Resolution,
        rel: str,
        line: int,
        unlinked: bool = False,
        endings: tuple[str, ...] = (),
    ) -> int:
        """Where the first mention of the note starts on a line of `rel`: a link, or
        in unlinked mode a plain-text match; 0 when none is found (R91)."""
        parsed = self.notes[rel].parsed
        if unlinked:
            pattern = self._unlinked_pattern(found, endings)
            text = unicodedata.normalize("NFC", parsed.masked_text(line))
            match = pattern.search(text) if pattern else None
            return match.start() if match else 0
        names = self._link_names(found)
        for target, column in link_spans(parsed.lines[line - 1]):
            if self._links_to(found, names, target, rel):
                return column
        return 0

    def _unlinked_pattern(
        self, found: Resolution, endings: tuple[str, ...]
    ) -> re.Pattern[str] | None:
        """Plain-text pattern for the note's title and aliases, or None when no term
        has three characters (R52-R54, R57)."""
        if found.path is None:
            terms = [found.name.strip()]  # R57
        else:
            terms = [
                PurePosixPath(found.path).stem,
                *self.notes[found.path].parsed.aliases,
            ]
        terms = [term for term in terms if len(term.strip()) >= 3]  # R54
        return _term_pattern(terms, endings) if terms else None

    def unlinked_mentions(
        self, found: Resolution, endings: tuple[str, ...] = ()
    ) -> dict[str, list[int]]:
        """Source note -> lines that name the note in plain text (R52-R57)."""
        pattern = self._unlinked_pattern(found, endings)
        if pattern is None:
            return {}
        mentions: dict[str, list[int]] = {}
        linked = self.linked_mentions(found)
        for rel, note in self.notes.items():
            if rel == found.path:
                continue
            parsed = note.parsed
            linking = {n for line in linked.get(rel, []) for n in parsed.block(line)}
            lines = [
                number
                for number in range(1, len(parsed.lines) + 1)
                if number not in linking  # R56
                and pattern.search(
                    unicodedata.normalize("NFC", parsed.masked_text(number))
                )
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

    def close_names(self, name: str, limit: int = 5) -> list[str]:
        """Titles and aliases close to an unknown name (spec 6.0 Close names)."""
        key = normalize(name)
        forms: dict[str, str] = {}
        for rel in sorted(self.notes):
            for shown in (PurePosixPath(rel).stem, *self.notes[rel].parsed.aliases):
                forms.setdefault(normalize(shown), shown)
        contained = sorted(
            (form for form in forms if key and key in form),
            key=lambda form: (len(form), form),
        )
        similar = difflib.get_close_matches(key, list(forms), n=limit, cutoff=0.6)
        ranked = contained + [form for form in similar if form not in contained]
        return [forms[form] for form in ranked[:limit]]
