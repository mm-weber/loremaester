"""Vault Graph MCP server — navigate the vault's wikilink graph."""

import json
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Vault Graph")

VAULT_PATH = os.environ.get("VAULT_PATH", "/workspace/vault")
GRAPH_PATH = os.path.join(VAULT_PATH, ".graph.json")

_graph = {"nodes": {}, "edges": [], "metadata": {}}


def _load_graph():
    """Load .graph.json from disk into module-level _graph."""
    global _graph
    with open(GRAPH_PATH, "r") as f:
        _graph = json.load(f)


try:
    _load_graph()
except (FileNotFoundError, json.JSONDecodeError):
    pass


@mcp.tool()
async def vault_graph(note: str, depth: int = 2) -> str:
    """BFS from a note up to depth hops, showing outgoing and incoming connections per level."""
    return None


@mcp.tool()
async def vault_backlinks(note: str) -> str:
    """Show all notes that link to the given note."""
    return None


@mcp.tool()
async def vault_central_notes(tag: str = None, limit: int = 10) -> str:
    """Rank notes by connection count (degree centrality), with optional tag filter."""
    return None


@mcp.tool()
async def vault_search_notes(name_pattern: str = None, tag: str = None, note_type: str = None, limit: int = 20) -> str:
    """Search notes by name, tag, and/or type with AND logic."""
    return None


@mcp.tool()
async def vault_reload_graph() -> str:
    """Reload .graph.json from disk without restarting the server."""
    return None


if __name__ == "__main__":
    mcp.run()
