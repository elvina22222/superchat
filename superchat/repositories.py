"""Data access layer.

Every module talks to data ONLY through these interfaces. Phase 1 uses the
JSON implementations below; in Phase 2 a class such as `AviasalesFlightRepository`
implements the same methods against the real API (auth, paging, caching), and
`build_repositories()` is the only place that changes.
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


class DataSourceError(Exception):
    """Raised by a repository when its source fails. Never shown raw to users."""


# --------------------------------------------------------------------- interfaces
class FlightRepository(ABC):
    @abstractmethod
    def search(self, origin: Optional[str] = None, destination: Optional[str] = None,
               date: Optional[str] = None) -> list[dict]: ...
    @abstractmethod
    def get(self, flight_id: str) -> Optional[dict]: ...
    @abstractmethod
    def reserve(self, flight_id: str, passengers: int) -> dict: ...
    @abstractmethod
    def cities(self) -> dict[str, str]:
        """IATA code -> city name for every airport the source knows."""
    @abstractmethod
    def airlines(self) -> list[str]: ...


class ProductRepository(ABC):
    @abstractmethod
    def all(self) -> list[dict]: ...
    @abstractmethod
    def get(self, product_id: str) -> Optional[dict]: ...


class ShowtimeRepository(ABC):
    """Covers movies, cinemas and showtimes (CinemaPlus exposes them together)."""
    @abstractmethod
    def movies(self) -> list[dict]: ...
    @abstractmethod
    def cinemas(self) -> list[dict]: ...
    @abstractmethod
    def showtimes(self, movie_id: Optional[str] = None, date: Optional[str] = None,
                  cinema_id: Optional[str] = None) -> list[dict]: ...
    @abstractmethod
    def get_showtime(self, showtime_id: str) -> Optional[dict]: ...
    @abstractmethod
    def reserve(self, showtime_id: str, seats: int) -> dict: ...


# ------------------------------------------------------------- JSON (mock) impls
def _load(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise DataSourceError(f"cannot read {path.name}") from exc


_booking_lock = threading.Lock()
_booking_counter = {"F": 0, "T": 0}


def _next_ref(prefix: str) -> str:
    with _booking_lock:
        _booking_counter[prefix] += 1
        return f"{prefix}-{1000 + _booking_counter[prefix]}"


class JsonFlightRepository(FlightRepository):
    def __init__(self, data_dir: Path):
        self._rows = _load(data_dir / "flights.json")

    def search(self, origin=None, destination=None, date=None):
        out = []
        for f in self._rows:
            if origin and f["origin"]["code"] != origin:
                continue
            if destination and f["destination"]["code"] != destination:
                continue
            if date and not f["departure_local"].startswith(date):
                continue
            out.append(dict(f))
        return out

    def get(self, flight_id):
        return next((dict(f) for f in self._rows if f["id"] == flight_id), None)

    def reserve(self, flight_id, passengers):
        with _booking_lock:
            f = next((f for f in self._rows if f["id"] == flight_id), None)
            if f is None:
                raise DataSourceError("unknown flight")
            if f["seats_available"] < passengers:
                return {"ok": False, "seats_available": f["seats_available"]}
            f["seats_available"] -= passengers
        return {"ok": True, "reference": _next_ref("F"), "flight_id": flight_id,
                "passengers": passengers, "total_azn": round(f["price_azn"] * passengers, 2)}

    def cities(self):
        out = {}
        for f in self._rows:
            for side in ("origin", "destination"):
                out[f[side]["code"]] = f[side]["city"]
            if f.get("via"):
                out.setdefault(f["via"], f["via"])
        return out

    def airlines(self):
        return sorted({f["airline"] for f in self._rows})


class JsonProductRepository(ProductRepository):
    def __init__(self, data_dir: Path):
        self._rows = _load(data_dir / "products.json")

    def all(self):
        return [dict(p) for p in self._rows]

    def get(self, product_id):
        return next((dict(p) for p in self._rows if p["id"] == product_id), None)


class JsonShowtimeRepository(ShowtimeRepository):
    def __init__(self, data_dir: Path):
        self._movies = _load(data_dir / "movies.json")
        self._cinemas = _load(data_dir / "cinemas.json")
        self._shows = _load(data_dir / "showtimes.json")

    def movies(self):
        return [dict(m) for m in self._movies]

    def cinemas(self):
        return [dict(c) for c in self._cinemas]

    def showtimes(self, movie_id=None, date=None, cinema_id=None):
        out = []
        for s in self._shows:
            if movie_id and s["movie_id"] != movie_id:
                continue
            if date and s["date"] != date:
                continue
            if cinema_id and s["cinema_id"] != cinema_id:
                continue
            out.append(dict(s))
        return sorted(out, key=lambda s: (s["date"], s["time"]))

    def get_showtime(self, showtime_id):
        return next((dict(s) for s in self._shows if s["id"] == showtime_id), None)

    def reserve(self, showtime_id, seats):
        with _booking_lock:
            s = next((s for s in self._shows if s["id"] == showtime_id), None)
            if s is None:
                raise DataSourceError("unknown showtime")
            if s["seats_available"] < seats:
                return {"ok": False, "seats_available": s["seats_available"]}
            s["seats_available"] -= seats
        return {"ok": True, "reference": _next_ref("T"), "showtime_id": showtime_id,
                "seats": seats, "total_azn": round(s["price_azn"] * seats, 2)}


@dataclass
class Repositories:
    flights: FlightRepository
    products: ProductRepository
    cinema: ShowtimeRepository


def build_repositories(data_dir: Path, env: Optional[dict] = None) -> Repositories:
    """Single switch point between mock data (Phase 1) and real APIs (Phase 2).
    With no API variables set, everything runs on the JSON files. See api_repositories.build_from_env."""
    from .api_repositories import build_from_env
    return build_from_env(data_dir, env)
