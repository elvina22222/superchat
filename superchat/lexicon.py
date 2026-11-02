"""Hand-written multilingual cue lists (EN / AZ / RU).

All patterns run on text that went through `nlp.norm`, so Azerbaijani letters are
already folded to ASCII (ə->e, ş->s, ç->c, ğ->g, ı->i, ö->o, ü->u).
Patterns are matched at the start of a word (see `nlp.has`).
"""

# ---- strong cues: nouns/verbs that name the topic -------------------------------
FLIGHT_STRONG = [
    r"flights?\b", r"fly(?:ing)?\b", r"airlines?", r"airports?", r"planes?\b", r"aviasales",
    r"layovers?", r"round[- ]trip", r"one[- ]way", r"boarding", r"(?:air|plane) tickets?",
    r"ucus\w*", r"ucmaq\w*", r"ucag\w*", r"aviabilet\w*", r"aviasirket\w*", r"hava limani\w*", r"reys\w*",
    r"teyyare\w*", r"gedis[- ]qayidis",
    r"рейс\w*", r"перел[её]т\w*", r"пол[её]т\w*", r"лет[еи]ть", r"улет\w*", r"самол[её]т\w*", r"авиа\w*",
    r"аэропорт\w*", r"авиакомпани\w*",
]
SHOP_STRONG = [
    r"buy(?:ing)?\b", r"purchase", r"products?\b", r"shop(?:ping)?\b", r"(?:my |the )?cart\b", r"basket",
    r"head\s?phones?", r"earbuds?", r"earphones?", r"speakers?\b", r"laptops?", r"notebooks?\b",
    r"backpacks?", r"bags?\b", r"(?:smart\s?)?phones?\b", r"smart\s?watch\w*", r"watches\b", r"power\s?banks?",
    r"gadgets?", r"electronics", r"shoes?\b", r"sneakers?", r"coffee (?:machine|maker)s?", r"espresso",
    r"board games?", r"gifts?\b", r"computers?", r"birmarket", r"in stock", r"out of stock",
    r"al(?:maq|mag|ir|im)\b", r"satin al\w*", r"sebet\w*", r"mehsul\w*", r"stokda", r"anbarda", r"qulaqliq\w*",
    r"qulaqciq\w*", r"noutbuk\w*", r"komputer\w*", r"canta\w*", r"telefon\w*", r"smartfon\w*", r"agilli saat\w*",
    r"dinamik\w*", r"elektronika", r"ayaqqabi\w*", r"qehve\w*", r"stolustu oyun\w*", r"hediyye\w*",
    r"купить", r"куплю", r"покуп\w*", r"корзин\w*", r"товар\w*", r"в наличии", r"наличи\w*", r"наушник\w*",
    r"ноутбук\w*", r"компьютер\w*", r"рюкзак\w*", r"сумк\w*", r"телефон\w*", r"смартфон\w*", r"умн\w* час\w*",
    r"часы", r"колонк\w*", r"электроник\w*", r"кроссовк\w*", r"обув\w*", r"кофемашин\w*",
    r"настольн\w* игр\w*", r"подар\w*",
]
CINEMA_STRONG = [
    r"movies?\b", r"films?\b", r"cinemas?", r"cinemaplus", r"playing\b", r"showing\b", r"showtimes?",
    r"screenings?", r"what'?s on\b", r"sci-?fi", r"science fiction", r"comed(?:y|ies)", r"dramas?\b",
    r"thrillers?", r"horror", r"animat\w*", r"cartoons?", r"romance", r"romantic", r"action (?:movie|film)s?", r"adventure", r"mystery", r"family (?:movie|film)s?",
    r"to watch\b", r"watch (?:a |an |some|something|tonight)", r"izlemek\w*", r"baxmaq\w*", r"посмотреть",
    r"film\w*", r"kino\w*", r"seans\w*", r"ne gedir", r"neler gedir", r"elmi[- ]?fantasti\w*", r"fantasti\w*",
    r"komedi\w*", r"dram\b", r"triller\w*", r"qorxu film\w*", r"cizgi film\w*", r"romanti\w*", r"dovus\w*",
    r"фильм\w*", r"кино\w*", r"кинотеатр\w*", r"сеанс\w*", r"ид[её]т\b", r"показыва\w*", r"фантастик\w*",
    r"комеди\w*", r"драм\w*", r"триллер\w*", r"ужас\w*", r"мульт\w*", r"мелодрам\w*", r"боевик\w*", r"приключен\w*", r"детектив\w*", r"мистик\w*", r"macera\w*", r"sirr\w*",
]

