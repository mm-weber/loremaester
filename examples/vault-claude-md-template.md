# Worldbuilding Vault — Claude Code Instructions

<!-- GM: Copy this file to your Obsidian vault root as CLAUDE.md -->
<!-- GM: Replace all placeholder values (YOUR_...) with your actual vault details -->

## Vault Overview

This is a TTRPG worldbuilding vault managed in Obsidian.

- **System**: YOUR_SYSTEM <!-- e.g. Pathfinder 2e, D&D 5e -->
- **World**: YOUR_WORLD <!-- e.g. Golarion, Forgotten Realms -->
- **Campaign**: YOUR_CAMPAIGN <!-- e.g. Kingmaker 2e -->

## Folder Structure

<!-- GM: Update this tree to match your vault layout -->

```
Vault Root/
├── YOUR_CAMPAIGN/
│   ├── NPC/              # Non-player characters
│   ├── Locations/        # Places, hexes, dungeons
│   ├── Factions/         # Organizations, groups
│   ├── Sessions/         # Session logs
│   ├── Background/       # Lore, history, world info
│   ├── Rules/            # House rules, references
│   ├── PC/               # Player characters
│   └── Encounters/       # Combat encounters, events
├── templates/            # Note templates (do not edit)
└── CLAUDE.md             # This file
```

## Note Types & Frontmatter Schemas

Every note MUST begin with a YAML frontmatter block (`---`). Use the correct `type` field.

### NPC

```yaml
---
aliases: []
type: NPC
faction: ""
location: ""
family: ""
relationships: ""
world: YOUR_WORLD
campaign: YOUR_CAMPAIGN
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

<!-- GM: The location field often uses hex codes (e.g. GB-3, TW-5) for hex-crawl campaigns -->

```yaml
---
aliases: []
type: place
faction: ""
location: ""
page: ""
world: YOUR_WORLD
campaign: YOUR_CAMPAIGN
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
world: YOUR_WORLD
campaign: YOUR_CAMPAIGN
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
world: YOUR_WORLD
campaign: YOUR_CAMPAIGN
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
world: YOUR_WORLD
campaign: YOUR_CAMPAIGN
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
world: YOUR_WORLD
campaign: YOUR_CAMPAIGN
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

<!-- GM: Add your custom tags here -->

## How to Search This Vault

- **Find backlinks** to a note: `Grep` for `[[Note Name]]` across `**/*.md`
- **List notes in a folder**: `Glob` with pattern like `YOUR_CAMPAIGN/NPC/**/*.md`
- **Traverse the graph**: `Read` a note, follow its `[[wikilinks]]` to related notes
- **Find by type**: `Grep` for `type: NPC` (or `place`, `Faction`, etc.) in frontmatter
- **Find by faction/location**: `Grep` for `faction: Name` or `location: HEX-CODE`

## How to Write New Notes

When creating or editing notes:

1. **Always include frontmatter** with the correct `type` field and all schema fields
2. **Place the file in the right folder** according to the folder structure above
3. **Create wikilinks** (`[[...]]`) to every existing note you reference
4. **Update related notes** — add backlinks in referenced notes when relevant
5. **Use Title Case with spaces** for the filename (e.g. `Captain Aldric.md`)
6. **Never delete or overwrite** existing notes without being asked
7. **Preserve the GM's language** — match the language used in existing notes
