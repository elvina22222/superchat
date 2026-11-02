# SuperChat — Phase 2 API contract

SuperChat reads all data through three repository interfaces (`superchat/repositories.py`).
For Phase 2, `superchat/api_repositories.py` implements them over HTTP. The clients expect the REST
contract below, which uses **the same field names as the official mock dataset**. If the organisers' real
API differs, only the small mapping inside these classes changes. The router, modules and UI stay as they are.
`tools/fake_api.py` implements this contract on top of the mock data, so it can be tested today.

## Common rules

| Topic | Rule |
|---|---|
| Auth | `Authorization: Bearer <key>` (Aviasales: `X-Access-Token: <token>`) |
| Lists | `GET` with `?page=N&limit=M` → `{"items": [...], "page": N, "next_page": N+1 or null, "total": T}` |
| Errors | 401 wrong key · 404 not found · 409 not enough seats (body `{"ok": false, "seats_available": n}`) · 429/5xx temporary |
| Retries | 429, 500, 502, 503, 504 and network errors: up to 3 retries, exponential back-off, honours `Retry-After` |
| Idempotency | every `POST` carries a unique `Idempotency-Key`; a retried reservation is booked only once |
| Caching | GET responses cached in memory: products 60 s, flights 30 s, showtimes 15 s, Aviasales 300 s; cleared after a reservation |
| Rate limit | client-side minimum interval between calls (Aviasales 100 ms) |
| Logging | every call logged with status and latency; tokens are redacted from logged URLs |

## Endpoints

| Domain | Method & path | Returns |
|---|---|---|
| Flights | `GET /airports` | list of `{code, city}` |
| | `GET /flights?origin=GYD&destination=IST&date=2026-11-06` | list of flight records |
| | `GET /flights/{id}` | one flight record |
| | `POST /flights/{id}/reservations` `{"passengers": 2}` | `{"ok": true, "reference", "total_azn"}` or 409 |
| Shopping | `GET /products` · `GET /products/{id}` | product records |
| Cinema | `GET /movies` · `GET /cinemas` | lists |
| | `GET /showtimes?movie_id=&date=&cinema_id=` · `GET /showtimes/{id}` | showtime records |
| | `POST /showtimes/{id}/reservations` `{"seats": 2}` | `{"ok": true, "reference", "total_azn"}` or 409 |

## Real Aviasales API (public)

`AviasalesFlightRepository` calls `GET https://api.travelpayouts.com/aviasales/v3/prices_for_dates`
(`origin`, `destination`, `departure_at`, `one_way=true`, `currency=azn`, `sorting=price`, `limit=30`).
Mapping: `airline` IATA code → airline name, `airline+flight_number` → flight number, `departure_at` → local
departure time, `transfers` → stops, `duration_to` → duration, `price` → price, `link` → Aviasales deep link.

This public API returns **cached cheapest prices from the last 48 hours**. It has **no arrival time, seat
count, baggage allowance or booking endpoint**. SuperChat therefore shows those fields as unknown (never
guessed) and replaces “reserve” with a hand-over link to Aviasales.
