# Worldbuilding Vault — Claude Code Instructions

<!-- This is an example vault for the bundled Grunvyr_Campaign scaffold. -->
<!-- To start fresh from generic placeholders, use ../../vault-claude-md-template.md instead. -->

## Vault Overview

This is a TTRPG worldbuilding vault managed in Obsidian.

- **System**: Pathfinder 2e
- **World**: Grunvyr
- **Campaign**: Grunvyr_Campaign

## Folder Structure

```
Vault Root/
├── Grunvyr_Campaign/
│   ├── NPC/              # Non-player characters
│   ├── Locations/        # Places, hexes, dungeons
│   ├── Factions/         # Organizations, groups
│   ├── Sessions/         # Session prep + scene sub-files
│   ├── Background/       # Lore, history, world info
│   ├── Rules/            # House rules, references
│   ├── Visualizations/   # Image-prompt notes for scene art, maps, NPC portraits
│   ├── Draft/            # WIP notes not yet canon
│   └── PC/               # Player characters
│       └── PlayerNotes/  # Colloquial notes from players' POV (canonical record of what happened)
├── templates/            # Note templates — see frontmatter schemas below
└── CLAUDE.md             # This file
```

## Available Skills

This vault ships with four Claude skills under `examples/ttrpg/skills/` (copy into `.claude/skills/` to activate):

| Skill | Use for |
|---|---|
| `worldbuilding` | Creating or expanding NPCs, locations, factions, lore. Researches sourcebooks via the `sourcebooks` MCP and navigates the vault via the `vault-graph` MCP. |
| `session-creation` | Preparing a new session: folder, main prep file, scene sub-files. Uses the 8 Steps of the Lazy DM + Situations Checklist (+ optional 5 Room Dungeon). |
| `chronik` | Updating `PC/Campaign_Chronicle.md` from `PC/PlayerNotes/` with strict information-exchange precision. |
| `vault-scout` | Mechanical vault sweeps (find / list / grep / tabulate frontmatter). Dispatches a Haiku subagent to keep main-agent context clean. |

## Note Types & Frontmatter Schemas

Every note MUST begin with a YAML frontmatter block (`---`). Use the correct `type:` field. The `templates/` folder ships matching templates for each.

### NPC

```yaml
---
aliases: []
type: NPC
faction: ""
location: ""
family: ""
relationships: ""
world: Grunvyr
campaign: Grunvyr_Campaign
date: YYYY-MM-DD
description: ""
alignment: ""
race: ""
class: ""
subclass: ""
level: 0
gender: ""
deceased: false
---
```

### Location

```yaml
---
aliases: []
type: place
faction: ""
location: ""
page: ""
world: Grunvyr
campaign: Grunvyr_Campaign
date: YYYY-MM-DD
description: ""
discovery: ""
properties: ""
trigger: ""
---
```

### Faction

```yaml
---
aliases: []
type: Faction
faction: []
location: []
world: Grunvyr
campaign: Grunvyr_Campaign
date: YYYY-MM-DD
description: ""
alignment: []
---
```

### Encounter

```yaml
---
aliases: []
type: Encounter
world: Grunvyr
campaign: Grunvyr_Campaign
date: YYYY-MM-DD
date_ingame: []
pc: []
npc: []
---
```

### Monster

```yaml
---
type: Monster
aliases: []
world: Grunvyr
campaign: Grunvyr_Campaign
date: YYYY-MM-DD
alignment: ""
---
```

### PC

```yaml
---
aliases: []
type: PC
faction: []
location: []
world: Grunvyr
campaign: Grunvyr_Campaign
date: YYYY-MM-DD
description: []
race: []
gender: []
class: []
subclass: []
level: 1
alignment: []
deceased: false
family: []
origin: []
---
```

## Wikilink Conventions

- **Link to a note**: `[[Note Name]]`
- **Link with display text**: `[[Note Name|display text]]`
- **Embed a note**: `![[Note Name]]`
- **Anchor reference**: `^anchor-name` (at end of a block)
- Note names use **Title Case with spaces** (e.g. `[[Captain Aldric]]`, `[[Sellen River]]`)
- Always link to existing notes when referencing known entities

## Tag Conventions

Tags go in the frontmatter `tags:` array. Standard tags:

- `#npc`, `#location`, `#faction` — entity types
- `#lore`, `#quest`, `#item` — content types
- `#session` — session logs

## How to Search This Vault

For one-off lookups, use plain tool calls:

- **Find backlinks** to a note: `Grep` for `[[Note Name]]` across `**/*.md`
- **List notes in a folder**: `Glob` with pattern like `Grunvyr_Campaign/NPC/**/*.md`
- **Traverse the graph**: `Read` a note, follow its `[[wikilinks]]` to related notes
- **Find by type**: `Grep` for `type: NPC` (or `place`, `Faction`, etc.) in frontmatter
- **Find by faction/location**: `Grep` for `faction: Name` or `location: HEX-CODE`

For larger mechanical sweeps (≥5 files, tabulate frontmatter, find all matches of a pattern), prefer the `vault-scout` skill — it dispatches a Haiku subagent so the main context stays clean.

## How to Write New Notes

When creating or editing notes:

1. **Always include frontmatter** with the correct `type` field and all schema fields from the matching template above
2. **Place the file in the right folder** according to the folder structure
3. **Create wikilinks** (`[[...]]`) to every existing note you reference
4. **Update related notes** — add backlinks in referenced notes when relevant (ask before modifying)
5. **Use Title Case with spaces** for the filename (e.g. `Captain Aldric.md`)
6. **Never delete or overwrite** existing notes without being asked
7. **Match the GM's voice** — read a few existing notes to calibrate tone before writing new prose
