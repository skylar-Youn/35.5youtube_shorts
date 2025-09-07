import os
import re
import io
import sys
import json
import math
import time
import argparse
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# PDF
import fitz  # PyMuPDF

# Media
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.VideoClip import ImageClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import (
    CompositeVideoClip,
    concatenate_videoclips,
)
from moviepy.audio.AudioClip import CompositeAudioClip, concatenate_audioclips
from moviepy.audio import fx as afx
from moviepy.video.fx.Resize import Resize

# Optional TTS
try:
    import pyttsx3
    HAS_TTS = True
except Exception:
    HAS_TTS = False

W, H = 1080, 1920  # 9:16


@dataclass
class DocumentInfo:
    title: str
    price: Optional[str] = None
    features: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    cta: str = "더 알아보기는 링크 클릭!"


@dataclass
class TemplateConfig:
    header: str = ""
    subheader: str = ""
    footer: str = ""
    cta_label: str = "제품 보기"
    profile_name: str = "@channel"
    theme_color: tuple = (16, 153, 127)  # teal-ish
    avatar_path: Optional[str] = None
    # Layout tuning
    bar_height: int = 90
    card_height: int = 280
    # CTA pill geometry
    pill_x: int = 24
    pill_y: int = 1920 - 220
    pill_w: int = 200
    pill_h: int = 64
    # Profile position (top-left of avatar circle)
    profile_x: int = 24
    profile_y_offset: int = 18  # added to (pill_y + pill_h)
    # Font sizes
    hdr_size: int = 40
    title_size: int = 56
    mid_size: int = 54
    cta_size: int = 32
    prof_size: int = 30
    foot_size: int = 28


