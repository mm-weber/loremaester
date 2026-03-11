"""Vault Graph Builder — parse Obsidian vault into .graph.json."""
import sys, json, re
from pathlib import Path
from datetime import datetime, timezone
import yaml

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]')


def extract_wikilinks(content: str) -> list[str]:
    return WIKILINK_RE.findall(content)


def parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {"tags": [], "type": None}
    second = content.find("---", 3)
    if second == -1:
        return {"tags": [], "type": None}
    yaml_str = content[3:second]
    try:
        data = yaml.safe_load(yaml_str)
    except Exception:
        return {"tags": [], "type": None}
    if not isinstance(data, dict):
        return {"tags": [], "type": None}
    tags = data.get("tags")
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        tags = [tags]
    note_type = data.get("type")
    return {"tags": tags, "type": note_type}


def build_graph(vault_path: str) -> dict:
    vault = Path(vault_path)
    nodes = {}
    for md_file in vault.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(content)
        links_to = extract_wikilinks(content)
        name = md_file.stem
        rel_path = md_file.relative_to(vault).as_posix()
        nodes[name] = {
            "path": rel_path,
            "tags": fm["tags"],
            "type": fm["type"],
            "links_to": links_to,
            "linked_from": [],
        }
    # Second pass: populate linked_from
    for name, node in nodes.items():
        for target in node["links_to"]:
            if target in nodes:
                nodes[target]["linked_from"].append(name)
    # Build edges
    edges = [
        {"source": name, "target": link}
        for name in nodes
        for link in nodes[name]["links_to"]
    ]
    metadata = {
        "vault_path": str(vault.resolve()),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "note_count": len(nodes),
        "edge_count": len(edges),
    }
    return {"nodes": nodes, "edges": edges, "metadata": metadata}


def main():
    if len(sys.argv) < 2:
        print("Usage: build_vault_graph.py <vault_path>", file=sys.stderr)
        sys.exit(1)
    vault_path = sys.argv[1]
    graph = build_graph(vault_path)
    output = Path(vault_path) / ".graph.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    print(
        f"Graph built: {graph['metadata']['note_count']} notes, "
        f"{graph['metadata']['edge_count']} edges → {output}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
