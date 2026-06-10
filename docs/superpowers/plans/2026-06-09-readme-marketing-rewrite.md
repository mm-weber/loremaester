# README Marketing Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md` from documentation-shape to marketing-shape per the locked design spec at `docs/superpowers/specs/2026-06-09-readme-marketing-design.md`. Position the project on architectural moat (agent-loop reasoning, retrieval as a leaf tool, write-back to vault) rather than feature stack. Target rendered length 150 to 220 lines.

**Architecture:** Single-file rewrite. Construct the new `README.md` from the 9 section bodies in spec §5.1 through §5.9, in document order. Verification gates (em-dash absence, link existence, line count) run between Write and commit.

**Tech Stack:** Bash, grep, wc, ls, git. No build/test framework involvement. The "tests" here are file-level verification commands.

---

## File structure

Files touched by this plan:

- **Modify:** `README.md` (rewrite from existing 163 lines to spec-derived ~165 to 200 lines).

Files referenced (read-only) but not modified:

- `docs/superpowers/specs/2026-06-09-readme-marketing-design.md` (the source of all section bodies).
- `docs/demo-walkthrough.md`, `docs/quickstart.md`, `docs/design.md`, `ATTRIBUTION.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, `.devcontainer/SecurityReview.md`, `specs/v0.2/specs_v0.2.md` (link targets verified to exist in Task 4).

---

## Task 1: Pre-flight verification

**Files:**
- Read: `README.md`, `docs/superpowers/specs/2026-06-09-readme-marketing-design.md`

- [ ] **Step 1: Confirm clean git state**

Run: `git status`

Expected: no uncommitted changes to `README.md`. If there are, stop and ask the user how to proceed (do not auto-stash).

- [ ] **Step 2: Confirm spec exists and is the right one**

Run: `head -5 docs/superpowers/specs/2026-06-09-readme-marketing-design.md`

Expected first line: `# README Marketing Design`. If the file is missing, this plan cannot be executed; stop and surface the error.

- [ ] **Step 3: Confirm the notices file rename has already happened**

Run: `ls -la THIRD_PARTY_NOTICES.md THIRD_PARTY_LICENSES.md 2>&1`

Expected: `THIRD_PARTY_NOTICES.md` exists, `THIRD_PARTY_LICENSES.md` does NOT exist. If `THIRD_PARTY_LICENSES.md` still exists, the rename in commit `f308474` may have been reverted; stop and re-investigate.

- [ ] **Step 4: Verify em-dash detection tool works**

Run: `printf 'a \xe2\x80\x94 b\n' | grep -P '\x{2014}' && echo MATCH`

Expected: prints `a — b` then `MATCH`. **Critical:** the pattern uses `\x{2014}` (PCRE Unicode codepoint syntax), NOT `\xE2\x80\x94` (byte syntax). In UTF-8 locales, `grep -P` interprets `\xNN` as a Unicode codepoint, so `\xE2\x80\x94` matches three codepoints (U+00E2 U+0080 U+0094) rather than the UTF-8 bytes of U+2014. If `grep -P` is not available on this system, escalate to the orchestrator.

- [ ] **Step 5: Capture baseline metrics**

Run: `wc -l README.md && grep -cP '\x{2014}|\x{2013}' README.md`

Expected: line count and em-dash count printed. Record both. The current README has 18 em-dashes (verified 2026-06-09); the rewrite drops them to zero.

- [ ] **Step 6: Confirm spec §5 section bodies are accessible**

Run: `grep -n "^### 5\." docs/superpowers/specs/2026-06-09-readme-marketing-design.md`

Expected: 9 hits (`### 5.1.` through `### 5.9.`). If any are missing, the spec has been edited since approval; stop and reconcile.

**No commit at this task.** Pre-flight only.

---

## Task 2: Write the new README from scratch using spec section bodies

**Files:**
- Modify: `README.md` (full rewrite)

