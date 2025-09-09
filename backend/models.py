from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class Transform(BaseModel):
    x: float = 0.0  # 0..1 relative
    y: float = 0.0  # 0..1 relative
    scale: float = 1.0
    opacity: float = 1.0
    rotation: float = 0.0


ClipType = Literal["video", "image", "audio", "text"]


class Clip(BaseModel):
    id: str
    type: ClipType
    src: Optional[str] = None  # path or URL (backend will normalize to local path)
    start: float = 0.0
    duration: float = 1.0
    transform: Transform = Field(default_factory=Transform)
    # Text settings
    text: Optional[str] = None
    text_size: int = 48
    text_color: str = "#ffffff"
    text_align: Literal["left", "center", "right"] = "center"
    # Image crop (optional, relative 0..1)
    crop: Optional[list[float]] = None  # [x0,y0,x1,y1]
    # Additional metadata
    meta: Dict[str, Any] = Field(default_factory=dict)


class Track(BaseModel):
    id: str
    kind: ClipType
    clips: List[Clip] = Field(default_factory=list)


class Template(BaseModel):
    name: str = "Clean"
    # Minimal template props (extend as needed)
    header: str = ""
    subheader: str = ""
    footer: str = ""
    cta_label: str = ""
    color: list[int] = Field(default_factory=lambda: [16, 153, 127])


class Script(BaseModel):
    title: str = ""
    price: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    cta: Optional[str] = None


class Project(BaseModel):
    id: str
    name: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 10.0
    template: Template = Field(default_factory=Template)
    tracks: List[Track] = Field(default_factory=list)
    script: Script = Field(default_factory=Script)
    assets: Dict[str, str] = Field(default_factory=dict)  # assetId -> local path
    created_at: float
    updated_at: float


class CreateProjectReq(BaseModel):
    name: str
    width: Optional[int] = 1080
    height: Optional[int] = 1920
    fps: Optional[int] = 30
    duration: Optional[float] = 10.0


class RenderReq(BaseModel):
    project_id: str
    out_name: Optional[str] = None
    with_tts: bool = False


class ScrollCaptureReq(BaseModel):
    url: str
    max_images: int = 12
    mobile: bool = True
    use_stealth: bool = True

