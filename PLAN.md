# PLAN.md — Skyway Retro Flight Booking

A Flask + SQLite flight booking app with an interactive seat map, styled as a
1960s–70s jet-age airline. Single deployable service, no build step.

**Two decisions still open** (marked ❓ below): single-seat vs. multi-seat
booking, and how the GitHub repo gets created (`gh` is not installed).

---

## 1. File / folder tree

```
managing_wth_ai/
├── PLAN.md                  # this file
├── README.md                # setup, run, deploy, feature tour
├── requirements.txt         # flask, gunicorn
├── .python-version          # 3.13 — pins Render's runtime
├── .gitignore               # __pycache__/, *.db, .venv/
├── render.yaml              # Render blueprint (build + start command)
│
├── run.py                   # local entrypoint: init db, seed, serve. `py run.py`
├── app.py                   # Flask app factory + all routes
├── db.py                    # sqlite3 connection helper, WAL, row factory, init
├── schema.sql               # DDL — tables, indexes, constraints
├── seed.py                  # idempotent seed: aircraft, 14 flights, seats
├── bookings.py              # booking creation, reference codes, cancellation
├── pricing.py               # cabin-class multipliers, fare formatting
│
├── templates/
│   ├── base.html            # shell: header, nav, footer, flash messages
│   ├── index.html           # landing + split-flap hero + search form
│   ├── flights.html         # departure board (results list)
│   ├── flight.html          # flight detail + INTERACTIVE SEAT MAP
│   ├── passenger.html       # passenger details form
│   ├── confirmation.html    # boarding pass
│   ├── lookup.html          # find booking by reference
│   └── error.html           # 404 / 500
│
├── static/
│   ├── css/retro.css        # palette, split-flap, boarding pass, seat map
│   ├── js/seatmap.js        # seat map: fetch availability, select, price
│   └── js/splitflap.js      # departure-board flip animation
│
└── tests/
    └── test_smoke.py        # stdlib unittest — no extra dependency
```

**Tradeoff:** all routes live in one `app.py` rather than blueprints — the app
has ~10 routes, and one file is easier for a grader to read end to end.

---

## 2. SQLite schema

Five tables. Money is stored as **integer cents** (no float rounding drift).
Timestamps are **ISO-8601 UTC strings** (`TEXT`), SQLite's normal idiom.

### `aircraft`
Defines a cabin layout so seats can be generated instead of hand-seeded.

| column | type | notes |
|---|---|---|
| `id` | INTEGER | PK |
| `model` | TEXT | e.g. "Boeing 707", "Douglas DC-8" |
| `seat_letters` | TEXT | e.g. `"ABCDEF"` — column letters, left to right |
| `total_rows` | INTEGER | e.g. 24 |
| `first_class_last_row` | INTEGER | rows 1..N are First |
| `business_last_row` | INTEGER | rows (first+1)..N are Business; rest Economy |

### `flights`

| column | type | notes |
|---|---|---|
| `id` | INTEGER | PK |
| `flight_number` | TEXT | UNIQUE, e.g. `"SK 401"` |
| `aircraft_id` | INTEGER | FK → `aircraft.id` |
| `origin_code` / `origin_city` | TEXT | `"JFK"` / `"New York"` |
| `dest_code` / `dest_city` | TEXT | `"LAX"` / `"Los Angeles"` |
| `departs_at` / `arrives_at` | TEXT | ISO-8601 UTC |
| `duration_minutes` | INTEGER | precomputed for display |
| `base_fare_cents` | INTEGER | Economy fare; other classes are multiples |
| `status` | TEXT | `SCHEDULED` / `DELAYED` — flavor for the board |

Indexes: `(origin_code, dest_code)`, `(departs_at)`.

### `seats`
One row per physical seat per flight. Generated at seed time from the aircraft
layout — **14 flights × ~100 seats ≈ 1,400 rows**, trivial for SQLite.

| column | type | notes |
|---|---|---|
| `id` | INTEGER | PK |
| `flight_id` | INTEGER | FK → `flights.id` ON DELETE CASCADE |
| `row_number` | INTEGER | 1..total_rows |
| `seat_letter` | TEXT | `"A"`.. |
| `cabin_class` | TEXT | `FIRST` / `BUSINESS` / `ECONOMY` |
| `price_cents` | INTEGER | frozen at seed time = base fare × class multiplier |

