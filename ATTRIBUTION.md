# Attribution

The **Worldbuilding Assistant for Claude Code** is released under the [MIT License](LICENSE). It **orchestrates** the software below rather than vendoring it. This file credits that work; for the exact license terms and redistribution notes (including the **MinIO AGPL-3.0** caveat), see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Core software

| Component | Author / Project | Role | License |
| --------- | ---------------- | ---- | ------- |
| [R2R](https://github.com/SciPhi-AI/R2R) | SciPhi AI | Retrieval engine — embeddings, vector search, ingestion (SDK + Docker image) | MIT |
| [Model Context Protocol SDK](https://github.com/modelcontextprotocol/python-sdk) (`mcp`) | Anthropic / MCP | Framework for the three MCP servers | MIT |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | pypdfium2 team / Google (PDFium) | Per-page PDF rendering for client-side OCR | Apache-2.0 / BSD-3 |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) / [pytesseract](https://github.com/madmaze/pytesseract) | Tesseract OCR contributors | Default CPU OCR engine | Apache-2.0 |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | Jaided AI | GPU OCR engine (opt-in) | Apache-2.0 |
| [PyTorch](https://github.com/pytorch/pytorch) | PyTorch contributors | Backend for the EasyOCR opt-in | BSD-3-Clause |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | Jeremy Singer-Vine | PDF text-layer + figure-region extraction | MIT |
| [Pillow](https://github.com/python-pillow/Pillow) | Pillow contributors | Image handling in the OCR path | HPND (permissive) |
| [PyYAML](https://github.com/yaml/pyyaml) | PyYAML contributors | Frontmatter + config parsing | MIT |
| [pytest](https://github.com/pytest-dev/pytest) / pytest-asyncio | pytest-dev | Test suite | MIT |
| [Ollama](https://github.com/ollama/ollama) + `mxbai-embed-large` | Ollama; Mixedbread AI | Local embedding model server + model | MIT (Ollama); see model card |

Runtime Docker images (Postgres/pgvector, MinIO, Hatchet, RabbitMQ, Unstructured.io) are pulled unchanged — see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for their licenses. The one-off `scripts/ocr_preprocess.py` helper (not on the default path) additionally uses [pdf2image](https://github.com/Belval/pdf2image) (MIT; needs the system **poppler**) and optionally [surya](https://github.com/VikParuchuri/surya) (copyleft — consult upstream).

## On the "LLM Wiki" pattern

This project's shape — an LLM that reads raw sources and maintains a structured, interlinked Markdown knowledge base — is a close cousin of the **"LLM Wiki"** pattern [Andrej Karpathy described publicly](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

To be clear and fair about provenance: this is an **independent implementation**, and its development **predates** that gist. The initial commit in this repository is dated **2026-03-06** — roughly a month before the gist (**2026-04-04**) — and no code or content from it was used. It's a natural, widespread pattern that several people have arrived at independently. Still, a hat tip to Karpathy for articulating it crisply and helping popularize it. 🎩

## This project

**Worldbuilding Assistant for Claude Code** — © its contributors, MIT-licensed. Built to run on [Claude Code](https://claude.com/claude-code) (Anthropic).
