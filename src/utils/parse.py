from __future__ import annotations
from typing import Optional, Tuple, List
import re
from bs4 import BeautifulSoup
from dateutil import parser as dtparser


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def parse_datetime(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    try:
        dt = dtparser.parse(text, dayfirst=True)
        return dt.isoformat()
    except Exception:
        return None


def parse_price_byn(text: Optional[str]) -> Tuple[Optional[float], Optional[float], Optional[bool]]:
    if not text:
        return None, None, None
    t = text.lower()
    if any(k in t for k in ["бесплатно", "free", "0 byn", "0 руб"]):
        return 0.0, 0.0, True
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+[\.,]?\d*", t)]
    if not nums:
        return None, None, None
    if len(nums) == 1:
        return nums[0], nums[0], False
    return min(nums), max(nums), False


def parse_age(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(\d+\+)", text)
    return m.group(1) if m else None


def extract_meta(soup: BeautifulSoup) -> Tuple[Optional[str], List[str]]:
    cover = None
    images: List[str] = []
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        cover = og_image["content"].strip()
    for tag in soup.select('img'):
        src = tag.get('src') or tag.get('data-src')
        if not src:
            continue
        # фильтруем пиксели/счётчики/loader-гифки
        low = src.lower()
        if any(x in low for x in ["/ajax-loader", "mc.yandex.ru", "counter", "pixel", "1x1"]):
            continue
        images.append(src)
    return cover, images


