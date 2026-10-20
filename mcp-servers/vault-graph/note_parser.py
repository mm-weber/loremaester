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

    def heading_path(self, line: int) -> list[str]:
        """Texts of the headings whose sections hold `line`, outermost first; a
        heading on `line` itself is left out (R31)."""
        chain: list[Heading] = []
        for heading in self.headings:
            if heading.line > line:
                break
            while chain and chain[-1].level >= heading.level:
                chain.pop()
            if heading.line < line:
                chain.append(heading)
        return [heading.text for heading in chain]

    def lead(self) -> tuple[int, int] | None:
        """Lines of the lead (spec 6.0 Terms), or None when there is none."""
        start = self.frontmatter[1] + 1 if self.frontmatter else 1
        while start <= len(self.lines) and not self.lines[start - 1].strip():
            start += 1
        headings = [h for h in self.headings if h.line >= start]
        if headings and headings[0].line == start and headings[0].level == 1:
            start += 1
            headings = headings[1:]
        end = headings[0].line - 1 if headings else len(self.lines)
        while start <= end and not self.lines[start - 1].strip():
            start += 1
        while end >= start and not self.lines[end - 1].strip():
            end -= 1
        return (start, end) if start <= end else None

    def masked_text(self, line: int) -> str:
        """Body text of a line for unlinked matching: frontmatter and code lines give
        "", and inline code, wikilinks, Markdown links and URLs are blanked out
        (R20, R55)."""
        if self.kinds[line - 1] in ("frontmatter", "code"):
            return ""
        text = self.lines[line - 1]
        for pattern in (_INLINE_CODE, _WIKILINK, _MARKDOWN_LINK, _URL):
            text = pattern.sub(_blank_out, text)
        return text

    def block(self, line: int) -> list[int]:
        """Lines of the Markdown block holding `line` (R23-R29)."""
        kind = self.kinds[line - 1]
        if kind in ("para", "quote"):
            return self._run(line, kind)
        if kind in ("item", "cont"):
            return self._item_block(line)
        if kind == "table":
            return self._table_block(line)
        if kind == "heading":
            return self._heading_block(line)
        if kind == "frontmatter":
            return self._property_block(line)
        return [line]

    def context(self, line: int) -> list[int]:
        """Context lines of a mention on `line`: the first line of its quote run, or
        of each ancestor item and the item a continuation belongs to (spec 6.0
        Context line)."""
        kind = self.kinds[line - 1]
        if kind == "quote":
            first = self._run(line, kind)[0]
            return [first] if first < line else []
        if kind not in ("item", "cont"):
            return []
        owner = self._owner(line)
        ancestors = [number for number in self.block(line) if number < owner]
        return ancestors + ([owner] if owner != line else [])

    def _run(self, line: int, kind: str) -> list[int]:
        """The run of adjacent lines of one kind around `line`."""
        start = end = line
        while start > 1 and self.kinds[start - 2] == kind:
            start -= 1
        while end < len(self.lines) and self.kinds[end] == kind:
            end += 1
        return list(range(start, end + 1))

    def _owner(self, line: int) -> int:
        """The list item whose run holds `line` (R24)."""
        if self.kinds[line - 1] == "item":
            return line
        limit = _indent(self.lines[line - 1])
        for number in range(line - 1, 0, -1):
            text = self.lines[number - 1]
            if not text.strip():
                continue
            indent = _indent(text)
            if self.kinds[number - 1] == "item" and indent < limit:
                return number
            if indent == 0:
                break
            limit = min(limit, indent)
        return line

    def _item_block(self, line: int) -> list[int]:
        """The list item holding `line` plus its deeper lines (R24)."""
        item = self._owner(line)
        base = _indent(self.lines[item - 1])
        end = item
        while (
            end < len(self.lines)
            and self.lines[end].strip()
            and _indent(self.lines[end]) > base
        ):
            end += 1
        lines = list(range(item, max(end, line) + 1))
        depth = base
        for number in range(item - 1, 0, -1):  # R25: ancestors, nearest first
            text = self.lines[number - 1]
            if not text.strip():
                continue
            indent = _indent(text)
            if self.kinds[number - 1] == "item" and indent < depth:
                lines.append(number)
                depth = indent
                if depth == 0:
                    break
            elif indent == 0:
                break  # a line at the margin ends the list
        return sorted(lines)

    def _table_block(self, line: int) -> list[int]:
        """The table's first row, its separator row if any, and this row (R26)."""
        first = line
        while first > 1 and self.kinds[first - 2] == "table":
            first -= 1
        rows = {first, line}
        if (
            first < len(self.lines)
            and self.kinds[first] == "table"
            and _TABLE_SEPARATOR.match(self.lines[first])
        ):
            rows.add(first + 1)
        return sorted(rows)

    def _heading_block(self, line: int) -> list[int]:
        """The heading plus the lines from the next non-blank line up to the next
        blank line or heading (R28)."""
        lines = [line]
        number = line + 1
        while number <= len(self.lines) and self.kinds[number - 1] == "blank":
            number += 1
        while number <= len(self.lines) and self.kinds[number - 1] not in (
            "blank",
            "heading",
        ):
            lines.append(number)
            number += 1
        return lines

    def _property_block(self, line: int) -> list[int]:
        """The frontmatter property holding `line`: its key line plus its indented
        or list continuation lines (R29)."""
        first, last = self.frontmatter
        if line in (first, last):
            return [line]
        key = line
        while key > first + 1 and not _YAML_KEY.match(self.lines[key - 1]):
            key -= 1
        end = key
        while end + 1 < last and not _YAML_KEY.match(self.lines[end]):
            end += 1
        return list(range(key, end + 1))


def _aliases(frontmatter: str) -> list[str]:
    """Aliases from the `aliases` and `alias` keys, each a list or one string (R18)."""
    try:
        data = yaml.safe_load(frontmatter)
    except Exception:  # bad syntax, tags, dates or nesting: PyYAML raises many types
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
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]")
_THEMATIC_BREAK = re.compile(
    r"^[ \t]*(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$"
)
_TABLE_SEPARATOR = re.compile(r"^[ \t]*\|[ \t|:-]*-[ \t|:-]*$")
_YAML_KEY = re.compile(r"^[^\s#-][^:]*:")


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
            if list_indent is not None and _indent(line) <= list_indent:
                list_indent = None
            continue
        kind = _kind(line)
        if kind == "item":
            indent = _indent(line)
            list_indent = indent if list_indent is None else min(list_indent, indent)
        elif (
            list_indent is not None and kind != "blank" and _indent(line) > list_indent
        ):
            if kind == "para":
                kind = "cont"  # other kinds keep their own kind inside the list
        else:
            list_indent = None
        kinds.append(kind)
    return kinds


_WIKILINK = re.compile(r"!?\[\[([^\[\]\n]+?)\]\]")
_ALIAS_SEPARATOR = re.compile(r"\\?\|")


_INLINE_CODE = re.compile(r"`+[^`\n]*`+")
_MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\([^)\n]*\)")
_URL = re.compile(r"(?:https?|ftp)://\S+|www\.\S+")


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
    lines = _LINE_BREAK.split(text)
    if lines and not lines[-1]:
        lines.pop()  # a final line break ends the last line; it starts no new one
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
