# -*- coding: utf-8 -*-
"""
chunking_engine/ui/app.py
=========================
Minimalist, calm, zero-dependency standalone Web UI for `ChunkingEngine`.
Sole purpose: clearly present `ChunkingEngine`'s mission and execute semantic
chunking without intruding on core engine logic.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from chunking_engine import ChunkingEngine

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chunking Engine</title>
<style>
  :root { --bg:#f8fafc; --card:#ffffff; --border:#e2e8f0; --text:#0f172a; --muted:#64748b; --accent:#334155; --accent-hover:#1e293b; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--text); line-height:1.55; }
  .wrap { max-width:860px; margin:2.5rem auto; padding:0 1.25rem; }
  h1 { font-size:1.35rem; font-weight:600; margin:0 0 1rem; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1.25rem 1.4rem; margin-bottom:1.1rem; }
  .label { font-size:0.73rem; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:var(--muted); margin-bottom:0.35rem; }
  .mission { margin:0 0 0.75rem; color:#334155; font-size:0.94rem; }
  .contracts { font-size:0.83rem; color:var(--muted); padding-top:0.65rem; border-top:1px solid var(--border); }
  code, pre { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; background:#f1f5f9; padding:0.12rem 0.38rem; border-radius:4px; font-size:0.82rem; }
  .row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.85rem; margin-bottom:0.9rem; }
  label.field { display:block; font-size:0.83rem; color:var(--muted); margin-bottom:0.3rem; }
  input[type="number"], textarea { width:100%; padding:0.55rem 0.7rem; border:1px solid var(--border); border-radius:7px; font-size:0.87rem; font-family:inherit; }
  .actions { display:flex; gap:0.6rem; margin-top:0.85rem; }
  button { padding:0.56rem 1.05rem; border-radius:7px; border:1px solid transparent; font-size:0.87rem; font-weight:500; cursor:pointer; background:var(--accent); color:#fff; }
  button:hover { background:var(--accent-hover); }
  button.secondary { background:#fff; color:var(--text); border-color:var(--border); }
  .chunk-item { border:1px solid var(--border); border-radius:8px; padding:0.9rem 1.05rem; margin-bottom:0.75rem; background:#fff; }
  .chunk-head { display:flex; justify-content:space-between; font-size:0.82rem; color:var(--muted); margin-bottom:0.45rem; border-bottom:1px solid var(--border); padding-bottom:0.35rem; }
  .hidden { display:none; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Chunking Engine</h1>
  <div class="card">
    <div class="label">Engine Mission</div>
    <p class="mission">Splits structured documents or Markdown/text into independent semantic <code>Chunk</code> items enriched with hierarchical chapter context (<code>section_breadcrumb</code>), keyword tags, and intact tables.</p>
    <div class="contracts"><b>Input:</b> Structured JSON or Markdown/text &nbsp;&middot;&nbsp; <b>Output:</b> <code>list[Chunk]</code> + <code>ChunkMetadata</code></div>
  </div>

  <div class="card">
    <div class="row">
      <div><label class="field">Max Words / Chunk</label><input type="number" id="maxW" value="80" min="15"></div>
      <div><label class="field">Overlap Words</label><input type="number" id="ovW" value="15" min="0"></div>
      <div><label class="field">Min Section Words</label><input type="number" id="minSec" value="10" min="1"></div>
    </div>
    <label class="field">Structured JSON or Markdown Input</label>
    <textarea id="docInput" rows="8"># Chapter 1: Modular Systems

Independent engines allow teams to test, refine, and deploy capabilities without coupling database or UI concerns into domain algorithms.

## Section 1.1: Context Preservation

Every semantic chunk carries its hierarchical section breadcrumb so downstream search, translation, and reasoning retain structural clarity.

| Field | Role |
| --- | --- |
| `section_breadcrumb` | Preserves parent chapter path |
| `overlap_words` | Maintains smooth continuity |</textarea>
    <div class="actions">
      <button onclick="runChunk()">Generate Chunks</button>
      <button class="secondary hidden" id="dlBtn" onclick="dlChunks()">Download Chunks JSON</button>
    </div>
  </div>

  <div id="outBox" class="hidden"></div>
</div>

<script>
let lastChunks = null;
function esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
async function runChunk() {
  const raw = document.getElementById('docInput').value;
  let parsed = raw;
  if (raw.trim().startsWith('{') || raw.trim().startsWith('[')) {
    try { parsed = JSON.parse(raw); } catch (_) {}
  }
  const resp = await fetch('/api/chunk', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      input: parsed,
      max_words: parseInt(document.getElementById('maxW').value || '80', 10),
      overlap_words: parseInt(document.getElementById('ovW').value || '15', 10),
      min_section_words: parseInt(document.getElementById('minSec').value || '10', 10)
    })
  });
  const data = await resp.json();
  if (!data.ok) { alert(data.error); return; }
  lastChunks = data.chunks;
  document.getElementById('dlBtn').classList.remove('hidden');
  const box = document.getElementById('outBox');
  box.classList.remove('hidden');
  box.innerHTML = `<div class="label" style="margin-bottom:0.6rem;">Generated ${lastChunks.length} Chunk(s)</div>` +
    lastChunks.map(c => `
      <div class="chunk-item">
        <div class="chunk-head">
          <span><b>#${c.chunk_index}</b> &middot; <code>${esc(c.section_breadcrumb || 'Root')}</code></span>
          <span>${c.metadata.word_count} words &middot; tags: ${esc((c.metadata.tags || []).slice(0,5).join(', ') || '—')}</span>
        </div>
        <div style="white-space:pre-wrap; font-size:0.9rem;">${esc(c.content)}</div>
      </div>`).join('');
}
function dlChunks() {
  if (!lastChunks) return;
  const blob = new Blob([JSON.stringify(lastChunks, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'chunks.json';
  a.click();
}
</script>
</body>
</html>
"""


def execute_chunking(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        engine = ChunkingEngine(
            max_words=int(payload.get("max_words") or 80),
            overlap_words=int(payload.get("overlap_words") or 15),
            min_section_words=int(payload.get("min_section_words") or 10),
        )
        chunks = engine.chunk(payload.get("input") or "")
        return {"ok": True, "chunks": [c.to_dict() for c in chunks]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class ChunkingUIHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/chunk":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = json.loads(self.rfile.read(length).decode("utf-8"))
        out = json.dumps(execute_chunking(raw), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def _pick_port(preferred: int = 8703) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve_ui(host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> None:
    actual_port = port or _pick_port(8703)
    server = ThreadingHTTPServer((host, actual_port), ChunkingUIHandler)
    url = f"http://{host}:{actual_port}"
    print(f"Chunking Engine UI running at {url} (Press Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Chunking Engine UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Chunking Engine Standalone UI")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    serve_ui(port=args.port, open_browser=not args.no_browser)
