# Image PDF Ingestion — Requirements

## 1. Problem Statement

TTRPG sourcebooks are frequently scanned PDFs — image-only pages with no selectable text. The Worldbuilding Assistant's DESIGN.md (line 23) states that R2R "handles OCR, chunking, and vector indexing" for these books, but this only works under a specific R2R deployment mode (Docker Full Mode with Unstructured.io).

Three critical gaps exist today:

1. **Silent failure.** In Light Mode (`pip install r2r` + `r2r serve`), image PDFs ingest without error but produce empty or garbage text. Users get zero search results with no indication of what went wrong.
2. **No detection or verification.** Users have no way to determine whether their PDFs are text-native or image-based, and no way to verify OCR quality after ingestion.
3. **No fallback path.** Users who cannot run Docker Full Mode have no supported way to ingest image PDFs at all.

## 2. User Personas & Scenarios

### Persona A: Docker-Comfortable User

- Can run Docker Full Mode (`compose.full.yaml` with Unstructured.io)
- Needs clear documentation that Full Mode is required for scanned books
- Scenario: Ingests a scanned D&D Monster Manual, expects OCR to happen server-side

### Persona B: Python-Only User

- Cannot or won't run Docker (resource constraints, corporate policy, preference)
- Uses Light Mode (`pip install r2r`)
- Needs a client-side OCR preprocessing path
- Scenario: Wants to ingest a scanned Pathfinder sourcebook without Docker

### Persona C: Mixed Library User

- Owns a mix of text-native PDFs (purchased digitally) and scanned PDFs (older books)
- Needs to identify which books require OCR before ingesting
- Scenario: Has 20 sourcebooks, wants to batch-classify them before choosing an ingestion strategy

## 3. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | System MUST clearly document which R2R mode supports image PDFs (Docker Full only) | P0 |
| FR-2 | System SHOULD provide a PDF type detection script that identifies image-only vs text-native PDFs | P1 |
| FR-3 | System SHOULD provide a client-side OCR preprocessing script for users who can't run Docker Full Mode | P1 |
| FR-4 | System SHOULD provide an OCR quality verification tool that spot-checks extracted text | P1 |
| FR-5 | System MAY extend MCP `ingest_document` to accept base64-encoded file content for small documents | P2 |
| FR-6 | QUICKSTART.md MUST be updated with image PDF guidance once tooling exists | P0 |

## 4. FR-2: PDF Type Detection Script

**File:** `scripts/detect_pdf_type.py`

**Purpose:** Classify PDFs as text-native, image-only, or mixed so users know which ingestion path to use.

**Interface:**

```
python scripts/detect_pdf_type.py /path/to/book.pdf
python scripts/detect_pdf_type.py /path/to/pdf/directory/
```

**Output (per file):**

```
Monster_Manual.pdf        image-only   (0 of 320 pages have extractable text)
Players_Handbook.pdf      text-native  (318 of 320 pages have extractable text)
Old_Campaign_Guide.pdf    mixed        (200 of 400 pages have extractable text)
```

**Classification logic:**

| Extracted text per page | Classification |
|---|---|
| >= 50 characters on >= 90% of pages | `text-native` |
| < 50 characters on >= 90% of pages | `image-only` |
| Otherwise | `mixed` |

**Method:** Attempt text extraction with `pdfplumber`. For each page, count extracted characters. If character count falls below threshold (50 chars/page), that page is classified as image-based.

**Dependencies:**

| Package | Type | Install |
|---|---|---|
| `pdfplumber` | Python | `pip install pdfplumber` |

**Runs on:** Host machine (where PDFs live).

## 5. FR-3: Client-Side OCR Preprocessing Script

**File:** `scripts/ocr_preprocess.py`

**Purpose:** Extract text from image PDFs via OCR on the host machine, then ingest the resulting text into R2R — providing a path for users who cannot run Docker Full Mode.

**Interface:**

```
python scripts/ocr_preprocess.py /path/to/book.pdf \
    --book-title "Monster Manual" \
    --chapter "Chapter 1: Monsters A-Z" \
    --page-range "1-320" \
    --engine tesseract

python scripts/ocr_preprocess.py /path/to/book.pdf \
    --book-title "Monster Manual" \
    --engine surya
```

