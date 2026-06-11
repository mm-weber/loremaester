# Contributing to Loremaester

Thanks for your interest in contributing. This is a small, focused project — contributions that match its philosophy land quickly.

First, what this project **is**: a self-hosted toolkit that turns Claude Code into a worldbuilding collaborator over an Obsidian vault and a library of TTRPG sourcebooks. It is **not** a Claude Code plugin — there is no marketplace manifest. It is a set of parts you run yourself: MCP servers (`mcp-servers/`), Claude Code skills (`skills/`), CLI tools (`scripts/`), and a Docker + devcontainer deployment (`docker/`, `.devcontainer/`).

## Philosophy

- **Read before you write.** Match the conventions already in the file you're editing.
- **Simplicity first.** Implement what's needed; don't add speculative abstraction without a real caller.
- **Permissive licenses only on the shipped path.** This matters here: a core dependency (`kreuzberg`, Elastic-License-2.0) was removed in v0.1 precisely because it wasn't OSI-permissive. New runtime dependencies on the default path must be MIT / Apache-2.0 / BSD — no copyleft, no source-available. Copyleft is acceptable only for clearly-optional, off-by-default helpers, and must be flagged in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- **Handle failure explicitly.** Don't swallow errors or return empty results silently — the OCR pipeline raises a document-identifying error rather than ingesting nothing, and new code should be just as loud.

## Workflow

1. **Open an issue** for anything non-trivial, so we can agree on the approach before you build.
2. **Fork** and branch from `main`.
3. **Set up** the devcontainer (VS Code "Reopen in Container", or `devcontainer up`). The image build pre-installs the project's Python deps via `pip install -r requirements-dev.txt`, so the MCP servers and the test suite work out of the box. The `scripts/` are [PEP 723](https://peps.python.org/pep-0723/) single-file scripts run with `uv run --no-project` and resolve their own deps per invocation.
4. **Make the change**, following existing patterns and the conventions in [`conductor/workflow.md`](conductor/workflow.md) and [`conductor/code_styleguides/python.md`](conductor/code_styleguides/python.md).
5. **Add or update tests** (see below) and keep the suite green.
6. **Note user-facing changes** under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
7. **Commit** with [Conventional Commits](https://www.conventionalcommits.org/) prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`) — the history uses them.
8. **Open a PR** describing the change and how you verified it.

## Testing standards

- Tests live next to what they test (`scripts/test_*.py`, `mcp-servers/*/test_*.py`), except the cross-component end-to-end suite at `tests/e2e/`.
- Run them with `pytest` (configuration in `pyproject.toml`).
- Tests must be **hermetic** (no live R2R / Ollama / network — mock the backends), **fast**, and **deterministic**. The OCR tests, for example, mock pypdfium2 / tesseract / easyocr and avoid numpy/pandas/torch so they run anywhere.
- New behavior needs a test that would fail without the change.

## What we won't merge

- Code with no tests, or that breaks existing tests without a documented reason.
- A new **non-permissive** runtime dependency on the default path (see Philosophy).
- Silent failure — swallowed exceptions, or empty-result fallbacks that hide problems.
- Speculative abstraction with no caller.
- Secrets, credentials, or real `.env` files (only `*.env.example` templates belong in git).

## Security

Please report vulnerabilities privately — see [`SECURITY.md`](SECURITY.md), not the public issue tracker.

## License

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE).

## Code of Conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
