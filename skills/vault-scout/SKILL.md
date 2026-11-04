---
name: vault-scout
description: Use when you need to find, list, or read-and-summarize Obsidian vault notes mechanically — e.g., "find all NPC notes tied to faction X", "list all session N scene files", "read frontmatter of these 12 notes and return a table", "grep all Locations/ notes for wikilinks to [[NPC Name]]". Dispatches a Haiku subagent to keep main-agent context clean and token costs low. Do NOT use for creative work (NPC design, prose, scene architecture) — those stay on the main agent. Triggers on phrases like "find notes that...", "list all...", "show me the frontmatter of...", "what notes link to...".
---

# Vault Scout

A Haiku-backed primitive for mechanical Obsidian-vault exploration. The main agent calls this skill when it needs a structured answer to a search/listing/frontmatter question without polluting its own context with dozens of file reads.

## Why this skill exists

Vault work frequently needs the same kind of mechanical sweep:
- "Find every NPC linked to a given faction"
- "List all notes under `Sessions/Session N/` and their frontmatter types"
- "Grep for `[[Note Name]]` across `Locations/` and show which notes reference it"
- "Read these 12 location notes and tell me which ones have no `discovery:` field"

These tasks are pattern-match + read + tabulate. No creative judgment, no prose generation. Letting the main Opus agent run them is wasteful: the main agent pays Opus prices for Haiku-grade work, and its context fills up with file contents it doesn't need beyond the tabulation.

`vault-scout` dispatches a Haiku subagent with the narrow question, lets Haiku do the scanning in its own context, and receives back a clean tabular or bulleted answer.

## When to use

- The task is **find X** / **list Y** / **read frontmatter and tabulate** / **grep for pattern Z**.
- The answer is a table, bulleted list, or short structured summary — not prose, not creative content.
- The work involves reading many files (≥5) or running pattern searches that would otherwise pollute main-agent context.
- The rules for the task are fully determined by the request (no judgment calls beyond "does this match?").

## When NOT to use

- **Creative work** — NPC psychology, location design, scene architecture, prose writing. Main Opus owns these.
- **Single-file reads** — one file, small, go direct. Dispatch overhead (~200 Opus tokens to write the prompt + ~80 Opus tokens to read the result) exceeds the work.
- **Mentions or sections of one note**: `vault_mentions`, `vault_read_note` and `vault_read_section` return just those parts in the main context, so there is nothing to offload.
- **Simple Bash ops** — file renames, `git mv`, `mkdir`. Main agent Bash is faster and cheaper.
- **Synthesis across sources** — if the answer requires combining vault content with sourcebook content, that's a worldbuilding task. Use `worldbuilding` or related skills.
- **Tasks needing taste/judgment** — "which NPC would work best for Session N?" is creative. Main Opus.

## Dispatch contract

The main agent invokes a Haiku subagent like this:

```
Agent(
  subagent_type="general-purpose",
  model="haiku",
  description="<short task description>",
  prompt="<self-contained task with explicit tool allowlist and output format>"
)
```

**The dispatch prompt MUST:**
1. State the task in one sentence.
2. List the paths or glob patterns to consider.
3. Name the tools the subagent may use: `Glob`, `Grep`, `Read`, `mcp__vault-graph__vault_search_notes`, `mcp__vault-graph__vault_backlinks`, `mcp__vault-graph__vault_graph`, `mcp__vault-graph__vault_central_notes`, `mcp__vault-graph__vault_mentions`, `mcp__vault-graph__vault_read_note`, `mcp__vault-graph__vault_read_section`.
4. Specify the output format (table columns, bullet structure, or short summary).
5. Cap verbosity: "Report under 200 words unless the listing itself is longer."

**The dispatch prompt MUST NOT:**
- Ask for interpretation, recommendations, or creative output.
- Include "also add..." side-tasks unrelated to the scan.
- Leave the output format open-ended ("describe what you find").
- Ask Haiku to determine status, canonicity, validity, or cross-reference sources — that's synthesis work for the main agent.

## Anti-hallucination contract

Haiku confidently invents plausible details when source text is ambiguous. **Every dispatch prompt MUST end with this suffix:**

```
IMPORTANT — FETCH ONLY, DO NOT INTERPRET:
- Extract exact quotes from source files. Do not paraphrase.
- If a field is not explicitly stated, write "NOT STATED" — do not infer.
- Include file path and line number for every extracted value.
- Do not determine status, canonicity, or cross-reference multiple sources.
- The calling agent will interpret; you only locate and quote.
```

**Why this matters:** The main agent (Opus) owns judgment. Haiku's job is to surface raw material with provenance. When Haiku invents, the main agent has no way to verify — it trusts the subagent's "findings" and propagates hallucinations to the user.

## Tool preferences (inside the subagent)

Prefer the MCP graph tools when they fit — they are faster than Glob+Grep for many questions:

- **`mcp__vault-graph__vault_search_notes(name_pattern="...", tag="...", note_type="...")`** — find notes by name, tag, or `type:` frontmatter. Fast, indexed.
- **`mcp__vault-graph__vault_backlinks(note="Name")`** — what links to this note. Pre-computed.
- **`mcp__vault-graph__vault_graph(note="Name", depth=2)`** — local neighborhood.
- **`mcp__vault-graph__vault_central_notes(tag="...")`** — most-connected nodes in a category. Useful for "what are the important X?".
- **`mcp__vault-graph__vault_mentions(note="Name")`**: the block around each link to the note, labelled `path:line`, plus a map of mentions not shown; `unlinked=true` for plain-text mentions. Reads the vault live.
- **`mcp__vault-graph__vault_read_note(note="Name")`**: a small note whole, a large one as an outline with line ranges.
- **`mcp__vault-graph__vault_read_section(note="Name", headings=["..."])`**: chosen sections in full.

