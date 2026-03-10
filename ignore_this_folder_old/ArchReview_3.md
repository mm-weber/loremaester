# Architecture Review 3 of 3: R2R + Claude Code MCP Integration

> **Independent Review** — This is 3 of 3 redundant architecture reviews conducted in parallel by independent agents. Each agent explored the workspace, read the architecture proposal, and answered the same 5 questions without seeing other agents' work. See `ArchReview_1.md` and `ArchReview_2.md` for the other two reviews.

> **Agent Focus**: Plugin architecture, future-proofing, ING-05 (Obsidian) and ING-06 (Scientific PDF) extensibility

> **Date**: 2026-03-06

---

## Q1: Is the proposed architecture the best way to integrate an agnostic RAG system with Claude Code?

**No.** It is a reasonable starting point but has fundamental issues:

- **R2R's built-in MCP server is too thin and immature** as the sole integration point. Three tools (`search`, `ingest`, `list_documents`) are insufficient for production use. Missing: `delete_document`, `get_status`, `search_collection`, collection management, health checks.
- **The "agnostic" claim is false.** EPICs 1-3 are deeply coupled to R2R's internal APIs (`unstructured_local`, `client.documents.create(chunks=[...])`, R2R config syntax). Swapping to LlamaIndex or Haystack would require rewriting most tickets.
- **The recommended alternative** is a **custom MCP wrapper** (Python) that wraps R2R's SDK and exposes a richer, provider-agnostic tool surface. This follows the existing workspace pattern (Terraform MCP runs via Docker in `.claude/settings.json`). Long-term, design the wrapper's tool schemas as the stable contract with swappable backends.

---

## Q2: What needs to be improved?

**Missing architecturally:**
- An abstraction/adapter layer between MCP tools and the R2R backend
- A unified preprocessing pipeline for format-specific ingestion
- Ingestion status tracking and error handling
- Context window budget management (multi-retrieval could inject 18K+ tokens per turn)
- Observability (logging, metrics, tracing)
- Document versioning and deduplication

**Over-engineered:**
- **EPIC 5 (Model Provider Abstraction)** -- all 5 tickets. R2R's internal LLM roles are irrelevant to Claude Code. Collapse to a single `.env` config ticket.
- **AGT-03/AGT-04** (prompt templates) are premature -- these are tuning tasks, not architecture.
- **RET-03 (HyDE)** adds latency/cost; should be optional, not baseline.

**Wrong assumptions:**
- R2R's MCP tool surface is assumed but unverified
- The firewall blocks all domains needed to pull Docker images and Ollama models (showstopper)
- `faster-whisper` with `large-v3-turbo` is impractical on CPU-only devcontainer

---

## Q3: Can we adopt a plugin system for ING-05/ING-06?

**Yes.** The `/workspace/plugins/` directory has 14 plugins with a rich, standardized structure. I recommend building a `rag-ingest` Claude Code plugin that:

1. **Bundles a custom MCP server** via `.mcp.json` (supported but unused by current plugins)
2. **Has pluggable format preprocessors** -- a `preprocessors/` directory where each adapter implements `FormatPreprocessor.preprocess(file_path) -> Chunk[]`, with auto-discovery via a registry
3. **Exposes `/ingest` and `/search` slash commands**, ingestion skills that auto-activate, and optional file-change hooks

Adding new formats (Notion, Confluence, EPUB, code repos) means creating one Python file in `preprocessors/` implementing the base interface -- no changes to the MCP server or core pipeline. The hookify plugin demonstrates exactly this pattern of pluggable rule files with auto-discovery.

---

## Q4: MVP suggestion

**Essential (Phase 1, ~1-2 weeks):** ING-04 (metadata schema), ING-01 (PDF text), RET-01 (chunk config), RET-02 (embedding model), RET-05 (metadata injection), MCP-01 (modified: custom wrapper), MCP-03 (Claude Code config), MCP-04 (smoke test, PDF only), plus two new tickets: Docker Compose for R2R stack, and firewall allowlist fixes.

**Defer:** ING-02/03/05/06 (rich formats), RET-03/04 (HyDE/reranking), AGT-01-04 (agent layer), MOD-01-05 (model abstraction entirely).

