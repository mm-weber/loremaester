---
name: chronik
description: Use when the GM asks to update, extend, or fix the Campaign Chronicle (Campaign_Chronicle.md) from PlayerNotes. Triggers on requests to add a session to the chronicle, summarize player notes into the campaign record, or fix missing details in existing chronicle entries. The core discipline is preserving precise information exchange details — who told whom what, what was withheld, what intelligence each party gained.
---

# Campaign Chronicle Update Assistant

Update the Campaign Chronicle from PlayerNotes with strict information-exchange precision. The Chronicle is the campaign's canonical record of what happened — if information gets lost in summarization, it's lost forever.

## The Cardinal Rule

> **For every NPC interaction in the Chronicle, a reader must be able to answer: "What exactly does each party know after this conversation that they didn't know before?"**

If the Chronicle entry doesn't answer that question, it's incomplete.

## Source of Truth Hierarchy

Per the vault's CLAUDE.md:
1. **PlayerNotes** = what HAPPENED (player actions, canon)
2. **In-game calendar / dates** = when events occurred (canon)
3. **Session prep files** = what was PLANNED (context, may or may not be canon depending on player actions)

The Chronicle synthesizes all three, but PlayerNotes always win on what occurred.

## Workflow

### Phase 1: Read and Identify

1. **Read the PlayerNotes** for the target session(s)
2. **Read all linked Session prep files** — find the session folder under `Sessions/Session N/` and read every sub-file. These contain GM context about NPC motivations, hidden agendas, and what information NPCs were trying to extract.
3. **Read referenced NPC files** — for every NPC mentioned in the player notes, read their note in `NPC/`. Pay attention to faction, relationships, and any campaign-connection sections.
4. **Check in-game dates** — if the vault tracks dates (e.g. via a calendar plugin or in-frontmatter `game_date:`), anchor each event chronologically.

### Phase 2: Extract Information Exchange Events

For EVERY scene where a PC talks to an NPC, build this matrix:

```
Scene: [PC] meets [NPC] at [Location]
├── What PC SHARED (explicitly stated in PlayerNotes)
│   └── List each piece of information with the exact phrasing from the notes
├── What PC WITHHELD or REFUSED to share
│   └── Note what was asked for and refused, with the reason if given
├── What NPC GAINED (cross-ref with Session prep — did the NPC learn something they were specifically after?)
│   └── Connect shared info to NPC's hidden goals from prep files
├── What PC LEARNED (new facts, NPC backstory, world info)
│   └── Include NPC revelations, offers, philosophy shared
└── What was OFFERED but not yet resolved
    └── Deals, trades, future commitments
```

**Critical:** PlayerNotes are written colloquially with typos and phonetic spellings. Cross-reference NPC and location names against existing vault notes to get canonical spellings.

### Phase 3: Draft the Chronicle Entry

Write the entry following the established Chronicle format:
- `### ~[Date] [Month] — [Event Title]` headings
- Bullet points with `[[wikilinks]]` to all NPCs, locations, factions
- **Bold section markers** for information exchange: use `**What [PC] shared:**`, `**What [NPC] learned:**`, `**What [PC] did NOT share:**` when a scene involves significant information exchange
- Keep entries factual and precise — the Chronicle is not prose, it's a record

### Phase 4: Cross-Reference Check

Before presenting the draft, verify against the PlayerNotes:

- [ ] Every NPC interaction has its information exchange captured
- [ ] Every deal/offer/refusal is recorded with both sides
- [ ] No intelligence gained by NPCs is omitted (cross-ref with Session prep hidden goals)
- [ ] No new facts learned by PCs are omitted
- [ ] In-game dates are consistent with any vault-tracked calendar
- [ ] All entity names use canonical vault spellings with correct `[[wikilinks]]`
- [ ] Metadata from PlayerNotes (XP, skill training, downtime activities) is translated into narrative facts where relevant (e.g., "5 XP for [[PC One]]" becomes training/downtime activities)

### Phase 5: Present and Write

1. **Show the draft** to the GM with the information exchange matrix for review
2. **Apply edits** based on GM feedback
3. **Write** to `PC/Campaign_Chronicle.md` in the correct chronological position
4. **Commit with a descriptive message** if the vault is git-tracked

## Common Pitfalls to Avoid

1. **Flattening conversations into "they met and talked"** — the whole point of this skill is to prevent this
2. **Missing what NPCs learned** — PlayerNotes only show the player's POV. Cross-reference Session prep to understand what the NPC was fishing for and whether they got it
3. **Conflating "offered" with "accepted"** — if a deal was offered but refused, both the offer AND the refusal must be in the Chronicle
4. **Losing the reason for refusals** — "[[PC One]] refused" is incomplete. "[[PC One]] refused because [[PC Two]] argued the information was more valuable" is precise
5. **Ignoring accidental information leaks** — if a PC mentioned something in passing that an NPC reacted to (per player notes), that's intelligence the NPC gained, even if the PC didn't intend to share it

## Updating Existing Entries

When fixing an existing Chronicle entry (not writing a new one):
1. Read the current entry
2. Read the corresponding PlayerNotes
3. Build the information exchange matrix
4. Identify what's missing from the current entry
5. Rewrite only the affected section, preserving surrounding entries
