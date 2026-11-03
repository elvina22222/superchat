// SuperChat engine — JavaScript port of the Python package (superchat/), so the chat runs in the browser.
// Cue lists, reply texts and data come from tables.json (exported from the Python code by export_tables.py).
(function (root) {
"use strict";

function createSuperChat(T) {
  const D = T.data;
  // ------------------------------------------------------------------ regex helpers
  const L = "[a-zа-я0-9_]";
  const BOUND = `(?:(?<!${L})(?=${L})|(?<=${L})(?!${L}))`;
  const cache = new Map();
  function U(p) {
    return p.replace(/\[\\w-\]/g, "[a-zа-я0-9_-]").replace(/\\b/g, BOUND).replace(/\\w/g, L);
  }
  function rx(p, flags = "") {
    const k = p + "\u0000" + flags;
    if (!cache.has(k)) cache.set(k, new RegExp(U(p), flags));
    return cache.get(k);
  }
  const has = (t, ...pats) => pats.some(p => rx("(?<![a-zа-я0-9])" + p).test(t));
  const hits = (t, pats) => pats.filter(p => has(t, p));
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  // ------------------------------------------------------------------ nlp
  const REF = "2026-11-02";
  const FOLD = { "ə": "e", "ı": "i", "ö": "o", "ü": "u", "ç": "c", "ş": "s", "ğ": "g", "ё": "е" };
  function norm(text) {
    let t = text.replace(/İ/g, "i").replace(/I/g, "i").toLowerCase().replace(/̇/g, "");
    t = t.replace(/[əıöüçşğё]/g, c => FOLD[c]);
    t = t.replace(/[“”«»"']/g, " ");
    return t.replace(/\s+/g, " ").trim();
  }
  const tokens = t => t.match(/[a-zа-я0-9]+/g) || [];
  const isQuestion = t => t.includes("?") || has(t, "is it", "are they", "does it", "mi\\b", "mu\\b", "midir",
    "\\w+(?:dir|dur|dirmi)\\b", "ли\\b");

  const AZW = new Set(T.nlp.AZ_WORDS), ENW = new Set(T.nlp.EN_WORDS);
  function detectLanguage(text) {
    const lo = text.toLowerCase();
    const cyr = (lo.match(/[а-яё]/g) || []).length, lat = (lo.match(/[a-zəğışçöü]/g) || []).length;
    if (cyr > lat) return "ru";
    if (/[əğışçöü]/.test(lo)) return "az";
    const tk = tokens(norm(text));
    const az = tk.filter(x => AZW.has(x)).length, en = tk.filter(x => ENW.has(x)).length;
    if (az === 0 && en === 0) return null;
    return az > en ? "az" : "en";
  }

  const NUMW = T.nlp.NUM_WORDS, NUMALT = Object.keys(NUMW).join("|");
  const MONTH_ALT = Object.values(T.nlp.MONTHS).join("|");
  function countIn(t) {
    let m = rx("(?<![a-zа-я0-9])(\\d{1,2}|" + NUMALT + ")\\s+" + T.nlp.COUNT_NOUNS + "(?![a-zа-я])").exec(t);
    if (m) return /^\d+$/.test(m[1]) ? +m[1] : NUMW[m[1]];
    m = rx("(?:for|на)\\s+(\\d|" + NUMALT + ")(?![a-zа-я0-9])(?!\\s*(?:azn|manat|man|ман|[a-zа-я]*\\s*(?:" + MONTH_ALT + ")))").exec(t);
    if (m) return /^\d+$/.test(m[1]) ? +m[1] : NUMW[m[1]];
    return null;
  }
  function ordinalIn(t) {
    for (const [p, i] of T.nlp.ORDINALS) if (has(t, p + "(?![a-zа-я])")) return i;
    const m = /(?:#|№|number|option|nomre|номер|вариант)\s*(\d{1,2})(?!\d)/.exec(t) ||
      /(?<![\d.:])(\d{1,2})\s*-?\s*(?:ci|cu|ji|-?й|-?ой|-?ая)(?![a-zа-я])/.exec(t);
    return m ? +m[1] - 1 : null;
  }
  function moneyRange(t) {
    const num = "(\\d+(?:[.,]\\d+)?)", f = s => parseFloat(s.replace(",", "."));
    let m = rx("(?:between|arasi|от)\\s*" + num + "\\s*(?:azn|manat|man)?\\s*(?:and|-|ve|до|ile)\\s*" + num).exec(t);
    if (m) return [f(m[1]), f(m[2])];
    m = rx(num + "\\s*-\\s*" + num + "\\s*(?:azn|manat|ман)").exec(t);
    if (m) return [f(m[1]), f(m[2])];
    let lo = null, hi = null;
    m = rx("(?:under|below|less than|cheaper than|up to|max(?:imum)?|до|дешевле|меньше|не дороже)\\s*" + num).exec(t) ||
        rx(num + "\\s*(?:azn|manat|man)?\\s*(?:-?(?:dan|den|ден|дан))?\\s*(?:ucuz|asagi|az|qeder)").exec(t);
    if (m) hi = f(m[1]);
    m = rx("(?:over|above|more than|from|от|дороже|больше)\\s*" + num + "\\s*(?:azn|manat|ман)").exec(t) ||
        rx(num + "\\s*(?:azn|manat|man)?\\s*-?(?:dan|den)\\s*(?:baha|yuxari|cox)").exec(t);
    if (m) lo = f(m[1]);
    return [lo, hi];
  }
  const pad = n => String(n).padStart(2, "0");
  function mkDate(day, month) {
    const d = new Date(Date.UTC(2026, month - 1, day));
    return d.getUTCMonth() === month - 1 ? `2026-${pad(month)}-${pad(day)}` : null;
  }
  function addDays(iso, n) { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
  const weekday = iso => (new Date(iso + "T00:00:00Z").getUTCDay() + 6) % 7; // Mon=0
  function findDates(t) {
    const found = [], taken = new Array(t.length).fill(false);
    const add = (m, iso) => {
      if (!iso) return;
      for (let i = m.index; i < m.index + m[0].length; i++) if (taken[i]) return;
      found.push([m.index, iso]);
      for (let i = m.index; i < m.index + m[0].length; i++) taken[i] = true;
    };
    const all = (p, fn) => { for (const m of t.matchAll(rx(p, "g"))) fn(m); };
    all("(20\\d\\d)-(\\d\\d)-(\\d\\d)", m => add(m, `${m[1]}-${m[2]}-${m[3]}`));
    for (const [mon, pat] of Object.entries(T.nlp.MONTHS)) {
      all("(\\d{1,2})\\s*(?:st|nd|rd|th|-?(?:ci|cu|si|su))?\\s*(?:of\\s+)?" + pat + "(?![a-z])", m => add(m, mkDate(+m[1], +mon)));
      all(pat + "\\s+(\\d{1,2})(?!\\d)(?:st|nd|rd|th)?", m => add(m, mkDate(+m[1], +mon)));
    }
    all("(?<![\\d:])(\\d{1,2})[./](\\d{1,2})(?![\\d:])", m => add(m, mkDate(+m[1], +m[2])));
    for (const [pat, wd] of T.nlp.WEEKDAYS)
      all("(?<![a-zа-я])" + pat + "(?![a-zа-я])", m => add(m, addDays(REF, ((wd - weekday(REF)) % 7 + 7) % 7)));
    all("(?<![a-zа-я])" + T.nlp.TODAY, m => add(m, REF));
    all("(?<![a-zа-я])" + T.nlp.TOMORROW + "(?![a-zа-я])", m => add(m, addDays(REF, 1)));
    return found.sort((a, b) => a[0] - b[0]).map(x => x[1]);
  }
  const WD = { en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], az: ["B.e.", "Ç.a.", "Ç.", "C.a.", "C.", "Ş.", "B."],
               ru: ["пн", "вт", "ср", "чт", "пт", "сб", "вс"] };
  const MO = { en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
               az: ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avq", "sen", "okt", "noy", "dek"],
               ru: ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"] };
  function prettyDate(iso, lang) {
    iso = iso.slice(0, 10);
    return `${WD[lang][weekday(iso)]} ${+iso.slice(8, 10)} ${MO[lang][+iso.slice(5, 7) - 1]}`;
  }
  const f1 = x => (Number.isInteger(x) ? x.toFixed(1) : String(x));   // Python prints 4.0, not 4
  const money = v => (Math.round(v * 100) / 100).toFixed(2).replace(/0+$/, "").replace(/\.$/, "") + " AZN";
  function hm(min, lang) {
    const u = { en: ["h", "m"], az: ["s", "dəq"], ru: ["ч", "мин"] }[lang];
    return `${Math.floor(min / 60)}${u[0]} ${pad(min % 60)}${u[1]}`;
  }
  const pick = (arr, i) => (i === null || i === undefined || !arr.length) ? null : (i < 0 ? arr[arr.length + i] : arr[i]) || null;
  function fmt(table, key, lang, kw) {
    const e = table[key]; let s = e[lang] || e.en;
    if (kw) s = s.replace(/\{(\w+)\}/g, (_, k) => (kw[k] !== undefined ? kw[k] : `{${k}}`));
    return s;
  }

  // ------------------------------------------------------------------ repositories (mock data, in memory)
  const flightsDB = JSON.parse(JSON.stringify(D.flights)), productsDB = D.products, moviesDB = D.movies,
        cinemasDB = D.cinemas, showsDB = JSON.parse(JSON.stringify(D.showtimes));
  let refF = 0, refT = 0;
  const repo = {
    flightSearch(o, d, date) {
      return flightsDB.filter(f => (!o || f.origin.code === o) && (!d || f.destination.code === d) &&
        (!date || f.departure_local.startsWith(date))).map(f => ({ ...f }));
    },
    flight: id => flightsDB.find(f => f.id === id) || null,
    reserveFlight(id, n) {
      const f = flightsDB.find(x => x.id === id);
      if (f.seats_available < n) return { ok: false, seats_available: f.seats_available };
      f.seats_available -= n;
      return { ok: true, reference: `F-${1000 + (++refF)}`, total_azn: f.price_azn * n };
    },
    product: id => productsDB.find(p => p.id === id) || null,
    movie: id => moviesDB.find(m => m.id === id) || null,
    showtimes(mid, date, cid) {
      return showsDB.filter(s => (!mid || s.movie_id === mid) && (!date || s.date === date) && (!cid || s.cinema_id === cid))
        .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
    },
    show: id => showsDB.find(s => s.id === id) || null,
    reserveShow(id, n) {
      const s = showsDB.find(x => x.id === id);
      if (s.seats_available < n) return { ok: false, seats_available: s.seats_available };
      s.seats_available -= n;
      return { ok: true, reference: `T-${1000 + (++refT)}`, total_azn: s.price_azn * n };
    },
  };

  // ------------------------------------------------------------------ entity index
  const cityNames = {};
  for (const f of flightsDB) { cityNames[f.origin.code] = f.origin.city; cityNames[f.destination.code] = f.destination.city; }
  for (const f of flightsDB) if (f.via && !cityNames[f.via]) cityNames[f.via] = f.via;
  const cityPatterns = {};
  for (const [code, city] of Object.entries(cityNames))
    cityPatterns[code] = [...(T.entities.CITY_ALIASES[code] || []), esc(norm(city)) + "\\w*"];
  const BASE = new Set(T.entities.BASE_FORMS), TSTOP = new Set(T.entities.TITLE_STOP);
  const airlines = [...new Set(flightsDB.map(f => f.airline))].sort();
  const flightNumbers = {};
  for (const f of flightsDB) (flightNumbers[f.flight_number.toLowerCase()] ||= []).push(f.id);
  const brands = [...new Set(productsDB.map(p => p.brand))].sort();
  const moviePatterns = {};
  for (const m of moviesDB) {
    const title = norm(m.title), pats = [esc(title)];
    if (title.startsWith("the ")) pats.push(esc(title.slice(4)));
    for (const tok of title.split(" ")) if (tok.length >= 5 && !TSTOP.has(tok)) pats.push(esc(tok) + "\\b");
    moviePatterns[m.id] = pats;
  }
  const cinemaPatterns = {};
  for (const c of cinemasDB) {
    const short = norm(c.name.replace("CinemaPlus", "")).trim(), first = short.split(" ")[0];
    cinemaPatterns[c.id] = [esc(norm(c.name)), esc(short), ...({
      ganjlik: ["ganjlik\\w*", "gencli\\w*", "гянджлик\\w*"],
      sumgayit: ["sumgayit\\w*", "sumqayit\\w*", "сумгаит\\w*", "сумгайыт\\w*"],
      "28": ["28 mall", "28 молл", "28 мол\\w*"] }[first] || [])];
  }
  const E = {
    findCities(t) {
      const hitsArr = [];
      for (const [code, pats] of Object.entries(cityPatterns)) {
        for (const p of pats) {
          const m = rx("(?<![a-zа-я0-9])" + p).exec(t);
          if (!m) continue;
          const word = /^[a-zа-я0-9]+/.exec(t.slice(m.index))[0], before = t.slice(0, m.index);
          let role = null;
          if (/(?:from|из|от|с)\s*$/.test(before)) role = "from";
          else if (/(?:to|into|в|во|до|на|->|–|-)\s*$/.test(before)) role = "to";
          else if (/(?:dan|den|nan|nen)$/.test(word) && word.length > 5) role = "from";
          else if (!BASE.has(word) && /(?:ya|ye|a|e)$/.test(word) && !/[iu]$/.test(word) && word.length > 4 && /^[a-z]/.test(word)) role = "to";
          hitsArr.push({ pos: m.index, code, role });
          break;
        }
      }
      hitsArr.sort((a, b) => a.pos - b.pos);
      const seen = new Set();
      return hitsArr.filter(h => !seen.has(h.code) && seen.add(h.code));
    },
    findAirline: t => airlines.find(a => has(t, esc(norm(a).split(" ")[0]))) || null,
    findFlightNumber(t) {
      for (const fn of Object.keys(flightNumbers))
        if (new RegExp("(?<![a-z0-9])" + fn.slice(0, 2) + "\\s?-?" + fn.slice(2) + "(?!\\d)").test(t)) return fn;
      return null;
    },
    findBrand: t => brands.find(b => has(t, esc(norm(b)) + "\\b")) || null,
    findProductsByName: t => productsDB.filter(p => ["en", "az", "ru"].some(l => t.includes(norm(p.name[l])))).map(p => p.id),
    findMovies(t) {
      const h = [];
      for (const [id, pats] of Object.entries(moviePatterns))
        for (const p of pats) { const m = rx("(?<![a-zа-я0-9])" + p).exec(t); if (m) { h.push([m.index, id]); break; } }
      return h.sort((a, b) => a[0] - b[0]).map(x => x[1]);
    },
    maskMovies(t) { for (const pats of Object.values(moviePatterns)) t = t.replace(rx(pats[0], "g"), " "); return t; },
    findCinema(t) {
      for (const [id, pats] of Object.entries(cinemaPatterns)) if (pats.some(p => p && has(t, p))) return id;
      return null;
    },
  };

  // ------------------------------------------------------------------ session
  const DOMAINS = ["flights", "shopping", "cinema"];
  function newSession() {
    return { lang: "en", last_domain: null, preferences: {}, pending: null, history: [], domains: {
      flights: { query: {}, filters: {}, results: [], return_results: [], selected: null, bookings: [] },
      shopping: { query: {}, results: [], selected: null, cart: {}, history: [] },
      cinema: { query: {}, movies: [], movie: null, showtimes: [], showtime: null, last_list: null, bookings: [], intent: null } } };
  }
  function hasState(s, d) {
    const x = s.domains[d];
    if (d === "flights") return !!(x.results.length || x.selected || Object.keys(x.query).length);
    if (d === "shopping") return !!(x.results.length || x.selected || Object.keys(x.cart).length);
    return !!(x.movies.length || x.movie || x.showtimes.length);
  }

  // ------------------------------------------------------------------ router
  const LX = T.lex;
  function score(t) {
    const cues = [], strong = { flights: 0, shopping: 0, cinema: 0 }, weak = { flights: 0, shopping: 0, cinema: 0 };
    const movies = E.findMovies(t), masked = E.maskMovies(t);
    if (movies.length) { strong.cinema += 2; cues.push("movie:" + movies.join(",")); }
    if (E.findCinema(t)) { strong.cinema += 2; cues.push("cinema-name"); }
    for (const [d, pats] of [["flights", LX.FLIGHT_STRONG], ["shopping", LX.SHOP_STRONG], ["cinema", LX.CINEMA_STRONG]]) {
      const h = hits(masked, pats); strong[d] += h.length; h.forEach(p => cues.push(`${d}:${p}`));
    }
    for (const [d, pats] of [["flights", LX.FLIGHT_WEAK], ["shopping", LX.SHOP_WEAK], ["cinema", LX.CINEMA_WEAK]])
      weak[d] += hits(masked, pats).length;
    const cities = E.findCities(masked);
    for (const c of cities) {
      if (c.code === "GYD" && !c.role && cities.length === 1) weak.flights += 1; else strong.flights += 2;
      cues.push("city:" + c.code);
    }
    if (E.findAirline(masked) || E.findFlightNumber(masked)) { strong.flights += 2; cues.push("airline/flight-no"); }
    if (E.findBrand(t) || E.findProductsByName(t).length) { strong.shopping += 2; cues.push("brand/product"); }
    return { strong, weak, cues };
  }
  function split(t, doms) {
    const parts = t.split(/\s*(?:,|;|\band also\b|\band\b|\bplus\b|\balso\b|\bve\b|\bhem de\b|(?<![а-я])и(?![а-я])|(?<![а-я])а также(?![а-я])|(?<![а-я])также(?![а-я]))\s+/);
    const out = {}; doms.forEach(d => out[d] = []);
    let last = null; const shared = [];
    for (const part of parts) {
      if (!part) continue;
      const s = score(part).strong;
      const best = doms.reduce((a, b) => (s[b] > s[a] ? b : a), doms[0]);
      if (s[best] === 0) { if (last) out[last].push(part); else shared.push(part); continue; }
      out[best].push(part); last = best;
    }
    const res = {};
    for (const d of doms) res[d] = out[d].length ? [...shared, ...out[d]].join(" ") : t;
    return res;
  }
  function route(t, session) {
    const { strong, weak, cues } = score(t);
    const doms = DOMAINS.filter(d => strong[d] > 0);
    const followup = hits(t, LX.FOLLOWUP).length > 0 || ordinalIn(t) !== null;
    const booking = hits(t, LX.BOOKING).length > 0, vague = hits(t, LX.VAGUE).length > 0, oos = hits(t, LX.OUT_OF_SCOPE).length > 0;
    const dates = findDates(t), nTok = tokens(t).length;
    const dec = (category, domains, extra) => ({ category, domains, cues: extra ? [...cues, extra] : cues });
    const lexical = cues.filter(c => DOMAINS.includes(c.split(":")[0])).length;
    const entityTopic = cues.some(c => /^(movie:|brand\/product|cinema-name|airline)/.test(c));
    if (oos && lexical === 0 && !entityTopic) return dec("out_of_scope", [], "oos-cue overrides place name");
    if (doms.length >= 2) { const d = dec("mixed", doms); d.clauses = split(t, doms); return d; }
    if (doms.length === 1) {
      const dom = doms[0];
      return followup && hasState(session, dom) ? dec("followup", [dom], "anaphora+state") : dec(dom, [dom]);
    }
    if (oos) return dec("out_of_scope", [], "oos-cue");
    const weakDoms = DOMAINS.filter(d => weak[d] > 0);
    if (weakDoms.length === 1) return dec(hasState(session, weakDoms[0]) ? "followup" : weakDoms[0], weakDoms, "weak-cue");
    const contextual = followup || booking || dates.length > 0 || countIn(t) !== null ||
      (vague && has(t, "how much", "price", "qiymet", "сколько", "цен"));
    if (contextual) {
      let cands = DOMAINS.filter(d => hasState(session, d));
      if (booking) {
        const fc = cands.filter(d => d === "flights" || d === "cinema");
        cands = fc.length ? fc : (has(t, "buy", "al\\b", "куп") ? cands.filter(d => d === "shopping") : []);
      }
      if (cands.includes(session.last_domain)) return dec("followup", [session.last_domain], "context:last-domain");
      if (cands.length === 1) return dec("followup", cands, "context:only-domain-with-state");
      return dec("ambiguous", [], "needs-context");
    }
    if (vague) return dec("ambiguous", [], "vague");
    if (hits(t, LX.GREETING).length && nTok <= 6) return dec("greeting", []);
    if (session.pending && nTok <= 4) return dec("ambiguous", [], "unclear-answer");
    return dec("out_of_scope", [], "no-cue");
  }

  // ------------------------------------------------------------------ flights module
  const FL = T.flights, fs = (k, lang, kw) => fmt(FL.STR, k, lang, kw);
  const city = c => cityNames[c] || c;
  const fStops = (f, lang) => f.stops === 0 ? fs("direct", lang) : fs("stops", lang, { n: f.stops, via: city(f.via) });
  const fSeats = (f, lang) => f.seats_available ? fs("seats", lang, { n: f.seats_available }) : fs("sold_out", lang);
  const fLine = (i, f, lang) => `${i}. ${f.airline} ${f.flight_number} · ${f.departure_local.slice(11)}→${f.arrival_local.slice(11)} · ${hm(f.duration_min, lang)} · ${fStops(f, lang)} · ${money(f.price_azn)} · ${fSeats(f, lang)}`;
  const fDetails = (f, lang) => fs("details", lang, { airline: f.airline, fn: f.flight_number, date: prettyDate(f.departure_local, lang),
    dep: f.departure_local.slice(11), arr: f.arrival_local.slice(11), o: f.origin.code, d: f.destination.code, dur: hm(f.duration_min, lang),
    stops: fStops(f, lang), bag: f.baggage_kg, cabin: f.cabin, seats: fSeats(f, lang), price: money(f.price_azn) });
  const directAnswer = (f, lang) => f.stops === 0 ? fs("is_direct_yes", lang) : fs("is_direct_no", lang, { n: f.stops, via: city(f.via) });
  function fParse(t) {
    const q = {}, cities = E.findCities(E.maskMovies(t));
    if (cities.length >= 2) {
      let [a, b] = cities;
      if (a.role === "to" || b.role === "from") [a, b] = [b, a];
      q.origin = a.code; q.destination = b.code;
    } else if (cities.length === 1) q[cities[0].role === "from" ? "origin" : "destination"] = cities[0].code;
    const dates = findDates(t);
    if (dates.length) { q.date = dates[0]; if (dates.length > 1 && has(t, ...FL.RETURN)) q.return_date = dates[1]; }
    const f = {};
    if (has(t, ...FL.DIRECT)) f.direct = true;
    if (has(t, ...FL.CHEAP)) f.sort = "price"; else if (has(t, ...FL.FAST)) f.sort = "duration"; else if (has(t, ...FL.EARLY)) f.sort = "departure";
    if (has(t, ...FL.MORNING)) f.tod = "morning"; else if (has(t, ...FL.AFTERNOON)) f.tod = "afternoon"; else if (has(t, ...FL.EVENING)) f.tod = "evening";
    const al = E.findAirline(t); if (al) f.airline = al;
    const hi = moneyRange(t)[1]; if (hi) f.max_price = hi;
    return { q, f };
  }
  function fApply(list, f) {
    let out = list;
    if (f.direct) out = out.filter(x => x.stops === 0);
    if (f.airline) out = out.filter(x => x.airline === f.airline);
    if (f.max_price) out = out.filter(x => x.price_azn <= f.max_price);
    if (f.tod) { const r = { morning: [0, 12], afternoon: [12, 17], evening: [17, 24] }[f.tod];
      out = out.filter(x => { const h = +x.departure_local.slice(11, 13); return h >= r[0] && h < r[1]; }); }
    const key = { price: x => x.price_azn, duration: x => x.duration_min }[f.sort];
    return [...out].sort((a, b) => key ? key(a) - key(b) : a.departure_local.localeCompare(b.departure_local));
  }
  const NOT_PLACES = new Set(["the", "a", "an", "my", "book", "buy", "fly", "go", "travel", "get", "be", "see", "watch", "have", "find", "me",
    "it", "this", "that", "there", "and", "on", "in", "for", "cart", "basket", "economy", "business", "return", "come", "back", "morning",
    "evening", "night", "today", "tomorrow", "tonight"]);
  function unknownPlace(t) {
    const known = Object.values(cityPatterns).flat();
    for (const m of t.matchAll(/(?<![a-zа-я])(?:to|from|в|из)\s+([a-zа-я]{3,})/g)) {
      const w = m[1];
      if (NOT_PLACES.has(w) || findDates(w).length || known.some(p => rx("^" + p).test(w))) continue;
      if (/^[a-z]/.test(w) && /^(to|from)/.test(m[0])) return w;
      if (/^[а-я]/.test(w) && !/^(?:котор|эт|т[оа]|субб|пятн|понед|воскр|сред|четв|вторн|январ|феврал|ноябр|декабр)/.test(w)) return w;
    }
    return null;
  }
  function flightsHandle(turn, session) {
    const st = session.domains.flights, { t, lang } = turn;
    const { q: qn, f: fn } = fParse(t);
    const results = st.results.map(repo.flight).filter(Boolean);
    let chosen = null;
    const fno = E.findFlightNumber(t);
    if (fno) {
      const ids = st.results.filter(i => repo.flight(i).flight_number.toLowerCase() === fno);
      chosen = repo.flight(ids[0] || flightNumbers[fno][0]);
    } else if (results.length && !qn.destination && !qn.origin && !qn.date) {
      chosen = pick(results, ordinalIn(t));
      if (!chosen && has(t, ...FL.SELECT_WORDS) && !has(t, ...FL.FLIGHTISH)) {
        const sf = { ...fn }; if (isQuestion(t)) delete sf.direct;
        const ranked = fApply(results, sf);
        if (ranked.length && Object.keys(sf).length) chosen = ranked[0];
      }
    }
    const wants = has(t, ...FL.RESERVE), cnt = countIn(t);
    if (cnt) session.preferences.passengers = cnt;
    const n = cnt || session.preferences.passengers || 1;
    if (wants) {
      const target = chosen || (st.selected ? repo.flight(st.selected) : null) || (results.length === 1 ? results[0] : null);
      if (!target) {
        if (results.length) return [fs("which_flight", lang), ...results.map((f, i) => fLine(i + 1, f, lang))].join("\n");
        if (!Object.keys(qn).length) return fs("need_route", lang);
      } else {
        st.selected = target.id;
        const r = repo.reserveFlight(target.id, n);
        if (!r.ok) return fs("not_enough", lang, { n: r.seats_available, fn: target.flight_number });
        st.bookings.push(r);
        return fs("booked", lang, { fn: target.flight_number, date: prettyDate(target.departure_local, lang), n, total: money(r.total_azn), ref: r.reference });
      }
    }
    if (has(t, ...FL.COMPARE) && results.length) {
      const idxs = [];
      for (const m of t.matchAll(/(?:first|second|third|fourth|1st|2nd|3rd|birinci|ikinci|ucuncu|перв[а-я]*|втор[а-я]*|трет[а-я]*|\d)/g)) {
        const k = /^\d+$/.test(m[0]) ? +m[0] - 1 : ordinalIn(m[0]);
        if (k !== null && k >= 0 && k < results.length && !idxs.includes(k)) idxs.push(k);
      }
      const pool = idxs.length >= 2 ? idxs.map(k => results[k]) : results.slice(0, 5);
      const c = pool.reduce((a, b) => b.price_azn < a.price_azn ? b : a), fa = pool.reduce((a, b) => b.duration_min < a.duration_min ? b : a);
      return [fs("compare_head", lang), ...pool.map((f, i) => fLine(i + 1, f, lang)), fs("compare_best", lang, { c: c.flight_number, f: fa.flight_number })].join("\n");
    }
    if (chosen) {
      st.selected = chosen.id;
      const out = [];
      if (has(t, ...FL.DIRECT) && isQuestion(t)) out.push(directAnswer(chosen, lang));
      else if (fn.sort === "price" && ordinalIn(t) === null) out.push(fs("selected_cheapest", lang));
      out.push(fDetails(chosen, lang));
      return out.join("\n");
    }
    if (st.selected && !Object.keys(qn).length && (isQuestion(t) || has(t, "baggage", "baqaj", "багаж")) && !has(t, ...FL.FLIGHTISH)) {
      const sel = repo.flight(st.selected), out = [];
      if (has(t, ...FL.DIRECT)) out.push(directAnswer(sel, lang));
      out.push(fDetails(sel, lang));
      return out.join("\n");
    }
    if (unknownPlace(t)) return fs("unknown_city", lang, { cities: Object.values(cityNames).sort().join(", ") });
    const q = (!qn.destination || qn.destination === st.query.destination || turn.category === "followup") ? { ...st.query } : {};
    Object.assign(q, qn);
    if (q.destination && !q.origin) q.origin = q.destination !== "GYD" ? "GYD" : null;
    if (!q.destination) { if (q.origin && q.origin !== "GYD") q.destination = "GYD"; else return fs("need_route", lang); }
    if (!cityNames[q.origin] || !cityNames[q.destination]) return fs("unknown_city", lang, { cities: Object.values(cityNames).sort().join(", ") });
    const filters = turn.category === "followup" ? { ...st.filters } : {};
    Object.assign(filters, fn);
    st.query = q; st.filters = filters; st.selected = null;
    const rname = `${city(q.origin)} → ${city(q.destination)}`;
    const allRoute = repo.flightSearch(q.origin, q.destination);
    if (!q.date) {
      if (!allRoute.length) return fs("no_route", lang);
      const found = fApply(allRoute, filters);
      st.results = found.map(f => f.id);
      return [fs("results_nodate", lang, { route: rname }),
        ...found.slice(0, 8).map((f, i) => `${i + 1}. ${prettyDate(f.departure_local, lang)} · ` + fLine(i + 1, f, lang).slice(3)),
        fs("pick_hint", lang)].join("\n");
    }
    const found = fApply(repo.flightSearch(q.origin, q.destination, q.date), filters);
    st.results = found.map(f => f.id);
    const lines = [];
    if (!found.length) {
      lines.push(fs("none", lang, { route: rname, date: prettyDate(q.date, lang), filters: Object.keys(filters).length ? fs("filtered", lang) : "" }));
      if (allRoute.length) {
        const pool = fApply(allRoute, filters).length ? fApply(allRoute, filters) : allRoute;
        lines.push(fs("other_dates", lang, { dates: [...new Set(pool.map(f => f.departure_local.slice(0, 10)))].sort().map(d => prettyDate(d, lang)).join(", ") }));
      } else lines[0] = fs("no_route", lang);
    } else {
      lines.push(fs("results", lang, { route: rname, date: prettyDate(q.date, lang) }), ...found.map((f, i) => fLine(i + 1, f, lang)));
      if (found.length > 1) lines.push(fs("pick_hint", lang));
    }
    if (q.return_date) {
      const back = fApply(repo.flightSearch(q.destination, q.origin, q.return_date), {});
      st.return_results = back.map(f => f.id);
      const rr = `${city(q.destination)} → ${city(q.origin)}`;
      lines.push("");
      if (back.length) lines.push(fs("return_head", lang, { route: rr, date: prettyDate(q.return_date, lang) }), ...back.map((f, i) => fLine(i + 1, f, lang)));
      else lines.push(fs("none", lang, { route: rr, date: prettyDate(q.return_date, lang), filters: "" }));
    }
    return lines.join("\n");
  }

  // ------------------------------------------------------------------ shopping module
  const SH = T.shopping, ss = (k, lang, kw) => fmt(SH.STR, k, lang, kw);
  const TYPE_PRED = {
    headphones: p => /headphones|earbuds/i.test(p.name.en), speaker: p => p.name.en.includes("Speaker"),
    laptops: p => p.category === "computers", bags: p => p.name.en.includes("Backpack"), shoes: p => p.name.en.includes("Shoes"),
    coffee: p => p.name.en.includes("Coffee"), games: p => p.category === "gifts", phones: p => p.category === "phones",
    wearables: p => p.category === "wearables", accessories: p => p.category === "accessories", audio: p => p.category === "audio" };
  const pname = (p, lang) => p.name[lang] || p.name.en;
  const pstock = (p, lang) => p.stock > 0 ? ss("in_stock", lang, { n: p.stock }) : ss("out_stock", lang);
  const pLine = (i, p, lang) => `${i}. ${pname(p, lang)} — ${p.brand}, ${p.color} · ${money(p.price_azn)} · ★${f1(p.rating)} · ${pstock(p, lang)}`;
  const pDetails = (p, lang) => ss("details", lang, { name: pname(p, lang), brand: p.brand, price: money(p.price_azn), rating: f1(p.rating),
    color: p.color, stock: pstock(p, lang), desc: p.description || "" });
  const cartTotal = cart => Object.entries(cart).reduce((s, [id, n]) => s + repo.product(id).price_azn * n, 0);
  function sParse(t) {
    const q = {};
    for (const [k, pats] of Object.entries(SH.TYPES)) if (has(t, ...pats)) { q.type = k; break; }
    const b = E.findBrand(t); if (b) q.brand = b;
    for (const [c, pats] of Object.entries(SH.COLORS)) if (has(t, ...pats)) { q.color = c; break; }
    const [lo, hi] = moneyRange(t); if (lo) q.min = lo; if (hi) q.max = hi;
    if (has(t, ...SH.CHEAP) && !hi) q.sort = "price"; else if (has(t, ...SH.BEST)) q.sort = "rating"; else if (has(t, ...SH.EXPENSIVE)) q.sort = "-price";
    const ids = E.findProductsByName(t); if (ids.length) q.ids = ids;
    return q;
  }
  function sSearch(q) {
    let items = [...productsDB];
    if (q.ids) items = items.filter(p => q.ids.includes(p.id));
    if (q.type) items = items.filter(TYPE_PRED[q.type]);
    if (q.brand) items = items.filter(p => p.brand === q.brand);
    if (q.color) items = items.filter(p => p.color === q.color);
    const base = [...items].sort((a, b) => a.price_azn - b.price_azn);
    if (q.min) items = items.filter(p => p.price_azn >= q.min);
    if (q.max) items = items.filter(p => p.price_azn <= q.max);
    const cmp = { price: (a, b) => a.price_azn - b.price_azn, "-price": (a, b) => b.price_azn - a.price_azn, rating: (a, b) => b.rating - a.rating }[q.sort]
      || ((a, b) => ((a.stock === 0) - (b.stock === 0)) || a.price_azn - b.price_azn);
    return [items.sort(cmp), base];
  }
  const cond = (q, lang) => (q.max ? ss("under", lang, { v: money(q.max) }) : "") + (q.min ? ss("over", lang, { v: money(q.min) }) : "");
  const sameQ = (a, b) => JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());
  function shoppingHandle(turn, session) {
    const st = session.domains.shopping, { t, lang } = turn, qn = sParse(t);
    const results = st.results.map(repo.product).filter(Boolean);
    const sel = st.selected ? repo.product(st.selected) : null;
    const isSearch = !!(qn.min || qn.max || has(t, ...SH.SEARCH));
    let target = null;
    const idx = ordinalIn(t);
    if (idx !== null && results.length) target = pick(results, idx);
    else if (qn.ids && qn.ids.length === 1 && !isSearch) target = repo.product(qn.ids[0]);
    else if (results.length && has(t, "(?:cheap|expensive)\\w* one", "ucuz olan\\w*", "daha ucuz\\w*", "en ucuz\\w*", "подешевле", "самый дешев\\w*")) {
      const sorted = [...results].sort((a, b) => a.price_azn - b.price_azn);
      target = has(t, "expensive") ? sorted[sorted.length - 1] : sorted[0];
    } else if (results.length && qn.brand && !qn.type) {
      const inList = results.filter(p => p.brand === qn.brand); target = inList.length === 1 ? inList[0] : null;
    }
    const pronoun = has(t, "\\bit\\b", "\\bthis\\b", "\\bthat\\b", "onu\\b", "bunu\\b", "его\\b", "е[её]\\b", "этот", "это");
    if (has(t, ...SH.REMOVE) && (has(t, ...SH.CART) || Object.keys(st.cart).length)) {
      let item = target || (pronoun ? sel : null);
      if (!item && qn.type) item = Object.keys(st.cart).map(repo.product).find(TYPE_PRED[qn.type]) || null;
      if (!item || !st.cart[item.id]) return ss("not_in_cart", lang);
      delete st.cart[item.id];
      return ss("removed", lang, { name: pname(item, lang), total: money(cartTotal(st.cart)) });
    }
    if (has(t, ...SH.ADD) && (has(t, ...SH.CART) || target || pronoun || sel)) {
      const item = target || sel;
      if (!item) return ss("which", lang);
      st.selected = item.id;
      const n = countIn(t) || 1;
      if (item.stock <= 0) return ss("add_oos", lang, { name: pname(item, lang) });
      if ((st.cart[item.id] || 0) + n > item.stock) return ss("add_limit", lang, { n: item.stock, name: pname(item, lang) });
      st.cart[item.id] = (st.cart[item.id] || 0) + n;
      return ss("added", lang, { n, name: pname(item, lang), total: money(cartTotal(st.cart)) });
    }
    if (has(t, ...SH.CART)) {
      if (!Object.keys(st.cart).length) return ss("cart_empty", lang);
      const lines = [ss("cart", lang)];
      for (const [id, n] of Object.entries(st.cart)) { const p = repo.product(id); lines.push(`• ${n} × ${pname(p, lang)} — ${money(p.price_azn * n)}`); }
      lines.push(ss("total", lang, { total: money(cartTotal(st.cart)) }));
      return lines.join("\n");
    }
    if (has(t, ...SH.COMPARE)) {
      let pool = [];
      for (const m of t.matchAll(/(?:first|second|third|fourth|birinci|ikinci|ucuncu|перв[а-я]*|втор[а-я]*|трет[а-я]*)/g)) {
        const k = ordinalIn(m[0]);
        if (k !== null && k < results.length && !pool.includes(results[k])) pool.push(results[k]);
      }
      if (pool.length < 2 && qn.ids && qn.ids.length >= 2) pool = qn.ids.map(repo.product);
      if (pool.length < 2) pool = !qn.type ? results.slice(0, 4) : sSearch(qn)[0].slice(0, 4);
      if (pool.length < 2) return ss("which", lang);
      const c = pool.reduce((a, b) => b.price_azn < a.price_azn ? b : a), r = pool.reduce((a, b) => b.rating > a.rating ? b : a);
      return [ss("compare_head", lang), ...pool.map((p, i) => pLine(i + 1, p, lang)), ss("compare_best", lang, { c: pname(c, lang), r: pname(r, lang) })].join("\n");
    }
    if (target || (sel && (pronoun || has(t, ...SH.STOCK)) && !qn.type)) {
      const item = target || sel; st.selected = item.id;
      if (has(t, ...SH.STOCK))
        return ss(item.stock > 0 ? "stock_yes" : "stock_no", lang, { name: pname(item, lang), n: item.stock }) + "\n" + pDetails(item, lang);
      return pDetails(item, lang);
    }
    let sq = (!qn.ids || qn.type) ? Object.fromEntries(Object.entries(qn).filter(([k]) => k !== "ids")) : qn;
    if (!Object.keys(sq).length) {
      if (has(t, ...SH.SEARCH)) return ss("not_found", lang);
      if (results.length) return [ss("again", lang, { cond: cond(st.query, lang) }), ...results.map((p, i) => pLine(i + 1, p, lang))].join("\n");
      return ss("need_query", lang);
    }
    if (turn.category === "followup" && !sq.type && st.query.type) sq = { ...st.query, ...sq };
    const current = { query: st.query, results: st.results, selected: st.selected };
    for (const past of [current, ...[...st.history].reverse()]) {
      if (past.query.type === sq.type && (has(t, ...SH.BACK) || sameQ(past.query, sq)) && (Object.keys(sq).length === 1 || sameQ(past.query, sq))) {
        st.query = past.query; st.results = past.results; st.selected = past.selected;
        const lines = [ss("again", lang, { cond: cond(past.query, lang) }), ...past.results.map(repo.product).map((p, i) => pLine(i + 1, p, lang))];
        if (past.selected) lines.push(ss("selected_note", lang, { name: pname(repo.product(past.selected), lang) }));
        return lines.join("\n");
      }
    }
    const [found, base] = sSearch(sq);
    if (Object.keys(st.query).length) {
      st.history = st.history.filter(h => !sameQ(h.query, st.query)).slice(-5);
      st.history.push({ query: st.query, results: st.results, selected: st.selected });
    }
    st.query = sq; st.results = found.map(p => p.id); st.selected = null;
    if (!found.length) {
      const out = [ss("none", lang, { cond: cond(sq, lang) })];
      if (base.length) { out.push(ss("closest", lang), ...base.slice(0, 3).map((p, i) => pLine(i + 1, p, lang))); st.results = base.slice(0, 3).map(p => p.id); }
      return out.join("\n");
    }
    const lines = [ss("results", lang, { cond: cond(sq, lang) }), ...found.map((p, i) => pLine(i + 1, p, lang))];
    if (found.length > 1) lines.push(ss("pick_hint", lang)); else st.selected = found[0].id;
    return lines.join("\n");
  }

  // ------------------------------------------------------------------ cinema module
  const CI = T.cinema, cs = (k, lang, kw) => fmt(CI.STR, k, lang, kw);
  const genres = m => Array.isArray(m.genre) ? m.genre : [m.genre];
  const cinemaName = id => (cinemasDB.find(c => c.id === id) || {}).name || id;
  const sSeats = (s, lang) => s.seats_available > 0 ? cs("seats", lang, { n: s.seats_available }) : cs("sold_out", lang);
  const showLine = (i, s, lang, withTitle) => `${i}. ${withTitle ? repo.movie(s.movie_id).title + " · " : ""}${prettyDate(s.date, lang)} ${s.time} · ${cinemaName(s.cinema_id)}, ${s.hall} · ${money(s.price_azn)} · ${sSeats(s, lang)}`;
  const movieLine = (i, m) => `${i}. ${m.title} — ${genres(m).join(", ")}, ${m.language}, ${m.age_rating}, ★${f1(m.rating)}`;
  const mDetails = (m, lang) => cs("details", lang, { title: m.title, year_genre: genres(m).join(", "), language: m.language,
    dur: m.duration_min, age: m.age_rating, rating: f1(m.rating), syn: m.synopsis || "" });
  const dateLabel = (d, lang) => d === REF ? cs("tonight", lang) : prettyDate(d, lang);
  function cParse(t) {
    const q = {};
    const g = Object.entries(CI.GENRES).filter(([, p]) => has(t, ...p)).map(([k]) => k);
    if (g.length) q.genre = g[0];
    for (const [ln, p] of Object.entries(CI.LANGS)) if (has(t, ...p)) q.language = ln;
    let m = /(?:rating|rated|reytinq[a-z]*|рейтинг[а-я]*)\s*(?:above|over|>|at least|from|от|выше)?\s*(\d(?:[.,]\d)?)/.exec(t);
    if (m) q.min_rating = parseFloat(m[1].replace(",", "."));
    const dates = findDates(t); if (dates.length) q.date = dates[0];
    const cid = E.findCinema(t); if (cid) q.cinema = cid;
    m = /(\d{1,2})[:.](\d{2})/.exec(t); if (m) q.time = `${pad(+m[1])}:${m[2]}`;
    return q;
  }
  function cinemaHandle(turn, session) {
    const st = session.domains.cinema, { t, lang } = turn, q = cParse(t);
    const listedMovies = st.movies.map(repo.movie), listedShows = st.showtimes.map(repo.show);
    const wantsBook = has(t, ...CI.RESERVE) || st.intent === "book";
    let n = countIn(t);
    if (has(t, "cinemas", "kinoteatrlar\\w*", "кинотеатр(?:ы|ов)", "which cinema", "hansi kinoteatr", "какие кинотеатры") && !E.findMovies(t).length && !q.genre)
      return [cs("cinemas", lang), ...cinemasDB.map(c => `• ${c.name} — ${c.address}`)].join("\n");
    let movie = null;
    const named = E.findMovies(t), idx = ordinalIn(t);
    if (named.length) movie = repo.movie(named[0]);
    else if (idx !== null && st.last_list === "showtimes" && listedShows.length) {
      const show = pick(listedShows, idx);
      if (show) { st.showtime = show.id; st.movie = show.movie_id; movie = repo.movie(show.movie_id); }
    } else if (idx !== null && listedMovies.length) movie = pick(listedMovies, idx);
    let gm = [];
    if (!movie && q.genre && listedMovies.length && has(t, "one\\b", "olan\\w*", "тот", "который", "the ")) {
      gm = listedMovies.filter(m => genres(m).includes(q.genre));
      if (gm.length === 1) movie = gm[0];
    }
    if (movie && (!st.movie || st.movie !== movie.id)) {
      st.movie = movie.id;
      st.showtime = (idx !== null && st.last_list === "showtimes") ? st.showtime : null;
    }
    if (!movie && st.movie && !gm.length && !q.genre && !q.language &&
        (wantsBook || has(t, ...CI.SEATS, ...CI.PRICE, ...CI.SHOWTIMES) || turn.category === "followup")) movie = repo.movie(st.movie);
    if (gm.length > 1) {
      const shows = gm.flatMap(m => repo.showtimes(m.id, q.date)).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
      st.showtimes = shows.map(s => s.id); st.last_list = "showtimes"; st.movie = null;
      const lines = [cs("several_genre", lang, { genre: q.genre, titles: gm.map(m => m.title).join(", ") })];
      if (shows.length) lines.push(...shows.map((s, i) => showLine(i + 1, s, lang, true)));
      else lines.push(cs("nothing_date", lang, { cond: "", date: dateLabel(q.date || REF, lang) }));
      if (wantsBook || n) lines.push(cs("which_show", lang));
      return lines.join("\n");
    }
    if (wantsBook) {
      if (n) session.preferences.tickets = n;
      n = n || session.preferences.tickets || 1;
      let show = st.showtime ? repo.show(st.showtime) : null;
      if (show && movie && show.movie_id !== movie.id) show = null;
      if (!show && idx !== null && st.last_list === "showtimes") show = pick(listedShows, idx);
      if (!show) {
        st.intent = "book";
        if (!movie) {
          const pool = listedMovies.length > 1 ? listedMovies : moviesDB.filter(m => repo.showtimes(m.id).length);
          st.movies = pool.map(m => m.id); st.last_list = "movies";
          return [cs("which_film", lang), ...pool.map((m, i) => movieLine(i + 1, m))].join("\n");
        }
        let cands = repo.showtimes(movie.id, q.date, q.cinema);
        if (q.time) cands = cands.filter(s => s.time === q.time);
        const bookable = cands.filter(s => s.seats_available >= n);
        if (bookable.length === 1 && (q.date || q.time || cands.length === 1)) show = bookable[0];
        else {
          if (!cands.length) cands = repo.showtimes(movie.id);
          st.showtimes = cands.map(s => s.id); st.last_list = "showtimes";
          return [cs("showtimes_for", lang, { title: movie.title, date: "" }), ...cands.map((s, i) => showLine(i + 1, s, lang)), cs("which_show", lang)].join("\n");
        }
      }
      const r = repo.reserveShow(show.id, n);
      if (!r.ok) return cs("not_enough", lang, { n: r.seats_available });
      st.showtime = show.id; st.intent = null; st.bookings.push(r);
      return cs("booked", lang, { n, title: repo.movie(show.movie_id).title, date: prettyDate(show.date, lang), time: show.time,
        cinema: cinemaName(show.cinema_id), hall: show.hall, total: money(r.total_azn), ref: r.reference });
    }
    if (idx !== null && st.last_list === "showtimes" && st.showtime && !named.length) {
      const s = repo.show(st.showtime);
      return cs("seat_answer", lang, { when: `${repo.movie(s.movie_id).title}, ${prettyDate(s.date, lang)} ${s.time}, ${cinemaName(s.cinema_id)}`,
        seats: sSeats(s, lang), price: money(s.price_azn) });
    }
    if (movie) {
      const shows = repo.showtimes(movie.id, q.date, q.cinema);
      const dateTxt = !q.date ? "" : q.date === REF ? " " + cs("tonight", lang) : cs("on", lang, { d: prettyDate(q.date, lang) });
      st.last_list = "showtimes"; st.query = { ...st.query, ...q };
      if (!shows.length) {
        const all = repo.showtimes(movie.id); st.showtimes = all.map(s => s.id);
        const lines = [cs("no_showtimes", lang, { title: movie.title, date: dateTxt })];
        if (all.length) lines.push(cs("other_days", lang, { dates: [...new Set(all.map(s => s.date))].sort().map(d => prettyDate(d, lang)).join(", ") }));
        return lines.join("\n");
      }
      st.showtimes = shows.map(s => s.id);
      const lines = [];
      if (!has(t, ...CI.SEATS, ...CI.PRICE, ...CI.SHOWTIMES) && !q.date && turn.category !== "followup") lines.push(mDetails(movie, lang));
      lines.push(cs("showtimes_for", lang, { title: movie.title, date: dateTxt }), ...shows.map((s, i) => showLine(i + 1, s, lang)));
      return lines.join("\n");
    }
    let c = "";
    if (q.genre) c += ` · ${q.genre}`; if (q.language) c += ` · ${q.language}`; if (q.min_rating) c += ` · ★≥${f1(q.min_rating)}`;
    let movies = moviesDB.filter(m => (!q.genre || genres(m).includes(q.genre)) && (!q.language || m.language === q.language) && (!q.min_rating || m.rating >= q.min_rating));
    if (has(t, ...CI.TOP)) movies = [...movies].sort((a, b) => b.rating - a.rating);
    if (q.date || has(t, "playing", "showing", "on now", "ne gedir", "neler gedir", "ид[её]т", "в прокате")) {
      const day = q.date || REF, ids = new Set(movies.map(m => m.id));
      const shows = repo.showtimes(null, day, q.cinema).filter(s => ids.has(s.movie_id));
      if (!shows.length) { st.movies = []; st.showtimes = []; return cs("nothing_date", lang, { cond: c, date: dateLabel(day, lang) }); }
      const order = [...new Set(shows.map(s => s.movie_id))];
      st.movies = order; st.showtimes = shows.map(s => s.id); st.last_list = "movies"; st.movie = null; st.query = { ...q, date: day };
      const lines = [cs("playing", lang, { date: dateLabel(day, lang) })];
      order.forEach((mid, i) => {
        const m = repo.movie(mid);
        const times = shows.filter(s => s.movie_id === mid).map(s => `${s.time} ${cinemaName(s.cinema_id).replace("CinemaPlus ", "")} (${sSeats(s, lang)})`).join(", ");
        lines.push(`${i + 1}. ${m.title} — ${genres(m).join(", ")}, ${m.language}, ★${f1(m.rating)} · ${times}`);
      });
      lines.push(cs("film_line_hint", lang));
      return lines.join("\n");
    }
    if (!movies.length) return cs("no_films", lang, { cond: c });
    st.movies = movies.map(m => m.id); st.last_list = "movies"; st.movie = null; st.query = q;
    return [cs("films", lang, { cond: c }), ...movies.map((m, i) => movieLine(i + 1, m)), cs("film_line_hint", lang)].join("\n");
  }

  // ------------------------------------------------------------------ orchestrator
  const MODULES = { flights: flightsHandle, shopping: shoppingHandle, cinema: cinemaHandle };
  const TX = T.app.TEXT, HEAD = T.app.HEAD;
  const sessions = new Map();
  function getSession(id) { if (!sessions.has(id)) sessions.set(id, newSession()); return sessions.get(id); }
  function clarify(t, lang, session) {
    if (hits(t, LX.BOOKING).length) { const n = countIn(t); return TX.ambiguous_book[lang].replace("{n}", n ? ` (${n})` : ""); }
    const active = DOMAINS.filter(d => hasState(session, d));
    if (active.length >= 2) {
      const names = TX.dom[lang];
      return TX.ambiguous_ctx[lang].replace("{a}", names[active[active.length - 2]]).replace("{b}", names[active[active.length - 1]]);
    }
    return TX.ambiguous[lang];
  }
  // ------------------------------------------------------------------ bonus: visual search
  // The browser classifies the photo (vision.js) into one of the catalogue's product types with a
  // confidence; this turns that into a shopping result, or a question when the model is unsure.
  const VIS = {
    type: { headphones: { en: "headphones", az: "qulaqlıq", ru: "наушники" }, speaker: { en: "a speaker", az: "dinamik", ru: "колонка" },
      laptops: { en: "a laptop", az: "noutbuk", ru: "ноутбук" }, phones: { en: "a smartphone", az: "smartfon", ru: "смартфон" },
      wearables: { en: "a smartwatch", az: "ağıllı saat", ru: "умные часы" }, bags: { en: "a backpack", az: "çanta", ru: "рюкзак" },
      shoes: { en: "running shoes", az: "qaçış ayaqqabısı", ru: "кроссовки" }, coffee: { en: "a coffee machine", az: "qəhvə maşını", ru: "кофемашина" },
      games: { en: "a board game", az: "stolüstü oyun", ru: "настольная игра" } },
    found: { en: "📷 This looks like {what} ({pct}% confidence).", az: "📷 Bu, deyəsən, {what} şəklidir ({pct}% əminliklə).", ru: "📷 Похоже, это {what} (уверенность {pct}%)." },
    color: { en: " Main colour: {c}.", az: " Əsas rəng: {c}.", ru: " Основной цвет: {c}." },
    unsure: { en: "📷 I’m not sure. It might be {what} ({pct}% confidence). Is that right? Reply “yes”, or tell me what it is.",
      az: "📷 Əmin deyiləm: bəlkə də {what} ({pct}% əminlik). Düzdür? “Bəli” yazın və ya nə olduğunu deyin.",
      ru: "📷 Я не уверен. Возможно, это {what} (уверенность {pct}%). Верно? Ответьте «да» или напишите, что это." },
    none: { en: "📷 I couldn’t match this photo to anything in our catalogue (my best guess: “{guess}”, {pct}%). What product are you looking for?",
      az: "📷 Bu şəkli kataloqdakı məhsulla uyğunlaşdıra bilmədim (ehtimal: “{guess}”, {pct}%). Hansı məhsulu axtarırsınız?",
      ru: "📷 Не удалось сопоставить фото с товарами каталога (догадка: «{guess}», {pct}%). Какой товар вы ищете?" },
  };
  const fill = (s, kw) => s.replace(/\{(\w+)\}/g, (_, k) => kw[k]);
  function showType(session, type, color, lang) {
    const st = session.domains.shopping;
    let [found] = sSearch({ type });
    if (color) found = [...found.filter(p => p.color === color), ...found.filter(p => p.color !== color)];
    if (Object.keys(st.query).length) {
      st.history = st.history.filter(h => !sameQ(h.query, st.query)).slice(-5);
      st.history.push({ query: st.query, results: st.results, selected: st.selected });
    }
    st.query = { type }; st.results = found.map(p => p.id); st.selected = found.length === 1 ? found[0].id : null;
    session.last_domain = "shopping";
    const lines = found.map((p, i) => pLine(i + 1, p, lang));
    if (found.length > 1) lines.push(ss("pick_hint", lang));
    return lines.join("\n");
  }
  function imageSearch(sessionId, result) {
    // result: {type, confidence (0..1), guess (top ImageNet label), guessConfidence, color}
    const session = getSession(sessionId), lang = session.lang || "en";
    const pct = Math.round(result.confidence * 100);
    let reply, category;
    if (result.type && result.confidence >= 0.4) {
      reply = fill(VIS.found[lang], { what: VIS.type[result.type][lang], pct }) +
        (result.color && sSearch({ type: result.type })[0].some(p => p.color === result.color) ? fill(VIS.color[lang], { c: result.color }) : "") +
        "\n" + showType(session, result.type, result.color, lang);
      category = "shopping";
    } else if (result.type && result.confidence >= 0.12) {
      session.visual_pending = { type: result.type, color: result.color };
      reply = fill(VIS.unsure[lang], { what: VIS.type[result.type][lang], pct });
      category = "ambiguous";
    } else {
      session.pending = { text: "" };
      reply = fill(VIS.none[lang], { guess: result.guess || "?", pct: Math.round((result.guessConfidence || 0) * 100) });
      category = "ambiguous";
    }
    const turn = { user: "[photo]", reply, category, domains: category === "shopping" ? ["shopping"] : [], lang,
      cues: ["image:" + (result.guess || "?"), "type:" + (result.confidence >= 0.12 ? result.type : "none"), "confidence:" + pct + "%"] };
    session.history.push(turn);
    return { ...turn, state: { lang: session.lang, last_domain: session.last_domain, preferences: session.preferences, domains: session.domains } };
  }

  function handle(sessionId, message) {
    const session = getSession(sessionId);
    message = String(message || "").trim().slice(0, 1000);
    const lang = detectLanguage(message) || session.lang;
    session.lang = lang;
    let t = norm(message);
    if (session.visual_pending) {                     // answer to "is it headphones?" after a photo
      const vp = session.visual_pending; session.visual_pending = null;
      if (has(t, "yes", "yeah", "yep", "correct", "right", "beli", "he\\b", "hə", "duzdur", "да\\b", "верно", "ага")) {
        const reply = showType(session, vp.type, vp.color, lang);
        const turn = { user: message, reply, category: "followup", domains: ["shopping"], lang, cues: ["visual-confirmed"] };
        session.history.push(turn);
        return { ...turn, state: { lang: session.lang, last_domain: session.last_domain, preferences: session.preferences, domains: session.domains } };
      }
    }
    if (session.pending) {
      const first = route(t, session);
      if (["flights", "shopping", "cinema", "followup"].includes(first.category) && t.split(" ").length <= 6) t = norm(session.pending.text) + " " + t;
      session.pending = null;
    }
    const d = route(t, session), cat = d.category;
    let reply;
    try {
      if (["flights", "shopping", "cinema", "followup"].includes(cat)) {
        const dom = d.domains[0];
        reply = MODULES[dom]({ raw: message, t, lang, category: cat }, session);
        session.last_domain = dom;
      } else if (cat === "mixed") {
        reply = d.domains.map(dom => {
          const r = HEAD[dom] + " " + MODULES[dom]({ raw: message, t: (d.clauses || {})[dom] || t, lang, category: dom }, session);
          session.last_domain = dom; return r;
        }).join("\n\n");
      } else if (cat === "ambiguous") { session.pending = { text: message }; reply = clarify(t, lang, session); }
      else if (cat === "greeting") reply = TX.greeting[lang];
      else reply = TX.oos[lang];
    } catch (e) {
      if (typeof console !== "undefined") console.error(e);
      reply = TX.error[lang];
    }
    if (reply) reply = reply[0].toUpperCase() + reply.slice(1);
    const turn = { user: message, reply, category: cat, domains: d.domains, lang, cues: d.cues.slice(0, 8) };
    session.history.push(turn);
    return { ...turn, state: { lang: session.lang, last_domain: session.last_domain, preferences: session.preferences, domains: session.domains } };
  }
  return { handle, imageSearch, route: (t, sid) => route(norm(t), getSession(sid)), reset: id => sessions.delete(id), getSession, norm };
}

if (typeof module !== "undefined" && module.exports) module.exports = { createSuperChat };
else root.createSuperChat = createSuperChat;
})(typeof window !== "undefined" ? window : globalThis);
