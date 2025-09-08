import os
import io
import time
import shlex
import json
import tempfile
import subprocess
from datetime import datetime
import hashlib

# Load environment variables from a local .env if present
try:
    # Prefer python-dotenv when available
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv(), override=False)
except Exception:
    # Lightweight fallback: parse .env manually without overriding existing env
    _env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(_env_path):
        try:
            with open(_env_path, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _s = _line.strip()
                    if not _s or _s.startswith("#") or "=" not in _s:
                        continue
                    _k, _v = _s.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
        except Exception:
            # Silently ignore .env parsing errors; app will rely on existing env
            pass

import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


APP_TITLE = "Product/PDF/Images → Shorts MP4"
UPLOAD_DIR = os.path.join(os.getcwd(), "ui_uploads")
OUTPUT_DIR = os.path.join(os.getcwd(), "ui_outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Persistent UI preferences (saved under OUTPUT_DIR)
PREFS_PATH = os.path.join(OUTPUT_DIR, "ui_prefs.json")


def _load_ui_prefs() -> dict:
    try:
        if os.path.exists(PREFS_PATH):
            with open(PREFS_PATH, "r", encoding="utf-8") as f:
                js = json.load(f)
                return js if isinstance(js, dict) else {}
    except Exception:
        pass
    return {}


def _save_ui_prefs():
    keys = [
        # Fetch preferences
        "images_fetch_pw",
        "images_fetch_pw_stealth",
        "images_fetch_deep",
        "images_fetch_detail_only",
        "images_fetch_pw_mobile",
        "images_fetch_pw_wait",
        "images_fetch_deep_scrolls",
        "images_fetch_count",
        "images_fetch_timeout",
        "images_prefill_limit",
        # Thumbnails
        "images_thumbs_hq",
        # Overview preference
        "images_prefer_overview",
        # Selection behavior
        "images_use_selected_only",
        # Site choice
        "images_fetch_site",
    ]
    data = {}
    for k in keys:
        if k in st.session_state:
            try:
                data[k] = st.session_state[k]
            except Exception:
                continue
    try:
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Built-in template presets
PRESET_TEMPLATES = {
    "Clean": {
        "header": "경제덕후",
        "subheader": "핵심만, 빠르게",
        "footer": "",
        "cta_label": "제품 보기",
        "profile_name": "@channel",
        "theme_color": [16, 153, 127],
        "bar_height": 90,
        "card_height": 260,
        "pill": {"x": 24, "y": 1700, "w": 200, "h": 64},
        "profile_x": 24,
        "profile_offset": 18,
        "font_sizes": {"hdr": 40, "title": 56, "mid": 54, "cta": 32, "prof": 30, "foot": 28},
    },
    "K-Edu": {
        "header": "3분 요약",
        "subheader": "알아두면 쓸데있는",
        "footer": "",
        "cta_label": "더보기",
        "profile_name": "@edu",
        "theme_color": [0, 120, 210],
        "bar_height": 110,
        "card_height": 300,
        "pill": {"x": 24, "y": 1720, "w": 220, "h": 70},
        "profile_x": 28,
        "profile_offset": 20,
        "font_sizes": {"hdr": 42, "title": 60, "mid": 54, "cta": 34, "prof": 30, "foot": 28},
    },
    "Dark": {
        "header": "INSIGHT",
        "subheader": "오늘의 한 줄",
        "footer": "",
        "cta_label": "구매하기",
        "profile_name": "@insight",
        "theme_color": [10, 10, 10],
        "bar_height": 80,
        "card_height": 220,
        "pill": {"x": 28, "y": 1700, "w": 220, "h": 64},
        "profile_x": 28,
        "profile_offset": 24,
        "font_sizes": {"hdr": 36, "title": 54, "mid": 52, "cta": 30, "prof": 28, "foot": 26},
    },
}


def save_uploaded_file(file, subdir=""):
    if file is None:
        return None
    dirpath = os.path.join(UPLOAD_DIR, subdir) if subdir else UPLOAD_DIR
    os.makedirs(dirpath, exist_ok=True)
    filename = f"{int(time.time()*1000)}_{file.name}"
    path = os.path.join(dirpath, filename)
    with open(path, "wb") as f:
        f.write(file.getbuffer())
    return path


def _safe_placeholder_code(placeholder, text: str) -> bool:
    """Safely update a Streamlit placeholder with code text.

    Returns False if the UI update appears to fail (e.g., session disconnected),
    so callers can stop streaming and clean up long‑running tasks.
    """
    try:
        placeholder.code(text)
        return True
    except Exception:
        # When the client disconnects or reruns, Streamlit/Tornado can close the
        # websocket underneath. Attempting to update the UI at that moment may
        # raise from the app thread. Treat it as a signal to stop streaming.
        return False


def run_cmd(cmd_list):
    start = time.time()
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    logs: list[str] = []
    log_area = st.empty()
    last_flush = 0.0
    try:
        for line in iter(proc.stdout.readline, ""):
            logs.append(line)
            # Throttle UI updates to reduce websocket chatter
            now = time.time()
            if now - last_flush >= 0.20:
                if not _safe_placeholder_code(log_area, "".join(logs[-200:])):
                    # UI likely gone; stop streaming and terminate process
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break
                last_flush = now
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
    ret = proc.wait()
    duration = time.time() - start
    # Final flush of logs (best effort)
    _safe_placeholder_code(log_area, "".join(logs[-200:]))
    return ret, "".join(logs), duration


def fetch_html_requests(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.coupang.com/",
        "Connection": "keep-alive",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_html_playwright(url: str, timeout: int = 30, use_stealth: bool = True, mobile: bool = True,
                          wait_state: str = "networkidle") -> str:
    try:
        from playwright.sync_api import sync_playwright
        try:
            from playwright_stealth import stealth_sync as pw_stealth
        except Exception:
            pw_stealth = None
    except Exception as e:
        raise RuntimeError("Playwright not installed") from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set headers and UA to encourage Korean content
        ua_mobile = "Mozilla/5.0 (Linux; Android 13; SM-G998N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context_args = {
            "locale": "ko-KR",
            "ignore_https_errors": True,
            "user_agent": ua_mobile if mobile else ua_desktop,
            "extra_http_headers": {
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.coupang.com/",
            },
        }
        if mobile:
            context_args.update({
                "viewport": {"width": 375, "height": 667},
                "is_mobile": True,
                "device_scale_factor": 2,
            })
        ctx = browser.new_context(**context_args)
        page = ctx.new_page()
        if use_stealth and pw_stealth:
            pw_stealth(page)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_load_state(wait_state, timeout=max(1000, (timeout - 3) * 1000))
        except Exception:
            pass
        html = page.content()
        ctx.close()
        browser.close()
        return html


def fetch_images_playwright_deep(url: str, timeout: int = 45, use_stealth: bool = True, mobile: bool = True,
                                 wait_state: str = "networkidle", scrolls: int = 8, delay: float = 0.8):
    """Open the page with Playwright, scroll/expand sections, and return large image URLs.

    - Scrolls the page gradually to trigger lazy-loading.
    - Clicks common "show more"/description toggles (including Korean labels).
    - Collects image src/data-src/srcset and filters likely thumbnails/icons.
    """
    try:
        from playwright.sync_api import sync_playwright
        try:
            from playwright_stealth import stealth_sync as pw_stealth
        except Exception:
            pw_stealth = None
    except Exception as e:
        raise RuntimeError("Playwright not installed") from e

    urls: list[str] = []
    title: str | None = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ua_mobile = "Mozilla/5.0 (Linux; Android 13; SM-G998N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context_args = {
            "locale": "ko-KR",
            "ignore_https_errors": True,
            "user_agent": ua_mobile if mobile else ua_desktop,
            "extra_http_headers": {
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.aliexpress.com/",
            },
        }
        ctx = browser.new_context(**context_args)
        page = ctx.new_page()
        if use_stealth and pw_stealth:
            pw_stealth(page)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_load_state(wait_state, timeout=max(1000, (timeout - 3) * 1000))
        except Exception:
            pass

        # Try to open description/details if present (limit 'more' clicks to 2)
        clicks = 0
        for sel in [
            "button:has-text('더보기')",
            "text=상세보기",
            "button:has-text('Show More')",
            "text=Show more",
            "text=Description",
            "text=상품 설명",
            "text=상세",
            "[data-spm*='desc']",
            "a[href*='description']",
        ]:
            if clicks >= 2:
                break
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=1500)
                    clicks += 1
                    page.wait_for_timeout(400)
            except Exception:
                continue

        # Gradual scroll to trigger lazy images
        for i in range(max(1, scrolls)):
            try:
                page.evaluate("(step) => { window.scrollTo(0, document.body.scrollHeight * step); }", (i + 1) / max(1, scrolls))
            except Exception:
                pass
            page.wait_for_timeout(int(delay * 1000))

        # Collect image URLs (filter by size and keywords)
        js = """
        (function(){
          const urls = new Set();
          function pickFromSrcset(srcset){
            if(!srcset) return null;
            try {
              const parts = srcset.split(',').map(s=>s.trim());
              const last = parts[parts.length-1] || parts[0];
              const u = (last.split(' ')||[])[0];
              return u || null;
            } catch(e){ return null; }
          }
          const imgs = Array.from(document.querySelectorAll('img'));
          for(const img of imgs){
            const rect = img.getBoundingClientRect();
            const w = Math.max(img.naturalWidth||0, rect.width||0);
            const h = Math.max(img.naturalHeight||0, rect.height||0);
            if(w < 120 || h < 120) continue;
            let u = img.currentSrc || img.src || img.getAttribute('data-src') || img.getAttribute('data-image') || img.getAttribute('data-original') || pickFromSrcset(img.getAttribute('srcset'));
            if(!u) continue;
            if(u.startsWith('data:')) continue;
            if(/sprite|icon|logo|blank|placeholder/i.test(u)) continue;
            if(u.startsWith('//')) u = 'https:' + u;
            urls.add(u);
          }
          const title = (document.querySelector('h1')||{}).textContent || document.title || '';
          return {title: title.trim(), urls: Array.from(urls)};
        })()
        """
        data = page.evaluate(js)
        urls = list(data.get("urls") or [])
        title = (data.get("title") or "").strip() or None

        ctx.close()
        browser.close()
    return title, urls


def fetch_detail_only_playwright(url: str, timeout: int = 45, use_stealth: bool = True, mobile: bool = True,
                                 wait_state: str = "networkidle"):
    """Open URL, click a single 'more/description' control, then extract images and text ONLY from
    the product description/detail container.

    Returns: (title, desc_text, image_urls, overview_lines)
    """
    try:
        from playwright.sync_api import sync_playwright
        try:
            from playwright_stealth import stealth_sync as pw_stealth
        except Exception:
            pw_stealth = None
    except Exception as e:
        raise RuntimeError("Playwright not installed") from e

    title: str | None = None
    desc_text: str | None = None
    urls: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ua_mobile = "Mozilla/5.0 (Linux; Android 13; SM-G998N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context_args = {
            "locale": "ko-KR",
            "ignore_https_errors": True,
            "user_agent": ua_mobile if mobile else ua_desktop,
            "extra_http_headers": {
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        }
        ctx = browser.new_context(**context_args)
        page = ctx.new_page()
        if use_stealth and pw_stealth:
            pw_stealth(page)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_load_state(wait_state, timeout=max(1000, (timeout - 3) * 1000))
        except Exception:
            pass

        # Click only once on a likely 'more/description' control
        for sel in [
            "button:has-text('더보기')",
            "text=상세보기",
            "button:has-text('Show More')",
            "text=Description",
            "text=상품 설명",
            "text=상세",
            "[data-spm*='desc']",
            "a[href*='description']",
        ]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=1500)
                    page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        # Attempt to locate a description container
        container = None
        for sel in [
            "div.detail-desc-decorate",
            "div.product-description",
            "div.detail-desc",
            "div#product-description",
            "div#product-detail",
            "div[id*='product-description']",
            "div[id*='description']",
            "div[class*='product-detail']",
        ]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    container = loc.first
                    break
            except Exception:
                continue

        # Evaluate inside container
        if container and container.count() > 0:
            data = container.evaluate("(el)=>{\n                const urls = new Set();\n                const pickFromSrcset = (srcset)=>{\n                  if(!srcset) return null;\n                  try{ const parts = srcset.split(',').map(s=>s.trim());\n                        const last = parts[parts.length-1]||parts[0];\n                        return (last.split(' ')||[])[0]||null; }catch(e){return null;}\n                };\n                const imgs = el.querySelectorAll('img');\n                for(const img of imgs){\n                  const rect = img.getBoundingClientRect();\n                  const w = Math.max(img.naturalWidth||0, rect.width||0);\n                  const h = Math.max(img.naturalHeight||0, rect.height||0);\n                  if(w < 120 || h < 120) continue;\n                  let u = img.currentSrc || img.src || img.getAttribute('data-src') || img.getAttribute('data-image') || img.getAttribute('data-original') || pickFromSrcset(img.getAttribute('srcset'));\n                  if(!u) continue;\n                  if(u.startsWith('data:')) continue;\n                  if(/sprite|icon|logo|blank|placeholder/i.test(u)) continue;\n                  if(u.startsWith('//')) u = 'https:' + u;\n                  urls.add(u);\n                }\n                const text = el.innerText || '';\n                return { urls: Array.from(urls), text: text.trim() };\n            }")
            urls = list(data.get("urls") or [])
            desc_text = (data.get("text") or "").strip() or None
            try:
                data2 = container.evaluate("(el)=>{\n                  // Prefer collecting content under a heading containing '개요' until the first image\n                  function splitLines(s){ if(!s) return []; return s.split(/[•\\n\\.\\|\u30fb\u00b7\-–·]+/).map(x=>x.trim()).filter(x=>x.length>=6 && x.length<=120); }\n                  function hasImg(node){ try { return !!node.querySelector('img'); } catch(e){ return false; } }\n                  function findGaeYoHeading(root){\n                    const heads = root.querySelectorAll('h1,h2,h3,h4,h5,h6,.title--title--O6xcB1q');\n                    for(const h of heads){\n                      const t = (h.textContent||'').trim();\n                      if(t.includes('개요')) return h;\n                    }\n                    return null;\n                  }\n                  let lines = [];\n                  const h = findGaeYoHeading(el);\n                  if(h){\n                    let texts = [];\n                    let sib = h.nextSibling;\n                    while(sib){\n                      if(sib.nodeType === 1){ // ELEMENT_NODE\n                        const tag = sib.tagName ? sib.tagName.toLowerCase() : '' ;\n                        if(['h1','h2','h3','h4','h5','h6'].includes(tag)) break;\n                        if(hasImg(sib)) break;\n                        const t = (sib.innerText||'').trim();\n                        if(t) texts.push(t);\n                      } else if(sib.nodeType === 3){ // TEXT_NODE\n                        const t = (sib.textContent||'').trim();\n                        if(t) texts.push(t);\n                      }\n                      sib = sib.nextSibling;\n                    }\n                    lines = splitLines(texts.join('\n'));\n                  }\n                  if(!lines.length){\n                    // Fallback: collect before first image in the description container\n                    let overviewText = '';\n                    const walker = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT, null);\n                    let node;\n                    while((node = walker.nextNode())){\n                      const tag = (node.tagName||'').toLowerCase();\n                      if(tag === 'img') { break; }\n                      if(node.querySelector && node.querySelector('img')) { break; }\n                      if(['p','li','div','span','h1','h2','h3','h4','section'].includes(tag)) {\n                        const t = (node.innerText||'').trim();\n                        if(t) overviewText += (overviewText? '\\n' : '') + t;\n                      }\n                    }\n                    lines = splitLines(overviewText);\n                  }\n                  return { overview: lines };\n                }")
                overview_lines = list(data2.get('overview') or [])
            except Exception:
                overview_lines = []
        # Title from h1 or document
        try:
            title = page.evaluate("() => (document.querySelector('h1')?.textContent || document.title || '').trim()") or None
        except Exception:
            title = None

        ctx.close()
        browser.close()
    return title, desc_text, urls, (overview_lines if 'overview_lines' in locals() else [])


