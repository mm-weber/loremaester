# Product Vision

## Product Overview

**Name:** R2R + Claude Code Integration

**Tagline:** A reproducible, self-hostable RAG quickstart that pairs SciPhi R2R with Claude Code and MCP.

**Description:**
A public reference project showing how to stand up a Retrieval-Augmented Generation stack
(SciPhi R2R + Ollama embeddings, host-side Docker) and drive it from Claude Code via native Python
MCP servers. It ships a worked TTRPG-sourcebook corpus, ingestion/OCR scripts, three MCP servers
(generic R2R wrapper, sourcebooks facade, vault-graph), and a locked-down release devcontainer.

## Problem Statement

### The Problem
Standing up a working, end-to-end RAG demo — ingestion, OCR for scanned PDFs, embeddings, retrieval,
and an agent that can query it — is fiddly and easy to get subtly wrong. Most examples are partial,
cloud-locked, or assume a hosted vector DB.

### Current Solutions
Hosted RAG SaaS; framework "hello world" snippets; notebook demos.

### Why They Fall Short
They skip the operational reality: self-hosting the stack, OCR for image-only PDFs, host-vs-container
networking, permissive licensing, and a sandboxed agent. This project is the missing
"works on your machine, end to end" reference.

## Target Users

### Primary Users
Developers evaluating R2R and/or Claude Code + MCP.

- **Who:** Engineers who want a self-hosted RAG they can read, run, and adapt.
- **Goals:** Clone, run the quickstart, query their own corpus.
- **Pain Points:** Half-working demos, hidden cloud dependencies, license traps.
- **Technical Proficiency:** Comfortable with Docker, Python, and CLIs.

### Secondary Users
TTRPG worldbuilders using the `sourcebooks` / `vault-graph` servers for lore retrieval.

## Core Value Proposition

### Key Benefits
1. End-to-end and self-hosted — nothing cloud-locked.
2. Reproducible — PEP 723 scripts run via `uv`; host-side Docker Compose for R2R.
3. Permissively licensed and honest about its third-party license footprint.

### Value Statement
> A RAG quickstart you can actually run, read, and trust — from PDF ingestion to an agent that queries it.

## Out of Scope

### Explicitly Not Included
- A hosted/managed offering.
- A production multi-tenant deployment (single-user / self-host focus).
- Non-PDF document pipelines (the demo corpus is PDF sourcebooks).

### Future Considerations
- v0.2 OCR consolidation and the kreuzberg removal (see the track registry).
