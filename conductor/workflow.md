# Development Workflow

## Core Principles
1. **The track spec/plan is the source of truth** for in-flight work.
2. **Tests alongside changes** — the repo mocks backends (R2R, OCR engines) so tests run without
   services. TDD encouraged, not hard-gated.
3. **Small, verifiable commits** — Conventional Commits, scoped to one change.
4. **Worktrees for features** — never commit directly to `main/`; one worktree per feature/PR
   (see the repo `CLAUDE.md`).

## Task Lifecycle
1. Pick the next pending task in the track plan; mark it `[~]`.
2. Where it fits, write/adjust tests first and run them.
3. Implement the minimum to pass; keep diffs minimal.
4. Run the suite; verify behavior.
5. Commit (`[track-id] task: …`); mark the task `[x]`.

## Commit Strategy
**Conventional Commits** (`feat:`, `fix:`, `docs:`, `security:`, `debug:`, `chore:` …).
Commit and push **only when asked**.

## Verification Commands
```bash
python -m pytest -q scripts/ mcp-servers/      # unit tests (backends mocked)
uv run --no-project scripts/<name>.py …        # run a PEP 723 script
git grep -n kreuzberg                          # e.g. confirm a dependency removal
```

## Manual Approval Gates
- Dependency changes (especially license-affecting ones).
- OCR pipeline changes.
- Devcontainer / security changes.

## Phase Completion Protocol
At the end of each phase: run the suite, confirm the spec's acceptance criteria, then a checkpoint
commit: `[track-id] checkpoint: phase N complete`.
