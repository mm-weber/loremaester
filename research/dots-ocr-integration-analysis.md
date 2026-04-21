# dots.ocr in R2R-ClaudeCode-integration — Deep-dive Analysis

**Status:** Research notes — not scheduled for implementation on this branch
**Date:** 2026-04-21
**Scope:** Evaluate whether and how `rednote-hilab/dots.ocr` could be adopted as an OCR backend alongside the existing Kreuzberg + pytesseract/surya stack. Documenting findings and integration options for future consideration; no code changes proposed as part of this work.

---

## 1. Context

The project ingests TTRPG sourcebooks (scanned PDFs, often 300+ pages, multi-column, German/English, dense with **stat blocks, tables, sidebars, and captioned illustrations**) into an R2R RAG pipeline so the GM can semantic-search them via Claude Code MCP. The current OCR stack works for clean, simple scans but has known weak points on layout-rich pages. This note asks whether dots.ocr — a layout-aware vision-language model — could materially improve extraction quality, and if so, how it would be wired in without breaking what works.

Before any adoption, we need a clear view of what exists, what dots.ocr actually offers beyond marketing claims, and where the trade-offs land *specifically for TTRPG sourcebooks*, not for generic document corpora.

---

## 2. What exists today

Two independent pipelines, both terminating in `R2RClient.documents.create(...)`:

### 2a. Kreuzberg-backed, flat-text pipeline

- **File:** `scripts/extract_text.py:46-50`
- **Shape:**
  ```python
  config = ExtractionConfig(ocr=OcrConfig(backend=engine, language=language))
  result = extract_file_sync(filepath, config=config)
  return result.content   # flat string
  ```
- **Backends exposed via CLI** (`extract_text.py:34-36`): `tesseract` (default), `easyocr`, `paddleocr`.
- **Output contract:** a single string. No layout, no confidence, no page boundaries, no table structure. This is the contract Kreuzberg imposes.
- **R2R path:** `client.documents.create(raw_text=content, metadata={"title": title})` — so R2R does its own chunking on the flat text.

### 2b. Manual per-page pipeline with confidence scoring

- **File:** `scripts/ocr_preprocess.py:44-125`
- **Shape:** `pdf2image` → per-page image → `pytesseract` **or** `surya.recognition` → `PageOcrResult(page_number, text, confidence)` → `[f"[Page {n}]\n{text}" for …]` chunks → `client.documents.create(chunks=chunks, metadata=...)`.
- **Confidence threshold:** `LOW_CONFIDENCE_THRESHOLD = 0.7` (line 25). Pages below this are reported but *still ingested*.
- **Metadata schema** (`ocr_preprocess.py:80-86`): `book_title` (required), `chapter`, `page_range` — matched to `mcp-servers/sourcebooks/server.py:50-54`.
- **Classifier:** `scripts/detect_pdf_type.py` buckets PDFs into `text-native` / `image-only` / `mixed` via `pdfplumber` character counts. Users decide manually which pipeline to run.

### 2c. What this stack does badly (from `requirements/image-pdf-ingestion.md`)

- Silent empty output on image PDFs ingested via Light Mode R2R.
- No automatic routing between pipelines — the user picks.
- No layout awareness: multi-column pages get read left-to-right across columns, stat blocks bleed into body text, table cells lose their grid.
- Chunking granularity is page-bounded (`[Page 47]\n…`). For RAG, this means a "Beholder" stat block split across pages 46–47 becomes two disjoint chunks that each half-answer a query.

These are real, documented pain points — not hypothetical.

---

## 3. What dots.ocr is