# ---- weak cues: attributes that lean towards one domain but are typical of follow-ups ----
FLIGHT_WEAK = [r"direct\b", r"non-?stop", r"stops?\b", r"baggage", r"luggage", r"depart\w*", r"arriv\w*",
               r"birbasa", r"aktarma\w*", r"baqaj\w*", r"yuk\b", r"прям\w*", r"пересадк\w*", r"багаж\w*",
               r"вылет\w*", r"прил[её]т\w*"]
SHOP_WEAK = [r"do you (?:have|sell)", r"sell\b", r"satirsiniz", r"продаете", r"продаёте", r"stock\b", r"available\b", r"add\b", r"remove\b", r"brand\w*", r"colou?r\w*", r"warranty",
             r"elave et\w*", r"sil\b", r"rengi?\w*", r"marka\w*", r"var ?mi", r"добав\w*", r"удал\w*",
             r"убер\w*", r"цвет\w*", r"бренд\w*", r"есть ли"]
CINEMA_WEAK = [r"hall\b", r"zal\b", r"зал\b", r"subtit\w*"]

# shared booking vocabulary — needs context to resolve
BOOKING = [r"book\w*", r"reserve\w*", r"reservation", r"tickets?", r"seats?\b", r"bron\w*", r"rezerv\w*",
           r"bilet\w*", r"yer\b", r"yerler\w*", r"заброн\w*", r"бронир\w*", r"бронь", r"билет\w*", r"мест[аоу]?\b"]

# anaphora / ellipsis markers -> message depends on earlier turns
FOLLOWUP = [
    r"(?:the|that|this) (?:[\w-]+ )?one\b", r"(?:cheap|expensive|direct|earl|lat|fast|short)\w* one\b",
    r"\bit\b", r"\bthem\b", r"\bthat\b", r"\bthose\b", r"\bthis one", r"the same", r"and (?:for|on|what|how)\b",
    r"what about", r"how about", r"back to", r"go back", r"return to", r"cheaper", r"cheapest", r"instead",
    r"is it\b", r"are they", r"more expensive", r"which one", r"another",
    r"onu\b", r"bunu\b", r"o\b", r"hemin", r"bes\b", r"ucuz olan\w*", r"daha ucuz\w*", r"en ucuz\w*",
    r"geri qayid\w*", r"qayidaq", r"ikincisi\w*", r"birincisi\w*", r"sonuncusu\w*",
    r"его\b", r"е[её]\b", r"их\b", r"этот", r"эта", r"это", r"тот\b", r"та\b", r"а (?:на|в|что|как)\b",
    r"подешевле", r"дешевле", r"самый дешев\w*", r"вернемся", r"вернёмся", r"назад к", r"а если",
]

VAGUE = [
    r"something", r"anything", r"recommend\w*", r"suggest\w*", r"surprise me", r"show me (?:something|what)",
    r"what do you have", r"what can you", r"help me", r"i want to book", r"book it", r"i'?m bored",
    r"bir sey", r"ne(?:ler)? var", r"meslehet\w*", r"tovsiye\w*", r"teklif\w*", r"darixir\w*",
    r"что[- ]нибудь", r"что[- ]то", r"посовету\w*", r"порекоменду\w*", r"предлож\w*", r"скучно",
    r"how much", r"price\b", r"qiymet\w*", r"сколько стоит", r"цен[аы]",
]

GREETING = [r"hi\b", r"hello", r"hey\b", r"good (?:morning|evening|afternoon)", r"salam", r"sabahiniz",
            r"привет", r"здравствуй\w*", r"добрый (?:день|вечер)", r"thanks?\b", r"thank you", r"sag ?ol",
            r"tesekkur\w*", r"спасибо"]

OUT_OF_SCOPE = [r"weather", r"forecast", r"temperature", r"news\b", r"football", r"recipe", r"joke",
                r"hotels?\b", r"taxi", r"translate", r"homework", r"stocks? market", r"bitcoin", r"exchange rate",
                r"hava (?:nec|nece|necedir|proqnoz\w*|haqqinda)", r"hava\b(?! limani)", r"xeber\w*", r"futbol\w*",
                r"resept\w*", r"zarafat\w*", r"otel\w*", r"taksi\w*", r"мезенн\w*",
                r"погод\w*", r"новост\w*", r"футбол\w*", r"рецепт\w*", r"анекдот\w*", r"шутк\w*", r"отел[ья]\w*",
                r"гостиниц\w*", r"такси", r"курс (?:валют|доллар)\w*"]