Constraint: `UNIQUE (flight_id, row_number, seat_letter)`.

**Tradeoff:** `price_cents` is denormalized onto the seat rather than computed
per request — the price a passenger is shown is the exact integer that gets
charged and stored, so displayed and billed fares can never disagree.

### `passengers`

| column | type | notes |
|---|---|---|
| `id` | INTEGER | PK |
| `full_name` | TEXT | NOT NULL |
| `email` | TEXT | NOT NULL |
| `phone` | TEXT | nullable |
| `created_at` | TEXT | ISO-8601 UTC |

A new passenger row is created per booking (no dedupe by email). Real airlines
do the same — the name on *this* ticket is what matters.

### `bookings`

| column | type | notes |
|---|---|---|
| `id` | INTEGER | PK |
| `reference` | TEXT | UNIQUE, 6 chars, e.g. `"PA4K7Q"` |
| `flight_id` | INTEGER | FK → `flights.id` |
| `seat_id` | INTEGER | FK → `seats.id` |
| `passenger_id` | INTEGER | FK → `passengers.id` |
| `price_paid_cents` | INTEGER | copied from `seats.price_cents` at purchase |
| `status` | TEXT | `CONFIRMED` / `CANCELLED` |
| `created_at` | TEXT | ISO-8601 UTC |

### Relationships

```
aircraft 1──* flights 1──* seats 1──0..1 bookings *──1 passengers
                    └──────────* bookings
```

### How availability is tracked

**Availability is derived, never stored.** There is no `is_booked` flag on
`seats`. A seat is available iff no `CONFIRMED` booking points at it:

```sql
SELECT s.*, b.id AS booking_id
FROM seats s
LEFT JOIN bookings b
  ON b.seat_id = s.id AND b.status = 'CONFIRMED'
WHERE s.flight_id = ?;
```

**Tradeoff:** one source of truth. A boolean flag would be a second place the
answer lives, and the two can drift; a join can't.

### How double-booking is prevented

A **partial unique index** — the database itself refuses the second sale:

```sql
CREATE UNIQUE INDEX one_active_booking_per_seat
  ON bookings (seat_id) WHERE status = 'CONFIRMED';
```

Two users confirming seat 14C at the same instant: the first `INSERT` wins, the
second raises `sqlite3.IntegrityError`, which `bookings.py` catches and turns
into "Seat 14C was just taken — please choose another." The user lands back on
the seat map with fresh availability. The partial predicate means a *cancelled*
booking releases the seat for resale, while history is preserved.

Supporting measures:
- Writes run inside `BEGIN IMMEDIATE` so the write lock is taken up front.
- `PRAGMA journal_mode=WAL` and `busy_timeout=5000` so readers never block.
- `PRAGMA foreign_keys=ON` per connection (SQLite defaults it off).

**Tradeoff:** correctness over an optimistic UI. No seat "holds"/timers — a
hold table would need expiry sweeping, which is real complexity for a demo.

---

## 3. Route map

| Method | URL | Renders / does |
|---|---|---|
| GET | `/` | Landing page: split-flap hero, search form (origin, destination, date) |
| GET | `/flights` | Departure board. Query params `origin`, `dest`, `date` (all optional). Shows each flight with seats-remaining and from-price |
| GET | `/flights/<int:flight_id>` | Flight detail + **interactive seat map** |
| GET | `/api/flights/<int:flight_id>/seats` | **JSON**: seat grid, cabin classes, per-seat price, taken/free. Fetched by the seat map on load and re-fetched on refresh |
| GET | `/flights/<int:flight_id>/passenger?seat_id=` | Passenger details form. 302s back to the seat map if the seat is already gone |
| POST | `/bookings` | Creates passenger + booking in one transaction. On success → `/bookings/<ref>`. On `IntegrityError` → back to seat map with a flash |
| GET | `/bookings/<reference>` | Boarding-pass confirmation page |
| GET | `/lookup` | Form: enter booking reference |
| POST | `/lookup` | Looks up reference → redirects to the boarding pass, or flashes "not found" |
| POST | `/bookings/<reference>/cancel` | Sets status `CANCELLED`, releasing the seat. Proves the partial index works |
| GET | `/healthz` | `{"status":"ok"}` — Render health check, cheap to poll |
| — | 404 / 500 | `error.html` in the retro theme |

