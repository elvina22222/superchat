"""Small production-style HTTP client for Phase 2 (standard library only).

Handles what the brief lists for real APIs: authentication headers, timeouts, retries with
exponential back-off (429 / 5xx / network errors, honouring Retry-After), a client-side rate
limit, an in-memory TTL cache for GET requests, page-by-page fetching, and logging of every call
with its latency. Every failure is raised as DataSourceError, which the chat turns into a
friendly message.
"""
from __future__ import annotations

import gzip
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterator, Optional

from .repositories import DataSourceError

log = logging.getLogger("superchat.http")


class HttpClient:
    def __init__(self, base_url: str, headers: Optional[dict] = None, timeout: float = 8.0, retries: int = 3,
                 backoff: float = 0.5, min_interval: float = 0.0, cache_ttl: float = 60.0,
                 opener: Optional[Callable] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "User-Agent": "SuperChat/1.0",
                        **(headers or {})}
        self.timeout, self.retries, self.backoff = timeout, retries, backoff
        self.min_interval, self.cache_ttl = min_interval, cache_ttl
        self._open = opener or urllib.request.urlopen     # injectable for tests
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()
        self._last_call = 0.0
        self.stats = {"calls": 0, "cache_hits": 0, "retries": 0, "errors": 0}

    # ---------------------------------------------------------------- internals
    def _throttle(self):
        with self._lock:
            wait = self._last_call + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _url(self, path: str, params: Optional[dict]) -> str:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        return url + ("?" + urllib.parse.urlencode(clean) if clean else "")

    def clear_cache(self):
        self._cache.clear()

    def request(self, method: str, path: str, params: Optional[dict] = None, body: Optional[dict] = None,
                use_cache: bool = True, ok_status: tuple = (), extra_headers: Optional[dict] = None):
        url = self._url(path, params)
        key = f"{method} {url}"
        if method == "GET" and use_cache and self.cache_ttl > 0:
            hit = self._cache.get(key)
            if hit and hit[0] > time.monotonic():
                self.stats["cache_hits"] += 1
                return hit[1]
        data = json.dumps(body).encode() if body is not None else None
        headers = {**self.headers, **(extra_headers or {})}
        if data is not None:
            headers["Content-Type"] = "application/json"
        last_err = "unknown error"
        for attempt in range(self.retries + 1):
            self._throttle()
            t0 = time.monotonic()
            try:
                self.stats["calls"] += 1
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with self._open(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    payload = json.loads(raw.decode("utf-8")) if raw else None
                log.info("%s %s -> %s in %.0f ms", method, _redact(url), getattr(resp, "status", 200),
                         (time.monotonic() - t0) * 1000)
                if method == "GET" and use_cache and self.cache_ttl > 0:
                    self._cache[key] = (time.monotonic() + self.cache_ttl, payload)
                return payload
            except urllib.error.HTTPError as e:
                if e.code in ok_status:                  # e.g. 409 "not enough seats" carries a useful body
                    try:
                        return json.loads(e.read().decode("utf-8"))
                    except (ValueError, OSError):
                        pass
                last_err = f"HTTP {e.code}"
                log.warning("%s %s -> %s (attempt %d)", method, _redact(url), e.code, attempt + 1)
                if e.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    self.stats["retries"] += 1
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    time.sleep(float(retry_after) if retry_after and retry_after.isdigit()
                               else self.backoff * (2 ** attempt))
                    continue
                break                                    # 4xx: retrying will not help
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
                last_err = type(e).__name__
                log.warning("%s %s failed: %s (attempt %d)", method, _redact(url), e, attempt + 1)
                if attempt < self.retries:
                    self.stats["retries"] += 1
                    time.sleep(self.backoff * (2 ** attempt))
                    continue
        self.stats["errors"] += 1
        raise DataSourceError(f"{method} {_redact(url)} failed: {last_err}")

    def get(self, path: str, params: Optional[dict] = None, **kw):
        return self.request("GET", path, params, **kw)

    def post(self, path: str, body: dict, ok_status: tuple = (409,), **kw):
        """POST with an Idempotency-Key, so a retried reservation can never be booked twice."""
        import uuid
        return self.request("POST", path, body=body, use_cache=False, ok_status=ok_status,
                            extra_headers={"Idempotency-Key": uuid.uuid4().hex}, **kw)

    def paginate(self, path: str, params: Optional[dict] = None, items_key: str = "items",
                 page_param: str = "page", max_pages: int = 50) -> Iterator[dict]:
        """Yield items across pages. Stops when a page is empty or the API reports no next page."""
        page = 1
        while page <= max_pages:
            payload = self.get(path, {**(params or {}), page_param: page})
            items = payload.get(items_key, []) if isinstance(payload, dict) else (payload or [])
            yield from items
            if not items or (isinstance(payload, dict) and not payload.get("next_page", len(items) > 0)):
                return
            page = payload.get("next_page", page + 1) if isinstance(payload, dict) else page + 1


def _redact(url: str) -> str:
    """Never write tokens to the logs."""
    parts = urllib.parse.urlsplit(url)
    q = [(k, "***" if k.lower() in ("token", "api_key", "key", "access_token") else v)
         for k, v in urllib.parse.parse_qsl(parts.query)]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(q)))
