# -*- coding: utf-8 -*-
"""
chunking_engine/engine.py
=========================
`ChunkingEngine` — Pure in-memory structural & semantic chunking engine.
Zero database imports, zero sibling engine imports, zero external dependencies!

Features preserved & upgraded:
  - Respects hierarchical section headings (`chapter_context` & `section_breadcrumb`).
  - Protects Quranic brackets `﴿...﴾` from mid-verse splitting.
  - Keeps Markdown tables cohesive.
  - Sliding-window paragraph overlap (`overlap_words`) within sections.
  - Bilingual Arabic/English TF keyword tagging.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import Chunk, ChunkingConfig, ChunkMetadata
from .tagger import extract_smart_tags

_QURAN_VERSE_RE = re.compile(r"﴿[^﴾]+﴾")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def _detect_lang(text: str) -> str:
    ara = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    lat = sum(1 for c in text if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    total = ara + lat
    if total == 0:
        return "ara"
    ratio = ara / total
    if ratio >= 0.70:
        return "ara"
    if ratio <= 0.15:
        return "eng"
    return "ara+eng"


def _extract_text_from_block(block: dict[str, Any]) -> str:
    if block.get("text"):
        return str(block["text"]).strip()
    spans = block.get("spans") or []
    if spans:
        return " ".join(str(s.get("text", "")) for s in spans if s.get("text")).strip()
    return ""


def _format_table_block(block: dict[str, Any]) -> str:
    if block.get("markdown"):
        return str(block["markdown"]).strip()
    rows = block.get("rows") or []
    if not rows:
        return ""
    col_count = int(block.get("col_count") or max((len(r) for r in rows), default=0))
    if col_count <= 0:
        return ""

    lines: list[str] = []
    for r_idx, row in enumerate(rows):
        cells_txt = [
            (c.get("text", "") if isinstance(c, dict) else str(c or ""))
            .replace("\n", " ")
            .replace("|", "\\|")
            .strip()
            for c in row
        ]
        while len(cells_txt) < col_count:
            cells_txt.append("")
        lines.append("| " + " | ".join(cells_txt[:col_count]) + " |")
        if r_idx == 0:
            lines.append("| " + " | ".join(["---"] * col_count) + " |")
    return "\n".join(lines)


def _split_oversized_text(text: str, max_words: int) -> list[str]:
    """
    Split an oversized paragraph along sentence boundaries while protecting
    Quranic brackets `﴿...﴾` from ever being split mid-verse.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]

    protected = _QURAN_VERSE_RE.sub(
        lambda m: m.group(0).replace(" ", "\u00A0"), text
    )
    sentences = re.split(r"(?<=[.۔؟!?\n])\s+", protected)
    segments: list[str] = []
    curr_words: list[str] = []

    for sent in sentences:
        restored = sent.replace("\u00A0", " ").strip()
        if not restored:
            continue
        # Tokenize while keeping non-breaking Quranic verses intact if possible
        verse_protected_tokens = _QURAN_VERSE_RE.sub(
            lambda m: m.group(0).replace(" ", "\u00A0"), restored
        ).split()

        expanded_words: list[str] = []
        for vtok in verse_protected_tokens:
            expanded_words.append(vtok.replace("\u00A0", " "))

        est_len = sum(len(x.split()) for x in expanded_words)
        curr_len = sum(len(x.split()) for x in curr_words)

        if curr_len + est_len > max_words and curr_words:
            segments.append(" ".join(curr_words))
            curr_words = []
            curr_len = 0

        if est_len > max_words:
            # Flush unit-by-unit while keeping each atomic `﴿...﴾` token together
            for unit in expanded_words:
                u_len = len(unit.split())
                if curr_len + u_len > max_words and curr_words:
                    segments.append(" ".join(curr_words))
                    curr_words = []
                    curr_len = 0
                curr_words.append(unit)
                curr_len += u_len
        else:
            curr_words.extend(expanded_words)

    if curr_words:
        segments.append(" ".join(curr_words))

    return segments


def _block_to_units(
    block: dict[str, Any], page_num: int, max_words: int
) -> list[dict[str, Any]]:
    b_type = block.get("type", "text")
    role = block.get("role", "body")

    if b_type in ("inline_cropped_image", "full_page_image_or_index"):
        img_path = block.get("image_path", "")
        alt_text = (block.get("alt_text") or "").strip()
        if not img_path:
            return []
        md_img = f"![{alt_text or f'Image p.{page_num}'}]({img_path})"
        return [
            {
                "kind": "image",
                "text": md_img,
                "word_count": max(1, len(alt_text.split())),
                "page": page_num,
                "media_paths": [str(img_path)],
            }
        ]

    if b_type == "table":
        tbl_md = _format_table_block(block)
        if not tbl_md:
            return []
        w_cnt = len(re.findall(r"\S+", tbl_md))
        return [
            {
                "kind": "table",
                "text": tbl_md,
                "word_count": max(1, w_cnt),
                "page": page_num,
                "media_paths": [],
            }
        ]

    text = _extract_text_from_block(block)
    if not text:
        return []

    is_heading = (
        role == "heading"
        or b_type in ("heading", "header")
        or bool(block.get("is_heading"))
    )
    if is_heading:
        lvl = max(1, min(int(block.get("heading_level") or 2), 6))
        return [
            {
                "kind": "heading",
                "text": text,
                "level": lvl,
                "word_count": len(text.split()),
                "page": page_num,
                "media_paths": [],
            }
        ]

    if role == "list_item":
        item_txt = text if text.startswith(("•", "-", "*")) else f"• {text}"
        return [
            {
                "kind": "list_item",
                "text": item_txt,
                "word_count": len(text.split()),
                "page": page_num,
                "media_paths": [],
            }
        ]

    segments = _split_oversized_text(text, max_words)
    return [
        {
            "kind": "body",
            "text": seg,
            "word_count": len(seg.split()),
            "page": page_num,
            "media_paths": [],
        }
        for seg in segments
        if seg.strip()
    ]


