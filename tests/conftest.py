"""Shared fixtures.

Every test gets its own SQLite file, created and seeded from scratch, so no test
can see another's bookings and the seed path itself is exercised on each run.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accounts  # noqa: E402
import db as database  # noqa: E402
import seed  # noqa: E402
from app import create_app  # noqa: E402

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Jetage1965!"


@pytest.fixture
def db_path(tmp_path):
    """An empty path for a database that does not exist yet."""
    path = str(tmp_path / "skyway-test.db")
    previous = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = path
    yield path
    if previous is None:
        os.environ.pop("DATABASE_PATH", None)
    else:
        os.environ["DATABASE_PATH"] = previous


@pytest.fixture
def app(db_path):
    """A Flask app whose create_app() builds and seeds the schema on the way up."""
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def conn(db_path, app):
    """A direct connection to the same database the app is using."""
    connection = database.connect(db_path)
    yield connection
    connection.close()


@pytest.fixture
def csrf(client):
    """The session's CSRF token, read from a rendered form.

    Defaults to /lookup because it renders a form whether or not anyone is
    signed in — /login and /register redirect away once you have a session, and
    a page that redirects has no token on it to read.
    """
    def token(path="/lookup"):
        page = client.get(path, follow_redirects=True).get_data(as_text=True)
        marker = 'name="csrf_token" value="'
        if marker not in page:                       # that page had no form
            page = client.get("/lookup").get_data(as_text=True)
        start = page.index(marker) + len(marker)
        return page[start:page.index('"', start)]
    return token


@pytest.fixture
def register(client, csrf):
    """Create an account and return the response."""
    def _register(username="flyer", email=None, password="Jetage1965!", **extra):
        payload = {
            "csrf_token": csrf("/register"),
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
            "confirm": extra.pop("confirm", password),
        }
        payload.update(extra)
        return client.post("/register", data=payload, follow_redirects=False)
    return _register


@pytest.fixture
def login(client, csrf):
    """Sign in as an existing account."""
    def _login(username=DEMO_USERNAME, password=DEMO_PASSWORD, **extra):
        payload = {"csrf_token": csrf("/login"), "username": username, "password": password}
        payload.update(extra)
        return client.post("/login", data=payload, follow_redirects=False)
    return _login


@pytest.fixture
def free_seat(conn):
    """The first bookable seat on a flight, with its flight id."""
    def _seat(flight_id=1):
        seat = next(s for s in database.get_seats(conn, flight_id) if s["available"])
        return flight_id, seat
    return _seat


@pytest.fixture
def book(client, csrf, free_seat):
    """Run the confirm step for a seat, as a signed-in user would."""
    def _book(flight_id=None, seat=None, **overrides):
        if seat is None:
            flight_id, seat = free_seat(flight_id or 1)
        form = {
            "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
            "flight_id": flight_id,
            "seat_id": seat["id"],
            "full_name": "Jimmy Ngo",
            "email": "jimmy@example.com",
            "phone": "+1 555 0142",
        }
        form.update(overrides)
        return client.post("/bookings", data=form, follow_redirects=False)
    return _book


@pytest.fixture
def seeded_users():
    return {"username": DEMO_USERNAME, "password": DEMO_PASSWORD}


@pytest.fixture
def accounts_module():
    return accounts


@pytest.fixture
def seed_module():
    return seed
