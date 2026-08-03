"""Criteria 6-9 and 11: accounts, hashing, and that they survive the process."""

from werkzeug.security import check_password_hash

import accounts
import db as database
import seed
from app import create_app


def _user(conn, username):
    return conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)
    ).fetchone()


def test_registering_stores_a_hash_and_never_the_password(conn, register):
    """Criterion 6."""
    password = "Jetage1965!"
    assert register(username="hashme", password=password).status_code == 302

    row = _user(conn, "hashme")
    assert row is not None
    assert row["password_hash"] != password
    assert password not in row["password_hash"]
    assert check_password_hash(row["password_hash"], password)
    assert not check_password_hash(row["password_hash"], "wrong-password")

    # and the plaintext is nowhere else in the row either
    assert password not in " ".join(str(value) for value in tuple(row))


def test_login_survives_logout_and_a_fresh_app_instance(client, conn, db_path, csrf, register):
    """Criterion 7: persistence is in the database, not the session."""
    register(username="persist", password="Jetage1965!")

    assert client.post("/logout", data={"csrf_token": csrf("/flights")}).status_code == 302
    assert client.get("/my-trips").status_code == 302   # signed out again

    signed_in = client.post("/login", data={
        "csrf_token": csrf("/login"), "username": "persist", "password": "Jetage1965!"})
    assert signed_in.status_code == 302

    # A brand new app object, pointed at the same file, still knows the account.
    other = create_app().test_client()
    page = other.get("/login").get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = page.index(marker) + len(marker)
    token = page[start:page.index('"', start)]

    again = other.post("/login", data={
        "csrf_token": token, "username": "persist", "password": "Jetage1965!"})
    assert again.status_code == 302
    assert other.get("/my-trips").status_code == 200


def test_seeded_demo_account_can_sign_in(client, login):
    assert login().status_code == 302
    assert client.get("/my-trips").status_code == 200


def test_wrong_password_and_unknown_user_give_the_same_generic_error(client, csrf, register):
    """Criterion 8."""
    register(username="known", password="Jetage1965!")
    client.post("/logout", data={"csrf_token": csrf("/flights")})

    wrong = client.post("/login", data={
        "csrf_token": csrf("/login"), "username": "known", "password": "not-it"})
    missing = client.post("/login", data={
        "csrf_token": csrf("/login"), "username": "nobody", "password": "not-it"})

    assert wrong.status_code == missing.status_code == 400
    message = "Invalid username or password."
    assert message in wrong.get_data(as_text=True)
    assert message in missing.get_data(as_text=True)
    # nothing may hint at which half was wrong
    for body in (wrong.get_data(as_text=True), missing.get_data(as_text=True)):
        assert "no such user" not in body.lower()
        assert "incorrect password" not in body.lower()


def test_duplicate_username_or_email_is_rejected(client, conn, csrf, register):
    """Criterion 9."""
    assert register(username="taken", email="taken@example.com").status_code == 302
    # Registering signs you in, and /register redirects a signed-in visitor.
    client.post("/logout", data={"csrf_token": csrf()})

    clash_name = register(username="TAKEN", email="other@example.com")
    assert clash_name.status_code == 400
    assert "already registered" in clash_name.get_data(as_text=True)

    clash_email = register(username="different", email="TAKEN@example.com")
    assert clash_email.status_code == 400
    assert "already registered" in clash_email.get_data(as_text=True)

    # only "taken" got in; counted off the seed so adding a demo account to
    # the fleet does not break this test
    assert database.count_rows(conn, "users") == len(seed.DEMO_USERS) + 1


def test_registration_validation(register):
    assert register(username="ab").status_code == 400              # too short
    assert register(username="has space").status_code == 400       # not alphanumeric
    assert register(username="shortpw", password="abc").status_code == 400
    assert register(username="mismatch", confirm="different").status_code == 400
    assert register(username="bademail", email="nope").status_code == 400


def test_my_trips_requires_login_and_shows_only_your_own(
        client, conn, csrf, register, book, free_seat):
    """Criterion 11."""
    assert client.get("/my-trips").status_code == 302

    register(username="alice")
    alice_reference = book()[1] if False else \
        book().headers["Location"].rsplit("/", 1)[-1]
    page = client.get("/my-trips")
    assert page.status_code == 200
    assert alice_reference in page.get_data(as_text=True)

    client.post("/logout", data={"csrf_token": csrf("/flights")})
    register(username="bob", email="bob@example.com")
    bob_page = client.get("/my-trips").get_data(as_text=True)

    assert alice_reference not in bob_page
    assert "No trips yet" in bob_page


def test_authenticate_is_case_insensitive_on_username(conn):
    accounts.register(conn, {"username": "MixedCase", "email": "mixed@example.com",
                             "password": "Jetage1965!", "confirm": "Jetage1965!"})
    assert accounts.authenticate(conn, "mixedcase", "Jetage1965!") is not None
    assert accounts.authenticate(conn, "MIXEDCASE", "Jetage1965!") is not None
    assert accounts.authenticate(conn, "mixedcase", "nope") is None


def test_forms_are_csrf_protected(client, register):
    """A POST without the session's token is refused."""
    register(username="csrfuser")
    assert client.post("/logout", data={}).status_code == 400
    assert client.post("/login", data={"username": "a", "password": "b"}).status_code == 400
    assert client.post("/register", data={"username": "x"}).status_code == 400
    assert client.post("/bookings", data={"flight_id": 1}).status_code == 400


def test_header_reflects_the_session(client, register, csrf):
    anonymous = client.get("/flights").get_data(as_text=True)
    assert "Sign in" in anonymous

    register(username="headercheck")
    signed_in = client.get("/flights").get_data(as_text=True)
    assert "Welcome aboard, headercheck" in signed_in
    assert "My Trips" in signed_in
    assert "Sign out" in signed_in
