# Research: Dwarven Politics and Governance in Source Books

## Step 1: Vault Context Gathered

Before looking at source books, here is what your vault already establishes as **canon** about dwarven politics and governance:

### Established Facts

**From [[Ironhold]]** (`Eryndor/Locations/Ironhold.md`):
- Ironhold is ruled by the **[[Ironhold Council]]**, a body of **five clan elders**
- The council meets in the **[[Hall of Ancestors]]**
- The current head of the council is **[[Thrain Ironbeard]]**, eldest of the [[Ironbeard Clan]]
- Ironhold is the heart of [[Dwarven Clans|dwarven civilization]]
- The city controls the richest mithril veins in [[Eryndor]]

**From [[Thrain Ironbeard]]** (`Eryndor/NPC/Thrain Ironbeard.md`):
- Thrain has led the council for **nearly forty years**
- He guided the city through the [[Dark Winter]] and the [[Goblin Siege of 1847]]
- He is a **traditionalist** — believes dwarves should focus on craft and mines
- He has **reluctantly approved increased trade** with the [[Merchant Guild]]
- His rival on the council is **[[Bera Stonefist]]**, who pushes for **modernization and closer ties with the surface kingdoms**

### Gaps Identified

The following are referenced via `[[wikilinks]]` but **do not yet have vault notes**:
- **[[Ironhold Council]]** — no dedicated faction note exists yet
- **[[Dwarven Clans]]** — no faction note for the broader dwarven political entity
- **[[Hall of Ancestors]]** — no location note for where the council meets
- **[[Ironbeard Clan]]** — no faction note for Thrain's clan
- **[[Bera Stonefist]]** — no NPC note for Thrain's political rival
- **[[Merchant Guild]]** — no faction note
- **[[Dark Winter]]** and **[[Goblin Siege of 1847]]** — no background/lore notes for these historical events

### Political Dynamics Established So Far

The vault paints a picture of a **five-seat council of clan elders** with a central ideological tension:
- **Traditionalist faction** (Thrain Ironbeard): isolationist, focus on craft and mining
- **Modernist faction** (Bera Stonefist): expansionist, closer ties with surface kingdoms

This is a strong foundation. The council structure, its key players, and the central political conflict are already defined.

---

## Step 2: Source Book Research

The sourcebooks MCP server is currently unavailable. Below are the **exact calls I would make** to research dwarven politics and governance, along with what I would expect to find.

### Call 1: Discover available books

```
list_books()
```

**Purpose:** Identify which source books are in the library that might cover dwarven content — looking for titles like a Dwarf Kingdoms Sourcebook, a core setting guide, or a races/cultures supplement.

### Call 2: Broad search for dwarven politics

```
search_lore(query="dwarven politics governance council clan elders", limit=10)
```

**Purpose:** Cast a wide net across all source books for any content about how dwarven governments work — councils, clan structures, succession, voting, authority.

### Call 3: Filtered search for setting/lore content

```
search_lore(query="dwarven council governance", content_type="setting")
```

**Purpose:** Narrow to setting material specifically, which is most likely to contain political structures and governance models rather than rules or bestiary entries.

### Call 4: Filtered search for lore content

```
search_lore(query="dwarf clan politics leadership succession", content_type="lore")
```

**Purpose:** Search lore-type content for details about how dwarven leadership works — succession rules, clan hierarchy, how council seats are assigned.

### Call 5: Search for dwarven factions and internal conflict

```
search_lore(query="dwarven factions traditionalist modernist isolationist trade", limit=10)
```

**Purpose:** Your vault already establishes a traditionalist vs. modernist tension. This search would find source book material about similar dwarven political divisions that could inspire how the factions operate, what the stakes are, and what happens when they clash.

### Call 6: Search for council mechanics

```
search_lore(query="council of elders dwarven voting authority power structure", limit=5)
```

**Purpose:** Look specifically for mechanical or narrative details about how dwarven councils function — do they vote? Is it consensus-based? Can the head overrule? What triggers a new election or succession?

### Call 7: Deep dive (conditional)

If the broad searches surfaced a specific book with strong dwarven governance content, I would then do a chapter-level pull:

```
get_chapter(book="<book title from results>", chapter="<chapter about dwarven society>")
```

**Purpose:** Get the full chapter text to understand the complete picture rather than just search snippets.

---

## Step 3: Findings and Recommendations

### What Your Vault Establishes (Canon)

| Element | Status | Source |
|---------|--------|--------|
| Council of five clan elders | Established | Ironhold.md |
| Thrain Ironbeard as council head | Established | Thrain Ironbeard.md |
| Hall of Ancestors as meeting place | Named only | Ironhold.md |
| Traditionalist vs. modernist tension | Established | Thrain Ironbeard.md |
| Bera Stonefist as rival voice | Named only | Thrain Ironbeard.md |
| Council has authority over trade policy | Implied | Thrain Ironbeard.md |

### Questions Source Books Could Answer

Since the sourcebooks MCP server is unavailable right now, here are the specific questions you would want the source books to inform (adapted to your vault's canon, never overriding it):

1. **Council mechanics** — How are the five seats assigned? One per clan? By age? By combat? By wealth? Your vault says Thrain is "eldest" which suggests seniority matters.

2. **Succession** — What happens when a council member dies or steps down? Does the clan choose a replacement, or is there a broader election?

3. **Head of council** — Is the head role purely seniority-based (your vault implies this with "eldest"), or does it involve a vote of the other four?

4. **Scope of authority** — The council approved trade with the Merchant Guild. What else falls under their jurisdiction? Military decisions? Religious matters? Mining rights?

5. **The five clans** — Only the Ironbeard Clan is named. Source books might inspire names, specializations, and political leanings for the other four clans.

6. **Historical precedent** — The Dark Winter and Goblin Siege of 1847 are mentioned as events Thrain navigated. Source books could provide models for how councils handle crises — emergency powers, war councils, etc.

7. **Bera Stonefist's platform** — "Modernization and closer ties with the surface kingdoms" is established. Source books could provide texture on what modernization looks like for dwarves and what the political costs are.

### Suggested Next Steps

Once the sourcebooks server is available, I can:
- Run the searches listed above and present the results for you to cherry-pick
- Draft an **[[Ironhold Council]]** faction note that weaves vault canon with source book inspiration
- Create NPC stubs for **[[Bera Stonefist]]** and the other three unnamed council members
- Draft a **[[Dwarven Clans]]** overview note covering the political landscape

Let me know if you want me to proceed with any of these once the source books are searchable, or if you want to draft the council note based on vault canon alone.
