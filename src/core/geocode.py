from __future__ import annotations
from typing import Optional, Dict, Tuple
import json
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from dotenv import load_dotenv
import os
import ssl
import certifi

CACHE_PATH = Path("/Users/amal/Downloads/1/data/geocache.json")


class Geocoder:
    def __init__(self):
        load_dotenv()
        user_agent = os.getenv("NOMINATIM_USER_AGENT", "belarus-events-harvester/0.1")
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.geocoder = Nominatim(user_agent=user_agent, timeout=10, ssl_context=ssl_context)
        self.rate_limited = RateLimiter(self.geocoder.geocode, min_delay_seconds=1.2)
        self.cache: Dict[str, Tuple[float, float]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if CACHE_PATH.exists():
            try:
                self.cache = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
            except Exception:
                self.cache = {}
        else:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text("{}", encoding='utf-8')

    def _save_cache(self) -> None:
        try:
            CACHE_PATH.write_text(json.dumps(self.cache, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass

    def geocode(self, address: Optional[str], city: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        key = f"{address}|{city}"
        if not address and not city:
            return None, None
        if key in self.cache:
            lat, lon = self.cache[key]
            return float(lat), float(lon)
        query = ", ".join([part for part in [address, city, "Belarus"] if part])
        try:
            loc = self.rate_limited(query)
            if loc and getattr(loc, 'latitude', None) and getattr(loc, 'longitude', None):
                lat = float(loc.latitude)
                lon = float(loc.longitude)
                self.cache[key] = (lat, lon)
                self._save_cache()
                return lat, lon
        except Exception:
            return None, None
        return None, None


class DummyGeocoder:
    def geocode(self, address: Optional[str], city: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        return None, None


