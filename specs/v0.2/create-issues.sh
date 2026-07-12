#!/usr/bin/env bash
# create-issues.sh — create the v0.2 milestone, labels, and issues on GitHub.
#
# Source of truth: specs/v0.2/v0.2-milestone-plan.md
# Prereq: gh auth login   (as a user with write access to mm-weber/loremaester)
# Safe to re-run: labels are updated (--force); issues whose title already
# exists are skipped.
#
# Usage:
#   gh auth login
#   bash specs/v0.2/create-issues.sh
#   REPO=someone/fork bash specs/v0.2/create-issues.sh   # override target repo

set -euo pipefail

REPO="${REPO:-mm-weber/loremaester}"
MILESTONE="v0.2"

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

echo ">> Repo: $REPO   Milestone: $MILESTONE"

# --- Milestone (create if missing) ---
if gh api "repos/$REPO/milestones?state=all" --jq '.[].title' | grep -qxF "$MILESTONE"; then
  echo ">> milestone exists: $MILESTONE"
else
  gh api "repos/$REPO/milestones" \
    -f title="$MILESTONE" -f state="open" \
    -f description="Hardening and polish: agent blast-radius reduction (credentials, hardened mounts, recoverable vault, scoped MCP verbs) plus the sourcebooks MCP design review, pyproject migration, and Dependabot." >/dev/null
  echo ">> created milestone: $MILESTONE"
fi

# --- Labels (idempotent via --force) ---
ensure_label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null; echo ">> label: $1"; }
ensure_label security          B60205 "Security hardening / threat-model work"
ensure_label area:devcontainer 0E8A16 "Devcontainer / sandbox config"
ensure_label area:mcp-servers  0E8A16 "MCP servers"
ensure_label area:data         0E8A16 "R2R / Postgres / MinIO corpus"
ensure_label area:ci           0E8A16 "CI / supply chain"
ensure_label area:packaging    0E8A16 "Python packaging"
ensure_label repo-config       5319E7 "GitHub repo settings applied manually"
ensure_label type:enhancement  A2EEEF "New capability"
ensure_label type:refactor     A2EEEF "Internal restructure, no behavior change"
ensure_label type:chore        FEF2C0 "Tooling / packaging / CI"
# Optional priority labels (not applied below; add per the Prio column if you want them):
# ensure_label priority:high   D93F0B "High priority"
# ensure_label priority:medium FBCA04 "Medium priority"
# ensure_label priority:low    C2E0C6 "Low priority"

# --- Issues (skip if a matching title already exists) ---
existing_titles="$(gh issue list --repo "$REPO" --state all --limit 300 --json title --jq '.[].title')"

create_issue() {
  local title="$1" body="$2"; shift 2
  if grep -qxF "$title" <<<"$existing_titles"; then
    echo ">> skip (exists): $title"
    return
  fi
  gh issue create --repo "$REPO" --milestone "$MILESTONE" --title "$title" --body "$body" "$@"
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

create_issue "SEC-0: [epic] Agent blast-radius hardening (tracking)" "$(cat <<'BODY'
Tracking issue for the agent blast-radius hardening workstream (two remediation lists: SSH/git credentials, and bind-mount confused-deputy). Executes the residual-risk mitigations flagged in `.devcontainer/SecurityReview.md`.

- [ ] SEC-1: Git credentials (HTTPS+PAT primary, deploy-key fallback; drop SSH-agent mount)
- [ ] SEC-2: Hardened bind mount (read-only PDFs, narrow RW vault + code)
- [ ] SEC-3: Remote backstops (protect main; verify PAT cannot delete/alter protection)
- [ ] SEC-4: Host-side recoverability (vault snapshots, PDF immutability, corpus rebuild)
- [ ] SEC-5: Scope destructive MCP verbs + HITL on irreversible ops

Related: BL-5 (Dependabot) is the supply-chain lever these lists reference. Full plan: `specs/v0.2/v0.2-milestone-plan.md`.
BODY
)" --label security

create_issue "SEC-1: Git credentials: HTTPS+PAT primary + deploy-key fallback; drop SSH-agent mount" "$(cat <<'BODY'
**Context.** `SSH_AUTH_SOCK` is bind-mounted (`.devcontainer/devcontainer.json:76,83`) and `origin` is SSH, so a compromised agent can use the full host SSH identity. `SecurityReview.md` records this as an accepted residual risk.

**Requirements (EARS).**
- THE devcontainer SHALL NOT mount the host SSH-agent socket (`SSH_AUTH_SOCK`).
- THE repository SHALL default `origin` to HTTPS authenticated by a Loremaester-only fine-grained PAT (Contents: read/write; no Administration, no Delete), supplied via a git credential helper.
- WHERE an SSH remote is required, THE repository SHALL document a per-repo ed25519 deploy key (optionally loaded with `ssh-add -c`) as the fallback; the personal SSH agent is never forwarded.
- WHERE registry authentication is needed (npm, PyPI), THE setup SHALL use separate scoped tokens, never the git PAT.

