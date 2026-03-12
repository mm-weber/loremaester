"""Vault Graph MCP server — navigate the vault's wikilink graph."""

import json
import os
from collections import deque

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Vault Graph")

VAULT_PATH = os.environ.get("VAULT_PATH", "/workspace/vault")
GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")

_graph = {"nodes": {}, "edges": [], "metadata": {}}


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
            return "Error: .graph.json not found. Run build-vault-graph.py first to generate it."
        try:
            with open(GRAPH_PATH, "r") as f:
                json.load(f)
        except json.JSONDecodeError:
            return "Error: .graph.json is malformed (invalid JSON). Re-run build-vault-graph.py."
        return "Error: Graph is empty or not loaded."
    return None


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
async def vault_reload_graph() -> str:
    """Reload .graph.json from disk without restarting the server."""
    global VAULT_PATH, GRAPH_PATH
    VAULT_PATH = os.environ.get("VAULT_PATH", "/workspace/vault")
    GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")
    try:
        _load_graph()
    except FileNotFoundError:
        return "Error: .graph.json not found. Run build-vault-graph.py first."
    except json.JSONDecodeError:
        return "Error: .graph.json is malformed (invalid JSON)."
    except Exception as e:
        return f"Error reloading graph: {e}"

    count = _graph.get("metadata", {}).get("note_count", len(_graph.get("nodes", {})))
    edges = _graph.get("metadata", {}).get("edge_count", len(_graph.get("edges", [])))
    return f"Graph reloaded successfully. {count} notes, {edges} edges."


if __name__ == "__main__":
    mcp.run()
