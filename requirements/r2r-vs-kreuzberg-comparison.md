# R2R vs Kreuzberg — Multi-format RAG Ingestion Comparison

> **Status:** Exploratory research — no implementation decisions made yet
> **Date:** 2026-03-20
> **Context:** M&A Due Diligence RAG pipeline, Docker Compose deployment, Claude Code via MCP

---

## The RAG Pipeline Has 6 Steps

```
Step 1: EXTRACTION — get text out of files (PDF, DOCX, JPEG, etc.)
Step 2: CHUNKING   — split text into pieces
Step 3: EMBEDDING  — turn text into vectors (via Ollama in our setup)
Step 4: STORAGE    — put vectors in pgvector/Postgres
Step 5: SEARCH/RAG — find relevant chunks, generate answers
Step 6: API/MCP    — expose it all to Claude Code
```

**R2R does ALL 6 steps.** It's a complete RAG system: parse → chunk → embed → store → search → serve.

**Kreuzberg does ONLY step 1.** It extracts text from documents. It doesn't chunk, embed, store, search, or serve anything.

**They are complementary, not competing.** The question is: should R2R handle extraction (step 1) itself, or should kreuzberg do extraction and feed text into R2R for steps 2–6?

---

## What "Bypasses R2R's Native Parsing" Means

When you call `R2R.documents.create(file_path="contract.pdf")`, R2R uses its own built-in parser (BasicPDFParser, or Unstructured.io in Docker Full Mode) to extract text. If R2R's team ships a better PDF parser next version, you benefit automatically.

If instead you do `kreuzberg.extract_file("contract.pdf")` and feed the raw text to R2R via `documents.create(raw_text=...)`, R2R never sees the original PDF. You skip R2R's parser entirely. Parser improvements in R2R updates won't help you — you've decoupled extraction from the rest of the pipeline.

**Whether this matters depends on extraction quality:**
- If R2R's parsers are good enough for your documents → let R2R handle it (simpler)
- If kreuzberg produces better text (especially for scanned docs, images, complex layouts) → use kreuzberg for extraction, R2R for everything else

---

## Format-by-Format Comparison

| Dimension | R2R native extraction | Kreuzberg extraction → R2R |
|---|---|---|
| **Text-native PDFs** | Excellent (BasicPDFParser or Unstructured.io) | Excellent (Rust PDF parser) |
| **Scanned/image PDFs** | Good in Docker Full Mode (Unstructured.io + Tesseract) | Excellent (3 OCR backends, automatic fallback, confidence scoring) |
| **Standalone images (JPEG/PNG)** | Basic (no OCR, just metadata) | Excellent (full OCR pipeline) |
| **Office docs (DOCX/XLSX/PPTX)** | Good (built-in parsers) | Excellent (88+ formats, table extraction) |
| **Deployment** | Already in Docker Compose | Add `pip install kreuzberg` + Tesseract to ingestion container |
| **Maintenance** | Zero — R2R handles it | You own the extraction step |
| **Quality visibility** | Opaque — R2R parses internally | Transparent — you see extracted text, quality scores, confidence before ingestion |

---

## M&A Due Diligence Considerations

- Extraction quality is paramount — bad OCR on a scanned contract = missed clauses = real liability
- Kreuzberg's confidence scoring lets you flag low-quality extractions for human review
- Kreuzberg's 3 OCR backends with fallback mean if Tesseract chokes on a document, PaddleOCR or EasyOCR may succeed
- R2R's native image handling has no OCR — standalone JPEG documents would produce empty text

---

## Target Architecture

```
                    ┌─────────────────────────────────────────┐
                    │          Docker Compose Stack            │
                    │                                         │
  Documents ──►     │  kreuzberg ──► R2R ──► pgvector         │
  (any format)      │  (extract)    (chunk+embed+store+search)│
                    │                    │                     │
                    │                    ▼                     │
                    │               MCP Server                │
                    └────────────────────┬────────────────────┘
                                         │
                                    Claude Code
```

**kreuzberg handles:** text extraction, OCR, format detection, confidence scoring, metadata
**R2R handles:** chunking, embedding (Ollama), vector storage, semantic search, RAG, MCP API

---

## Three Candidate Integration Patterns

### Pattern A: Kreuzberg Pre-processes Everything

```python
result = kreuzberg.extract_file_sync("document.pdf")
r2r_client.documents.create(raw_text=result.content, metadata={...})
```

All extraction goes through kreuzberg. R2R never sees original files. Maximum control over extraction quality.

**Pros:** Uniform extraction quality, confidence scoring on everything, full control
**Cons:** R2R parser improvements are bypassed, you own the extraction step

### Pattern B: R2R for Text-native, Kreuzberg for OCR/Images

```python
if needs_ocr(file) or not r2r_supports(file):
    result = kreuzberg.extract_file_sync(file)
    r2r_client.documents.create(raw_text=result.content, metadata={...})
else:
    r2r_client.documents.create(file_path=file, metadata={...})
```

Let R2R handle what it's good at. Use kreuzberg where R2R falls short. Two code paths but lighter.

**Pros:** Simpler for text-native docs, benefits from R2R parser updates
**Cons:** Two code paths, inconsistent quality visibility, format routing logic needed

### Pattern C: Kreuzberg with Folder-based Routing

Same as Pattern A, but with a folder structure that drives metadata and OCR config per content type.

```
incoming/
├── contracts/     → kreuzberg with high-quality OCR, metadata: type=contract
├── financials/    → kreuzberg with table extraction focus
└── correspondence/→ kreuzberg with standard OCR
```

**Pros:** Content-type-aware extraction, metadata automation
**Cons:** Most complex to set up, rigid folder structure

---

## No Decision Needed Now

This is exploratory. The comparison is saved for future decision-making when we're ready to extend the ingestion pipeline beyond PDF-only.
