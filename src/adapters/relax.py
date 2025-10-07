from __future__ import annotations
from typing import List, Optional, Tuple
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


BASE = "https://afisha.relax.by/"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_list(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    links: List[str] = []
    # Ищем ссылки на детальные карточки событий
    for a in soup.select("a[href*='/event/']"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(BASE, href)
        links.append(full)
    # Удаляем дубликаты, сохраняя порядок
    seen = set()
    unique = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        unique.append(u)
    return unique


def _parse_detail(url: str, html: str, geocoder: Geocoder) -> Optional[Event]:
    soup = BeautifulSoup(html, "lxml")

    # Попытка разобрать JSON-LD со схемой Event
    jsonld_title = None
    jsonld_start = None
    jsonld_end = None
    jsonld_address = None
    jsonld_city = None
    jsonld_image = None
    jsonld_desc = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            import json as _json
            data = _json.loads(script.get_text() or "{}")
            if isinstance(data, dict) and data.get("@type") in ("Event",):
                jsonld_title = data.get("name") or jsonld_title
                jsonld_start = data.get("startDate") or jsonld_start
                jsonld_end = data.get("endDate") or jsonld_end
                jsonld_image = (data.get("image") or jsonld_image)
                jsonld_desc = data.get("description") or jsonld_desc
                loc = data.get("location") or {}
                addr = (loc.get("address") if isinstance(loc, dict) else None) or {}
                if isinstance(addr, dict):
                    jsonld_address = addr.get("streetAddress") or jsonld_address
                    jsonld_city = addr.get("addressLocality") or jsonld_city
        except Exception:
            continue

    title = clean_text(jsonld_title) or clean_text(soup.select_one("h1") and soup.select_one("h1").get_text())
    if not title:
        # fallback для некоторых страниц
        title = clean_text(soup.select_one("meta[property='og:title']") and soup.select_one("meta[property='og:title']").get("content"))
    if not title:
        return None

    # Дата/время: пробуем найти элемент со временем
    start_dt = parse_datetime(jsonld_start) if jsonld_start else None
    end_dt = parse_datetime(jsonld_end) if jsonld_end else None
    date_nodes = soup.select("time, .event-date, .date, .schedule")
    for node in date_nodes:
        txt = clean_text(node.get_text())
        val = parse_datetime(txt)
        if val and not start_dt:
            start_dt = val
        elif val and not end_dt:
            end_dt = val
    # если ничего не нашли — пробуем og:updated_time как суррогат (не идеально)
    if not start_dt:
        meta_time = soup.select_one("meta[property='event:start_time']") or soup.select_one("meta[property='og:updated_time']")
        if meta_time and meta_time.get("content"):
            start_dt = parse_datetime(meta_time.get("content"))
    if not start_dt:
        # невозможно нормализовать без даты
        return None

    # Площадка: имя и адрес
    venue_name = None
    venue_address = jsonld_address
    # частые места: .place, .venue, .location
    v_name_node = soup.select_one(".place, .venue, .location a, .location")
    if v_name_node:
        venue_name = clean_text(v_name_node.get_text())
    # адрес
    addr_node = soup.select_one(".address, .place-address, .venue-address")
    if addr_node:
        venue_address = clean_text(addr_node.get_text())
    if not venue_name:
        # fallback из меты
        meta_site = soup.select_one("meta[property='business:contact_data:street_address']")
        if meta_site and meta_site.get("content"):
            venue_name = clean_text(meta_site.get("content"))
    if not venue_name:
        venue_name = ""

    # Город из хлебных крошек/заголовков
    city = jsonld_city
    crumbs = soup.select(".breadcrumbs a, .crumbs a")
    for a in crumbs:
        t = (a.get_text() or "").strip()
        if t and len(t) > 2 and t[0].isupper():
            if t.lower() in ("афиша", "календарь"):
                continue
            city = t
            break

    # Категория
    category = None
    cat_node = soup.select_one(".category, .rubric, .tags a")
    if cat_node:
        category = clean_text(cat_node.get_text())

    # Цена/возраст
    price_text_candidates = [
        n.get_text() for n in soup.select(".price, .prices, .ticket-price, .cost")
    ]
    price_text = clean_text(" ".join(price_text_candidates)) if price_text_candidates else None
    price_min, price_max, is_free = parse_price_byn(price_text)

    age_text = clean_text(
        (soup.select_one(".age-limit") and soup.select_one(".age-limit").get_text())
        or (soup.select_one(".age") and soup.select_one(".age").get_text())
    )
    age = parse_age(age_text)

    # Обложка и изображения, описание
    cover_url, images = extract_meta(soup)
    if isinstance(jsonld_image, str):
        cover_url = cover_url or jsonld_image
    description = clean_text(jsonld_desc) if jsonld_desc else None
    desc_node = soup.select_one(".description, .event-description, article, .content")
    if desc_node:
        description = clean_text(desc_node.get_text())

    # Геокодирование
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
        source="relax",
        source_uid=None,
        cover_url=cover_url,
        description=description,
        images=images or None,
        fetched_at=_now_iso(),
    )


def harvest_relax(client: HttpClient, geocoder: Geocoder, limit: int = 50) -> List[Event]:
    results: List[Event] = []
    # Перебираем несколько потенциальных лент: корень, город, город+рубрики
    sections = ["concert", "theatre", "exhibition", "festival"]
    list_urls: List[str] = [BASE, urljoin(BASE, "minsk/")]
    list_urls += [urljoin(BASE, f"minsk/{s}/") for s in sections]

    for list_url in list_urls:
        if len(results) >= limit:
            break
        try:
            html = client.get(list_url).text
        except Exception:
            continue
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
    return results


