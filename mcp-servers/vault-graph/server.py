"""Vault Graph MCP server — navigate the vault's wikilink graph."""

import importlib.util
import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Vault Graph")

VAULT_PATH = os.environ.get("VAULT_PATH", "/workspace/vault")
GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")

_graph = {"nodes": {}, "edges": [], "metadata": {}}

# Load the builder script by path so vault_rebuild_graph can call it in-process.
# Fail soft: if the builder isn't reachable, the server still starts and the
# other tools work; only vault_rebuild_graph surfaces an error.
_BUILDER_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "build_vault_graph.py"
_builder = None
try:
    _spec = importlib.util.spec_from_file_location("build_vault_graph", _BUILDER_PATH)
    _builder = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_builder)
except Exception:
    _builder = None


def _load_graph():
    """Load .graph.json from disk into module-level _graph."""
    global _graph, GRAPH_PATH
    GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")
    with open(GRAPH_PATH, "r") as f:
        _graph = json.load(f)


try:
    _load_graph()
except (FileNotFoundError, json.JSONDecodeError):
    pass


def _check_graph() -> str | None:
    """Return an error message if the graph is not loaded, else None."""
    if not _graph.get("nodes"):
        if not os.path.exists(GRAPH_PATH):
            return "Error: .graph.json not found. Run vault_rebuild_graph to create it."
        try:
            with open(GRAPH_PATH, "r") as f:
                json.load(f)
        except json.JSONDecodeError:
            return "Error: .graph.json is malformed (invalid JSON). Run vault_rebuild_graph to regenerate."
        return "Error: Graph is empty or not loaded."
    return None


