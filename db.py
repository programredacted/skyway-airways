"""SQLite connection handling and every read query the app makes.

Routes call these functions; no route writes SQL itself.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_DB_PATH = PROJECT_ROOT / "flights.db"
SCHEMA_PATH = PROJECT_ROOT / "schema.sql"


def connect(db_path=None):
    """Open a connection with the pragmas this app depends on."""
    connection = sqlite3.connect(
        str(db_path or DEFAULT_DB_PATH),
        timeout=5.0,
        isolation_level=None,  # we manage transactions explicitly, see transaction()
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")  # SQLite defaults this off
    connection.execute("PRAGMA journal_mode = WAL")  # readers never block on a writer
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def transaction(connection):
    """Run a write inside BEGIN IMMEDIATE so the write lock is taken up front."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")


# CREATE TABLE IF NOT EXISTS leaves an existing table exactly as it is, so a
# column added to schema.sql later would never appear in a database that was
# already created. Backfilling here means an old file keeps working instead of
# having to be deleted and reseeded.
MIGRATIONS = {
    "users": [
        ("is_admin", "INTEGER NOT NULL DEFAULT 0"),
        ("is_locked", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "bookings": [
        ("former_username", "TEXT"),
    ],
}


def init_db(connection):
    """Create tables and indexes. Safe to run against an existing database."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    add_missing_columns(connection)


def add_missing_columns(connection):
    """Add any column in MIGRATIONS that this database does not have yet."""
    for table, columns in MIGRATIONS.items():
        present = {row["name"]
                   for row in connection.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns:
            if name not in present:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


# --- flights -----------------------------------------------------------------

# Availability is derived, never stored: a seat is free when no CONFIRMED
# booking points at it. One source of truth, so nothing can drift out of sync.
FLIGHT_COLUMNS = """
    f.*,
    a.model AS aircraft_model,
    COUNT(s.id) AS total_seats,
    SUM(CASE WHEN b.id IS NULL THEN 1 ELSE 0 END) AS seats_available,
    MIN(CASE WHEN b.id IS NULL THEN s.price_cents END) AS from_price_cents
"""

FLIGHT_JOINS = """
    FROM flights f
    JOIN aircraft a ON a.id = f.aircraft_id
    JOIN seats s ON s.flight_id = f.id
    LEFT JOIN bookings b ON b.seat_id = s.id AND b.status = 'CONFIRMED'
"""


def get_flights(connection, origin=None, dest=None, date=None):
    """All flights, newest departure first, optionally filtered. One query, no N+1."""
    conditions = []
    params = []
    if origin:
        conditions.append("f.origin_code = ?")
        params.append(origin.upper())
    if dest:
        conditions.append("f.dest_code = ?")
        params.append(dest.upper())
    if date:
        conditions.append("substr(f.departs_at, 1, 10) = ?")
        params.append(date)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT {FLIGHT_COLUMNS} {FLIGHT_JOINS} {where} GROUP BY f.id ORDER BY f.departs_at"
    return connection.execute(sql, params).fetchall()


def get_flight(connection, flight_id):
    """One flight with its availability totals, or None."""
    sql = f"SELECT {FLIGHT_COLUMNS} {FLIGHT_JOINS} WHERE f.id = ? GROUP BY f.id"
    return connection.execute(sql, (flight_id,)).fetchone()


def get_airports(connection):
    """Every airport we serve, with its clock offset and coordinates."""
    return connection.execute(
        "SELECT code, city, utc_offset_hours, latitude, longitude"
        " FROM airports ORDER BY city"
    ).fetchall()


def get_routes(connection):
    """Every flight with both endpoints' coordinates, for the route map.

    Availability rides along so the map can colour a route by how full it is.
    """
    return connection.execute(
        """
        SELECT f.id, f.flight_number, f.status,
               f.origin_code, f.origin_city, f.dest_code, f.dest_city,
               f.departs_at, f.arrives_at, f.duration_minutes,
               a.model AS aircraft_model,
               o.latitude AS origin_lat, o.longitude AS origin_lon,
               d.latitude AS dest_lat,   d.longitude AS dest_lon,
               COUNT(s.id) AS total_seats,
               SUM(CASE WHEN b.id IS NULL THEN 1 ELSE 0 END) AS seats_available,
               MIN(CASE WHEN b.id IS NULL THEN s.price_cents END) AS from_price_cents
        FROM flights f
        JOIN aircraft a ON a.id = f.aircraft_id
        JOIN airports o ON o.code = f.origin_code
        JOIN airports d ON d.code = f.dest_code
        JOIN seats s ON s.flight_id = f.id
        LEFT JOIN bookings b ON b.seat_id = s.id AND b.status = 'CONFIRMED'
        GROUP BY f.id
        ORDER BY f.departs_at
        """
    ).fetchall()


# --- seats -------------------------------------------------------------------

def get_seats(connection, flight_id):
    """Every seat on a flight with an `available` flag, in cabin order."""
    return connection.execute(
        """
        SELECT s.*, (b.id IS NULL) AS available
        FROM seats s
        LEFT JOIN bookings b ON b.seat_id = s.id AND b.status = 'CONFIRMED'
        WHERE s.flight_id = ?
        ORDER BY s.row_number, s.seat_letter
        """,
        (flight_id,),
    ).fetchall()


def get_seat(connection, seat_id):
    """One seat with its flight, or None. `available` reflects live state."""
    return connection.execute(
        """
        SELECT s.*, (b.id IS NULL) AS available, f.flight_number, f.base_fare_cents
        FROM seats s
        JOIN flights f ON f.id = s.flight_id
        LEFT JOIN bookings b ON b.seat_id = s.id AND b.status = 'CONFIRMED'
        WHERE s.id = ?
        """,
        (seat_id,),
    ).fetchone()


def get_cabin_summary(connection, flight_id):
    """Per-cabin seat counts and cheapest available fare, for the seat map legend."""
    return connection.execute(
        """
        SELECT s.cabin_class,
               COUNT(*) AS total,
               SUM(CASE WHEN b.id IS NULL THEN 1 ELSE 0 END) AS available,
               MIN(s.price_cents) AS price_cents
        FROM seats s
        LEFT JOIN bookings b ON b.seat_id = s.id AND b.status = 'CONFIRMED'
        WHERE s.flight_id = ?
        GROUP BY s.cabin_class
        """,
        (flight_id,),
    ).fetchall()


def get_aircraft_for_flight(connection, flight_id):
    """The cabin layout used to draw the seat map."""
    return connection.execute(
        """
        SELECT a.* FROM aircraft a
        JOIN flights f ON f.aircraft_id = a.id
        WHERE f.id = ?
        """,
        (flight_id,),
    ).fetchone()


# --- bookings (reads; writes live in bookings.py) ----------------------------

def get_booking_by_reference(connection, reference):
    """A booking joined to everything the boarding pass needs to print."""
    return connection.execute(
        """
        SELECT b.*,
               p.full_name, p.email, p.phone,
               s.row_number, s.seat_letter, s.cabin_class,
               f.flight_number, f.airline, f.origin_code, f.origin_city,
               f.dest_code, f.dest_city, f.departs_at, f.arrives_at,
               f.duration_minutes,
               a.model AS aircraft_model
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        JOIN seats s ON s.id = b.seat_id
        JOIN flights f ON f.id = b.flight_id
        JOIN aircraft a ON a.id = f.aircraft_id
        WHERE b.reference = ?
        """,
        (reference.strip().upper(),),
    ).fetchone()


def get_active_booking_for_seat(connection, seat_id):
    """The CONFIRMED booking holding a seat, if any. Used to tell a genuine
    clash apart from the same passenger submitting the form twice."""
    return connection.execute(
        """
        SELECT b.reference, b.status, p.email, p.full_name
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        WHERE b.seat_id = ? AND b.status = 'CONFIRMED'
        """,
        (seat_id,),
    ).fetchone()


def count_rows(connection, table):
    """Row count for a table. Used by the seed guard and the tests."""
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
