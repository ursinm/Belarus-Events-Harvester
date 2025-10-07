from __future__ import annotations
import hashlib
from typing import Optional


def build_event_key(title: str, start_dt: str, venue_name: str, source_uid: Optional[str]) -> str:
    if source_uid:
        return f"uid::{source_uid}"
    basis = f"{title}|{start_dt}|{venue_name}"
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()


