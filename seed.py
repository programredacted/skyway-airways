"""Seed the database with the Skyway timetable.

Idempotent: seeding is skipped entirely if any flight already exists, so a fresh
deploy fills an empty database and a restart leaves a populated one alone.

Run directly to (re)build and print the timetable:  py seed.py
"""

import random
from datetime import datetime, timedelta

import db
from pricing import CABIN_ORDER, fare_for_class, format_fare

AIRLINE = "Skyway Airways"

# code -> (city, hours offset from UTC, latitude, longitude).
# Whole-hour offsets only, to keep arrival maths honest; coordinates are the
# real airport positions, used to plot the route map.
AIRPORTS = {
    "JFK": ("New York", -5, 40.64, -73.78),
    "LAX": ("Los Angeles", -8, 33.94, -118.41),
    "SFO": ("San Francisco", -8, 37.62, -122.38),
    "ORD": ("Chicago", -6, 41.98, -87.90),
    "MIA": ("Miami", -5, 25.79, -80.29),
    "ANC": ("Anchorage", -9, 61.17, -150.00),
    "HNL": ("Honolulu", -10, 21.32, -157.92),
    "MEX": ("Mexico City", -6, 19.44, -99.07),
    "GIG": ("Rio de Janeiro", -3, -22.81, -43.25),
    "LHR": ("London", 0, 51.47, -0.45),
    "CDG": ("Paris", 1, 49.01, 2.55),
    "FCO": ("Rome", 1, 41.80, 12.25),
    "FRA": ("Frankfurt", 1, 50.04, 8.56),
    "IST": ("Istanbul", 3, 41.28, 28.75),
    "HKG": ("Hong Kong", 8, 22.31, 113.91),
    "HND": ("Tokyo", 9, 35.55, 139.78),
    "SYD": ("Sydney", 10, -33.94, 151.18),
}

# Cabin bands are row ranges: rows 1..first_class_last_row are First, the next
# rows up to business_last_row are Business, everything behind that is Economy.
AIRCRAFT = [
    {"model": "Boeing 707-320B", "seat_letters": "ABCDEF", "aisle_after": "C",
     "total_rows": 24, "first_class_last_row": 3, "business_last_row": 8},
    {"model": "Douglas DC-8-62", "seat_letters": "ABCDEF", "aisle_after": "C",
     "total_rows": 22, "first_class_last_row": 2, "business_last_row": 6},
    {"model": "Convair 880", "seat_letters": "ABCD", "aisle_after": "B",
     "total_rows": 18, "first_class_last_row": 2, "business_last_row": 5},
    {"model": "Boeing 727-100", "seat_letters": "ABCDEF", "aisle_after": "C",
     "total_rows": 20, "first_class_last_row": 2, "business_last_row": 5},
    {"model": "Boeing 747-100", "seat_letters": "ABCDEFGHJ", "aisle_after": "C,F",
     "total_rows": 28, "first_class_last_row": 3, "business_last_row": 9},
    {"model": "Lockheed L-1011 TriStar", "seat_letters": "ABCDEFGH", "aisle_after": "B,F",
     "total_rows": 26, "first_class_last_row": 3, "business_last_row": 8},
]

