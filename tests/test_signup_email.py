"""The passenger details, carried across the sign-in they were interrupted by.

Typing a name and email, being told to register, and coming back to an empty
form is the friction this removes.
"""


def _start_a_booking(client, csrf, free_seat, email="traveller@example.com",
                     name="Jimmy Ngo", phone="+1 555 0142"):
    """Fill in the passenger form while signed out. The confirm is refused and
    the visitor is sent to sign in."""
    flight_id, seat = free_seat(1)
    response = client.post("/bookings", data={
        "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
        "flight_id": flight_id,
        "seat_id": seat["id"],
        "full_name": name,
        "email": email,
        "phone": phone,
    })
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    return flight_id, seat


def test_the_email_lands_in_the_register_form(client, csrf, free_seat):
    _start_a_booking(client, csrf, free_seat)

    body = client.get("/register").get_data(as_text=True)
    assert 'value="traveller@example.com"' in body
    assert "Carried over from the booking you started" in body


def test_the_details_survive_registering_and_refill_the_form(client, csrf,
                                                             free_seat, register):
    """The whole point: sign_in clears the session to defeat fixation, and the
    draft has to live through that or the form comes back blank."""
    flight_id, seat = _start_a_booking(client, csrf, free_seat)

    assert register(username="returning").status_code == 302     # signs them in

    body = client.get(
        f"/flights/{flight_id}/passenger?seat_id={seat['id']}").get_data(as_text=True)
    assert 'value="Jimmy Ngo"' in body
    assert 'value="traveller@example.com"' in body
    assert 'value="+1 555 0142"' in body


def test_the_details_survive_signing_in_to_an_existing_account(client, csrf,
                                                               free_seat, login):
    flight_id, seat = _start_a_booking(client, csrf, free_seat)
    assert login().status_code == 302

    body = client.get(
        f"/flights/{flight_id}/passenger?seat_id={seat['id']}").get_data(as_text=True)
    assert 'value="Jimmy Ngo"' in body


def test_the_draft_is_dropped_once_the_booking_exists(client, csrf, free_seat,
                                                      register):
    flight_id, seat = _start_a_booking(client, csrf, free_seat)
    register(username="finisher")

    confirmed = client.post("/bookings", data={
        "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
        "flight_id": flight_id, "seat_id": seat["id"],
        "full_name": "Jimmy Ngo", "email": "traveller@example.com",
        "phone": "+1 555 0142",
    })
    assert confirmed.status_code == 302
    assert "/bookings/" in confirmed.headers["Location"]

    # Signing out is what proves it: a signed-in visitor legitimately sees
    # these fields filled from their account, so an empty form only means
    # anything once the account is out of the picture.
    client.post("/logout", data={"csrf_token": csrf()})

    next_flight, next_seat = free_seat(2)
    body = client.get(
        f"/flights/{next_flight}/passenger?seat_id={next_seat['id']}").get_data(as_text=True)
    assert 'value="Jimmy Ngo"' not in body
    assert 'value="traveller@example.com"' not in body


def test_it_never_appears_in_a_url(client, csrf, free_seat):
    """It rides in the session cookie, so it cannot be shared or logged."""
    flight_id, seat = _start_a_booking(client, csrf, free_seat)
    response = client.get("/register")
    assert response.status_code == 200
    assert "traveller" not in response.headers.get("Location", "")


def test_a_visitor_who_typed_nothing_gets_an_empty_field(client, csrf, free_seat):
    _start_a_booking(client, csrf, free_seat, email="", name="", phone="")
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
