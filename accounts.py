"""User accounts: registration, sign-in, and the session they live in.

Passwords never exist in the database in readable form. `register` hashes on the
way in and `authenticate` compares against the hash; nothing here can return a
plaintext password, because nothing here ever has one.
"""

import re
import sqlite3
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

import db

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9]{3,20}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MINIMUM_PASSWORD_LENGTH = 8


class RegistrationError(Exception):
    """Carries per-field messages back to the form."""

    def __init__(self, errors):
        super().__init__("registration rejected")
        self.errors = errors


def validate(form):
    """Return (cleaned values, errors). Runs on the server, always."""
    values = {
        "username": form.get("username", "").strip(),
        "email": form.get("email", "").strip(),
    }
    password = form.get("password", "")
    confirm = form.get("confirm", "")
    errors = {}

    if not USERNAME_PATTERN.match(values["username"]):
        errors["username"] = "3 to 20 letters and numbers, nothing else."
    if not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "That doesn't look like an email address."
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        errors["password"] = f"At least {MINIMUM_PASSWORD_LENGTH} characters."
    elif password != confirm:
        errors["confirm"] = "The two passwords don't match."

    return values, password, errors


def register(connection, form):
    """Create an account. Raises RegistrationError with per-field messages."""
    values, password, errors = validate(form)
    if errors:
        raise RegistrationError(errors)

    try:
        with db.transaction(connection):
            cursor = connection.execute(
                """
                INSERT INTO users (username, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (values["username"], values["email"],
                 generate_password_hash(password), _now()),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError as error:
        # The unique indexes are on LOWER(...), so this is where a clash lands.
        field = "email" if "email" in str(error) else "username"
        raise RegistrationError({field: f"That {field} is already registered."}) from error

    return get_by_id(connection, user_id)


def authenticate(connection, username, password):
    """The user if the credentials match, else None.

    Callers must report one generic failure for both a wrong password and an
    unknown username — saying which was wrong tells an attacker who has an
    account here.
    """
    row = connection.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
        ((username or "").strip(),),
    ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password or ""):
        return None
    return row


def get_by_id(connection, user_id):
    return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def bookings_for(connection, user_id):
    """Every booking this account has made, newest first."""
    return connection.execute(
        """
        SELECT b.reference, b.status, b.price_paid_cents, b.created_at,
               p.full_name, p.email,
               s.row_number, s.seat_letter, s.cabin_class,
               f.flight_number, f.airline, f.origin_code, f.origin_city,
               f.dest_code, f.dest_city, f.departs_at, f.arrives_at,
               f.duration_minutes, a.model AS aircraft_model
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        JOIN seats s ON s.id = b.seat_id
        JOIN flights f ON f.id = b.flight_id
        JOIN aircraft a ON a.id = f.aircraft_id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
        """,
        (user_id,),
    ).fetchall()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
