"""Conversation state: one `Session` per chat, holding shared state plus a
separate, independent state object per domain."""
from __future__ import annotations

import copy
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

DOMAINS = ("flights", "shopping", "cinema")


def _flights() -> dict:
    return {"query": {}, "filters": {}, "results": [], "return_results": [], "selected": None,
            "bookings": [], "history": []}


def _shopping() -> dict:
    return {"query": {}, "results": [], "selected": None, "cart": {}, "history": []}


def _cinema() -> dict:
    return {"query": {}, "movies": [], "movie": None, "showtimes": [], "showtime": None,
            "last_list": None, "bookings": []}


@dataclass
class Session:
    id: str
    lang: str = "en"
    last_domain: Optional[str] = None
    preferences: dict = field(default_factory=dict)   # e.g. passengers, budget, home city
    pending: Optional[dict] = None                     # an unanswered clarifying question
    history: list = field(default_factory=list)        # full transcript, all domains
    domains: dict = field(default_factory=lambda: {"flights": _flights(), "shopping": _shopping(),
                                                    "cinema": _cinema()})

    def has_state(self, domain: str) -> bool:
        s = self.domains[domain]
        if domain == "flights":
            return bool(s["results"] or s["selected"] or s["query"])
        if domain == "shopping":
            return bool(s["results"] or s["selected"] or s["cart"])
        return bool(s["movies"] or s["movie"] or s["showtimes"])

    def snapshot(self) -> dict:
        """Compact view of state for the UI's debug panel."""
        return {"lang": self.lang, "last_domain": self.last_domain, "preferences": self.preferences,
                "pending": self.pending, "domains": copy.deepcopy(self.domains)}


class SessionStore:
    """In-memory store. Phase 2: swap for Redis or a database behind the same two methods."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, session_id: Optional[str]) -> Session:
        with self._lock:
            if not session_id or session_id not in self._sessions:
                session_id = session_id or uuid.uuid4().hex[:12]
                self._sessions[session_id] = Session(id=session_id)
            return self._sessions[session_id]

    def reset(self, session_id: str) -> Session:
        with self._lock:
            self._sessions[session_id] = Session(id=session_id)
            return self._sessions[session_id]