Full flow: `/` → `/flights` → `/flights/<id>` (seat map) → `/passenger` →
`POST /bookings` → boarding pass. `/lookup` proves DB persistence live in the
demo.

---

## 4. Build order

Each step ends with a summary and a **full stop** for your review.

**Step 1 — Skeleton + database**
`db.py`, `schema.sql`, `seed.py`, `run.py`, `requirements.txt`, `.gitignore`.
*Done when:* `py run.py` creates `flights.db`, and a query shows **14 flights**
and ~1,400 seat rows. Re-running does **not** duplicate data.

**Step 2 — Core routes, unstyled**
`app.py` with `/`, `/flights`, `/flights/<id>`, plus base/index/flights/flight
templates in plain HTML.
*Done when:* I can browse to a flight detail page and see its seats listed as
text, with correct availability counts.

**Step 3 — Booking flow, end to end**
`bookings.py`, passenger form, `POST /bookings`, confirmation, `/lookup`,
cancel.
*Done when:* booking a seat writes rows to `passengers` + `bookings`, the
reference retrieves the booking via `/lookup`, and the seat then shows as taken
on the seat map. Booking the same seat twice fails gracefully with a flash, not
a 500.

**Step 4 — Interactive seat map**
`/api/flights/<id>/seats`, `static/js/seatmap.js`, seat-map CSS.
*Done when:* clicking a seat highlights it, shows class + price in a summary
panel, taken seats are unclickable, a legend explains the states, and
"Continue" carries the selected `seat_id` into the passenger form. Booking in a
second browser tab and refreshing shows the seat as taken.

**Step 5 — Retro theme**
`retro.css`, split-flap board, boarding-pass confirmation, responsive layout.
*Done when:* every page is on-theme and legible, the flow is navigable without
instructions, and it doesn't break at 375px wide.

**Step 6 — Tests + README**
`tests/test_smoke.py`: seed integrity, booking round-trip, double-book
rejection, every route returns 200.
*Done when:* `py -m unittest discover tests` passes, README documents the
single-command run.

**Step 7 — Deploy**
`render.yaml`, `.python-version`, gunicorn, git init + push, Render service.
*Done when:* a public URL serves the full booking flow, and I've completed a
real booking on it.

---

## 5. Where the seat map plugs in

**Backend**
- `GET /api/flights/<id>/seats` returns one JSON payload:
  ```json
  {
    "flight": {"number": "SK 401", "aircraft": "Boeing 707"},
    "seat_letters": ["A","B","C","D","E","F"],
    "aisle_after": "C",
    "rows": [
      {"row": 1, "cabin_class": "FIRST", "seats": [
        {"id": 12, "label": "1A", "price_cents": 89000, "available": true}
      ]}
    ],
    "class_summary": [{"cabin_class":"FIRST","from_price_cents":89000,"available":8}]
  }
  ```
- Built from the single LEFT JOIN in §2 — one query, no N+1.
- Re-validated server-side at `GET /passenger` and again inside the `POST
  /bookings` transaction. The JSON is a *view*, never the authority.

**Frontend** (`static/js/seatmap.js`, vanilla, ~120 lines)
- On load: fetch the JSON, build the grid as `<button>` elements (keyboard
  focusable and screen-reader labelled — buttons, not divs).
- Seat state via CSS classes: `.seat--free`, `.seat--taken`, `.seat--selected`,
  plus `.cabin--first/business/economy` for the class-band coloring.
- Click a free seat → deselect any previous, update a sticky summary panel with
  seat label, cabin class, and formatted fare; enable "Continue".
- **Live availability:** re-fetch on window focus and via a "Refresh seats"
  button; if the selected seat has since been taken, it clears the selection and
  says so. *Tradeoff: polling on focus instead of WebSockets — nothing to keep
  alive on a free dyno that sleeps.*