The new `README.md` is built by concatenating the spec's locked section bodies in this order:

| # | Spec section | What it contains | Header level in README |
|---|---|---|---|
| 1 | §5.1 Hero block | `# Worldbuilding Assistant for Claude Code` + 2-paragraph hero + 30-min demo CTA blockquote | H1 |
| 2 | §5.2 "What you get" | 5 numbered feature bullets | H2 |
| 3 | §5.3 Techie section | "Retrieval is a tool here, not the product" + 5 paragraphs + Karpathy/claude-obsidian related-work blockquote | H2 |
| 4 | §5.4 "See it in 30 minutes" | bundled demo pitch + 6-row prompts table + `docs/demo-walkthrough.md` link | H2 |
| 5 | §5.5 "What's inside" | 6 subsections (Architecture / 3 MCP servers / 4 skills / OCR pipeline / Hardened devcontainer / Multi-instance) | H2 + 6 × H3 |
| 6 | §5.6 Quickstart | 5-step bash block + reader-intent trailing pointer | H2 |
| 7 | §5.7 "What's not included (yet)" | 3 honesty bullets | H2 |
| 8 | §5.8 Contributing & community | 4 governance link bullets | H2 |
| 9 | §5.9 License | 3 paragraphs | H2 |

- [ ] **Step 1: Read the spec section bodies you will need**

Use Read on `docs/superpowers/specs/2026-06-09-readme-marketing-design.md` covering lines that hold §5.1 through §5.9. Each `### 5.x.` heading is followed by a fenced code block (or, for §5.6, a fenced block with `bash` lang tag) containing the literal markdown to drop into the new README. Copy each fenced block's contents verbatim. Do NOT paraphrase.

- [ ] **Step 2: Construct the new README in your editor or scratchpad, in document order**

Concatenate the 9 section bodies in the order in the table above. Insert one blank line between sections. Do not add any headers, intro paragraphs, or transitions that the spec does not specify. The first line of the file must be exactly `# Worldbuilding Assistant for Claude Code` (from §5.1).

Do NOT include:
- The current README's `## Project Structure` tree (cut per spec §6, belongs in `docs/design.md`).
- The current README's `## Documentation` list (cut per spec §6, superseded by the hero CTA and inline section pointers).
- The current README's `## Development` section including the long PEP 723 paragraph (cut per spec §6, belongs in `docs/quickstart.md`).

