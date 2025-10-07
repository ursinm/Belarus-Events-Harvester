from __future__ import annotations
from typing import List, Optional
from urllib.parse import urljoin
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.utils.http import HttpClient
from src.utils.parse import clean_text, parse_datetime, extract_meta
from src.core.models import Event, Venue
from src.core.geocode import Geocoder


BASE = "https://minsktourism.by/"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_list(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    links: List[str] = []
    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(BASE, href)
        if "/afisha/" in full or "/event/" in full or "/calendar/" in full:
            links.append(full)
    seen = set()
    uniq: List[str] = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    return uniq


def _parse_detail(url: str, html: str, geocoder: Geocoder) -> Optional[Event]:
    soup = BeautifulSoup(html, "lxml")

    title = clean_text(soup.select_one("h1") and soup.select_one("h1").get_text())
    if not title:
        return None

    start_dt = None
    end_dt = None
    for n in soup.select("time, .date, .event-date"):
        val = parse_datetime(clean_text(n.get_text()))
        if val and not start_dt:
            start_dt = val
        elif val and not end_dt:
            end_dt = val
    if not start_dt:
        return None

    venue_name = clean_text((soup.select_one(".place, .location") or {}).get_text() if soup.select_one(".place, .location") else None) or ""
    venue_address = clean_text((soup.select_one(".address") or {}).get_text() if soup.select_one(".address") else None)
    city = "Минск"

    category = clean_text((soup.select_one(".category, .tags a") or {}).get_text() if soup.select_one(".category, .tags a") else None)

    cover_url, images = extract_meta(soup)
    description = None
    dnode = soup.select_one(".description, article, .content")
    if dnode:
        description = clean_text(dnode.get_text())

    lat, lon = geocoder.geocode(venue_address or venue_name, city)

    venue = Venue(name=venue_name or "Unknown", address=venue_address, lat=lat, lon=lon)

    return Event(
        title=title,
        start_dt=start_dt,
        end_dt=end_dt,
        venue=venue,
        city=city,
        category=category,
        price_min_byn=None,
        price_max_byn=None,
        is_free=None,
        age=None,
        link=url,
        source="minsktourism",
        source_uid=None,
        cover_url=cover_url,
        description=description,
        images=images or None,
        fetched_at=_now_iso(),
    )


def harvest_minsktourism(client: HttpClient, geocoder: Geocoder, limit: int = 50) -> List[Event]:
    results: List[Event] = []
    list_url = urljoin(BASE, "afisha/")
    visited = 0
    while list_url and visited < 5 and len(results) < limit:
        try:
            html = client.get(list_url).text
        except Exception:
            break
        links = _parse_list(html)
        for url in links:
            if len(results) >= limit:
                break
            try:
                detail = client.get(url).text
                ev = _parse_detail(url, detail, geocoder)
                if ev:
                    results.append(ev)
            except Exception:
                continue
        soup = BeautifulSoup(html, "lxml")
        next_a = soup.select_one('a[rel="next"], .pagination a.next, a[aria-label="Next"]')
        list_url = urljoin(list_url, next_a.get('href')) if next_a and next_a.get('href') else None
        visited += 1
    return results


