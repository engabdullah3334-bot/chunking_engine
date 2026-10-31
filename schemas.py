# -*- coding: utf-8 -*-
"""
chunking_engine/schemas.py
==========================
Standard data contracts for `ChunkingEngine`: `Chunk`, `ChunkMetadata`, and `ChunkingConfig`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ChunkingConfig:
    """Configuration parameters for semantic & structural chunking."""

    max_words_per_chunk: int = 350
    overlap_words: int = 50
    min_section_words: int = 40
    top_k_tags: int = 10


@dataclass
class ChunkMetadata:
    """Rich metadata attached to every independent `Chunk`."""

    page_start: int = 1
    page_end: int = 1
    word_count: int = 0
    char_count: int = 0
    tags: list[str] = field(default_factory=list)
    block_types: list[str] = field(default_factory=list)
    media_paths: list[str] = field(default_factory=list)
    has_table: bool = False
    has_quranic_verse: bool = False
    language: str = "ara"
    source_file: str | None = None
    source_chunk_id: str | None = None
    translation_info: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    """
    Independent semantic chunk accompanied by `ChunkMetadata` and hierarchical
    chapter context (`chapter_context` & `section_breadcrumb`).
    """

    chunk_id: str
    chunk_index: int
    content: str
    chapter_context: list[str] = field(default_factory=list)
    section_breadcrumb: str = ""
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    @property
    def contextualized_content(self) -> str:
        """
        Return `content` prefixed with its hierarchical `section_breadcrumb`
        (ideal for RAG vector embeddings so every chunk carries chapter context).
        """
        if self.section_breadcrumb and not self.content.startswith(
            f"### {self.section_breadcrumb}"
        ):
            return f"### {self.section_breadcrumb}\n\n{self.content}"
        return self.content

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "chapter_context": list(self.chapter_context),
            "section_breadcrumb": self.section_breadcrumb,
            "contextualized_content": self.contextualized_content,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_any(cls, obj: Any, default_index: int = 1) -> "Chunk":
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, str):
            words = len(obj.split())
            return cls(
                chunk_id=f"chunk_{default_index:04d}",
                chunk_index=default_index,
                content=obj,
                metadata=ChunkMetadata(word_count=words, char_count=len(obj)),
            )
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            d = obj.to_dict()
        elif isinstance(obj, dict):
            d = obj
        else:
            d = vars(obj)

        raw_meta = d.get("metadata") or {}
        if hasattr(raw_meta, "to_dict"):
            raw_meta = raw_meta.to_dict()

        meta_fields = {
            k: v
            for k, v in raw_meta.items()
            if k in ChunkMetadata.__dataclass_fields__
        }
        chapter_ctx = list(d.get("chapter_context") or [])
        breadcrumb = str(
            d.get("section_breadcrumb")
            or (" > ".join(chapter_ctx) if chapter_ctx else "")
        )
        content = str(d.get("content") or d.get("chunk_content") or "")
        meta_fields.setdefault("word_count", len(content.split()))
        meta_fields.setdefault("char_count", len(content))

        idx = int(d.get("chunk_index") or default_index)
        cid = str(d.get("chunk_id") or f"chunk_{idx:04d}")
        return cls(
            chunk_id=cid,
            chunk_index=idx,
            content=content,
            chapter_context=chapter_ctx,
            section_breadcrumb=breadcrumb,
            metadata=ChunkMetadata(**meta_fields),
        )