The `## Multi-Instance Deployment` content from the current README's standalone H2 gets folded into the new README as the `### Multi-instance deployment` H3 subsection of `## What's inside` (per spec §5.5, last subsection).

- [ ] **Step 3: Write the new README to disk**

Use Write on `README.md` with the concatenated content from Step 2. This is a full file replacement, not an Edit.

- [ ] **Step 4: Verify the new README's H1/H2 outline matches the spec outline exactly**

Run: `grep -nP "^##? " README.md`

Expected output (line numbers will vary):

```
1:# Worldbuilding Assistant for Claude Code
<N>:## What you get
<N>:## Retrieval is a tool here, not the product
<N>:## See it in 30 minutes
<N>:## What's inside
<N>:## Quickstart
<N>:## What's not included (yet)
<N>:## Contributing & community
<N>:## License
```

Exactly 9 lines, exactly that order. If any are missing or out of order, fix and re-run Step 4 before proceeding.

**No commit at this task.** Verification happens in Tasks 3 through 5; the single commit covering Tasks 2 through 5 happens at the end of Task 5.

---

## Task 3: Verify zero em-dashes in the new README

**Files:**
- Verify: `README.md`

- [ ] **Step 1: Grep for em-dashes (U+2014) and en-dashes (U+2013)**

Run: `grep -nP '\x{2014}|\x{2013}' README.md ; echo "EXIT: $?"`

Expected: no output lines, `EXIT: 1`.

If any lines are returned, those are em-dashes that slipped through. For each one, edit the line and replace per the rules in [[feedback-no-em-dashes-in-writing]]:

- Parenthetical asides: use `( ... )` instead of `— ... —`.
- Strong break before a coda: use a period and start a new sentence.
- List of items: use `( a, b, or c )`, never `— a, b, or c —`.
- Restate / clarify: use a comma, colon, or semicolon.

Re-run Step 1 after every fix until `EXIT: 1`.

- [ ] **Step 2: Confirm no hyphens were accidentally converted**

Run: `grep -cE "(text-native|auto-falls|30-minute|default-DROP|host-R2R|hybrid|book/chapter/page|Vault\+Books)" README.md`

Expected: a non-zero count. Compound modifiers and hyphenated names must survive the em-dash purge. If this count is unexpectedly low, you over-corrected; restore the hyphens.

**No commit yet.**

---

## Task 4: Verify all internal links resolve

**Files:**
- Verify: `README.md` and every file path it links to.

- [ ] **Step 1: Extract relative-path link targets**

Run: `grep -oE '\]\(\S+\)' README.md | grep -vE 'https?://' | sed -E 's/\]\(([^)]+)\)/\1/' | sed -E 's/#.*$//' | sort -u`

Expected: prints a clean list of every relative path used in a markdown link, one per line. Save the output as the verification list.

- [ ] **Step 2: For each path in the list, confirm the file exists on disk**

For each path P in the Step 1 list, run: `ls -la "$P" >/dev/null 2>&1 && echo "OK: $P" || echo "MISSING: $P"`

Expected: every line says `OK: ...`. If any line says `MISSING: ...`, the corresponding link target does not exist; either the path in the README has a typo or the target file has not been created yet. Per the spec, all the paths below should exist; if any are missing, stop and reconcile.

Required paths (must all show `OK:`):

```
docs/demo-walkthrough.md
docs/quickstart.md
docs/design.md
ATTRIBUTION.md
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
LICENSE
THIRD_PARTY_NOTICES.md
.devcontainer/SecurityReview.md
specs/v0.2/specs_v0.2.md
```

- [ ] **Step 3: Confirm no `THIRD_PARTY_LICENSES.md` ghost references remain in `README.md`**

Run: `grep -nP "THIRD_PARTY_LICENSES" README.md ; echo "EXIT: $?"`

Expected: no output, `EXIT: 1`. The notices file was renamed in commit `f308474`; any lingering `THIRD_PARTY_LICENSES` string in the README is stale.

**No commit yet.**

---

## Task 5: Verify line-count budget and commit

**Files:**
- Verify: `README.md`
- Commit: README.md

- [ ] **Step 1: Confirm line count is within budget**

Run: `wc -l README.md`

Expected: between 150 and 220 inclusive. The spec's target range is 150 to 220 rendered lines. If significantly under 150, a section may have been dropped; cross-check against the §4 outline in the spec. If significantly over 220, a deprecated section (Project Structure / Documentation / Development / Multi-Instance Deployment H2) likely survived; re-check Step 2 of Task 2.

- [ ] **Step 2: Diff against the previous README for a sanity sweep**

Run: `git diff --stat README.md`

Expected: a single-file diff with substantial additions and deletions (this is a rewrite, not an edit). Skim the diff for anything unexpected.

- [ ] **Step 3: Stage and commit**

Run:

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: rewrite README to marketing-shape per design spec

Replaces the documentation-shape README with a marketing-shape rewrite
per docs/superpowers/specs/2026-06-09-readme-marketing-design.md.
Hero block, 5 "What you get" bullets, the architectural-moat techie
section ("Retrieval is a tool here, not the product"), the 30-min
demo CTA section with the 6-prompt proof table, a consolidated
"What's inside" with 6 subsections (architecture, 3 MCP servers / 14
tools, 4 skills, OCR pipeline, hardened devcontainer, multi-instance),
Quickstart with host/devcontainer location annotations, a 3-bullet
"What's not included (yet)" honesty section, and tightened
Contributing + License blocks. Em-dash purged everywhere per user
style preference. THIRD_PARTY_NOTICES rename applied.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds. If a pre-commit hook fails, fix the underlying issue and re-stage; never `--amend` or `--no-verify`.

- [ ] **Step 4: Verify the commit landed and the working tree is clean**

Run: `git status && git log -1 --stat`

Expected: working tree clean, the latest commit is the README rewrite, only `README.md` modified.

---

## Task 6: Post-commit review

**Files:**
- Read: `README.md` (rendered if possible).

- [ ] **Step 1: Re-render check**

If a markdown renderer is available (VS Code preview, `glow`, `mdcat`, GitHub's web view via `gh`), open the rendered README and skim the result. Watch for:

- Hero block prominence (bold first paragraph, then prose, then CTA blockquote).
- Tables (3 in total: 6-prompt demo proof, 3-row MCP servers, 4-row skills).
- The ASCII diagram in `### Architecture` renders inside the code fence (no broken box-drawing).
- The Karpathy related-work blockquote at the end of the techie section is properly indented as a blockquote.

