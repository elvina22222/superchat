from __future__ import annotations

import re

from ..nlp import count_in, has, money_range, norm, ordinal_in
from .base import Module, Turn, money, pick

# (query patterns, predicate on product)
TYPES = {
    "headphones": ([r"head\s?phones?", r"earbuds?", r"earphones?", r"qulaqliq\w*", r"qulaqciq\w*", r"наушник\w*"],
                   lambda p: re.search(r"headphones|earbuds", p["name"]["en"], re.I)),
    "speaker": ([r"speakers?", r"dinamik\w*", r"колонк\w*"], lambda p: "Speaker" in p["name"]["en"]),
    "laptops": ([r"laptops?", r"notebooks?", r"noutbuk\w*", r"komputer\w*", r"ноутбук\w*", r"компьютер\w*", r"computers?"],
                lambda p: p["category"] == "computers"),
    "bags": ([r"backpacks?", r"bags?\b", r"canta\w*", r"рюкзак\w*", r"сумк\w*"], lambda p: "Backpack" in p["name"]["en"]),
    "shoes": ([r"shoes?", r"sneakers?", r"trainers?", r"ayaqqabi\w*", r"krossovk\w*", r"кроссовк\w*", r"обув\w*"],
              lambda p: "Shoes" in p["name"]["en"]),
    "coffee": ([r"coffee", r"espresso", r"qehve\w*", r"кофе\w*"], lambda p: "Coffee" in p["name"]["en"]),
    "games": ([r"board games?", r"games?\b", r"gifts?", r"oyun\w*", r"hediyye\w*", r"настольн\w*", r"игр\w*", r"подар\w*"],
              lambda p: p["category"] == "gifts"),
    "phones": ([r"(?:smart\s?)?phones?\b", r"telefon\w*", r"smartfon\w*", r"телефон\w*", r"смартфон\w*"],
               lambda p: p["category"] == "phones"),
    "wearables": ([r"smart\s?watch\w*", r"watches", r"agilli saat\w*", r"умн\w* час\w*", r"часы"],
                  lambda p: p["category"] == "wearables"),
    "accessories": ([r"accessor\w*", r"aksesuar\w*", r"аксессуар\w*"], lambda p: p["category"] == "accessories"),
    "audio": ([r"audio", r"sound", r"аудио"], lambda p: p["category"] == "audio"),
}
COLORS = {"black": [r"black", r"qara", r"черн\w*", r"чёрн\w*"], "white": [r"white", r"ag\b", r"бел\w*"],
          "silver": [r"silver", r"gumus\w*", r"серебр\w*"], "grey": [r"gr[ae]y", r"boz", r"сер(?:ый|ая|ого|ые|ую)"],
          "blue": [r"blue", r"goy\b", r"син\w*", r"голуб\w*"], "pink": [r"pink", r"cehrayi", r"розов\w*"],
          "red": [r"red\b", r"qirmizi", r"красн\w*"],
          "multicolor": [r"multicolou?r\w*", r"colou?rful", r"rengareng", r"разноцветн\w*"]}
CART = [r"cart", r"basket", r"sebet\w*", r"корзин\w*"]
ADD = [r"add\w*", r"put (?:it|this|them)", r"buy\b", r"i'?ll take", r"elave\w*", r"sebete at\w*", r"al\b", r"alim", r"gotur\w*",
       r"добав\w*", r"полож\w*", r"возьму", r"куплю", r"купить"]
REMOVE = [r"remove\w*", r"delete\w*", r"take out", r"drop\b", r"sil\w*", r"cixar\w*", r"удал\w*", r"убер\w*", r"убрать"]
STOCK = [r"in stock", r"stock\b", r"available", r"availability", r"stokda", r"anbarda", r"var ?mi", r"movcud\w*",
         r"в наличии", r"наличи\w*", r"есть ли", r"есть в"]