def _staleness_summary() -> str:
    """Return a short warning if vault .md files are newer than .graph.json, else ''."""
    try:
        graph_mtime = os.path.getmtime(GRAPH_PATH)
    except OSError:
        return ""
    newer_count = 0
    newest_mtime = 0.0
    for md in Path(VAULT_PATH).rglob("*.md"):
        try:
            m = md.stat().st_mtime
        except OSError:
            continue
        if m > graph_mtime:
            newer_count += 1
            if m > newest_mtime:
                newest_mtime = m
    if newer_count == 0:
        return ""
    newest_iso = datetime.fromtimestamp(newest_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    return f" STALE: {newer_count} .md file(s) modified since last build (newest: {newest_iso})."


@mcp.tool()
async def vault_graph(note: str, depth: int = 2) -> str:
    """BFS from a note up to depth hops, showing outgoing and incoming connections per level."""
    err = _check_graph()
    if err:
        return err

    depth = max(1, min(depth, 4))
    nodes = _graph["nodes"]

    if note not in nodes:
        return f"Error: Note '{note}' not found in the graph."

    visited = {note}
    queue = deque()
    # Seed with depth-1 neighbors
    node_data = nodes[note]
    for target in node_data.get("links_to", []):
        queue.append((target, 1, "→"))
    for source in node_data.get("linked_from", []):
        queue.append((source, 1, "←"))

    levels = {}  # depth -> list of (name, direction, type)
    while queue:
        name, d, direction = queue.popleft()
        if d > depth:
            continue
        if name in visited:
            continue
        visited.add(name)

        info = nodes.get(name)
        note_type = info["type"] if info else "unknown"
        levels.setdefault(d, []).append((name, direction, note_type))

        if d < depth and info:
            for target in info.get("links_to", []):
                if target not in visited:
                    queue.append((target, d + 1, "→"))
            for source in info.get("linked_from", []):
                if source not in visited:
                    queue.append((source, d + 1, "←"))

    lines = [f"## Graph for: {note}"]
    node_info = nodes[note]
    lines.append(f"Path: {node_info['path']}  |  Type: {node_info['type']}\n")

    if not levels:
        lines.append("No connections found.")
        return "\n".join(lines)

    for d in sorted(levels):
        lines.append(f"### Depth {d}")
        for name, direction, ntype in sorted(levels[d], key=lambda x: x[0]):
            lines.append(f"  {direction} {name} ({ntype})")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def vault_backlinks(note: str) -> str:
    """Show all notes that link to the given note."""
    err = _check_graph()
    if err:
        return err

    nodes = _graph["nodes"]
    if note not in nodes:
        return f"Error: Note '{note}' not found in the graph."

    backlinks = nodes[note].get("linked_from", [])
    if not backlinks:
        return f"No backlinks found for '{note}'."

    lines = [f"## Backlinks for: {note}\n"]
    for bl in sorted(backlinks):
        info = nodes.get(bl)
        if info:
            lines.append(f"- {bl} ({info['type']}) — {info['path']}")
        else:
            lines.append(f"- {bl} (unknown)")
    return "\n".join(lines)


@mcp.tool()
async def vault_central_notes(tag: str = None, limit: int = 10) -> str:
    """Rank notes by connection count (degree centrality), with optional tag filter."""
    err = _check_graph()
    if err:
        return err

    nodes = _graph["nodes"]
    ranked = []
    for name, data in nodes.items():
        if tag and tag not in data.get("tags", []):
            continue
        degree = len(data.get("links_to", [])) + len(data.get("linked_from", []))
        ranked.append((name, degree, data))

    ranked.sort(key=lambda x: (-x[1], x[0]))
    ranked = ranked[:limit]

    if not ranked:
        return "No notes found matching the filter."

    lines = [f"## Most Connected Notes" + (f" (tag: {tag})" if tag else "") + "\n"]
    for name, degree, data in ranked:
        lines.append(f"- {name} — {degree} connections ({data['type']}) — {data['path']}")
    return "\n".join(lines)


@mcp.tool()
async def vault_search_notes(name_pattern: str = None, tag: str = None, note_type: str = None, limit: int = 20) -> str:
    """Search notes by name, tag, and/or type with AND logic."""
    err = _check_graph()
    if err:
        return err

    nodes = _graph["nodes"]
    results = []
    for name, data in nodes.items():
        if name_pattern and name_pattern.lower() not in name.lower():
            continue
        if tag and tag not in data.get("tags", []):
            continue
        raw_type = data.get("type")
        if note_type:
            if isinstance(raw_type, list):
                if not any(t.lower() == note_type.lower() for t in raw_type if isinstance(t, str)):
                    continue
            elif not isinstance(raw_type, str) or raw_type.lower() != note_type.lower():
                continue
        degree = len(data.get("links_to", [])) + len(data.get("linked_from", []))
        results.append((name, data, degree))

    results.sort(key=lambda x: x[0])
    results = results[:limit]

    if not results:
        return "No notes found matching the search criteria."

    lines = [f"## Search Results\n"]
    for name, data, degree in results:
        lines.append(f"- {name} ({data['type']}) — {data['path']} — {degree} connections")
    return "\n".join(lines)


@mcp.tool()
async def vault_reload_cache() -> str:
    """Re-read .graph.json from disk without rebuilding it. Fast. Use after an external rebuild."""
    global VAULT_PATH, GRAPH_PATH
    VAULT_PATH = os.environ.get("VAULT_PATH", "/workspace/vault")
    GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")
    try:
        _load_graph()
    except FileNotFoundError:
        return "Error: .graph.json not found. Run vault_rebuild_graph to create it."
    except json.JSONDecodeError:
        return "Error: .graph.json is malformed (invalid JSON). Run vault_rebuild_graph to regenerate."
    except Exception as e:
        return f"Error reloading cache: {e}"

    count = _graph.get("metadata", {}).get("note_count", len(_graph.get("nodes", {})))
    edges = _graph.get("metadata", {}).get("edge_count", len(_graph.get("edges", [])))
    return f"Cache reloaded: {count} notes, {edges} edges.{_staleness_summary()}"


@mcp.tool()
async def vault_rebuild_graph() -> str:
    """Re-parse the vault, regenerate .graph.json, and reload the cache in one step."""
    global VAULT_PATH, GRAPH_PATH
    VAULT_PATH = os.environ.get("VAULT_PATH", "/workspace/vault")
    GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")
    if _builder is None:
        return (
            f"Error: builder not importable at {_BUILDER_PATH}. "
            "Shell out to `uv run --no-project scripts/build_vault_graph.py <vault>` instead."
        )
    try:
        graph = _builder.build_graph(VAULT_PATH)
        with open(GRAPH_PATH, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2)
        _load_graph()
    except Exception as e:
        return f"Error rebuilding graph: {type(e).__name__}: {e}"
    meta = _graph.get("metadata", {})
    return f"Graph rebuilt: {meta.get('note_count', '?')} notes, {meta.get('edge_count', '?')} edges."


if __name__ == "__main__":
    mcp.run()
