"""SuperChat orchestrator: language -> route -> module(s) -> one reply."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .entities import EntityIndex
from .modules.base import Turn
from .modules.cinema import CinemaModule
from .modules.flights import FlightsModule
from .modules.shopping import ShoppingModule
from .nlp import count_in, detect_language, norm
from .repositories import DataSourceError, Repositories, build_repositories
from .router import RuleRouter
from .state import SessionStore

log = logging.getLogger("superchat")

TEXT = {
    "greeting": {"en": "Hi! I’m SuperChat. I can find flights ✈️, products 🛍️ and cinema showtimes 🎬 — just ask in one chat.",
                 "az": "Salam! Mən SuperChat-am. Uçuşlar ✈️, məhsullar 🛍️ və kino seansları 🎬 üzrə kömək edə bilərəm.",
                 "ru": "Привет! Я SuperChat. Помогу с авиабилетами ✈️, товарами 🛍️ и сеансами в кино 🎬 — всё в одном чате."},
    "oos": {"en": "Sorry, I can’t help with that. I can search flights, shop for products, or find films and showtimes.",
            "az": "Bağışlayın, bu mövzuda kömək edə bilmirəm. Uçuş, məhsul və ya kino seansı axtara bilərəm.",
            "ru": "Извините, с этим я помочь не могу. Я ищу авиабилеты, товары, фильмы и сеансы."},
    "ambiguous": {"en": "Do you mean a flight, a product, or a film?",
                  "az": "Uçuşu, məhsulu, yoxsa filmi nəzərdə tutursunuz?",
                  "ru": "Вы имеете в виду рейс, товар или фильм?"},
    "ambiguous_book": {"en": "What should I book{n} — a flight or a film? If a film, which one and when?",
                       "az": "Nəyi bron edim{n} — uçuş, yoxsa film? Filmdirsə, hansı və nə vaxt?",
                       "ru": "Что забронировать{n} — рейс или фильм? Если фильм — какой и когда?"},
    "ambiguous_ctx": {"en": "Do you mean the {a} or the {b}?", "az": "{a}, yoxsa {b} nəzərdə tutursunuz?",
                      "ru": "Вы про {a} или про {b}?"},
    "dom": {"en": {"flights": "flight", "shopping": "products", "cinema": "film"},
            "az": {"flights": "uçuşu", "shopping": "məhsulu", "cinema": "filmi"},
            "ru": {"flights": "рейс", "shopping": "товары", "cinema": "фильм"}},
    "error": {"en": "Sorry, I couldn’t reach that service just now. Please try again in a moment.",
              "az": "Bağışlayın, xidmətə hazırda qoşulmaq alınmadı. Bir az sonra yenidən cəhd edin.",
              "ru": "Извините, сервис сейчас недоступен. Попробуйте ещё раз чуть позже."},
}
HEAD = {"flights": "✈️", "shopping": "🛍️", "cinema": "🎬"}


class SuperChat:
    def __init__(self, data_dir: Path | str = Path(__file__).resolve().parent.parent / "data",
                 repos: Optional[Repositories] = None):
        self.repos = repos or build_repositories(Path(data_dir))
        self.entities = EntityIndex(self.repos)
        self.router = RuleRouter(self.entities)
        self.modules = {m.name: m for m in (FlightsModule(self.repos, self.entities),
                                            ShoppingModule(self.repos, self.entities),
                                            CinemaModule(self.repos, self.entities))}
        self.sessions = SessionStore()

    def handle(self, session_id: Optional[str], message: str) -> dict:
        session = self.sessions.get(session_id)
        message = (message or "").strip()[:1000]
        lang = detect_language(message) or session.lang
        session.lang = lang
        t = norm(message)

        # an earlier clarifying question gets answered: merge the two messages
        if session.pending:
            first = self.router.route(t, session)
            if first.category in ("flights", "shopping", "cinema", "followup") and len(t.split()) <= 6:
                t = norm(session.pending["text"]) + " " + t
            session.pending = None

        decision = self.router.route(t, session)
        cat = decision.category
        try:
            if cat in ("flights", "shopping", "cinema", "followup"):
                dom = decision.domains[0]
                reply = self.modules[dom].handle(Turn(message, t, lang, cat), session)
                session.last_domain = dom
            elif cat == "mixed":
                parts = []
                for dom in decision.domains:
                    clause = decision.clauses.get(dom, t)
                    parts.append(f"{HEAD[dom]} " + self.modules[dom].handle(Turn(message, clause, lang, dom), session))
                    session.last_domain = dom
                reply = "\n\n".join(parts)
            elif cat == "ambiguous":
                session.pending = {"text": message}
                reply = self._clarify(t, lang, session)
            elif cat == "greeting":
                reply = TEXT["greeting"][lang]
            else:
                reply = TEXT["oos"][lang]
        except DataSourceError:
            log.exception("data source failed")
            reply = TEXT["error"][lang]
        except Exception:  # never let a bug break the chat
            log.exception("unexpected error")
            reply = TEXT["error"][lang]

        reply = reply[:1].upper() + reply[1:] if reply else reply
        turn = {"user": message, "reply": reply, "category": cat, "domains": decision.domains, "lang": lang,
                "cues": decision.cues[:8]}
        session.history.append(turn)
        return {"session_id": session.id, **turn, "state": session.snapshot()}

    def _clarify(self, t: str, lang: str, session) -> str:
        from . import lexicon as L
        from .nlp import has
        if has(t, *L.BOOKING):
            n = count_in(t)
            ntxt = {"en": f" ({n})", "az": f" ({n})", "ru": f" ({n})"}[lang] if n else ""
            return TEXT["ambiguous_book"][lang].format(n=ntxt)
        active = [d for d in ("flights", "shopping", "cinema") if session.has_state(d)]
        if len(active) >= 2:
            names = TEXT["dom"][lang]
            return TEXT["ambiguous_ctx"][lang].format(a=names[active[-2]], b=names[active[-1]])
        return TEXT["ambiguous"][lang]
