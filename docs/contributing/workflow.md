# Development Workflow

Day-to-day mechanics for working in this repo. The contributor steps (fork, branch, test, open a PR)
live in [`CONTRIBUTING.md`](../../CONTRIBUTING.md); this doc covers how changes are made and verified.

## Core principles
1. **Tests alongside changes.** The repo mocks its backends (R2R, OCR engines) so tests run without
   any services. TDD is encouraged, not hard-gated.
2. **Small, verifiable commits.** Conventional Commits, each scoped to one change.
3. **Worktrees for features.** Never commit directly to `main`; one worktree per feature/PR (see the
   repo `CLAUDE.md`).

## The change loop
1. Where it fits, write or adjust tests first and run them.
2. Implement the minimum to pass; keep diffs minimal.
3. Run the suite and verify behavior.
4. Commit with a Conventional Commits message; push when ready.

## Commit strategy
**Conventional Commits** (`feat:`, `fix:`, `docs:`, `security:`, `chore:`, …), one change per commit.

## Verification commands
```bash
python -m pytest -q scripts/ mcp-servers/      # unit tests (backends mocked)
uv run --no-project scripts/<name>.py …        # run a PEP 723 script
git grep -n <term>                             # e.g. confirm a dependency removal
```

## Manual approval gates
Call these out in the PR and expect extra review:
- Dependency changes (especially license-affecting ones).
- OCR pipeline changes.
- Devcontainer / security changes.

Before marking work done: run the full suite and confirm the change's acceptance criteria.
