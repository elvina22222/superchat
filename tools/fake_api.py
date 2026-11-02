"""Local stand-in for the organisers' APIs (flights, e-commerce, CinemaPlus), built from the official mock data.

It follows docs/API_CONTRACT.md and behaves like a real service, so Phase 2 code can be tested today:
Bearer-token auth (401), pagination (small pages), 404s, 409 when seats run out, idempotent
reservations (Idempotency-Key), latency, and random 503/429 failures to exercise retries.

    python tools/fake_api.py --port 8100 --key demo-key --fail-rate 0.2
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


class FakeAPI:
    def __init__(self, key="demo-key", fail_rate=0.0, latency=0.0, page_size=5, seed=7):
        self.key, self.fail_rate, self.latency, self.page_size = key, fail_rate, latency, page_size
        self.rng = random.Random(seed)
        self.db = {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8"))
                   for n in ("flights", "products", "movies", "cinemas", "showtimes")}
        self.idem: dict[str, tuple[int, dict]] = {}
        self.lock = threading.Lock()
        self.counter = 0
        self.log: list[str] = []

    # -------------------------------------------------------------- helpers
    def page(self, rows, q):
        page = int(q.get("page", 1))
        size = int(q.get("limit", self.page_size))
        chunk = rows[(page - 1) * size: page * size]
        return 200, {"items": chunk, "page": page, "next_page": page + 1 if page * size < len(rows) else None,
                     "total": len(rows)}

    def find(self, table, id_):
        return next((r for r in self.db[table] if r["id"] == id_), None)

    def reserve(self, table, id_, n, prefix):
        with self.lock:
            row = self.find(table, id_)
            if row is None:
                return 404, {"error": "not found"}
            if row["seats_available"] < n:
                return 409, {"ok": False, "seats_available": row["seats_available"]}
            row["seats_available"] -= n
            self.counter += 1
            return 201, {"ok": True, "reference": f"{prefix}-{9000 + self.counter}", f"{table[:-1]}_id": id_,
                         "total_azn": round(row["price_azn"] * n, 2)}

    # -------------------------------------------------------------- routing
    def handle(self, method, path, query, body, headers):
        self.log.append(f"{method} {path}")
        if self.key and headers.get("Authorization") != f"Bearer {self.key}":
            return 401, {"error": "invalid or missing API key"}
        if self.fail_rate and self.rng.random() < self.fail_rate:
            return self.rng.choice([(503, {"error": "temporarily unavailable"}), (429, {"error": "rate limited"})])
        parts = [p for p in path.split("/") if p]
        q = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        if method == "GET":
            if parts == ["airports"]:
                seen = {}
                for f in self.db["flights"]:
                    for side in ("origin", "destination"):
                        seen[f[side]["code"]] = f[side]["city"]
                return self.page([{"code": c, "city": n} for c, n in seen.items()], q)
            if parts == ["flights"]:
                rows = [f for f in self.db["flights"]
                        if (not q.get("origin") or f["origin"]["code"] == q["origin"])
                        and (not q.get("destination") or f["destination"]["code"] == q["destination"])
                        and (not q.get("date") or f["departure_local"].startswith(q["date"]))]
                return self.page(rows, q)
            if parts in (["products"], ["movies"], ["cinemas"]):
                return self.page(self.db[parts[0]], q)
            if parts == ["showtimes"]:
                rows = [s for s in self.db["showtimes"]
                        if all(not q.get(k) or s[k] == q[k] for k in ("movie_id", "date", "cinema_id"))]
                return self.page(rows, q)
            if len(parts) == 2 and parts[0] in ("flights", "products", "showtimes", "movies", "cinemas"):
                row = self.find(parts[0], parts[1])
                return (200, row) if row else (404, {"error": "not found"})
        if method == "POST" and len(parts) == 3 and parts[2] == "reservations":
            key = headers.get("Idempotency-Key")
            if key and key in self.idem:
                return self.idem[key]
            if parts[0] == "flights":
                res = self.reserve("flights", parts[1], int(body.get("passengers", 1)), "AF")
            elif parts[0] == "showtimes":
                res = self.reserve("showtimes", parts[1], int(body.get("seats", 1)), "CP")
            else:
                res = (404, {"error": "not found"})
            if key:
                self.idem[key] = res
            return res
        return 404, {"error": "not found"}


def make_server(api: FakeAPI, host="127.0.0.1", port=8100) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def _go(self, method):
            if api.latency:
                time.sleep(api.latency)
            u = urllib.parse.urlsplit(self.path)
            n = int(self.headers.get("Content-Length", 0) or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except ValueError:
                body = {}
            code, payload = api.handle(method, u.path, u.query, body, self.headers)
            out = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            if code == 429:
                self.send_header("Retry-After", "0")
            self.end_headers()
            self.wfile.write(out)

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

        def log_message(self, *a):
            pass

    return ThreadingHTTPServer((host, port), H)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--key", default="demo-key")
    ap.add_argument("--fail-rate", type=float, default=0.0)
    ap.add_argument("--latency", type=float, default=0.0)
    a = ap.parse_args()
    srv = make_server(FakeAPI(a.key, a.fail_rate, a.latency), port=a.port)
    print(f"Fake API on http://127.0.0.1:{a.port} (key: {a.key}, fail rate {a.fail_rate})")
    srv.serve_forever()
