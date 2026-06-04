# Worldbuilding skill — evaluation workspace

This directory holds an **A/B evaluation** of the [`worldbuilding` skill](../worldbuilding/SKILL.md).
Each scenario was run twice against the same fixture vault — once **with** the skill active and once
**without** it (baseline Claude Code) — so you can read the two outputs side by side and judge what
the skill adds.

These are **illustrative, qualitative** comparisons (the `assertions` arrays are intentionally empty —
this is a read-and-compare exhibit, not an automated pass/fail suite). All world content
(`Eryndor`, `Ironhold`, `Thrain Ironbeard`, …) is a small **fictional test fixture**, unrelated to any
real campaign.

## Layout

```
worldbuilding-workspace/
└── iteration-1/
    ├── eval-create-faction/      # scenario 1
    │   ├── eval_metadata.json    # { eval_id, eval_name, prompt, assertions }
    │   ├── with_skill/outputs/   # output.md (run log) + generated note(s)
    │   └── without_skill/outputs/
    ├── eval-expand-location/     # scenario 3
    │   ├── eval_metadata.json
    │   ├── with_skill/outputs/
    │   └── without_skill/outputs/
    └── eval-research-lore/       # scenario 2 (research only — no note written)
        ├── eval_metadata.json
        ├── with_skill/outputs/
        └── without_skill/outputs/
```

In each `outputs/` folder, `output.md` is the **run log** (what the agent did, step by step), and any
other `*.md` (e.g. `Ironhold_Council.md`, `Ironhold-expanded.md`) is the **generated vault note**.

## The scenarios

| Folder | `eval_id` | Task given to the agent |
|---|---|---|
| `eval-create-faction` | 1 | Create a Faction note for the *Ironhold Council* and save it to the vault. |
| `eval-research-lore` | 2 | Research what the source books say about dwarven politics/governance (no note written). |
| `eval-expand-location` | 3 | Flesh out the *Ironhold* city note with districts, landmarks, and daily life. |

## How to read a comparison

1. Open a scenario's `eval_metadata.json` to see the exact `prompt`.
2. Read `with_skill/outputs/output.md` vs `without_skill/outputs/output.md` (the run logs).
3. Compare the generated note(s) in each `outputs/` folder.

## What the comparison shows

Across these runs, the skill-driven outputs consistently:

- **Follow the skill's 4-step workflow** — gather vault context → research source books → generate →
  write back — visible as explicit steps in the `with_skill` run logs, versus ad-hoc behavior in the baseline.
- **Honor the vault's schema and canon** — full frontmatter (including `world` / `campaign` pulled from
  the vault's `CLAUDE.md`) and content that stays consistent with existing notes, rather than a partial,
  reinvented frontmatter.
- **Wikilink thoroughly** — link every referenced entity (existing *and* not-yet-created), keeping the
  graph connected; the baseline links fewer and misses planned notes.
- **Surface decisions for the GM** — the `with_skill` faction note ends with an explicit
  "Decisions for GM Review" section (alignment, aliases, inferred governance model) flagging creative
  additions for confirmation; the baseline does not.

See [`../worldbuilding/SKILL.md`](../worldbuilding/SKILL.md) for the skill definition these runs exercise.
