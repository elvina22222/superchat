"""Dump Python outputs for every test conversation and routing case, to check the JS port gives identical results."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from routing_cases import DEV, HELDOUT, STRESS
from run_tests import CONVERSATIONS
from superchat.app import SuperChat
from superchat.nlp import norm

out = {"routing": [], "convs": []}
bot = SuperChat()
for name, cases in (("dev", DEV), ("held", HELDOUT), ("stress", STRESS)):
    for i, (ctx, msg, exp, lang) in enumerate(cases):
        sid = f"r-{name}-{i}"
        for c in ctx:
            bot.handle(sid, c)
        out["routing"].append({"sid": sid, "ctx": ctx, "msg": msg, "expected": exp,
                               "py": bot.router.route(norm(msg), bot.sessions.get(sid)).category})
bot = SuperChat()
extra = [["Cümə günü Bakıdan İstanbula uçuş tap","Ən ucuzu birbaşadır?","Bu axşam hansı filmlər gedir?","100 manatdan ucuz qulaqlıq var?","Birincini səbətə at","Səbətimi göstər"],
 ["Найди рейс в Дубай","А на 8 ноября?","Что идёт в субботу?","Покажи смартфоны","Сравни их","Вернёмся к рейсам","Забронируй первый"],
 ["Show me headphones","Show me laptops","Compare the first and second","Add the first one to my cart","Back to the headphones","Remove the laptop from my cart","What's in my cart?"],
 ["Any comedies in Russian?","Flights to Tashkent","Flights to Paris on Monday","Do you have a coffee machine?","Tell me a joke","hello","flights Baku Istanbul 6 November return 9 November"],
 ["Movies with rating above 8","Book 3 tickets for Deep Signal on Saturday","I want running shoes and a ticket to Dubai and something to watch tonight"]]
convs = [[m for m, *_ in turns] for _, turns in CONVERSATIONS] + extra
for i, msgs in enumerate(convs):
    rows = []
    for m in msgs:
        r = bot.handle(f"c{i}", m)
        rows.append({"msg": m, "cat": r["category"], "reply": r["reply"]})
    out["convs"].append(rows)
(ROOT / "web" / "parity.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print("dumped", len(out["routing"]), sum(len(c) for c in out["convs"]))
