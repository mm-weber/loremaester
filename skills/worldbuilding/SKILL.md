---
name: worldbuilding
description: Use when creating or expanding worldbuilding content — locations, NPCs, factions, lore entries, quests, or items for a TTRPG campaign managed in an Obsidian vault. Triggers on any request to create, describe, detail, or flesh out campaign world elements, even if the user doesn't explicitly say "worldbuilding". Also use when the user asks to research source books, cross-reference lore, or add new notes to their vault.
---

# Worldbuilding Assistant

Orchestrate Obsidian vault navigation, source book research, and TTRPG content generation. The GM's vault is the single source of truth — source books provide inspiration, never override what's already established.

## Workflow

Every worldbuilding request follows four steps. Some requests (pure research, quick lookups) may only need steps 1–2. Use judgment about which steps apply.

### Step 1: Gather Vault Context

Before generating anything, understand what already exists. The vault is canon.

1. **Search the graph** for related notes:
   - `vault_search_notes(name_pattern="topic")` to find notes by name
   - `vault_search_notes(tag="faction")` or `vault_search_notes(note_type="NPC")` to find by category
   - `vault_central_notes(tag="location")` to find the most-connected notes in a category

2. **Map connections** around the topic:
   - `vault_graph(note="Note Name", depth=2)` to see how a note connects to the rest of the world
   - `vault_backlinks(note="Note Name")` to see what references this note

3. **Read primary notes** — Read the most relevant notes found above. Follow wikilinks 1–2 levels deep to build context:
   - Read the note itself
   - Read notes it links to (first-level wikilinks)
   - Optionally read one more level if the topic is broad

4. **Search for mentions** across the vault:
   - Grep for `[[Topic Name]]` to find every note that references this concept
   - Grep frontmatter fields like `faction: "Name"` or `location: "Place"` for structured references

5. **Summarize** what's established before proceeding. Note any contradictions or gaps.

### Step 2: Research Source Books

Use the sourcebooks MCP server to find relevant published material.

1. **Broad search**: `search_lore(query="topic keywords")` for general results
2. **Filtered search**: Narrow with `book` and `content_type` when results are too broad:
   - `search_lore(query="dwarven politics", book="Dwarf Kingdoms Sourcebook")`
   - `search_lore(query="undead", content_type="bestiary")`
3. **Deep dive**: `get_chapter(book="Book Title", chapter="Chapter 3")` when you need full chapter context
4. **Discover sources**: `list_books()` if unsure what source books are available

Content types for filtering: `lore`, `rules`, `bestiary`, `adventure`, `setting`, `appendix`

### Step 3: Generate Content

Combine vault context and source book research to create new worldbuilding content.

**Canon hierarchy** — this is non-negotiable:
- The GM's vault is **CANON**. Never contradict established facts, relationships, or characterizations.
- Source books are **INSPIRATION**. Adapt ideas to fit the GM's world. Don't copy verbatim — reinterpret through the lens of what already exists in the vault.

**Writing rules:**
- Create `[[wikilinks]]` to every existing note you reference. Use Title Case with spaces: `[[Captain Aldric]]`, `[[Sellen River]]`, `[[Ironhold Council]]`
- For display text variants use `[[Note Name|display text]]`
- Follow the vault's frontmatter schema for the note type (see Frontmatter Reference below)
- Use the vault's tag conventions in the frontmatter `tags:` array
- Match the GM's existing voice and writing style — read a few existing notes to calibrate tone
- When in doubt about a creative decision, present options to the GM rather than choosing

### Step 4: Write to Vault

Only reach this step when the GM wants content saved to the vault.

1. **Place the note** in the correct folder based on its type:
   | Type | Folder |
   |------|--------|
   | NPC | `{Campaign}/NPC/` |
   | Location/place | `{Campaign}/Locations/` |
   | Faction | `{Campaign}/Factions/` |
   | Session log | `{Campaign}/Sessions/` |
   | Lore/background | `{Campaign}/Background/` |
   | Rules | `{Campaign}/Rules/` |
   | PC | `{Campaign}/PC/` |

   Encounter notes typically live as scene sub-files under `{Campaign}/Sessions/Session N/`, not in a standalone Encounters/ folder.

2. **Include full frontmatter** matching the vault's schema for that note type

3. **Update related notes** — add `[[wikilinks]]` pointing to the new note in any existing notes that should reference it. Ask before modifying existing notes.

4. **Refresh the graph**: call `vault_rebuild_graph()` so the graph index reflects the new content. This re-parses the vault and reloads the cache in one step. (Note: `vault_reload_cache()` only re-reads the existing `.graph.json` — it won't pick up newly-written notes.)

5. **Present a summary** to the GM:
   - What note was created (with path)
   - What existing notes were updated with backlinks
   - What `[[wikilinks]]` were created in the new note
   - Any decisions you made that the GM should review

## Rules

These apply at every step:

- **Ask before overwriting.** If a note already exists at the target path, show the GM what would change and get confirmation.
- **Wikilink everything.** Every reference to a known concept gets a `[[wikilink]]`. This is how the vault stays navigable.
- **Vault > Source books.** If a source book says dwarves are isolationist but the vault establishes them as traders, the vault wins. Always.
- **Adapt, don't copy.** Source book material should be reinterpreted to fit the GM's world, not pasted in.
- **Match the voice.** Read existing notes to understand how the GM writes — formal or casual, terse or detailed, first-person or third-person — and match it.

## Frontmatter Reference

Use the vault's CLAUDE.md for the definitive schema. These are the common types:

**NPC:**
```yaml
type: NPC
aliases: []
faction: ""
location: ""
race: ""
class: ""
level: 0
gender: ""
deceased: false
tags: [npc]
```

**Location (place):**
```yaml
type: place
aliases: []
faction: ""
location: ""
description: ""
tags: [location]
```

**Faction:**
```yaml
type: Faction
aliases: []
faction: []
location: []
description: ""
alignment: []
tags: [faction]
```

Always check the vault's own CLAUDE.md for the full schema — the GM may have customized fields.

## Tag Conventions

Standard tags in frontmatter `tags:` array:
`#npc`, `#location`, `#faction`, `#lore`, `#quest`, `#item`, `#session`
