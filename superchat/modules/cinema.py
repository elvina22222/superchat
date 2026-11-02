from __future__ import annotations

import re

from ..nlp import REFERENCE_DATE, count_in, find_dates, has, ordinal_in, pretty_date
from .base import Module, Turn, money, pick

GENRES = {
    "sci-fi": [r"sci-?fi", r"science fiction", r"scifi", r"elmi[- ]?fantasti\w*", r"fantasti\w*", r"фантастик\w*"],
    "comedy": [r"comed\w*", r"funny", r"komedi\w*", r"комеди\w*"],
    "drama": [r"drama\w*", r"dram\b", r"драм\w*"],
    "thriller": [r"thriller\w*", r"triller\w*", r"триллер\w*"],
    "horror": [r"horror", r"scary", r"qorxu\w*", r"ужас\w*", r"хоррор\w*"],
    "animation": [r"animat\w*", r"cartoon\w*", r"cizgi\w*", r"анимац\w*", r"мульт\w*"],
    "romance": [r"roman(?:ce|tic)\w*", r"romanti\w*", r"мелодрам\w*", r"романти\w*"],
    "action": [r"action", r"dovus\w*", r"ekshn", r"боевик\w*", r"экшн"],
    "adventure": [r"adventure\w*", r"macera\w*", r"приключен\w*"],
    "mystery": [r"myster\w*", r"sirli", r"детектив\w*", r"мистик\w*", r"загадочн\w*"],
    "crime": [r"crime", r"cinayet\w*", r"криминал\w*"],
    "family": [r"family", r"kids", r"children", r"aile\w*", r"usaq\w*", r"семейн\w*", r"детск\w*", r"для детей"],
}
LANGS = {"English": [r"english", r"ingilis\w*", r"англ\w*"],
         "Azerbaijani": [r"azerbaijani", r"azeri", r"azerbaycan\w*", r"азербайджан\w*", r"азерб\w*"],
         "Russian": [r"russian", r"rus dil\w*", r"rusca", r"русск\w*", r"на русском"]}
RESERVE = [r"book\w*", r"reserve\w*", r"bron\w*", r"rezerv\w*", r"заброн\w*", r"бронир\w*", r"buy tickets?",
           r"bilet al\w*", r"купи\w* билет\w*", r"i'?ll take"]
SEATS = [r"seats?", r"available", r"yer\w*", r"мест\w*", r"свободн\w*", r"tickets? left", r"sold out"]
PRICE = [r"price", r"how much", r"cost", r"qiymet\w*", r"necey\w*", r"сколько стоит", r"цен\w*", r"стоимост\w*"]
SHOWTIMES = [r"showtimes?", r"when\b", r"what time", r"times?\b", r"schedule", r"seans\w*", r"ne vaxt", r"saat nec\w*",
             r"сеанс\w*", r"когда", r"во сколько", r"расписан\w*", r"where\b", r"harada", r"где"]
TOP = [r"best", r"top", r"highest", r"en yaxsi", r"лучш\w*", r"высок\w* рейтинг"]