def fetch_overview_only_playwright(url: str, timeout: int = 45, use_stealth: bool = True, mobile: bool = True,
                                   wait_state: str = "networkidle") -> list[str]:
    """Extract only the overview lines under the '개요' title from AliExpress pages.

    Heuristics:
    - Locate description wrapper (class contains 'description--wrap').
    - Within it, find content root (#product-description or class contains 'product-description').
    - Collect text before the first image and split into short lines.
    """
    try:
        from playwright.sync_api import sync_playwright
        try:
            from playwright_stealth import stealth_sync as pw_stealth
        except Exception:
            pw_stealth = None
    except Exception as e:
        raise RuntimeError("Playwright not installed") from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ua_mobile = "Mozilla/5.0 (Linux; Android 13; SM-G998N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context_args = {
            "locale": "ko-KR",
            "ignore_https_errors": True,
            "user_agent": ua_mobile if mobile else ua_desktop,
            "extra_http_headers": {"Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"},
        }
        if mobile:
            context_args.update({
                "viewport": {"width": 375, "height": 667},
                "is_mobile": True,
                "device_scale_factor": 2,
            })
        ctx = p.chromium.new_context(**context_args)
        page = ctx.new_page()
        if use_stealth and pw_stealth:
            pw_stealth(page)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_load_state(wait_state, timeout=max(1000, (timeout - 3) * 1000))
        except Exception:
            pass
        for i in range(6):
            try:
                page.evaluate("(step) => { window.scrollTo(0, document.body.scrollHeight * step); }", (i + 1) / 6)
            except Exception:
                pass
            page.wait_for_timeout(500)
        # Try to open description if collapsed
        for sel in [
            "button:has-text('더보기')",
            "text=상세보기",
            "button:has-text('Show More')",
            "text=Description",
            "text=상품 설명",
            "text=상세",
        ]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=1500)
                    page.wait_for_timeout(400)
                    break
            except Exception:
                continue
        # Evaluate overview from description wrapper
        overview_lines: list[str] = []
        try:
            data = page.evaluate("""
            () => {
              function splitLines(s){ if(!s) return []; return s.split(/[•\n\.\|\u30fb\u00b7\-–·]+/).map(x=>x.trim()).filter(x=>x.length>=6 && x.length<=120); }
              function firstTextBeforeImage(root){
                let overviewText = '';
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null);
                let node;
                while((node = walker.nextNode())){
                  const tag = (node.tagName||'').toLowerCase();
                  if(tag === 'img') { break; }
                  if(node.querySelector && node.querySelector('img')) { break; }
                  if(['p','li','div','span','h1','h2','h3','h4','section'].includes(tag)) {
                    const t = (node.innerText||'').trim();
                    if(t) overviewText += (overviewText? '\n' : '') + t;
                  }
                }
                return overviewText;
              }
              const wrap = document.querySelector("div[class*='description--wrap']") || document.body;
              const content = wrap.querySelector('#product-description, [class*="product-description"]') || wrap;
              let block = firstTextBeforeImage(content);
              let lines = splitLines(block);
              if(!lines.length){
                // Fallback: gather first few text paragraphs/list items ignoring images
                const parts = [];
                const walkers = content.querySelectorAll('p, li, div');
                for(const el of walkers){
                  if(el.querySelector && el.querySelector('img')) continue;
                  const t = (el.innerText||'').trim();
                  if(t && t.length >= 6){ parts.push(t); }
                  if(parts.length >= 10) break;
                }
                lines = splitLines(parts.join('\n'));
              }
              return lines;
            }
            """)
            if isinstance(data, list):
                overview_lines = [str(x) for x in data if x]
        except Exception:
            overview_lines = []
        ctx.close()
        browser.close()
        return overview_lines


def fetch_specifications_playwright(url: str, timeout: int = 45, use_stealth: bool = True, mobile: bool = True,
                                    wait_state: str = "networkidle") -> list[str]:
    """Extract specification lines (key: value or bullet items) from product pages.

    Heuristics:
    - Look for elements with classes containing 'spec', 'product-props', 'specification'.
    - Extract table rows (th/td or td pairs) and list items.
    - Limit to reasonable line lengths to avoid noise.
    """
    try:
        from playwright.sync_api import sync_playwright
        try:
            from playwright_stealth import stealth_sync as pw_stealth
        except Exception:
            pw_stealth = None
    except Exception as e:
        raise RuntimeError("Playwright not installed") from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ua_mobile = "Mozilla/5.0 (Linux; Android 13; SM-G998N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        context_args = {
            "locale": "ko-KR",
            "ignore_https_errors": True,
            "user_agent": ua_mobile if mobile else ua_desktop,
            "extra_http_headers": {
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        }
        ctx = browser.new_context(**context_args)
        page = ctx.new_page()
        if use_stealth and pw_stealth:
            pw_stealth(page)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_load_state(wait_state, timeout=max(1000, (timeout - 3) * 1000))
        except Exception:
            pass

        # Click likely spec/detail toggles once to reveal content
        for sel in [
            "text=Specifications", "text=Specification", "text=스펙", "text=제품 스펙", "text=상품 스펙",
            "button:has-text('더보기')", "text=상세보기",
        ]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=1500)
                    page.wait_for_timeout(400)
                    break
            except Exception:
                continue

        js = """
        (function(){
          const out = [];
          const MAX = 48;
          function add(line){
            if(!line) return;
            const t = String(line).trim();
            if(t.length < 3 || t.length > 100) return;
            if(out.indexOf(t) === -1) out.push(t);
          }
          // Tables under spec-like containers
          const scopes = Array.from(document.querySelectorAll('[class*="spec"], [class*="product-prop"], [class*="product-spec"], [class*="specification"]'));
          for(const sc of scopes){
            // Rows
            const rows = sc.querySelectorAll('tr');
            for(const r of rows){
              const ths = r.querySelectorAll('th');
              const tds = r.querySelectorAll('td');
              if(ths.length && tds.length){
                for(let i=0;i<Math.min(ths.length, tds.length, MAX);i++){
                  const k = ths[i].innerText.trim();
                  const v = tds[i].innerText.trim();
                  if(k && v) add(k + ': ' + v);
                }
              } else if(tds.length >= 2){
                for(let i=0;i<tds.length-1 && i<MAX;i+=2){
                  const k = tds[i].innerText.trim();
                  const v = tds[i+1].innerText.trim();
                  if(k && v) add(k + ': ' + v);
                }
              } else {
                const t = r.innerText.trim();
                add(t);
              }
            }
            // List items
            const lis = sc.querySelectorAll('li');
            for(const li of lis){
              const t = li.innerText.trim();
              add(t);
            }
          }
          return out.slice(0, 40);
        })()
        """
        try:
            lines = page.evaluate(js)
        except Exception:
            lines = []

        ctx.close()
        browser.close()
    # Simple cleanup
    cleaned = []
    for ln in lines or []:
        s = " ".join((ln or "").split())
        if 3 <= len(s) <= 100 and s not in cleaned:
            cleaned.append(s)
    return cleaned[:40]


def parse_images_from_html(html: str, base_url: str, max_items: int = 8):
    soup = BeautifulSoup(html, "lxml")
    # Title (robust with Korean preference)
    candidates = []
    for sel in [
        "meta[property='og:title']",
        "meta[name='og:title']",
        "meta[name='title']",
        "meta[property='twitter:title']",
        "meta[name='twitter:title']",
        "meta[itemprop='name']",
    ]:
        m = soup.select_one(sel)
        if m and m.get("content"):
            t = (m.get("content") or "").strip()
            if t:
                candidates.append(t)
    if soup.title:
        t = soup.title.get_text(" ", strip=True)
        if t:
            candidates.append(t)
    h = soup.select_one("h1, h2, .product-title, .prod-buy-header__title")
    if h:
        t = h.get_text(" ", strip=True)
        if t:
            candidates.append(t)
    def _has_korean(s: str) -> bool:
        import re as _re
        return bool(_re.search(r"[가-힣]", s or ""))
    title = next((t for t in candidates if _has_korean(t)), (candidates[0] if candidates else None))

    urls = []
    # og:image first
    for m in soup.find_all("meta", property="og:image"):
        c = m.get("content")
        if c:
            urls.append(urljoin(base_url, c))
    # then all <img>
    for img in soup.select("img"):
        for k in ("src", "data-src", "data-img-src"):
            v = img.get(k)
            if v:
                urls.append(urljoin(base_url, v))
                break
    # dedup and filter http(s)
    seen = set()
    out = []
    for u in urls:
        if not (u.startswith("http://") or u.startswith("https://")):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= max_items:
            break
    return title, out


def parse_aliexpress_thumbnails_from_html(html: str) -> list[str]:
    """Extract AliExpress thumbnail URLs (summImagePathList) from inline DCData JSON if present.

    Returns a list of absolute URLs (as-is from the page). These are typically small (e.g., _80x80).
    """
    import re as _re
    thumbs: list[str] = []
    try:
        m = _re.search(r"DCData\s*=\s*(\{.*?\});", html, _re.S)
        if m:
            js = m.group(1)
            try:
                data = json.loads(js)
                lst = data.get("summImagePathList") or []
                if isinstance(lst, list):
                    for u in lst:
                        if isinstance(u, str) and u.startswith(("http://", "https://")):
                            thumbs.append(u)
            except Exception:
                pass
        if not thumbs:
            # Fallback: parse list literal
            m2 = _re.search(r'"summImagePathList"\s*:\s*\[(.*?)\]', html, _re.S)
            if m2:
                seg = m2.group(1)
                for mu in _re.finditer(r'"(https?://[^"]+)"', seg):
                    thumbs.append(mu.group(1))
    except Exception:
        pass
    # Deduplicate while preserving order
    seen = set()
    out: list[str] = []
    for u in thumbs:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def upgrade_aliexpress_image_url(u: str) -> str:
    """Attempt to convert AliExpress small/thumbnail URLs to higher-res originals.

    Heuristics:
    - Remove size suffixes like _80x80, _160x160, etc.
    - Collapse patterns like .jpg_80x80.jpg -> .jpg, .png_80x80.png -> .png
    - Convert .webp or .jpg_.webp -> .jpg
    """
    try:
        import re as _re
        s = u
        # Common WEBP → JPG cleanup
        s = s.replace('.jpg_.webp', '.jpg').replace('.png_.webp', '.png').replace('.webp', '.jpg')
        # Collapse duplicated extension patterns with size in between
        s = _re.sub(r"(\.jpe?g)_\d+x\d+\.jpe?g", r"\1", s)
        s = _re.sub(r"(\.png)_\d+x\d+\.png", r"\1", s)
        # Remove trailing _WxH before extension
        s = _re.sub(r"_\d+x\d+(?=\.jpe?g\b)", "", s)
        s = _re.sub(r"_\d+x\d+(?=\.png\b)", "", s)
        # Remove quality suffixes like _Q90
        s = _re.sub(r"_Q\d+", "", s)
        return s
    except Exception:
        return u


