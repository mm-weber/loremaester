# Security Policy

We take the security of **Loremaester** seriously. Thank you for helping keep it and its users safe.

## Reporting a Vulnerability

Please report vulnerabilities openly as an issue.

Please include:

- A short description of the issue.
- Steps to reproduce.
- Affected file(s) / component and version (commit SHA if possible).
- A suggested fix, if you have one.

## Response 
This is a small, maintainer-driven project, but I'll do my best to keep up with any input.

## Scope

**In scope** — code maintained in this repository:

- The MCP servers under `mcp-servers/` (`r2r-wrapper`, `sourcebooks`, `vault-graph`).
- The CLI tools under `scripts/` (ingestion, OCR, graph builder, verification).
- The skills under `skills/` (and the demo copy under `examples/ttrpg/skills/`).
- The deployment and sandbox configuration under `docker/` and `.devcontainer/`.

**Out of scope:**

- Your own vault content and the documents you ingest.
- Third-party components we orchestrate but do not vendor — R2R, Ollama and its models, the Docker images (Postgres/pgvector, MinIO, Hatchet, RabbitMQ, Unstructured.io), and Obsidian. Report those to their respective projects (see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)).
- Issues that require pre-existing privileged access to the host machine.

## Design Assumptions

This project assumes a **single-user, single-tenant** deployment: R2R + Ollama run on your host, and Claude Code runs in a sandboxed devcontainer that reaches them over `host.docker.internal`. The devcontainer is the security boundary. Its threat model (a compromised agent context via prompt injection or a poisoned dependency), the host-R2R-not-Docker-in-Docker decision, the egress firewall, and the locked-down posture are documented in **[`.devcontainer/SecurityReview.md`](.devcontainer/SecurityReview.md)**. Multi-tenant or shared-host deployments might need explicit additional hardening, and are out-of-scope for now.

**Supply chain.** All container images, the host compose stacks and the devcontainer base, are pinned by **`sha256` digest** (not floating tags), so builds are reproducible and an upstream tag can't be silently repointed. Automated digest/version updates via [Dependabot](https://docs.github.com/code-security/dependabot) are **staged for v0.2** (a ready-to-use config sits at `specs/v0.2/dependabot.yml`, kept out of `.github/` so GitHub does not validate it yet); for v0.1, re-pin manually when bumping versions.

## Disclosure

Reporters who act in good faith under this policy will not face legal action, and will be credited in the release notes for the fix unless they ask otherwise.
