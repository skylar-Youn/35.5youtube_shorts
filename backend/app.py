from __future__ import annotations
import os
import time
import uuid
from typing import Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi import HTTPException

from .models import CreateProjectReq, Project, Track, Clip, RenderReq, ScrollCaptureReq
from .storage import project_dir, save_project, load_project, list_projects
from .scroll_capture import deep_image_fetch, download_images, sanitize_filename
from .render import render_project


app = FastAPI(title="Editor Backend", default_response_class=JSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    return """
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Editor Backend</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 2rem; line-height: 1.5; }
        code { background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 4px; }
        a { color: #2563eb; text-decoration: none; }
        a:hover { text-decoration: underline; }
      </style>
    </head>
    <body>
      <h1>Editor Backend API</h1>
      <p>Backend is running. Useful endpoints:</p>
      <ul>
        <li><a href=\"/health\">/health</a> – quick status check</li>
        <li><a href=\"/projects\">/projects</a> – list projects</li>
        <li><a href=\"/docs\">/docs</a> – interactive API docs (OpenAPI)</li>
      </ul>
      <p>If you expected the UI, run the Next.js app in <code>editor</code> (port 3000) and open <code>http://localhost:3000</code>. Configure it to point here via <code>NEXT_PUBLIC_BACKEND_URL</code>.</p>
    </body>
    </html>
    """


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Deliberately return no content to avoid 404 noise if no favicon is provided.
    return Response(status_code=204)


@app.get("/health")
def health():
    return {"ok": True, "time": time.time()}


@app.get("/projects")
def api_list_projects():
    return {"projects": list_projects()}


@app.post("/projects")
def api_create_project(req: CreateProjectReq):
    pid = uuid.uuid4().hex[:12]
    now = time.time()
    prj = Project(
        id=pid,
        name=req.name,
        width=req.width or 1080,
        height=req.height or 1920,
        fps=req.fps or 30,
        duration=req.duration or 10.0,
        created_at=now,
        updated_at=now,
        tracks=[
            Track(id="v1", kind="image", clips=[]),
            Track(id="t1", kind="text", clips=[]),
            Track(id="a1", kind="audio", clips=[]),
        ],
    )
    save_project(prj)
    return prj.model_dump()


@app.get("/projects/{pid}")
def api_get_project(pid: str):
    prj = load_project(pid)
    if not prj:
        raise HTTPException(404, "Project not found")
    return prj.model_dump()


@app.put("/projects/{pid}")
def api_update_project(pid: str, body: Dict):
    prj = load_project(pid)
    if not prj:
        raise HTTPException(404, "Project not found")
    try:
        updated = Project.model_validate(body)
    except Exception:
        raise HTTPException(400, "Invalid project body")
    save_project(updated)
    return updated.model_dump()


@app.post("/projects/{pid}/assets/upload")
async def api_upload_asset(pid: str, file: UploadFile = File(...)):
    prj = load_project(pid)
    if not prj:
        raise HTTPException(404, "Project not found")
    d = os.path.join(project_dir(pid), "assets")
    os.makedirs(d, exist_ok=True)
    name = sanitize_filename(file.filename or f"asset_{int(time.time())}")
    path = os.path.join(d, name)
    with open(path, "wb") as f:
        f.write(await file.read())
    asset_id = uuid.uuid4().hex[:10]
    prj.assets[asset_id] = path
    save_project(prj)
    return {"assetId": asset_id, "path": path}


@app.post("/scroll/capture")
def api_scroll_capture(req: ScrollCaptureReq):
    title, urls = deep_image_fetch(req.url, mobile=req.mobile, use_stealth=req.use_stealth)
    return {"title": title, "urls": urls[: max(1, req.max_images)]}


@app.post("/projects/{pid}/ingest_urls")
def api_ingest_urls(pid: str, body: Dict):
    prj = load_project(pid)
    if not prj:
        raise HTTPException(404, "Project not found")
    urls = body.get("urls") or []
    if not isinstance(urls, list) or not urls:
        raise HTTPException(400, "urls must be a non-empty list")
    out_dir = os.path.join(project_dir(pid), "assets")
    paths = download_images(urls, out_dir)
    return {"paths": paths}


@app.post("/render")
def api_render(req: RenderReq):
    prj = load_project(req.project_id)
    if not prj:
        raise HTTPException(404, "Project not found")
    out_dir = os.path.join(project_dir(prj.id), "renders")
    name = req.out_name or f"render_{int(time.time())}.mp4"
    out_path = os.path.join(out_dir, name)

    prog = {"val": 0.0}

    def _cb(p):
        prog["val"] = float(p)

    path = render_project(prj, out_path, progress_cb=_cb)
    return {"ok": True, "path": path, "progress": prog["val"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
