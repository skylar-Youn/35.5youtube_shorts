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
try:
    from moviepy.video.fx.FadeIn import FadeIn
    from moviepy.video.fx.FadeOut import FadeOut
except Exception:
    FadeIn = None  # type: ignore
    FadeOut = None  # type: ignore
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip

from .models import Project, Track, Clip, Template
from .tts import synthesize as tts_synthesize



def _mk_text_clip(text: str, w: int, h: int, size: int, color: str, align: str, opacity: float = 1.0,
                  pos: tuple[int, int] = (0, 0), duration: float = 1.0,
                  outline_w: int = 0, outline_color: str | None = None,
                  bg_color: str | None = None, bg_pad: int = 0) -> ImageClip:
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
    # Optional background
    if bg_color:
        try:
            br = int(bg_color[1:3], 16)
            bg = int(bg_color[3:5], 16)
            bb = int(bg_color[5:7], 16)
            ba = 200
        except Exception:
            br, bg, bb, ba = (0, 0, 0, 140)
        pad = max(0, int(bg_pad))
        rx0 = max(0, x - pad)
        ry0 = max(0, y - pad)
        rx1 = min(w, x + tw + pad)
        ry1 = min(h, y + th + pad)
        try:
            dr.rounded_rectangle([rx0, ry0, rx1, ry1], radius=12, fill=(br, bg, bb, ba))
        except Exception:
            dr.rectangle([rx0, ry0, rx1, ry1], fill=(br, bg, bb, ba))
    # Outline
    stroke_kw = {}
    if outline_w and outline_color:
        try:
            or_, og, ob = int(outline_color[1:3], 16), int(outline_color[3:5], 16), int(outline_color[5:7], 16)
        except Exception:
            or_, og, ob = (0, 0, 0)
        stroke_kw = {"stroke_width": max(1, int(outline_w)), "stroke_fill": (or_, og, ob, a)}
    dr.text((x, y), text, font=f, fill=(r, g, b, a), **stroke_kw)
    return ImageClip(np.array(img)).with_duration(duration)


def _mk_image_clip(path: str, canvas_w: int, canvas_h: int, start: float, duration: float, tr, fade_in=0.0, fade_out=0.0, scale_fn=None) -> ImageClip:
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
    # Basic Ken Burns or custom scale
    if scale_fn is None:
        scale_fn = lambda t: tr.scale + 0.02 * t / max(0.001, duration)
    clip = clip.with_effects([Resize(scale_fn)])
    if FadeIn and fade_in > 0:
        clip = clip.with_effects([FadeIn(fade_in)])
    if FadeOut and fade_out > 0:
        clip = clip.with_effects([FadeOut(fade_out)])
    return clip.with_opacity(tr.opacity)


