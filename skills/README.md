# Skills

The Claude Code **skills** this project provides. Each skill is a `SKILL.md` that
Claude Code auto-loads when its description matches your request — no manual
invocation needed.

| Skill | What it does |
|-------|--------------|
| `worldbuilding/` | Synthesize vault canon + sourcebook research into new, frontmatter-correct notes. |
| `session-creation/` | Draft a session with the 8 Steps of the Lazy DM + the Situations Checklist. |
| `chronik/` | Maintain a campaign chronicle, preserving who-told-whom-what across NPC interactions. |
| `vault-scout/` | Dispatch mechanical vault sweeps to a cheaper model, keeping the main context clean. |

## Using them

Copy the skill(s) you want into a Claude Code skills directory:

```bash
# project-local (loads only under this project)
mkdir -p .claude/skills && cp -r skills/worldbuilding .claude/skills/

# or personal (loads everywhere)
cp -r skills/worldbuilding ~/.claude/skills/
```

This is **not** a Claude Code plugin — there is no marketplace manifest. The skills
are plain `SKILL.md` files you copy where you want them.

## Related

- **`examples/ttrpg/skills/`** — a ready-to-use copy of these skills bundled with the
  demo walkthrough (kept in sync with this library). See [`docs/demo-walkthrough.md`](../docs/demo-walkthrough.md).
- **`evals/`** — the evaluation harness measuring skill impact (with-skill vs without-skill).
