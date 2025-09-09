Editor: CapCut-like Structure (Python + Next.js)

Overview
- Backend: FastAPI (Python) for scroll capture, assets, timeline, rendering.
- Frontend: Next.js (React) for a simplified CapCut-like UI (timeline, assets, properties, script editor, render).
- Rendering: moviepy + PIL for basic image/text/video composition; can integrate shorts_maker2 for rich templates later.

Folder Structure
- `backend/`: FastAPI app + pydantic models + rendering helpers.
- `projects/<id>/`: Per-project storage (assets, renders, project.json).
- `editor/`: Next.js UI (timeline, asset panel, script editor, preview, properties).

Run (Unified)
1) One-time backend setup:
   pip install -r backend/requirements.txt
   python -m playwright install chromium
2) Start both server and UI from repo root:
   npm install
   cp editor/.env.local.example editor/.env.local
   npm run dev
   # Server: http://localhost:8000, UI: http://localhost:3000

Key API Endpoints
- `POST /projects { name }` → create project
- `GET /projects` → list
- `GET /projects/{id}` / `PUT /projects/{id}` → load/save timeline
- `POST /projects/{id}/assets/upload` → upload file
- `POST /scroll/capture { url }` → fetch image URLs with Playwright
- `POST /projects/{id}/ingest_urls { urls }` → download images into project assets
- `POST /render { project_id }` → render MP4 via moviepy
- `POST /render/start { project_id }` → background render (use `/render/sse/{jobId}` for progress)
- `GET /render/status/{jobId}` / `GET /render/sse/{jobId}` → render progress (JSON/SSE)
- `GET /projects/{id}/srt/export` / `POST /projects/{id}/srt/import` → SRT IO

Editing Capabilities (current)
- Drag/resize timeline clips with zoom + snapping; delete via Del, fine adjust via arrows.
- Upload assets or fetch images via URL auto-scroll (Python Playwright).
- Edit script (title/price/features/CTA) for later use in templates or TTS.
- Clip properties panel: start/duration/x/y/scale/opacity and text props.
- Template overlay (top bar/CTA/bottom caption) applied during render; basic TTS from Script.
- Render basic 9:16 video with image layers and text overlays; audio layers if clips provided; background render with SSE.

Planned Enhancements
- Proper draggable/resizable timeline clips with snapping and keyboard shortcuts.
- Multi-track overlays (stickers/images), transitions, keyframes for position/opacity.
- Template application (map template JSON into overlay drawing like shorts_maker2).
- TTS integration per-script section; SRT import/export.
- Background rendering queue + progress SSE.

Notes
- Existing `ui_app.py` and `shorts_maker2.py` remain intact. We can progressively migrate advanced layout/templating and TTS from them into the backend renderer.
- For stability in scraping, keep Playwright headless and use the stealth plugin.