def _mk_video_clip(path: str, canvas_w: int, canvas_h: int, start: float, duration: float, tr, fade_in=0.0, fade_out=0.0, scale_fn=None):
    clip = VideoFileClip(path).subclip(0, duration)
    # Letterbox to canvas size
    clip = clip.resize(height=canvas_h) if clip.w / clip.h > canvas_w / canvas_h else clip.resize(width=canvas_w)
    clip = clip.with_start(start).with_duration(duration).with_opacity(tr.opacity)
    if FadeIn and fade_in > 0:
        clip = clip.with_effects([FadeIn(fade_in)])
    if FadeOut and fade_out > 0:
        clip = clip.with_effects([FadeOut(fade_out)])
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
                    # Optional scale keyframes (within clip local time)
                    scale_fn = None
                    kfs = getattr(c, "keyframes", None)
                    if kfs:
                        try:
                            kfs_sorted = sorted([kf for kf in kfs if isinstance(kf, dict) and "t" in kf], key=lambda k: float(k.get("t", 0)))
                            def interp(t: float):
                                if not kfs_sorted:
                                    return c.transform.scale
                                if t <= float(kfs_sorted[0].get("t", 0)):
                                    return float(kfs_sorted[0].get("scale", c.transform.scale))
                                if t >= float(kfs_sorted[-1].get("t", 0)):
                                    return float(kfs_sorted[-1].get("scale", c.transform.scale))
                                for i in range(len(kfs_sorted)-1):
                                    a, b = kfs_sorted[i], kfs_sorted[i+1]
                                    ta, tb = float(a.get("t", 0)), float(b.get("t", 0))
                                    if ta <= t <= tb:
                                        va = float(a.get("scale", c.transform.scale))
                                        vb = float(b.get("scale", c.transform.scale))
                                        u = (t - ta) / max(1e-6, (tb - ta))
                                        return va * (1 - u) + vb * u
                                return c.transform.scale
                            scale_fn = lambda t: interp(t)
                        except Exception:
                            scale_fn = None
                    if track.kind == "video" or (os.path.splitext(c.src)[1].lower() in [".mp4", ".mov", ".mkv", ".webm"]):
                        layers.append(_mk_video_clip(c.src, W, H, c.start, c.duration, c.transform, getattr(c, "fade_in", 0.0), getattr(c, "fade_out", 0.0), scale_fn))
                    else:
                        layers.append(_mk_image_clip(c.src, W, H, c.start, c.duration, c.transform, getattr(c, "fade_in", 0.0), getattr(c, "fade_out", 0.0), scale_fn))
                except Exception:
                    pass
            elif track.kind == "text" and c.text:
                x = int(c.transform.x * W)
                y = int(c.transform.y * H)
                tclip = _mk_text_clip(
                    c.text, W, H, getattr(c, "text_size", 48), getattr(c, "text_color", "#ffffff"), getattr(c, "text_align", "center"),
                    c.transform.opacity, (x, y), c.duration,
                    getattr(c, "text_outline_width", 0), getattr(c, "text_outline_color", None), getattr(c, "text_bg_color", None), getattr(c, "text_bg_pad", 0)
                ).with_start(c.start)
                if FadeIn and getattr(c, "fade_in", 0.0) > 0:
                    tclip = tclip.with_effects([FadeIn(getattr(c, "fade_in", 0.0))])
                if FadeOut and getattr(c, "fade_out", 0.0) > 0:
                    tclip = tclip.with_effects([FadeOut(getattr(c, "fade_out", 0.0))])
                layers.append(tclip)
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
    # Template overlay (top-level) with optional caption from script
    try:
        overlay = _make_template_overlay(prj)
        if overlay is not None:
            ov_clip = ImageClip(np.array(overlay)).with_duration(prj.duration)
            base = CompositeVideoClip([base, ov_clip]).with_duration(prj.duration)
    except Exception:
        pass
    if audio_layers:
        base = base.with_audio(CompositeAudioClip(audio_layers))
    # Optional TTS from script features (single track)
    try:
        caption_lines = []
        if prj.script and isinstance(prj.script.features, list):
            caption_lines = [str(x) for x in prj.script.features if str(x).strip()]
        if not caption_lines and prj.script and prj.script.title:
            caption_lines = [prj.script.title]
        if caption_lines:
            text = " ".join(caption_lines)
            tts_path = os.path.join(os.path.dirname(out_path), "narration.mp3")
            got = tts_synthesize(text, tts_path, backend="auto")
            if got and os.path.exists(got):
                from moviepy.audio.io.AudioFileClip import AudioFileClip
                narr = AudioFileClip(got).with_start(0).with_duration(min(base.duration, AudioFileClip(got).duration))
                if base.audio is not None:
                    from moviepy.audio.AudioClip import CompositeAudioClip
                    base = base.with_audio(CompositeAudioClip([base.audio, narr]))
                else:
                    base = base.with_audio(narr)
    except Exception:
        pass
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if progress_cb:
        progress_cb(0.95)
    base.write_videofile(out_path, fps=prj.fps, codec="libx264", audio_codec="aac")
    if progress_cb:
        progress_cb(1.0)
    return out_path


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


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int):
    words = str(text or "").split()
    lines, cur = [], []
    for w in words:
        cur.append(w)
        t = " ".join(cur)
        bb = draw.textbbox((0, 0), t, font=font)
        if (bb[2]-bb[0]) > max_width:
            cur.pop()
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    return lines