def _normalize_input_to_pages(
    structured_input: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Accept `ExtractedDocument` (duck-typed), `dict`, `list[dict]` (`pages`),
    JSON file path, or plain Markdown/text `str`, and return `(pages, doc_meta)`.
    """
    if isinstance(structured_input, Path) or (
        isinstance(structured_input, str)
        and len(structured_input) < 260
        and "\n" not in structured_input
        and Path(structured_input).exists()
    ):
        p = Path(structured_input)
        raw = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix.lower() == ".json":
            return _normalize_input_to_pages(json.loads(raw))
        return _normalize_input_to_pages(raw)

    if isinstance(structured_input, str):
        blocks: list[dict[str, Any]] = []
        for para in re.split(r"\n\s*\n", structured_input.strip()):
            para = para.strip()
            if not para:
                continue
            m_h = _MD_HEADING_RE.match(para)
            if m_h and "\n" not in para:
                blocks.append(
                    {
                        "type": "text",
                        "role": "heading",
                        "heading_level": len(m_h.group(1)),
                        "text": m_h.group(2).strip(),
                    }
                )
            else:
                blocks.append({"type": "text", "role": "body", "text": para})
        return [{"metadata": {"page_number": 1}, "blocks": blocks}], {}

    if isinstance(structured_input, list):
        return structured_input, {}

    if hasattr(structured_input, "to_dict") and callable(structured_input.to_dict):
        data = structured_input.to_dict()
    elif isinstance(structured_input, dict):
        data = structured_input
    else:
        raise TypeError(f"Unsupported input type for ChunkingEngine: {type(structured_input)!r}")

    doc_meta = data.get("metadata") or {}
    if data.get("pages"):
        return list(data["pages"]), doc_meta

    # Fallback: reconstruct a logical page if a custom dict only supplied headings/texts/tables
    blocks = []
    for h in data.get("headings") or []:
        blocks.append(
            {
                "type": "text",
                "role": "heading",
                "heading_level": h.get("level", 2),
                "text": h.get("text", ""),
                "page_number": h.get("page_number", 1),
            }
        )
    for t in data.get("texts") or []:
        blocks.append(
            {
                "type": "text",
                "role": "list_item" if t.get("role") == "list_item" else "body",
                "text": t.get("text", ""),
                "page_number": t.get("page_number", 1),
            }
        )
    for tb in data.get("tables") or []:
        blocks.append(
            {
                "type": "table",
                "rows": tb.get("rows", []),
                "col_count": tb.get("col_count", 0),
                "markdown": tb.get("markdown"),
                "page_number": tb.get("page_number", 1),
            }
        )
    return [{"metadata": {"page_number": 1}, "blocks": blocks}], doc_meta


class ChunkingEngine:
    """
    Standalone Structural & Semantic Chunking Engine.

    Usage:
        from chunking_engine import ChunkingEngine

        chunker = ChunkingEngine(max_words=350, overlap_words=50)
        chunks = chunker.chunk(extracted_doc)
    """

    def __init__(
        self,
        max_words: int = 350,
        overlap_words: int = 50,
        min_section_words: int = 40,
        top_k_tags: int = 10,
    ) -> None:
        self.config = ChunkingConfig(
            max_words_per_chunk=max_words,
            overlap_words=overlap_words,
            min_section_words=min_section_words,
            top_k_tags=top_k_tags,
        )

    def chunk(
        self,
        structured_doc: Any,
        max_words: int | None = None,
        overlap_words: int | None = None,
        min_section_words: int | None = None,
        doc_prefix: str | None = None,
    ) -> list[Chunk]:
        """
        Split a structured document (`ExtractedDocument`, `dict`, `pages`, or `str`)
        into an array of independent `Chunk` objects with metadata and chapter context.
        """
        pages_data, doc_meta = _normalize_input_to_pages(structured_doc)
        max_w = max_words if max_words is not None else self.config.max_words_per_chunk
        ov_w = overlap_words if overlap_words is not None else self.config.overlap_words
        min_sec_w = (
            min_section_words
            if min_section_words is not None
            else self.config.min_section_words
        )

        source_file = doc_meta.get("file_name")
        doc_lang = doc_meta.get("language") or ""
        prefix = doc_prefix or (Path(source_file).stem if source_file else "doc")

        heading_stack: dict[int, str] = {}
        buffer_units: list[dict[str, Any]] = []
        buffer_words = 0
        chunks: list[Chunk] = []

        def _active_context() -> list[str]:
            return [heading_stack[k] for k in sorted(heading_stack) if heading_stack[k]]

        def _flush_buffer(keep_overlap: bool = False) -> None:
            nonlocal buffer_units, buffer_words
            if not buffer_units:
                return

            text_parts: list[str] = []
            media_paths: list[str] = []
            pages_seen: list[int] = []
            kinds_seen: list[str] = []

            for u in buffer_units:
                if u["text"]:
                    text_parts.append(u["text"])
                pages_seen.append(int(u["page"]))
                media_paths.extend(u.get("media_paths", []))
                if u["kind"] not in kinds_seen:
                    kinds_seen.append(u["kind"])

            body_text = "\n\n".join(text_parts).strip()
            if not body_text:
                buffer_units = []
                buffer_words = 0
                return

            idx = len(chunks) + 1
            p_start = min(pages_seen) if pages_seen else 1
            p_end = max(pages_seen) if pages_seen else 1
            ctx_list = _active_context()
            breadcrumb = " > ".join(ctx_list)
            word_cnt = len(re.findall(r"\S+", body_text))
            tags = extract_smart_tags(body_text, top_k=self.config.top_k_tags)
            dedup_media = list(dict.fromkeys(media_paths))

            chunks.append(
                Chunk(
                    chunk_id=f"{prefix}_chunk_{idx:04d}",
                    chunk_index=idx,
                    content=body_text,
                    chapter_context=ctx_list,
                    section_breadcrumb=breadcrumb,
                    metadata=ChunkMetadata(
                        page_start=p_start,
                        page_end=p_end,
                        word_count=word_cnt,
                        char_count=len(body_text),
                        tags=tags,
                        block_types=kinds_seen,
                        media_paths=dedup_media,
                        has_table=("table" in kinds_seen),
                        has_quranic_verse=bool(_QURAN_VERSE_RE.search(body_text)),
                        language=doc_lang or _detect_lang(body_text),
                        source_file=source_file,
                    ),
                )
            )

            if keep_overlap and ov_w > 0:
                overlap_buf: list[dict[str, Any]] = []
                ov_cnt = 0
                for u in reversed(buffer_units):
                    if u["kind"] in ("image", "table", "heading"):
                        continue
                    if ov_cnt + u["word_count"] <= ov_w or not overlap_buf:
                        if u["word_count"] > ov_w:
                            tail_words = u["text"].split()[-ov_w:]
                            tail_txt = " ".join(tail_words)
                            overlap_buf.insert(
                                0,
                                {
                                    "kind": "body",
                                    "text": tail_txt,
                                    "word_count": len(tail_words),
                                    "page": u["page"],
                                    "media_paths": [],
                                    "is_overlap": True,
                                },
                            )
                            ov_cnt += len(tail_words)
                            break
                        else:
                            u_copy = dict(u)
                            u_copy["is_overlap"] = True
                            u_copy["media_paths"] = []
                            overlap_buf.insert(0, u_copy)
                            ov_cnt += u["word_count"]
                    else:
                        break
                buffer_units = overlap_buf
                buffer_words = ov_cnt
            else:
                buffer_units = []
                buffer_words = 0

        for page in pages_data:
            p_num = int(page.get("metadata", {}).get("page_number") or 1)
            for b in page.get("blocks", []):
                blk_page = int(b.get("page_number") or p_num)
                units = _block_to_units(b, blk_page, max_w)
                for u in units:
                    if u["kind"] == "heading":
                        non_overlap_words = sum(
                            item["word_count"]
                            for item in buffer_units
                            if not item.get("is_overlap")
                        )
                        if non_overlap_words >= min_sec_w:
                            _flush_buffer(keep_overlap=False)
                        else:
                            buffer_units = [
                                item for item in buffer_units if not item.get("is_overlap")
                            ]
                            buffer_words = sum(item["word_count"] for item in buffer_units)

                        lvl = int(u.get("level") or 2)
                        heading_stack[lvl] = u["text"]
                        for deeper_k in [k for k in heading_stack if k > lvl]:
                            del heading_stack[deeper_k]
                        continue

                    non_overlap_words = sum(
                        item["word_count"]
                        for item in buffer_units
                        if not item.get("is_overlap")
                    )
                    if (
                        buffer_words + u["word_count"] > max_w
                        and non_overlap_words >= min_sec_w
                    ):
                        _flush_buffer(keep_overlap=True)

                    buffer_units.append(u)
                    buffer_words += u["word_count"]

                    if buffer_words >= max_w:
                        _flush_buffer(keep_overlap=True)

        if any(not item.get("is_overlap") for item in buffer_units):
            _flush_buffer(keep_overlap=False)

        return chunks

    @staticmethod
    def save_to_json(chunks: list[Chunk], output_path: str | Path) -> Path:
        """Optional convenience exporter to write `list[Chunk]` as a JSON file."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out

