"""Print a booking straight out of SQLite:  py show_booking.py ABC123

Reads the database directly with the stdlib driver -- no Flask, no app code --
so what it prints is what is actually stored, not what a page says is stored.
With no reference it shows the most recent booking.
"""

import sqlite3
import sys

QUERY = """
SELECT b.reference, b.status, b.created_at,
       p.full_name, p.email,
       f.flight_number, f.origin_code, f.dest_code,
       s.row_number || s.seat_letter AS seat, s.cabin_class,
       b.price_paid_cents
FROM bookings b
JOIN passengers p ON p.id = b.passenger_id
JOIN flights    f ON f.id = b.flight_id
JOIN seats      s ON s.id = b.seat_id
"""


def fetch(reference):
    connection = sqlite3.connect("flights.db")
    connection.row_factory = sqlite3.Row
    if reference:
        return connection.execute(
            QUERY + " WHERE b.reference = ?", (reference.upper(),)
        ).fetchone()
    return connection.execute(QUERY + " ORDER BY b.id DESC LIMIT 1").fetchone()


def main():
    reference = sys.argv[1] if len(sys.argv) > 1 else None
    booking = fetch(reference)
    if booking is None:
        print(f"No booking found for {reference!r}.")
        return

    print()
    for label, value in [
        ("Reference", booking["reference"]),
        ("Status", booking["status"]),
        ("Passenger", f'{booking["full_name"]}  <{booking["email"]}>'),
        ("Flight", f'{booking["flight_number"]}  '
                   f'{booking["origin_code"]} -> {booking["dest_code"]}'),
        ("Seat", f'{booking["seat"]}  ({booking["cabin_class"]})'),
        ("Paid", f'${booking["price_paid_cents"] / 100:,.2f}'),
        ("Booked at", booking["created_at"]),
    ]:
        print(f"  {label:<11} {value}")
    print()


if __name__ == "__main__":
    main()
