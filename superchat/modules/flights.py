from __future__ import annotations

import re

from ..nlp import count_in, find_dates, has, is_question, money_range, ordinal_in, pretty_date
from .base import Module, Turn, hm, money, pick

RESERVE = [r"book\w*", r"reserve\w*", r"bron\w*", r"rezerv\w*", r"заброн\w*", r"бронир\w*", r"оформ\w*",
           r"i'?ll take", r"götür", r"gotur\w*", r"бер[уё]"]
COMPARE = [r"compar\w*", r"vs\b", r"versus", r"difference", r"muqayis\w*", r"ferq\w*", r"сравн\w*", r"разниц\w*"]
DIRECT = [r"direct\w*", r"non-?stop", r"birbasa", r"aktarmasiz", r"прям\w*", r"без пересад\w*"]
CHEAP = [r"cheap\w*", r"lowest price", r"ucuz\w*", r"дешев\w*", r"подешевле"]
FAST = [r"fast\w*", r"shortest", r"quick\w*", r"en tez", r"en qisa", r"быстр\w*", r"короч\w*"]
EARLY = [r"earliest", r"en erken", r"самый ранн\w*"]
MORNING = [r"morning", r"seher\w*", r"утр\w*"]
AFTERNOON = [r"afternoon", r"gunorta\w*", r"днем", r"днём"]
EVENING = [r"evening", r"night", r"axsam\w*", r"gece\w*", r"вечер\w*", r"ноч\w*"]
SELECT_WORDS = CHEAP + DIRECT + FAST + EARLY + MORNING + EVENING + [r"(?:the|that|this) (?:[\w-]+ )?one", r"\bone\b", r"olan", r"тот", r"этот"]
RETURN = [r"return\w*", r"round[- ]trip", r"back on", r"come back", r"geri", r"qayid\w*", r"gedis[- ]qayidis",
          r"обратн\w*", r"туда и обратно", r"вернуться"]
FLIGHTISH = [r"flights?", r"ucus\w*", r"reys\w*", r"рейс\w*", r"перел[её]т\w*"]