**Acceptance.**
- [ ] No `SSH_AUTH_SOCK` mount or env in `devcontainer.json`.
- [ ] `git push` / `pull` succeed over HTTPS using the fine-grained PAT.
- [ ] Deploy-key fallback documented in the devcontainer/security docs.
- [ ] `SecurityReview.md` residual-risk entry updated.

Refs: List 1 #1,2,5,6,7. Pairs with SEC-2 (same file); verified by SEC-3.
BODY
)" --label security --label area:devcontainer

create_issue "SEC-2: Hardened bind mount: read-only PDFs, narrow RW vault + code" "$(cat <<'BODY'
**Context.** The host repo tree is bind-mounted read-write (`workspaceMount`, `devcontainer.json:87`); only the repo and the SSH socket are mounted (`:59-76`), no `$HOME`/parent. On Linux, read-only mounts plus a narrow writable surface remove most of the blast radius while keeping host IDE access and native speed. Chosen over a container-volume clone after review.

**Requirements (EARS).**
- THE ~34G sourcebook PDFs SHALL be mounted read-only, and MAY additionally be made immutable on the host with `chattr +i` (the container lacks `CAP_LINUX_IMMUTABLE` to clear it).
- THE writable bind mounts SHALL be limited to the Obsidian vault and the code tree; THE devcontainer SHALL NOT mount `$HOME`, parent directories, or the SSH socket (removed by SEC-1).
- WHERE bundled reference material is present (skills, fixtures, static config), THE devcontainer SHALL mount it read-only.
- THE container SHALL be documented as disposable, with the protected remote and host-side snapshots (SEC-4) as the source of truth.

**Acceptance.**
- [ ] PDFs mounted `:ro`; an in-container delete attempt fails (verified).
- [ ] Only vault + code are writable; no `$HOME`/parent/socket mounts.
- [ ] VSCode "Reopen in Container" gives a working edit session.
- [ ] `SecurityReview.md` updated to the hardened-bind posture.

Refs: List 2 #1,2,3,7. Pairs with SEC-1 (same PR) and SEC-4 (recovery half).
BODY
)" --label security --label area:devcontainer

create_issue "SEC-3: Remote backstops: protect main + verify PAT cannot delete/alter protection" "$(cat <<'BODY'
**Context.** Token scope decides whether the agent can push; branch protection decides whether it can rewrite or destroy history. A write-scoped token can still force-push an unprotected branch, so both are required.

**Requirements (EARS).**
- THE `main` branch SHALL require a pull request to merge, SHALL block force-push, and SHALL block deletion.
- THE fine-grained PAT from SEC-1 SHALL NOT be able to delete the repository or modify protection rules (guaranteed by omitting Administration; verify).
- Repository deletion SHALL require an administrator the token does not have.

**Acceptance.**
- [ ] `main` protected: PR required, force-push blocked, deletion blocked.
- [ ] Verified: the PAT cannot delete the repo or edit protection.

Refs: List 1 #3,4. Closes the loop with SEC-1.
BODY
)" --label security --label repo-config

create_issue "SEC-4: Host-side recoverability: vault snapshots, PDF immutability, corpus rebuild" "$(cat <<'BODY'
**Context.** Under the hardened bind mount, the Obsidian vault is the mutable, precious set. Its local-only commits live in the writable mount, so an `rm -rf` destroys them; recovery must be off-container. PDFs are static and immutable; the R2R corpus (Postgres/MinIO named volumes) is derived from the PDFs and rebuildable.

**Requirements (EARS).**
- THE vault SHALL have a host-side recovery point taken at least hourly using an incremental mechanism (a CoW snapshot on btrfs/ZFS/LVM, or `restic`/`borg` on ext4); full tarballs SHALL NOT be used.
- Snapshot and backup destinations SHALL NOT be mounted into the container.
- THE sourcebook PDFs SHALL be `:ro`/immutable and backed up once, on change.
- THE R2R corpus SHALL be treated as rebuildable: the repo SHALL document the rebuild path, and MAY take a periodic `pg_dump` if re-ingest is expensive.
- THE snapshot retention SHALL be bounded (for example hourly x24, daily x14).

**Acceptance.**
- [ ] Off-container, incremental, hourly vault snapshot in place.
- [ ] PDF immutability + one-time backup documented.
- [ ] Corpus rebuild path documented (and/or `pg_dump` scheduled).
- [ ] Retention policy configured.

Refs: List 2 #4. Pairs with SEC-2. Related: the R2R API is unauthenticated (`SecurityReview.md` residual); optional API-key follow-up.
BODY
)" --label security --label area:data

create_issue "SEC-5: Scope destructive MCP verbs + HITL on irreversible ops" "$(cat <<'BODY'
**Context.** `r2r-wrapper` exposes an ungated `delete_document` (`mcp-servers/r2r-wrapper/r2r_mcp_wrapper.py`), and `vault-graph` exposes an ungated `vault_rebuild_graph` (`mcp-servers/vault-graph/server.py`) that overwrites `.graph.json`. `workflow.md` already defines manual approval gates for devcontainer/security changes.