If no renderer is available, skip this step. The grep / wc gates from Tasks 3 to 5 are the primary correctness checks; rendering is a sanity layer on top.

- [ ] **Step 2: Surface follow-ups noted in the spec (do NOT do them in this plan)**

Per spec §7, three items are deferred and stay open after this rewrite:

1. **Project rename to "Loremaester"** (separate task; touches hero H1 + ATTRIBUTION + design.md + bullets B2/B3 references).
2. **Hardened devcontainer subsection revisit at v0.1 release prep** (recheck `### Hardened devcontainer` copy against any late-cycle changes to `.devcontainer/SecurityReview.md` or `init-firewall.sh` before tagging v0.1).
3. **OCR EasyOCR docs hook** (CUDA install incantation stays in `docs/quickstart.md`; no README change needed).

Confirm these three items remain on the user's backlog after the README ships. Do not act on them in this plan.

**No commit at this task.** Review-only.

---

## Self-review (against spec)

**1. Spec coverage:**

| Spec section | Plan task that implements it |
|---|---|
| §2 positioning decisions (locked) | Tasks 2 to 5 implement the rewrite; the decisions are baked into the spec's section bodies that Task 2 copies verbatim. |
| §3 voice / register rules | Encoded in the spec bodies; Task 3 (em-dash check) enforces the one machine-checkable rule. |
| §4 section outline | Task 2 Step 4 verifies the outline matches exactly. |
| §5.1 through §5.9 section bodies | Task 2 Step 2 places them all in document order. |
| §6 deltas (CUT items) | Task 2 Step 2 explicitly lists Project Structure / Documentation / Development as cuts; Task 5 Step 1 (line count) catches accidentally-surviving CUTs. |
| §7 open follow-ups | Task 6 Step 2 surfaces them post-commit. |
| §8 self-review (spec-side) | Already done at spec-write time; not re-run here. |
| §9 hand-off | After Task 5 commits, this plan is complete. |

**2. Placeholder scan:** no `TBD` / `TODO` / `fill in details` in the plan body. Every step lists an exact command or an exact action with explicit expected output.

**3. Type consistency:** the file paths cited across tasks (`README.md`, `docs/superpowers/specs/2026-06-09-readme-marketing-design.md`, `THIRD_PARTY_NOTICES.md`, etc.) match the spec's references. The required-paths list in Task 4 Step 2 matches the link targets that appear in the spec's section bodies.

**4. Ambiguity check:** Task 2 Step 2 is the one step with the most judgment in it (assembling the new file). It is bounded by Step 4's outline check, Task 3's em-dash check, Task 4's link-existence check, and Task 5's line-count check. Any drift gets caught downstream before the commit lands.