Fall back to `Glob` + `Grep` + `Read` when:
- The search is text-pattern-based (e.g., "find all notes mentioning a keyword in prose").
- The graph index may be stale (recent moves/adds not yet reloaded). This applies to the graph tools only; the three tools above read the vault live.
- The task needs file-content inspection beyond the graph.

## Output contract

Returns one of three shapes to the main agent:

1. **Raw extraction table** (preferred for multi-field queries):
   ```
   | File | Line | Field | Verbatim Quote |
   |---|---|---|---|
   | /full/path/Note.md | 42 | destination | "leads to the eastern marches" |
   | /full/path/Note.md | 45 | key | NOT STATED |
   ```
2. **Bulleted list with provenance** — when the task is "find all matching notes":
   ```
   - /full/path/note.md:23 — "exact quote from line 23"
   - /full/path/other.md:7 — "exact quote from line 7"
   ```
3. **Short summary** — when the task is a count, a boolean, or a short answer. Still cite file:line for any claim.

**Key rules:**
- Always absolute paths, so the main agent can Read without path juggling.
- Always include line numbers — enables verification.
- Verbatim quotes in double-quotes; `NOT STATED` (no quotes) when absent.
- Never summarize or paraphrase content — quote it.

## Examples

### Example 1 — Find NPCs by faction

**Main agent invocation:**
```
Agent(
  subagent_type="general-purpose",
  model="haiku",
  description="Find NPCs linked to [Faction Name]",
  prompt="""
  Find all NPC notes in <vault-root>/Grunvyr_Campaign/NPC/
  whose frontmatter `faction:` field contains '[Faction Name]'.

  Tools: Glob, Grep, Read.
  Output as: | File | Line | Field | Verbatim Quote |
  Extract: filename, faction: value, alignment: value (verbatim from frontmatter).

  IMPORTANT — FETCH ONLY, DO NOT INTERPRET:
  - Extract exact quotes from source files. Do not paraphrase.
  - If a field is not explicitly stated, write "NOT STATED" — do not infer.
  - Include file path and line number for every extracted value.
  - Do not determine status, canonicity, or cross-reference multiple sources.
  - The calling agent will interpret; you only locate and quote.
  """
)
```

### Example 2 — List session scene files

**Main agent invocation:**
```
Agent(
  subagent_type="general-purpose",
  model="haiku",
  description="List Session N scene files",
  prompt="""
  List all .md files under <vault-root>/Grunvyr_Campaign/Sessions/Session N/,
  including subfolders.

  For each file, read the frontmatter and report: Path, type: field value, date: field value.

  Tools: Glob, Read.
  Output as a bulleted list, one line per file.
  """
)
```

### Example 3 — Mentions via graph MCP

**Main agent invocation:**
```
Agent(
  subagent_type="general-purpose",
  model="haiku",
  description="Mentions of [[NPC Name]]",
  prompt="""
  Use mcp__vault-graph__vault_mentions(note="NPC Name") to get every note that links to NPC Name.md, with the block around each link.

  For each mention, report: path:line, and the sentence that mentions NPC Name, quoted from the excerpt. If the response ends with a map of mentions not shown, call the tool again with paths=[...] for those notes.

  Tools: mcp__vault-graph__vault_mentions.
  Output as a table.
  """
)
```

## BAD vs GOOD prompt patterns

**BAD — asks Haiku to interpret:**
```
Find all portals in the vault. For each portal, determine:
- Status: discovered by PCs vs. planned/GM-only
- Whether the key has been found
- If the portal is still active
```
↑ "determine," "whether," "if" — these invite synthesis. Haiku will invent confident answers.

**GOOD — asks Haiku to fetch with provenance:**
```
Find all notes mentioning "Portal" or "Gate" in Locations/ and Sessions/.
For each match, extract verbatim:
- Any line containing "Destination" or "leads to"
- Any line containing "Key"

Tools: Grep, Read.
Output as: | File | Line | Field | Verbatim Quote |

IMPORTANT — FETCH ONLY, DO NOT INTERPRET:
- Extract exact quotes from source files. Do not paraphrase.
- If a field is not explicitly stated, write "NOT STATED" — do not infer.
- Include file path and line number for every extracted value.
- Do not determine status, canonicity, or cross-reference multiple sources.
- The calling agent will interpret; you only locate and quote.
```
↑ Main agent (Opus) receives raw quotes with line numbers, then cross-references PlayerNotes itself to determine status.

## Failure modes to avoid

1. **Don't dispatch for <5 file reads.** The Opus-priced dispatch prompt costs more than the work.
2. **Don't dispatch creative tasks.** A Haiku subagent asked for "who would be a good NPC for this plot" will produce Haiku-grade NPCs. That's a loss.
3. **Don't dispatch synthesis across vault + sourcebooks.** That's `worldbuilding` territory; Haiku's cross-source reasoning is weaker.
4. **Don't dispatch tasks where the main agent needs to reason about every file individually.** If the main agent will Read the same files anyway to make a decision, the dispatch is pure overhead — the files will be in the main context twice.

If the main agent catches itself dispatching many sequential `vault-scout` calls to drill down (scan → read → scan → read), consolidate into one dispatch with a more specific prompt. Haiku is good at following narrow instructions; give it the full search-tree in one go.