def _make_template_overlay(prj: Project) -> Image.Image | None:
    tpl: Template = prj.template or Template()
    W, H = prj.width, prj.height
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    theme = tuple((tpl.color + [0, 0, 0])[:3])
    # top bar
    bar_h = max(40, min(H // 4, int(tpl.bar_height)))
    draw.rectangle([0, 0, W, bar_h], fill=(theme[0], theme[1], theme[2], 230))
    # header
    if tpl.header:
        f = _font(max(16, int(tpl.size_hdr)))
        bb = draw.textbbox((0, 0), tpl.header, font=f)
        draw.text((24, (bar_h - (bb[3]-bb[1])) // 2), tpl.header, font=f, fill=(255, 255, 255, 255))
    # title card or badge
    card_h = max(120, min(H // 2, int(tpl.card_height)))
    if getattr(tpl, "badge_title", False):
        if prj.script and prj.script.title:
            f = _font(max(18, int(tpl.size_title)))
            lines = _wrap_lines(draw, prj.script.title, f, max_width=W - 320, max_lines=2)
            maxw, total_h = 0, 0
            for l in lines:
                bb = draw.textbbox((0, 0), l, font=f)
                maxw = max(maxw, bb[2]-bb[0])
                total_h += (bb[3]-bb[1]) + 6
            total_h = max(0, total_h - 6)
            bx0 = (W - (maxw + 64)) // 2
            by0 = bar_h + 18
            bx1 = bx0 + maxw + 64
            by1 = by0 + total_h + 36
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=24, fill=(255,255,255,245), outline=(theme[0], theme[1], theme[2], 255), width=6)
            y = by0 + 18
            for l in lines:
                bb = draw.textbbox((0, 0), l, font=f)
                draw.text(((W - (bb[2]-bb[0])) // 2, y), l, font=f, fill=(0,0,0,255))
                y += (bb[3]-bb[1]) + 6
    else:
        draw.rectangle([0, bar_h, W, bar_h + card_h], fill=(255, 255, 255, 235))
        if prj.script and prj.script.title:
            f = _font(max(18, int(tpl.size_title)))
            lines = _wrap_lines(draw, prj.script.title, f, max_width=W - 120, max_lines=3)
            y = bar_h + 26
            for l in lines:
                bb = draw.textbbox((0, 0), l, font=f)
                draw.text(((W - (bb[2]-bb[0])) // 2, y), l, font=f, fill=(0,0,0,255))
                y += (bb[3]-bb[1]) + 6
            draw.line([60, bar_h + card_h - 10, W - 60, bar_h + card_h - 10], fill=(60, 60, 60, 255), width=2)
    # caption block bottom
    if getattr(tpl, "bottom_caption_bar", False):
        area_h = max(100, int(getattr(tpl, "caption_area_h", 250)))
        bar_hh = min(area_h - 20, int(getattr(tpl, "bottom_caption_bar_h", 140)))
        y0 = H - area_h - 20
        y1 = y0 + bar_hh
        draw.rounded_rectangle([24, y0, W-24, y1], radius=20, fill=(255,255,255,245))
    # dynamic caption (features -> first line)
    try:
        cap = None
        if prj.script and prj.script.features:
            cap = str(prj.script.features[0])
        elif prj.script and prj.script.price:
            cap = str(prj.script.price)
        if cap:
            f = _font(max(18, int(tpl.size_mid)))
            lines = _wrap_lines(draw, cap, f, max_width=W-140, max_lines=3)
            total_h = sum(draw.textbbox((0,0), l, font=f)[3]-draw.textbbox((0,0), l, font=f)[1] for l in lines) + max(0, (len(lines)-1))*8
            if tpl.caption_pos == "bottom":
                area_h = max(120, int(getattr(tpl, "caption_area_h", 250)))
                y = H - area_h + 10
                if y + total_h > H - 10:
                    y = max(H - 10 - total_h, 0)
            else:
                y = bar_h + card_h + 60
            for l in lines:
                bb = draw.textbbox((0, 0), l, font=f)
                draw.text(((W - (bb[2]-bb[0])) // 2, y), l, font=f, fill=(20,20,20,255))
                y += (bb[3]-bb[1]) + 8
    except Exception:
        pass
    # CTA pill
    pill_x = max(8, min(W - int(tpl.pill_w) - 8, int(tpl.pill_x)))
    pill_y = max(8, min(H - int(tpl.pill_h) - 8, int(tpl.pill_y)))
    draw.rounded_rectangle([pill_x, pill_y, pill_x + int(tpl.pill_w), pill_y + int(tpl.pill_h)], radius=28, fill=(255,255,255,235))
    fcta = _font(max(14, int(tpl.size_cta)))
    bb = draw.textbbox((0,0), tpl.cta_label or "제품 보기", font=fcta)
    draw.text((pill_x + (int(tpl.pill_w) - (bb[2]-bb[0])) // 2, pill_y + (int(tpl.pill_h) - (bb[3]-bb[1])) // 2), tpl.cta_label or "제품 보기", font=fcta, fill=(16,16,16,255))
    # profile name
    fprof = _font(max(12, int(tpl.size_prof)))
    y_prof = pill_y + int(tpl.pill_h) + int(tpl.profile_offset)
    draw.ellipse([tpl.profile_x, y_prof, tpl.profile_x + 56, y_prof + 56], fill=(230,230,230,255))
    draw.text((tpl.profile_x + 56 + 12, y_prof + 13), tpl.profile_name or "@channel", font=fprof, fill=(255,255,255,255))
    # footer
    if tpl.footer:
        ff = _font(max(12, int(tpl.size_foot)))
        bb = draw.textbbox((0,0), tpl.footer, font=ff)
        draw.text((24, H - 36 - (bb[3]-bb[1])), tpl.footer, font=ff, fill=(230,230,230,255))
    return overlay
