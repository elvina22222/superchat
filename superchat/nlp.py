"""Small, dependency-free text helpers shared by the router and the modules:
normalisation, language detection, numbers, ordinals and date resolution
for English, Azerbaijani and Russian."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

REFERENCE_DATE = date(2026, 11, 2)  # Monday; fixed by the brief for the mock dataset

_AZ_FOLD = str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ç": "c", "ş": "s", "ğ": "g", "ё": "е"})


def norm(text: str) -> str:
    """Lower-case and fold Azerbaijani letters to ASCII so 'uçuş' == 'ucus'."""
    text = text.replace("İ", "i").replace("I", "i").lower()
    text = text.replace("i̇", "i")  # 'İ'.lower() leaves a combining dot
    text = text.translate(_AZ_FOLD)
    text = re.sub(r"[“”«»\"']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text_norm: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", text_norm)


def is_question(text_norm: str) -> bool:
    return "?" in text_norm or has(text_norm, r"is it", r"are they", r"does it", r"mi\b", r"mu\b", r"midir",
                                   r"\w+(?:dir|dur|dirmi)\b", r"ли\b")


def has(text_norm: str, *patterns: str) -> bool:
    """True if any regex pattern matches at a word start."""
    return any(re.search(r"(?<![a-zа-я0-9])" + p, text_norm) for p in patterns)


# ------------------------------------------------------------------- language
_AZ_LETTERS = set("əğışçöü")
_AZ_WORDS = {"salam", "mene", "menim", "goster", "var", "varmi", "ucuz", "ucus", "bilet", "neche",
             "nece", "hansi", "istiyirem", "isteyirem", "lazimdir", "lazim", "bu", "ve", "ucun",
             "bakidan", "istanbula", "qulaqliq", "noutbuk", "film", "filmler", "kino", "sebet",
             "elave", "et", "yer", "yerler", "neler", "gedir", "olan", "hava", "sabah", "axsam",
             "cume", "senbe", "bazar", "noyabr", "ile", "ne", "nedir", "zehmet", "olmasa", "sagol",
             "tesekkur", "beli", "xeyr", "ikinci", "birinci", "ucuncu", "sonuncu", "daha", "stokda",
             "bron", "rezerv", "cant", "canta", "ucusu", "ucuslar", "tap", "tapin", "goster"}
_EN_WORDS = {"the", "and", "flight", "flights", "show", "me", "find", "what", "is", "to", "from",
             "for", "please", "any", "book", "cart", "cheaper", "playing", "tonight", "do", "you",
             "have", "under", "one", "it", "in", "stock", "seats", "how", "much", "hi", "hello"}


def detect_language(text: str) -> Optional[str]:
    """Return 'en', 'az', 'ru' or None when the message is too short to tell."""
    cyr = len(re.findall(r"[а-яё]", text.lower()))
    lat = len(re.findall(r"[a-zəğışçöü]", text.lower()))
    if cyr > lat:
        return "ru"
    if any(ch in _AZ_LETTERS for ch in text.lower()):
        return "az"
    toks = tokens(norm(text))
    az = sum(t in _AZ_WORDS for t in toks)
    en = sum(t in _EN_WORDS for t in toks)
    if az == en == 0:
        return None
    return "az" if az > en else "en"


# --------------------------------------------------------------------- numbers
_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "bir": 1, "iki": 2, "uc": 3, "dord": 4, "bes": 5, "alti": 6,
    "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
}
_COUNT_NOUNS = r"(?:seats?|tickets?|people|persons?|passengers?|adults?|pcs|pieces?|units?|x|" \
               r"yer|bilet|nefer|ededi?|eded|" \
               r"мест[ао]?|билет(?:а|ов)?|человек[а]?|пассажир(?:а|ов)?|штук[и]?)"


def count_in(text_norm: str) -> Optional[int]:
    """Quantity like 'two seats', '3 tickets', 'iki bilet', 'два места'."""
    m = re.search(r"(?<![a-zа-я0-9])(\d{1,2}|" + "|".join(_NUM_WORDS) + r")\s+" + _COUNT_NOUNS + r"(?![a-zа-я])",
                  text_norm)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else _NUM_WORDS[v]
    m = re.search(r"(?:for|на)\s+(\d|" + "|".join(_NUM_WORDS) + r")(?![a-zа-я0-9])(?!\s*(?:azn|manat|man|ман|[a-zа-я]*\s*(?:" +
                  "|".join(_MONTHS.values()) + r")))", text_norm)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else _NUM_WORDS[v]
    return None


_ORDINALS = [
    (r"(?:first|1st|birinci\w*|перв\w*)", 0), (r"(?:second|2nd|ikinci\w*|втор\w*)", 1),
    (r"(?:third|3rd|ucuncu\w*|трет\w*)", 2), (r"(?:fourth|4th|dorduncu\w*|четв[её]рт\w*)", 3),
    (r"(?:fifth|5th|besinci\w*|пят(?:ый|ая|ое|ую))", 4), (r"(?:last|sonuncu\w*|axirinci\w*|последн\w*)", -1),
]


def ordinal_in(text_norm: str) -> Optional[int]:
    for pat, idx in _ORDINALS:
        if has(text_norm, pat + r"(?![a-zа-я])"):
            return idx
    m = re.search(r"(?:#|№|number|option|nomre|номер|вариант)\s*(\d{1,2})(?!\d)", text_norm) or \
        re.search(r"(?<![\d.:])(\d{1,2})\s*-?\s*(?:ci|cu|ci|cı|ji|-?й|-?ой|-?ая)(?![a-zа-я])", text_norm)
    if m:
        return int(m.group(1)) - 1
    return None


def money_range(text_norm: str) -> tuple[Optional[float], Optional[float]]:
    """'under 100 AZN', '100 manatdan ucuz', 'до 100', 'between 500 and 1500', 'over 200'."""
    lo = hi = None
    num = r"(\d+(?:[.,]\d+)?)"
    m = re.search(r"(?:between|arasi|от)\s*" + num + r"\s*(?:azn|manat|man)?\s*(?:and|-|ve|до|ile)\s*" + num, text_norm)
    if m:
        return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    m = re.search(num + r"\s*-\s*" + num + r"\s*(?:azn|manat|ман)", text_norm)
    if m:
        return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    m = re.search(r"(?:under|below|less than|cheaper than|up to|max(?:imum)?|до|дешевле|меньше|не дороже)\s*" + num, text_norm) \
        or re.search(num + r"\s*(?:azn|manat|man)?\s*(?:-?(?:dan|den|ден|дан))?\s*(?:ucuz|asagi|az|qeder)", text_norm)
    if m:
        hi = float(m.group(1).replace(",", "."))
    m = re.search(r"(?:over|above|more than|from|от|дороже|больше)\s*" + num + r"\s*(?:azn|manat|ман)", text_norm) \
        or re.search(num + r"\s*(?:azn|manat|man)?\s*-?(?:dan|den)\s*(?:baha|yuxari|cox)", text_norm)
    if m:
        lo = float(m.group(1).replace(",", "."))
    return lo, hi


# ----------------------------------------------------------------------- dates
_MONTHS = {
    1: r"(?:jan(?:uary)?|yanvar\w*|январ\w*)", 2: r"(?:feb(?:ruary)?|fevral\w*|феврал\w*)",
    3: r"(?:mar(?:ch)?|mart\w*|март\w*)", 4: r"(?:apr(?:il)?|aprel\w*|апрел\w*)",
    5: r"(?:may|мая|май)", 6: r"(?:june?|iyun\w*|июн\w*)", 7: r"(?:july?|iyul\w*|июл\w*)",
    8: r"(?:aug(?:ust)?|avqust\w*|август\w*)", 9: r"(?:sep(?:t(?:ember)?)?|sentyabr\w*|сентябр\w*)",
    10: r"(?:oct(?:ober)?|oktyabr\w*|октябр\w*)", 11: r"(?:nov(?:ember)?|noyabr\w*|ноябр\w*)",
    12: r"(?:dec(?:ember)?|dekabr\w*|декабр\w*)",
}
# order matters: multi-word Azerbaijani names first ('cume axsami' = Thursday, not Friday)
_WEEKDAYS = [
    (r"bazar ertesi\w*", 0), (r"cersenbe axsami\w*", 1), (r"cume axsami\w*", 3),
    (r"(?:monday|понедельник\w*)", 0), (r"(?:tuesday|вторник\w*)", 1),
    (r"(?:wednesday|cersenbe\w*|сред[ауы])", 2), (r"(?:thursday|четверг\w*)", 3),
    (r"(?:friday|cume\w*|пятниц\w*)", 4), (r"(?:saturday|senbe\w*|суббот\w*)", 5),
    (r"(?:sunday|bazar(?:\s+gunu)?|воскресень\w*)", 6),
]
_TODAY = r"(?:tonight|today|this evening|bu gun\w*|bu axsam|bu gece|сегодня|вечером|этим вечером)"
_TOMORROW = r"(?:tomorrow|sabah(?:a|ki)?|завтра)"


def _mk(day: int, month: int) -> Optional[str]:
    try:
        return date(REFERENCE_DATE.year, month, day).isoformat()
    except ValueError:
        return None


def find_dates(text_norm: str) -> list[str]:
    """All dates mentioned, in order of appearance, as ISO strings."""
    found: list[tuple[int, str]] = []
    t = text_norm
    taken = [False] * len(t)

    def add(m, iso):
        if iso and not any(taken[m.start():m.end()]):
            found.append((m.start(), iso))
            for i in range(m.start(), m.end()):
                taken[i] = True

    for m in re.finditer(r"(20\d\d)-(\d\d)-(\d\d)", t):
        add(m, f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    for mon, pat in _MONTHS.items():
        for m in re.finditer(r"(\d{1,2})\s*(?:st|nd|rd|th|-?(?:ci|cu|si|su))?\s*(?:of\s+)?" + pat + r"(?![a-z])", t):
            add(m, _mk(int(m.group(1)), mon))
        for m in re.finditer(pat + r"\s+(\d{1,2})(?!\d)(?:st|nd|rd|th)?", t):
            add(m, _mk(int(m.group(1)), mon))
    for m in re.finditer(r"(?<![\d:])(\d{1,2})[./](\d{1,2})(?![\d:])", t):
        add(m, _mk(int(m.group(1)), int(m.group(2))))
    for pat, wd in _WEEKDAYS:
        for m in re.finditer(r"(?<![a-zа-я])" + pat + r"(?![a-zа-я])", t):
            delta = (wd - REFERENCE_DATE.weekday()) % 7
            add(m, (REFERENCE_DATE + timedelta(days=delta)).isoformat())
    for m in re.finditer(r"(?<![a-zа-я])" + _TODAY, t):
        add(m, REFERENCE_DATE.isoformat())
    for m in re.finditer(r"(?<![a-zа-я])" + _TOMORROW + r"(?![a-zа-я])", t):
        add(m, (REFERENCE_DATE + timedelta(days=1)).isoformat())
    return [iso for _, iso in sorted(found)]


def pretty_date(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso[:10])
    wd = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
          "az": ["B.e.", "Ç.a.", "Ç.", "C.a.", "C.", "Ş.", "B."],
          "ru": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]}[lang][d.weekday()]
    mon = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
           "az": ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avq", "sen", "okt", "noy", "dek"],
           "ru": ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]}[lang][d.month - 1]
    return f"{wd} {d.day} {mon}"
