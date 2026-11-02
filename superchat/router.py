"""Hybrid rule-based router.

Each message is scored against multilingual cue lists (lexicon.py) and against
entities taken from the data itself (cities, brands, film titles ...). The scores,
plus the session state, decide one of seven categories:

    flights | shopping | cinema | mixed | followup | ambiguous | out_of_scope
    (+ 'greeting' for pure small talk, answered with a short capability note)

The router is deliberately deterministic and explainable: every decision carries
the cues that produced it, which the UI can show and the test log can analyse.
`Router` is an interface, so an LLM- or classifier-based router can be swapped in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from . import lexicon as L
from .entities import EntityIndex
from .nlp import count_in, find_dates, has, ordinal_in, tokens
from .state import DOMAINS, Session


@dataclass
class Decision:
    category: str
    domains: list[str]
    strong: dict = field(default_factory=dict)
    weak: dict = field(default_factory=dict)
    cues: list[str] = field(default_factory=list)
    clauses: dict = field(default_factory=dict)   # domain -> text part (mixed messages)


class Router(Protocol):
    def route(self, text_norm: str, session: Session) -> Decision: ...


def movies_or_products(cues: list[str]) -> bool:
    return any(c.startswith(("movie:", "brand/product", "cinema-name", "airline")) for c in cues)


def _hits(t: str, patterns: list[str]) -> list[str]:
    return [p for p in patterns if has(t, p)]


class RuleRouter:
    def __init__(self, entities: EntityIndex):
        self.e = entities

    # ------------------------------------------------------------------ scoring
    def score(self, t: str) -> tuple[dict, dict, list[str]]:
        cues: list[str] = []
        strong = {d: 0 for d in DOMAINS}
        weak = {d: 0 for d in DOMAINS}

        movies = self.e.find_movies(t)
        masked = self.e.mask_movies(t)
        if movies:
            strong["cinema"] += 2
            cues.append("movie:" + ",".join(movies))
        if self.e.find_cinema(t):
            strong["cinema"] += 2
            cues.append("cinema-name")

        for d, pats in (("flights", L.FLIGHT_STRONG), ("shopping", L.SHOP_STRONG), ("cinema", L.CINEMA_STRONG)):
            h = _hits(masked, pats)
            strong[d] += len(h)
            cues += [f"{d}:{p}" for p in h]
        for d, pats in (("flights", L.FLIGHT_WEAK), ("shopping", L.SHOP_WEAK), ("cinema", L.CINEMA_WEAK)):
            h = _hits(masked, pats)
            weak[d] += len(h)

        cities = self.e.find_cities(masked)
        for c in cities:
            if c["code"] == "GYD" and not c["role"] and len(cities) == 1:
                weak["flights"] += 1          # 'in Baku' alone is not a travel request
            else:
                strong["flights"] += 2
            cues.append("city:" + c["code"])
        if self.e.find_airline(masked) or self.e.find_flight_number(masked):
            strong["flights"] += 2
            cues.append("airline/flight-no")
        if self.e.find_brand(t) or self.e.find_product_by_name(t):
            strong["shopping"] += 2
            cues.append("brand/product")
        return strong, weak, cues

    # ----------------------------------------------------------------- decision
    def route(self, t: str, session: Session) -> Decision:
        strong, weak, cues = self.score(t)
        doms = [d for d in DOMAINS if strong[d] > 0]
        followup = bool(_hits(t, L.FOLLOWUP)) or ordinal_in(t) is not None
        booking = bool(_hits(t, L.BOOKING))
        vague = bool(_hits(t, L.VAGUE))
        oos = bool(_hits(t, L.OUT_OF_SCOPE))
        dates = find_dates(t)
        n_tok = len(tokens(t))

        def dec(cat, ds, extra=None):
            return Decision(cat, ds, strong, weak, cues + ([extra] if extra else []))

        lexical = sum(1 for c in cues if c.split(":")[0] in DOMAINS)   # topic words, not just entities
        if oos and lexical == 0 and not movies_or_products(cues):
            return dec("out_of_scope", [], "oos-cue overrides place name")
        if len(doms) >= 2:
            # a single cinema genre word next to a strong flight/shop request is still mixed
            d = dec("mixed", doms)
            d.clauses = self.split(t, doms)
            return d
        if len(doms) == 1:
            dom = doms[0]
            if followup and session.has_state(dom):
                return dec("followup", [dom], "anaphora+state")
            return dec(dom, [dom])

        # ---- no explicit topic word ---------------------------------------
        if oos:
            return dec("out_of_scope", [], "oos-cue")
        weak_doms = [d for d in DOMAINS if weak[d] > 0]
        if len(weak_doms) == 1:
            dom = weak_doms[0]
            return dec("followup" if session.has_state(dom) else dom, [dom], "weak-cue")

        contextual = followup or booking or bool(dates) or count_in(t) is not None or \
            (vague and has(t, r"how much", r"price", r"qiymet", r"сколько", r"цен"))
        if contextual:
            cands = [d for d in DOMAINS if session.has_state(d)]
            if booking:
                cands = [d for d in cands if d in ("flights", "cinema")] or \
                        ([d for d in cands if d == "shopping"] if has(t, r"buy", r"al\b", r"куп") else [])
            if session.last_domain in cands:
                return dec("followup", [session.last_domain], "context:last-domain")
            if len(cands) == 1:
                return dec("followup", cands, "context:only-domain-with-state")
            return dec("ambiguous", [], "needs-context")
        if vague:
            return dec("ambiguous", [], "vague")
        if _hits(t, L.GREETING) and n_tok <= 6:
            return dec("greeting", [])
        if session.pending and n_tok <= 4:
            return dec("ambiguous", [], "unclear-answer")
        return dec("out_of_scope", [], "no-cue")

    # ------------------------------------------------------- mixed: split text
    def split(self, t: str, doms: list[str]) -> dict:
        """Assign each clause of a mixed message to the domain whose cues it carries."""
        parts = re.split(r"\s*(?:,|;|\band also\b|\band\b|\bplus\b|\balso\b|\bve\b|\bhem de\b|\bи\b|\bа также\b|\bтакже\b)\s+", t)
        out: dict[str, list[str]] = {d: [] for d in doms}
        last = None
        shared_ctx = []
        for part in parts:
            s, _, _ = self.score(part)
            best = max(doms, key=lambda d: s[d])
            if s[best] == 0:
                if last:
                    out[last].append(part)
                else:
                    shared_ctx.append(part)
                continue
            out[best].append(part)
            last = best
        return {d: " ".join(shared_ctx + v) if v else t for d, v in out.items()}
