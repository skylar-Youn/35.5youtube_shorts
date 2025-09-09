from __future__ import annotations
import os
import threading
import time
import uuid
from typing import Dict, Any, Callable

JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def start_render(job_fn: Callable[[Callable[[float], None]], str]) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        JOBS[job_id] = {"status": "queued", "progress": 0.0, "path": None, "error": None, "started": time.time()}

    def _run():
        def _cb(p: float):
            with _LOCK:
                JOBS[job_id]["progress"] = float(max(0.0, min(1.0, p)))
        try:
            with _LOCK:
                JOBS[job_id]["status"] = "running"
            out = job_fn(_cb)
            with _LOCK:
                JOBS[job_id]["status"] = "done"
                JOBS[job_id]["path"] = out
                JOBS[job_id]["progress"] = 1.0
        except Exception as e:
            with _LOCK:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = str(e)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return job_id


def get_job(job_id: str) -> Dict[str, Any] | None:
    with _LOCK:
        return dict(JOBS.get(job_id) or {})

