# Devcontainer Security Review

**Scope:** the **release devcontainer** shipped with this repo (`.devcontainer/`). It
sandboxes Claude Code (the agent); R2R and Ollama run on the **host**.

## Threat model
The primary adversary is a **compromised agent context inside the devcontainer** —
reached via prompt injection (a malicious sourcebook PDF, web content, or MCP tool
output), a poisoned `pip`/`npm`/PEP-723 dependency, or a malicious MCP server. The
devcontainer exists to contain exactly that. Secondary: another process/host on the
LAN reaching an exposed service.

## Architecture decision: host-R2R, not Docker-in-Docker
R2R's stack (Postgres + pgvector, MinIO, Hatchet, Unstructured, R2R, dashboard) runs
**on the host** via `docker compose`. The devcontainer runs only Claude Code and three
native-Python MCP servers, which reach the host's R2R/Ollama via `host.docker.internal`.

An earlier iteration provisioned the container for **Docker-in-Docker** (R2R inside the
container). DinD was removed because:

- **It is incompatible with the working setup.** `host.docker.internal` resolves to the
  host gateway, so the MCP servers can only reach R2R when R2R is on the host — not
  inside an inner DinD daemon.
- **It guts the sandbox.** DinD requires a root `dockerd`, the `node` user in the
  `docker` group (root-equivalent), and a seccomp profile looser than Docker's default
  (allowing `mount`/`unshare`/`setns`/`pivot_root`). A compromised agent would inherit a
  large, well-documented container-escape surface — the opposite of what the sandbox is for.
- **Nothing in this repo needs it.** Every `docker compose` command is host-side
  (including the multi-instance `r2r-infra.sh`/`r2r-instance.sh` helpers); the MCP
  servers, bundled skills, tests, and CI have zero Docker dependencies. The only
  in-container Docker consumer was a leftover `terraform` MCP server (`docker run …`),
  and the repo has no Terraform files — it was dev-environment slack and was removed.

## Current posture (locked down)
- **No Docker-in-Docker** — the `docker-in-docker` feature, the `node` docker-group
  membership, and the `dind-seccomp.json` override are removed.
- **Docker's default seccomp** applies (no `--security-opt seccomp` override).
- **Capabilities:** only `--cap-add=NET_ADMIN`, used by the egress firewall — not for Docker.
- **Egress firewall** (`init-firewall.sh`): default-DROP with an allowlist (GitHub, npm,
  PyPI/uv, Anthropic + VS Code telemetry). Host access is scoped to the gateway IP on
  ports **7272** (R2R) and **11434** (Ollama) only — no whole-subnet carve-out.
- **PID 1 runs as root** solely so the entrypoint can apply iptables rules; the
  interactive/agent shell runs as the unprivileged `node` user.
- **Pinned images** — the devcontainer base (`FROM node:20@sha256:…`) and every image in
  the host compose stacks are pinned by **`sha256` digest**, not a floating tag, so builds
  are reproducible and an upstream tag can't be silently repointed. Automated bumps via
  **Dependabot** are **staged for v0.2** (`.github/dependabot.yml` ships commented out); for
  v0.1, re-pin manually when updating.

## Original findings — status
- **C-1 — `seccomp=unconfined`:** **Resolved.** The override is gone; Docker's default
  (allowlist) seccomp now applies. (The interim `dind-seccomp.json` denylist was deleted
  with DinD.)
- **H-1 — `CAP_SYS_PTRACE`:** **Resolved.** Not granted in `runArgs`; cross-process
  memory inspection is unavailable to the agent.
- **H-3 — firewall via sudoers:** **Resolved.** The firewall runs from the root
  `entrypoint.sh`, so no sudoers rule is needed.

## Residual risks (accepted by design)
- **SSH-agent forwarding** — `devcontainer.json` bind-mounts the host `SSH_AUTH_SOCK`
  so git over SSH works. While mounted, a compromised agent could use the host's keys.
  Mitigations if this matters: an agent that confirms each use, a scoped key, or switch
  to HTTPS+PAT and drop the mount.
- **Host service exposure** — *Mitigated.* The compose stacks bind every published port to
  `127.0.0.1` **except** `r2r:7272`, which binds loopback **and** the docker-bridge gateway
  (`172.17.0.1`) — so the devcontainer reaches it via `host.docker.internal` while the
  host's routable LAN interface stays unbound (Postgres, MinIO, dashboards, queues are
  loopback-only). *Remaining:* `r2r:7272` is still reachable from other containers on the
  host and is **unauthenticated** (the Ollama-embeddings config configures no auth provider)
  — add an R2R API key if that surface matters. (macOS/Docker Desktop: the `172.17.0.1` line
  is Linux-only — drop it; `127.0.0.1` alone suffices there.)

## Validating after a rebuild
- `docker --version` should be **absent** inside the container (no Docker shipped).
- `grep '^FROM' .devcontainer/Dockerfile` shows an `@sha256:` digest (the base is pinned).
- The firewall log shows `Host gateway detected as …` and the scoped 7272/11434 rule.
- From inside the container: `curl http://host.docker.internal:7272/v3/health` succeeds;
  `curl https://example.com` is blocked (egress lockdown working).
