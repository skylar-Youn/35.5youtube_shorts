from __future__ import annotations
import os
import time
from typing import Iterable
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.video.VideoClip import ImageClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.Resize import Resize
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip

from .models import Project, Track, Clip


def _font(size: int) -> ImageFont.ImageFont:
    for p in [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\malgun.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _mk_text_clip(text: str, w: int, h: int, size: int, color: str, align: str, opacity: float = 1.0,
                  pos: tuple[int, int] = (0, 0), duration: float = 1.0) -> ImageClip:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    f = _font(size)
    bbox = dr.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    if align == "left":
        x = pos[0]
    elif align == "right":
        x = max(0, pos[0] - tw)
    else:
        x = max(0, pos[0] - tw // 2)
    y = max(0, pos[1] - th // 2)
    # Convert hex color
    try:
        if color.startswith('#') and len(color) in (7, 9):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        else:
            r, g, b = (255, 255, 255)
    except Exception:
        r, g, b = (255, 255, 255)
    a = int(max(0.0, min(1.0, opacity)) * 255)
    dr.text((x, y), text, font=f, fill=(r, g, b, a))
    return ImageClip(np.array(img)).with_duration(duration)


def _mk_image_clip(path: str, canvas_w: int, canvas_h: int, start: float, duration: float, tr) -> ImageClip:
    img = Image.open(path).convert("RGB")
    iw, ih = img.size
    target_ratio = canvas_w / canvas_h
    src_ratio = iw / ih
    if src_ratio > target_ratio:
        new_h = canvas_h
        new_w = int(src_ratio * new_h)
    else:
        new_w = canvas_w
        new_h = int(new_w / src_ratio)
    img_resized = img.resize((new_w, new_h))
    canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
    x = (canvas_w - new_w) // 2
    y = (canvas_h - new_h) // 2
    canvas.paste(img_resized, (x, y))
    clip = ImageClip(np.array(canvas)).with_start(start).with_duration(duration)
    # Basic Ken Burns
    clip = clip.with_effects([Resize(lambda t: tr.scale + 0.02 * t / max(0.001, duration))])
    return clip.with_opacity(tr.opacity)


def _mk_video_clip(path: str, canvas_w: int, canvas_h: int, start: float, duration: float, tr):
    clip = VideoFileClip(path).subclip(0, duration)
    # Letterbox to canvas size
    clip = clip.resize(height=canvas_h) if clip.w / clip.h > canvas_w / canvas_h else clip.resize(width=canvas_w)
    clip = clip.with_start(start).with_duration(duration).with_opacity(tr.opacity)
    return clip


def _iter_clips(track: Track) -> Iterable[Clip]:
    for c in track.clips:
        yield c


def render_project(prj: Project, out_path: str, progress_cb=None) -> str:
    W, H = prj.width, prj.height
    layers = []
    audio_layers = []
    total = sum(len(t.clips) for t in prj.tracks)
    done = 0
    for track in prj.tracks:
        for c in _iter_clips(track):
            if track.kind in ("image", "video") and c.src and os.path.exists(c.src):
                try:
                    if track.kind == "video" or (os.path.splitext(c.src)[1].lower() in [".mp4", ".mov", ".mkv", ".webm"]):
                        layers.append(_mk_video_clip(c.src, W, H, c.start, c.duration, c.transform))
                    else:
                        layers.append(_mk_image_clip(c.src, W, H, c.start, c.duration, c.transform))
                except Exception:
                    pass
            elif track.kind == "text" and c.text:
                x = int(c.transform.x * W)
                y = int(c.transform.y * H)
                layers.append(
                    _mk_text_clip(
                        c.text, W, H, c.text_size, c.text_color, c.text_align, c.transform.opacity, (x, y), c.duration
                    ).with_start(c.start)
                )
            elif track.kind == "audio" and c.src and os.path.exists(c.src):
                try:
                    ac = AudioFileClip(c.src).with_start(c.start).with_duration(c.duration)
                    audio_layers.append(ac)
                except Exception:
                    pass
            done += 1
            if progress_cb:
                progress_cb(min(0.9, done / max(1, total)))

    base = CompositeVideoClip(layers, size=(W, H)).with_duration(prj.duration)
    if audio_layers:
        base = base.with_audio(CompositeAudioClip(audio_layers))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if progress_cb:
        progress_cb(0.95)
    base.write_videofile(out_path, fps=prj.fps, codec="libx264", audio_codec="aac")
    if progress_cb:
        progress_cb(1.0)
    return out_path
