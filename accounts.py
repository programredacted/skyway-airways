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

# Names that must not be claimed by a visitor. "admin" is the account the seed
# creates for the staff panel: if someone registered it first, the seed would
# find the name taken and the database would end up with no admin at all.
RESERVED_USERNAMES = {"admin", "administrator", "root", "staff", "crew", "skyway"}


class AccountLocked(Exception):
    """Someone tried to delete an account that is protected."""


class RegistrationError(Exception):
    """Carries per-field messages back to a form. Also raised by change_password."""

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
    elif values["username"].lower() in RESERVED_USERNAMES:
        errors["username"] = "That username is reserved. Please pick another."
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


def change_password(connection, user_id, form):
    """Replace the stored hash.

    The current password is required even though the caller is already signed
    in: a session left open on a shared machine should not be enough to lock
    the owner out of their own account.
    """
    row = get_by_id(connection, user_id)
    current = form.get("current_password", "")
    new = form.get("new_password", "")
    confirm = form.get("confirm_password", "")
    errors = {}

    if row is None or not check_password_hash(row["password_hash"], current):
        errors["current_password"] = "That isn't your current password."

    if len(new) < MINIMUM_PASSWORD_LENGTH:
        errors["new_password"] = f"At least {MINIMUM_PASSWORD_LENGTH} characters."
    elif new != confirm:
        errors["confirm_password"] = "The two passwords don't match."
    elif new == current:
        errors["new_password"] = "That's already your password."

    if errors:
        raise RegistrationError(errors)

    with db.transaction(connection):
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new), user_id),
        )
    return get_by_id(connection, user_id)


def get_by_id(connection, user_id):
    return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def last_passenger_details(connection, user_id):
    """The name and phone this account travelled under last time.

    An account holds a username and an email, not a passenger name — so the
    only place a returning traveller's name exists is on the booking they made
    before. Newest first, since that is the one most likely still correct.
    """
    return connection.execute(
        """
        SELECT p.full_name, p.email, p.phone
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def list_accounts(connection, seeded_usernames=()):
    """Every account with how many bookings it holds, newest first.

    Each row is tagged `seeded` so the panel can keep the demo logins apart
    from accounts people actually registered. Matched on name rather than a
    column, because that is exactly what makes an account one of the seed's.
    """
    seeded = {name.lower() for name in seeded_usernames}
    rows = connection.execute(
        """
        SELECT u.id, u.username, u.email, u.created_at, u.is_admin, u.is_locked,
               COUNT(b.id) AS booking_count
        FROM users u
        LEFT JOIN bookings b ON b.user_id = u.id AND b.status = 'CONFIRMED'
        GROUP BY u.id
        ORDER BY u.id DESC
        """
    ).fetchall()
    return [{**dict(row), "seeded": row["username"].lower() in seeded}
            for row in rows]


SEEDED_SHOWN = 40


def booking_totals(connection):
    """Counts on each side of the line, so the page can say what it is not
    showing rather than stopping quietly."""
    return connection.execute(
        """
        SELECT
          SUM(CASE WHEN user_id IS NOT NULL THEN 1 ELSE 0 END)  AS from_accounts,
          SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END)      AS seeded,
          SUM(CASE WHEN status = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmed,
          COUNT(*)                                              AS total
        FROM bookings
        """
    ).fetchone()


def account_bookings(connection):
    """Every booking made from an account — the real activity, never capped."""
    return _bookings(connection, "b.user_id IS NOT NULL")


def seeded_bookings(connection, limit=SEEDED_SHOWN):
    """The pre-sold seats the seed invents to make the map look flown.

    They hold no account and there are hundreds, so they are capped and kept
    in their own list: mixed in, they buried the handful that are real. A
    booking left behind by a deleted account is excluded — it has a username
    on it and gets its own box.
    """
    return _bookings(
        connection, "b.user_id IS NULL AND b.former_username IS NULL", limit)


def _bookings(connection, where, limit=None):
    return connection.execute(
        """
        SELECT b.reference, b.status, b.price_paid_cents, b.created_at,
               b.user_id, b.former_username, u.username,
               p.full_name, p.email,
               s.row_number, s.seat_letter, s.cabin_class,
               f.flight_number, f.origin_code, f.dest_code, f.dest_city,
               f.departs_at
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        JOIN seats s ON s.id = b.seat_id
        JOIN flights f ON f.id = b.flight_id
        LEFT JOIN users u ON u.id = b.user_id
        WHERE """ + where + """
        ORDER BY b.id DESC
        LIMIT ?
        """,
        (limit if limit is not None else -1,),      # -1 is SQLite for "no limit"
    ).fetchall()


def set_locked(connection, user_id, locked):
    """Protect an account from deletion, or stop protecting it."""
    with db.transaction(connection):
        connection.execute("UPDATE users SET is_locked = ? WHERE id = ?",
                           (1 if locked else 0, user_id))
    return get_by_id(connection, user_id)


def ghost_bookings(connection):
    """Bookings whose account was deleted while they were kept.

    A seat deliberately left sold has to stay visible and cancellable, or it is
    lost among the hundreds the seed pre-sold. `former_username` is what tells
    the two apart. Newest first, most recently orphaned account first.
    """
    return _bookings(connection, "b.user_id IS NULL AND b.former_username IS NOT NULL")


def delete_account(connection, user_id, cancel_bookings=False):
    """Remove an account. Returns True if a row went.

    Its bookings either stay CONFIRMED — the seat was paid for, and the
    reference still works at /lookup — or are cancelled outright, which is the
    caller's decision, not this function's. Either way the username is written
    onto them, so a kept booking can still be found and acted on afterwards.

    Refuses a locked account here rather than only in the view: hiding the
    button is a courtesy, this is the actual rule.
    """
    row = get_by_id(connection, user_id)
    if row is None:
        return False
    if row["is_locked"]:
        raise AccountLocked(row["username"])

    with db.transaction(connection):
        if cancel_bookings:
            connection.execute(
                """UPDATE bookings SET status = 'CANCELLED'
                   WHERE user_id = ? AND status = 'CONFIRMED'""",
                (user_id,),
            )
        connection.execute(
            "UPDATE bookings SET user_id = NULL, former_username = ? WHERE user_id = ?",
            (row["username"], user_id),
        )
        cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0


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