COMPARE = [r"compar\w*", r"vs\b", r"versus", r"difference", r"muqayis\w*", r"ferq\w*", r"сравн\w*", r"разниц\w*"]
CHEAP = [r"cheap\w*", r"ucuz\w*", r"дешев\w*", r"подешевле"]
BEST = [r"best", r"top[- ]rated", r"highest rat\w*", r"en yaxsi", r"лучш\w*"]
EXPENSIVE = [r"expensive", r"premium", r"baha\w*", r"дорог\w*"]
SEARCH = [r"do you have", r"have you got", r"show\b", r"find", r"search", r"looking for", r"any\b", r"need\b", r"want", r"istey\w*", r"istiy\w*",
          r"хочу", r"нуж[ео]н\w*",
          r"var ?mi", r"varmi", r"goster\w*", r"axtar\w*", r"tap\b", r"есть\b", r"покаж\w*", r"найд\w*", r"ищу", r"нужн\w*"]
BACK = [r"back to", r"go back", r"return to", r"geri qayid\w*", r"qayidaq", r"вернемся", r"вернёмся", r"назад к"]


class ShoppingModule(Module):
    name = "shopping"
    STR = {
        "need_query": {"en": "What are you looking for? I can search headphones, laptops, backpacks, phones, smartwatches and more.",
                       "az": "Nə axtarırsınız? Qulaqlıq, noutbuk, çanta, telefon, ağıllı saat və s. axtara bilərəm.",
                       "ru": "Что вы ищете? Могу найти наушники, ноутбуки, рюкзаки, телефоны, умные часы и другое."},
        "not_found": {"en": "Sorry, I couldn’t find that in the catalogue. I have headphones and earbuds, a speaker, laptops, smartphones, a smartwatch, a backpack, running shoes, a coffee machine and a board game.",
                      "az": "Bağışlayın, bunu kataloqda tapmadım. Məndə qulaqlıq, dinamik, noutbuk, smartfon, ağıllı saat, çanta, qaçış ayaqqabısı, qəhvə maşını və stolüstü oyun var.",
                      "ru": "Извините, этого нет в каталоге. Есть наушники, колонка, ноутбуки, смартфоны, умные часы, рюкзак, кроссовки, кофемашина и настольная игра."},
        "results": {"en": "Here is what I found{cond}:", "az": "Tapdıqlarım{cond}:", "ru": "Вот что нашлось{cond}:"},
        "again": {"en": "Back to your earlier list{cond}:", "az": "Əvvəlki siyahınız{cond}:", "ru": "Возвращаемся к вашему списку{cond}:"},
        "selected_note": {"en": "You were looking at: {name}.", "az": "Baxdığınız məhsul: {name}.", "ru": "Вы смотрели: {name}."},
        "under": {"en": " under {v}", "az": " ({v}-dən ucuz)", "ru": " до {v}"},
        "over": {"en": " over {v}", "az": " ({v}-dən baha)", "ru": " от {v}"},
        "none": {"en": "Sorry, nothing in the catalogue matches{cond}.", "az": "Təəssüf ki, kataloqda uyğun məhsul yoxdur{cond}.",
                 "ru": "К сожалению, в каталоге ничего не подходит{cond}."},
        "closest": {"en": "Closest options in that category:", "az": "Bu kateqoriyada ən yaxın variantlar:",
                    "ru": "Ближайшие варианты в этой категории:"},
        "in_stock": {"en": "in stock ({n})", "az": "stokda var ({n})", "ru": "в наличии ({n})"},
        "out_stock": {"en": "out of stock", "az": "stokda yoxdur", "ru": "нет в наличии"},
        "stock_yes": {"en": "Yes — {name} is in stock: {n} available.", "az": "Bəli — {name} stokda var: {n} ədəd.",
                      "ru": "Да — {name} в наличии: {n} шт."},
        "stock_no": {"en": "Sorry, {name} is currently out of stock.", "az": "Təəssüf ki, {name} hazırda stokda yoxdur.",
                     "ru": "К сожалению, {name} сейчас нет в наличии."},
        "details": {"en": "{name} — {brand}\n• Price: {price}\n• Rating: ★{rating}\n• Colour: {color}\n• Stock: {stock}\n• {desc}",
                    "az": "{name} — {brand}\n• Qiymət: {price}\n• Reytinq: ★{rating}\n• Rəng: {color}\n• Stok: {stock}\n• {desc}",
                    "ru": "{name} — {brand}\n• Цена: {price}\n• Рейтинг: ★{rating}\n• Цвет: {color}\n• Наличие: {stock}\n• {desc}"},
        "which": {"en": "Which product do you mean? Say “the first one” or its name.",
                  "az": "Hansı məhsulu nəzərdə tutursunuz? “Birincini” və ya adını yazın.",
                  "ru": "Какой товар вы имеете в виду? Скажите «первый» или название."},
        "added": {"en": "Added {n} × {name} to your cart. Cart total: {total}.",
                  "az": "Səbətə əlavə edildi: {n} × {name}. Səbət cəmi: {total}.",
                  "ru": "Добавлено в корзину: {n} × {name}. Сумма корзины: {total}."},
        "add_oos": {"en": "{name} is out of stock, so I can’t add it to the cart.",
                    "az": "{name} stokda yoxdur, səbətə əlavə edə bilmirəm.",
                    "ru": "{name} нет в наличии, поэтому добавить в корзину нельзя."},
        "add_limit": {"en": "Only {n} of {name} in stock.", "az": "{name} üçün stokda cəmi {n} ədəd var.",
                      "ru": "{name} в наличии только {n} шт."},
        "removed": {"en": "Removed {name} from your cart. Cart total: {total}.", "az": "{name} səbətdən silindi. Səbət cəmi: {total}.",
                    "ru": "{name} удалён из корзины. Сумма корзины: {total}."},
        "not_in_cart": {"en": "That item is not in your cart.", "az": "Bu məhsul səbətinizdə yoxdur.", "ru": "Этого товара нет в корзине."},
        "cart_empty": {"en": "Your cart is empty.", "az": "Səbətiniz boşdur.", "ru": "Ваша корзина пуста."},
        "cart": {"en": "Your cart:", "az": "Səbətiniz:", "ru": "Ваша корзина:"},
        "total": {"en": "Total: {total}", "az": "Cəmi: {total}", "ru": "Итого: {total}"},
        "compare_head": {"en": "Comparison:", "az": "Müqayisə:", "ru": "Сравнение:"},
        "compare_best": {"en": "Cheapest: {c}. Best rated: {r}.", "az": "Ən ucuz: {c}. Ən yüksək reytinq: {r}.",
                         "ru": "Самый дешёвый: {c}. Лучший рейтинг: {r}."},
        "pick_hint": {"en": "Ask “is the second one in stock?”, “compare them” or “add the first one to my cart”.",
                      "az": "“İkinci stokda var?”, “müqayisə et” və ya “birincini səbətə at” yaza bilərsiniz.",
                      "ru": "Спросите «второй есть в наличии?», «сравни их» или «добавь первый в корзину»."},
    }

    def name_of(self, p, lang):
        return p["name"].get(lang) or p["name"]["en"]

    def stock(self, p, lang):
        return self.s("in_stock", lang, n=p["stock"]) if p["stock"] > 0 else self.s("out_stock", lang)

    def line(self, i, p, lang):
        return f"{i}. {self.name_of(p, lang)} — {p['brand']}, {p['color']} · {money(p['price_azn'])} · ★{p['rating']} · {self.stock(p, lang)}"

    def details(self, p, lang):
        return self.s("details", lang, name=self.name_of(p, lang), brand=p["brand"], price=money(p["price_azn"]),
                      rating=p["rating"], color=p["color"], stock=self.stock(p, lang), desc=p.get("description", ""))

    def cart_total(self, cart):
        return round(sum(self.repos.products.get(pid)["price_azn"] * n for pid, n in cart.items()), 2)

    # ------------------------------------------------------------------ parsing
    def parse(self, t):
        q = {}
        for key, (pats, _) in TYPES.items():
            if has(t, *pats):
                q["type"] = key
                break
        b = self.e.find_brand(t)
        if b:
            q["brand"] = b
        for c, pats in COLORS.items():
            if has(t, *pats):
                q["color"] = c
                break
        lo, hi = money_range(t)
        if lo:
            q["min"] = lo
        if hi:
            q["max"] = hi
        if has(t, *CHEAP) and not hi:
            q["sort"] = "price"
        elif has(t, *BEST):
            q["sort"] = "rating"
        elif has(t, *EXPENSIVE):
            q["sort"] = "-price"
        names = self.e.find_product_by_name(t)
        if names:
            q["ids"] = names
        return q

    def search(self, q):
        items = self.repos.products.all()
        if q.get("ids"):
            items = [p for p in items if p["id"] in q["ids"]]
        if q.get("type"):
            items = [p for p in items if TYPES[q["type"]][1](p)]
        if q.get("brand"):
            items = [p for p in items if p["brand"] == q["brand"]]
        if q.get("color"):
            items = [p for p in items if p["color"] == q["color"]]
        base = list(items)
        if q.get("min"):
            items = [p for p in items if p["price_azn"] >= q["min"]]
        if q.get("max"):
            items = [p for p in items if p["price_azn"] <= q["max"]]
        key = {"price": lambda p: p["price_azn"], "-price": lambda p: -p["price_azn"],
               "rating": lambda p: -p["rating"]}.get(q.get("sort"), lambda p: (p["stock"] == 0, p["price_azn"]))
        return sorted(items, key=key), sorted(base, key=lambda p: p["price_azn"])

    def cond(self, q, lang):
        c = ""
        if q.get("max"):
            c += self.s("under", lang, v=money(q["max"]))
        if q.get("min"):
            c += self.s("over", lang, v=money(q["min"]))
        return c

    # ------------------------------------------------------------------- handle
    def handle(self, turn: Turn, session) -> str:
        st = session.domains["shopping"]
        t, lang = turn.t, turn.lang
        q_new = self.parse(t)
        results = [p for p in (self.repos.products.get(i) for i in st["results"]) if p]
        sel = self.repos.products.get(st["selected"]) if st["selected"] else None

        # which product does the message point at?
        target = None
        idx = ordinal_in(t)
        if idx is not None and results:
            target = pick(results, idx)
        elif q_new.get("ids") and len(q_new["ids"]) == 1 and not self._is_search(t, q_new):
            target = self.repos.products.get(q_new["ids"][0])
        elif results and has(t, r"(?:cheap|expensive)\w* one", r"ucuz olan\w*", r"daha ucuz\w*", r"подешевле", r"самый дешев\w*"):
            target = sorted(results, key=lambda p: p["price_azn"])[-1 if has(t, r"expensive") else 0]
        elif results and q_new.get("brand") and not q_new.get("type"):
            in_list = [p for p in results if p["brand"] == q_new["brand"]]
            target = in_list[0] if len(in_list) == 1 else None
        pronoun = has(t, r"\bit\b", r"\bthis\b", r"\bthat\b", r"onu\b", r"bunu\b", r"его\b", r"е[её]\b", r"этот", r"это")

        # ---- cart operations
        if has(t, *REMOVE) and (has(t, *CART) or st["cart"]):
            item = target or (sel if pronoun else None)
            if item is None and q_new.get("type"):
                item = next((self.repos.products.get(pid) for pid in st["cart"]
                             if TYPES[q_new["type"]][1](self.repos.products.get(pid))), None)
            if item is None or item["id"] not in st["cart"]:
                return self.s("not_in_cart", lang)
            del st["cart"][item["id"]]
            return self.s("removed", lang, name=self.name_of(item, lang), total=money(self.cart_total(st["cart"])))
        if has(t, *ADD) and (has(t, *CART) or target or pronoun or sel):
            item = target or sel
            if item is None:
                return self.s("which", lang)
            st["selected"] = item["id"]
            n = count_in(t) or 1
            if item["stock"] <= 0:
                return self.s("add_oos", lang, name=self.name_of(item, lang))
            if st["cart"].get(item["id"], 0) + n > item["stock"]:
                return self.s("add_limit", lang, n=item["stock"], name=self.name_of(item, lang))
            st["cart"][item["id"]] = st["cart"].get(item["id"], 0) + n
            return self.s("added", lang, n=n, name=self.name_of(item, lang), total=money(self.cart_total(st["cart"])))
        if has(t, *CART):
            if not st["cart"]:
                return self.s("cart_empty", lang)
            lines = [self.s("cart", lang)]
            for pid, n in st["cart"].items():
                p = self.repos.products.get(pid)
                lines.append(f"• {n} × {self.name_of(p, lang)} — {money(p['price_azn'] * n)}")
            lines.append(self.s("total", lang, total=money(self.cart_total(st["cart"]))))
            return "\n".join(lines)

        # ---- compare
        if has(t, *COMPARE):
            pool = []
            for w in re.findall(r"(?:first|second|third|fourth|birinci|ikinci|ucuncu|перв\w*|втор\w*|трет\w*)", t):
                k = ordinal_in(w)
                if k is not None and k < len(results) and results[k] not in pool:
                    pool.append(results[k])
            if len(pool) < 2 and q_new.get("ids") and len(q_new["ids"]) >= 2:
                pool = [self.repos.products.get(i) for i in q_new["ids"]]
            if len(pool) < 2:
                pool = results[:4] if not q_new.get("type") else self.search(q_new)[0][:4]
            if len(pool) < 2:
                return self.s("which", lang)
            c = min(pool, key=lambda p: p["price_azn"])
            r = max(pool, key=lambda p: p["rating"])
            return "\n".join([self.s("compare_head", lang)] + [self.line(i + 1, p, lang) for i, p in enumerate(pool)] +
                             [self.s("compare_best", lang, c=self.name_of(c, lang), r=self.name_of(r, lang))])

        # ---- stock question / details on one product
        if target or (sel and (pronoun or has(t, *STOCK)) and not q_new.get("type")):
            item = target or sel
            st["selected"] = item["id"]
            if has(t, *STOCK):
                key = "stock_yes" if item["stock"] > 0 else "stock_no"
                return self.s(key, lang, name=self.name_of(item, lang), n=item["stock"]) + "\n" + self.details(item, lang)
            return self.details(item, lang)

        # ---- search, or return to an earlier search ("back to the headphones")
        search_q = {k: v for k, v in q_new.items() if k != "ids"} if (not q_new.get("ids") or q_new.get("type")) else q_new
        if not search_q:
            if has(t, *SEARCH):
                return self.s("not_found", lang)
            if results:
                return "\n".join([self.s("again", lang, cond=self.cond(st["query"], lang))] +
                                 [self.line(i + 1, p, lang) for i, p in enumerate(results)])
            return self.s("need_query", lang)
        if turn.category == "followup" and not search_q.get("type") and st["query"].get("type"):
            search_q = {**st["query"], **search_q}
        current = {"query": st["query"], "results": st["results"], "selected": st["selected"]}
        for past in [current] + st["history"][::-1]:
            if past["query"].get("type") == search_q.get("type") and (has(t, *BACK) or past["query"] == search_q):
                if len(search_q) == 1 or past["query"] == search_q:
                    st["query"], st["results"], st["selected"] = past["query"], past["results"], past["selected"]
                    items = [self.repos.products.get(i) for i in past["results"]]
                    lines = [self.s("again", lang, cond=self.cond(past["query"], lang))]
                    lines += [self.line(i + 1, p, lang) for i, p in enumerate(items)]
                    if past["selected"]:
                        lines.append(self.s("selected_note", lang, name=self.name_of(self.repos.products.get(past["selected"]), lang)))
                    return "\n".join(lines)
        found, base = self.search(search_q)
        self._remember(st)
        st["query"], st["results"], st["selected"] = search_q, [p["id"] for p in found], None
        if not found:
            out = [self.s("none", lang, cond=self.cond(search_q, lang))]
            if base:
                out.append(self.s("closest", lang))
                out += [self.line(i + 1, p, lang) for i, p in enumerate(base[:3])]
                st["results"] = [p["id"] for p in base[:3]]
            return "\n".join(out)
        lines = [self.s("results", lang, cond=self.cond(search_q, lang))]
        lines += [self.line(i + 1, p, lang) for i, p in enumerate(found)]
        if len(found) > 1:
            lines.append(self.s("pick_hint", lang))
        else:
            st["selected"] = found[0]["id"]
        return "\n".join(lines)

    @staticmethod
    def _is_search(t, q):
        return bool(q.get("min") or q.get("max") or has(t, *SEARCH))

    def _remember(self, st):
        if st["query"]:
            st["history"] = [h for h in st["history"] if h["query"] != st["query"]][-5:]
            st["history"].append({"query": st["query"], "results": st["results"], "selected": st["selected"]})
