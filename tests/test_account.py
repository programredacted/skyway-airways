"""The account page: what it shows, what it deliberately cannot show, and the
password change that stands in for the password it cannot show."""

import html

from werkzeug.security import check_password_hash

import accounts


def _user(conn, username):
    return conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)
    ).fetchone()


def _text(response):
    """Rendered page with entities resolved — Jinja escapes the apostrophes in
    the validation messages, so a raw "don't match" never matches."""
    return html.unescape(response.get_data(as_text=True))


def test_account_page_requires_signing_in(client):
    response = client.get("/account")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_account_page_shows_the_username_and_email(client, register):
    register(username="recordme", email="recordme@example.com")

    body = client.get("/account").get_data(as_text=True)
    assert "recordme" in body
    assert "recordme@example.com" in body


def test_account_page_never_shows_the_password(client, register):
    """The column holds a PBKDF2 hash, so there is nothing to show. The page
    must not leak the hash either — it is still a credential."""
    password = "Jetage1965!"
    register(username="quiet", password=password)

    body = client.get("/account").get_data(as_text=True)
    assert password not in body
    assert "pbkdf2" not in body.lower()
    assert "password_hash" not in body


def test_changing_the_password_replaces_the_hash(client, conn, csrf, register):
    register(username="changer", password="Jetage1965!")
    before = _user(conn, "changer")["password_hash"]

    response = client.post("/account", data={
        "csrf_token": csrf("/account"),
        "current_password": "Jetage1965!",
        "new_password": "Clipper707!",
        "confirm_password": "Clipper707!",
    })
    assert response.status_code == 302

    after = _user(conn, "changer")["password_hash"]
    assert after != before
    assert check_password_hash(after, "Clipper707!")
    assert not check_password_hash(after, "Jetage1965!")


def test_the_new_password_is_the_one_that_signs_you_in(client, csrf, register):
    register(username="rotate", password="Jetage1965!")
    client.post("/account", data={
        "csrf_token": csrf("/account"),
        "current_password": "Jetage1965!",
        "new_password": "Clipper707!",
        "confirm_password": "Clipper707!",
    })
    client.post("/logout", data={"csrf_token": csrf("/flights")})

    stale = client.post("/login", data={
        "csrf_token": csrf("/login"), "username": "rotate", "password": "Jetage1965!"})
    assert stale.status_code == 400

    fresh = client.post("/login", data={
        "csrf_token": csrf("/login"), "username": "rotate", "password": "Clipper707!"})
    assert fresh.status_code == 302


def test_changing_a_password_needs_the_current_one(client, conn, csrf, register):
    """A session left open on a shared machine should not be enough."""
    register(username="guarded", password="Jetage1965!")
    before = _user(conn, "guarded")["password_hash"]

    response = client.post("/account", data={
        "csrf_token": csrf("/account"),
        "current_password": "not-my-password",
        "new_password": "Clipper707!",
        "confirm_password": "Clipper707!",
    })
    assert response.status_code == 400
    assert "isn't your current password" in _text(response)
    assert _user(conn, "guarded")["password_hash"] == before


def test_a_short_or_mismatched_new_password_is_rejected(client, conn, csrf, register):
    register(username="picky", password="Jetage1965!")
    before = _user(conn, "picky")["password_hash"]

    short = client.post("/account", data={
        "csrf_token": csrf("/account"), "current_password": "Jetage1965!",
        "new_password": "short", "confirm_password": "short"})
    assert short.status_code == 400
    assert "At least 8 characters" in _text(short)

    mismatch = client.post("/account", data={
        "csrf_token": csrf("/account"), "current_password": "Jetage1965!",
        "new_password": "Clipper707!", "confirm_password": "Clipper747!"})
    assert mismatch.status_code == 400
    assert "don't match" in _text(mismatch)

    assert _user(conn, "picky")["password_hash"] == before


def test_change_password_is_csrf_protected(client, register):
    register(username="forged", password="Jetage1965!")
    response = client.post("/account", data={
        "current_password": "Jetage1965!",
        "new_password": "Clipper707!",
        "confirm_password": "Clipper707!",
    })
    assert response.status_code == 400


def test_password_fields_ship_a_toggle_that_needs_javascript(client):
    """Every password input gets a Show button, and it is hidden until the
    script reveals it — a browser without JavaScript is never offered a
    control that could not work."""
    for path in ("/login", "/register"):
        body = client.get(path).get_data(as_text=True)
        assert 'data-pw-toggle' in body, path
        assert 'js/password.js' in body, path
        # every toggle starts hidden and every one names a real input
        assert body.count("data-pw-toggle") == body.count('type="password"')
        assert body.count("hidden>Show</button>") == body.count("data-pw-toggle")


def test_the_change_password_form_also_carries_toggles(client, register):
    register(username="toggler")
    body = client.get("/account").get_data(as_text=True)
    for field in ("current_password", "new_password", "confirm_password"):
        assert f'data-pw-toggle="{field}"' in body


def test_change_password_rejects_reusing_the_same_password(client, csrf, register):
    register(username="samey", password="Jetage1965!")
    response = client.post("/account", data={
        "csrf_token": csrf("/account"),
        "current_password": "Jetage1965!",
        "new_password": "Jetage1965!",
        "confirm_password": "Jetage1965!",
    })
    assert response.status_code == 400
    assert "already your password" in _text(response)


def test_accounts_module_exposes_no_way_to_read_a_password(conn, register):
    """A guard on the shape of the module, not just this page: nothing here
    should ever return plaintext."""
    register(username="opaque", password="Jetage1965!")
    row = accounts.get_by_id(conn, _user(conn, "opaque")["id"])
    assert "Jetage1965!" not in " ".join(str(value) for value in tuple(row))
