from __future__ import annotations
import argparse
from typing import List

from src.utils.http import HttpClient
from src.core.models import Event
from src.core.dedupe import build_event_key
from src.core.geocode import Geocoder, DummyGeocoder
from src.adapters.relax import harvest_relax
from src.adapters.bez_kassira import harvest_bezkassira
from src.adapters.ticketpro import harvest_ticketpro
from src.adapters.belarus_by import harvest_belarus_by
from src.adapters.minsk_tourism import harvest_minsktourism
from src.adapters.virtualbrest import harvest_virtualbrest
from src.adapters.vitebsk_biz import harvest_vitebsk_biz


def write_jsonl(path: str, events: List[Event]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        for e in events:
            f.write(e.model_dump_json(ensure_ascii=False) + "\n")


SOURCES = {
    "relax": harvest_relax,
    "bezkassira": harvest_bezkassira,
    "ticketpro": harvest_ticketpro,
    "belarus.by": harvest_belarus_by,
    "minsktourism": harvest_minsktourism,
    "virtualbrest": harvest_virtualbrest,
    "vitebsk.biz": harvest_vitebsk_biz,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Belarus Events Harvester")
    parser.add_argument("--sources", type=str, default="relax", help="comma-separated sources")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", type=str, default="/Users/amal/Downloads/1/outputs/events.jsonl")
    parser.add_argument("--no-geocode", action="store_true", help="disable geocoding")
    args = parser.parse_args()

    client = HttpClient()
    geocoder = DummyGeocoder() if args.no_geocode else Geocoder()

    selected = [s.strip() for s in args.sources.split(',') if s.strip()]
    events: List[Event] = []

    for src in selected:
        if src not in SOURCES:
            print(f"Unknown source: {src}")
            continue
        events.extend(SOURCES[src](client, geocoder, args.limit))

    # Дедупликация на выходе
    seen = set()
    unique_events: List[Event] = []
    for e in events:
        key = build_event_key(e.title, e.start_dt, e.venue.name, e.source_uid)
        if key in seen:
            continue
        seen.add(key)
        unique_events.append(e)

    write_jsonl(args.out, unique_events)
    print(f"Wrote {len(unique_events)} events to {args.out}")


if __name__ == "__main__":
    main()


