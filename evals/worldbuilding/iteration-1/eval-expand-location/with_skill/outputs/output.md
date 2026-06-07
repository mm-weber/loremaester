# Worldbuilding Skill — Expand Location: Ironhold

## Step 1: Gather Vault Context

### MCP Calls (Simulated — servers unavailable)

**vault_search_notes:**
- `vault_search_notes(name_pattern="Ironhold")` — would return `Eryndor/Locations/Ironhold.md`
- `vault_search_notes(tag="location")` — would list all location notes in the vault

**vault_graph:**
- `vault_graph(note="Ironhold", depth=2)` — would show connections: Ironhold -> Iron Mountains, Ironhold Council, Hall of Ancestors, Thrain Ironbeard, Ironbeard Clan, Dwarven Clans, Eryndor; and second-level links from Thrain -> Bera Stonefist, Merchant Guild, Dark Winter, Goblin Siege of 1847

**vault_backlinks:**
- `vault_backlinks(note="Ironhold")` — would return notes that link *to* Ironhold. Found: `Thrain Ironbeard.md` references `[[Ironhold]]`.

### Notes Read

1. **Ironhold.md** (`Eryndor/Locations/Ironhold.md`) — Exists. A dwarven city in the Iron Mountains, 2000+ years old, ruled by the Ironhold Council (5 clan elders), led by Thrain Ironbeard. Controls the richest mithril veins in Eryndor. Short note with no districts, landmarks, or daily life.

2. **Thrain Ironbeard.md** (`Eryndor/NPC/Thrain Ironbeard.md`) — Exists. Traditionalist council head, 40-year tenure, guided city through Dark Winter and Goblin Siege of 1847. Rival: Bera Stonefist (modernizer). Recently approved increased trade with Merchant Guild.

3. **Linked notes that DO NOT exist yet:**
   - `Iron Mountains` (location, no note)
   - `Ironhold Council` (faction, no note)
   - `Hall of Ancestors` (location, no note)
   - `Ironbeard Clan` (faction, no note)
   - `Dwarven Clans` (faction, no note)
   - `Bera Stonefist` (NPC, no note)
   - `Merchant Guild` (faction, no note)
   - `Dark Winter` (lore, no note)
   - `Goblin Siege of 1847` (lore, no note)

### Established Canon (must not contradict)

- Ironhold is carved into the Iron Mountains
- Over 2000 years old
- Ruled by the Ironhold Council (5 clan elders)
- Current head: Thrain Ironbeard (traditionalist)
- Council rival: Bera Stonefist (modernizer)
- Controls richest mithril veins in Eryndor
- Hall of Ancestors is where the council meets
- Increased trade with the Merchant Guild in recent years
- Survived the Dark Winter and the Goblin Siege of 1847
- The city is the heart of dwarven civilization

### Gaps Identified

- No districts or city layout
- No landmarks beyond the Hall of Ancestors
- No daily life details
- No description of trade, markets, or economy beyond mithril
- No mention of population, defenses, or infrastructure

---

## Step 2: Research Source Books

### MCP Calls (Simulated — sourcebooks server unavailable)

I would make the following calls to the sourcebooks MCP server:

1. **`list_books()`** — Discover what source books are available in the collection.

2. **`search_lore(query="dwarven city districts layout")`** — Broad search for how dwarven cities are typically organized in the source material: vertical tiers, clan quarters, industrial zones, etc.

3. **`search_lore(query="dwarven stronghold daily life culture")`** — Research daily routines, crafting culture, religious practices, food and drink, music, social customs.

4. **`search_lore(query="dwarven city landmarks great forge hall")`** — Search for notable dwarven landmarks: great forges, throne rooms, mine entrances, deep roads, vaults.

5. **`search_lore(query="mithril mining dwarven economy trade")`** — Since Ironhold controls mithril veins, research how mithril mining shapes a city's economy and politics.

6. **`search_lore(query="dwarven defenses fortification gates")`** — Research defensive architecture for a 2000-year-old mountain stronghold.

7. **`search_lore(query="dwarven clans politics council governance", content_type="lore")`** — Filtered search for governance structures to flesh out the Ironhold Council.

Since the MCP server is unavailable, I will draw on genre-standard dwarven city tropes adapted to the established canon: vertical city carved into rock, organized by function and clan, centered on mining and smithing, with a tension between tradition and modernization already established in the vault.

---

## Step 3: Generate Content

### Design Decisions

The existing note establishes a traditionalist-vs-modernizer tension (Thrain vs Bera). The expanded content should reflect this in the city's physical layout — older deep districts vs. newer surface-facing areas. The mithril economy and 2000-year history give us a foundation for layered districts built over centuries.

I'm proposing:
1. **Expand the existing Ironhold.md** with districts, landmarks, and daily life sections
2. **Offer** (not auto-create) supplementary notes the GM might want

### Proposed Expanded Ironhold Note

See `Ironhold-expanded.md` in this outputs directory.

### Proposed Options for the GM

The expanded note references several entities that don't have their own notes yet. I'd recommend creating notes for the most significant ones:

**High priority (referenced heavily):**
- `Ironhold Council` — faction note, since it's central to governance
- `Hall of Ancestors` — location note, the most important landmark

**Medium priority (new content):**
- `The Crucible` — the great forge district
- `Deep Market` — trade hub

**Lower priority (existing wikilinks without notes):**
- `Iron Mountains`, `Ironbeard Clan`, `Dwarven Clans`, `Bera Stonefist`, `Merchant Guild`

I would present these options to the GM and only create them on request.

---

## Step 4: Write to Vault

### What was done

1. **Expanded note written:** `Ironhold-expanded.md` saved to this outputs directory. This is the proposed replacement for `/tmp/test-vault/Eryndor/Locations/Ironhold.md`.

2. **No existing notes were modified** without GM confirmation. The following notes would benefit from adding a `[[Ironhold]]` backlink, but none exist yet to modify.

3. **Wikilinks created in the expanded note:**
   - Existing notes: `[[Thrain Ironbeard]]`
   - Existing wikilinks preserved: `[[Iron Mountains]]`, `[[Ironhold Council]]`, `[[Hall of Ancestors]]`, `[[Ironbeard Clan]]`, `[[Dwarven Clans]]`, `[[Eryndor]]`, `[[Merchant Guild]]`
   - New wikilinks: `[[The Crucible]]`, `[[Deep Market]]`, `[[Mithril Gate]]`, `[[Bera Stonefist]]`, `[[Deep Roads]]`, `[[Goblin Siege of 1847]]`, `[[Dark Winter]]`

4. **`vault_reload_graph()`** would be called after writing to refresh the graph index.

### Decisions for GM Review

- **District names and layout** are new creative content not established in canon. The GM should review whether the five-district structure fits their vision.
- **The Crucible, Deep Market, Mithril Gate** are new named locations. If the GM has other ideas for landmark names, these can be changed.
- **Population estimate (15,000)** is invented. GM should adjust to fit their world's scale.
- **Daily life details** (three-shift cycle, stone bread, deep mushrooms) are genre-flavored inventions. All can be revised.
- **The political tension** between Thrain and Bera is reflected in the districts (Lower Holds as Bera's power base vs. Deep Halls as traditionalist territory). This should be confirmed as the GM's intent.
