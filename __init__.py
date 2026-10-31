# -*- coding: utf-8 -*-
"""
chunking_engine
===============
Standalone structural & semantic document chunking engine.

Usage:
    from chunking_engine import ChunkingEngine

    chunker = ChunkingEngine(max_words=350, overlap_words=50)
    chunks = chunker.chunk(extracted_doc)
"""

from .engine import ChunkingEngine
from .schemas import Chunk, ChunkingConfig, ChunkMetadata
from .tagger import extract_smart_tags

__all__ = [
    "ChunkingEngine",
    "Chunk",
    "ChunkMetadata",
    "ChunkingConfig",
    "extract_smart_tags",
]