- **Model:** 1.7B-parameter Qwen2.5-1.5B LLM + 1.2B NaViT vision encoder, released July 2025 (rednote-hilab), updated as `dots.mocr` March 2026. MIT license — commercial use permitted. ~6 GB download.
- **Shape:** a single VLM that does **layout detection + reading-order + OCR + table HTML + formula LaTeX** in one forward pass, prompt-controlled.
- **Output:** JSON with bounding boxes + category labels (`Text`, `Title`, `Table`, `Formula`, `Picture`, `Caption`, …), plus concatenated Markdown and per-region content (HTML for tables, LaTeX for formulas).
- **Serving:** official path is **vLLM ≥ 0.11.0** with an OpenAI-compatible REST endpoint. HuggingFace `AutoModel` works but is slower. No official Python SDK.
- **Benchmarks it reports:**
  - OmniDocBench v1.5: 88.4 overall (below GLM-OCR 94.6, PaddleOCR-VL-1.5 94.5, MinerU 2.5 ~90.7 — but compact).
  - TableTEDS: 88.6% EN / 89.0% CH — leads its weight class.
  - Reading-order error: lowest among tested open systems.
  - Claims 100-language support with strong multilingual deltas over smaller models.
- **Known failure modes** (from the upstream blog + GitHub issues): handwriting totally unsupported; footers and page numbers frequently missed; no figure extraction (captions yes, image bytes no); ~10% hallucination rate reported independently in LlamaIndex's ParseBench; blank-page handling brittle in v1.5.

The 1.7B parameter count is the headline — it matches formula accuracy of 40× larger VLMs while fitting on a 12–24 GB consumer GPU.

---

## 4. Quality comparison (sourcebook-relevant)

| Dimension | tesseract | easyocr (via Kreuzberg) | surya | **dots.ocr** |
|---|---|---|---|---|
| Clean single-column scans | ★★★★ | ★★★★ | ★★★★ | ★★★★★ |
| Multi-column reading order | ★★ (bleeds columns) | ★★ | ★★★ | ★★★★★ |
| Stat blocks / tables as structure | ✗ (flat text) | ✗ | ★ (some layout) | ★★★★★ (HTML) |
| Sidebars separated from body | ✗ | ✗ | ★★ | ★★★★★ (category labels) |
| German + English code-switching | ★★★ (needs lang flag) | ★★★ | ★★★ | ★★★★ (natively multilingual) |
| Captioned illustrations | ✗ (caption floats) | ✗ | ★ | ★★★★ (`Caption` category) |
| Handwriting | ★★ | ★★ | ★★ | ✗ (explicit non-goal) |
| Hallucination risk | minimal (character-level) | minimal | low | **~10% (per ParseBench)** |
| Per-line confidence for flagging | ✓ (conf scores) | partial | ✓ | ✗ (VLM tokens, no per-char conf) |

**The trade is sharp**: dots.ocr's structural output is transformative for the *layout* problems this repo actually has (columns, stat blocks, sidebars), but it introduces a *new* failure mode (fabricated content) that the current stack doesn't have. For a "GM reference" RAG, hallucinated monster HP is worse than a garbled OCR line — garbled looks wrong; hallucination looks right.

---

## 5. Performance comparison (for a 320-page sourcebook)

