# -*- coding: utf-8 -*-
"""
chunking_engine/__main__.py
===========================
Standalone CLI, UI launcher, and self-test runner for `chunking_engine`.

Commands:
    python -m chunking_engine --ui
    python -m chunking_engine --self-test
    python -m chunking_engine extracted_doc.json --out chunks.json
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chunking_engine import ChunkingEngine
else:
    from .engine import ChunkingEngine


def _configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def launch_ui() -> None:
    app_path = Path(__file__).resolve().parent / "ui" / "app.py"
    subprocess.run([sys.executable, str(app_path)], check=False)


def run_self_test() -> None:
    _configure_utf8()
    print("=" * 64)
    print("  ChunkingEngine — Standalone Self-Test Suite")
    print("=" * 64)

    chunker = ChunkingEngine(max_words=45, overlap_words=10, min_section_words=10)

    # Bilingual / Arabic test fixture verifying chapter hierarchy & Quranic bracket protection
    verse = "﴿إِنَّ اللَّهَ يَأْمُرُ بِالْعَدْلِ وَالْإِحْسَانِ وَإِيتَاءِ ذِي الْقُرْبَىٰ﴾"
    structured_sample = {
        "metadata": {"file_name": "book.pdf", "language": "ara"},
        "pages": [
            {
                "metadata": {"page_number": 1},
                "blocks": [
                    {"type": "text", "role": "heading", "heading_level": 1, "text": "الباب الأول: الأخلاق"},
                    {"type": "text", "role": "heading", "heading_level": 2, "text": "الفصل الأول: العدل"},
                    {
                        "type": "text",
                        "role": "body",
                        "text": (
                            f"يُعد العدل ركيزة أساسية في بناء المجتمعات الإنسانية المتوازنة. {verse}. "
                            "ولذلك اهتم العلماء والمفكرون بتأصيل قواعد الإنصاف والمساواة بين الناس في كافة المعاملات."
                        ),
                    },
                ],
            },
            {
                "metadata": {"page_number": 2},
                "blocks": [
                    {"type": "text", "role": "heading", "heading_level": 2, "text": "الفصل الثاني: الإتقان"},
                    {
                        "type": "table",
                        "col_count": 2,
                        "rows": [["القيمة", "الأثر"], ["الإتقان", "جودة المخرجات"]],
                    },
                ],
            },
        ],
    }

    chunks = chunker.chunk(structured_sample)
    assert len(chunks) >= 2, f"Expected >=2 chunks, got {len(chunks)}"

    assert chunks[0].chapter_context == ["الباب الأول: الأخلاق", "الفصل الأول: العدل"]
    assert chunks[0].section_breadcrumb == "الباب الأول: الأخلاق > الفصل الأول: العدل"
    assert any(verse in c.content for c in chunks), "Quranic verse was split across chunks!"
    assert any(c.metadata.has_quranic_verse for c in chunks)
    assert any(c.metadata.has_table for c in chunks)
    assert chunks[-1].chapter_context == ["الباب الأول: الأخلاق", "الفصل الثاني: الإتقان"]

    print(f"  [PASS] Generated chunks        -> {len(chunks)} chunks")
    print("  [PASS] Chapter context & Quran -> Hierarchy & atomic verse preserved")
    print(f"  [PASS] Table & Smart Tags      -> tags={chunks[0].metadata.tags[:4]}")

    print("=" * 64)
    print("  ALL CHUNKING ENGINE SELF-TESTS PASSED SUCCESSFULLY!")
    print("=" * 64)


def main() -> None:
    _configure_utf8()
    parser = argparse.ArgumentParser(description="ChunkingEngine Standalone CLI & UI")
    parser.add_argument("input", nargs="?", help="Path to structured JSON or Markdown/text file")
    parser.add_argument("--max-words", type=int, default=350)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--out", type=str, default=None, help="Output JSON path for chunks")
    parser.add_argument("--ui", action="store_true", help="Launch calm standalone Web UI")
    parser.add_argument("--self-test", action="store_true", help="Run standalone self-test suite")
    args = parser.parse_args()

    if args.ui:
        launch_ui()
        return

    if args.self_test:
        run_self_test()
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    engine = ChunkingEngine(max_words=args.max_words, overlap_words=args.overlap)
    chunks = engine.chunk(Path(args.input))
    print(f"Generated {len(chunks)} semantic chunks.")
    for c in chunks[:5]:
        print(
            f"  [{c.chunk_index:03d}] p.{c.metadata.page_start}-{c.metadata.page_end} | "
            f"{c.metadata.word_count}w | ctx='{c.section_breadcrumb}'"
        )
    if args.out:
        out_p = engine.save_to_json(chunks, args.out)
        print(f"Saved chunks JSON -> {out_p}")


if __name__ == "__main__":
    main()
