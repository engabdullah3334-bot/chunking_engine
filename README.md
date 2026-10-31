# `chunking_engine` — Context-Preserving Structural & Semantic Chunking

**`chunking_engine`** is a standalone, zero-dependency Python chunking package that transforms structured documents (or raw Markdown/plain text) into self-contained `Chunk` objects enriched with hierarchical chapter breadcrumbs and bilingual keyword metadata.

### Engineering Problem Solved
Naive fixed-character or token-window splitters slice through the middle of Markdown tables, sever quoted verses (`﴿...﴾`), mix unrelated chapters together, and strip section titles away from body paragraphs—causing severe context loss during vector retrieval (RAG) and machine translation.

`ChunkingEngine` solves this by tracking an active multi-level heading stack (`H1 > H2 > ... > H6`), flushing cleanly at meaningful section boundaries, keeping tables and ornate-bracketed quotations (`﴿...﴾`) atomic, applying intra-section sliding-window word overlap, and attaching both clean `content` and `contextualized_content` (`### Section Breadcrumb + content`) to every `Chunk`.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Testing](#testing)
- [License and Contributing](#license-and-contributing)

---

## Prerequisites

- **Operating System:** Windows, Linux, or macOS.
- **Python:** `>= 3.10`
- **External Libraries:** **None.** Implemented 100% with the Python Standard Library (`re`, `json`, `dataclasses`, `collections`, `pathlib`, `http.server`).

---

## Installation

### Option A: Within the Full Workspace

```powershell
git clone <repository-url> engines
cd engines
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# Zero external dependencies required
python -m chunking_engine --self-test
```

### Option B: Standalone Copy into Any External Project

```powershell
Copy-Item -Recurse .\chunking_engine C:\path\to\your_project\chunking_engine
```

---

## Usage

### 1. Python API Example

```python
from chunking_engine import ChunkingEngine

chunker = ChunkingEngine(
    max_words=350,
    overlap_words=50,
    min_section_words=40,
    top_k_tags=10,
)

# Accepts ExtractedDocument, dict, JSON file path, Markdown path, or raw string
chunks = chunker.chunk(extracted_doc)

for chunk in chunks:
    print(f"[{chunk.chunk_id}] {chunk.section_breadcrumb} ({chunk.metadata.word_count} words)")
    print("Smart Tags:", chunk.metadata.tags)

# Optional JSON export
chunker.save_to_json(chunks, "output/chunks.json")
```

### 2. Command-Line Interface & Calm Standalone Web UI

```powershell
# Chunk a structured JSON or Markdown file from the CLI
python -m chunking_engine handbook_structured.json --max-words 300 --overlap 40 --out chunks.json

# Launch the calm standalone Web UI in your browser
python -m chunking_engine --ui
```

### 3. Expected Input & Output Shapes

- **Input:** `ExtractedDocument` object (duck-typed via `.to_dict()`), structured `dict`, raw `pages` list, `Path` to `.json`/`.md`/`.txt`, or raw `str`.
- **Output (`list[Chunk]`, serialized via `Chunk.to_dict()`):**
  ```json
  [
    {
      "chunk_id": "handbook_chunk_0001",
      "chunk_index": 1,
      "content": "Modular architecture isolates responsibilities cleanly.",
      "chapter_context": ["Part 1: Architecture", "Chapter 1: Isolation"],
      "section_breadcrumb": "Part 1: Architecture > Chapter 1: Isolation",
      "contextualized_content": "### Part 1: Architecture > Chapter 1: Isolation\n\nModular architecture isolates responsibilities cleanly.",
      "metadata": {
        "page_start": 1,
        "page_end": 2,
        "word_count": 6,
        "char_count": 55,
        "tags": ["modular", "architecture", "isolates", "responsibilities"],
        "block_types": ["body"],
        "media_paths": [],
        "has_table": false,
        "has_quranic_verse": false,
        "language": "eng",
        "source_file": "handbook.pdf",
        "source_chunk_id": null,
        "translation_info": null
      }
    }
  ]
  ```

---

## Architecture

### Package File Structure

```text
chunking_engine/
├── __init__.py          # Exports ChunkingEngine, Chunk, ChunkMetadata, ChunkingConfig, extract_smart_tags
├── __main__.py          # Standalone CLI, --ui launcher, and --self-test suite
├── engine.py            # Input normalizer, atomic unit splitter, heading stack, & overlap buffer
├── schemas.py           # Chunk, ChunkMetadata, and ChunkingConfig dataclasses
├── tagger.py            # Pure-stdlib bilingual (Arabic/English) stopword-filtered TF keyword tagger
├── requirements.txt     # Documents zero external dependencies
├── ui/
│   ├── __init__.py
│   └── app.py           # Zero-dependency calm standalone HTTP Web UI (port 8703)
└── README.md
```

### Internal Data Flow

```text
Input (ExtractedDocument | dict | Path | str)
  │
  ▼
`_normalize_input_to_pages()` ──► Unified Page Blocks
  │
  ▼
`_block_to_units()`
  • Protects `﴿...﴾` spans from sentence splitting
  • Keeps Markdown tables & media references atomic
  │
  ▼
Heading Stack Tracker (`heading_stack[level]`) + Word-Budget Buffer (`max_words`)
  • Flushes cleanly at section boundaries (`>= min_section_words`) without bleeding overlap across chapters
  • Retains `overlap_words` sliding window within long sections
  • Enriches each Chunk via `extract_smart_tags()`
  │
  ▼
Returns `list[Chunk]`
```

---

## Configuration

| Parameter / Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `max_words` / `max_words_per_chunk` | `int` | `350` | Target word ceiling per chunk before triggering a flush. |
| `overlap_words` | `int` | `50` | Number of trailing body words carried into the next chunk within the same section. |
| `min_section_words` | `int` | `40` | Minimum non-overlap words required before a new heading forces an immediate chunk flush. |
| `top_k_tags` | `int` | `10` | Maximum number of salient keyword tags extracted per chunk. |
| `doc_prefix` (per-call) | `str \| None` | Stem of `source_file` or `"doc"` | Prefix used when generating deterministic `chunk_id` values (`<prefix>_chunk_0001`). |
| `--port` (UI CLI flag) | `int` | `8703` (auto-fallback) | Localhost port for `python chunking_engine/ui/app.py`. |

---

## API Reference

### `ChunkingEngine`

- **`ChunkingEngine(max_words: int = 350, overlap_words: int = 50, min_section_words: int = 40, top_k_tags: int = 10)`**
  Initializes the chunker with a `ChunkingConfig`.
- **`chunk(structured_doc: Any, max_words: int | None = None, overlap_words: int | None = None, min_section_words: int | None = None, doc_prefix: str | None = None) -> list[Chunk]`**
  Segments `structured_doc` into independent `Chunk` instances. Per-call arguments override constructor defaults without mutating engine state.
- **`ChunkingEngine.save_to_json(chunks: list[Chunk], output_path: str | Path) -> Path`** *(staticmethod)*
  Writes serialized chunks to `output_path` in UTF-8 JSON format.

### Data Contracts & Helpers

- **`Chunk.from_any(obj: Any, default_index: int = 1) -> Chunk`** — Normalizes a `Chunk`, `dict`, or `str` into a typed `Chunk`.
- **`Chunk.contextualized_content -> str`** *(property)* — Prepends `### <section_breadcrumb>` to `content` for context-rich embedding generation.
- **`extract_smart_tags(text: str, top_k: int = 10) -> list[str]`** — Extracts top bilingual keywords stripped of Arabic prefixes/diacritics and English/Arabic stopwords.

---

## Testing

Execute the standalone verification suite (tests multi-level chapter hierarchy, `section_breadcrumb` generation, atomic protection of `﴿...﴾` spans, table detection, and smart keyword tagging):

```powershell
python -m chunking_engine --self-test
```

---

## License and Contributing

- **License:** MIT License.
- **Contributing:** Keep `chunking_engine` 100% pure Python Standard Library with zero cross-engine imports. Ensure all comments and documentation are written in English and run `python -m chunking_engine --self-test` prior to submitting a Pull Request.
