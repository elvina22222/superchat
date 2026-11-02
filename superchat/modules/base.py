from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..entities import EntityIndex
from ..repositories import Repositories
from ..state import Session


@dataclass
class Turn:
    raw: str
    t: str            # normalised text this module should read (a clause for mixed messages)
    lang: str
    category: str


class Module:
    name = ""
    STR: dict = {}

    def __init__(self, repos: Repositories, entities: EntityIndex):
        self.repos = repos
        self.e = entities

    def s(self, key: str, lang: str, **kw) -> str:
        entry = self.STR[key]
        text = entry.get(lang) or entry["en"]
        return text.format(**kw) if kw else text

    def handle(self, turn: Turn, session: Session) -> str:  # pragma: no cover
        raise NotImplementedError


def pick(items: list, idx: Optional[int]):
    if idx is None or not items:
        return None
    try:
        return items[idx]
    except IndexError:
        return None


def money(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") + " AZN"


def hm(minutes: int, lang: str) -> str:
    h, m = divmod(minutes, 60)
    u = {"en": ("h", "m"), "az": ("s", "dəq"), "ru": ("ч", "мин")}[lang]
    return f"{h}{u[0]} {m:02d}{u[1]}"