**Phased roadmap:** Phase 1 (core pipeline) -> Phase 2 (rich ingestion + plugin system) -> Phase 3 (optimization: HyDE, reranking, prompt tuning) -> Phase 4 (hardening).

---

## Q5: Technical caveats

Ten specific risks identified:

1. **Docker-in-Docker nesting** -- R2R's Docker stack inside DinD creates triple nesting with 8 shared CPUs and ephemeral storage.
2. **No outbound internet** -- The firewall blocks `ghcr.io`, `ollama.ai`, `huggingface.co`. This is a **showstopper** that must be fixed first.
3. **R2R MCP server maturity** -- Schema instability, limited error reporting, unverified tool surface.
4. **Model role confusion** -- R2R has its own LLM (for HyDE, summarization) competing with Claude. Solution: configure R2R as retrieval-only, disable its agent/RAG features.
5. **Context window pressure** -- 3 queries x 6 chunks x 1024 tokens = ~18K tokens per turn, accumulating over conversation turns.
6. **Embedding model migration** -- Changing embedding models requires re-embedding all documents; the choice is effectively irreversible.
7. **Postgres persistence** -- DinD volumes are ephemeral; data is lost on container rebuild without explicit volume mapping.
8. **Ollama resource contention** -- `mxbai-embed-large` needs ~1.5GB RAM; concurrent with R2R and Postgres on 8 shared CPUs.
9. **No authentication** between Claude Code MCP client and R2R server.
10. **No incremental sync** for continuously updated sources like Obsidian vaults.

---

## Detailed Analysis (Initial Deep-Dive): Plugin Architecture

### 1. Existing Plugin Patterns Analysis

#### 1.1 Plugin Structure & Conventions

All Claude Code plugins follow a consistent structure:

```
plugin-name/
+-- .claude-plugin/
|   +-- plugin.json          # Minimal metadata (name, version, author)
+-- commands/                # Slash commands (markdown files)
+-- agents/                  # Specialized agents (markdown files)
+-- skills/                  # Reusable skill guidance (markdown files)
+-- hooks/                   # Event handlers (Python scripts + hooks.json)
+-- .mcp.json               # MCP server configuration (optional)
+-- README.md               # Plugin documentation
```

**Key observations:**
- `plugin.json` is intentionally minimal (just name/version/author) -- metadata is deferred to commands and agents
- Commands are markdown files with YAML frontmatter + prose instructions
- Agents are specialized markdown files (no code generation -- pure instruction)
- Skills are reusable guidance documents triggered by keywords
- Hooks are Python scripts that intercept Claude Code events (PreToolUse, Stop, SessionStart, etc.)
- No "plugin configuration schema" -- plugins use `.local.md` files in `.claude/` for user settings

#### 1.2 Extensibility Patterns Found

**Pattern 1: Hookify (Rule-Based Extensibility)**
- Uses Python-based rule engine with YAML frontmatter configuration
- Rules live as `.claude/hookify.<name>.local.md` files (user-created)
- Each rule has: enabled flag, event matcher, conditions (field/operator/pattern), action (warn/block), message
- Rules auto-load from `.claude/` directory without restart
- **Strength**: Zero-code extensibility, easy for users to add rules
- **Limitation**: Designed for blocking/warning, not pipeline transformation

**Pattern 2: Feature-Dev (Agent-Based Extensibility)**
- Specialized agents (code-explorer, code-architect, code-reviewer) launched in parallel
- Each agent has a markdown prompt file defining its focus
- **Strength**: Flexible, composable, good for complex analysis
- **Limitation**: No standardized agent discovery mechanism

**Pattern 3: Plugin-Dev (Meta-Plugin Architecture)**
- 7 specialized skills for plugin development (hook-dev, mcp-integration, plugin-structure, etc.)
- Each skill is a markdown file with progressive disclosure: core docs -> detailed references -> examples
- Skills are auto-triggered by keywords in the prompt
- **Strength**: Excellent for guiding plugin developers
- **Limitation**: Skills are guidance, not executable transformations

---

### 2. Analysis of R2R Ingestion Requirements

