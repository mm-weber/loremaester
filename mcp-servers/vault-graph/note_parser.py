"""Pure line scanner for Obsidian notes (spec: specs/v0.2/surgical-search.md)."""

import re
from dataclasses import dataclass, field

import yaml

ATTACHMENT_EXTENSIONS = frozenset(
    [
        "avif",
        "bmp",
        "gif",
        "jpeg",
        "jpg",
        "png",
        "svg",
        "webp",
        "flac",
        "m4a",
        "mp3",
        "ogg",
        "wav",
        "3gp",
        "mkv",
        "mov",
        "mp4",
        "ogv",
        "webm",
        "pdf",
        "canvas",
        "base",
    ]
)


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    line: int  # 1-based


@dataclass(frozen=True)
class Link:
    target: str  # as written: "Note" or "Folder/Note", without text, heading or block
    line: int  # 1-based


@dataclass
class ParsedNote:
    lines: list[str]
    frontmatter: tuple[int, int] | None = None
    aliases: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    headings: list[Heading] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def section(self, heading_line: int) -> tuple[int, int]:
        """First and last line of the section a heading opens (R30)."""
        level = next(h.level for h in self.headings if h.line == heading_line)
        for heading in self.headings:
            if heading.line > heading_line and heading.level <= level:
                return heading_line, heading.line - 1
        return heading_line, len(self.lines)

    def block(self, line: int) -> list[int]:
        """Lines of the Markdown block holding `line` (R23-R29)."""
        kind = self.kinds[line - 1]
        if kind == "para":
            return self._run(line, kind)
        if kind in ("item", "cont"):
            return self._item_block(line)
        return [line]

    def _run(self, line: int, kind: str) -> list[int]:
        """The run of adjacent lines of one kind around `line`."""
        start = end = line
        while start > 1 and self.kinds[start - 2] == kind:
            start -= 1
        while end < len(self.lines) and self.kinds[end] == kind:
            end += 1
        return list(range(start, end + 1))

    def _item_block(self, line: int) -> list[int]:
        """The list item holding `line` plus its deeper lines (R24)."""
        item = line
        if self.kinds[line - 1] == "cont":
            depth = _indent(self.lines[line - 1])
            item = next(
                number
                for number in range(line - 1, 0, -1)
                if self.kinds[number - 1] == "item"
                and _indent(self.lines[number - 1]) < depth
            )
        base = _indent(self.lines[item - 1])
        end = item
        while (
            end < len(self.lines)
            and self.kinds[end] in ("item", "cont")
            and _indent(self.lines[end]) > base
        ):
            end += 1
        return list(range(item, end + 1))


def _aliases(frontmatter: str) -> list[str]:
    """Aliases from the `aliases` and `alias` keys, each a list or one string (R18)."""
    try:
        data = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return []  # R17: the frontmatter text stays, no aliases
    if not isinstance(data, dict):
        return []
    found = []
    for key in ("aliases", "alias"):
        value = data.get(key)
        for alias in value if isinstance(value, list) else [value]:
            if isinstance(alias, str) and alias.strip():
                found.append(alias.strip())
    return found


_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)\s*$")
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]")
_THEMATIC_BREAK = re.compile(
    r"^[ \t]*(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$"
)


def _kind(line: str) -> str:
    """Kind of a line outside code and frontmatter (spec 6.0 Terms)."""
    if not line.strip():
        return "blank"
    if _THEMATIC_BREAK.match(line):
        return "break"
    if _HEADING.match(line):
        return "heading"
    if _LIST_ITEM.match(line):
        return "item"
    first = line.lstrip()[0]
    if first == "|":
        return "table"
    if first == ">":
        return "quote"
    return "para"


def _indent(line: str) -> int:
    """Indentation in columns; a tab counts as four (R24)."""
    width = 0
    for char in line:
        if char == " ":
            width += 1
        elif char == "\t":
            width += 4
        else:
            break
    return width


def _classify(lines: list[str], body_start: int) -> list[str]:
    """One kind per line (spec 6.0 Terms); `cont` marks text that continues a
    list item (R24)."""
    kinds = ["frontmatter"] * body_start
    fence = ""
    list_indent: int | None = None  # smallest item indentation in this list run
    for line in lines[body_start:]:
        opener = _FENCE.match(line)
        if fence:
            if opener and opener.group(1)[0] == fence:
                fence = ""
            kinds.append("code")
            continue
        if opener:
            fence = opener.group(1)[0]
            kinds.append("code")
            list_indent = None
            continue
        kind = _kind(line)
        if kind == "item":
            indent = _indent(line)
            list_indent = indent if list_indent is None else min(list_indent, indent)
        elif kind == "para" and list_indent is not None and _indent(line) > list_indent:
            kind = "cont"
        else:
            list_indent = None
        kinds.append(kind)
    return kinds


_WIKILINK = re.compile(r"!?\[\[([^\[\]\n]+?)\]\]")
_ALIAS_SEPARATOR = re.compile(r"\\?\|")


_INLINE_CODE = re.compile(r"`+[^`\n]*`+")


def _blank_out(match: re.Match[str]) -> str:
    """Replace a match with spaces of the same length."""
    return " " * len(match.group(0))


def _is_attachment(target: str) -> bool:
    """A target ending in a known attachment extension (R22)."""
    _, dot, extension = target.rpartition(".")
    return bool(dot) and extension.lower() in ATTACHMENT_EXTENSIONS


def _links_in(line: str, number: int) -> list[Link]:
    """Wikilinks and embeds on one line, as link targets (R20-R22)."""
    links = []
    for match in _WIKILINK.finditer(_INLINE_CODE.sub(_blank_out, line)):
        target = _ALIAS_SEPARATOR.split(match.group(1), maxsplit=1)[0]
        target = target.split("#", 1)[0].strip()
        if target and not _is_attachment(target):
            links.append(Link(target, number))
    return links


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
    note.kinds = _classify(lines, note.frontmatter[1] if note.frontmatter else 0)
    for number, (line, kind) in enumerate(zip(lines, note.kinds, strict=True), start=1):
        if kind == "heading":
            hashes, title = _HEADING.match(line).groups()
            note.headings.append(Heading(len(hashes), title, number))  # R19
        if kind != "code":
            note.links += _links_in(line, number)  # R20
    return note