def parse_overview_from_html_static(html: str) -> list[str]:
    """Best-effort '개요' extraction from static HTML (no JS), AliExpress style.

    Looks for description wrapper and collects text until the first <img>.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        wrap = soup.find(lambda tag: getattr(tag, 'name', '') == 'div' and tag.has_attr('class') and any('description--wrap' in c for c in tag.get('class', [])))
        if not wrap:
            wrap = soup.select_one('#product-description, [class*="product-description"]')
        if not wrap:
            return []
        chunks: list[str] = []
        for child in wrap.children:
            try:
                nm = getattr(child, 'name', None)
                if nm == 'img' or (nm and child.find('img')):
                    break
                t = child.get_text("\n", strip=True) if getattr(child, 'get_text', None) else str(child).strip()
                if t:
                    chunks.append(t)
            except Exception:
                continue
        import re as _re
        lines = []
        for c in _re.split(r"[•\n\.\|\-–·]+", "\n".join(chunks)):
            cc = c.strip()
            if 6 <= len(cc) <= 160:
                lines.append(cc)
        return lines[:10]
    except Exception:
        return []


def parse_product_text_from_html(html: str):
    """Parse title, price, features from generic product-like HTML.

    - Title: og:title > <title>
    - Price: Won patterns like 49,900원 or ₩49,900; or common price selectors.
    - Features: Split og:description or list items.
    """
    soup = BeautifulSoup(html, "lxml")
    # Title (robust with Korean preference)
    candidates = []
    for sel in [
        "meta[property='og:title']",
        "meta[name='og:title']",
        "meta[name='title']",
        "meta[property='twitter:title']",
        "meta[name='twitter:title']",
        "meta[itemprop='name']",
    ]:
        m = soup.select_one(sel)
        if m and m.get("content"):
            t = (m.get("content") or "").strip()
            if t:
                candidates.append(t)
    if soup.title:
        t = soup.title.get_text(" ", strip=True)
        if t:
            candidates.append(t)
    h = soup.select_one("h1, h2, .product-title, .prod-buy-header__title")
    if h:
        t = h.get_text(" ", strip=True)
        if t:
            candidates.append(t)
    def _has_korean(s: str) -> bool:
        import re as _re
        return bool(_re.search(r"[가-힣]", s or ""))
    title = next((t for t in candidates if _has_korean(t)), (candidates[0] if candidates else None))

    # Price
    import re as _re
    text = soup.get_text("\n", strip=True)
    price = None
    m = _re.search(r"(?:₩|\b)[\s]*([0-9]{1,3}(?:,[0-9]{3})+)\s*원?", text)
    if m:
        price = m.group(0)
    if not price:
        for sel in [
            "span.total-price",
            "span.total-price > strong",
            "span.prod-sale-price > strong",
            "span.prod-price__price",
        ]:
            el = soup.select_one(sel)
            if el:
                price = el.get_text(" ", strip=True)
                break
        if not price:
            mp = soup.find("meta", attrs={"itemprop": "price"}) or soup.find("meta", attrs={"property": "og:product:price:amount"})
            if mp and mp.get("content"):
                price = mp["content"]

    # Features
    features = []
    # Prefer extracting overview under '개요' heading until first image/next heading
    try:
        heading = None
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            ttxt = (tag.get_text(" ", strip=True) or "").strip()
            if "개요" in ttxt:
                heading = tag
                break
        if heading is not None:
            buf = []
            for sib in heading.next_siblings:
                try:
                    nm = getattr(sib, "name", None)
                    if nm in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                        break
                    if nm and sib.find("img"):
                        break
                    txt = sib.get_text("\n", strip=True) if getattr(sib, "get_text", None) else str(sib).strip()
                    if txt:
                        buf.append(txt)
                except Exception:
                    continue
            joined = "\n".join(buf)
            import re as _re2
            for chunk in _re2.split(r"[•\n\.\|\-–·]+", joined):
                c = chunk.strip()
                if 6 <= len(c) <= 160:
                    features.append(c)
    except Exception:
        pass
    ogd = soup.select_one("meta[property='og:description'], meta[name='og:description'], meta[name='description'], meta[itemprop='description']")
    desc = ogd.get("content").strip() if ogd and ogd.get("content") else ""
    for chunk in _re.split(r"[•\n\.\|]+", desc):
        c = chunk.strip()
        if 6 <= len(c) <= 120:
            features.append(c)
    if len(features) < 3:
        for li in soup.select("li"):
            t = li.get_text(" ", strip=True)
            if 6 <= len(t) <= 120:
                features.append(t)
            if len(features) >= 6:
                break
    # Dedup and limit
    dedup = []
    for f in features:
        if f not in dedup:
            dedup.append(f)
    features = dedup[:5] if dedup else []
    return title, price, features


def detect_site(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return "auto"
    if "coupang.com" in host:
        return "coupang"
    if any(h in host for h in ["aliexpress.com", "ali.com", "alibaba.com", "aliexpress"]):
        return "aliexpress"
    return "auto"


def refine_features(features):
    out = []
    for f in features or []:
        f = " ".join(f.split())  # normalize spaces
        try:
            import re as _re
            f = _re.sub(r"^[\s\-•\*·–—]+", "", f)
            # Skip obvious spec label lines like "사양:", "이름:", "소재:" etc.
            if _re.match(r"^[A-Za-z가-힣]{1,10}\s*[:：]", f):
                continue
        except Exception:
            pass
        if not (6 <= len(f) <= 120):
            continue
        if f not in out:
            out.append(f)
        if len(out) >= 5:
            break
    return out


def convert_price_to_krw(price: str, usd: float = 1350.0, eur: float = 1450.0, jpy: float = 9.5, cny: float = 190.0):
    import re as _re
    if not price:
        return price
    s = price.strip()
    # Detect currency and amount
    sym = None
    if s.startswith("$") or "USD" in s.upper():
        sym = "USD"
    elif s.startswith("€") or "EUR" in s.upper():
        sym = "EUR"
    elif s.startswith("¥") or "JPY" in s.upper():
        sym = "JPY"
    elif s.startswith("¥") or "CNY" in s.upper() or "RMB" in s.upper():
        sym = "CNY"
    # Extract number
    m = _re.search(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", s)
    if not sym or not m:
        return price
    amt = float(m.group(1).replace(",", ""))
    rate = {"USD": usd, "EUR": eur, "JPY": jpy, "CNY": cny}.get(sym)
    if not rate:
        return price
    krw = int(round(amt * rate, 0))
    # format with thousands
    krw_str = f"{krw:,}원"
    return f"약 {krw_str}"


def download_images(urls, subdir="images_fetch"):
    paths = []
    os.makedirs(os.path.join(UPLOAD_DIR, subdir), exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 Chrome/124.0"}
    for i, u in enumerate(urls, 1):
        try:
            r = requests.get(u, headers=headers, timeout=20)
            r.raise_for_status()
            ext = ".jpg"
            ct = r.headers.get("content-type", "").lower()
            if "png" in ct:
                ext = ".png"
            fn = os.path.join(UPLOAD_DIR, subdir, f"fetched_{int(time.time()*1000)}_{i}{ext}")
            with open(fn, "wb") as f:
                f.write(r.content)
            paths.append(fn)
        except Exception:
            continue
    return paths


def download_thumbnails(urls, subdir="images_thumbs"):
    """Download small thumbnail images to a separate folder.

    Same behavior as download_images but keeps files under a different subdir for clarity.
    """
    return download_images(urls, subdir=subdir)


def generate_script_text(title: str | None, price: str | None, features: list[str] | None, cta: str | None) -> str:
    """Create a simple Korean narration script from inputs.

    Builds: hook line, up to 4 bullet features, optional price line, CTA.
    """
    lines: list[str] = []
    if title:
        lines.append(f"{title} — 이 가격에 이 구성?" if price else f"{title} — 핵심만 30초 요약!")
    for f in (features or [])[:4]:
        f = (f or '').strip()
        if f:
            lines.append(f"• {f}")
    if price:
        lines.append(f"가격: {price}")
    if cta:
        lines.append(cta)
    return "\n".join(lines)


def render_script_from_template(tpl: str, title: str | None, price: str | None, features: list[str] | None, cta: str | None) -> str:
    """Render a script using a simple placeholder template.

    Supported placeholders:
    - {title}, {price}, {cta}
    - {price_line} → "가격: {price}" if price exists, else empty
    - {features_bullets} → join features as lines beginning with •
    - {features_numbers} → join features as lines beginning with 1., 2., …
    """
    feats = features or []
    bullets = "\n".join([f"• {f}" for f in feats if f])
    numbers = "\n".join([f"{i+1}. {f}" for i, f in enumerate(feats) if f])
    price_line = f"가격: {price}" if (price and str(price).strip()) else ""
    mapping = {
        "title": title or "",
        "price": price or "",
        "cta": cta or "",
        "price_line": price_line,
        "features_bullets": bullets,
        "features_numbers": numbers,
    }
    out = tpl
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def ai_generate_script(title: str, price: str, features: list[str], cta: str, template: str) -> str | None:
    """Call OpenAI Chat Completions to generate a Korean script.

    Requires OPENAI_API_KEY env var. Optional OPENAI_MODEL (default: gpt-4o-mini).
    """
    # Reset last error holder
    try:
        st.session_state["ai_last_error"] = None
    except Exception:
        pass
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        try:
            st.session_state["ai_last_error"] = "OPENAI_API_KEY가 설정되어 있지 않습니다 (.env 또는 환경변수 확인)."
        except Exception:
            pass
        return None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    try:
        import requests as _rq
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        sys_prompt = (
            "You are a Korean copywriter for short-form product videos. "
            "Given title/price/features and a template with placeholders, "
            "produce a concise script in Korean suitable for TTS. Return ONLY the final script text."
        )
        user_payload = {
            "title": title,
            "price": price,
            "features": features,
            "cta": cta,
            "template": template,
            "instructions": "Fill placeholders in the template. Keep to 4-6 short lines."
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.7,
        }
        resp = _rq.post(f"{base}/chat/completions", headers=headers, json=data, timeout=45)
        if resp.status_code != 200:
            # Try to extract detailed error message
            err_msg = f"OpenAI 오류 {resp.status_code}"
            try:
                j = resp.json()
                em = (j.get("error") or {}).get("message") or j.get("message")
                if em:
                    err_msg += f": {em}"
            except Exception:
                txt = (resp.text or "").strip()
                if txt:
                    err_msg += f": {txt[:300]}"
            try:
                st.session_state["ai_last_error"] = f"{err_msg} (model={model}, base={base})"
            except Exception:
                pass
            return None
        js = resp.json()
        content = ((js.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not (content or "").strip():
            try:
                st.session_state["ai_last_error"] = "OpenAI 응답에 본문이 없습니다 (choices[0].message.content 비어있음)."
            except Exception:
                pass
            return None
        return content
    except Exception as e:
        try:
            st.session_state["ai_last_error"] = f"요청 중 예외: {type(e).__name__}: {e}"
        except Exception:
            pass
        return None


def build_template_json_if_applied(apply_tpl: bool) -> str | None:
    if not apply_tpl:
        return None
    data = {
        "header": st.session_state.get("tpl_header", ""),
        "subheader": st.session_state.get("tpl_subheader", ""),
        "footer": st.session_state.get("tpl_footer", ""),
        "cta_label": st.session_state.get("tpl_cta", "제품 보기"),
        "profile_name": st.session_state.get("tpl_profile", "@channel"),
        "theme_color": [
            int(st.session_state.get("tpl_color", "#10997F")[1:3], 16),
            int(st.session_state.get("tpl_color", "#10997F")[3:5], 16),
            int(st.session_state.get("tpl_color", "#10997F")[5:7], 16),
        ],
        "bar_height": st.session_state.get("tpl_bar", 90),
        "card_height": st.session_state.get("tpl_card", 280),
        "pill": {
            "x": st.session_state.get("tpl_pill_x", 24),
            "y": st.session_state.get("tpl_pill_y", 1700),
            "w": st.session_state.get("tpl_pill_w", 200),
            "h": st.session_state.get("tpl_pill_h", 64),
        },
        "profile_x": st.session_state.get("tpl_prof_x", 24),
        "profile_offset": st.session_state.get("tpl_prof_off", 18),
        "font_sizes": {
            "hdr": st.session_state.get("tpl_size_hdr", 40),
            "title": st.session_state.get("tpl_size_title", 56),
            "mid": st.session_state.get("tpl_size_mid", 54),
            "cta": st.session_state.get("tpl_size_cta", 32),
            "prof": st.session_state.get("tpl_size_prof", 30),
            "foot": st.session_state.get("tpl_size_foot", 28),
        },
    }
    # if all fields empty and default profile/cta, avoid applying template
    if not any([data["header"], data["subheader"], data["footer"], data["cta_label"], data["profile_name"]]):
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"template_{int(time.time()*1000)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def make_template_preview_image(caption: str | None = None, bg_path: str | None = None):
    """Render a quick template preview image using shorts_maker2 overlay logic.

    - Uses current Template inputs from session_state.
    - If bg_path is None, draws a simple dark gradient background.
    """
    try:
        from shorts_maker2 import TemplateConfig, _make_template_overlay, W as VID_W, H as VID_H
    except Exception:
        # Fallback sizes if import fails
        from PIL import Image
        VID_W, VID_H = 1080, 1920
        im = Image.new("RGB", (VID_W, VID_H), (18, 18, 18))
        return im

    # Build template config from current UI values
    hexcol = st.session_state.get("tpl_color", "#10997F")
    theme_tuple = (
        int(hexcol[1:3], 16), int(hexcol[3:5], 16), int(hexcol[5:7], 16)
    )
    tpl = TemplateConfig(
        header=st.session_state.get("tpl_header", ""),
        subheader=st.session_state.get("tpl_subheader", ""),
        footer=st.session_state.get("tpl_footer", ""),
        cta_label=st.session_state.get("tpl_cta", "제품 보기"),
        profile_name=st.session_state.get("tpl_profile", "@channel"),
        theme_color=theme_tuple,
        avatar_path=st.session_state.get("tpl_avatar_path"),
        bar_height=int(st.session_state.get("tpl_bar", 90)),
        card_height=int(st.session_state.get("tpl_card", 280)),
        pill_x=int(st.session_state.get("tpl_pill_x", 24)),
        pill_y=int(st.session_state.get("tpl_pill_y", 1700)),
        pill_w=int(st.session_state.get("tpl_pill_w", 200)),
        pill_h=int(st.session_state.get("tpl_pill_h", 64)),
        profile_x=int(st.session_state.get("tpl_prof_x", 24)),
        profile_y_offset=int(st.session_state.get("tpl_prof_off", 18)),
        hdr_size=int(st.session_state.get("tpl_size_hdr", 40)),
        title_size=int(st.session_state.get("tpl_size_title", 56)),
        mid_size=int(st.session_state.get("tpl_size_mid", 54)),
        cta_size=int(st.session_state.get("tpl_size_cta", 32)),
        prof_size=int(st.session_state.get("tpl_size_prof", 30)),
        foot_size=int(st.session_state.get("tpl_size_foot", 28)),
    )

    # Background
    from PIL import Image, ImageDraw
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert("RGB").resize((VID_W, VID_H))
        except Exception:
            bg = Image.new("RGB", (VID_W, VID_H), (18, 18, 18))
    else:
        # Simple dark gradient background
        bg = Image.new("RGB", (VID_W, VID_H), (18, 18, 18))
        dr = ImageDraw.Draw(bg)
        for i in range(VID_H):
            a = int(40 + 40 * (i / max(1, VID_H)))
            dr.line([(0, i), (VID_W, i)], fill=(a, a, a))

    overlay = _make_template_overlay(caption or "", tpl, font_path=st.session_state.get("font_path") or None)
    bg.paste(overlay, (0, 0), overlay)
    return bg


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    # Apply any pending ENV prefills BEFORE creating any widgets (sidebar, etc.)
    env_preset = st.session_state.get("env_prefill_dict")
    if isinstance(env_preset, dict) and env_preset:
        for k, v in env_preset.items():
            st.session_state[k] = v
        st.session_state.pop("env_prefill_dict", None)

    # Load UI prefs once per session (before creating the widgets that use these keys)
    if not st.session_state.get("_ui_prefs_loaded"):
        prefs = _load_ui_prefs()
        if isinstance(prefs, dict):
            for k, v in prefs.items():
                # Do not override if user already set something this session
                if k not in st.session_state:
                    st.session_state[k] = v
        st.session_state["_ui_prefs_loaded"] = True

    with st.sidebar:
        st.header("Global Options")
        default_out = f"out_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        out_name = st.text_input("Output filename", value=default_out, key="out_name")
        duration = st.slider("Duration (seconds)", 6, 60, st.session_state.get("duration", 24), 1, key="duration")
        min_slide = st.slider("Min slide (s)", 1.0, 6.0, st.session_state.get("min_slide", 2.0), 0.5, key="min_slide")
        max_slide = st.slider("Max slide (s)", 2.0, 8.0, st.session_state.get("max_slide", 5.0), 0.5, key="max_slide")
        font_path = st.text_input("Font path (optional)", value=st.session_state.get("font_path", ""), key="font_path")
        no_tts = st.checkbox("Disable TTS", value=st.session_state.get("no_tts", False), key="no_tts")
        voice_rate = st.number_input("Voice rate", min_value=120, max_value=240, value=st.session_state.get("voice_rate", 185), step=5, key="voice_rate")
        cta = st.text_input("CTA", value=st.session_state.get("cta", "더 알아보기는 링크 클릭!"), key="cta")
        music_file = st.file_uploader("Background music (mp3/wav)", type=["mp3", "wav"], key="music")
        apply_tpl = st.checkbox("Apply template overlay", value=st.session_state.get("apply_tpl", True), key="apply_tpl")
        st.markdown("---")
        st.caption("Price conversion to KRW (approx)")
        price_convert = st.checkbox("Convert price to KRW", value=st.session_state.get("price_convert", False), key="price_convert")
        colr1, colr2, colr3, colr4 = st.columns(4)
        with colr1:
            usd_rate = st.number_input("USD KRW", 800.0, 3000.0, st.session_state.get("rate_usd", 1350.0), 10.0, key="rate_usd")
        with colr2:
            eur_rate = st.number_input("EUR KRW", 900.0, 3000.0, st.session_state.get("rate_eur", 1450.0), 10.0, key="rate_eur")
        with colr3:
            jpy_rate = st.number_input("JPY KRW", 5.0, 20.0, st.session_state.get("rate_jpy", 9.5), 0.1, key="rate_jpy")
        with colr4:
            cny_rate = st.number_input("CNY KRW", 100.0, 400.0, st.session_state.get("rate_cny", 190.0), 5.0, key="rate_cny")

        st.markdown("---")
        st.caption("Save/Load environment (font/TTS/duration/KRW rates/template flag)")
        col_env1, col_env2 = st.columns(2)
        with col_env1:
            if st.button("Save Env JSON"):
                env = {
                    "font_path": st.session_state.get("font_path", ""),
                    "no_tts": st.session_state.get("no_tts", False),
                    "voice_rate": st.session_state.get("voice_rate", 185),
                    "cta": st.session_state.get("cta", "더 알아보기는 링크 클릭!"),
                    "apply_tpl": st.session_state.get("apply_tpl", True),
                    "price_convert": st.session_state.get("price_convert", False),
                    "rate_usd": st.session_state.get("rate_usd", 1350.0),
                    "rate_eur": st.session_state.get("rate_eur", 1450.0),
                    "rate_jpy": st.session_state.get("rate_jpy", 9.5),
                    "rate_cny": st.session_state.get("rate_cny", 190.0),
                    "duration": st.session_state.get("duration", 24),
                    "min_slide": st.session_state.get("min_slide", 2.0),
                    "max_slide": st.session_state.get("max_slide", 5.0),
                    # Optional preview/template helpers
                    "tpl_avatar_path": st.session_state.get("tpl_avatar_path"),
                    "tpl_preview_bg_path": st.session_state.get("tpl_preview_bg_path"),
                }
                st.download_button(
                    "Download env_config.json",
                    data=json.dumps(env, ensure_ascii=False, indent=2),
                    file_name="env_config.json",
                    mime="application/json",
                )
        with col_env2:
            env_up = st.file_uploader("Load Env JSON", type=["json"], key="env_json_upload")
            if env_up is not None:
                try:
                    js = json.loads(env_up.read().decode("utf-8"))
                    # Map loaded values directly to widget keys via prefill dict
                    prefill = {}
                    for k in [
                        "font_path","no_tts","voice_rate","cta","apply_tpl","price_convert",
                        "rate_usd","rate_eur","rate_jpy","rate_cny","duration","min_slide","max_slide",
                        "tpl_avatar_path","tpl_preview_bg_path",
                    ]:
                        if k in js:
                            prefill[k] = js[k]
                    st.session_state["env_prefill_dict"] = prefill
                    st.success("Environment loaded; applying settings…")
                    try:
                        st.rerun()
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Failed to load env: {e}")

        # Integrated save/load: environment + template in one JSON
        st.markdown("---")
        st.caption("Save/Load ALL (Env + Template)")
        col_all1, col_all2 = st.columns(2)
        with col_all1:
            if st.button("Save All JSON"):
                # Env part (reuse values above)
                env = {
                    "font_path": st.session_state.get("font_path", ""),
                    "no_tts": st.session_state.get("no_tts", False),
                    "voice_rate": st.session_state.get("voice_rate", 185),
                    "cta": st.session_state.get("cta", "더 알아보기는 링크 클릭!"),
                    "apply_tpl": st.session_state.get("apply_tpl", True),
                    "price_convert": st.session_state.get("price_convert", False),
                    "rate_usd": st.session_state.get("rate_usd", 1350.0),
                    "rate_eur": st.session_state.get("rate_eur", 1450.0),
                    "rate_jpy": st.session_state.get("rate_jpy", 9.5),
                    "rate_cny": st.session_state.get("rate_cny", 190.0),
                    "duration": st.session_state.get("duration", 24),
                    "min_slide": st.session_state.get("min_slide", 2.0),
                    "max_slide": st.session_state.get("max_slide", 5.0),
                    "tpl_avatar_path": st.session_state.get("tpl_avatar_path"),
                    "tpl_preview_bg_path": st.session_state.get("tpl_preview_bg_path"),
                }
                # Template part
                def _hex_to_rgb_tuple(hx: str):
                    hx = (hx or "#10997F").lstrip('#')
                    try:
                        return [int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16)]
                    except Exception:
                        return [16,153,127]
                template = {
                    "header": st.session_state.get("tpl_header", ""),
                    "subheader": st.session_state.get("tpl_subheader", ""),
                    "footer": st.session_state.get("tpl_footer", ""),
                    "cta_label": st.session_state.get("tpl_cta", "제품 보기"),
                    "profile_name": st.session_state.get("tpl_profile", "@channel"),
                    "theme_color": _hex_to_rgb_tuple(st.session_state.get("tpl_color", "#10997F")),
                    "bar_height": st.session_state.get("tpl_bar", 90),
                    "card_height": st.session_state.get("tpl_card", 280),
                    "pill": {
                        "x": st.session_state.get("tpl_pill_x", 24),
                        "y": st.session_state.get("tpl_pill_y", 1700),
                        "w": st.session_state.get("tpl_pill_w", 200),
                        "h": st.session_state.get("tpl_pill_h", 64),
                    },
                    "profile_x": st.session_state.get("tpl_prof_x", 24),
                    "profile_offset": st.session_state.get("tpl_prof_off", 18),
                    "font_sizes": {
                        "hdr": st.session_state.get("tpl_size_hdr", 40),
                        "title": st.session_state.get("tpl_size_title", 56),
                        "mid": st.session_state.get("tpl_size_mid", 54),
                        "cta": st.session_state.get("tpl_size_cta", 32),
                        "prof": st.session_state.get("tpl_size_prof", 30),
                        "foot": st.session_state.get("tpl_size_foot", 28),
                    },
                }
                # Scripts part (Images + PDF)
                try:
                    imgs_feats = [l.strip() for l in (st.session_state.get("features_images", "") or "").splitlines() if l.strip()]
                except Exception:
                    imgs_feats = []
                try:
                    pdf_feats = [l.strip() for l in (st.session_state.get("features_pdf", "") or "").splitlines() if l.strip()]
                except Exception:
                    pdf_feats = []
                scripts = {
                    "images": {
                        "title": st.session_state.get("title_images", ""),
                        "price": st.session_state.get("price_images", ""),
                        "features": imgs_feats,
                        "cta": st.session_state.get("cta", "더 알아보기는 링크 클릭!"),
                        "script": st.session_state.get("script_images", ""),
                    },
                    "pdf": {
                        "title": st.session_state.get("title_pdf", ""),
                        "price": st.session_state.get("price_pdf", ""),
                        "features": pdf_feats,
                        "cta": st.session_state.get("cta", "더 알아보기는 링크 클릭!"),
                        # If no explicit PDF script UI, generate based on current values for convenience
                        "script": generate_script_text(
                            st.session_state.get("title_pdf"),
                            st.session_state.get("price_pdf"),
                            pdf_feats,
                            st.session_state.get("cta") or "더 알아보기는 링크 클릭!",
                        ),
                    },
                }
                # Script templates (currently Images only)
                script_templates = {
                    "images": st.session_state.get("script_template_images", "{title} — 핵심만 30초 요약!\n{features_bullets}\n{price_line}\n{cta}")
                }
                all_data = {"env": env, "template": template, "scripts": scripts, "script_templates": script_templates}
                st.download_button(
                    "Download all_config.json",
                    data=json.dumps(all_data, ensure_ascii=False, indent=2),
                    file_name="all_config.json",
                    mime="application/json",
                )
        with col_all2:
            all_up = st.file_uploader("Load All JSON", type=["json"], key="all_json_upload")
            if all_up is not None and not st.session_state.get("_all_json_loaded_once"):
                try:
                    js = json.loads(all_up.read().decode("utf-8"))
                    # Env apply via prefill
                    if isinstance(js.get("env"), dict):
                        st.session_state["env_prefill_dict"] = js["env"]
                    # Template apply via prefill keys
                    if isinstance(js.get("template"), dict):
                        tp = js["template"]
                        st.session_state["tpl_header_prefill"] = tp.get("header", "")
                        st.session_state["tpl_subheader_prefill"] = tp.get("subheader", "")
                        st.session_state["tpl_footer_prefill"] = tp.get("footer", "")
                        st.session_state["tpl_cta_prefill"] = tp.get("cta_label", "제품 보기")
                        st.session_state["tpl_profile_prefill"] = tp.get("profile_name", "@channel")
                        col = tp.get("theme_color") or [16,153,127]
                        st.session_state["tpl_color_prefill"] = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                        # Advanced
                        st.session_state["tpl_bar_prefill"] = tp.get("bar_height", 90)
                        st.session_state["tpl_card_prefill"] = tp.get("card_height", 280)
                        pill = tp.get("pill") or {"x":24, "y":1700, "w":200, "h":64}
                        st.session_state["tpl_pill_x_prefill"] = pill.get("x", 24)
                        st.session_state["tpl_pill_y_prefill"] = pill.get("y", 1700)
                        st.session_state["tpl_pill_w_prefill"] = pill.get("w", 200)
                        st.session_state["tpl_pill_h_prefill"] = pill.get("h", 64)
                        st.session_state["tpl_prof_x_prefill"] = tp.get("profile_x", 24)
                        st.session_state["tpl_prof_off_prefill"] = tp.get("profile_offset", 18)
                        fs = tp.get("font_sizes") or {}
                        st.session_state["tpl_size_hdr_prefill"] = fs.get("hdr", 40)
                        st.session_state["tpl_size_title_prefill"] = fs.get("title", 56)
                        st.session_state["tpl_size_mid_prefill"] = fs.get("mid", 54)
                        st.session_state["tpl_size_cta_prefill"] = fs.get("cta", 32)
                        st.session_state["tpl_size_prof_prefill"] = fs.get("prof", 30)
                        st.session_state["tpl_size_foot_prefill"] = fs.get("foot", 28)
                        st.session_state["tpl_prefill_pending"] = True
                    # Scripts apply via prefill keys
                    sc = js.get("scripts") or {}
                    if isinstance(sc.get("images"), dict):
                        si = sc["images"]
                        if si.get("title"):
                            st.session_state["title_images_prefill"] = si.get("title")
                        if si.get("price"):
                            st.session_state["price_images_prefill"] = si.get("price")
                        if isinstance(si.get("features"), list):
                            st.session_state["features_images_prefill"] = "\n".join(si.get("features"))
                        if si.get("script"):
                            st.session_state["script_images_prefill"] = si.get("script")
                        st.session_state["images_prefill_pending"] = True
                    if isinstance(sc.get("pdf"), dict):
                        sp = sc["pdf"]
                        if sp.get("title"):
                            st.session_state["title_pdf_prefill"] = sp.get("title")
                        if sp.get("price"):
                            st.session_state["price_pdf_prefill"] = sp.get("price")
                        if isinstance(sp.get("features"), list):
                            st.session_state["features_pdf_prefill"] = "\n".join(sp.get("features"))
                        st.session_state["pdf_prefill_pending"] = True
                    # Script templates apply
                    stpl = js.get("script_templates") or {}
                    if isinstance(stpl.get("images"), str):
                        st.session_state["script_template_images_prefill"] = stpl.get("images")
                        st.session_state["images_prefill_pending"] = True
                    st.success("All settings loaded; applying…")
                    # Prevent repeat processing and let prefills apply in this same run
                    try:
                        st.session_state["all_json_upload"] = None
                        st.session_state["_all_json_loaded_once"] = True
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Failed to load all: {e}")

    # Unify to use shorts_maker2.py only
    tab1, tab2, tab3 = st.tabs(["Images", "PDF", "Template"])

    with tab1:
        st.subheader("Images → MP4 (shorts_maker2.py)")
        imgs = st.file_uploader(
            "Upload images (2+ recommended)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="images_images_upload",
        )
        # Apply any pending prefill values BEFORE creating widgets to avoid Streamlit key-lock errors
        if st.session_state.get("images_prefill_pending"):
            if "title_images_prefill" in st.session_state:
                st.session_state["title_images"] = st.session_state.pop("title_images_prefill")
            if "price_images_prefill" in st.session_state:
                st.session_state["price_images"] = st.session_state.pop("price_images_prefill")
            if "features_images_prefill" in st.session_state:
                st.session_state["features_images"] = st.session_state.pop("features_images_prefill")
            if "script_images_prefill" in st.session_state:
                st.session_state["script_images"] = st.session_state.pop("script_images_prefill")
            # Apply last-source marker if provided
            if "script_last_source_prefill" in st.session_state:
                st.session_state["script_last_source"] = st.session_state.pop("script_last_source_prefill")
            if "script_template_images_prefill" in st.session_state:
                st.session_state["script_template_images"] = st.session_state.pop("script_template_images_prefill")
            st.session_state["images_prefill_pending"] = False
        title2 = st.text_input("Title", value="", key="title_images")
        price2 = st.text_input("Price", value="", key="price_images")
        feats2 = st.text_area("Features (one per line)", key="features_images")
        script2 = st.text_area("대본 (자동 생성/수정 가능)", key="script_images", height=160)
        # Show script status and last error if any
        last_src = st.session_state.get("script_last_source")
        if last_src:
            src_label = {"ai": "AI", "template": "Template", "prefill": "Prefill", "ai_error": "AI 실패"}.get(last_src, str(last_src))
            st.caption(f"Script source: {src_label}")
        err = st.session_state.get("ai_last_error")
        if err:
            st.error(err)
        elif not (script2 or "").strip():
            st.info("아직 대본이 없습니다. '현재 값으로 대본 생성' 또는 'AI에게 요청하기'를 눌러 생성하세요.")

        # Show/manage fetched images with selection checkboxes
        fetched = st.session_state.get("images_fetched_paths") or []
        thumbs = st.session_state.get("images_thumbs_paths") or []
        if fetched:
            st.caption(f"Fetched images ready: {len(fetched)} files")
            # Selection state dict: path -> bool
            sel_state = st.session_state.get("images_sel_state") or {}
            # Default new items to True
            for p in fetched:
                if p not in sel_state:
                    sel_state[p] = True
            st.session_state["images_sel_state"] = sel_state

            # Controls: use selected only, select all/none, clear/add/remove
            col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([1,1,1,2])
            with col_ctrl1:
                use_selected_only = st.checkbox(
                    "Use selected only",
                    value=st.session_state.get("images_use_selected_only", True),
                    key="images_use_selected_only",
                    on_change=_save_ui_prefs,
                )
            with col_ctrl2:
                if st.button("Select all"):
                    for p in list(sel_state.keys()):
                        sel_state[p] = True
                    st.session_state["images_sel_state"] = sel_state
            with col_ctrl3:
                if st.button("Clear selection"):
                    for p in list(sel_state.keys()):
                        sel_state[p] = False
                    st.session_state["images_sel_state"] = sel_state
            with col_ctrl4:
                add_files = st.file_uploader(
                    "Add more fetched images",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key="images_fetch_add",
                )
                if add_files:
                    new_paths = []
                    for f in add_files:
                        try:
                            pth = save_uploaded_file(f, subdir="images")
                            if pth:
                                new_paths.append(pth)
                        except Exception:
                            continue
                    if new_paths:
                        cur = st.session_state.get("images_fetched_paths") or []
                        st.session_state["images_fetched_paths"] = cur + new_paths
                        for p in new_paths:
                            sel_state[p] = True
                        st.session_state["images_sel_state"] = sel_state
                        st.success(f"Added {len(new_paths)} images.")
                        try:
                            st.rerun()
                        except Exception:
                            pass

            # Render grid with checkboxes
            cols = st.columns(4)
            for i, p in enumerate(fetched):
                try:
                    with cols[i % 4]:
                        cap = f"image_{i+1}"
                        st.image(p, caption=cap, width=180)
                        h = hashlib.md5(p.encode("utf-8")).hexdigest()[:10]
                        checked = st.checkbox("select", value=sel_state.get(p, True), key=f"img_sel_{h}")
                        sel_state[p] = checked
                        col_ud1, col_ud2, col_ud3, col_ud4 = st.columns([1,1,1,1])
                        with col_ud1:
                            if st.button("↑", key=f"img_up_{h}") and i > 0:
                                # swap up
                                fetched[i-1], fetched[i] = fetched[i], fetched[i-1]
                                st.session_state["images_fetched_paths"] = fetched
                                try:
                                    st.rerun()
                                except Exception:
                                    pass
                        with col_ud2:
                            if st.button("↓", key=f"img_down_{h}") and i < len(fetched) - 1:
                                fetched[i+1], fetched[i] = fetched[i], fetched[i+1]
                                st.session_state["images_fetched_paths"] = fetched
                                try:
                                    st.rerun()
                                except Exception:
                                    pass
                        with col_ud3:
                            if st.button("↥", key=f"img_top_{h}") and i > 0:
                                itm = fetched.pop(i)
                                fetched.insert(0, itm)
                                st.session_state["images_fetched_paths"] = fetched
                                try:
                                    st.rerun()
                                except Exception:
                                    pass
                        with col_ud4:
                            if st.button("↧", key=f"img_bot_{h}") and i < len(fetched) - 1:
                                itm = fetched.pop(i)
                                fetched.append(itm)
                                st.session_state["images_fetched_paths"] = fetched
                                try:
                                    st.rerun()
                                except Exception:
                                    pass
                        # Per-image delete
                        if st.button("Delete", key=f"img_del_{h}"):
                            try:
                                if os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass
                            # remove from fetched and selection
                            fetched2 = [q for q in fetched if q != p]
                            st.session_state["images_fetched_paths"] = fetched2
                            sel_state.pop(p, None)
                            try:
                                st.rerun()
                            except Exception:
                                pass
                except Exception:
                    continue
            st.session_state["images_sel_state"] = sel_state
            selected = [p for p in fetched if sel_state.get(p, False)]
            st.session_state["images_selected_paths"] = selected
            st.caption(f"Selected: {len(selected)} / {len(fetched)}")

            # Remove selected / Clear all
            col_rm1, col_rm2 = st.columns([1,1])
            with col_rm1:
                if st.button("Remove selected") and selected:
                    keep = []
                    for pth in fetched:
                        if pth in selected:
                            try:
                                if os.path.exists(pth):
                                    os.remove(pth)
                            except Exception:
                                pass
                        else:
                            keep.append(pth)
                    st.session_state["images_fetched_paths"] = keep
                    # purge removed from selection state
                    for pth in selected:
                        sel_state.pop(pth, None)
                    st.session_state["images_sel_state"] = sel_state
                    try:
                        st.rerun()
                    except Exception:
                        pass
            with col_rm2:
                if st.button("Clear all"):
                    try:
                        for pth in fetched:
                            try:
                                if os.path.exists(pth):
                                    os.remove(pth)
                            except Exception:
                                pass
                    finally:
                        st.session_state.pop("images_fetched_paths", None)
                        st.session_state.pop("images_sel_state", None)
                        st.session_state.pop("images_selected_paths", None)
                        st.session_state.pop("images_thumbs_paths", None)
                        st.session_state.pop("images_thumbs_sel_state", None)
                        try:
                            st.rerun()
                        except Exception:
                            pass

        # Show thumbnails (if any)
        if thumbs:
            st.markdown("---")
            st.caption(f"Downloaded thumbnails: {len(thumbs)} files")

            # Selection state dict: path -> bool
            t_sel_state = st.session_state.get("images_thumbs_sel_state") or {}
            for p in thumbs:
                if p not in t_sel_state:
                    t_sel_state[p] = True
            st.session_state["images_thumbs_sel_state"] = t_sel_state

            # Controls for thumbnails
            col_t1, col_t2, col_t3, col_t4 = st.columns([1,1,1,1])
            with col_t1:
                if st.button("Select all thumbs"):
                    for p in list(t_sel_state.keys()):
                        t_sel_state[p] = True
                    st.session_state["images_thumbs_sel_state"] = t_sel_state
            with col_t2:
                if st.button("Clear selection (thumbs)"):
                    for p in list(t_sel_state.keys()):
                        t_sel_state[p] = False
                    st.session_state["images_thumbs_sel_state"] = t_sel_state
            with col_t3:
                if st.button("Remove selected thumbs"):
                    kept = []
                    for p in thumbs:
                        if t_sel_state.get(p, False):
                            try:
                                if os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass
                        else:
                            kept.append(p)
                    st.session_state["images_thumbs_paths"] = kept
                    # Purge removed keys
                    for p in list(t_sel_state.keys()):
                        if p not in kept:
                            t_sel_state.pop(p, None)
                    st.session_state["images_thumbs_sel_state"] = t_sel_state
                    try:
                        st.rerun()
                    except Exception:
                        pass
            with col_t4:
                if st.button("Clear all thumbs"):
                    try:
                        for p in thumbs:
                            try:
                                if os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass
                    finally:
                        st.session_state.pop("images_thumbs_paths", None)
                        st.session_state.pop("images_thumbs_sel_state", None)
                        try:
                            st.rerun()
                        except Exception:
                            pass

            # Render thumbnails grid with checkboxes
            cols_t = st.columns(6)
            for i, p in enumerate(thumbs):
                try:
                    with cols_t[i % 6]:
                        st.image(p, caption=f"thumb_{i+1}", width=120)
                        h = hashlib.md5(("thumb::" + p).encode("utf-8")).hexdigest()[:10]
                        checked = st.checkbox("select", value=t_sel_state.get(p, True), key=f"thumb_sel_{h}")
                        t_sel_state[p] = checked
                except Exception:
                    continue
            st.session_state["images_thumbs_sel_state"] = t_sel_state

        # Template editing moved to Template tab
        st.caption("Edit template in the Template tab. Current values will be applied.")

        st.markdown("---")
        st.caption("Optional: fetch images+text from a product URL and run with shorts_maker2.py")
        url_fetch = st.text_input("Fetch URL", key="images_fetch_url")
        auto_site = detect_site(url_fetch) if url_fetch else "auto"
        # Respect saved preference if present
        initial_site = st.session_state.get("images_fetch_site", auto_site)
        site_sel = st.selectbox(
            "Site",
            ["auto", "coupang", "aliexpress"],
            index=["auto","coupang","aliexpress"].index(initial_site if initial_site in ["auto","coupang","aliexpress"] else auto_site),
            key="images_fetch_site",
            on_change=_save_ui_prefs,
        )
        if url_fetch:
            st.caption(f"Detected: {auto_site}")
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            fetch_count = st.slider("Fetch count", 2, 10, int(st.session_state.get("images_fetch_count", 4)), 1, key="images_fetch_count", on_change=_save_ui_prefs)
            fetch_timeout = st.number_input("Timeout (s)", 5, 120, int(st.session_state.get("images_fetch_timeout", 30)), key="images_fetch_timeout", on_change=_save_ui_prefs)
        with colf2:
            use_playwright = st.checkbox("Playwright fallback", value=bool(st.session_state.get("images_fetch_pw", False)), key="images_fetch_pw", on_change=_save_ui_prefs)
            pw_stealth = st.checkbox("Stealth", value=bool(st.session_state.get("images_fetch_pw_stealth", True)), key="images_fetch_pw_stealth", on_change=_save_ui_prefs)
            deep_fetch = st.checkbox("Deep fetch (scroll/expand)", value=bool(st.session_state.get("images_fetch_deep", False)), key="images_fetch_deep", on_change=_save_ui_prefs)
            detail_only = st.checkbox("Detail-only images (1x 더보기)", value=bool(st.session_state.get("images_fetch_detail_only", False)), key="images_fetch_detail_only", on_change=_save_ui_prefs)
            prefer_overview = st.checkbox("Prefer '개요' for Features (AliExpress)", value=bool(st.session_state.get("images_prefer_overview", True)), key="images_prefer_overview", on_change=_save_ui_prefs)
        with colf3:
            pw_mobile = st.checkbox("Mobile", value=bool(st.session_state.get("images_fetch_pw_mobile", True)), key="images_fetch_pw_mobile", on_change=_save_ui_prefs)
            pw_wait = st.selectbox("Wait state", ["networkidle", "domcontentloaded", "load"], index=["networkidle","domcontentloaded","load"].index(st.session_state.get("images_fetch_pw_wait", "networkidle")), key="images_fetch_pw_wait", on_change=_save_ui_prefs)
            deep_scrolls = st.slider("Scroll passes", 3, 16, int(st.session_state.get("images_fetch_deep_scrolls", 8)), 1, key="images_fetch_deep_scrolls", on_change=_save_ui_prefs)
            thumbs_hq = st.checkbox("Hi-res thumbnails", value=bool(st.session_state.get("images_thumbs_hq", True)), key="images_thumbs_hq", on_change=_save_ui_prefs)

        # Optional: Use Selenium-based AliExpress fetcher (56.*) when site is AliExpress
        use_ali56 = False
        if site_sel == "aliexpress":
            use_ali56 = st.checkbox("Use AliExpress Selenium fetcher (56)", value=True, key="images_fetch_use_56")

        # Prefill controls: limit + button
        col_pf1, col_pf2, col_pf3 = st.columns([1,1,2])
        with col_pf1:
            prefill_limit = st.number_input(
                "Prefill images (count)", 1, 20,
                int(st.session_state.get("images_prefill_limit", int(st.session_state.get("images_fetch_count", 4)))),
                key="images_prefill_limit",
                on_change=_save_ui_prefs,
            )
        with col_pf2:
            parse_clicked = st.button("Parse URL ➜ Prefill fields", key="btn_parse_prefill")

        if parse_clicked:
            if not url_fetch:
                st.warning("Enter a URL first.")
            else:
                try:
                    html = fetch_html_requests(url_fetch, timeout=int(fetch_timeout))
                except Exception as e:
                    html = None
                    if use_playwright:
                        try:
                            html = fetch_html_playwright(url_fetch, timeout=int(fetch_timeout), use_stealth=pw_stealth, mobile=pw_mobile, wait_state=pw_wait)
                        except Exception as e2:
                            st.error(f"Fetch failed: {e2}")
                    else:
                        st.error(f"Fetch failed: {e}")
                if html:
                    prefill_limit = int(st.session_state.get("images_prefill_limit", int(st.session_state.get("images_fetch_count", 4))))
                    t_title, t_price, t_feats = parse_product_text_from_html(html)
                    # Prefer overview for AliExpress when enabled
                    overview_pref_lines: list[str] | None = None
                    if (st.session_state.get("images_prefer_overview", True) and site_sel == "aliexpress"):
                        # Try static first, then Playwright fallback
                        try:
                            tmp = parse_overview_from_html_static(html)
                        except Exception:
                            tmp = []
                        if tmp:
                            overview_pref_lines = tmp
                        elif use_playwright:
                            try:
                                overview_pref_lines = fetch_overview_only_playwright(
                                    url_fetch,
                                    timeout=int(fetch_timeout),
                                    use_stealth=pw_stealth,
                                    mobile=pw_mobile,
                                    wait_state=pw_wait,
                                ) or []
                            except Exception:
                                overview_pref_lines = None
                    # Download images either via Selenium 56, detail-only, deep fetch, or built-in
                    dpaths = []
                    desc_text = None
                    spec_lines: list[str] | None = None
                    # Detail-only branch (Playwright)
                    if use_playwright and detail_only:
                        try:
                            d_title, d_text, d_urls, d_overview = fetch_detail_only_playwright(
                                url_fetch,
                                timeout=int(fetch_timeout),
                                use_stealth=pw_stealth,
                                mobile=pw_mobile,
                                wait_state=pw_wait,
                            )
                            if d_title and not t_title:
                                t_title = d_title
                            if d_urls:
                                try:
                                    d_urls = d_urls[: int(prefill_limit)]
                                except Exception:
                                    pass
                                dpaths = download_images(d_urls)
                            desc_text = d_text
                            overview_lines = d_overview
                            # Fallback: if AliExpress and overview empty, try overview-only parser
                            if site_sel == "aliexpress" and (not overview_lines):
                                try:
                                    overview_lines = fetch_overview_only_playwright(
                                        url_fetch,
                                        timeout=int(fetch_timeout),
                                        use_stealth=pw_stealth,
                                        mobile=pw_mobile,
                                        wait_state=pw_wait,
                                    )
                                except Exception:
                                    pass
                            # Try to extract specification lines
                            try:
                                spec_lines = fetch_specifications_playwright(
                                    url_fetch,
                                    timeout=int(fetch_timeout),
                                    use_stealth=pw_stealth,
                                    mobile=pw_mobile,
                                    wait_state=pw_wait,
                                )
                            except Exception:
                                spec_lines = None
                        except Exception as e:
                            st.warning(f"Detail-only fetch failed: {e}")
                    # Thumbnails (AliExpress only) — try to extract and download
                    if site_sel == "aliexpress" and html:
                        try:
                            thumb_urls = parse_aliexpress_thumbnails_from_html(html)
                        except Exception:
                            thumb_urls = []
                        if thumb_urls:
                            if st.session_state.get("images_thumbs_hq", True):
                                try:
                                    thumb_urls = [upgrade_aliexpress_image_url(u) for u in thumb_urls]
                                except Exception:
                                    pass
                            dthumbs = download_thumbnails(thumb_urls)
                            if dthumbs:
                                curt = st.session_state.get("images_thumbs_paths") or []
                                st.session_state["images_thumbs_paths"] = curt + dthumbs
                    if site_sel == "aliexpress" and use_ali56:
                        try:
                            base_dir = os.path.join(UPLOAD_DIR, "aliexpress_downloads")
                            os.makedirs(base_dir, exist_ok=True)
                            st.info("Running AliExpress Selenium fetcher (headless)…")
                            cmd56 = [
                                os.path.basename(os.sys.executable),
                                "56.aliexpressmov1ok_pdfok.py",
                                "--url", url_fetch,
                                "--out_dir", base_dir,
                                "--headless",
                            ]
                            st.code(" ".join(shlex.quote(c) for c in cmd56))
                            code56, logs56, took56 = run_cmd(cmd56)
                            # Pick the most recent created folder under base_dir
                            latest_dir = None
                            try:
                                subs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
                                if subs:
                                    subs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                                    latest_dir = subs[0]
                            except Exception:
                                latest_dir = None
                            # Collect images from that folder
                            if latest_dir and os.path.isdir(latest_dir):
                                imgs = []
                                pdfs = []
                                for root, _dirs, files in os.walk(latest_dir):
                                    for fn in files:
                                        if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                                            imgs.append(os.path.join(root, fn))
                                        if fn.lower().endswith(".pdf"):
                                            pdfs.append(os.path.join(root, fn))
                                try:
                                    dpaths = imgs[: int(prefill_limit)]
                                except Exception:
                                    dpaths = imgs
                                if pdfs:
                                    st.session_state["pdf_fetched_paths"] = pdfs
                                    st.info(f"Saved {len(pdfs)} PDF file(s). Latest dir: {latest_dir}")
                                    # Show simple links and download buttons for PDFs
                                    for i, p in enumerate(pdfs[:4], 1):
                                        try:
                                            with open(p, "rb") as f:
                                                st.download_button(
                                                    label=f"Download PDF {i}: {os.path.basename(p)}",
                                                    data=f.read(),
                                                    file_name=os.path.basename(p),
                                                    mime="application/pdf",
                                                )
                                        except Exception:
                                            st.write(p)
                                # Try to use product_details.json for overview/description prefill
                                try:
                                    details_json = os.path.join(latest_dir, "product_details.json")
                                    if os.path.exists(details_json):
                                        with open(details_json, "r", encoding="utf-8") as jf:
                                            det = json.load(jf)
                                        overview_txt = (det.get("개요") or det.get("상세설명") or "").strip()
                                        if overview_txt:
                                            import re as _re
                                            parts = [_s.strip() for _s in _re.split(r"[•\n\.|\u2022]+", overview_txt) if 6 <= len(_s.strip()) <= 120]
                                            feat_from_overview = parts[:5]
                                            with st.expander("개요 텍스트 미리보기"):
                                                st.text(overview_txt[:1200] + ("…" if len(overview_txt) > 1200 else ""))
                                            if feat_from_overview:
                                                st.session_state["features_images_prefill"] = "\n".join(refine_features(feat_from_overview))
                                                # Re-generate script with these features
                                                tpl_default = "{title} — 핵심만 30초 요약!\n{features_bullets}\n{price_line}\n{cta}"
                                                cur_tpl = st.session_state.get("script_template_images", tpl_default)
                                                scr = render_script_from_template(
                                                    cur_tpl,
                                                    st.session_state.get("title_images", "") or (t_title or ""),
                                                    st.session_state.get("price_images", "") or (t_price or ""),
                                                    refine_features(feat_from_overview),
                                                    st.session_state.get("cta") or "더 알아보기는 링크 클릭!",
                                                )
                                                if scr:
                                                    st.session_state["script_images_prefill"] = scr
                                                st.session_state["images_prefill_pending"] = True
                                                st.info("product_details.json의 개요 텍스트로 필드를 업데이트했습니다.")
                                except Exception:
                                    pass
                            if not dpaths:
                                st.warning("Selenium fetcher finished but found no images; falling back to built-in parser.")
                        except Exception as e:
                            st.warning(f"AliExpress Selenium fetch failed: {e}")
                    if not dpaths:
                        # Built-in image URL parsing + download
                        img_urls = []
                        try:
                            if use_playwright and deep_fetch:
                                try:
                                    deep_title, deep_urls = fetch_images_playwright_deep(
                                        url_fetch,
                                        timeout=int(fetch_timeout),
                                        use_stealth=pw_stealth,
                                        mobile=pw_mobile,
                                        wait_state=pw_wait,
                                        scrolls=int(deep_scrolls),
                                    )
                                    if deep_title and not t_title:
                                        t_title = deep_title
                                    img_urls = deep_urls
                                except Exception as e:
                                    st.warning(f"Deep fetch failed; falling back: {e}")
                            if not img_urls:
                                if site_sel == "coupang":
                                    try:
                                        import parser_coupang as pc
                                        cp = pc.parse(html)
                                        img_urls = cp.images[: int(prefill_limit)]
                                    except Exception:
                                        _, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(prefill_limit))
                                elif site_sel == "aliexpress":
                                    try:
                                        import parser_aliexpress as pa
                                        ap = pa.parse(html)
                                        img_urls = ap.images[: int(prefill_limit)]
                                    except Exception:
                                        _, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(prefill_limit))
                                else:
                                    _, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(prefill_limit))
                        except Exception:
                            img_urls = []
                        if img_urls:
                            try:
                                img_urls = img_urls[: int(prefill_limit)]
                            except Exception:
                                pass
                            dpaths = download_images(img_urls)
                        else:
                            dpaths = []
                    if dpaths:
                        cur = st.session_state.get("images_fetched_paths") or []
                        st.session_state["images_fetched_paths"] = cur + dpaths
                    # Prefill features: prefer explicit preference > overview lines > specification lines > description lines
                    features_set = False
                    if overview_pref_lines:
                        st.session_state["features_images_prefill"] = "\n".join(refine_features(overview_pref_lines))
                        st.session_state["script_images_prefill"] = "\n".join(overview_pref_lines)
                        features_set = True
                    elif 'overview_lines' in locals() and overview_lines:
                        st.session_state["features_images_prefill"] = "\n".join(refine_features(overview_lines))
                        st.session_state["script_images_prefill"] = "\n".join(overview_lines)
                        features_set = True
                    elif spec_lines:
                        st.session_state["features_images_prefill"] = "\n".join(refine_features(spec_lines))
                        st.session_state["script_images_prefill"] = "\n".join(spec_lines)
                        features_set = True
                    elif desc_text:
                        try:
                            import re as _re
                            cand = [_s.strip() for _s in _re.split(r"[•\n\.\|\-–·]+", desc_text) if 6 <= len(_s.strip()) <= 120]
                        except Exception:
                            cand = []
                        if cand:
                            st.session_state["features_images_prefill"] = "\n".join(refine_features(cand))
                        st.session_state["script_images_prefill"] = desc_text
                        features_set = True
                    # Optional KRW conversion for display/script
                    if price_convert and t_price:
                        t_price_disp = convert_price_to_krw(t_price, usd=usd_rate, eur=eur_rate, jpy=jpy_rate, cny=cny_rate)
                    else:
                        t_price_disp = t_price
                    # Queue prefill updates and rerun so they apply before widgets instantiate
                    if t_title:
                        st.session_state["title_images_prefill"] = t_title
                    if t_price_disp:
                        st.session_state["price_images_prefill"] = t_price_disp
                    # If specification lines exist, keep them; otherwise fallback to generic t_feats
                    if t_feats and not spec_lines and not features_set:
                        st.session_state["features_images_prefill"] = "\n".join(t_feats)
                    # Generate a narration script from template (or fallback)
                    tpl_default = "{title} — 핵심만 30초 요약!\n{features_bullets}\n{price_line}\n{cta}"
                    cur_tpl = st.session_state.get("script_template_images", tpl_default)
                    scr = render_script_from_template(cur_tpl, t_title or "", t_price_disp or "", refine_features(t_feats or []), st.session_state.get("cta") or "더 알아보기는 링크 클릭!")
                    if scr:
                        st.session_state["script_images_prefill"] = scr
                        st.session_state["script_last_source_prefill"] = "prefill"
                    st.session_state["images_prefill_pending"] = True
                    st.success(f"Parsed content; downloaded {len(dpaths)} images; updating fields & script…")
                    try:
                        st.rerun()
                    except Exception:
                        pass

        if st.button("Fetch URL ➜ Run"):
            out_path = os.path.join(OUTPUT_DIR, out_name)
            # 1) Fetch HTML
            html = None
            parsed_title = None
            if url_fetch:
                try:
                    html = fetch_html_requests(url_fetch, timeout=int(fetch_timeout))
                except Exception as e:
                    if use_playwright:
                        try:
                            html = fetch_html_playwright(url_fetch, timeout=int(fetch_timeout), use_stealth=pw_stealth, mobile=pw_mobile, wait_state=pw_wait)
                        except Exception as e2:
                            st.error(f"Fetch failed: {e2}")
                    else:
                        st.error(f"Fetch failed: {e}")
            if not html:
                st.error("No HTML fetched. Provide a valid URL or disable Playwright fallback.")
            else:
                # 2) Parse images
                desc_text = None
                if use_playwright and st.session_state.get("images_fetch_detail_only"):
                    try:
                        parsed_title, desc_text, img_urls, overview_lines = fetch_detail_only_playwright(
                            url_fetch,
                            timeout=int(fetch_timeout),
                            use_stealth=pw_stealth,
                            mobile=pw_mobile,
                            wait_state=pw_wait,
                        )
                        # Fallback: if AliExpress and no overview, try overview-only
                        if site_sel == "aliexpress" and (not overview_lines):
                            try:
                                overview_lines = fetch_overview_only_playwright(
                                    url_fetch,
                                    timeout=int(fetch_timeout),
                                    use_stealth=pw_stealth,
                                    mobile=pw_mobile,
                                    wait_state=pw_wait,
                                )
                            except Exception:
                                pass
                    except Exception as e:
                        st.warning(f"Detail-only fetch failed, falling back: {e}")
                        parsed_title, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(fetch_count))
                        tt_title, tt_price, tt_feats = parse_product_text_from_html(html)
                elif use_playwright and deep_fetch:
                    try:
                        parsed_title, img_urls = fetch_images_playwright_deep(
                            url_fetch,
                            timeout=int(fetch_timeout),
                            use_stealth=pw_stealth,
                            mobile=pw_mobile,
                            wait_state=pw_wait,
                            scrolls=int(deep_scrolls),
                        )
                    except Exception as e:
                        st.warning(f"Deep fetch failed, falling back: {e}")
                        parsed_title, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(fetch_count))
                    tt_title, tt_price, tt_feats = parse_product_text_from_html(html)
                else:
                    if site_sel == "coupang":
                        try:
                            import parser_coupang as pc
                            cp = pc.parse(html)
                            parsed_title = cp.title
                            tt_price = cp.price
                            tt_feats = cp.features
                            img_urls = cp.images[: int(fetch_count)]
                        except Exception:
                            parsed_title, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(fetch_count))
                            tt_title, tt_price, tt_feats = parse_product_text_from_html(html)
                    elif site_sel == "aliexpress":
                        try:
                            import parser_aliexpress as pa
                            ap = pa.parse(html)
                            parsed_title = ap.title
                            tt_price = ap.price
                            tt_feats = ap.features
                            img_urls = ap.images[: int(fetch_count)]
                        except Exception:
                            parsed_title, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(fetch_count))
                            tt_title, tt_price, tt_feats = parse_product_text_from_html(html)
                    else:
                        parsed_title, img_urls = parse_images_from_html(html, base_url=url_fetch, max_items=int(fetch_count))
                        tt_title, tt_price, tt_feats = parse_product_text_from_html(html)
                # Even if not detail-only, when preferred and AliExpress, try overview-only to update Features UI (for UI fields)
                overview_pref_lines = []
                if site_sel == "aliexpress" and st.session_state.get("images_prefer_overview", True):
                    try:
                        ov_static = parse_overview_from_html_static(html)
                        if ov_static:
                            overview_pref_lines = ov_static
                    except Exception:
                        pass
                    if (not overview_pref_lines) and use_playwright:
                        try:
                            overview_pref_lines = fetch_overview_only_playwright(
                                url_fetch,
                                timeout=int(fetch_timeout),
                                use_stealth=pw_stealth,
                                mobile=pw_mobile,
                                wait_state=pw_wait,
                            ) or []
                        except Exception:
                            pass

                if not img_urls:
                    st.error("No images found from URL")
                else:
                    # 3) Download images
                    if not deep_fetch and not st.session_state.get("images_fetch_detail_only"):
                        img_urls = img_urls[: int(fetch_count)]
                    dpaths = download_images(img_urls)
                    # Thumbnails (AliExpress only) — parse and download alongside
                    if site_sel == "aliexpress" and html:
                        try:
                            thumb_urls = parse_aliexpress_thumbnails_from_html(html)
                        except Exception:
                            thumb_urls = []
                        if thumb_urls:
                            if st.session_state.get("images_thumbs_hq", True):
                                try:
                                    thumb_urls = [upgrade_aliexpress_image_url(u) for u in thumb_urls]
                                except Exception:
                                    pass
                            dthumbs = download_thumbnails(thumb_urls)
                            if dthumbs:
                                cur_t = st.session_state.get("images_thumbs_paths") or []
                                st.session_state["images_thumbs_paths"] = cur_t + dthumbs
                    # Also add to fetched list for later review/editing
                    if dpaths:
                        cur = st.session_state.get("images_fetched_paths") or []
                        st.session_state["images_fetched_paths"] = cur + dpaths
                    # Resolve images to run: include thumbnails and prioritize selected thumbs
                    use_selected_only = st.session_state.get("images_use_selected_only", True)
                    selected_paths = st.session_state.get("images_selected_paths") or []
                    thumbs_all = st.session_state.get("images_thumbs_paths") or []
                    thumbs_sel_state = st.session_state.get("images_thumbs_sel_state") or {}
                    selected_thumbs = [p for p in thumbs_all if thumbs_sel_state.get(p, True)]
                    # Build prioritized list
                    if use_selected_only:
                        base_list = selected_paths
                        rest_thumbs = []  # only selected thumbs when in selected-only mode
                    else:
                        base_list = dpaths
                        rest_thumbs = [p for p in thumbs_all if p not in selected_thumbs]
                    ordered = selected_thumbs + base_list + rest_thumbs
                    # Deduplicate while preserving order
                    paths_to_run = []
                    seen = set()
                    for p in ordered:
                        if p and (p not in seen):
                            seen.add(p)
                            paths_to_run.append(p)
                    if len(paths_to_run) < 2:
                        st.error("Need at least 2 images to run. Select more or fetch again.")
                    else:
                        # Update UI features when overview is preferred and available (no rerun to avoid interrupting run)
                        if site_sel == "aliexpress" and overview_pref_lines:
                            st.session_state["features_images_prefill"] = "\n".join(refine_features(overview_pref_lines))
                            st.session_state["images_prefill_pending"] = True
                        # 4) Build and run shorts_maker2.py
                        cmd = [
                            os.path.basename(os.sys.executable),
                            "shorts_maker2.py",
                            "--images",
                            *paths_to_run,
                            "--out", out_path,
                            "--duration", str(duration),
                            "--min_slide", str(min_slide),
                            "--max_slide", str(max_slide),
                        ]
                        tpl_json = build_template_json_if_applied(apply_tpl)
                        if tpl_json:
                            cmd += ["--template_json", tpl_json]
                        # Optional avatar for template
                        if st.session_state.get("tpl_avatar_path"):
                            cmd += ["--tpl_avatar", st.session_state.get("tpl_avatar_path")]
                        # Determine title/price/features priorities: UI input > site parser > generic parser
                        title_to_use = title2 or parsed_title or (locals().get("tt_title") if 'tt_title' in locals() else None) or ""
                        if title_to_use:
                            cmd += ["--title", title_to_use]
                        price_to_use = price2 or (locals().get("tt_price") if 'tt_price' in locals() else None)
                        # Optional KRW conversion
                        if price_convert and price_to_use:
                            price_to_use = convert_price_to_krw(price_to_use, usd=usd_rate, eur=eur_rate, jpy=jpy_rate, cny=cny_rate)
                        if price_to_use:
                            cmd += ["--price", price_to_use]
                        if feats2.strip():
                            for line in feats2.splitlines():
                                line = line.strip()
                                if line:
                                    cmd += ["--feature", line]
                        elif 'overview_lines' in locals() and overview_lines:
                            for line in refine_features(overview_lines):
                                cmd += ["--feature", line]
                        elif 'spec_lines' in locals() and spec_lines:
                            for line in refine_features(spec_lines):
                                cmd += ["--feature", line]
                        elif 'desc_text' in locals() and isinstance(desc_text, str) and desc_text.strip():
                            try:
                                import re as _re
                                desc_feats = [_s.strip() for _s in _re.split(r"[•\n\.\|\-–·]+", desc_text) if 6 <= len(_s.strip()) <= 120]
                                for line in refine_features(desc_feats):
                                    cmd += ["--feature", line]
                            except Exception:
                                pass
                        elif locals().get("tt_feats"):
                            for line in refine_features(locals()["tt_feats"]):
                                cmd += ["--feature", line]
                        if no_tts:
                            cmd.append("--no_tts")
                        cmd += ["--voice_rate", str(voice_rate)]
                        if font_path:
                            cmd += ["--font_path", font_path]
                        if cta:
                            cmd += ["--cta", cta]
                        if music_file is not None:
                            music_path = save_uploaded_file(music_file, subdir="music")
                            cmd += ["--music", music_path]

                        st.write("Running:")
                        st.code(" ".join(shlex.quote(c) for c in cmd))
                        code, logs, took = run_cmd(cmd)
                        if code == 0 and os.path.exists(out_path):
                            st.success(f"Done in {took:.1f}s: {out_path}")
                            st.video(out_path)
                        else:
                            st.error("Failed. See logs above.")
        st.markdown("---")
        st.caption("Save/Load script text (title/price/features/CTA)")
        col_sc1, col_sc2 = st.columns(2)
        with col_sc1:
            if st.button("Save Script JSON (Images)"):
                data = {
                    "title": st.session_state.get("title_images", ""),
                    "price": st.session_state.get("price_images", ""),
                    "features": [l.strip() for l in st.session_state.get("features_images", "").splitlines() if l.strip()],
                    "cta": cta,
                    "script": st.session_state.get("script_images", ""),
                }
                st.download_button(
                    "Download script_images.json",
                    data=json.dumps(data, ensure_ascii=False, indent=2),
                    file_name="script_images.json",
                    mime="application/json",
                )
        with col_sc2:
            script_up = st.file_uploader("Load Script JSON (Images)", type=["json"], key="script_images_upload")
            if script_up is not None:
                try:
                    js = json.loads(script_up.read().decode("utf-8"))
                    if js.get("title"):
                        st.session_state["title_images_prefill"] = js.get("title")
                    if js.get("price"):
                        st.session_state["price_images_prefill"] = js.get("price")
                    if isinstance(js.get("features"), list):
                        st.session_state["features_images_prefill"] = "\n".join(js.get("features"))
                    if js.get("cta"):
                        st.session_state["cta"] = js.get("cta")
                    if js.get("script"):
                        st.session_state["script_images_prefill"] = js.get("script")
                    st.session_state["images_prefill_pending"] = True
                    st.success("Script loaded; updating fields…")
                    try:
                        st.rerun()
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Failed to load script: {e}")

        # Manual generation from current inputs (via template)
        col_gen1, col_gen2, col_gen3 = st.columns([1,1,2])
        with col_gen1:
            if st.button("현재 값으로 대본 생성", key="images_gen_script_btn"):
                feats_list = [l.strip() for l in (feats2 or "").splitlines() if l.strip()]
                tpl_default = "{title} — 핵심만 30초 요약!\n{features_bullets}\n{price_line}\n{cta}"
                cur_tpl = st.session_state.get("script_template_images", tpl_default)
                scr = render_script_from_template(cur_tpl,
                                                  title2 or st.session_state.get("title_images"),
                                                  (price2 or st.session_state.get("price_images")),
                                                  refine_features(feats_list),
                                                  st.session_state.get("cta") or "더 알아보기는 링크 클릭!")
                st.session_state["script_images_prefill"] = scr
                st.session_state["script_last_source_prefill"] = "template"
                st.session_state["images_prefill_pending"] = True
                try:
                    st.rerun()
                except Exception:
                    pass
        with col_gen2:
            if st.button("AI에게 요청하기", key="images_ai_script_btn"):
                feats_list = [l.strip() for l in (feats2 or "").splitlines() if l.strip()]
                tpl_default = "{title} — 핵심만 30초 요약!\n{features_bullets}\n{price_line}\n{cta}"
                cur_tpl = st.session_state.get("script_template_images", tpl_default)
                ans = ai_generate_script(title2 or st.session_state.get("title_images", ""),
                                         price2 or st.session_state.get("price_images", ""),
                                         refine_features(feats_list),
                                         st.session_state.get("cta") or "더 알아보기는 링크 클릭!",
                                         cur_tpl)
                if ans:
                    st.session_state["script_images_prefill"] = ans.strip()
                    st.session_state["script_last_source_prefill"] = "ai"
                    # Backup AI output to OUTPUT_DIR/AI.txt (append with timestamp)
                    try:
                        os.makedirs(OUTPUT_DIR, exist_ok=True)
                        backup_path = os.path.join(OUTPUT_DIR, "AI.txt")
                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        title_for_log = title2 or st.session_state.get("title_images", "")
                        with open(backup_path, "a", encoding="utf-8") as bf:
                            bf.write(f"[{ts}] {title_for_log}\n")
                            bf.write(ans.strip() + "\n\n")
                        st.caption(f"AI 대본 백업 저장: {backup_path}")
                    except Exception:
                        pass
                    st.session_state["images_prefill_pending"] = True
                    try:
                        st.rerun()
                    except Exception:
                        pass
                else:
                    err = st.session_state.get("ai_last_error")
                    if err:
                        st.session_state["script_last_source"] = "ai_error"
                        st.error(err)
                    else:
                        st.warning("AI 호출 실패 또는 OPENAI_API_KEY 미설정. 사이드바 텍스트를 이용해 직접 생성 버튼을 사용하세요.")

        with st.expander("대본 템플릿 (편집/저장/불러오기)"):
            tpl_default = "{title} — 핵심만 30초 요약!\n{features_bullets}\n{price_line}\n{cta}"
            tpl_txt = st.text_area(
                "Template",
                key="script_template_images",
                value=st.session_state.get("script_template_images", tpl_default),
                height=150,
                help="사용 가능한 placeholder: {title}, {features_bullets}, {features_numbers}, {price}, {price_line}, {cta}"
            )
            col_ta, col_tb, col_tc = st.columns(3)
            with col_ta:
                if st.button("템플릿 초기화"):
                    st.session_state["script_template_images_prefill"] = tpl_default
                    st.session_state["images_prefill_pending"] = True
                    try:
                        st.rerun()
                    except Exception:
                        pass
            with col_tb:
                st.download_button(
                    "Save Script Template",
                    data=json.dumps({"template": st.session_state.get("script_template_images", tpl_default)}, ensure_ascii=False, indent=2),
                    file_name="script_template.json",
                    mime="application/json",
                )
            with col_tc:
                tpl_up = st.file_uploader("Load Script Template", type=["json"], key="script_tpl_upload")
                if tpl_up is not None:
                    try:
                        js = json.loads(tpl_up.read().decode("utf-8"))
                        if js.get("template"):
                            st.session_state["script_template_images_prefill"] = js.get("template")
                            st.session_state["images_prefill_pending"] = True
                            try:
                                st.rerun()
                            except Exception:
                                pass
                    except Exception as e:
                        st.error(f"Failed to load template: {e}")
        st.markdown("---")
        st.caption("Slides JSON (optional): specify per-slide caption/duration/highlight")
        slides_json_up = st.file_uploader("Slides JSON (Images)", type=["json"], key="slides_images_upload")
        if st.button("Download sample slides.json"):
            sample = [
                {"image": "path/img1.jpg", "caption": "첫 슬라이드 캡션", "duration": 3.0, "highlight": [0.2,0.5,0.8,0.8]},
                {"image": "path/img2.jpg", "caption": "둘째 슬라이드", "duration": 3.0}
            ]
            st.download_button("slides_sample.json", data=json.dumps(sample, ensure_ascii=False, indent=2), file_name="slides_sample.json", mime="application/json")

        if st.button("Run from Images"):
            out_path = os.path.join(OUTPUT_DIR, out_name)
            cmd = [
                os.path.basename(os.sys.executable),
                "shorts_maker2.py",
                "--images",
            ]
            img_paths = []
            use_selected_only = st.session_state.get("images_use_selected_only", True)
            selected_paths = st.session_state.get("images_selected_paths") or []
            if use_selected_only and selected_paths:
                img_paths = list(selected_paths)
            else:
                for f in imgs or []:
                    p = save_uploaded_file(f, subdir="images")
                    img_paths.append(p)
                # Include any fetched images from URL parsing
                if st.session_state.get("images_fetched_paths"):
                    img_paths += list(st.session_state.get("images_fetched_paths"))
            cmd += img_paths
            cmd += ["--out", out_path, "--duration", str(duration), "--min_slide", str(min_slide), "--max_slide", str(max_slide)]
            # Template via JSON if applied
            tpl_json = build_template_json_if_applied(apply_tpl)
            if tpl_json:
                cmd += ["--template_json", tpl_json]
            if st.session_state.get("tpl_avatar_path"):
                cmd += ["--tpl_avatar", st.session_state.get("tpl_avatar_path")]
            if slides_json_up is not None:
                # Save uploaded slides json
                slides_path = save_uploaded_file(slides_json_up, subdir="slides")
                cmd += ["--slides_json", slides_path]
            if title2:
                cmd += ["--title", title2]
            if price2:
                cmd += ["--price", price2]
            if feats2.strip():
                for line in feats2.splitlines():
                    line = line.strip()
                    if line:
                        cmd += ["--feature", line]
            if no_tts:
                cmd.append("--no_tts")
            cmd += ["--voice_rate", str(voice_rate)]
            if font_path:
                cmd += ["--font_path", font_path]
            if cta:
                cmd += ["--cta", cta]
            if music_file is not None:
                music_path = save_uploaded_file(music_file, subdir="music")
                cmd += ["--music", music_path]

            st.write("Running:")
            st.code(" ".join(shlex.quote(c) for c in cmd))
            code, logs, took = run_cmd(cmd)
            if code == 0 and os.path.exists(out_path):
                st.success(f"Done in {took:.1f}s: {out_path}")
                st.video(out_path)
            else:
                st.error("Failed. See logs above.")

    with tab2:
        st.subheader("PDF → MP4 (shorts_maker2.py)")
        pdf = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_upload")
        max_pages = st.number_input("Max pages", 1, 30, 6, key="pdf_max_pages")
        zoom = st.number_input("Render zoom", 1.0, 4.0, 2.0, 0.1, key="pdf_zoom")
        pdf_mode = st.selectbox("PDF mode", ["auto", "image", "page"], index=0, key="pdf_mode")
        colp1, colp2 = st.columns(2)
        with colp1:
            min_img_ratio = st.slider("Min image area ratio", 0.005, 0.3, 0.05, 0.005, key="pdf_min_img_ratio")
        with colp2:
            crop_margin = st.slider("Crop margin ratio", 0.0, 0.1, 0.01, 0.005, key="pdf_crop_margin")
        max_extract = st.number_input("Max extracted images", 1, 200, 20, key="pdf_max_extract")
        # Apply any pending PDF prefills before creating the widgets
        if st.session_state.get("pdf_prefill_pending"):
            if "title_pdf_prefill" in st.session_state:
                st.session_state["title_pdf"] = st.session_state.pop("title_pdf_prefill")
            if "price_pdf_prefill" in st.session_state:
                st.session_state["price_pdf"] = st.session_state.pop("price_pdf_prefill")
            if "features_pdf_prefill" in st.session_state:
                st.session_state["features_pdf"] = st.session_state.pop("features_pdf_prefill")
            st.session_state["pdf_prefill_pending"] = False
        title3 = st.text_input("Title override (optional)", key="title_pdf")
        price3 = st.text_input("Price override (optional)", key="price_pdf")
        feats3 = st.text_area("Features (one per line)", key="features_pdf")
        st.caption("Slides JSON (optional): specify per-slide caption/duration/highlight")
        slides_pdf_up = st.file_uploader("Slides JSON (PDF)", type=["json"], key="slides_pdf_upload")
        if st.button("Run from PDF"):
            out_path = os.path.join(OUTPUT_DIR, out_name)
            pdf_path = save_uploaded_file(pdf, subdir="pdf") if pdf else None
            cmd = [
                os.path.basename(os.sys.executable),
                "shorts_maker2.py",
                "--pdf",
                pdf_path or "",
                "--out",
                out_path,
                "--duration",
                str(duration),
                "--max_pages",
                str(max_pages),
                "--zoom",
                str(zoom),
                "--pdf_mode",
                pdf_mode,
                "--min_img_ratio",
                str(min_img_ratio),
                "--crop_margin",
                str(crop_margin),
                "--max_extract",
                str(max_extract),
                "--min_slide",
                str(min_slide),
                "--max_slide",
                str(max_slide),
            ]
            tpl_json = build_template_json_if_applied(apply_tpl)
            if tpl_json:
                cmd += ["--template_json", tpl_json]
            if st.session_state.get("tpl_avatar_path"):
                cmd += ["--tpl_avatar", st.session_state.get("tpl_avatar_path")]
            if slides_pdf_up is not None:
                slides_path = save_uploaded_file(slides_pdf_up, subdir="slides")
                cmd += ["--slides_json", slides_path]
            if title3:
                cmd += ["--title", title3]
            if price3:
                cmd += ["--price", price3]
            if feats3.strip():
                for line in feats3.splitlines():
                    line = line.strip()
                    if line:
                        cmd += ["--feature", line]
            if no_tts:
                cmd.append("--no_tts")
            cmd += ["--voice_rate", str(voice_rate)]
            if font_path:
                cmd += ["--font_path", font_path]
            if cta:
                cmd += ["--cta", cta]
            if music_file is not None:
                music_path = save_uploaded_file(music_file, subdir="music")
                cmd += ["--music", music_path]

            st.write("Running:")
            st.code(" ".join(shlex.quote(c) for c in cmd))
            code, logs, took = run_cmd(cmd)
            if code == 0 and os.path.exists(out_path):
                st.success(f"Done in {took:.1f}s: {out_path}")
                st.video(out_path)
            else:
                st.error("Failed. See logs above.")
        st.markdown("---")
        st.caption("Save/Load script text (title/price/features/CTA)")
        col_sc3, col_sc4 = st.columns(2)
        with col_sc3:
            if st.button("Save Script JSON (PDF)"):
                data = {
                    "title": st.session_state.get("title_pdf", ""),
                    "price": st.session_state.get("price_pdf", ""),
                    "features": [l.strip() for l in st.session_state.get("features_pdf", "").splitlines() if l.strip()],
                    "cta": cta,
                }
                st.download_button(
                    "Download script_pdf.json",
                    data=json.dumps(data, ensure_ascii=False, indent=2),
                    file_name="script_pdf.json",
                    mime="application/json",
                )
        with col_sc4:
            script_pdf_up = st.file_uploader("Load Script JSON (PDF)", type=["json"], key="script_pdf_upload")
            if script_pdf_up is not None:
                try:
                    js = json.loads(script_pdf_up.read().decode("utf-8"))
                    if js.get("title"):
                        st.session_state["title_pdf_prefill"] = js.get("title")
                    if js.get("price"):
                        st.session_state["price_pdf_prefill"] = js.get("price")
                    if isinstance(js.get("features"), list):
                        st.session_state["features_pdf_prefill"] = "\n".join(js.get("features"))
                    if js.get("cta"):
                        st.session_state["cta"] = js.get("cta")
                    st.session_state["pdf_prefill_pending"] = True
                    st.success("Script loaded; updating fields…")
                    try:
                        st.rerun()
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Failed to load script: {e}")

    with tab3:
        st.subheader("Template (overlay)")
        # Preset selection
        preset = st.selectbox("Preset", list(PRESET_TEMPLATES.keys()) + ["Custom"], index=0, key="tpl_preset")
        if st.button("Apply Preset") and preset in PRESET_TEMPLATES:
            p = PRESET_TEMPLATES[preset]
            st.session_state["tpl_header"] = p.get("header", "")
            st.session_state["tpl_subheader"] = p.get("subheader", "")
            st.session_state["tpl_footer"] = p.get("footer", "")
            st.session_state["tpl_cta"] = p.get("cta_label", "제품 보기")
            st.session_state["tpl_profile"] = p.get("profile_name", "@channel")
            col = p.get("theme_color", [16,153,127])
            st.session_state["tpl_color"] = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
            st.session_state["tpl_bar"] = p.get("bar_height", 90)
            st.session_state["tpl_card"] = p.get("card_height", 280)
            pill = p.get("pill", {"x":24, "y":1700, "w":200, "h":64})
            st.session_state["tpl_pill_x"] = pill.get("x", 24)
            st.session_state["tpl_pill_y"] = pill.get("y", 1700)
            st.session_state["tpl_pill_w"] = pill.get("w", 200)
            st.session_state["tpl_pill_h"] = pill.get("h", 64)
            st.session_state["tpl_prof_x"] = p.get("profile_x", 24)
            st.session_state["tpl_prof_off"] = p.get("profile_offset", 18)
            fs = p.get("font_sizes", {})
            st.session_state["tpl_size_hdr"] = fs.get("hdr", 40)
            st.session_state["tpl_size_title"] = fs.get("title", 56)
            st.session_state["tpl_size_mid"] = fs.get("mid", 54)
            st.session_state["tpl_size_cta"] = fs.get("cta", 32)
            st.session_state["tpl_size_prof"] = fs.get("prof", 30)
            st.session_state["tpl_size_foot"] = fs.get("foot", 28)
            st.success(f"Applied preset: {preset}")
            try:
                st.rerun()
            except Exception:
                pass
        # Apply any pending Template-prefills before creating the widgets
        if st.session_state.get("tpl_prefill_pending"):
            if "tpl_header_prefill" in st.session_state:
                st.session_state["tpl_header"] = st.session_state.pop("tpl_header_prefill")
            if "tpl_subheader_prefill" in st.session_state:
                st.session_state["tpl_subheader"] = st.session_state.pop("tpl_subheader_prefill")
            if "tpl_footer_prefill" in st.session_state:
                st.session_state["tpl_footer"] = st.session_state.pop("tpl_footer_prefill")
            if "tpl_cta_prefill" in st.session_state:
                st.session_state["tpl_cta"] = st.session_state.pop("tpl_cta_prefill")
            if "tpl_profile_prefill" in st.session_state:
                st.session_state["tpl_profile"] = st.session_state.pop("tpl_profile_prefill")
            if "tpl_color_prefill" in st.session_state:
                st.session_state["tpl_color"] = st.session_state.pop("tpl_color_prefill")
            # Advanced numeric/layout prefills
            if "tpl_bar_prefill" in st.session_state:
                st.session_state["tpl_bar"] = st.session_state.pop("tpl_bar_prefill")
            if "tpl_card_prefill" in st.session_state:
                st.session_state["tpl_card"] = st.session_state.pop("tpl_card_prefill")
            if "tpl_pill_x_prefill" in st.session_state:
                st.session_state["tpl_pill_x"] = st.session_state.pop("tpl_pill_x_prefill")
            if "tpl_pill_y_prefill" in st.session_state:
                st.session_state["tpl_pill_y"] = st.session_state.pop("tpl_pill_y_prefill")
            if "tpl_pill_w_prefill" in st.session_state:
                st.session_state["tpl_pill_w"] = st.session_state.pop("tpl_pill_w_prefill")
            if "tpl_pill_h_prefill" in st.session_state:
                st.session_state["tpl_pill_h"] = st.session_state.pop("tpl_pill_h_prefill")
            if "tpl_prof_x_prefill" in st.session_state:
                st.session_state["tpl_prof_x"] = st.session_state.pop("tpl_prof_x_prefill")
            if "tpl_prof_off_prefill" in st.session_state:
                st.session_state["tpl_prof_off"] = st.session_state.pop("tpl_prof_off_prefill")
            if "tpl_size_hdr_prefill" in st.session_state:
                st.session_state["tpl_size_hdr"] = st.session_state.pop("tpl_size_hdr_prefill")
            if "tpl_size_title_prefill" in st.session_state:
                st.session_state["tpl_size_title"] = st.session_state.pop("tpl_size_title_prefill")
            if "tpl_size_mid_prefill" in st.session_state:
                st.session_state["tpl_size_mid"] = st.session_state.pop("tpl_size_mid_prefill")
            if "tpl_size_cta_prefill" in st.session_state:
                st.session_state["tpl_size_cta"] = st.session_state.pop("tpl_size_cta_prefill")
            if "tpl_size_prof_prefill" in st.session_state:
                st.session_state["tpl_size_prof"] = st.session_state.pop("tpl_size_prof_prefill")
            if "tpl_size_foot_prefill" in st.session_state:
                st.session_state["tpl_size_foot"] = st.session_state.pop("tpl_size_foot_prefill")
            st.session_state["tpl_prefill_pending"] = False
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tpl_header = st.text_input("Header (top bar)", value=st.session_state.get("tpl_header", ""), key="tpl_header")
            tpl_subheader = st.text_area("Subheader (big title)", key="tpl_subheader", value=st.session_state.get("tpl_subheader", ""))
            tpl_footer = st.text_input("Footer (bottom text)", value=st.session_state.get("tpl_footer", ""), key="tpl_footer")
        with col_t2:
            tpl_cta = st.text_input("CTA label", value=st.session_state.get("tpl_cta", "제품 보기"), key="tpl_cta")
            tpl_profile = st.text_input("Profile name", value=st.session_state.get("tpl_profile", "@channel"), key="tpl_profile")
            theme_color = st.color_picker("Theme color", value=st.session_state.get("tpl_color", "#10997F"), key="tpl_color")
            # Optional avatar image for preview and run
            avatar_up = st.file_uploader("Avatar image (circle)", type=["jpg","jpeg","png"], key="tpl_avatar_up")
            if avatar_up is not None:
                try:
                    apath = save_uploaded_file(avatar_up, subdir="tpl_avatar")
                    st.session_state["tpl_avatar_path"] = apath
                    st.success("Avatar saved for template.")
                except Exception as e:
                    st.error(f"Failed to save avatar: {e}")

        with st.expander("Advanced layout / typography"):
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1:
                bar_h = st.number_input("Bar height", 40, 480, value=st.session_state.get("tpl_bar", 90), key="tpl_bar")
                card_h = st.number_input("Card height", 120, 960, value=st.session_state.get("tpl_card", 280), key="tpl_card")
                prof_x = st.number_input("Profile X", 0, 800, value=st.session_state.get("tpl_prof_x", 24), key="tpl_prof_x")
                prof_off = st.number_input("Profile offset (below pill)", 0, 200, value=st.session_state.get("tpl_prof_off", 18), key="tpl_prof_off")
            with col_a2:
                pill_x = st.number_input("CTA X", 0, 1000, value=st.session_state.get("tpl_pill_x", 24), key="tpl_pill_x")
                pill_y = st.number_input("CTA Y", 0, 1800, value=st.session_state.get("tpl_pill_y", 1700), key="tpl_pill_y")
                pill_w = st.number_input("CTA Width", 100, 400, value=st.session_state.get("tpl_pill_w", 200), key="tpl_pill_w")
                pill_h = st.number_input("CTA Height", 40, 160, value=st.session_state.get("tpl_pill_h", 64), key="tpl_pill_h")
            with col_a3:
                size_hdr = st.number_input("Hdr size", 12, 96, value=st.session_state.get("tpl_size_hdr", 40), key="tpl_size_hdr")
                size_title = st.number_input("Title size", 12, 96, value=st.session_state.get("tpl_size_title", 56), key="tpl_size_title")
                size_mid = st.number_input("Mid size", 12, 96, value=st.session_state.get("tpl_size_mid", 54), key="tpl_size_mid")
                size_cta = st.number_input("CTA size", 12, 96, value=st.session_state.get("tpl_size_cta", 32), key="tpl_size_cta")
                size_prof = st.number_input("Profile size", 12, 96, value=st.session_state.get("tpl_size_prof", 30), key="tpl_size_prof")
                size_foot = st.number_input("Footer size", 12, 96, value=st.session_state.get("tpl_size_foot", 28), key="tpl_size_foot")

        st.caption("Save/Load template text")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("Save Template JSON"):
                data = {
                    "header": st.session_state.get("tpl_header", ""),
                    "subheader": st.session_state.get("tpl_subheader", ""),
                    "footer": st.session_state.get("tpl_footer", ""),
                    "cta_label": st.session_state.get("tpl_cta", "제품 보기"),
                    "profile_name": st.session_state.get("tpl_profile", "@channel"),
                    "theme_color": [int(st.session_state.get("tpl_color", "#10997F")[1:3],16), int(st.session_state.get("tpl_color", "#10997F")[3:5],16), int(st.session_state.get("tpl_color", "#10997F")[5:7],16)],
                    "bar_height": st.session_state.get("tpl_bar", 90),
                    "card_height": st.session_state.get("tpl_card", 280),
                    "pill": {"x": st.session_state.get("tpl_pill_x", 24), "y": st.session_state.get("tpl_pill_y", 1700), "w": st.session_state.get("tpl_pill_w", 200), "h": st.session_state.get("tpl_pill_h", 64)},
                    "profile_x": st.session_state.get("tpl_prof_x", 24),
                    "profile_offset": st.session_state.get("tpl_prof_off", 18),
                    "font_sizes": {"hdr": st.session_state.get("tpl_size_hdr", 40), "title": st.session_state.get("tpl_size_title", 56), "mid": st.session_state.get("tpl_size_mid", 54), "cta": st.session_state.get("tpl_size_cta", 32), "prof": st.session_state.get("tpl_size_prof", 30), "foot": st.session_state.get("tpl_size_foot", 28)},
                }
                st.download_button("Download template.json", data=json.dumps(data, ensure_ascii=False, indent=2), file_name="template.json", mime="application/json")
        with col_s2:
            tpl_file = st.file_uploader("Load Template JSON", type=["json"], key="tpl_upload")
            if tpl_file is not None:
                try:
                    tpl_data = json.loads(tpl_file.read().decode("utf-8"))
                    st.session_state["tpl_header_prefill"] = tpl_data.get("header", "")
                    st.session_state["tpl_subheader_prefill"] = tpl_data.get("subheader", "")
                    st.session_state["tpl_footer_prefill"] = tpl_data.get("footer", "")
                    st.session_state["tpl_cta_prefill"] = tpl_data.get("cta_label", "제품 보기")
                    st.session_state["tpl_profile_prefill"] = tpl_data.get("profile_name", "@channel")
                    col = tpl_data.get("theme_color") or [16,153,127]
                    st.session_state["tpl_color_prefill"] = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                    # Advanced fields
                    st.session_state["tpl_bar_prefill"] = tpl_data.get("bar_height", 90)
                    st.session_state["tpl_card_prefill"] = tpl_data.get("card_height", 280)
                    pill = tpl_data.get("pill") or {"x":24, "y":1700, "w":200, "h":64}
                    st.session_state["tpl_pill_x_prefill"] = pill.get("x", 24)
                    st.session_state["tpl_pill_y_prefill"] = pill.get("y", 1700)
                    st.session_state["tpl_pill_w_prefill"] = pill.get("w", 200)
                    st.session_state["tpl_pill_h_prefill"] = pill.get("h", 64)
                    st.session_state["tpl_prof_x_prefill"] = tpl_data.get("profile_x", 24)
                    st.session_state["tpl_prof_off_prefill"] = tpl_data.get("profile_offset", 18)
                    fs = tpl_data.get("font_sizes") or {}
                    st.session_state["tpl_size_hdr_prefill"] = fs.get("hdr", 40)
                    st.session_state["tpl_size_title_prefill"] = fs.get("title", 56)
                    st.session_state["tpl_size_mid_prefill"] = fs.get("mid", 54)
                    st.session_state["tpl_size_cta_prefill"] = fs.get("cta", 32)
                    st.session_state["tpl_size_prof_prefill"] = fs.get("prof", 30)
                    st.session_state["tpl_size_foot_prefill"] = fs.get("foot", 28)
                    st.session_state["tpl_prefill_pending"] = True
                    st.success("Template loaded; updating fields…")
                    try:
                        st.rerun()
                    except Exception:
                        pass
                except Exception as e:
                    st.error(f"Failed to load template: {e}")

        st.markdown("---")
        st.subheader("미리보기")
        prev_col1, prev_col2 = st.columns([2,1])
        with prev_col2:
            st.caption("옵션")
            preview_caption = st.text_area("미리보기 캡션 (중앙 본문)", key="tpl_preview_caption", height=90)
            bg_up = st.file_uploader("배경 이미지 (선택)", type=["jpg","jpeg","png"], key="tpl_preview_bg")
            if bg_up is not None:
                try:
                    bpath = save_uploaded_file(bg_up, subdir="tpl_preview")
                    st.session_state["tpl_preview_bg_path"] = bpath
                    st.caption("배경 이미지 적용됨")
                except Exception:
                    st.warning("배경 이미지 저장 실패 — 기본 배경 사용")
            cur_font = st.session_state.get("font_path") or "(기본 폰트)"
            st.caption(f"미리보기 폰트: {cur_font}")
            st.info("한글이 깨지면 좌측 상단 'Font path'에 한글 폰트(.ttf/.ttc) 경로를 지정하세요. 예: /usr/share/fonts/truetype/nanum/NanumGothic.ttf")
        with prev_col1:
            img = make_template_preview_image(st.session_state.get("tpl_preview_caption", ""), st.session_state.get("tpl_preview_bg_path"))
            st.image(img, caption="Template 미리보기 (1080x1920)", width='stretch')


if __name__ == "__main__":
    main()
