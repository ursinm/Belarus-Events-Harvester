from __future__ import annotations
from typing import List, Optional
from urllib.parse import urljoin
from datetime import datetime, timezone
import re

from bs4 import BeautifulSoup

from src.utils.http import HttpClient
from src.utils.parse import (
    clean_text,
    parse_datetime,
    parse_price_byn,
    parse_age,
    extract_meta,
)
from src.core.models import Event, Venue
from src.core.geocode import Geocoder
from xml.etree import ElementTree as ET
from src.utils.render import render_html


BASE = "https://www.ticketpro.by/"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_list(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    links: List[str] = []
    # карточки событий часто имеют ссылки в плитках/списках
    for a in soup.select(".event a[href], .events-list a[href], a[href]"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(BASE, href)
        if re.search(r"/(event|ru/Events|ru/Concerts|ru/Theatre|ru/Sport)/", full):
            lf = full.lower()
            if ("minsk" in lf) or ("vitebsk" in lf):
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

    # JSON-LD
    jsonld = None
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            import json as _json
            data = _json.loads(s.get_text() or "{}")
            if isinstance(data, dict) and data.get("@type") in ("Event",):
                jsonld = data
                break
        except Exception:
            continue

    title = clean_text((jsonld or {}).get("name")) if jsonld else None
    if not title:
        title = clean_text(soup.select_one("h1") and soup.select_one("h1").get_text())
    if not title:
        return None

    start_dt = parse_datetime((jsonld or {}).get("startDate")) if jsonld else None
    end_dt = parse_datetime((jsonld or {}).get("endDate")) if jsonld else None
    if not start_dt:
        for n in soup.select("time, .date, .event-date"):
            val = parse_datetime(clean_text(n.get_text()))
            if val and not start_dt:
                start_dt = val
            elif val and not end_dt:
                end_dt = val
    if not start_dt:
        return None

    venue_name = None
    venue_address = None
    city = None
    loc = (jsonld or {}).get("location") if jsonld else None
    if isinstance(loc, dict):
        venue_name = clean_text((loc.get("name") or "") if loc else None)
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            venue_address = clean_text(addr.get("streetAddress"))
            city = clean_text(addr.get("addressLocality")) or city

    if not venue_name:
        vnode = soup.select_one(".venue, .place, .location a, .location")
        if vnode:
            venue_name = clean_text(vnode.get_text())
    if not venue_address:
        anode = soup.select_one(".address, .place-address, .venue-address")
        if anode:
            venue_address = clean_text(anode.get_text())

    category = None
    cnode = soup.select_one(".category, .breadcrumbs a:last-child, .tags a")
    if cnode:
        category = clean_text(cnode.get_text())

    price_text = clean_text(" ".join([n.get_text() for n in soup.select(".price, .prices, .cost")] ))
    price_min, price_max, is_free = parse_price_byn(price_text)

    age = parse_age(clean_text((soup.select_one(".age-limit") or {}).get_text() if soup.select_one(".age-limit") else None))

    cover_url, images = extract_meta(soup)
    if jsonld and isinstance(jsonld.get("image"), str):
        cover_url = cover_url or jsonld.get("image")
    description = clean_text((jsonld or {}).get("description"))
    if not description:
        dnode = soup.select_one(".description, .event-description, article, .content")
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
        price_min_byn=price_min,
        price_max_byn=price_max,
        is_free=is_free,
        age=age,
        link=url,
        source="ticketpro",
        source_uid=None,
        cover_url=cover_url,
        description=description,
        images=images or None,
        fetched_at=_now_iso(),
    )


def harvest_ticketpro(client: HttpClient, geocoder: Geocoder, limit: int = 50) -> List[Event]:
    results: List[Event] = []
    candidate_lists = [
        urljoin(BASE, "ru/Events/"),
        urljoin(BASE, "ru/Concerts/"),
        urljoin(BASE, "ru/Theatre/"),
        urljoin(BASE, "ru/Sport/"),
        urljoin(BASE, "ru/AllEvents/"),
        urljoin(BASE, "ru/All/"),
    ]
    list_url = None
    for url in candidate_lists:
        try:
            client.get(url)
            list_url = url
            break
        except Exception:
            continue
    if not list_url:
        # fallback: sitemap
        try:
            sm = client.get(urljoin(BASE, "sitemap.xml")).text
            root = ET.fromstring(sm)
            urls: List[str] = []
            for loc in root.iter():
                if loc.tag.endswith('loc') and loc.text:
                    u = loc.text.strip()
                    if "/event/" in u or "/Events/" in u:
                        urls.append(u)
            for url in urls:
                if len(results) >= limit:
                    break
                try:
                    detail = client.get(url).text
                    ev = _parse_detail(url, detail, geocoder)
                    if ev:
                        results.append(ev)
                except Exception:
                    continue
        except Exception:
            pass
        return results
    visited_pages = 0
    while list_url and visited_pages < 5 and len(results) < limit:
        if len(results) >= limit:
            break
        try:
            html = client.get(list_url).text
            if len(_parse_list(html)) == 0:
                html = render_html(list_url, wait_selector="a")
        except Exception:
            break
        links = _parse_list(html)
        for url in links:
            if len(results) >= limit:
                break
            try:
                detail = client.get(url).text
                if 'application/ld+json' not in detail and 'time' not in detail:
                    detail = render_html(url, wait_selector="h1")
                ev = _parse_detail(url, detail, geocoder)
                if ev:
                    results.append(ev)
            except Exception:
                continue
        soup = BeautifulSoup(html, "lxml")
        next_a = soup.select_one('a[rel="next"], .pagination a.next, a[aria-label="Next"]')
        list_url = urljoin(list_url, next_a.get('href')) if next_a and next_a.get('href') else None
        visited_pages += 1
    return results


