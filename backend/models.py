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
    # Transitions
    fade_in: float = 0.0
    fade_out: float = 0.0
    # Text settings
    text: Optional[str] = None
    text_size: int = 48
    text_color: str = "#ffffff"
    text_align: Literal["left", "center", "right"] = "center"
    text_outline_color: Optional[str] = None
    text_outline_width: int = 0
    text_bg_color: Optional[str] = None
    text_bg_pad: int = 0
    # Image crop (optional, relative 0..1)
    crop: Optional[list[float]] = None  # [x0,y0,x1,y1]
    # Additional metadata
    meta: Dict[str, Any] = Field(default_factory=dict)
    # Simple keyframes for transforms (relative times within clip)
    keyframes: Optional[list[Dict[str, Any]]] = None  # e.g., [{"t":0, "opacity":1, "scale":1.0}]


class Track(BaseModel):
    id: str
    kind: ClipType
    clips: List[Clip] = Field(default_factory=list)


class Template(BaseModel):
    name: str = "Clean"
    # Texts
    header: str = ""
    subheader: str = ""
    footer: str = ""
    cta_label: str = "제품 보기"
    profile_name: str = "@channel"
    # Color
    color: list[int] = Field(default_factory=lambda: [16, 153, 127])
    # Layout
    bar_height: int = 90
    card_height: int = 260
    # CTA pill
    pill_x: int = 24
    pill_y: int = 1720
    pill_w: int = 200
    pill_h: int = 64
    # Profile
    profile_x: int = 24
    profile_offset: int = 18
    # Fonts
    size_hdr: int = 40
    size_title: int = 56
    size_mid: int = 54
    size_cta: int = 32
    size_prof: int = 30
    size_foot: int = 28
    # Caption behavior
    caption_pos: Literal["mid", "bottom"] = "mid"
    caption_area_h: int = 250
    badge_title: bool = False
    bottom_caption_bar: bool = False
    bottom_caption_bar_h: int = 140


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