**Pipeline:**

```
PDF file
  → Page images (pdf2image / Pillow)
  → OCR per page (pytesseract or surya-ocr)
  → Chunked text (with page boundaries preserved)
  → R2R ingestion via SDK (raw_text or chunks parameter)
  → Document ID + per-page confidence scores
```

**Metadata preservation:** The script MUST attach metadata matching the schema used by `mcp-servers/sourcebooks/server.py` (lines 50-54):

```python
metadata = {
    "book_title": str,   # required
    "chapter": str,      # optional
    "page_range": str,   # optional
}
```

**Engine selection:**

| Engine | Flag | System deps | Notes |
|---|---|---|---|
| Tesseract | `--engine tesseract` (default) | `tesseract-ocr`, `poppler-utils` | Fast, mature, good accuracy on clean scans |
| Surya | `--engine surya` | None (Python-native) | No system deps, slower, handles complex layouts better |

**Output:**

```
Ingested: Monster Manual
  Document ID: 7a3f...
  Pages processed: 320
  Average confidence: 0.87
  Low-confidence pages: 12, 45, 201
```

**Dependencies:**

| Package | Type | Install |
|---|---|---|
| `pdf2image` | Python | `pip install pdf2image` |
| `Pillow` | Python | `pip install Pillow` |
| `pytesseract` | Python | `pip install pytesseract` |
| `tesseract-ocr` | System | `apt install tesseract-ocr` |
| `poppler-utils` | System | `apt install poppler-utils` |
| `surya-ocr` | Python (optional) | `pip install surya-ocr` |
| `r2r` | Python | `pip install r2r` |

**Runs on:** Host machine.

## 6. FR-4: OCR Quality Verification

**File:** `scripts/verify_ingestion.py`

**Purpose:** After ingesting a document (via any method), verify that the extracted text is usable — not empty, not garbled, and searchable.

**Interface:**

```
python scripts/verify_ingestion.py --document-id 7a3f...
python scripts/verify_ingestion.py --book-title "Monster Manual"
```

**Checks performed:**

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| Document exists in R2R | Document found with status `success` | — | Document not found or status is not `success` |
| Chunk count | Reasonable for document size (> 10 chunks for a book) | Low chunk count (< 10) | Zero chunks |
| Text quality | Chunks contain recognizable English words | > 20% of chunks contain garbled text (high non-ASCII ratio, no dictionary words) | > 50% of chunks are garbled |
| Search coherence | Sample search for book title returns relevant chunks | Results returned but low relevance scores (< 0.3) | No results or all scores < 0.1 |

**Output:**

```
Verification: Monster Manual (ID: 7a3f...)
  [PASS] Document exists — status: success
  [PASS] Chunk count — 847 chunks (expected: 500-1500 for 320 pages)
  [WARN] Text quality — 15% of sampled chunks have garbled text
         → Pages 12, 45, 201 may have poor OCR quality
  [PASS] Search coherence — "beholder" returned 5 results, avg score 0.72

Overall: WARN — document is usable but some pages may have OCR issues
```

**Dependencies:**

| Package | Type | Install |
|---|---|---|
| `r2r` | Python | `pip install r2r` |

**Runs on:** Host machine (uses R2R SDK against `localhost:7272`).

## 7. FR-6: QUICKSTART.md Updates

Deferred until FR-2/FR-3/FR-4 scripts exist. The following changes will be needed:

### 7.1. "PDF Types" callout in Step 2

Add a callout box after the current ingestion instructions explaining the difference between text-native and scanned/image PDFs, and why it matters.

### 7.2. Decision tree

```
Are your PDFs scanned (image-only)?
├── Don't know → Run: python scripts/detect_pdf_type.py /path/to/pdfs/
├── Yes, and I can run Docker
│   └── Use Docker Full Mode (compose.full.yaml) — OCR happens server-side
├── Yes, and I can't run Docker
│   └── Use: python scripts/ocr_preprocess.py /path/to/book.pdf --book-title "..."
└── No, they're text-native
    └── Use: r2r documents create /path/to/book.pdf (current instructions)
```

### 7.3. Detection script usage in Step 2