class CinemaModule(Module):
    name = "cinema"
    STR = {
        "playing": {"en": "Showing {date}:", "az": "{date} nümayiş olunur:", "ru": "В прокате {date}:"},
        "films": {"en": "Films{cond}:", "az": "Filmlər{cond}:", "ru": "Фильмы{cond}:"},
        "nothing_date": {"en": "Nothing{cond} is showing on {date}.", "az": "{date} tarixində{cond} film yoxdur.",
                         "ru": "На {date}{cond} сеансов нет."},
        "no_films": {"en": "No films match{cond}.", "az": "Uyğun film tapılmadı{cond}.", "ru": "Подходящих фильмов нет{cond}."},
        "film_line_hint": {"en": "Ask for showtimes, seats or “book 2 tickets for the first one”.",
                           "az": "Seanslar, boş yerlər və ya “birinciyə 2 bilet bron et” soruşa bilərsiniz.",
                           "ru": "Спросите о сеансах, местах или «забронируй 2 билета на первый»."},
        "showtimes_for": {"en": "{title} — showtimes{date}:", "az": "{title} — seanslar{date}:", "ru": "{title} — сеансы{date}:"},
        "no_showtimes": {"en": "{title} has no showtimes{date}.", "az": "{title} filminin{date} seansı yoxdur.",
                         "ru": "У фильма {title} нет сеансов{date}."},
        "other_days": {"en": "It is showing on: {dates}.", "az": "Nümayiş tarixləri: {dates}.", "ru": "Сеансы есть: {dates}."},
        "seats": {"en": "{n} seats free", "az": "{n} boş yer", "ru": "свободно мест: {n}"},
        "sold_out": {"en": "sold out", "az": "yer yoxdur", "ru": "мест нет"},
        "which_film": {"en": "Which film would you like to book?", "az": "Hansı filmə bilet bron edim?",
                       "ru": "На какой фильм забронировать?"},
        "which_show": {"en": "Which showtime should I book? Reply with its number.",
                       "az": "Hansı seansı bron edim? Nömrəsini yazın.", "ru": "Какой сеанс забронировать? Укажите номер."},
        "several_genre": {"en": "Two or more {genre} films match — {titles}. Here are their options:",
                          "az": "Bir neçə {genre} filmi var — {titles}. Variantlar:",
                          "ru": "Подходит несколько фильмов жанра {genre} — {titles}. Варианты:"},
        "booked": {"en": "Booked ✅ {n} ticket(s) for {title}, {date} {time}, {cinema} ({hall}). Total {total}. Reference {ref}. (Mock booking — no payment.)",
                   "az": "Bron edildi ✅ {title}, {date} {time}, {cinema} ({hall}) — {n} bilet. Cəmi {total}. Kod: {ref}. (Test bronu — ödəniş yoxdur.)",
                   "ru": "Забронировано ✅ {n} билет(а) на {title}, {date} {time}, {cinema} ({hall}). Итого {total}. Номер брони {ref}. (Тестовая бронь — без оплаты.)"},
        "not_enough": {"en": "Sorry, only {n} seat(s) left for that showtime.", "az": "Təəssüf ki, bu seansda cəmi {n} yer qalıb.",
                       "ru": "К сожалению, на этот сеанс осталось мест: {n}."},
        "details": {"en": "{title} ({year_genre}) · {language} · {dur} min · {age} · ★{rating}\n{syn}",
                    "az": "{title} ({year_genre}) · {language} · {dur} dəq · {age} · ★{rating}\n{syn}",
                    "ru": "{title} ({year_genre}) · {language} · {dur} мин · {age} · ★{rating}\n{syn}"},
        "cinemas": {"en": "Our cinemas:", "az": "Kinoteatrlarımız:", "ru": "Наши кинотеатры:"},
        "seat_answer": {"en": "{when}: {seats}, {price} per ticket.", "az": "{when}: {seats}, bilet {price}.",
                        "ru": "{when}: {seats}, билет {price}."},
        "on": {"en": " on {d}", "az": " {d}", "ru": " на {d}"},
        "tonight": {"en": "tonight", "az": "bu axşam", "ru": "сегодня"},
    }

    # ---------------------------------------------------------------- helpers
    def movie(self, mid):
        return next((m for m in self.repos.cinema.movies() if m["id"] == mid), None)

    def cinema_name(self, cid):
        return next((c["name"] for c in self.repos.cinema.cinemas() if c["id"] == cid), cid)

    @staticmethod
    def genres(m):
        g = m["genre"]
        return g if isinstance(g, list) else [g]

    def seats(self, s, lang):
        return self.s("seats", lang, n=s["seats_available"]) if s["seats_available"] > 0 else self.s("sold_out", lang)

    def show_line(self, i, s, lang, with_title=False):
        title = self.movie(s["movie_id"])["title"] + " · " if with_title else ""
        return (f"{i}. {title}{pretty_date(s['date'], lang)} {s['time']} · {self.cinema_name(s['cinema_id'])}, {s['hall']}"
                f" · {money(s['price_azn'])} · {self.seats(s, lang)}")

    def movie_line(self, i, m):
        return f"{i}. {m['title']} — {', '.join(self.genres(m))}, {m['language']}, {m['age_rating']}, ★{m['rating']}"

    def details(self, m, lang):
        return self.s("details", lang, title=m["title"], year_genre=", ".join(self.genres(m)), language=m["language"],
                      dur=m["duration_min"], age=m["age_rating"], rating=m["rating"], syn=m.get("synopsis", ""))

    def date_label(self, d, lang):
        return self.s("tonight", lang) if d == REFERENCE_DATE.isoformat() else pretty_date(d, lang)

    # ------------------------------------------------------------------ parse
    def parse(self, t):
        q = {}
        g = [k for k, pats in GENRES.items() if has(t, *pats)]
        if g:
            q["genre"] = g[0]
        for lname, pats in LANGS.items():
            if has(t, *pats):
                q["language"] = lname
        m = re.search(r"(?:rating|rated|reytinq\w*|рейтинг\w*)\s*(?:above|over|>|at least|from|от|выше)?\s*(\d(?:[.,]\d)?)", t)
        if m:
            q["min_rating"] = float(m.group(1).replace(",", "."))
        dates = find_dates(t)
        if dates:
            q["date"] = dates[0]
        cid = self.e.find_cinema(t)
        if cid:
            q["cinema"] = cid
        tm = re.search(r"(\d{1,2})[:.](\d{2})", t)
        if tm:
            q["time"] = f"{int(tm.group(1)):02d}:{tm.group(2)}"
        return q

    def filter_movies(self, q):
        out = self.repos.cinema.movies()
        if q.get("genre"):
            out = [m for m in out if q["genre"] in self.genres(m)]
        if q.get("language"):
            out = [m for m in out if m["language"] == q["language"]]
        if q.get("min_rating"):
            out = [m for m in out if m["rating"] >= q["min_rating"]]
        return out

    # ----------------------------------------------------------------- handle
    def handle(self, turn: Turn, session) -> str:
        st = session.domains["cinema"]
        t, lang = turn.t, turn.lang
        q = self.parse(t)
        listed_movies = [self.movie(i) for i in st["movies"]]
        listed_shows = [self.repos.cinema.get_showtime(i) for i in st["showtimes"]]
        wants_book = has(t, *RESERVE) or st.get("intent") == "book"
        n = count_in(t)

        # ---- cinema list
        if has(t, r"cinemas", r"kinoteatrlar\w*", r"кинотеатр(?:ы|ов)", r"which cinema", r"hansi kinoteatr", r"какие кинотеатры") \
                and not self.e.find_movies(t) and not q.get("genre"):
            return "\n".join([self.s("cinemas", lang)] + [f"• {c['name']} — {c['address']}" for c in self.repos.cinema.cinemas()])

        # ---- resolve the film the user means
        movie = None
        named = self.e.find_movies(t)
        idx = ordinal_in(t)
        if named:
            movie = self.movie(named[0])
        elif idx is not None and st["last_list"] == "showtimes" and listed_shows:
            show = pick(listed_shows, idx)
            if show:
                st["showtime"], st["movie"] = show["id"], show["movie_id"]
                movie = self.movie(show["movie_id"])
        elif idx is not None and listed_movies:
            movie = pick(listed_movies, idx)
        genre_matches = []
        if not movie and q.get("genre") and listed_movies and has(t, r"one\b", r"olan\w*", r"тот", r"который", r"the "):
            genre_matches = [m for m in listed_movies if q["genre"] in self.genres(m)]
            if len(genre_matches) == 1:
                movie = genre_matches[0]
        if movie and (not st["movie"] or st["movie"] != movie["id"]):
            st["movie"], st["showtime"] = movie["id"], (st["showtime"] if idx is not None and st["last_list"] == "showtimes" else None)
        if not movie and st["movie"] and not genre_matches and not q.get("genre") and not q.get("language") \
                and (wants_book or has(t, *SEATS, *PRICE, *SHOWTIMES) or turn.category == "followup"):
            movie = self.movie(st["movie"])

        # ---- several films of the asked genre ("the sci-fi one" when two are sci-fi)
        if len(genre_matches) > 1:
            shows = [s for m in genre_matches for s in self.repos.cinema.showtimes(m["id"], q.get("date"))]
            shows.sort(key=lambda s: (s["date"], s["time"]))
            st["showtimes"], st["last_list"], st["movie"] = [s["id"] for s in shows], "showtimes", None
            lines = [self.s("several_genre", lang, genre=q["genre"], titles=", ".join(m["title"] for m in genre_matches))]
            lines += [self.show_line(i + 1, s, lang, with_title=True) for i, s in enumerate(shows)] or \
                     [self.s("nothing_date", lang, cond="", date=self.date_label(q.get("date", ""), lang))]
            if wants_book or n:
                lines.append(self.s("which_show", lang))
            return "\n".join(lines)

        # ---- booking
        if wants_book:
            if n:
                session.preferences["tickets"] = n
            n = n or session.preferences.get("tickets") or 1
            show = self.repos.cinema.get_showtime(st["showtime"]) if st["showtime"] else None
            if show and movie and show["movie_id"] != movie["id"]:
                show = None
            if not show and idx is not None and st["last_list"] == "showtimes":
                show = pick(listed_shows, idx)
            if not show:
                st["intent"] = "book"
                if not movie:
                    pool = listed_movies if len(listed_movies) > 1 else \
                        [m for m in self.repos.cinema.movies() if self.repos.cinema.showtimes(m["id"])]
                    st["movies"], st["last_list"] = [m["id"] for m in pool], "movies"
                    return "\n".join([self.s("which_film", lang)] + [self.movie_line(i + 1, m) for i, m in enumerate(pool)])
                cands = self.repos.cinema.showtimes(movie["id"], q.get("date"), q.get("cinema"))
                if q.get("time"):
                    cands = [s for s in cands if s["time"] == q["time"]]
                bookable = [s for s in cands if s["seats_available"] >= n]
                if len(bookable) == 1 and (q.get("date") or q.get("time") or len(cands) == 1):
                    show = bookable[0]
                else:
                    cands = cands or self.repos.cinema.showtimes(movie["id"])
                    st["showtimes"], st["last_list"] = [s["id"] for s in cands], "showtimes"
                    return "\n".join([self.s("showtimes_for", lang, title=movie["title"], date="")] +
                                     [self.show_line(i + 1, s, lang) for i, s in enumerate(cands)] +
                                     [self.s("which_show", lang)])
            r = self.repos.cinema.reserve(show["id"], n)
            if not r["ok"]:
                return self.s("not_enough", lang, n=r["seats_available"])
            st["showtime"], st["intent"] = show["id"], None
            st["bookings"].append(r)
            return self.s("booked", lang, n=n, title=self.movie(show["movie_id"])["title"], date=pretty_date(show["date"], lang),
                          time=show["time"], cinema=self.cinema_name(show["cinema_id"]), hall=show["hall"],
                          total=money(r["total_azn"]), ref=r["reference"])

        # ---- a showtime was picked from the list ("the second one")
        if idx is not None and st["last_list"] == "showtimes" and st["showtime"] and not named:
            s = self.repos.cinema.get_showtime(st["showtime"])
            return self.s("seat_answer", lang, when=f"{self.movie(s['movie_id'])['title']}, {pretty_date(s['date'], lang)} {s['time']}, "
                                                   f"{self.cinema_name(s['cinema_id'])}",
                          seats=self.seats(s, lang), price=money(s["price_azn"]))

        # ---- showtimes / seats / price for one film
        if movie:
            shows = self.repos.cinema.showtimes(movie["id"], q.get("date"), q.get("cinema"))
            date_txt = ("" if not q.get("date") else " " + self.s("tonight", lang) if q["date"] == REFERENCE_DATE.isoformat()
                        else self.s("on", lang, d=pretty_date(q["date"], lang)))
            st["last_list"] = "showtimes"
            st["query"] = {**st["query"], **q}
            if not shows:
                all_shows = self.repos.cinema.showtimes(movie["id"])
                st["showtimes"] = [s["id"] for s in all_shows]
                lines = [self.s("no_showtimes", lang, title=movie["title"], date=date_txt)]
                if all_shows:
                    lines.append(self.s("other_days", lang, dates=", ".join(sorted({pretty_date(s["date"], lang) for s in all_shows}))))
                return "\n".join(lines)
            st["showtimes"] = [s["id"] for s in shows]
            lines = []
            if not has(t, *SEATS, *PRICE, *SHOWTIMES) and not q.get("date") and turn.category != "followup":
                lines.append(self.details(movie, lang))
            lines.append(self.s("showtimes_for", lang, title=movie["title"], date=date_txt))
            lines += [self.show_line(i + 1, s, lang) for i, s in enumerate(shows)]
            return "\n".join(lines)

        # ---- listings: what is playing on a date, or films by genre/language/rating
        cond = ""
        if q.get("genre"):
            cond += f" · {q['genre']}"
        if q.get("language"):
            cond += f" · {q['language']}"
        if q.get("min_rating"):
            cond += f" · ★≥{q['min_rating']}"
        movies = self.filter_movies(q)
        if has(t, *TOP):
            movies.sort(key=lambda m: -m["rating"])
        if q.get("date") or has(t, r"playing", r"showing", r"on now", r"ne gedir", r"neler gedir", r"ид[её]т", r"в прокате"):
            day = q.get("date", REFERENCE_DATE.isoformat())
            shows = [s for s in self.repos.cinema.showtimes(date=day, cinema_id=q.get("cinema"))
                     if s["movie_id"] in {m["id"] for m in movies}]
            if not shows:
                st["movies"], st["showtimes"] = [], []
                return self.s("nothing_date", lang, cond=cond, date=self.date_label(day, lang))
            order = []
            for s in shows:
                if s["movie_id"] not in order:
                    order.append(s["movie_id"])
            st["movies"], st["showtimes"], st["last_list"], st["movie"] = order, [s["id"] for s in shows], "movies", None
            st["query"] = {**q, "date": day}
            lines = [self.s("playing", lang, date=self.date_label(day, lang))]
            for i, mid in enumerate(order):
                m = self.movie(mid)
                times = ", ".join(f"{s['time']} {self.cinema_name(s['cinema_id']).replace('CinemaPlus ', '')} ({self.seats(s, lang)})"
                                  for s in shows if s["movie_id"] == mid)
                lines.append(f"{i + 1}. {m['title']} — {', '.join(self.genres(m))}, {m['language']}, ★{m['rating']} · {times}")
            lines.append(self.s("film_line_hint", lang))
            return "\n".join(lines)
        if not movies:
            return self.s("no_films", lang, cond=cond)
        st["movies"], st["last_list"], st["movie"] = [m["id"] for m in movies], "movies", None
        st["query"] = q
        return "\n".join([self.s("films", lang, cond=cond)] + [self.movie_line(i + 1, m) for i, m in enumerate(movies)] +
                         [self.s("film_line_hint", lang)])