# days_out is relative to the seed date, so the timetable never goes stale.
# sold_fraction drives how much of Economy is pre-sold; premium cabins sell less.
FLIGHTS = [
    {"number": "SK 001", "origin": "JFK", "dest": "LHR", "aircraft": "Boeing 707-320B",
     "days_out": 1, "departs": "19:30", "minutes": 425, "fare": 42900,
     "status": "SCHEDULED", "sold_fraction": 0.32},
    {"number": "SK 002", "origin": "LHR", "dest": "JFK", "aircraft": "Boeing 707-320B",
     "days_out": 2, "departs": "11:00", "minutes": 475, "fare": 43900,
     "status": "SCHEDULED", "sold_fraction": 0.24},
    {"number": "SK 014", "origin": "JFK", "dest": "LAX", "aircraft": "Douglas DC-8-62",
     "days_out": 1, "departs": "08:15", "minutes": 355, "fare": 18900,
     "status": "SCHEDULED", "sold_fraction": 0.41},
    {"number": "SK 021", "origin": "LAX", "dest": "HNL", "aircraft": "Douglas DC-8-62",
     "days_out": 3, "departs": "10:45", "minutes": 320, "fare": 24900,
     "status": "SCHEDULED", "sold_fraction": 0.36},
    {"number": "SK 033", "origin": "SFO", "dest": "HND", "aircraft": "Boeing 747-100",
     "days_out": 4, "departs": "13:20", "minutes": 630, "fare": 68900,
     "status": "SCHEDULED", "sold_fraction": 0.27},
    {"number": "SK 044", "origin": "JFK", "dest": "CDG", "aircraft": "Boeing 707-320B",
     "days_out": 2, "departs": "21:05", "minutes": 440, "fare": 43900,
     "status": "DELAYED", "sold_fraction": 0.55},
    {"number": "SK 055", "origin": "ORD", "dest": "SFO", "aircraft": "Boeing 727-100",
     "days_out": 1, "departs": "07:40", "minutes": 265, "fare": 15900,
     "status": "SCHEDULED", "sold_fraction": 0.48},
    {"number": "SK 066", "origin": "MIA", "dest": "GIG", "aircraft": "Douglas DC-8-62",
     "days_out": 5, "departs": "22:30", "minutes": 550, "fare": 54900,
     "status": "SCHEDULED", "sold_fraction": 0.30},
    {"number": "SK 077", "origin": "JFK", "dest": "FCO", "aircraft": "Lockheed L-1011 TriStar",
     "days_out": 6, "departs": "18:50", "minutes": 520, "fare": 47900,
     "status": "SCHEDULED", "sold_fraction": 0.22},
    # Nearly sold out -- the seat map should look busy in the demo.
    {"number": "SK 088", "origin": "LAX", "dest": "SYD", "aircraft": "Boeing 747-100",
     "days_out": 7, "departs": "23:15", "minutes": 890, "fare": 89900,
     "status": "SCHEDULED", "sold_fraction": 0.93},
    {"number": "SK 099", "origin": "ORD", "dest": "MEX", "aircraft": "Boeing 727-100",
     "days_out": 3, "departs": "15:25", "minutes": 245, "fare": 15900,
     "status": "SCHEDULED", "sold_fraction": 0.38},
    # Also nearly sold out, and the smallest aircraft in the fleet.
    {"number": "SK 101", "origin": "SFO", "dest": "ANC", "aircraft": "Convair 880",
     "days_out": 4, "departs": "09:10", "minutes": 305, "fare": 22900,
     "status": "SCHEDULED", "sold_fraction": 0.90},
    {"number": "SK 112", "origin": "JFK", "dest": "FRA", "aircraft": "Lockheed L-1011 TriStar",
     "days_out": 8, "departs": "20:00", "minutes": 465, "fare": 44900,
     "status": "SCHEDULED", "sold_fraction": 0.26},
    {"number": "SK 121", "origin": "HNL", "dest": "HKG", "aircraft": "Boeing 747-100",
     "days_out": 9, "departs": "12:00", "minutes": 615, "fare": 62900,
     "status": "SCHEDULED", "sold_fraction": 0.34},
    {"number": "SK 133", "origin": "LHR", "dest": "IST", "aircraft": "Boeing 727-100",
     "days_out": 5, "departs": "16:40", "minutes": 230, "fare": 19900,
     "status": "SCHEDULED", "sold_fraction": 0.44},
]

SEED_PASSENGER_NAMES = [
    "Ava Lindqvist", "Marcus Bell", "Rosalind Vane", "Theo Marchetti",
    "Ingrid Sorensen", "Desmond Clay", "Nadia Farouk", "Walter Ng",
    "Cleo Baptiste", "Harold Weaver", "Juno Takahashi", "Estelle Moreau",
    "Rafael Duarte", "Beatrix Holm", "Owen Castellanos", "Mira Anand",
    "Sylvia Cortez", "Gordon Pike", "Leona Whitfield", "Amos Trager",
]


def cabin_class_for_row(row_number, aircraft):
    if row_number <= aircraft["first_class_last_row"]:
        return "FIRST"
    if row_number <= aircraft["business_last_row"]:
        return "BUSINESS"
    return "ECONOMY"