def safe_font(font_path: Optional[str] = None, size: int = 60) -> ImageFont.FreeTypeFont:
    paths = []
    if font_path and os.path.exists(font_path):
        paths.append(font_path)
    paths += [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\malgun.ttf",
    ]
    for pth in paths:
        try:
            return ImageFont.truetype(pth, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> List[str]:
    words = text.split()
    lines = []
    line = []
    for w in words:
        line.append(w)
        test = " ".join(line)
        bbox = draw.textbbox((0, 0), test, font=font)
        tw = bbox[2] - bbox[0]
        if tw > max_width:
            if len(line) > 1:
                line.pop()
            lines.append(" ".join(line))
            line = [w]
            if len(lines) >= max_lines:
                break
    if line and len(lines) < max_lines:
        lines.append(" ".join(line))
    return lines


def _make_template_overlay(dynamic_caption: Optional[str], tpl: TemplateConfig, font_path: Optional[str]) -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Top bar
    bar_h = max(40, min(H // 4, int(tpl.bar_height)))
    theme = tpl.theme_color
    draw.rectangle([0, 0, W, bar_h], fill=(theme[0], theme[1], theme[2], 230))
    # Header text inside bar (left)
    font_hdr = safe_font(font_path, size=max(16, int(tpl.hdr_size)))
    hdr = tpl.header or ""
    if hdr:
        bbox = draw.textbbox((0, 0), hdr, font=font_hdr)
        th = bbox[3] - bbox[1]
        draw.text((24, (bar_h - th) // 2), hdr, font=font_hdr, fill=(255, 255, 255, 255))

    # White title area (card-like)
    card_h = max(120, min(H // 2, int(tpl.card_height)))
    draw.rectangle([0, bar_h, W, bar_h + card_h], fill=(255, 255, 255, 235))
    # Subheader/title lines
    font_title = safe_font(font_path, size=max(18, int(tpl.title_size)))
    subhdr = tpl.subheader or ""
    if subhdr:
        lines = _wrap_lines(draw, subhdr, font_title, max_width=W - 120, max_lines=3)
        y = bar_h + 26
        for l in lines:
            bbox = draw.textbbox((0, 0), l, font=font_title)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, y), l, font=font_title, fill=(0, 0, 0, 255))
            y += (bbox[3] - bbox[1]) + 6
        # Divider
        draw.line([60, bar_h + card_h - 10, W - 60, bar_h + card_h - 10], fill=(60, 60, 60, 255), width=2)

    # Dynamic caption (mid)
    if dynamic_caption:
        font_mid = safe_font(font_path, size=max(18, int(tpl.mid_size)))
        maxw = W - 140
        lines = _wrap_lines(draw, dynamic_caption, font_mid, maxw, max_lines=3)
        # Place text below the card, approx below 1/3 of screen
        y0 = bar_h + card_h + 60
        for l in lines:
            bbox = draw.textbbox((0, 0), l, font=font_mid)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(((W - tw) // 2, y0), l, font=font_mid, fill=(20, 20, 20, 255))
            y0 += th + 8

    # Bottom gradient for readability
    grad_h = 360
    for i in range(grad_h):
        a = int(180 * (i / grad_h))
        draw.line([(0, H - grad_h + i), (W, H - grad_h + i)], fill=(0, 0, 0, a))

    # CTA pill (bottom-left)
    pill_h = max(40, int(tpl.pill_h))
    pill_w = max(120, int(tpl.pill_w))
    pill_x = max(8, min(W - pill_w - 8, int(tpl.pill_x)))
    pill_y = max(8, min(H - pill_h - 8, int(tpl.pill_y)))
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=28, fill=(255, 255, 255, 235))
    font_cta = safe_font(font_path, size=max(14, int(tpl.cta_size)))
    cta_text = tpl.cta_label or "제품 보기"
    bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((pill_x + (pill_w - tw) // 2, pill_y + (pill_h - th) // 2), cta_text, font=font_cta, fill=(16, 16, 16, 255))

    # Profile + subscribe chip
    prof_y = pill_y + pill_h + int(tpl.profile_y_offset)
    prof_x = max(8, min(W - 56 - 8, int(tpl.profile_x)))
    # avatar circle or image
    avatar_box = [prof_x, prof_y, prof_x + 56, prof_y + 56]
    if tpl.avatar_path and os.path.exists(tpl.avatar_path):
        try:
            av = Image.open(tpl.avatar_path).convert("RGB").resize((56, 56), Image.LANCZOS)
            # create circular mask
            mask = Image.new("L", (56, 56), 0)
            md = ImageDraw.Draw(mask)
            md.ellipse([0, 0, 56, 56], fill=255)
            overlay.paste(av, (prof_x, prof_y), mask)
        except Exception:
            draw.ellipse(avatar_box, fill=(230, 230, 230, 255))
    else:
        draw.ellipse(avatar_box, fill=(230, 230, 230, 255))
    font_prof = safe_font(font_path, size=max(12, int(tpl.prof_size)))
    pname = tpl.profile_name or "@channel"
    bbox = draw.textbbox((0, 0), pname, font=font_prof)
    draw.text((prof_x + 56 + 12, prof_y + 13), pname, font=font_prof, fill=(255, 255, 255, 255))
    # subscribe pill
    sub_w = 96
    sub_h = 44
    sub_x = prof_x + 56 + 12 + (bbox[2] - bbox[0]) + 12
    sub_y = prof_y + 6
    draw.rounded_rectangle([sub_x, sub_y, sub_x + sub_w, sub_y + sub_h], radius=20, fill=(255, 255, 255, 235))
    font_sub = safe_font(font_path, size=max(12, int(tpl.cta_size) - 6))
    sb = "구독"
    bb = draw.textbbox((0, 0), sb, font=font_sub)
    draw.text((sub_x + (sub_w - (bb[2]-bb[0])) // 2, sub_y + (sub_h - (bb[3]-bb[1])) // 2), sb, font=font_sub, fill=(16, 16, 16, 255))

    # Footer text
    foot = tpl.footer or ""
    if foot:
        font_foot = safe_font(font_path, size=max(12, int(tpl.foot_size)))
        bb = draw.textbbox((0, 0), foot, font=font_foot)
        draw.text((24, H - 36 - (bb[3]-bb[1])), foot, font=font_foot, fill=(230, 230, 230, 255))

    return overlay


def make_image_slide(src_path: str, caption: Optional[str], duration: float, font_path: Optional[str], tpl: Optional[TemplateConfig] = None,
                     highlight: Optional[List[float]] = None) -> ImageClip:
    img = Image.open(src_path).convert("RGB")
    img_w, img_h = img.size
    target_ratio = W / H
    src_ratio = img_w / img_h

    if src_ratio > target_ratio:
        new_h = H
        new_w = int(src_ratio * new_h)
    else:
        new_w = W
        new_h = int(new_w / src_ratio)
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    x = (W - new_w) // 2
    y = (H - new_h) // 2
    canvas.paste(img_resized, (x, y))

    clip = ImageClip(np.array(canvas)).with_duration(duration)

    # Optional highlight rectangle [x0,y0,x1,y1] in 0..1 coords on final canvas
    if highlight and len(highlight) == 4:
        try:
            x0 = int(max(0, min(1, highlight[0])) * W)
            y0 = int(max(0, min(1, highlight[1])) * H)
            x1 = int(max(0, min(1, highlight[2])) * W)
            y1 = int(max(0, min(1, highlight[3])) * H)
            if x1 > x0 and y1 > y0:
                hi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                hd = ImageDraw.Draw(hi)
                hd.rectangle([x0, y0, x1, y1], outline=(255, 255, 0, 255), width=8)
                hd.rectangle([x0, y0, x1, y1], fill=(255, 255, 0, 40))
                clip = CompositeVideoClip([clip, ImageClip(np.array(hi)).with_duration(duration)])
        except Exception:
            pass

    if tpl:
        overlay = _make_template_overlay(caption, tpl, font_path)
        overlay_clip = ImageClip(np.array(overlay)).with_duration(duration)
        clip = CompositeVideoClip([clip, overlay_clip]).with_duration(duration)
    else:
        if caption:
            txt_img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
            draw = ImageDraw.Draw(txt_img)
            font = safe_font(font_path, size=54)
            lines = _wrap_lines(draw, caption, font, max_width=W - 120, max_lines=3)
            cur_y = 30
            for l in lines[:3]:
                bbox = draw.textbbox((0, 0), l, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(((W - tw)//2, cur_y), l, font=font, fill=(245,245,245,255))
                cur_y += th + 12
            caption_clip = (
                ImageClip(np.array(txt_img))
                .with_duration(duration)
                .with_position(("center", "bottom"))
            )
            clip = CompositeVideoClip([clip, caption_clip]).with_duration(duration)

    clip = clip.with_effects([Resize(lambda t: 1.02 + 0.02 * t / max(0.001, duration))])
    return clip


def synthesize_voice(lines: List[str], out_path: str, rate: int = 185) -> Optional[str]:
    if not HAS_TTS:
        return None
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        for v in engine.getProperty("voices"):
            name = (getattr(v, "name", "") or "").lower()
            langs = (getattr(v, "languages", []) or [])
            if "ko" in str(langs).lower() or "korean" in name:
                engine.setProperty("voice", v.id)
                break
        engine.save_to_file(" ".join(lines), out_path)
        engine.runAndWait()
        return out_path
    except Exception:
        return None


def build_timeline(images: List[str], script: Dict[str, List[str]], duration: int, font_path: Optional[str],
                   min_slide: float, max_slide: float, tpl: Optional[TemplateConfig] = None,
                   slides_spec: Optional[List[Dict]] = None) -> CompositeVideoClip:
    if slides_spec:
        slides = []
        for i, spec in enumerate(slides_spec):
            path = spec.get("image") if isinstance(spec, dict) else None
            if not path or not os.path.exists(path):
                path = images[i % len(images)] if images else None
            if not path:
                continue
            cap = spec.get("caption") if isinstance(spec, dict) else None
            per = float(spec.get("duration", max(min_slide, min(max_slide, duration / max(1, len(slides_spec))))))
            hl = spec.get("highlight") if isinstance(spec, dict) else None
            slide = make_image_slide(path, cap, per, font_path, tpl=tpl, highlight=hl)
            slides.append(slide)
        if not slides:
            # fallback to default flow
            slides_spec = None

    if not slides_spec:
        captions = script["hook"] + script["core"] + script["closing"]
        n = max(len(images), len(captions))
        if n == 0:
            n = 6
        per = max(min_slide, min(max_slide, duration / n))
        total = per * n
        scale = duration / total if total > 0 else 1.0
        per *= scale

        while len(images) < n:
            images.append(images[-1])

        slides = []
        for i in range(n):
            cap = captions[i] if i < len(captions) else None
            slide = make_image_slide(images[i], cap, per, font_path, tpl=tpl)
            slides.append(slide)
    video = concatenate_videoclips(slides, method="compose")
    video = video.with_effects([Resize((W, H))])
    return video


def extract_features_from_text(text: str, max_features: int = 5) -> List[str]:
    lines = [l.strip() for l in text.splitlines()]
    cands = []
    for l in lines:
        if not l:
            continue
        if len(l) < 6 or len(l) > 90:
            continue
        if re.match(r"^[•\-\d\s\.]+$", l):
            continue
        cands.append(l)
        if len(cands) >= max_features * 2:
            break
    # dedup
    dedup = []
    for c in cands:
        if c not in dedup:
            dedup.append(c)
    return dedup[:max_features] or ["핵심 내용 1", "핵심 내용 2", "핵심 내용 3"]


def _extract_image_blocks(page: fitz.Page, zoom: float, min_area_ratio: float = 0.05,
                          margin_ratio: float = 0.01, out_dir: str = "_work_pdf",
                          page_index: int = 0) -> List[str]:
    """Extract large image blocks from a PDF page by cropping the page to image bboxes.

    - Uses page.get_text("rawdict") to find blocks of type image and their bbox.
    - Filters out small images by min_area_ratio (relative to page area).
    - Adds a small margin around the bbox.
    """
    out_paths: List[str] = []
    try:
        raw = page.get_text("rawdict") or {}
        blocks = raw.get("blocks", [])
    except Exception:
        blocks = []

    page_area = float(page.rect.width * page.rect.height)
    mat = fitz.Matrix(zoom, zoom)
    os.makedirs(out_dir, exist_ok=True)
    idx = 0
    for b in blocks:
        try:
            btype = b.get("type")
            # In PyMuPDF, image blocks usually have type == 1
            if btype != 1:
                continue
            bbox = b.get("bbox")
            if not bbox:
                continue
            r = fitz.Rect(bbox)
            if r.width * r.height < page_area * float(min_area_ratio):
                continue
            # Expand bbox by margin ratio and clip to page rect
            mx, my = r.width * margin_ratio, r.height * margin_ratio
            r = fitz.Rect(r.x0 - mx, r.y0 - my, r.x1 + mx, r.y1 + my)
            r = r & page.rect
            if r.is_empty:
                continue
            pix = page.get_pixmap(matrix=mat, clip=r, alpha=False)
            fn = os.path.join(out_dir, f"page{page_index+1:02d}_img{idx+1:02d}.jpg")
            pix.save(fn)
            out_paths.append(fn)
            idx += 1
        except Exception:
            continue
    return out_paths


def parse_pdf(pdf_path: str, max_pages: int = 6, zoom: float = 2.0,
              mode: str = "page", min_img_ratio: float = 0.05, crop_margin: float = 0.01,
              max_extract: int = 20) -> DocumentInfo:
    doc = fitz.open(pdf_path)
    title = (doc.metadata.get("title") or "").strip() or os.path.basename(pdf_path)
    all_text = []
    images = []
    work_dir = "_work_pdf"
    os.makedirs(work_dir, exist_ok=True)

    extracted_images: List[str] = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text = page.get_text("text")
        all_text.append(text)
        if mode in ("image", "auto"):
            imgs = _extract_image_blocks(page, zoom=zoom, min_area_ratio=min_img_ratio,
                                         margin_ratio=crop_margin, out_dir=work_dir, page_index=i)
            for pth in imgs:
                if pth not in extracted_images:
                    extracted_images.append(pth)
            if len(extracted_images) >= max_extract:
                break
        if mode in ("page",):
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            fn = os.path.join(work_dir, f"page_{i+1:02d}.jpg")
            pix.save(fn)
            images.append(fn)

    doc.close()
    combined = "\n".join(all_text)
    # fallback title as first significant line
    if not title:
        for l in combined.splitlines():
            l = l.strip()
            if len(l) >= 6:
                title = l
                break
        if not title:
            title = "문서 요약"

    # price detection (optional)
    price = None
    m = re.search(r"(?:₩|\b)[\s]*([0-9]{1,3}(?:,[0-9]{3})+)\s*원?", combined)
    if m:
        price = m.group(0)

    features = extract_features_from_text(combined, max_features=5)
    # If mode is 'image' or 'auto' and we have extracted images, prefer them
    final_images = extracted_images if (mode in ("image", "auto") and extracted_images) else images
    # Fallback: if auto mode produced nothing, render whole pages
    if mode == "auto" and not final_images:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            fn = os.path.join(work_dir, f"page_{i+1:02d}.jpg")
            pix.save(fn)
            final_images.append(fn)
    return DocumentInfo(title=title, price=price, features=features, images=final_images)


def generate_script(p: DocumentInfo, cta: Optional[str] = None) -> Dict[str, List[str]]:
    hook = []
    core = []
    closing = []

    if p.price:
        hook.append(f"{p.title} — 이 가격에 이 구성?")
    else:
        hook.append(f"{p.title} — 핵심만 30초 요약!")

    for f in p.features[:4]:
        core.append(f"• {f}")

    if p.price:
        core.append(f"가격: {p.price}")

    closing.append(cta or p.cta)
    return {"hook": hook, "core": core, "closing": closing}


def main():
    ap = argparse.ArgumentParser(description="PDF/이미지 → Shorts MP4")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=str, help="입력 PDF 경로")
    src.add_argument("--images", nargs="+", help="입력 이미지 경로들(2장 이상 권장)")
    ap.add_argument("--out", type=str, default="out.mp4")
    ap.add_argument("--duration", type=int, default=24)
    ap.add_argument("--max_pages", type=int, default=6, help="사용할 최대 페이지 수")
    ap.add_argument("--zoom", type=float, default=2.0, help="PDF 렌더링 확대 배율")
    ap.add_argument("--music", type=str, help="배경음악 mp3/wav (선택)")
    ap.add_argument("--no_tts", action="store_true", help="TTS 내레이션 비활성화")
    ap.add_argument("--voice_rate", type=int, default=185)
    ap.add_argument("--font_path", type=str, default=None)
    ap.add_argument("--min_slide", type=float, default=2.0)
    ap.add_argument("--max_slide", type=float, default=5.0)
    ap.add_argument("--cta", type=str, default=None)
    ap.add_argument("--title", type=str, default=None, help="제목 텍스트 덮어쓰기")
    ap.add_argument("--price", type=str, default=None, help="가격 텍스트 덮어쓰기")
    ap.add_argument("--feature", action="append", help="특징 문구 추가(반복 가능)")
    # Template options
    ap.add_argument("--template_json", type=str, help="템플릿 텍스트 JSON 경로")
    ap.add_argument("--save_template", type=str, help="현재 텍스트를 템플릿 JSON으로 저장")
    ap.add_argument("--tpl_header", type=str, default=None)
    ap.add_argument("--tpl_subheader", type=str, default=None)
    ap.add_argument("--tpl_footer", type=str, default=None)
    ap.add_argument("--tpl_cta_label", type=str, default=None)
    ap.add_argument("--tpl_profile", type=str, default=None)
    ap.add_argument("--tpl_avatar", type=str, default=None, help="프로필 아바타 이미지 경로 (원형)")
    # Advanced layout/typography options (optional, also supported via template JSON)
    ap.add_argument("--tpl_bar", type=int, help="상단 바 높이(px)")
    ap.add_argument("--tpl_card", type=int, help="카드 높이(px)")
    ap.add_argument("--tpl_pill", type=str, help="CTA pill geom 'x,y,w,h'")
    ap.add_argument("--tpl_profile_xy", type=str, help="프로필 아바타 좌표 'x,y' (px)")
    ap.add_argument("--tpl_profile_x", type=int, help="프로필 X 좌표(px)")
    ap.add_argument("--tpl_profile_offset", type=int, help="프로필 수직 오프셋(px, pill 아래에서)"
                    )
    ap.add_argument("--tpl_sizes", type=str, help="폰트 크기들 'hdr,title,mid,cta,prof,foot'")
    # Script (text) save/load
    ap.add_argument("--script_json", type=str, help="제목/가격/특징/CTA를 담은 JSON 파일 경로")
    ap.add_argument("--save_script", type=str, help="현재 스크립트 텍스트를 JSON으로 저장")
    ap.add_argument("--pdf_mode", choices=["page", "image", "auto"], default="auto",
                    help="PDF 처리 방식: 전체 페이지 렌더(page), 이미지 블록 추출(image), 자동(auto)")
    ap.add_argument("--min_img_ratio", type=float, default=0.05,
                    help="이미지 블록 최소 면적 비율(페이지 대비)")
    ap.add_argument("--crop_margin", type=float, default=0.01,
                    help="이미지 bbox 여백 비율")
    ap.add_argument("--max_extract", type=int, default=20,
                    help="페이지에서 추출할 최대 이미지 수(전체)")
    args = ap.parse_args()

    # Build info and images depending on source
    # Optionally load script JSON overrides early
    script_data = None
    if args.script_json and os.path.exists(args.script_json):
        try:
            with open(args.script_json, "r", encoding="utf-8") as f:
                script_data = json.load(f)
        except Exception:
            script_data = None

    if args.pdf:
        if not os.path.exists(args.pdf):
            print("[error] PDF not found:", args.pdf)
            sys.exit(1)
        info = parse_pdf(
            args.pdf,
            max_pages=args.max_pages,
            zoom=args.zoom,
            mode=args.pdf_mode,
            min_img_ratio=args.min_img_ratio,
            crop_margin=args.crop_margin,
            max_extract=args.max_extract,
        )
        if (script_data and script_data.get("title")) or args.title:
            info.title = (script_data.get("title") if script_data else None) or args.title
        if (script_data and script_data.get("price")) or args.price:
            info.price = (script_data.get("price") if script_data else None) or args.price
        if (script_data and script_data.get("features")) or args.feature:
            for ftxt in args.feature:
                if ftxt and ftxt not in info.features:
                    info.features.append(ftxt)
            info.features = info.features[:6]
            if script_data and isinstance(script_data.get("features"), list):
                for ftxt in script_data["features"]:
                    if ftxt and ftxt not in info.features:
                        info.features.append(ftxt)
                info.features = info.features[:6]
        if args.cta:
            info.cta = args.cta
        elif script_data and script_data.get("cta"):
            info.cta = script_data.get("cta")
        images = info.images
    else:
        # Images mode
        valid_imgs = [p for p in (args.images or []) if os.path.exists(p)]
        if len(valid_imgs) == 0:
            print("[error] No valid image paths provided")
            sys.exit(1)
        # Build minimal info from overrides
        base_title = os.path.splitext(os.path.basename(valid_imgs[0]))[0]
        title = (script_data.get("title") if script_data else None) or args.title or base_title
        feats = ["핵심 내용 1", "핵심 내용 2", "핵심 내용 3"]
        if script_data and isinstance(script_data.get("features"), list):
            feats = script_data["features"]
        if args.feature:
            feats = [*(feats or []), *[x for x in args.feature if x]]
        info = DocumentInfo(title=title, price=(script_data.get("price") if script_data else None) or args.price, features=feats, images=list(valid_imgs))
        if args.cta:
            info.cta = args.cta
        elif script_data and script_data.get("cta"):
            info.cta = script_data.get("cta")
        images = info.images

    # Ensure we have at least a few images
    if not images:
        # create placeholders from title
        images = []
        for i in range(5):
            im = Image.new("RGB", (W, H), (18, 18, 18))
            draw = ImageDraw.Draw(im)
            font = safe_font(size=72)
            txt = info.title if i == 0 else f"Slide {i+1}"
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((W - tw)//2, (H - th)//2), txt, fill=(235,235,235), font=font)
            work_dir = "_work_pdf"
            os.makedirs(work_dir, exist_ok=True)
            fn = os.path.join(work_dir, f"ph_{i+1:02d}.jpg")
            im.save(fn, "JPEG", quality=90)
            images.append(fn)

    script = generate_script(info, cta=args.cta)

    # Template config assembling
    tpl_conf = None
    tpl_data = None
    if args.template_json and os.path.exists(args.template_json):
        try:
            with open(args.template_json, "r", encoding="utf-8") as f:
                tpl_data = json.load(f)
        except Exception:
            tpl_data = None
    tpl_data = tpl_data or {}
    header = args.tpl_header if args.tpl_header is not None else tpl_data.get("header")
    subheader = args.tpl_subheader if args.tpl_subheader is not None else tpl_data.get("subheader")
    footer = args.tpl_footer if args.tpl_footer is not None else tpl_data.get("footer")
    cta_label = args.tpl_cta_label if args.tpl_cta_label is not None else tpl_data.get("cta_label")
    profile_name = args.tpl_profile if args.tpl_profile is not None else tpl_data.get("profile_name")
    theme_color = tpl_data.get("theme_color")
    if theme_color and isinstance(theme_color, list) and len(theme_color) == 3:
        theme_tuple = tuple(int(x) for x in theme_color)
    else:
        theme_tuple = (16, 153, 127)
    # Load optional advanced keys from JSON
    adv = tpl_data if tpl_data else {}
    bar_h = adv.get("bar_height")
    card_h = adv.get("card_height")
    pill = adv.get("pill") or {}
    profile_xy = adv.get("profile_xy") or {}
    profile_x_adv = adv.get("profile_x")
    profile_off_adv = adv.get("profile_offset")
    sizes = adv.get("font_sizes") or {}
    if any([header, subheader, footer, cta_label, profile_name]) or args.tpl_avatar:
        tpl_conf = TemplateConfig(
            header=header or "",
            subheader=subheader or "",
            footer=footer or "",
            cta_label=cta_label or (info.cta or "제품 보기"),
            profile_name=profile_name or "@channel",
            theme_color=theme_tuple,
            avatar_path=args.tpl_avatar,
            bar_height=int(args.tpl_bar if args.tpl_bar is not None else (bar_h if bar_h is not None else 90)),
            card_height=int(args.tpl_card if args.tpl_card is not None else (card_h if card_h is not None else 280)),
            pill_x=int((list(map(int, (args.tpl_pill or "").split(",")))[0] if args.tpl_pill else (pill.get("x", 24)))),
            pill_y=int((list(map(int, (args.tpl_pill or "").split(",")))[1] if args.tpl_pill else (pill.get("y", H-220)))),
            pill_w=int((list(map(int, (args.tpl_pill or "").split(",")))[2] if args.tpl_pill else (pill.get("w", 200)))),
            pill_h=int((list(map(int, (args.tpl_pill or "").split(",")))[3] if args.tpl_pill else (pill.get("h", 64)))),
            profile_x=int(args.tpl_profile_x if args.tpl_profile_x is not None else (profile_x_adv if profile_x_adv is not None else profile_xy.get("x", 24))),
            profile_y_offset=int(args.tpl_profile_offset if args.tpl_profile_offset is not None else (profile_off_adv if profile_off_adv is not None else 18)),
            hdr_size=int((list(map(int, (args.tpl_sizes or "").split(",")))[0] if args.tpl_sizes else sizes.get("hdr", 40))),
            title_size=int((list(map(int, (args.tpl_sizes or "").split(",")))[1] if args.tpl_sizes else sizes.get("title", 56))),
            mid_size=int((list(map(int, (args.tpl_sizes or "").split(",")))[2] if args.tpl_sizes else sizes.get("mid", 54))),
            cta_size=int((list(map(int, (args.tpl_sizes or "").split(",")))[3] if args.tpl_sizes else sizes.get("cta", 32))),
            prof_size=int((list(map(int, (args.tpl_sizes or "").split(",")))[4] if args.tpl_sizes else sizes.get("prof", 30))),
            foot_size=int((list(map(int, (args.tpl_sizes or "").split(",")))[5] if args.tpl_sizes else sizes.get("foot", 28))),
        )
    # Slides spec JSON support
    slides_spec = None
    if getattr(args, "slides_json", None) and os.path.exists(args.slides_json):
        try:
            with open(args.slides_json, "r", encoding="utf-8") as f:
                slides_spec = json.load(f)
            if not isinstance(slides_spec, list):
                slides_spec = None
        except Exception:
            slides_spec = None

    video = build_timeline(images, script, duration=args.duration, font_path=args.font_path,
                           min_slide=args.min_slide, max_slide=args.max_slide, tpl=tpl_conf,
                           slides_spec=slides_spec)

    # Narration
    narration_path = None
    if not args.no_tts:
        work_dir = "_work_pdf"
        os.makedirs(work_dir, exist_ok=True)
        narration_path = synthesize_voice(
            script["hook"] + script["core"] + script["closing"],
            os.path.join(work_dir, "narration.wav"),
            rate=args.voice_rate,
        )

    final = video
    audio_clips = []
    if narration_path and os.path.exists(narration_path):
        try:
            audio_clips.append(AudioFileClip(narration_path))
        except Exception:
            pass
    if args.music and os.path.exists(args.music):
        try:
            bgm = AudioFileClip(args.music).with_effects([afx.MultiplyVolume(0.12)])
            if bgm.duration < video.duration:
                loops = math.ceil(video.duration / bgm.duration)
                bgm = concatenate_audioclips([bgm] * loops).with_duration(video.duration)
            audio_clips.append(bgm)
        except Exception as e:
            print("[warn] music load failed:", e)

    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).with_duration(video.duration)
        final = video.with_audio(final_audio)

    # Optionally save template used
    if args.save_template:
        out_tpl = {
            "header": header or "",
            "subheader": subheader or "",
            "footer": footer or "",
            "cta_label": (cta_label or (info.cta or "제품 보기")),
            "profile_name": profile_name or "@channel",
            "theme_color": list(theme_tuple),
        }
        try:
            with open(args.save_template, "w", encoding="utf-8") as f:
                json.dump(out_tpl, f, ensure_ascii=False, indent=2)
            print("[info] saved template:", args.save_template)
        except Exception as e:
            print("[warn] failed to save template:", e)

    # Optionally save script used
    if args.save_script:
        out_script = {
            "title": info.title,
            "price": info.price,
            "features": info.features,
            "cta": info.cta,
        }
        try:
            with open(args.save_script, "w", encoding="utf-8") as f:
                json.dump(out_script, f, ensure_ascii=False, indent=2)
            print("[info] saved script:", args.save_script)
        except Exception as e:
            print("[warn] failed to save script:", e)

    # Export
    final.write_videofile(
        args.out,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=None,
        pixel_format="yuv420p",
    )
    print("[done] exported:", args.out)


if __name__ == "__main__":
    main()