**Requirements (EARS).**
- THE MCP servers SHALL NOT expose delete or bulk-destroy tools by default; WHERE a destructive verb is genuinely required, THE server SHALL require a confirmation token.
- THE harness SHALL gate irreversible shell operations (`rm -rf`, `git clean -fdx`, force-push), especially on the vault and `.git`, behind human approval via Claude Code hooks.
- THE harness SHALL NOT gate routine file writes (to avoid oversight-overload / rubber-stamping).

**Acceptance.**
- [ ] `delete_document` and `vault_rebuild_graph` are removed or confirmation-gated.
- [ ] Hooks require approval for `rm -rf` / `git clean -fdx` / force-push.
- [ ] Routine writes are unaffected.

Refs: List 2 #5,6. Coordinate with BL-1/BL-2 (same MCP files).
BODY
)" --label security --label area:mcp-servers

# ---------------------------------------------------------------------------
# Backlog (from specs/v0.2/v0.2-milestone-plan.md)
# ---------------------------------------------------------------------------

create_issue "BL-1: sourcebooks MCP design-review fixes" "$(cat <<'BODY'
**Context.** Design-review findings for `mcp-servers/sourcebooks/server.py` (`specs/v0.2/v0.2-milestone-plan.md` issues 1-7). Covers #2-#7 and structural items B and C.

**Requirements.**
- `list_books` SHALL NOT silently truncate at 100 documents (paginate or expose a `limit`; at minimum warn on truncation). [#2]
- `get_chapter` SHALL return deterministic, ordered chapter content (prefer `list_chunks` with a metadata filter over search). [#3]
- `search_lore` SHALL return an explicit empty-result message. [#4]
- Attribute access SHALL be consistent across servers. [#5]
- The async/sync client mismatch SHALL be resolved or documented. [#6]
- Tool docstrings SHALL be enriched for correct tool selection. [#7 / struct C]
- Response formatting SHALL be factored to a shared helper where it duplicates the generic wrapper. [struct B]

**Acceptance.** A failing-first test per behavior; no silent truncation; empty-result messages present; docstrings enriched. Tests hermetic per `CONTRIBUTING.md`.

Refs: `specs/v0.2/v0.2-milestone-plan.md` issues 2-7, B, C. Coordinate with SEC-5 and BL-2 (same files).
BODY
)" --label area:mcp-servers --label type:enhancement

create_issue "BL-2: shared cached R2R client across MCP servers" "$(cat <<'BODY'
**Context.** All three MCP servers construct a new `R2RClient` per call (`specs/v0.2/v0.2-milestone-plan.md` issue #1, structural A).

**Requirements.**
- A shared `r2r_utils.get_client()` SHALL provide a cached module-level client (after confirming `R2RClient.__init__` cost).
- `r2r-wrapper` and `sourcebooks` SHALL use it.

**Acceptance.** Single client reused per process; tests pass; no behavior change.

Refs: `specs/v0.2/v0.2-milestone-plan.md` issue #1, structural A.
BODY
)" --label area:mcp-servers --label type:refactor

create_issue "BL-3: R-3 end-to-end collection support (optional)" "$(cat <<'BODY'
**Context.** The generic `r2r` wrapper supports `collection_ids`, but the `sourcebooks` server and the ingest/verify CLIs do not scope by collection.

**Requirements.** Add `--collection` to `ingest_books.py` / `verify_ingestion.py` and collection filtering to the sourcebooks server so retrieval honors it.

**Acceptance.** End-to-end collection scoping works; docs updated.

Refs: `specs/v0.2/v0.2-milestone-plan.md` R-3. Priority low / stretch.
BODY
)" --label area:mcp-servers

create_issue "BL-4: R-4 migrate Python deps to pyproject.toml [project]" "$(cat <<'BODY'
**Context.** Move dependency declarations from `requirements*.txt` to `pyproject.toml [project]`.

**Requirements (from R-4).** Declare runtime deps in `[project].dependencies`, test deps in `[project.optional-dependencies].test`; add a minimal `[build-system]` (hatchling) so `pip install -e ".[test]"` works; Dockerfile and CI install via `pip install -e ".[test]"`; remove `requirements*.txt`; keep PEP 723 script metadata intact.

**Acceptance.** `pip install -e ".[test]"` installs all deps; CI green; `requirements*.txt` removed.

Refs: `specs/v0.2/v0.2-milestone-plan.md` R-4.
BODY
)" --label area:packaging --label type:chore

create_issue "BL-5: R-5 activate Dependabot supply-chain updates" "$(cat <<'BODY'
**Context.** Config is staged at `specs/v0.2/dependabot.yml`.

**Requirements (from R-5).** `git mv specs/v0.2/dependabot.yml .github/dependabot.yml`; cover `docker` (`/.devcontainer`, `/docker`) and `github-actions` (`/`), grouped weekly; enable in Settings -> Code security; config on the default branch. Add a `pip` ecosystem (tracking `requirements*.txt`, or the `pyproject.toml` from BL-4 once landed).

**Acceptance.** Active `.github/dependabot.yml` on `main`; Dependabot enabled; first update PRs appear.

Refs: `specs/v0.2/v0.2-milestone-plan.md` R-5. The supply-chain lever the security lists reference; cross-link SEC-0.
BODY
)" --label area:ci --label type:chore

echo ">> done."