def local_times(spec, seed_date):
    """Departure and arrival as local clock times at their own airports."""
    hour, minute = (int(part) for part in spec["departs"].split(":"))
    departs = seed_date + timedelta(days=spec["days_out"], hours=hour, minutes=minute)

    offset_shift = AIRPORTS[spec["dest"]][1] - AIRPORTS[spec["origin"]][1]
    arrives = departs + timedelta(minutes=spec["minutes"] + offset_shift * 60)

    stamp = "%Y-%m-%dT%H:%M"
    return departs.strftime(stamp), arrives.strftime(stamp)


def seed_if_empty(connection, seed_date=None):
    """Populate an empty database. Returns True if it seeded, False if it skipped."""
    seed_date = seed_date or datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    with db.transaction(connection):
        # Airports are guarded separately, so a database seeded before this
        # table existed still picks them up on the next start.
        _insert_airports_if_empty(connection)
        _insert_demo_users_if_empty(connection)

        if db.count_rows(connection, "flights") > 0:
            return False

        aircraft_ids = _insert_aircraft(connection)
        passenger_ids = _insert_seed_passengers(connection)

        for spec in FLIGHTS:
            flight_id = _insert_flight(connection, spec, aircraft_ids, seed_date)
            _insert_seats(connection, flight_id, spec, aircraft_ids)
            _presell_seats(connection, flight_id, spec, passenger_ids)

    return True


def _insert_airports_if_empty(connection):
    if db.count_rows(connection, "airports") > 0:
        return False
    connection.executemany(
        "INSERT INTO airports (code, city, utc_offset_hours, latitude, longitude)"
        " VALUES (?, ?, ?, ?, ?)",
        [(code, city, offset, lat, lon)
         for code, (city, offset, lat, lon) in AIRPORTS.items()],
    )
    return True


# Two accounts so a fresh deploy can be signed into immediately. Passwords are
# hashed on the way in exactly like a real registration; the plaintext lives
# only here, in the seed, and is documented in the README.
DEMO_USERS = [
    ("demo", "demo@skyway.example", "Jetage1965!"),
    ("captain", "captain@skyway.example", "Clipper707!"),
]


def _insert_demo_users_if_empty(connection):
    if db.count_rows(connection, "users") > 0:
        return False

    from werkzeug.security import generate_password_hash

    created_at = datetime.now().isoformat(timespec="seconds")
    connection.executemany(
        "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        [(username, email, generate_password_hash(password), created_at)
         for username, email, password in DEMO_USERS],
    )
    return True