**ING-05 (Obsidian Vault Pre-Processor)**
- **Needs**: Strip/resolve wikilinks (`[[note-name]]`), parse YAML frontmatter, convert Obsidian markdown
- **Preserves**: Graph structure (linked notes) -- flat ingest loses semantic relationships
- **Challenge**: Current R2R ingestion is document-centric; Obsidian is graph-centric

**ING-06 (Scientific PDF Math/Formula Handling)**
- **Needs**: Use mathpix API or nougat (Meta) as pre-processor before R2R ingestion
- **Challenge**: External services (mathpix) or heavy models (nougat) -- preprocessing overhead

**Common Challenge:**
Both require **format detection -> preprocessing -> normalization -> R2R ingestion**:
```
Raw file (Obsidian vault / PDF)
  -> Detect format
  -> Apply format-specific preprocessor
  -> Normalize to R2R-ingestable format
  -> Ingest with R2R
  -> Optionally enrich metadata (graph, math LaTeX, etc.)
```

---

### 3. Proposed Plugin Architecture: "R2R Preprocessor Framework"

#### 3.1 Decision: Three-Layer Approach

Rather than a single plugin, a **three-layer architecture**:

**Layer 1: Claude Code Plugin** (`plugin-r2r-preprocessors`)
- Commands for preprocessing workflows
- Agents for format detection and coordination
- Skills for preprocessor-specific guidance
- Hooks for optional validation/progress tracking

