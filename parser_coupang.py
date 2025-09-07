import re
from typing import List, Optional
from bs4 import BeautifulSoup

class CoupangParsed:
    def __init__(self, title: str, price: Optional[str], features: List[str], images: List[str]):
        self.title = title
        self.price = price
        self.features = features
        self.images = images

def parse(html: str) -> CoupangParsed:
    soup = BeautifulSoup(html, "lxml")

    # --- Title (prefer Korean) ---
    cands = []
    ogt = soup.find("meta", property="og:title")
    if ogt and ogt.get("content"):
        cands.append(ogt["content"].strip())
    for sel in ["h2.prod-buy-header__title", "h1.prod-buy-header__title",
                "div.prod-buy-header__title", "meta[name='title']"]:
        el = soup.select_one(sel)
        if el:
            c = (el.get("content") or el.get_text(" ", strip=True)).strip()
            if c:
                cands.append(c)
    if soup.title:
        t = soup.title.get_text(" ", strip=True)
        if t:
            cands.append(t)
    def _has_ko(s: str) -> bool:
        return bool(re.search(r"[가-힣]", s or ""))
    title = next((t for t in cands if _has_ko(t)), (cands[0] if cands else None))
    if not title:
        title = "쿠팡 상품"

    # --- Price ---
    text = soup.get_text("\n", strip=True)
    price = None
    m = re.search(r"(?:₩|\b)[\s]*([0-9]{1,3}(?:,[0-9]{3})+)\s*원?", text)
    if m:
        price = m.group(0)
    if not price:
        for sel in ["span.total-price", "span.total-price > strong",
                    "span.prod-sale-price > strong", "span.prod-price__price"]:
            el = soup.select_one(sel)
            if el:
                price = el.get_text(" ", strip=True)
                break
        if not price:
            mp = soup.find("meta", attrs={"property": "og:product:price:amount"}) or soup.find("meta", attrs={"itemprop": "price"})
            if mp and mp.get("content"):
                price = mp["content"]

    # --- Features ---
    features = []
    for li in soup.select("li.prod-description-attribute__item, ul.prod-description-attribute li"):
        t = li.get_text(" ", strip=True)
        if 6 <= len(t) <= 120:
            features.append(t)
            if len(features) >= 6:
                break
    if len(features) < 3:
        ogd = soup.find("meta", property="og:description")
        desc = ogd.get("content").strip() if ogd and ogd.get("content") else ""
        for chunk in re.split(r"[•\n\.\|]+", desc):
            c = chunk.strip()
            if 6 <= len(c) <= 120:
                features.append(c)
    if not features:
        features = ["핵심 기능 1", "핵심 기능 2", "핵심 기능 3"]
    features = list(dict.fromkeys(features))[:5]

    # --- Images ---
    def _norm(u: str) -> str:
        if not u:
            return u
        # remove query strings that often reduce size
        u = u.split("?")[0]
        # prefer jpg over webp if both provided
        u = u.replace(".webp", ".jpg")
        return u

    images = []
    for m in soup.find_all("meta", property="og:image"):
        if m.get("content"):
            images.append(_norm(m["content"]))
    if len(images) < 5:
        for img in soup.select("img"):
            src = img.get("src") or img.get("data-img-src") or ""
            if "coupangcdn.com" in src:
                images.append(_norm(src))
            if len(images) >= 8:
                break
    images = list(dict.fromkeys(images))[:8]

    return CoupangParsed(title, price, features, images)
