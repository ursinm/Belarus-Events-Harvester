from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field


class Venue(BaseModel):
    name: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class Event(BaseModel):
    title: str
    start_dt: str  # ISO8601
    end_dt: Optional[str] = None  # ISO8601
    venue: Venue
    city: Optional[str] = None
    category: Optional[str] = None
    price_min_byn: Optional[float] = None
    price_max_byn: Optional[float] = None
    is_free: Optional[bool] = None
    age: Optional[str] = None
    link: HttpUrl
    source: str
    source_uid: Optional[str] = None
    cover_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    images: Optional[List[HttpUrl]] = None
    fetched_at: str = Field(..., description="ISO8601 time of fetch")