class FlightsModule(Module):
    name = "flights"
    STR = {
        "need_route": {"en": "Where would you like to fly, and on which date? For example: “Baku to Istanbul on Friday”.",
                       "az": "Hara və hansı tarixə uçmaq istəyirsiniz? Məsələn: “Cümə günü Bakıdan İstanbula”.",
                       "ru": "Куда и на какую дату вы хотите лететь? Например: «Баку — Стамбул в пятницу»."},
        "need_date": {"en": "Which date should I check for {route}?",
                      "az": "{route} üçün hansı tarixi yoxlayım?",
                      "ru": "На какую дату проверить {route}?"},
        "unknown_city": {"en": "I only have flights between these cities: {cities}.",
                         "az": "Məndə yalnız bu şəhərlər arasında uçuşlar var: {cities}.",
                         "ru": "У меня есть рейсы только между этими городами: {cities}."},
        "results": {"en": "Flights {route}, {date}:", "az": "{route} uçuşları, {date}:", "ru": "Рейсы {route}, {date}:"},
        "results_nodate": {"en": "Flights {route}:", "az": "{route} uçuşları:", "ru": "Рейсы {route}:"},
        "none": {"en": "I found no flights {route} on {date}{filters}.",
                 "az": "{date} tarixində {route} üzrə uçuş tapılmadı{filters}.",
                 "ru": "Рейсов {route} на {date} не найдено{filters}."},
        "other_dates": {"en": "This route does fly on: {dates}.", "az": "Bu istiqamətdə uçuş tarixləri: {dates}.",
                        "ru": "По этому направлению есть рейсы: {dates}."},
        "no_route": {"en": "There are no flights on this route in my data.",
                     "az": "Məlumatlarımda bu istiqamət üzrə uçuş yoxdur.",
                     "ru": "В моих данных нет рейсов по этому направлению."},
        "filtered": {"en": " with these filters", "az": " (seçilmiş filtrlərlə)", "ru": " с этими фильтрами"},
        "direct": {"en": "direct", "az": "birbaşa", "ru": "прямой"},
        "stops": {"en": "{n} stop via {via}", "az": "{n} aktarma ({via})", "ru": "{n} пересадка ({via})"},
        "seats": {"en": "seats left: {n}", "az": "{n} yer qalıb", "ru": "осталось мест: {n}"},
        "seats_unknown": {"en": "seats: check on booking", "az": "yer sayı: bron zamanı", "ru": "места: уточнить при брони"},
        "stops_novia": {"en": "{n} stop", "az": "{n} aktarma", "ru": "пересадок: {n}"},
        "handoff": {"en": "To book {fn} for {n} passenger(s) (about {total}), continue on Aviasales: {link}",
                    "az": "{fn} reysini {n} sərnişin üçün (təxminən {total}) bron etmək üçün Aviasales-də davam edin: {link}",
                    "ru": "Чтобы забронировать {fn} на {n} пасс. (около {total}), продолжите на Aviasales: {link}"},
        "sold_out": {"en": "sold out", "az": "yer qalmayıb", "ru": "мест нет"},
        "pick_hint": {"en": "Say “the cheaper one”, “the second one” or “book the first one”.",
                      "az": "“Ucuz olanı”, “ikincini” və ya “birincini bron et” yaza bilərsiniz.",
                      "ru": "Напишите «подешевле», «второй» или «забронируй первый»."},
        "details": {"en": "{airline} {fn}, {date}\n• {dep} {o} → {arr} {d} ({dur})\n• {stops}\n• Baggage: {bag} kg, {cabin}\n• {seats}\n• Price: {price}",
                    "az": "{airline} {fn}, {date}\n• {dep} {o} → {arr} {d} ({dur})\n• {stops}\n• Baqaj: {bag} kq, {cabin}\n• {seats}\n• Qiymət: {price}",
                    "ru": "{airline} {fn}, {date}\n• {dep} {o} → {arr} {d} ({dur})\n• {stops}\n• Багаж: {bag} кг, {cabin}\n• {seats}\n• Цена: {price}"},
        "is_direct_yes": {"en": "Yes, it is a direct flight.", "az": "Bəli, birbaşa uçuşdur.", "ru": "Да, это прямой рейс."},
        "is_direct_no_novia": {"en": "No, it has {n} stop.", "az": "Xeyr, {n} aktarma var.", "ru": "Нет, пересадок: {n}."},
        "is_direct_no": {"en": "No, it has {n} stop in {via}.", "az": "Xeyr, {via} şəhərində {n} aktarma var.",
                         "ru": "Нет, у него {n} пересадка в {via}."},
        "selected_cheapest": {"en": "The cheapest option is:", "az": "Ən ucuz variant:", "ru": "Самый дешёвый вариант:"},
        "which_flight": {"en": "Which flight should I book? Tell me its number in the list.",
                         "az": "Hansı uçuşu bron edim? Siyahıdakı nömrəsini yazın.",
                         "ru": "Какой рейс забронировать? Назовите номер в списке."},
        "booked": {"en": "Reserved ✅ {fn} on {date}, {n} passenger(s), total {total}. Reference {ref}. (Mock reservation — no payment taken.)",
                   "az": "Bron edildi ✅ {fn}, {date}, {n} sərnişin, cəmi {total}. Kod: {ref}. (Test bronu — ödəniş alınmır.)",
                   "ru": "Забронировано ✅ {fn}, {date}, пассажиров: {n}, итого {total}. Номер брони {ref}. (Тестовая бронь — без оплаты.)"},
        "not_enough": {"en": "Sorry, only {n} seat(s) left on {fn}.", "az": "Təəssüf ki, {fn} reysində cəmi {n} yer qalıb.",
                       "ru": "К сожалению, на {fn} осталось мест: {n}."},
        "compare_head": {"en": "Comparison:", "az": "Müqayisə:", "ru": "Сравнение:"},
        "compare_best": {"en": "Cheapest: {c}. Fastest: {f}.", "az": "Ən ucuz: {c}. Ən sürətli: {f}.",
                         "ru": "Самый дешёвый: {c}. Самый быстрый: {f}."},
        "return_head": {"en": "Return {route}, {date}:", "az": "Geri dönüş {route}, {date}:", "ru": "Обратно {route}, {date}:"},
        "assume_origin": {"en": " (from Baku)", "az": " (Bakıdan)", "ru": " (из Баку)"},
    }

    # ------------------------------------------------------------------ parsing
    def parse(self, t: str, st: dict) -> dict:
        q = {}
        cities = self.e.find_cities(self.e.mask_movies(t))
        if len(cities) >= 2:
            a, b = cities[0], cities[1]
            if a["role"] == "to" or b["role"] == "from":
                a, b = b, a
            q["origin"], q["destination"] = a["code"], b["code"]
        elif len(cities) == 1:
            c = cities[0]
            q["origin" if c["role"] == "from" else "destination"] = c["code"]
        dates = find_dates(t)
        if dates:
            q["date"] = dates[0]
            if len(dates) > 1 and has(t, *RETURN):
                q["return_date"] = dates[1]
        f = {}
        if has(t, *DIRECT):
            f["direct"] = True
        if has(t, *CHEAP):
            f["sort"] = "price"
        elif has(t, *FAST):
            f["sort"] = "duration"
        elif has(t, *EARLY):
            f["sort"] = "departure"
        if has(t, *MORNING):
            f["tod"] = "morning"
        elif has(t, *AFTERNOON):
            f["tod"] = "afternoon"
        elif has(t, *EVENING):
            f["tod"] = "evening"
        al = self.e.find_airline(t)
        if al:
            f["airline"] = al
        _, hi = money_range(t)
        if hi:
            f["max_price"] = hi
        return {"q": q, "f": f}

    def _apply(self, flights: list[dict], f: dict) -> list[dict]:
        out = flights
        if f.get("direct"):
            out = [x for x in out if x["stops"] == 0]
        if f.get("airline"):
            out = [x for x in out if x["airline"] == f["airline"]]
        if f.get("max_price"):
            out = [x for x in out if x["price_azn"] <= f["max_price"]]
        tod = f.get("tod")
        if tod:
            rng = {"morning": (0, 12), "afternoon": (12, 17), "evening": (17, 24)}[tod]
            out = [x for x in out if rng[0] <= int(x["departure_local"][11:13]) < rng[1]]
        key = {"price": lambda x: x["price_azn"], "duration": lambda x: x["duration_min"],
               "departure": lambda x: x["departure_local"]}.get(f.get("sort"), lambda x: x["departure_local"])
        return sorted(out, key=key)

    # ---------------------------------------------------------------- rendering
    def _city(self, code):
        return self.e.city_names.get(code, code)

    def _stops(self, f, lang):
        if f["stops"] == 0:
            return self.s("direct", lang)
        if not f.get("via"):
            return self.s("stops_novia", lang, n=f["stops"])
        return self.s("stops", lang, n=f["stops"], via=self._city(f["via"]))

    def _seats(self, f, lang):
        if f.get("seats_available") is None:            # real APIs may not report seats
            return self.s("seats_unknown", lang)
        return self.s("seats", lang, n=f["seats_available"]) if f["seats_available"] else self.s("sold_out", lang)

    @staticmethod
    def _arr(f):
        return (f.get("arrival_local") or "")[11:] or "—"

    def line(self, i, f, lang):
        return (f"{i}. {f['airline']} {f['flight_number']} · {f['departure_local'][11:]}→{self._arr(f)}"
                f" · {hm(f['duration_min'], lang)} · {self._stops(f, lang)} · {money(f['price_azn'])} · {self._seats(f, lang)}")

    def details(self, f, lang):
        return self.s("details", lang, airline=f["airline"], fn=f["flight_number"],
                      date=pretty_date(f["departure_local"], lang), dep=f["departure_local"][11:],
                      arr=self._arr(f), o=f["origin"]["code"], d=f["destination"]["code"],
                      dur=hm(f["duration_min"], lang), stops=self._stops(f, lang),
                      bag=f["baggage_kg"] if f.get("baggage_kg") is not None else "?",
                      cabin=f["cabin"], seats=self._seats(f, lang), price=money(f["price_azn"])
                      ).replace("? kg", "not stated").replace("? kq", "göstərilməyib").replace("? кг", "не указан")

    def route_name(self, q):
        return f"{self._city(q.get('origin', 'GYD'))} → {self._city(q['destination'])}" if q.get("destination") \
            else f"{self._city(q.get('origin', 'GYD'))} → ?"

    _NOT_PLACES = {"the", "a", "an", "my", "book", "buy", "fly", "go", "travel", "get", "be", "see", "watch", "have",
                   "find", "me", "it", "this", "that", "there", "and", "on", "in", "for", "cart", "basket", "economy",
                   "business", "return", "come", "back", "morning", "evening", "night", "today", "tomorrow", "tonight"}

    def unknown_place(self, t):
        """'to Paris' / 'в Париж': a place name that is not in the data -> say so instead of guessing."""
        known_pats = [p for pats in self.e.city_patterns.values() for p in pats]
        for m in re.finditer(r"(?<![a-zа-я])(?:to|from|в|из)\s+([a-zа-я]{3,})", t):
            w = m.group(1)
            if w in self._NOT_PLACES or find_dates(w) or any(re.match(p, w) for p in known_pats):
                continue
            if re.match(r"[a-z]", w) and m.group(0).startswith(("to", "from")):
                return w
            if re.match(r"[а-я]", w) and not re.match(r"(?:котор|эт|т[оа]|субб|пятн|понед|воскр|сред|четв|вторн|январ|феврал|ноябр|декабр)", w):
                return w
        return None

    # ------------------------------------------------------------------- handle
    def handle(self, turn: Turn, session) -> str:
        st = session.domains["flights"]
        t, lang = turn.t, turn.lang
        p = self.parse(t, st)
        q_new, f_new = p["q"], p["f"]
        results = [self.repos.flights.get(i) for i in st["results"]]
        results = [r for r in results if r]

        # ---- explicit selection by flight number / ordinal on the current list
        chosen = None
        fn = self.e.find_flight_number(t)
        if fn:
            ids = [i for i in st["results"] if self.repos.flights.get(i)["flight_number"].lower() == fn] or \
                  self.e.flight_numbers[fn][:1]
            chosen = self.repos.flights.get(ids[0])
        elif results and not q_new.get("destination") and not q_new.get("origin") and not q_new.get("date"):
            idx = ordinal_in(t)
            chosen = pick(results, idx)
            if chosen is None and has(t, *SELECT_WORDS) and not has(t, *FLIGHTISH):
                sel_f = dict(f_new)
                if is_question(t):
                    sel_f.pop("direct", None)      # "is it direct?" asks, it does not filter
                ranked = self._apply(results, sel_f)
                if ranked and sel_f:
                    chosen = ranked[0]

        wants_booking = has(t, *RESERVE)
        n = count_in(t) or session.preferences.get("passengers") or 1
        if count_in(t):
            session.preferences["passengers"] = n

        if wants_booking:
            target = chosen or (self.repos.flights.get(st["selected"]) if st["selected"] else None) or \
                     (results[0] if len(results) == 1 else None)
            if target is None:
                if results:
                    return self.s("which_flight", lang) + "\n" + "\n".join(
                        self.line(i + 1, f, lang) for i, f in enumerate(results))
                if not q_new:
                    return self.s("need_route", lang)
            else:
                st["selected"] = target["id"]
                r = self.repos.flights.reserve(target["id"], n)
                if not r["ok"]:
                    return self.s("not_enough", lang, n=r["seats_available"], fn=target["flight_number"])
                st["bookings"].append(r)
                if r.get("handoff"):                     # real API without booking: hand over to the provider
                    return self.s("handoff", lang, fn=target["flight_number"], n=n, total=money(r["total_azn"]),
                                  link=r.get("link") or "aviasales.com")
                return self.s("booked", lang, fn=target["flight_number"], date=pretty_date(target["departure_local"], lang),
                              n=n, total=money(r["total_azn"]), ref=r["reference"])

        if has(t, *COMPARE) and results:
            idxs = [i for i in range(len(results)) if False]
            ords = re.findall(r"(?:first|second|third|fourth|1st|2nd|3rd|birinci|ikinci|ucuncu|перв\w*|втор\w*|трет\w*|\d)", t)
            from ..nlp import ordinal_in as _o
            for w in ords:
                k = _o(w) if not w.isdigit() else int(w) - 1
                if k is not None and 0 <= k < len(results) and k not in idxs:
                    idxs.append(k)
            pool = [results[k] for k in idxs] if len(idxs) >= 2 else results[:5]
            cheapest = min(pool, key=lambda x: x["price_azn"])
            fastest = min(pool, key=lambda x: x["duration_min"])
            lines = [self.s("compare_head", lang)] + [self.line(i + 1, f, lang) for i, f in enumerate(pool)]
            lines.append(self.s("compare_best", lang, c=cheapest["flight_number"], f=fastest["flight_number"]))
            return "\n".join(lines)

        if chosen:
            st["selected"] = chosen["id"]
            out = []
            if has(t, *DIRECT) and is_question(t):
                out.append(self.s("is_direct_yes", lang) if chosen["stops"] == 0 else
                           (self.s("is_direct_no", lang, n=chosen["stops"], via=self._city(chosen["via"])) if chosen.get("via") else self.s("is_direct_no_novia", lang, n=chosen["stops"])))
            elif f_new.get("sort") == "price" and ordinal_in(t) is None:
                out.append(self.s("selected_cheapest", lang))
            out.append(self.details(chosen, lang))
            return "\n".join(out)

        # questions about the selected flight ("is it direct?", "how much baggage?")
        if st["selected"] and not q_new and (is_question(t) or has(t, r"baggage", r"baqaj", r"багаж")) \
                and not has(t, *FLIGHTISH):
            sel = self.repos.flights.get(st["selected"])
            out = []
            if has(t, *DIRECT):
                out.append(self.s("is_direct_yes", lang) if sel["stops"] == 0 else
                           (self.s("is_direct_no", lang, n=sel["stops"], via=self._city(sel["via"])) if sel.get("via") else self.s("is_direct_no_novia", lang, n=sel["stops"])))
            out.append(self.details(sel, lang))
            return "\n".join(out)

        # ---- search (new or refined)
        known = set(self.e.city_names)
        unknown = self.unknown_place(t)
        if unknown:
            return self.s("unknown_city", lang, cities=", ".join(sorted(self.e.city_names.values())))
        q = dict(st["query"]) if (not q_new.get("destination") or q_new.get("destination") == st["query"].get("destination")
                                  or turn.category == "followup") else {}
        q.update(q_new)
        if q.get("destination") and not q.get("origin"):
            q["origin"] = "GYD" if q["destination"] != "GYD" else None
        if not q.get("destination"):
            if q.get("origin") and q.get("origin") != "GYD":
                q["destination"] = "GYD"
            else:
                return self.s("need_route", lang)
        if q.get("origin") not in known or q.get("destination") not in known:
            return self.s("unknown_city", lang, cities=", ".join(sorted(self.e.city_names.values())))
        filters = dict(st["filters"]) if turn.category == "followup" else {}
        filters.update(f_new)
        st["query"], st["filters"] = q, filters
        st["selected"] = None

        route = self.route_name(q)
        all_route = self.repos.flights.search(q["origin"], q["destination"])
        if not q.get("date"):
            if not all_route:
                return self.s("no_route", lang)
            found = self._apply(all_route, filters)
            st["results"] = [f["id"] for f in found]
            head = self.s("results_nodate", lang, route=route)
            return "\n".join([head] + [f"{i + 1}. {pretty_date(f['departure_local'], lang)} · " + self.line(i + 1, f, lang)[3:]
                                       for i, f in enumerate(found[:8])] + [self.s("pick_hint", lang)])
        found = self._apply(self.repos.flights.search(q["origin"], q["destination"], q["date"]), filters)
        st["results"] = [f["id"] for f in found]
        lines = []
        if not found:
            lines.append(self.s("none", lang, route=route, date=pretty_date(q["date"], lang),
                                filters=self.s("filtered", lang) if filters else ""))
            if all_route:
                dates = sorted({f["departure_local"][:10] for f in self._apply(all_route, filters) or all_route})
                lines.append(self.s("other_dates", lang, dates=", ".join(pretty_date(d, lang) for d in dates)))
            else:
                lines[-1] = self.s("no_route", lang)
        else:
            lines.append(self.s("results", lang, route=route, date=pretty_date(q["date"], lang)))
            lines += [self.line(i + 1, f, lang) for i, f in enumerate(found)]
            if len(found) > 1:
                lines.append(self.s("pick_hint", lang))
        if q.get("return_date"):
            back = self._apply(self.repos.flights.search(q["destination"], q["origin"], q["return_date"]), {})
            st["return_results"] = [f["id"] for f in back]
            rroute = f"{self._city(q['destination'])} → {self._city(q['origin'])}"
            lines.append("")
            if back:
                lines.append(self.s("return_head", lang, route=rroute, date=pretty_date(q["return_date"], lang)))
                lines += [self.line(i + 1, f, lang) for i, f in enumerate(back)]
            else:
                lines.append(self.s("none", lang, route=rroute, date=pretty_date(q["return_date"], lang), filters=""))
        return "\n".join(lines)
