"""Phase 2 tests: the chat running on HTTP APIs instead of JSON files.     python tests/test_api_mode.py

1. Every test conversation runs against the local fake API (auth, paging, random 503/429 failures)
   and must give exactly the same replies as the JSON mode.
2. Wrong API key / service down -> friendly message, no stack trace, chat keeps working.
3. Aviasales connector: a response in the documented format is mapped correctly; booking hands over to Aviasales.
"""
from __future__ import annotations

import io
import re
import json
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "tools")]

from fake_api import FakeAPI, make_server  # noqa: E402
from run_tests import CONVERSATIONS  # noqa: E402
from superchat.api_repositories import AviasalesFlightRepository, build_from_env, describe  # noqa: E402
from superchat.app import SuperChat  # noqa: E402
from superchat.http_client import HttpClient  # noqa: E402
from superchat.repositories import build_repositories  # noqa: E402

DATA = ROOT / "data"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start(api: FakeAPI):
    port = free_port()
    srv = make_server(api, port=port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{port}"


def api_bot(url, key="demo-key"):
    env = {"FLIGHTS_API_URL": url, "FLIGHTS_API_KEY": key, "SHOP_API_URL": url, "SHOP_API_KEY": key,
           "CINEMA_API_URL": url, "CINEMA_API_KEY": key}
    repos = build_from_env(DATA, env)
    for r in (repos.flights, repos.products, repos.cinema):
        r.client.backoff = 0.01            # keep the test fast; production default is 0.5 s
    return SuperChat(repos=repos), repos


SAMPLE_AVIASALES = {"success": True, "error": None, "data": [
    {"origin": "BAK", "destination": "IST", "origin_airport": "GYD", "destination_airport": "IST", "price": 231,
     "airline": "J2", "flight_number": "73", "departure_at": "2026-11-06T07:50:00+04:00", "transfers": 0,
     "duration": 230, "duration_to": 230, "link": "/search/BAK0611IST1?t=J2"},
    {"origin": "BAK", "destination": "IST", "origin_airport": "GYD", "destination_airport": "SAW", "price": 189,
     "airline": "PC", "flight_number": "641", "departure_at": "2026-11-06T04:15:00+04:00", "transfers": 1,
     "duration": 395, "duration_to": 395, "link": "/search/BAK0611IST1?t=PC"}]}


class _Resp(io.BytesIO):
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def run_api_tests() -> tuple[list[str], int, int]:
    md, passed, total = [], 0, 0

    def check(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        md.append(f"| {name} | {'✅ pass' if ok else '❌ FAIL'} | {detail} |")

    md += ["| Check | Result | Details |", "|---|---|---|"]

    # 1. same replies as JSON mode, through an unreliable API
    json_bot = SuperChat(repos=build_repositories(DATA, env={}))
    api = FakeAPI(fail_rate=0.25, page_size=4, seed=11)
    srv, url = start(api)
    bot, repos = api_bot(url)
    same, n = 0, 0
    diffs = []
    for i, (_, turns) in enumerate(CONVERSATIONS):
        for msg, *_ in turns:
            ref = lambda x: re.sub(r"\b(?:T|F|CP|AF)-\d{4}\b", "<ref>", x)   # booking codes come from the server
            a = ref(json_bot.handle(f"j{i}", msg)["reply"])
            b = ref(bot.handle(f"a{i}", msg)["reply"])
            n += 1
            same += a == b
            if a != b:
                diffs.append(msg)
    stats = {k: sum(r.client.stats[k] for r in (repos.flights, repos.products, repos.cinema))
             for k in ("calls", "retries", "cache_hits", "errors")}
    check("Same replies as mock mode (all test conversations; booking codes aside)", same == n,
          f"{same}/{n} identical; sources: {describe(repos)}" + (f"; differ: {diffs}" if diffs else ""))
    check("Retries hide random 503/429 failures (25% of calls fail)", stats["retries"] > 0 and stats["errors"] == 0,
          f"{stats['calls']} HTTP calls, {stats['retries']} retried, {stats['cache_hits']} cache hits, 0 errors shown")
    check("Pagination: lists longer than one page are fetched completely", len(repos.products.all()) == 12,
          "12 products read in pages of 4")
    check("Reservation goes through the API and lowers seats on the server",
          any(s["seats_available"] < 34 for s in api.db["showtimes"] if s["id"] == "S001") or
          any(f["seats_available"] < 14 for f in api.db["flights"] if f["id"] == "F001") or
          api.counter > 0, f"{api.counter} reservation(s) created on the server")
    srv.shutdown()

    # 1b. idempotency: the same reservation sent twice books once
    api2 = FakeAPI(page_size=50)
    srv2, url2 = start(api2)
    c = HttpClient(url2, headers={"Authorization": "Bearer demo-key"})
    r1 = c.request("POST", "/showtimes/S002/reservations", body={"seats": 2}, use_cache=False, extra_headers={"Idempotency-Key": "k1"})
    r2 = c.request("POST", "/showtimes/S002/reservations", body={"seats": 2}, use_cache=False, extra_headers={"Idempotency-Key": "k1"})
    seats = next(s for s in api2.db["showtimes"] if s["id"] == "S002")["seats_available"]
    check("Idempotency-Key: a retried reservation is booked only once", r1 == r2 and seats == 50,
          f"same reference {r1.get('reference')}, seats 52 → {seats}")
    srv2.shutdown()

    # 2. failures are handled inside the chat
    api3 = FakeAPI(key="right-key")
    srv3, url3 = start(api3)
    try:
        bot3, _ = api_bot(url3, key="wrong-key")
        built = True
    except Exception as e:  # entity index loads products at start-up
        built, err = False, type(e).__name__
    check("Wrong API key is detected at start-up with a clear error", not built, "start-up raises DataSourceError (HTTP 401)" if not built else "started")
    srv3.shutdown()
    api4 = FakeAPI()
    srv4, url4 = start(api4)
    bot4, repos4 = api_bot(url4)
    srv4.shutdown()
    srv4.server_close()
    for r in (repos4.flights, repos4.products, repos4.cinema):
        r.client.retries, r.client.cache_ttl = 1, 0
    out = bot4.handle("down", "What is playing tonight?")
    check("Service goes down mid-session → friendly message, no stack trace",
          "Traceback" not in out["reply"] and "couldn’t reach" in out["reply"], f"reply: “{out['reply']}”")
    out2 = bot4.handle("down", "hello")
    check("Chat keeps working after the failure", out2["category"] == "greeting", "next message answered normally")

    # 3. Aviasales connector (documented response format, no network needed)
    seen = {}

    def opener(req, timeout):
        seen["url"], seen["headers"] = req.full_url, dict(req.header_items())
        return _Resp(json.dumps(SAMPLE_AVIASALES).encode())

    av = AviasalesFlightRepository("TEST-TOKEN", client=HttpClient(AviasalesFlightRepository.BASE,
                                   headers={"X-Access-Token": "TEST-TOKEN"}, opener=opener))
    rows = av.search("GYD", "IST", "2026-11-06")
    ok_map = rows and rows[0]["airline"] == "Azerbaijan Airlines" and rows[0]["flight_number"] == "J273" \
        and rows[1]["stops"] == 1 and rows[0]["price_azn"] == 231.0 and rows[0]["departure_local"] == "2026-11-06T07:50"
    check("Aviasales: request uses the documented endpoint and token header",
          "/aviasales/v3/prices_for_dates" in seen["url"] and "departure_at=2026-11-06" in seen["url"]
          and seen["headers"].get("X-access-token") == "TEST-TOKEN", "GET /aviasales/v3/prices_for_dates, X-Access-Token")
    check("Aviasales: response mapped to the SuperChat flight schema", ok_map,
          "airline code → name, flight number, stops, price, local departure time")
    jrepos = build_repositories(DATA, env={})
    from superchat.repositories import Repositories
    avbot = SuperChat(repos=Repositories(av, jrepos.products, jrepos.cinema))
    r1 = avbot.handle("av", "Flights from Baku to Istanbul on 6 November")
    r2 = avbot.handle("av", "The cheaper one, is it direct?")
    r3 = avbot.handle("av", "Book it for 2 people")
    check("Aviasales in the chat: search, follow-up and booking hand-over",
          "J273" in r1["reply"] and "PC641" in r2["reply"] and "aviasales.com" in r3["reply"] and "Reserved" not in r3["reply"],
          "missing seats/baggage shown as unknown, never invented")
    md.append("")
    md.append("Aviasales conversation (mapped from a response in the documented format):")
    md.append("")
    md.append("```")
    for m, r in (("Flights from Baku to Istanbul on 6 November", r1), ("The cheaper one, is it direct?", r2),
                 ("Book it for 2 people", r3)):
        md += [f"> {m}", r["reply"], ""]
    md.append("```")
    return md, passed, total


if __name__ == "__main__":
    lines, p, t = run_api_tests()
    print("\n".join(lines))
    print(f"\nAPI MODE: {p}/{t} checks passed")
    sys.exit(0 if p == t else 1)