- Progressive enhancement: with JS off, the flight page still renders a plain
  server-side list of available seats with links into the passenger form.

**Class-based pricing** lives in `pricing.py` (`FIRST` ×4.0, `BUSINESS` ×2.2,
`ECONOMY` ×1.0 over `base_fare_cents`), applied once at seed time and displayed
from `seats.price_cents` thereafter.

---

## 6. Deployment (Render)

- **Service:** Render free Web Service, defined in `render.yaml` so it's
  reproducible and reviewable.
- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT "app:create_app()"`
  *Tradeoff:* **1 worker**, threads for concurrency — multiple processes would
  each race to seed the same SQLite file on boot, and free tier has 512 MB
  anyway.
- **Runtime:** `.python-version` pinned to `3.13`. Local is 3.14.6; nothing in
  the app uses version-specific behavior.
- **Health check:** `/healthz`.

**Seeding on a fresh deploy.** Render's free filesystem is ephemeral — the
`.db` file is gone on every deploy and on restart after idle. So the app
**self-seeds at startup**, inside `create_app()`:

1. `CREATE TABLE IF NOT EXISTS` from `schema.sql` (safe to re-run).
2. Open `BEGIN IMMEDIATE`, `SELECT COUNT(*) FROM flights`; if 0, insert
   aircraft, 14 flights, all seats, and a handful of pre-booked seats so the map
   doesn't look empty; commit.
3. Non-zero count → do nothing.

Idempotent and race-safe: the immediate transaction means that even if two
processes ever start together, one blocks and then sees a non-zero count.

Flight dates are generated **relative to today at seed time**, so a deploy
weeks from now still shows future departures.

**Consequence to accept:** bookings made on the live URL survive until the next
deploy or idle-restart, not forever. Fine for a graded demo — and `/lookup`
still proves persistence live. If your rubric grades durable persistence on the
deployed URL, say so and I'll swap the storage layer for Render Postgres
(~1 extra dependency, schema stays nearly identical).

**GitHub ❓** — `gh` isn't installed. Either you create an empty repo and I set
the remote and push, or you install `gh` and I do all of it.

---

## 7. Risks and de-risking

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | **Ephemeral disk wipes the DB** on the live URL | Certain | Idempotent seed-on-boot (§6). Demo bookings still work; `/lookup` proves persistence within the session |
| 2 | **Cold start** — free services sleep after 15 min idle, ~50 s to wake | High | Hit the URL a few minutes before presenting. README says so in bold |
| 3 | **Multi-worker seed race** corrupting/duplicating seed data | Medium | 1 gunicorn worker + `BEGIN IMMEDIATE` guard |
| 4 | **SQLite "database is locked"** under concurrent writes | Medium | WAL mode, `busy_timeout=5000`, short transactions, no long-lived connections |
| 5 | **Stale seat map** — user selects a seat someone just booked | Medium | Re-validated at the form *and* inside the insert; `IntegrityError` → friendly flash, not a 500. Explicitly covered by a smoke test |
| 6 | **Seat map unusable on a phone/projector** | Medium | Horizontally scrollable seat container, min 44px touch targets, tested at 375px in Step 5 |
| 7 | **Render build fails** on an unexpected dependency | Low | Only `flask` + `gunicorn`, both pinned. Deploy a hello-world early in Step 7 before pushing the full app |
| 8 | **Timezone confusion** in displayed times | Low | Store UTC, display as "local time at the airport" with a fixed offset per airport in the seed. Never call `datetime.now()` in a template |
| 9 | **Python 3.14 local vs 3.13 on Render** | Low | No version-specific syntax; `.python-version` pins the deploy |
| 10 | **Last-minute deploy failure with no fallback** | Low | Deploy at Step 7 with time to spare; README documents the one-command local run as the backup demo path |

---

## Open questions for you

1. ❓ **Single seat per booking** (my assumption) or party-of-N?
2. ❓ **GitHub repo** — you create it, or install `gh` and I do?
3. Does the rubric require bookings to survive a *redeploy* on the public URL?
   If yes → Postgres instead of SQLite for the deployed copy.