Show `detect_pdf_type.py` as an optional first step before ingesting.

### 7.4. Verification step after ingestion

Show `verify_ingestion.py` as a recommended post-ingestion check.

### 7.5. Troubleshooting additions

| Symptom | Cause | Fix |
|---|---|---|
| Search returns no results for an ingested book | Image PDF ingested without OCR (Light Mode) | Use Docker Full Mode or `ocr_preprocess.py` |
| Search returns garbled/nonsensical text | Poor OCR quality | Re-ingest with different engine or check scan quality |
| `detect_pdf_type.py` says "mixed" | PDF has some text pages and some image pages | Ingest in Full Mode, or preprocess image pages only |

## 8. Non-Requirements (Out of Scope)

The following are explicitly out of scope for this project:

- **Extending MCP wrapper to accept `file_path`.** Architecture constraint: the devcontainer cannot access the host filesystem. `file_path` ingestion requires server-side file access. See `ARCHITECHTURE_beta.md` lines 148-150.
- **Running OCR inside the devcontainer.** No Tesseract available, no GPU access, not the right environment for heavy processing.
- **Automatic OCR detection during ingestion.** This would be an R2R server-side feature — outside our control.
- **Modifying R2R's ingestion pipeline.** We work with R2R as-is and provide client-side tooling around it.
- **Supporting non-PDF image formats** (TIFF, DJVU, etc.). PDFs only for MVP.
- **FR-5: MCP base64 ingestion.** Extending `ingest_document` to accept base64-encoded file content (P2) is deferred to a future milestone. Current workaround: use `raw_text`/`chunks` parameters via `ocr_preprocess.py`.

## 9. Dependencies & Constraints

### System packages (host machine)

| Package | Required for | Install |
|---|---|---|
| `tesseract-ocr` | FR-3 (Tesseract engine) | `apt install tesseract-ocr` |
| `poppler-utils` | FR-3 (PDF → page images) | `apt install poppler-utils` |

### Python packages (host machine)

| Package | Required for | Install |
|---|---|---|
| `pdfplumber` | FR-2 (PDF type detection) | `pip install pdfplumber` |
| `pdf2image` | FR-3 (PDF → page images) | `pip install pdf2image` |
| `Pillow` | FR-3 (image handling) | `pip install Pillow` |
| `pytesseract` | FR-3 (Tesseract engine) | `pip install pytesseract` |
| `surya-ocr` | FR-3 (Surya engine, optional) | `pip install surya-ocr` |
| `r2r` | FR-3, FR-4 (R2R SDK) | `pip install r2r` |

### Constraints

- All scripts run on the **host machine**, not inside the devcontainer.
- The devcontainer has no outbound internet — but the host does, so `pip install` works on the host.
- `surya-ocr` is Python-native but slower than Tesseract and less accurate on some scan types.
- `pdf2image` requires `poppler-utils` for the `pdftoppm` binary.
- R2R must be running at `localhost:7272` for FR-3 (ingestion) and FR-4 (verification).

## 10. Acceptance Criteria

| ID | Criterion | Validates |
|---|---|---|
| AC-1 | A user with a scanned TTRPG sourcebook can get from PDF to searchable content in R2R using either Docker Full Mode or `ocr_preprocess.py` | FR-1, FR-3 |
| AC-2 | A user running `detect_pdf_type.py` on a directory of PDFs gets a correct classification for each file | FR-2 |
| AC-3 | A user is warned BEFORE ingesting if their PDF is image-only and they are in Light Mode | FR-1, FR-2 |
| AC-4 | After ingestion, a user can verify OCR quality with `python scripts/verify_ingestion.py --book-title "..."` and get a PASS/WARN/FAIL report | FR-4 |
| AC-5 | `ocr_preprocess.py` attaches metadata (`book_title`, `chapter`, `page_range`) matching the schema used by `mcp-servers/sourcebooks/server.py` | FR-3 |
| AC-6 | QUICKSTART.md guides users through the correct ingestion path based on their PDF type | FR-6 |
| AC-7 | All script names (`detect_pdf_type.py`, `ocr_preprocess.py`, `verify_ingestion.py`) are consistent between this document, QUICKSTART.md, and the actual files | All |
