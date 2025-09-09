from __future__ import annotations
import os
import time
import hashlib
from typing import List, Tuple


def deep_image_fetch(url: str, mobile: bool = True, use_stealth: bool = True, scrolls: int = 8, delay: float = 0.8,
                     timeout: int = 45) -> Tuple[str | None, List[str]]:
    try:
        from playwright.sync_api import sync_playwright
        try:
            from playwright_stealth import stealth_sync as pw_stealth
        except Exception:
            pw_stealth = None
    except Exception as e:
        raise RuntimeError("Playwright not installed. pip install playwright playwright-stealth && playwright install") from e

    title = None
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
            page.wait_for_load_state("networkidle", timeout=max(1000, (timeout - 3) * 1000))
        except Exception:
            pass

        # Try to open description or more content up to 2 times
        clicks = 0
        for sel in [
            "button:has-text('더보기')",
            "text=상세보기",
            "button:has-text('Show More')",
            "text=Show more",
            "text=Description",
            "text=상품 설명",
            "text=상세",
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

        for i in range(max(1, scrolls)):
            try:
                page.evaluate("(step) => { window.scrollTo(0, document.body.scrollHeight * step); }", (i + 1) / max(1, scrolls))
            except Exception:
                pass
            page.wait_for_timeout(int(delay * 1000))

        data = page.evaluate(
            """
            (function(){
              const urls = new Set();
              function pickFromSrcset(srcset){
                if(!srcset) return null;
                const parts = srcset.split(',').map(s=>s.trim());
                const last = parts[parts.length-1] || parts[0];
                const u = (last.split(' ')||[])[0];
                return u || null;
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
        )
        urls = list(data.get("urls") or [])
        t = (data.get("title") or "").strip()
        title = t or None
        ctx.close()
        browser.close()
    return title, urls


def sanitize_filename(name: str) -> str:
    bad = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f<>:\"/\\|?*"
    return "".join(c for c in name if c not in bad)[:80] or f"untitled-{int(time.time())}"


def download_images(urls: list[str], out_dir: str) -> list[str]:
    import requests
    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []
    for u in urls:
        try:
            r = requests.get(u, timeout=20)
            r.raise_for_status()
            ext = ".jpg"
            ct = (r.headers.get("content-type") or "").lower()
            if "png" in ct:
                ext = ".png"
            elif "webp" in ct:
                ext = ".webp"
            h = hashlib.md5(u.encode()).hexdigest()[:12]
            p = os.path.join(out_dir, f"img_{h}{ext}")
            with open(p, "wb") as f:
                f.write(r.content)
            paths.append(p)
        except Exception:
            continue
    return paths

