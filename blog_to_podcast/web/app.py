from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from blog_to_podcast.core.pipeline import BlogToPodcastPipeline

app = FastAPI(
    title="Blog → Podcast Studio",
    description="Paste any blog URL or raw text and generate a narrated podcast episode.",
)

pipeline = BlogToPodcastPipeline()
OUTPUT_PATH = Path("blog_to_podcast/output/final_podcast.mp3")


class ConvertRequest(BaseModel):
    url: Optional[str] = Field(None, description="Blog URL to process")
    text: Optional[str] = Field(None, description="Raw blog text to convert")


def _build_index_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Blog → Podcast Studio</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f172a;
      --card: rgba(15, 23, 42, 0.85);
      --accent: #6366f1;
      --accent-bright: #a855f7;
      --text: #e2e8f0;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body {
      margin: 0;
      background: radial-gradient(circle at top, #1e1b4b, #020617);
      min-height: 100vh;
      padding: 2rem;
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .app {
      width: min(900px, 100%);
      background: var(--card);
      border: 1px solid rgba(99, 102, 241, 0.25);
      box-shadow: 0 20px 60px rgba(15, 23, 42, 0.8);
      border-radius: 24px;
      padding: 2.5rem 3rem;
      backdrop-filter: blur(18px);
    }
    h1 {
      font-size: clamp(2rem, 4vw, 2.8rem);
      margin: 0 0 0.6rem;
    }
    p.subtitle {
      margin: 0;
      color: var(--muted);
      font-size: 1.05rem;
    }
    form {
      margin-top: 2rem;
      display: grid;
      gap: 1.5rem;
    }
    label {
      font-weight: 500;
      display: block;
      margin-bottom: 0.4rem;
      color: #cbd5f5;
    }
    input[type="url"], textarea {
      width: 100%;
      border: 1px solid rgba(148, 163, 184, 0.35);
      border-radius: 16px;
      padding: 0.9rem 1.1rem;
      font-size: 1rem;
      background: rgba(15, 23, 42, 0.6);
      color: var(--text);
      transition: border 0.2s ease, box-shadow 0.2s ease;
      resize: vertical;
    }
    input:focus, textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.35);
    }
    .cta {
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
      align-items: center;
    }
    button {
      border: none;
      border-radius: 999px;
      padding: 0.95rem 1.8rem;
      font-size: 1rem;
      background: linear-gradient(135deg, var(--accent), var(--accent-bright));
      color: #fff;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      min-width: 220px;
    }
    button:disabled {
      opacity: 0.6;
      cursor: progress;
    }
    button:hover:not(:disabled) {
      transform: translateY(-1px) scale(1.01);
      box-shadow: 0 10px 25px rgba(99, 102, 241, 0.35);
    }
    .status {
      font-size: 0.95rem;
      color: var(--muted);
    }
    .result-card {
      margin-top: 2.2rem;
      border-radius: 18px;
      padding: 1.8rem;
      background: rgba(15, 23, 42, 0.65);
      border: 1px solid rgba(226, 232, 240, 0.08);
      display: none;
    }
    .result-card.active { display: block; }
    .result-card h2 {
      margin-top: 0;
      font-size: 1.2rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
    }
    pre {
      white-space: pre-wrap;
      font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
      line-height: 1.6;
      max-height: 360px;
      overflow-y: auto;
      margin: 1rem 0;
      background: rgba(2, 6, 23, 0.65);
      border-radius: 16px;
      padding: 1rem;
      border: 1px solid rgba(148, 163, 184, 0.18);
    }
    .download-link {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
      margin-top: 0.5rem;
    }
    .download-link svg {
      width: 1rem;
      height: 1rem;
      fill: currentColor;
    }
    @media (max-width: 640px) {
      body { padding: 1rem; }
      .app { padding: 1.5rem; border-radius: 18px; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <h1>Blog → Podcast Studio</h1>
      <p class="subtitle">Feed me any link or text and I’ll hand you a polished, narrated MP3 with a ready-to-read script.</p>
    </header>

    <form id="podcast-form">
      <div>
        <label for="url">Blog URL (optional)</label>
        <input type="url" id="url" name="url" placeholder="https://example.com/your-post" />
      </div>
      <div>
        <label for="text">Or paste blog content</label>
        <textarea id="text" name="text" rows="8" placeholder="Drop raw article text here if you don't have a public link."></textarea>
      </div>
      <div class="cta">
        <button type="submit" id="run-btn">Generate Podcast</button>
        <span class="status" id="status">Standing by.</span>
      </div>
    </form>

    <section class="result-card" id="results">
      <h2>Script Preview</h2>
      <pre id="script-output"></pre>
      <a class="download-link" id="download-link" href="#" download="final_podcast.mp3" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24"><path d="M5 20h14v-2H5v2zm7-18L5.33 9h3.84v4h4.66V9h3.84L12 2z"/></svg>
        Download final_podcast.mp3
      </a>
    </section>
  </div>

  <script>
    const form = document.getElementById("podcast-form");
    const statusEl = document.getElementById("status");
    const runBtn = document.getElementById("run-btn");
    const results = document.getElementById("results");
    const scriptOutput = document.getElementById("script-output");
    const downloadLink = document.getElementById("download-link");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const url = document.getElementById("url").value.trim();
      const text = document.getElementById("text").value.trim();

      if (!url && !text) {
        statusEl.textContent = "Please provide either a URL or raw text.";
        return;
      }

      runBtn.disabled = true;
      statusEl.textContent = "Brewing your podcast...";
      results.classList.remove("active");

      try {
        const response = await fetch("/api/convert", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, text }),
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Conversion failed.");
        }
        const data = await response.json();
        scriptOutput.textContent = data.script || "(Empty script)";
        downloadLink.href = data.audio_url;
        results.classList.add("active");
        statusEl.textContent = "Done! Grab your script + MP3 below.";
      } catch (error) {
        console.error(error);
        statusEl.textContent = error.message || "Something went wrong.";
      } finally {
        runBtn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _build_index_html()


@app.post("/api/convert", response_class=JSONResponse)
async def convert(request: ConvertRequest) -> JSONResponse:
    source = request.url or request.text
    if not source:
        raise HTTPException(status_code=400, detail="Provide a URL or raw text.")

    try:
        result = await run_in_threadpool(pipeline.run, blog_source=source)
    except Exception as exc:  # pragma: no cover - surfaced via HTTP
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    timestamp = int(time.time())
    return JSONResponse(
        {
            "script": result.get("podcast_script", ""),
            "audio_url": f"/download/final?ts={timestamp}",
        }
    )


@app.get("/download/final")
async def download_final() -> FileResponse:
    if not OUTPUT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="No podcast has been generated yet. Run a conversion first.",
        )
    return FileResponse(
        OUTPUT_PATH,
        filename="final_podcast.mp3",
        media_type="audio/mpeg",
    )



