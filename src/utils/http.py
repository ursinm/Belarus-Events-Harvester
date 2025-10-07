from __future__ import annotations
from typing import Optional, Dict
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class HttpClient:
    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)
        self.timeout = timeout

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((requests.RequestException,)),
    )
    def get(self, url: str, params: Optional[Dict[str, str]] = None) -> requests.Response:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code in (429, 503):
            time.sleep(1.5)
        resp.raise_for_status()
        return resp


