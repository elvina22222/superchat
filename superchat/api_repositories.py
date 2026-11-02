"""Phase 2 data sources: repositories that call real HTTP APIs.

They implement the SAME interfaces as the JSON repositories, so the router, modules and UI do not
change. Which source is used is decided in `build_repositories()` from environment variables
(see README → "Real APIs").

* AviasalesFlightRepository - the public Aviasales Data API (Travelpayouts, /aviasales/v3/prices_for_dates).
* HttpFlightRepository / HttpProductRepository / HttpShowtimeRepository - REST clients for the
  organisers' APIs, following the contract in docs/API_CONTRACT.md (field names = the mock dataset).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .http_client import HttpClient
from .repositories import (DataSourceError, FlightRepository, ProductRepository, Repositories, ShowtimeRepository,
                           JsonFlightRepository, JsonProductRepository, JsonShowtimeRepository)

# ------------------------------------------------------------------------------- Aviasales (real, public)
AIRLINE_NAMES = {"J2": "Azerbaijan Airlines", "TK": "Turkish Airlines", "PC": "Pegasus", "FZ": "flydubai",
                 "EK": "Emirates", "SU": "Aeroflot", "HY": "Uzbekistan Airways", "A9": "Georgian Airways",
                 "BA": "British Airways", "QR": "Qatar Airways", "LH": "Lufthansa", "W6": "Wizz Air",
                 "G9": "Air Arabia", "AJ": "AZAL", "U6": "Ural Airlines", "S7": "S7 Airlines"}
DEFAULT_CITIES = {"GYD": "Baku", "IST": "Istanbul", "DXB": "Dubai", "MOW": "Moscow", "SVO": "Moscow",
                  "TBS": "Tbilisi", "TAS": "Tashkent", "LON": "London", "LHR": "London", "ALA": "Almaty",
                  "TSE": "Astana", "DOH": "Doha", "AYT": "Antalya", "PAR": "Paris", "BER": "Berlin", "ROM": "Rome"}


class AviasalesFlightRepository(FlightRepository):
    """Real flight prices from Aviasales.

    Limits of this public API (shown honestly in the chat): prices are the cheapest fares found by
    users in the last 48 hours, not live inventory; it has no seat counts, no baggage allowance and
    no booking endpoint. 'Reserve' therefore hands the user over to Aviasales with a deep link.
    """
    BASE = "https://api.travelpayouts.com"

    def __init__(self, token: str, currency: str = "azn", cities: Optional[dict] = None, client: Optional[HttpClient] = None,
                 default_month: str = "2026-11"):
        self.client = client or HttpClient(self.BASE, headers={"X-Access-Token": token}, min_interval=0.1, cache_ttl=300)
        self.currency = currency
        self._cities = cities or DEFAULT_CITIES
        self._seen: dict[str, dict] = {}
        self.default_month = default_month

    def _map(self, row: dict) -> dict:
        dep = row["departure_at"]                                  # e.g. 2026-11-06T07:30:00+04:00 (local time)
        code = f"{row.get('airline', '')}{row.get('flight_number', '')}"
        dur = row.get("duration_to") or row.get("duration") or 0
        f = {
            "id": f"AS-{code}-{dep[:16]}",
            "airline": AIRLINE_NAMES.get(row.get("airline"), row.get("airline", "?")),
            "flight_number": code,
            "origin": {"code": row.get("origin_airport") or row["origin"],
                       "city": self._cities.get(row["origin"], row["origin"])},
            "destination": {"code": row.get("destination_airport") or row["destination"],
                            "city": self._cities.get(row["destination"], row["destination"])},
            "departure_local": dep[:16],
            "arrival_local": None,              # the API gives no arrival time; shown as "—", never guessed
            "duration_min": dur,
            "stops": row.get("transfers", 0),
            "via": None,
            "price_azn": float(row["price"]),
            "cabin": "economy",
            "baggage_kg": None,                 # not provided by this API
            "seats_available": None,            # not provided by this API
            "link": "https://www.aviasales.com" + row["link"] if row.get("link") else None,
        }
        self._seen[f["id"]] = f
        return f

    def search(self, origin=None, destination=None, date=None):
        payload = self.client.get("/aviasales/v3/prices_for_dates", {
            "origin": origin, "destination": destination, "departure_at": date or self.default_month,
            "one_way": "true", "currency": self.currency, "sorting": "price", "limit": 30})
        if not isinstance(payload, dict) or not payload.get("success"):
            raise DataSourceError(f"aviasales: {payload.get('error') if isinstance(payload, dict) else 'bad response'}")
        rows = [self._map(r) for r in payload.get("data") or []]
        if date:
            rows = [r for r in rows if r["departure_local"].startswith(date)]
        return rows

    def get(self, flight_id):
        return dict(self._seen[flight_id]) if flight_id in self._seen else None

    def reserve(self, flight_id, passengers):
        f = self._seen.get(flight_id)
        if not f:
            raise DataSourceError("unknown flight")
        return {"ok": True, "handoff": True, "link": f["link"], "flight_id": flight_id, "passengers": passengers,
                "total_azn": round(f["price_azn"] * passengers, 2), "reference": None}

    def cities(self):
        return dict(self._cities)

    def airlines(self):
        return sorted(set(AIRLINE_NAMES.values()))


# ------------------------------------------------------------------------- organisers' REST APIs (contract)
def _client(url: str, key: Optional[str], cache_ttl: float) -> HttpClient:
    return HttpClient(url, headers={"Authorization": f"Bearer {key}"} if key else {}, cache_ttl=cache_ttl,
                      min_interval=0.02)


class HttpFlightRepository(FlightRepository):
    def __init__(self, url: str, key: Optional[str] = None, client: Optional[HttpClient] = None):
        self.client = client or _client(url, key, cache_ttl=30)
        self._airports = None

    def search(self, origin=None, destination=None, date=None):
        return list(self.client.paginate("/flights", {"origin": origin, "destination": destination, "date": date}))

    def get(self, flight_id):
        return self.client.get(f"/flights/{flight_id}")

    def reserve(self, flight_id, passengers):
        r = self.client.post(f"/flights/{flight_id}/reservations", {"passengers": passengers})
        self.client.clear_cache()            # seat counts changed
        return r

    def cities(self):
        if self._airports is None:
            self._airports = {a["code"]: a["city"] for a in self.client.paginate("/airports")}
        return dict(self._airports)

    def airlines(self):
        return sorted({f["airline"] for f in self.search()})


class HttpProductRepository(ProductRepository):
    def __init__(self, url: str, key: Optional[str] = None, client: Optional[HttpClient] = None):
        self.client = client or _client(url, key, cache_ttl=60)

    def all(self):
        return list(self.client.paginate("/products"))

    def get(self, product_id):
        return self.client.get(f"/products/{product_id}")


class HttpShowtimeRepository(ShowtimeRepository):
    def __init__(self, url: str, key: Optional[str] = None, client: Optional[HttpClient] = None):
        self.client = client or _client(url, key, cache_ttl=15)

    def movies(self):
        return list(self.client.paginate("/movies"))

    def cinemas(self):
        return list(self.client.paginate("/cinemas"))

    def showtimes(self, movie_id=None, date=None, cinema_id=None):
        rows = list(self.client.paginate("/showtimes", {"movie_id": movie_id, "date": date, "cinema_id": cinema_id}))
        return sorted(rows, key=lambda s: (s["date"], s["time"]))

    def get_showtime(self, showtime_id):
        return self.client.get(f"/showtimes/{showtime_id}")

    def reserve(self, showtime_id, seats):
        r = self.client.post(f"/showtimes/{showtime_id}/reservations", {"seats": seats})
        self.client.clear_cache()
        return r


# ------------------------------------------------------------------------------------ source selection
def build_from_env(data_dir: Path, env: Optional[dict] = None) -> Repositories:
    """Pick each data source from the environment; anything not configured stays on the mock JSON files.

    AVIASALES_TOKEN=...                      -> real Aviasales prices for flights
    FLIGHTS_API_URL / FLIGHTS_API_KEY        -> organisers' flights API (takes priority over Aviasales)
    SHOP_API_URL / SHOP_API_KEY              -> e-commerce API
    CINEMA_API_URL / CINEMA_API_KEY          -> CinemaPlus API
    """
    env = os.environ if env is None else env
    if env.get("FLIGHTS_API_URL"):
        flights = HttpFlightRepository(env["FLIGHTS_API_URL"], env.get("FLIGHTS_API_KEY"))
    elif env.get("AVIASALES_TOKEN"):
        flights = AviasalesFlightRepository(env["AVIASALES_TOKEN"], env.get("AVIASALES_CURRENCY", "azn"))
    else:
        flights = JsonFlightRepository(data_dir)
    products = HttpProductRepository(env["SHOP_API_URL"], env.get("SHOP_API_KEY")) if env.get("SHOP_API_URL") \
        else JsonProductRepository(data_dir)
    cinema = HttpShowtimeRepository(env["CINEMA_API_URL"], env.get("CINEMA_API_KEY")) if env.get("CINEMA_API_URL") \
        else JsonShowtimeRepository(data_dir)
    return Repositories(flights, products, cinema)


def describe(repos: Repositories) -> str:
    return " | ".join(f"{name}: {type(r).__name__}" for name, r in
                      (("flights", repos.flights), ("shopping", repos.products), ("cinema", repos.cinema)))
