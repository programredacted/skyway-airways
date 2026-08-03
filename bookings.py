"""Creating, cancelling and referencing bookings — the only writes the app makes."""

import random
import sqlite3
from datetime import datetime, timezone

import db

# Reference alphabet without look-alikes (no O/0, no I/1) so it can be read aloud.
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REFERENCE_LENGTH = 6


class SeatUnavailable(Exception):
    """Raised when the chosen seat was sold between selection and confirmation."""


def make_reference(rng=random):
    return "".join(rng.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_booking(connection, seat_id, full_name, email, phone=None, user_id=None):
    """Sell one seat to one passenger. Returns the booking reference.

    Raises SeatUnavailable if someone else confirmed the seat first — the
    partial unique index on bookings is what actually decides the race.
    `user_id` ties the booking to an account so it can appear in My Trips.
    """
    with db.transaction(connection):
        seat = connection.execute(
            "SELECT id, flight_id, price_cents FROM seats WHERE id = ?", (seat_id,)
        ).fetchone()
        if seat is None:
            raise SeatUnavailable("That seat does not exist.")

        cursor = connection.execute(
            "INSERT INTO passengers (full_name, email, phone, created_at) VALUES (?, ?, ?, ?)",
            (full_name.strip(), email.strip(), (phone or "").strip() or None, utc_now()),
        )
        passenger_id = cursor.lastrowid

        reference = _insert_booking(connection, seat, passenger_id, user_id)

    return reference


def _insert_booking(connection, seat, passenger_id, user_id=None):
    """Insert with a fresh reference, retrying only on a reference collision.

    Two unique constraints can fire here. A clash on `reference` is harmless --
    draw another code. A clash on `seat_id` means the partial index refused a
    second sale of the seat, which is the race we care about.
    """
    for _ in range(5):
        reference = make_reference()
        try:
            connection.execute(
                """
                INSERT INTO bookings
                    (reference, flight_id, seat_id, passenger_id, user_id,
                     price_paid_cents, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', ?)
                """,
                (reference, seat["flight_id"], seat["id"], passenger_id, user_id,
                 seat["price_cents"], utc_now()),
            )
            return reference
        except sqlite3.IntegrityError as error:
            if "bookings.reference" not in str(error):
                raise SeatUnavailable("That seat was just taken.") from error
            # Duplicate reference: draw another and retry.
    raise RuntimeError("Could not generate a unique booking reference.")


def cancel_booking(connection, reference):
    """Release the seat back to the map. Returns True if a booking was cancelled."""
    with db.transaction(connection):
        cursor = connection.execute(
            "UPDATE bookings SET status = 'CANCELLED' WHERE reference = ? AND status = 'CONFIRMED'",
            (reference.strip().upper(),),
        )
        return cursor.rowcount > 0
