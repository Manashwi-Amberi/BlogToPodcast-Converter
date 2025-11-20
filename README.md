**Project Overview**
- **Purpose**: Convert blog posts into a narrated podcast episode (script generation via Groq, text-to-speech via Murf, simple intro/outro mixing).
- **Location**: main code lives under `blog_to_podcast/`.

**Quick Start (Windows / PowerShell)**
- Create and activate a virtual environment, then install dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r blog_to_podcast/requirements.txt
```

- Provide API keys (either in a `.env` file at repo root or as environment variables):
  - `MURF_API_KEY` — Murf Text-to-Speech API key
  - `GROQ_API_KEY` — Groq chat/completions API key

- Run the simple example (executes the end-to-end pipeline and writes an MP3):
```powershell
# make sure .env or environment variables are set
python -m blog_to_podcast.run_example
```

- Run the web server (FastAPI app) for the HTTP endpoint:
```powershell
python -m uvicorn blog_to_podcast.web.app:app --reload
```

**API / Manual Test**
- After the server is running, POST to `/api/convert` with JSON including one of: `raw_text`, `text_file`, or `url`.
- Example PowerShell curl (replace body text):
```powershell
$body = @{ raw_text = 'Short article text to convert to podcast' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/convert -Method Post -ContentType 'application/json' -Body $body
```

**Where outputs go**
- Final mixed MP3: `blog_to_podcast/output/final_podcast.mp3`
- Script text is printed to stdout in the CLI example and returned in the web API response JSON.

**Important Files**
- `blog_to_podcast/agents/audio_generator.py` — TTS + audio mixing (Murf integration, intro/outro handling).
- `blog_to_podcast/agents/script_generator.py` — Script generation logic (calls `GroqClient`).
- `blog_to_podcast/agents/blog_cleaner.py` — Fetches / cleans blog content before sending to generator.
- `blog_to_podcast/core/groq_client.py` — Groq client wrapper.
- `blog_to_podcast/run_example.py` — Small local runner exercising the pipeline.
- `blog_to_podcast/web/app.py` — FastAPI app (HTTP endpoint).

**Configuration & Defaults**
The project has sensible defaults inside the code. Notable defaults changed during recent fixes:
- Groq max output tokens default: `3000` (was `1500`) — allows longer script outputs.
- Blog cleaner `max_chars` default: `30000` (was `15000`) — allows larger blog inputs.
- Intro/outro fade durations are applied only when positive (prevents pydub fade errors).

If you want to tune these without editing code, you can change them directly in the dataclass definitions:
- `blog_to_podcast/core/groq_client.py` — `max_output_tokens`
- `blog_to_podcast/agents/blog_cleaner.py` — `max_chars`
- `blog_to_podcast/agents/audio_generator.py` — `intro_path`, `outro_path`, `speech_delta_db`, etc.

(If you prefer, I can add environment-variable overrides for these next.)

**Prerequisites / Troubleshooting**
- API keys missing: The services will raise runtime errors if `MURF_API_KEY` or `GROQ_API_KEY` are not set. Add them to a `.env` file at repo root or set them in the shell before running.

- FFmpeg/ffprobe: PyDub relies on ffmpeg. The project attempts to use `imageio-ffmpeg`'s ffmpeg binary, but on some Windows setups `ffprobe` may be required in PATH. If you see errors mentioning ffmpeg/ffprobe:
  - Install native FFmpeg or add a binary to PATH.
  - Common options on Windows:
```powershell
# If you have winget
winget install Gyan.FFmpeg
# Or install from https://ffmpeg.org and add ffmpeg/bin to PATH
```

- Missing intro/outro assets: Default expected assets are `blog_to_podcast/assets/intro.mp3` and `blog_to_podcast/assets/outro.mp3`. If they are missing an error will be raised. Provide your own short MP3s at those paths or update paths in `AudioGeneratorAgent`.

- Murf audio payloads: Different Murf SDK versions may return base64-encoded audio or a signed URL. The audio generator has been made defensive and should handle either, but network errors or permission issues from Murf may still occur. Check logs for details.

- If you hit an error like `TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'` when mixing fades — that was fixed by applying fades only when positive durations were passed. If you still see fade issues, verify the intro/outro files are valid audio files.

- If Groq returns HTML or truncated content, check `GROQ_API_KEY` and consider increasing `max_output_tokens` in `blog_to_podcast/core/groq_client.py` or split large inputs.

**Logging**
- For debugging, run the example or server with more verbose logging. The code uses Python's standard `logging` module. To see debug logs in `run_example.py` you can change `basicConfig(level=logging.INFO)` to `level=logging.DEBUG`, or add similar logging setup in `web/app.py` when launching the server.

**Development / Tests**
- Unit tests are not included. For robustness, consider adding tests that mock Murf responses (base64, signed URL, failure) and assertions for audio output.

**Common Commands**
```powershell
# Activate virtualenv
.\.venv\Scripts\Activate.ps1
# Run example
python -m blog_to_podcast.run_example
# Run server
python -m uvicorn blog_to_podcast.web.app:app --reload
```

**If something fails**
- Paste the full traceback into an issue or here. Include the last printed log lines, the values of environment variables (omit secrets), and whether `intro.mp3`/`outro.mp3` exist.

---

If you'd like, I can also:
- Add environment variable configuration for `max_tokens` and `max_chars` so you can tune them without editing code.
- Add more verbose logs for Murf downloads and Groq responses, or add unit tests for the `_synthesize` function.

