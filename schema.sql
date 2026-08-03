-- Skyway Airways schema. Safe to re-run: every object is IF NOT EXISTS.
-- Money is stored as integer cents. Times are local clock times at the airport
-- (ISO-8601, no zone) -- exactly what a printed timetable shows.

CREATE TABLE IF NOT EXISTS aircraft (
    id                    INTEGER PRIMARY KEY,
    model                 TEXT    NOT NULL UNIQUE,
    seat_letters          TEXT    NOT NULL,  -- the full width, e.g. "ABCDEF", left to right
    aisle_after           TEXT    NOT NULL,  -- letters an aisle follows, e.g. "C" or "C,F"
    total_rows            INTEGER NOT NULL,
    first_class_last_row  INTEGER NOT NULL,  -- rows 1..N are First
    business_last_row     INTEGER NOT NULL,  -- next rows are Business, remainder Economy
    -- Premium cabins are not the full width: First flies 1-1 and Business 2-2, so
    -- they use a subset of the letters and leave the middle of the row empty.
    first_letters         TEXT    NOT NULL,
    business_letters      TEXT    NOT NULL
);

-- Airports carry the two things the timetable itself cannot: a clock offset for
-- the departure-board clock, and coordinates for the route map.
CREATE TABLE IF NOT EXISTS airports (
    code             TEXT PRIMARY KEY,
    city             TEXT    NOT NULL,
    utc_offset_hours INTEGER NOT NULL,  -- whole hours; no daylight saving
    latitude         REAL    NOT NULL,
    longitude        REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS flights (
    id               INTEGER PRIMARY KEY,
    flight_number    TEXT    NOT NULL UNIQUE,
    airline          TEXT    NOT NULL,
    aircraft_id      INTEGER NOT NULL REFERENCES aircraft (id),
    origin_code      TEXT    NOT NULL,
    origin_city      TEXT    NOT NULL,
    dest_code        TEXT    NOT NULL,
    dest_city        TEXT    NOT NULL,
    departs_at       TEXT    NOT NULL,  -- local at origin, "YYYY-MM-DDTHH:MM"
    arrives_at       TEXT    NOT NULL,  -- local at destination
    duration_minutes INTEGER NOT NULL,  -- true elapsed time, zone-independent
    base_fare_cents  INTEGER NOT NULL,  -- Economy fare; other cabins are multiples
    status           TEXT    NOT NULL DEFAULT 'SCHEDULED'
);

CREATE INDEX IF NOT EXISTS idx_flights_route ON flights (origin_code, dest_code);
CREATE INDEX IF NOT EXISTS idx_flights_departure ON flights (departs_at);

CREATE TABLE IF NOT EXISTS seats (
    id          INTEGER PRIMARY KEY,
    flight_id   INTEGER NOT NULL REFERENCES flights (id) ON DELETE CASCADE,
    row_number  INTEGER NOT NULL,
    seat_letter TEXT    NOT NULL,
    cabin_class TEXT    NOT NULL CHECK (cabin_class IN ('FIRST', 'BUSINESS', 'ECONOMY')),
    price_cents INTEGER NOT NULL,
    UNIQUE (flight_id, row_number, seat_letter)
);

CREATE INDEX IF NOT EXISTS idx_seats_flight ON seats (flight_id);

-- Accounts. Passwords are only ever stored as a werkzeug hash; nothing in the
-- app has access to the plaintext after registration.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Case-insensitive uniqueness: "Jimmy" and "jimmy" are the same account.
CREATE UNIQUE INDEX IF NOT EXISTS one_account_per_username
    ON users (LOWER(username));
CREATE UNIQUE INDEX IF NOT EXISTS one_account_per_email
    ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS passengers (
    id         INTEGER PRIMARY KEY,
    full_name  TEXT NOT NULL,
    email      TEXT NOT NULL,
    phone      TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id               INTEGER PRIMARY KEY,
    reference        TEXT    NOT NULL UNIQUE,
    flight_id        INTEGER NOT NULL REFERENCES flights (id),
    seat_id          INTEGER NOT NULL REFERENCES seats (id),
    passenger_id     INTEGER NOT NULL REFERENCES passengers (id),
    -- The account that made the booking. Nullable so the seeded pre-sold seats,
    -- which belong to no one, still satisfy the constraint.
    user_id          INTEGER          REFERENCES users (id),
    price_paid_cents INTEGER NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'CONFIRMED'
                             CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    created_at       TEXT    NOT NULL
);

-- The rule that makes double-booking impossible: at most one CONFIRMED booking
-- per seat. A CANCELLED booking releases the seat but stays in the history.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_booking_per_seat
    ON bookings (seat_id) WHERE status = 'CONFIRMED';

CREATE INDEX IF NOT EXISTS idx_bookings_flight ON bookings (flight_id);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings (user_id);
