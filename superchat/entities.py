"""Entity index built from the repositories at start-up (cities, airlines, brands,
product names, movie titles, cinemas). Because it is built from data, adding a
city or film to the source automatically makes the router and modules aware of it."""
from __future__ import annotations

import re
from typing import Optional

from .nlp import norm, has
from .repositories import Repositories

# Extra spellings/inflections for known airports. Unknown codes still match by city name.
CITY_ALIASES = {
    "GYD": [r"baku", r"baki\w*", r"баку", r"gyd"],
    "IST": [r"istanbul\w*", r"стамбул\w*", r"ist\b"],
    "DXB": [r"dubai", r"dubay\w*", r"дубай\w*", r"dxb"],
    "SVO": [r"moscow", r"moskva\w*", r"москв\w*", r"svo"],
    "TBS": [r"tbilisi\w*", r"tiflis\w*", r"тбилиси", r"tbs"],
    "LHR": [r"london\w*", r"лондон\w*", r"lhr"],
    "TAS": [r"tashkent\w*", r"taskent\w*", r"ташкент\w*", r"tas\b"],
}
_FROM_BEFORE = re.compile(r"(?:from|из|от|с)\s*$")
_TO_BEFORE = re.compile(r"(?:to|into|в|во|до|на|->|–|-)\s*$")
_FROM_SUFFIX = re.compile(r"(?:dan|den|nan|nen)$")
_TO_SUFFIX = re.compile(r"(?:ya|ye|a|e)$")

_BASE_FORMS = {"baki", "baku", "moskva", "dubay", "dubai", "tiflis", "tbilisi", "istanbul", "london", "tashkent", "taskent"}
_TITLE_STOP = {"spring", "track", "laugh", "paper", "last", "deep", "iron", "zero", "midnight"}


class EntityIndex:
    def __init__(self, repos: Repositories):
        self.city_names = repos.flights.cities()
        self.city_patterns: dict[str, list[str]] = {}
        for code, city in self.city_names.items():
            pats = list(CITY_ALIASES.get(code, []))
            pats.append(re.escape(norm(city)) + r"\w*")
            self.city_patterns[code] = pats
        self.airlines = repos.flights.airlines()
        self.flight_numbers = {}
        for f in repos.flights.search():
            self.flight_numbers.setdefault(f["flight_number"].lower(), []).append(f["id"])

        self.products = repos.products.all()
        self.brands = sorted({p["brand"] for p in self.products})
        self.colors = sorted({p["color"] for p in self.products})

        self.movies = repos.cinema.movies()
        self.movie_patterns: dict[str, list[str]] = {}
        for m in self.movies:
            title = norm(m["title"])
            pats = [re.escape(title)]
            if title.startswith("the "):
                pats.append(re.escape(title[4:]))
            for tok in title.split():
                if len(tok) >= 5 and tok not in _TITLE_STOP:
                    pats.append(re.escape(tok) + r"\b")
            self.movie_patterns[m["id"]] = pats
        self.cinemas = repos.cinema.cinemas()
        self.cinema_patterns = {}
        for c in self.cinemas:
            short = norm(c["name"].replace("CinemaPlus", "")).strip()
            pats = [re.escape(norm(c["name"])), re.escape(short)]
            first = short.split()[0]
            pats += {"ganjlik": [r"ganjlik\w*", r"gencli\w*", r"гянджлик\w*"],
                     "sumgayit": [r"sumgayit\w*", r"sumqayit\w*", r"сумгаит\w*", r"сумгайыт\w*"],
                     "28": [r"28 mall", r"28 молл", r"28 мол\w*"]}.get(first, [])
            self.cinema_patterns[c["id"]] = pats

    # ----------------------------------------------------------------- flights
    def find_cities(self, t: str) -> list[dict]:
        """Cities in order of appearance with a role guess: 'from', 'to' or None."""
        hits = []
        for code, pats in self.city_patterns.items():
            for p in pats:
                for m in re.finditer(r"(?<![a-zа-я0-9])" + p, t):
                    word = re.match(r"[a-zа-я0-9]+", t[m.start():]).group(0)
                    before = t[:m.start()]
                    role = None
                    if _FROM_BEFORE.search(before):
                        role = "from"
                    elif _TO_BEFORE.search(before):
                        role = "to"
                    elif _FROM_SUFFIX.search(word) and len(word) > 5:
                        role = "from"
                    elif word not in _BASE_FORMS and _TO_SUFFIX.search(word) \
                            and not word.endswith(("i", "u")) and len(word) > 4 and re.match(r"[a-z]", word):
                        role = "to"
                    hits.append({"pos": m.start(), "code": code, "role": role})
                    break
        hits.sort(key=lambda h: h["pos"])
        out, seen = [], set()
        for h in hits:
            if h["code"] not in seen:
                seen.add(h["code"])
                out.append(h)
        return out

    def find_airline(self, t: str) -> Optional[str]:
        for a in self.airlines:
            if has(t, re.escape(norm(a).split()[0])):
                return a
        return None

    def find_flight_number(self, t: str) -> Optional[str]:
        for fn in self.flight_numbers:
            if re.search(r"(?<![a-z0-9])" + fn[:2] + r"\s?-?" + fn[2:] + r"(?!\d)", t):
                return fn
        return None

    # ---------------------------------------------------------------- shopping
    def find_brand(self, t: str) -> Optional[str]:
        return next((b for b in self.brands if has(t, re.escape(norm(b)) + r"\b")), None)

    def find_product_by_name(self, t: str) -> list[str]:
        out = []
        for p in self.products:
            for lang in ("en", "az", "ru"):
                if norm(p["name"][lang]) in t:
                    out.append(p["id"])
                    break
        return out

    # ------------------------------------------------------------------ cinema
    def find_movies(self, t: str) -> list[str]:
        hits = []
        for mid, pats in self.movie_patterns.items():
            for p in pats:
                m = re.search(r"(?<![a-zа-я0-9])" + p, t)
                if m:
                    hits.append((m.start(), mid))
                    break
        return [mid for _, mid in sorted(hits)]

    def mask_movies(self, t: str) -> str:
        """Hide movie titles so 'Hearts in Baku' is not read as a city."""
        for pats in self.movie_patterns.values():
            t = re.sub(pats[0], " ", t)
        return t

    def find_cinema(self, t: str) -> Optional[str]:
        for cid, pats in self.cinema_patterns.items():
            if any(has(t, p) for p in pats if p):
                return cid
        return None
