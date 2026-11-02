"""Export the Python cue lists, reply texts and data to one JSON file for the browser version."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from superchat import lexicon as L, nlp, entities, app
from superchat.modules import flights as F, shopping as S, cinema as C

def lists(mod):
    return {k: v for k, v in vars(mod).items() if k.isupper() and isinstance(v, list) and all(isinstance(x, str) for x in v)}

out = {
    "lex": lists(L),
    "flights": {**lists(F), "STR": F.FlightsModule.STR},
    "shopping": {**lists(S), "STR": S.ShoppingModule.STR, "TYPES": {k: v[0] for k, v in S.TYPES.items()},
                 "COLORS": S.COLORS},
    "cinema": {**lists(C), "STR": C.CinemaModule.STR, "GENRES": C.GENRES, "LANGS": C.LANGS},
    "app": {"TEXT": app.TEXT, "HEAD": app.HEAD},
    "nlp": {"MONTHS": nlp._MONTHS, "WEEKDAYS": nlp._WEEKDAYS, "TODAY": nlp._TODAY, "TOMORROW": nlp._TOMORROW,
            "NUM_WORDS": nlp._NUM_WORDS, "COUNT_NOUNS": nlp._COUNT_NOUNS, "ORDINALS": nlp._ORDINALS,
            "AZ_WORDS": sorted(nlp._AZ_WORDS), "EN_WORDS": sorted(nlp._EN_WORDS)},
    "entities": {"CITY_ALIASES": entities.CITY_ALIASES, "BASE_FORMS": sorted(entities._BASE_FORMS),
                 "TITLE_STOP": sorted(entities._TITLE_STOP)},
    "data": {n: json.load(open(ROOT / "data" / f"{n}.json", encoding="utf-8"))
             for n in ("flights", "products", "movies", "cinemas", "showtimes")},
}
(ROOT / "web" / "tables.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print("ok", len(json.dumps(out)))
