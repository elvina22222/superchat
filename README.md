# SuperChat

One chat for **flights** (Aviasales), **shopping** (Shopping Assistant) and **cinema** (CinemaPlus).
The user never picks a mode: every message is routed automatically, topics can switch at any time,
and each domain keeps its own state, so you can come back to an earlier topic.
It works in **English, Azerbaijani and Russian**, including switching language mid-chat.

## Run it — one command

Requires **Python 3.10+**. No packages to install (standard library only). By default it runs offline on the mock data; real APIs are optional (see below).

```bash
python run.py
```

Open **http://127.0.0.1:8000** in your browser.

Other options:

```bash
python run.py --cli          # chat in the terminal
python run.py --port 9000    # use another port
python tests/run_tests.py    # run all tests and regenerate TEST_LOG.md
```

## Live demo (browser version)

`web/superchat.html` is the same assistant compiled into one self-contained page, so it runs without a server.
`web/engine.js` is a JavaScript port of the Python engine. It reads the same cue lists, reply texts and data,
exported by `web/export_tables.py`. `node web/parity_test.js` checks that the JS port gives **the same output as Python**
on all 208 test messages (208/208). Rebuild the page with `python web/build.py`.

## Try these

| Message | What it shows |
|---|---|
| Find me a flight from Baku to Istanbul on Friday | Flight search, date resolved against Mon 2 Nov 2026 |
| The cheaper one, is it direct? | Follow-up within flights |
| What is playing tonight? | Switch to cinema |
| Do you have wireless headphones under 100 AZN? | Switch to shopping, price filter, stock status |
| Okay, and the sci-fi one, any seats on Saturday? | Return to cinema; two sci-fi films match, so both are shown |
| I need a flight to Istanbul on 6 November and a backpack for the trip | Mixed intent: two modules, one reply |
| Back to the headphones | Earlier shopping list and selection restored |
| Book two seats | Missing context → clarifying question |
| Show me something good / What is the weather in Ganja? | Ambiguous / out of scope |
| Bu axşam hansı filmlər gedir? · Найди рейс в Дубай | Azerbaijani / Russian |

The right-hand panel shows each routing decision (category, cues found) and the live session state.

## Project layout

```
run.py                     single entry point (web or --cli)
data/                      official mock dataset (5 JSON files)
static/index.html          chat UI
superchat/
  repositories.py          data interfaces + JSON implementations   ← swap here for real APIs
  entities.py              cities, airlines, brands, titles, cinemas, all built from the data
  lexicon.py               EN/AZ/RU cue lists used by the router
  nlp.py                   normalisation, language detection, dates, numbers, ordinals, prices
  router.py                hybrid rule router → 7 categories
  state.py                 session: shared state + separate state per domain
  app.py                   orchestrator: language → route → module(s) → reply; error handling
  server.py                standard-library HTTP server (/api/chat, /api/reset)
  modules/flights.py       search, filter/sort, details, compare, round trip, mock reservation
  modules/shopping.py      search, details, compare, stock, cart add/remove/total
  modules/cinema.py        films by genre/language/rating/date, showtimes, seats, price, mock booking
tests/routing_cases.py     labelled routing tests: dev (70), held-out (48), stress (30)
tests/run_tests.py         runs everything and writes TEST_LOG.md
tests/test_api_mode.py     Phase 2 tests on HTTP APIs
superchat/http_client.py   HTTP client: retries, rate limit, cache, paging, logging
superchat/api_repositories.py  Aviasales + REST repositories, source selection from env
tools/fake_api.py          local fake of the organisers' APIs (auth, paging, failures)
docs/API_CONTRACT.md       expected endpoints and behaviour
web/                       browser version for the live link (engine.js, build.py, parity test)
REPORT.pdf                 technical report (4 pages)
TEST_LOG.md                test results, accuracy and error analysis
```

## Real APIs (Phase 2) — implemented

Modules only call `FlightRepository`, `ProductRepository` and `ShowtimeRepository`. The HTTP versions are in
`superchat/api_repositories.py`, built on `superchat/http_client.py`, which handles auth, timeouts, retries with
back-off, `Retry-After`, rate limiting, caching, pagination, idempotent reservations and logging. Each source is
switched on with environment variables. Anything not set stays on the mock JSON files.

| Variable | Effect |
|---|---|
| `AVIASALES_TOKEN` | real flight prices from the public Aviasales Data API (Travelpayouts) |
| `FLIGHTS_API_URL`, `FLIGHTS_API_KEY` | organisers' flights API (takes priority over Aviasales) |
| `SHOP_API_URL`, `SHOP_API_KEY` | e-commerce API |
| `CINEMA_API_URL`, `CINEMA_API_KEY` | CinemaPlus API |

```bash
python run.py --api-demo                      # starts a local fake API (20% random failures) and runs the chat on it
AVIASALES_TOKEN=xxxx python run.py            # real Aviasales prices for flights (needs a Travelpayouts token)
python tests/test_api_mode.py                 # 11 checks: same replies as mock mode, retries, paging, idempotency, failures, Aviasales
```

The expected endpoints are in `docs/API_CONTRACT.md`, and `tools/fake_api.py` implements them on the mock data.
When the organisers send the real API documentation and keys, only the field mapping inside these classes may need to change.
Errors are raised as `DataSourceError`; the chat answers with a polite message and never shows a stack trace.

## Notes

* Reservations are mock only. They lower seats in memory and return a reference such as `F-1001`. No payment, no personal data.
* The reference date is fixed to **Monday 2 November 2026**, as the brief requires (`superchat/nlp.py`).
* Libraries: Python standard library only. The UI is plain HTML/JS.