def _insert_aircraft(connection):
    """Insert the fleet; return {model: id}."""
    ids = {}
    for plane in AIRCRAFT:
        cursor = connection.execute(
            """
            INSERT INTO aircraft
                (model, seat_letters, aisle_after, total_rows,
                 first_class_last_row, business_last_row)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (plane["model"], plane["seat_letters"], plane["aisle_after"],
             plane["total_rows"], plane["first_class_last_row"], plane["business_last_row"]),
        )
        ids[plane["model"]] = cursor.lastrowid
    return ids


def _insert_seed_passengers(connection):
    """Fictional passengers who hold the pre-sold seats."""
    created_at = datetime.now().isoformat(timespec="seconds")
    ids = []
    for name in SEED_PASSENGER_NAMES:
        handle = name.lower().replace(" ", ".")
        cursor = connection.execute(
            "INSERT INTO passengers (full_name, email, phone, created_at) VALUES (?, ?, ?, ?)",
            (name, f"{handle}@example.com", None, created_at),
        )
        ids.append(cursor.lastrowid)
    return ids


def _insert_flight(connection, spec, aircraft_ids, seed_date):
    departs_at, arrives_at = local_times(spec, seed_date)
    origin_city = AIRPORTS[spec["origin"]][0]
    dest_city = AIRPORTS[spec["dest"]][0]


    cursor = connection.execute(
        """
        INSERT INTO flights
            (flight_number, airline, aircraft_id, origin_code, origin_city,
             dest_code, dest_city, departs_at, arrives_at, duration_minutes,
             base_fare_cents, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (spec["number"], AIRLINE, aircraft_ids[spec["aircraft"]],
         spec["origin"], origin_city, spec["dest"], dest_city,
         departs_at, arrives_at, spec["minutes"], spec["fare"], spec["status"]),
    )
    return cursor.lastrowid


def _insert_seats(connection, flight_id, spec, aircraft_ids):
    """One row per physical seat, priced by cabin at seed time."""
    plane = next(p for p in AIRCRAFT if p["model"] == spec["aircraft"])
    rows = []
    for row_number in range(1, plane["total_rows"] + 1):
        cabin_class = cabin_class_for_row(row_number, plane)
        price_cents = fare_for_class(spec["fare"], cabin_class)
        for letter in plane["seat_letters"]:
            rows.append((flight_id, row_number, letter, cabin_class, price_cents))

    connection.executemany(
        """
        INSERT INTO seats (flight_id, row_number, seat_letter, cabin_class, price_cents)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )


# Premium cabins sell slower than the back of the aircraft.
CABIN_SELL_RATE = {"FIRST": 0.45, "BUSINESS": 0.7, "ECONOMY": 1.0}


def _presell_seats(connection, flight_id, spec, passenger_ids):
    """Book a realistic slice of each cabin so the seat map shows sold seats.

    Seeded from the flight number, so the same flight always sells the same
    seats -- reproducible demos and reproducible tests.
    """
    rng = random.Random(spec["number"])
    seats = connection.execute(
        "SELECT id, cabin_class, price_cents FROM seats WHERE flight_id = ?", (flight_id,)
    ).fetchall()

    chosen = []
    for cabin_class in CABIN_ORDER:
        in_cabin = [seat for seat in seats if seat["cabin_class"] == cabin_class]
        sell_count = round(len(in_cabin) * spec["sold_fraction"] * CABIN_SELL_RATE[cabin_class])
        chosen.extend(rng.sample(in_cabin, min(sell_count, len(in_cabin))))

    created_at = datetime.now().isoformat(timespec="seconds")
    rows = []
    for index, seat in enumerate(chosen):
        rows.append((
            _seed_reference(rng),
            flight_id,
            seat["id"],
            passenger_ids[index % len(passenger_ids)],
            seat["price_cents"],
            created_at,
        ))

    connection.executemany(
        """
        INSERT INTO bookings
            (reference, flight_id, seat_id, passenger_id, price_paid_cents, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'CONFIRMED', ?)
        """,
        rows,
    )


def _seed_reference(rng):
    """Seed references start with 'S' so demo bookings are easy to tell apart."""
    import bookings  # imported here to keep the seed module import-light

    return "S" + bookings.make_reference(rng)[1:]


# --- console output ----------------------------------------------------------

def print_timetable(connection):
    """Print the seeded flights as a departure board."""
    flights = db.get_flights(connection)

    header = (
        f"{'FLIGHT':<7} {'ROUTE':<38} {'AIRCRAFT':<24} "
        f"{'DEPARTS':<17} {'ARRIVES':<17} {'DUR':>6} {'FROM':>7} {'SEATS FREE':>11}"
    )
    print(header)
    print("-" * len(header))

    for flight in flights:
        route = (f"{flight['origin_code']}-{flight['dest_code']}  "
                 f"{flight['origin_city']} to {flight['dest_city']}")
        duration = f"{flight['duration_minutes'] // 60}h{flight['duration_minutes'] % 60:02d}"
        seats = f"{flight['seats_available']}/{flight['total_seats']}"
        print(
            f"{flight['flight_number']:<7} {route:<38} {flight['aircraft_model']:<24} "
            f"{flight['departs_at'].replace('T', ' '):<17} "
            f"{flight['arrives_at'].replace('T', ' '):<17} "
            f"{duration:>6} {format_fare(flight['from_price_cents'] or 0):>7} {seats:>11}"
        )

    total_seats = db.count_rows(connection, "seats")
    sold = db.count_rows(connection, "bookings")
    print("-" * len(header))
    print(f"{len(flights)} flights, {total_seats} seats, {sold} already sold, "
          f"{total_seats - sold} available. All times local to each airport.")


if __name__ == "__main__":
    connection = db.connect()
    db.init_db(connection)
    seeded = seed_if_empty(connection)
    print("Seeded a fresh database.\n" if seeded else "Database already seeded, left alone.\n")
    print_timetable(connection)
    connection.close()