**Layer 2: MCP Tools** (via R2R's MCP server or new `r2r-preprocessor-mcp`)
- Tools exposed to agents: `detect_format`, `preprocess_document`, `normalize_to_r2r_format`, `ingest_with_metadata`
- Handles async preprocessing (especially for heavy models like nougat)
- Communicates with R2R server

**Layer 3: Standalone Preprocessor Pipeline** (Python/Node scripts)
- Runs independently or via MCP
- Format-specific preprocessors (Obsidian parser, nougat wrapper, mathpix client, etc.)
- Metadata schema enforcement (ING-04)
- Can be used outside Claude Code (CI/CD, scripts, etc.)

#### 3.2 Proposed Plugin Structure

```
plugin-r2r-preprocessors/
+-- .claude-plugin/
|   +-- plugin.json
+-- commands/
|   +-- preprocess-and-ingest.md      # Main orchestration command
|   +-- batch-process-vault.md        # For Obsidian vaults
|   +-- detect-format.md              # Format detection only
+-- agents/
|   +-- format-detector.md            # Detects file format, suggests preprocessor
|   +-- preprocessor-orchestrator.md  # Coordinates preprocessing -> R2R ingestion
|   +-- metadata-validator.md         # Validates chunk metadata schema
+-- skills/
|   +-- obsidian-vault-ingestion/     # ING-05 guidance
|   |   +-- SKILL.md
|   |   +-- examples/
|   |   +-- references/
|   +-- pdf-math-handling/            # ING-06 guidance
|   |   +-- SKILL.md
|   |   +-- examples/
|   |   +-- references/
|   +-- preprocessor-development/     # How to add new preprocessors
|       +-- SKILL.md
|       +-- examples/
+-- hooks/
|   +-- preprocessing-progress.py     # Optional: track preprocessing status
+-- .mcp.json                         # References r2r-preprocessor MCP server
+-- README.md
```

#### 3.3 Core Architecture: Pluggable Preprocessor Registry

**Key Innovation**: A **preprocessor registry pattern** that makes adding new preprocessors trivial.

##### Preprocessor Interface (Abstract Contract)

Each preprocessor implements:

```python
class BasePreprocessor(ABC):
    """Abstract base for all format-specific preprocessors."""

    @property
    def format_name(self) -> str:
        """E.g., 'obsidian', 'pdf-scientific', 'notion', 'confluence', 'epub'"""
        pass

    @property
    def supported_extensions(self) -> List[str]:
        """E.g., ['.md', '.vault'] for Obsidian"""
        pass

    @property
    def detection_hints(self) -> Dict[str, Any]:
        """E.g., {'vault_dir': True, 'yaml_frontmatter': True, 'wikilinks': True}"""
        pass

    def detect(self, file_path: str, content: Optional[bytes] = None) -> float:
        """
        Confidence score 0.0-1.0 that this preprocessor handles the file.
        E.g., Obsidian detector returns 1.0 for files in a .obsidian/ directory.
        """
        pass

    def preprocess(self, file_path: str, config: Dict[str, Any]) -> PreprocessedDocument:
        """
        Transform raw file into standardized PreprocessedDocument.

        Returns:
        {
            'text': normalized_text,
            'metadata': {
                'source_file': '...',
                'source_type': 'obsidian',
                'page_or_timestamp': ...,
                'section_title': ...,
                'ingest_date': ISO-8601,
                'doc_version': '1.0',
                # Format-specific extensions:
                'obsidian_graph': {...},
                'math_latex': {...},
                'additional_metadata': {...}
            }
        }
        """
        pass

    def normalize(self, preprocessed: PreprocessedDocument) -> R2RIngestableDocs:
        """
        Convert preprocessed output to R2R chunk format.
        Applies ING-04 metadata schema uniformly.
        """
        pass
```

##### Preprocessor Registry (Discovery + Auto-Loading)

```python
class PreprocessorRegistry:
    """Auto-discovers and manages all available preprocessors."""

    def __init__(self, plugins_dir: str = None):
        self.registry = {}
        self.discover_preprocessors(plugins_dir or os.getenv('CLAUDE_PLUGIN_ROOT'))

    def register(self, preprocessor: BasePreprocessor):
        self.registry[preprocessor.format_name] = preprocessor

    def detect_format(self, file_path: str) -> Tuple[str, float]:
        """
        Auto-detect format by running all preprocessors' detect() methods.
        Returns: (format_name, confidence_score)
        """
        pass

    def get_preprocessor(self, format_name: str) -> BasePreprocessor:
        pass

    def list_preprocessors(self) -> List[Dict]:
        pass
```

##### Built-In Preprocessors

**Preprocessor 1: Obsidian Vault Preprocessor** (ING-05)

```python
class ObsidianPreprocessor(BasePreprocessor):
    format_name = "obsidian"
    supported_extensions = [".md", ".vault"]
    detection_hints = {
        'has_obsidian_folder': True,
        'yaml_frontmatter': True,
        'wikilinks': True,
    }

    def preprocess(self, file_path: str, config: Dict) -> PreprocessedDocument:
        """
        1. Parse YAML frontmatter
        2. Resolve [[wikilinks]] to graph edges
        3. Convert Obsidian markdown syntax to standard markdown
        4. Extract section headings as section_title
        5. Preserve graph links in metadata
        """
        pass
```

**Preprocessor 2: Scientific PDF Preprocessor** (ING-06)

```python
class ScientificPDFPreprocessor(BasePreprocessor):
    format_name = "pdf-scientific"
    supported_extensions = [".pdf"]
    detection_hints = {
        'has_math_content': True,
        'high_formula_density': True,
    }

    def preprocess(self, file_path: str, config: Dict) -> PreprocessedDocument:
        """
        1. Detect if PDF has heavy math/LaTeX
        2. If yes: route to mathpix API or nougat model
        3. Extract structured math expressions
        4. Convert to normalized LaTeX/MathML
        5. Preserve formula context in metadata
        """
        # config['ocr_engine'] = 'mathpix' | 'nougat' | 'pdfplumber'
        pass
```

##### Future-Proofing: Easy to Add New Preprocessors

To add support for **Notion**, **Confluence**, **EPUB**, or **Code Repos**, a user would:

1. **Create a new preprocessor class** (inherits from `BasePreprocessor`)
2. **Place it in** the preprocessors directory
3. **Implement 5 methods** (format_name, supported_extensions, detect, preprocess, normalize)
4. **Registry auto-discovers it** -- no registration code needed, just file placement

Example: Adding Notion support

```python
class NotionPreprocessor(BasePreprocessor):
    format_name = "notion"
    supported_extensions = [".notion", ".ndjson"]

    def detect(self, file_path: str, content: Optional[bytes] = None) -> float:
        if file_path.endswith('.notion') or 'notion-export' in file_path:
            return 0.95
        if content and b'"type":"page"' in content:
            return 0.7
        return 0.0

    def preprocess(self, file_path: str, config: Dict) -> PreprocessedDocument:
        # Parse Notion JSON/ndjson, extract page hierarchy, resolve database properties
        pass
```

---

### 4. Three-Layer Implementation Details

#### 4.1 Layer 1: Claude Code Plugin Commands

**Command: `/preprocess-and-ingest <file-or-vault-path>`**

```yaml
---
description: Detect format, preprocess, and ingest into R2R
argument-hint: <file-or-vault-path> [--format explicit-format] [--skip-detect]
allowed-tools: Read, Bash, MCP(r2r-preprocessor)
---

# Preprocess and Ingest into R2R

## Steps
1. User provides file/vault path
2. Format detection agent analyzes the file
3. Show detected format with confidence score
4. Suggest or confirm preprocessor to use
5. Launch preprocessing (via MCP tool)
6. Validate metadata schema (ING-04)
7. Ingest into R2R with normalized metadata
```

**Command: `/batch-process-vault <vault-path>`**

Special workflow for Obsidian vaults:
- Detects all `.md` files in vault
- Builds graph of wikilinks
- Processes files in dependency order (so backlinks are resolved)
- Preserves graph structure in metadata
- Creates "related documents" metadata edges

#### 4.2 Layer 2: MCP Server (`r2r-preprocessor-mcp`)

Exposed tools:

```json
{
  "tools": {
    "detect_format": {
      "description": "Auto-detect file format",
      "input": { "file_path": "string" },
      "output": { "format": "string", "confidence": "0.0-1.0", "preprocessor": "string" }
    },
    "preprocess_document": {
      "description": "Preprocess file using detected/specified preprocessor",
      "input": {
        "file_path": "string",
        "format": "string (optional, auto-detect if omitted)",
        "config": { "model": "mathpix|nougat|pdfplumber", "api_key": "..." }
      },
      "output": {
        "preprocessed_text": "string",
        "metadata": { "source_type": "...", "graph": "..." },
        "chunks_ready": "boolean"
      }
    },
    "validate_metadata": {
      "description": "Validate chunks conform to ING-04 metadata schema",
      "input": { "chunks": [{ "text": "...", "metadata": {} }] },
      "output": { "valid": "boolean", "errors": ["..."] }
    },
    "ingest_with_metadata": {
      "description": "Ingest preprocessed chunks into R2R with full metadata",
      "input": { "collection_id": "string", "chunks": [], "graph": "optional" },
      "output": { "ingested_count": "int", "document_ids": [] }
    }
  }
}
```

#### 4.3 Layer 3: Standalone Preprocessor Pipeline

A Python package (can be installed separately):

```
r2r-preprocessors/
+-- r2r_preprocessors/
|   +-- __init__.py
|   +-- base.py              # BasePreprocessor abstract class
|   +-- registry.py          # PreprocessorRegistry
|   +-- preprocessors/
|   |   +-- obsidian.py      # ING-05
|   |   +-- pdf_scientific.py # ING-06
|   |   +-- notion.py        # Future
|   |   +-- __init__.py
|   +-- metadata_schema.py   # ING-04 schema validation
|   +-- r2r_client.py        # Wrapper around R2R ingestion
|   +-- cli.py               # CLI tool: preprocess-ingest
+-- setup.py
+-- README.md
```

**CLI Usage** (runnable standalone):

```bash
# Auto-detect format and preprocess
python -m r2r_preprocessors.cli preprocess my-vault/ --output chunks.jsonl

# Explicit format + config
python -m r2r_preprocessors.cli preprocess paper.pdf --format pdf-scientific \
  --config '{"ocr_engine":"mathpix","api_key":"sk-..."}' --output chunks.jsonl

# Batch process Obsidian vault
python -m r2r_preprocessors.cli batch-vault my-obsidian-vault/ \
  --preserve-graph --output chunks.jsonl

# Then ingest to R2R
python -m r2r_preprocessors.cli ingest chunks.jsonl --r2r-url http://localhost:7667
```

---

### 5. Plugin Architecture: How It Supports Extensibility

#### 5.1 Adding a New Preprocessor (Minimal Code)

**Scenario**: User wants to add Confluence preprocessor

**Step 1**: Create one Python file implementing BasePreprocessor

```python
from r2r_preprocessors.base import BasePreprocessor

class ConfluencePreprocessor(BasePreprocessor):
    format_name = "confluence"
    supported_extensions = [".confluence", ".html"]

    def detect(self, file_path: str, content: Optional[bytes] = None) -> float:
        if file_path.endswith('.confluence'):
            return 1.0
        if b'confluence' in content:
            return 0.6
        return 0.0

    def preprocess(self, file_path: str, config: Dict) -> PreprocessedDocument:
        # Implementation
        pass
```

**Step 2**: Registry auto-discovers it (no registration code)

**Step 3**: User can now use `/preprocess-and-ingest` -- it will detect & use Confluence preprocessor

**That's it.** No modifying plugin manifests, no restarting, no boilerplate.

#### 5.2 Interaction with MCP

**Option A: Preprocessor runs in MCP server** (recommended for heavy operations)
- Mathpix API calls, nougat model invocations run server-side
- MCP tool returns preprocessed chunks

**Option B: Preprocessor runs client-side in Claude Code**
- Lighter formats (Obsidian, simple markdown)
- Can directly modify files if needed

**Hybrid recommendation:**
- Obsidian (ING-05): Client-side (fast, no external deps)
- PDF Scientific (ING-06): Server-side MCP tools (heavy models, slow)
- Format detection: Client-side (quick regex/heuristics)

#### 5.3 Metadata Preservation Through Pipeline

The schema (ING-04) is enforced at every stage:

```
Raw Obsidian file
  | [Obsidian preprocessor]
  +-- Extracts YAML frontmatter -> metadata.ingest_date, metadata.doc_version
  +-- Parses [[wikilinks]] -> metadata.obsidian_graph
  +-- Identifies sections -> metadata.section_title
  +-- Returns PreprocessedDocument with standardized metadata
  | [Normalize stage]
  +-- Validates metadata.source_file, metadata.source_type, etc. (ING-04)
  +-- Converts to R2R chunk format with metadata headers
  | [R2R ingestion]
  +-- Chunks stored with metadata queryable (RET-05: metadata injection into context)
```

---

### 6. Comparison: Plugin vs. MCP vs. Standalone

| Aspect | Claude Code Plugin | MCP Tool | Standalone CLI |
|--------|------------------|----------|-----------------|
| **Where it runs** | Client (Claude Code session) | Server (R2R MCP) | Anywhere (CI/CD, scripts) |
| **Discovery** | Auto-discovered by plugin registry | Exposed by MCP server config | Manual invocation |
| **Add new preprocessor** | Drop file in `preprocessors/` | Modify MCP server code | Extend Python package |
| **User experience** | `/preprocess-and-ingest` command | Agents call MCP tools | CLI tool or Python API |
| **Async/long operations** | Block Claude Code session | Can stream results via SSE | Run in background |
| **Metadata validation** | Can check before R2R | Can check before R2R | Can validate in pipeline |
| **Integration with R2R** | Via MCP to R2R server | Direct if MCP is R2R MCP | Direct via R2R SDK |

**Recommendation**: **All three layers**
1. **Plugin** = User-facing interface (commands, agents, guidance via skills)
2. **MCP** = Async preprocessing, heavy operations (mathpix, nougat)
3. **Standalone** = Reusable library, CI/CD pipelines, testing

---

### 7. Design Principles for Future-Proofing

#### 7.1 ING-05 & ING-06 as First-Class, But Not Special

Both are implemented as **regular preprocessors in the registry**, not hardcoded special cases. This means new preprocessors (Notion, Confluence, EPUB) require identical effort to add.

#### 7.2 Metadata Schema as Contract

The ING-04 metadata schema is:
- Enforced at preprocessing (all preprocessors must produce it)
- Validated before R2R ingestion (separate validation step)
- Queryable after ingestion (RET-05: metadata headers in context)

New preprocessors inherit ING-04 enforcement automatically. If schema evolves, all preprocessors benefit simultaneously.

#### 7.3 Format Detection is Composable

Each preprocessor provides `detection_hints` and `detect()`. Registry runs all detectors in parallel, picks highest confidence. Future preprocessors auto-integrate.

#### 7.4 Config is Flexible

Each preprocessor receives a `config` dict:

```python
{
    "mathpix_api_key": "...",
    "nougat_model": "0.1.0-small",
    "preserve_graph": True,
    "chunk_size": 1024,
    "chunk_overlap": 100,
}
```

New preprocessors can add new config keys without breaking others. Config can come from `.claude/r2r-preprocessors.local.md` (plugin settings pattern). Env vars can override via CLI.

---

### 8. Extensibility Hooks for Advanced Users

#### 8.1 Hook: Custom Preprocessor Discovery

Advanced users can extend the registry:

```
# In .claude/r2r-preprocessors.local.md
---
custom_preprocessor_paths:
  - /path/to/my/preprocessors
  - ~/.local/share/r2r-preprocessors
---
```

Registry loads preprocessors from both plugin directories and custom paths.

#### 8.2 Skill: "Building Custom Preprocessors"

A new skill teaches:
- How to inherit from BasePreprocessor
- The contract (5 methods)
- Testing patterns
- Common patterns (regex detection, metadata extraction, etc.)
- Example: Minimal preprocessor scaffold

#### 8.3 Agent: Preprocessor Validator

```
claude /preprocess-and-ingest <file> --validate-preprocessor my-custom
```

Runs format detection confidence, metadata schema validation, sample preprocessing + chunk inspection, and reports issues.

---

### 9. Integration with R2R MCP

The `plugin-r2r-preprocessors` plugin:
1. **Does NOT duplicate** R2R's MCP tools (search, ingest, list_documents)
2. **Adds preprocessing layer** BEFORE those tools are called
3. **Uses R2R's MCP ingest tool** after preprocessing complete

Integration flow:

```
Claude Code session
  | [User: /preprocess-and-ingest vault/]
  +-- Plugin command launches agents
  +-- Format-detector agent (local)
  +-- Preprocessor-orchestrator agent calls MCP: preprocess_document()
  +-- MCP server runs preprocessing (heavy operations)
  +-- MCP returns chunks with metadata
  +-- Orchestrator calls R2R's MCP ingest tool
  +-- User gets success message with document IDs
```

---

### 10. Implementation Roadmap

**Phase 1: Foundation (2-3 weeks)**
- [ ] Define BasePreprocessor interface
- [ ] Implement PreprocessorRegistry with auto-discovery
- [ ] Create Obsidian preprocessor (ING-05)
- [ ] Create Scientific PDF preprocessor with mathpix integration (ING-06)
- [ ] Implement ING-04 metadata schema validation

**Phase 2: Claude Code Integration (1-2 weeks)**
- [ ] Create plugin-r2r-preprocessors plugin structure
- [ ] Implement `/preprocess-and-ingest` command
- [ ] Create format-detector agent
- [ ] Create preprocessor-orchestrator agent
- [ ] Write skills guidance (Obsidian, PDF, custom preprocessor development)

**Phase 3: MCP Server (1-2 weeks)**
- [ ] Create r2r-preprocessor MCP server
- [ ] Expose: detect_format, preprocess_document, validate_metadata, ingest_with_metadata
- [ ] Integration test with R2R

**Phase 4: Future-Proofing & Docs (1 week)**
- [ ] Write custom preprocessor scaffold/template
- [ ] Document preprocessor interface thoroughly
- [ ] Create example: Notion preprocessor (demonstrates extensibility)
- [ ] Setup preprocessor testing utilities

---

### Summary

The proposed architecture provides:

1. **Immediate value for ING-05 & ING-06** -- Obsidian and PDF math handling work out of the box
2. **Trivial extensibility for future formats** -- Adding Notion, Confluence, EPUB requires only implementing BasePreprocessor (5 methods)
3. **Zero-friction user experience** -- Plugin commands + agents, no manual pipeline plumbing
4. **Metadata preservation** -- ING-04 schema enforced throughout, graph structure (Obsidian) preserved
5. **Architectural alignment** -- Uses existing Claude Code patterns (plugins, commands, agents, skills, MCP)
6. **Reusability** -- Standalone library means preprocessing works in CI/CD, scripts, local tools
7. **Scalability** -- Heavy operations (mathpix, nougat) can run server-side via MCP, don't block Claude Code

This design treats ING-05 and ING-06 not as special cases, but as the first two implementations of a general pluggable preprocessor framework.
