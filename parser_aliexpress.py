import re
import json
from typing import List, Optional
from bs4 import BeautifulSoup


class AliParsed:
    def __init__(self, title: str, price: Optional[str], features: List[str], images: List[str]):
        self.title = title
        self.price = price
        self.features = features
        self.images = images


def _parse_json_ld(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    yield item
        elif isinstance(data, dict) and data.get("@type") == "Product":
            yield data


def _parse_runparams(html: str):
    # Very heuristic extraction of window.runParams = { ... } structure
    m = re.search(r"window\.runParams\s*=\s*(\{.*?\});\s*window", html, re.S)
    if not m:
        m = re.search(r"window\.runParams\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        return None
    txt = m.group(1)
    # Try to fix unquoted keys and trailing commas with a loose load
    try:
        return json.loads(txt)
    except Exception:
        # As a fallback, try to extract some obvious arrays/fields
        return None


def parse(html: str) -> AliParsed:
    soup = BeautifulSoup(html, "lxml")

    title = None
    price = None
    features: List[str] = []
    images: List[str] = []

    # Prefer extracting product overview lines under the '개요' (Overview) heading
    try:
        overview_lines: List[str] = []
        # Find any heading that contains '개요'
        heading = None
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            t = (tag.get_text(" ", strip=True) or "").strip()
            if "개요" in t:
                heading = tag
                break
        if heading is not None:
            # Collect text from siblings after the heading until an image or next heading appears
            def has_img(el) -> bool:
                try:
                    return bool(el.find("img"))
                except Exception:
                    return False
            buf: List[str] = []
            for sib in heading.next_siblings:
                try:
                    # Stop at next heading
                    if getattr(sib, "name", None) in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                        break
                    # If this sibling (element) or its subtree contains an image, stop
                    if getattr(sib, "name", None) and has_img(sib):
                        break
                    txt = ""
                    if getattr(sib, "get_text", None):
                        # Collect paragraph/list-like texts
                        txt = sib.get_text("\n", strip=True)
                    else:
                        # NavigableString or others
                        txt = str(sib).strip()
                    if txt:
                        buf.append(txt)
                except Exception:
                    continue
            # Split buffered text into lines
            joined = "\n".join(buf)
            for c in re.split(r"[•\n\.\|\-–·]+", joined):
                cc = c.strip()
                if 6 <= len(cc) <= 160:
                    overview_lines.append(cc)
        # If we found reasonable overview lines, prefer them for features (cap to 5)
        if overview_lines:
            features.extend(overview_lines[:5])
    except Exception:
        pass

    # Prefer JSON-LD Product
    for prod in _parse_json_ld(soup):
        title = prod.get("name") or title
        offers = prod.get("offers") or {}
        if isinstance(offers, dict):
            price = offers.get("price") or price
            if price and offers.get("priceCurrency"):
                cur = offers.get("priceCurrency")
                if not any(c in price for c in "$₩€¥"):
                    price = f"{price} {cur}"
        imgs = prod.get("image")
        if isinstance(imgs, list):
            images.extend(imgs)
        elif isinstance(imgs, str):
            images.append(imgs)
        desc = prod.get("description") or ""
        for c in re.split(r"[•\n\.\|]+", desc):
            c = c.strip()
            if 6 <= len(c) <= 120:
                features.append(c)
        break  # Use first product block

    # Fallbacks
    if not title:
        ogt = soup.find("meta", property="og:title")
        if ogt and ogt.get("content"):
            title = ogt["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    if not title:
        title = "AliExpress Product"

    def _norm(u: str) -> str:
        if not u:
            return u
        # prefer jpg and strip size suffixes like _640x640, _Q90
        u = re.sub(r"(_\d+x\d+)|(_Q\d+)", "", u)
        u = u.replace(".webp", ".jpg")
        u = u.replace(".jpg_.webp", ".jpg")
        u = u.replace(".jpg_Q90.jpg", ".jpg")
        return u

    if not images:
        ogimgs = [m.get("content") for m in soup.find_all("meta", property="og:image") if m.get("content")]
        images.extend([_norm(x) for x in ogimgs])
    if len(images) < 8:
        for img in soup.select("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-image") or ""
            if any(host in src for host in ("ae01.alicdn.com", "img.alicdn.com", "i.alicdn.com")):
                images.append(_norm(src))
            if len(images) >= 8:
                break

    if not price:
        text = soup.get_text("\n", strip=True)
        m = re.search(r"([$€¥₩])\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", text)
        if m:
            price = f"{m.group(1)}{m.group(2)}"

    # Features: also check bullets
    if len(features) < 3:
        for li in soup.select("li"):
            t = li.get_text(" ", strip=True)
            if 6 <= len(t) <= 120:
                features.append(t)
            if len(features) >= 6:
                break
    # Dedup
    def dedup_list(xs):
        out = []
        for x in xs:
            if x and x not in out:
                out.append(x)
        return out

    images = dedup_list(images)[:8]
    features = dedup_list(features)[:5] or ["Key feature 1", "Key feature 2", "Key feature 3"]

    return AliParsed(title=title, price=price, features=features, images=images)
