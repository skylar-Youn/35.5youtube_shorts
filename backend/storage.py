from __future__ import annotations
import os
import json
import time
from typing import Optional
from .models import Project


ROOT = os.path.abspath(os.path.join(os.getcwd(), "projects"))
os.makedirs(ROOT, exist_ok=True)


def project_dir(pid: str) -> str:
    d = os.path.join(ROOT, pid)
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "assets"), exist_ok=True)
    os.makedirs(os.path.join(d, "renders"), exist_ok=True)
    return d


def project_path(pid: str) -> str:
    return os.path.join(project_dir(pid), "project.json")


def save_project(prj: Project) -> None:
    prj.updated_at = time.time()
    p = project_path(prj.id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(prj.model_dump(), f, ensure_ascii=False, indent=2)


def load_project(pid: str) -> Optional[Project]:
    p = project_path(pid)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Project.model_validate(data)


def list_projects() -> list[dict]:
    out = []
    for name in os.listdir(ROOT):
        d = os.path.join(ROOT, name)
        if not os.path.isdir(d):
            continue
        pj = load_project(name)
        if pj:
            out.append({"id": pj.id, "name": pj.name, "updated_at": pj.updated_at})
    out.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return out