| Backend | Hardware | Per-page | 320-page book | Notes |
|---|---|---|---|---|
| tesseract (CPU) | 4 cores | ~0.5–1 s | **3–5 min** | Baseline |
| easyocr (GPU) | consumer GPU | ~0.3–0.8 s | 2–4 min | If CUDA present |
| surya (CPU/GPU) | 8-core or GPU | ~1.5–3 s | 8–15 min | Slower, better layout |
| **dots.ocr (vLLM)** | 12–24 GB GPU | **6–20 s** (issue #117 reports 20 s on RTX 4000 Ada SFF) | **32 min – 1 h 45 min** | vLLM continuous batching helps; still 10×+ slower |

Other operational costs dots.ocr uniquely carries:

- **6 GB model download** (one-time) and **cold-start latency** dominated by model load.
- **vLLM 0.11.0+ hard pin**; conflicts with some transformers versions (GH issue #95). Needs its own process/container.
- **GPU requirement**: the project's devcontainer has no GPU and the `image-pdf-ingestion.md` §8 explicitly calls "Running OCR inside the devcontainer" out of scope. dots.ocr must run on the host — or on a separate GPU container (`vllm/vllm-openai:v0.11.0`). This mirrors how R2R's own Docker Full Mode runs OCR server-side; it is not a new architectural violation, but it is a new service to run.
- **No CPU or Apple Silicon path** documented. Users without an NVIDIA GPU are out.

---

## 6. Three integration patterns (and which to prefer)

### Pattern A — Add as a Kreuzberg backend (via upstream)

`OcrConfig(backend="dots")` inside `extract_text.py`. Requires upstream Kreuzberg PR. **Rejected.** Kreuzberg's interface collapses output to `result.content` (flat string), which deletes dots.ocr's entire value proposition. Paying the GPU cost for flat text is negative ROI vs. tesseract.

### Pattern B — New engine branch in `ocr_preprocess.py`

Add `elif engine == "dots":` to `ocr_page()` (`ocr_preprocess.py:44-59`), returning `PageOcrResult(page_number, text, confidence)` where `text` is dots.ocr's Markdown and `confidence` is a proxy (e.g., page-level token logprob mean, or 1.0 if non-empty else 0.0).

**Pro:** minimal blast radius, fits existing pipeline, unlocked via `--engine dots` CLI flag.
**Con:** still flattens structure to one string per page. Chunks remain `[Page N]\n…`. Tables come through as Markdown (better than raw OCR) but bboxes, reading order, and category labels are discarded. Uses ~10× the compute for ~1.5× the quality gain. **Worth it as a first step only if the MVP is "does dots.ocr produce usable markdown at all on our specific sourcebooks".**

### Pattern C — New parallel pipeline `scripts/dots_ingest.py` (recommended if adopted)

A sibling to `ocr_preprocess.py`, not a replacement. Exploits the structured output end-to-end:

```
PDF → pdf2image (reuse)
    → vLLM /v1/chat/completions (dots.ocr, layout+OCR prompt)
    → JSON regions per page: {category, bbox, content, page}
    → section-aware chunker:
        · concatenate consecutive `Text`/`Caption` regions under a `Title`
        · emit Table regions as standalone chunks (preserve HTML)
        · cross page boundaries when a section continues
    → R2R: client.documents.create(chunks=chunks, metadata={
          book_title, chapter, page_range,
          section_title, region_categories, has_tables, bbox_ref
      })
```

**Pros:**
- Chunks align to **sections**, not pages. A "Beholder" stat block on pp. 46–47 is one chunk with `section_title="Beholder"` metadata. This is a material improvement for RAG recall on named entity queries — exactly the GM's usage pattern.
- Table HTML survives into R2R. Queries like "what's the damage of a critical hit on table 3-4" become answerable.
- Per-chunk metadata (`region_categories`) enables filtering at query time ("only Table chunks", "only Caption chunks for illustrations").
- Confidence proxy: flag pages where dots.ocr output is suspiciously short, fully blank, or has no `Title`/`Text` regions detected — these are the hallucination risk surface.
- Stays out of Kreuzberg's way. `extract_text.py` remains untouched. `ocr_preprocess.py` remains the "fast, no-GPU" path.

**Cons:**
- New file, new tests, new vLLM service the user must run. More operational surface.
- Requires a hallucination-detection pass *we write ourselves* — upstream doesn't provide per-region confidence.

### Pattern D (creative) — Selective re-OCR using dots.ocr as a "rescue" backend

Bolt onto the existing Pattern B, but flip the default: run **tesseract first** for speed (~5 min for a book), then use `ocr_preprocess.py`'s `low_confidence_pages` list (threshold 0.7, already computed at `ocr_preprocess.py:94`) to *selectively* re-OCR just the flagged pages through dots.ocr. A 320-page book with 12 low-confidence pages becomes 5 min tesseract + ~3 min dots.ocr rescue instead of 90 min full dots.ocr.

This is the highest-leverage pattern if the goal is **quality uplift on the problem pages** rather than "use the fancy model everywhere". It also puts dots.ocr's hallucination risk *only* on pages where tesseract already failed — which is exactly where the trade is favorable.

### Pattern E (more creative) — dots.ocr → Obsidian vault bridge

The user maintains an Obsidian vault (see `obsidian_vaults/GM-Vault-Pathfinder2e/…`). dots.ocr's structured output (Title regions + Text regions + Table HTML) maps almost 1:1 to Obsidian note structure. A separate tool could turn a sourcebook PDF into a folder of linked `.md` files with `![[image-p47-bbox.png]]` embeds for captioned illustrations — converting a scanned book into a browsable vault section, not just searchable text in R2R. Out of scope for any near-term integration but worth noting because dots.ocr is the only backend in this analysis that makes it feasible.

---

## 7. Drawbacks — honest enumeration

1. **Hallucination rate ~10%** (ParseBench). For a *factual reference* RAG, this is the largest single risk. Tesseract garbles; it doesn't invent.
2. **GPU requirement excludes Persona B** ("Python-only, no Docker" — `image-pdf-ingestion.md:22-27`). vLLM needs CUDA. No MLX, no CPU path documented. Adopting dots.ocr cannot replace tesseract/surya; it can only supplement.
3. **10×+ slower per page**. Fine for batch ingestion of a library; painful for iterative re-runs during tuning.
4. **Dependency conflict risk**: vLLM 0.11.0 pin, transformers version conflicts (issue #95). Best isolated in its own container, not installed in the main project venv.
5. **Project maturity**: 140 open issues, July 2025 release, rebranded to `dots.mocr` in March 2026. Not a "set and forget" dependency.
6. **No figure/image byte extraction**. Illustrations are detected as `Picture` regions with bboxes, but the pixels aren't returned — you need a separate crop step using the bbox against the original page image.
7. **Footers/page numbers missed** — acknowledged upstream. Minor for sourcebook RAG, but "see page 47" cross-references in the text won't align with extracted page metadata if the printed page numbers drift from PDF page numbers.
8. **Confidence signal is weaker** than tesseract/surya. The project's `LOW_CONFIDENCE_THRESHOLD = 0.7` mechanism (`ocr_preprocess.py:25`) doesn't translate directly; we'd need to design a proxy (token logprobs, region count, empty output detection).
9. **Architectural fork**: Pattern C creates a third pipeline on top of the existing two. That's a cost the repo should accept knowingly — it's not a simplification.
10. **Chinese benchmark weighting**: upstream reports lean on CJK corpora. English + German performance claims are less directly validated; real-world testing on a German Pathfinder sourcebook is required before trusting them.

---

## 8. Tentative recommendation (if ever pursued)

**Do not replace the existing stack. Add dots.ocr as Pattern C (new pipeline) with Pattern D (selective rescue) as the first observable payoff.**

Rationale:
- The existing Kreuzberg + tesseract/surya stack is the right default: fast, CPU-capable, well-tested, low-risk. Keep it.
- dots.ocr earns its keep only where structural output matters — multi-column reading order, stat blocks, tables. A new pipeline isolates the risk (hallucinations, GPU dep, service dependency) and lets the user opt in per-book or per-page.
- Pattern D layered on Pattern C gives the fastest concrete quality win: the existing confidence scoring already identifies exactly where tesseract fails, and dots.ocr is at its best precisely on those layout-complex pages.

**Smallest proof-of-value experiment (if revisited):**
1. Stand up vLLM on the host with dots.ocr (`vllm/vllm-openai:v0.11.0`, model `rednote-hilab/dots.ocr`).
2. Write a thin `scripts/dots_client.py` that calls the OpenAI-compatible endpoint with a single page image and parses the layout JSON.
3. Pick **one** real sourcebook page the project currently handles badly (a stat-block page, a 2-column table page, a German page).
4. Run it through tesseract, through `ocr_preprocess.py --engine surya`, and through dots.ocr. Compare outputs side-by-side against the printed page.
5. **Only if** the dots.ocr output is materially better on the target pages, proceed to Pattern C (section-aware ingestion) and Pattern D (selective rescue). If not, archive the idea — the 10× slowdown isn't worth it.

This gatekeeps further investment on *measured* quality delta, not upstream benchmark claims.

---

## 9. Files that would be touched if pursued

| Path | Role | Change type |
|---|---|---|
| `scripts/dots_client.py` | NEW — vLLM client + JSON parsing | New file |
| `scripts/dots_ingest.py` | NEW — full Pattern C pipeline | New file |
| `scripts/ocr_preprocess.py:117-125` | Add optional `rescue_with_dots=True` kwarg that re-OCRs `low_confidence_pages` via `dots_client` | Surgical edit |
| `scripts/test_dots_ingest.py` | NEW — fixture-based tests (mock vLLM) | New file |
| `requirements/image-pdf-ingestion.md` | Add FR-7/FR-8 documenting dots.ocr path and Persona D ("GPU-equipped user") | Edit |
| `docs/design.md` | Add dots.ocr pipeline to architecture section | Edit |
| `docs/troubleshooting.md` | Add hallucination warning + verification guidance | Edit |

Not touched: `extract_text.py` (Kreuzberg facade stays pure), Kreuzberg itself, R2R config.

Reused (not duplicated): `pdf2image.convert_from_path` from `ocr_preprocess.py:67-73`, the metadata schema from `ocr_preprocess.py:80-86`, `R2RClient.documents.create(chunks=...)` pattern from `ocr_preprocess.py:89-101`, the confidence-flagging and reporting style from `OcrReport`/`format_report`.

---

## 10. Verification plan (if ever pursued)

End-to-end acceptance, in order:

1. **Service health**: `curl http://localhost:<port>/v1/models` returns `rednote-hilab/dots.ocr`. No GPU → stop here, the whole plan is moot on this host.
2. **Single-page ground truth**: pick 3 representative sourcebook pages (stat-block, 2-column narrative German, table page). Manually transcribe ground truth. Run tesseract, surya, dots.ocr. Score character error rate + table cell F1 for each. Pass bar: dots.ocr wins on structure, loses by < 5 CER on plain text.
3. **Hallucination probe**: feed dots.ocr a **blank page** and a **pure-image page** (illustration with no text). Expected: empty or near-empty output. Fail if it fabricates paragraphs. This is the #1 risk surface.
4. **Pattern C integration**: ingest one full chapter (~20 pages) via `dots_ingest.py`. Inspect resulting R2R chunks: section boundaries should align to `Title` regions, not page breaks. Table chunks should be marked `has_tables=true` in metadata.
5. **Pattern D rescue path**: take a book already ingested via `ocr_preprocess.py` whose report shows `low_confidence_pages`. Run the rescue. Verify that those page chunks are *replaced* (not duplicated) in R2R and that their content is measurably better by a query-based spot check (`verify_ingestion.py --book-title …`).
6. **Multilingual smoke test**: a German Pathfinder page with English game terms ("saving throw", "DC"). Confirm no language corruption and that reading order survives on 2-column layouts.
7. **Regression guard**: running existing `scripts/test_extract_text.py` and `scripts/test_ocr_preprocess.py` still passes — no change to their contracts.

If any of steps 2, 3, or 5 fail, the integration does not ship; document the failure mode and reconsider.

---

## 11. Sources

- GitHub: <https://github.com/rednote-hilab/dots.ocr>
- Paper: <https://arxiv.org/html/2512.02498v1>
- HuggingFace: <https://huggingface.co/rednote-hilab/dots.ocr>
- OmniDocBench leaderboard: <https://www.codesota.com/ocr/benchmark/omnidocbench>
- LlamaIndex ParseBench (hallucination rate): <https://www.llamaindex.ai/blog/parsebench>
- vLLM dots.ocr support: <https://docs.vllm.ai/en/latest/api/vllm/model_executor/models/dots_ocr/>
- Upstream issues referenced: #95 (VRAM/vLLM pin), #117 (throughput), #185 (handwriting), #198 (output format), #292 (blank pages)
