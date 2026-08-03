"""The email typed at the passenger step, carried to the register form."""

from conftest import DEMO_PASSWORD, DEMO_USERNAME  # noqa: F401  (fixtures use them)


def _start_a_booking(client, csrf, free_seat, email="traveller@example.com"):
    """Fill in the passenger form while signed out. The confirm is refused and
    the visitor is sent to sign in."""
    flight_id, seat = free_seat(1)
    response = client.post("/bookings", data={
        "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
        "flight_id": flight_id,
        "seat_id": seat["id"],
        "full_name": "Jimmy Ngo",
        "email": email,
        "phone": "+1 555 0142",
    })
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    return response


def test_the_email_lands_in_the_register_form(client, csrf, free_seat):
    _start_a_booking(client, csrf, free_seat)

    body = client.get("/register").get_data(as_text=True)
    assert 'value="traveller@example.com"' in body
    assert "Carried over from the booking you started" in body


def test_it_is_used_once_and_then_forgotten(client, csrf, free_seat):
    """A one-time convenience, not a stored profile."""
    _start_a_booking(client, csrf, free_seat)

    assert 'value="traveller@example.com"' in client.get("/register").get_data(as_text=True)
    assert 'value="traveller@example.com"' not in client.get("/register").get_data(as_text=True)


def test_it_never_appears_in_a_url(client, csrf, free_seat):
    """It rides in the session cookie, so it cannot be shared or logged."""
    response = _start_a_booking(client, csrf, free_seat)
    assert "traveller" not in response.headers["Location"]
    assert "@" not in response.headers["Location"]


def test_a_visitor_who_typed_nothing_gets_an_empty_field(client, csrf, free_seat):
    _start_a_booking(client, csrf, free_seat, email="")
    body = client.get("/register").get_data(as_text=True)
    assert 'id="email" name="email" value=""' in body
    assert "Carried over" not in body


def test_a_plain_visit_to_register_is_unaffected(client):
    body = client.get("/register").get_data(as_text=True)
    assert 'id="email" name="email" value=""' in body
    assert "Carried over" not in body


def test_the_carried_email_can_still_be_replaced(client, csrf, free_seat, conn):
    _start_a_booking(client, csrf, free_seat)
    response = client.post("/register", data={
        "csrf_token": csrf("/register"),
        "username": "chooser",
        "email": "different@example.com",
        "password": "Jetage1965!",
        "confirm": "Jetage1965!",
    })
    assert response.status_code == 302

    row = conn.execute(
        "SELECT email FROM users WHERE username = 'chooser'").fetchone()
    assert row["email"] == "different@example.com"
