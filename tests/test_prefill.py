"""Booking while signed in should not mean typing what the account knows."""


def _form(client, free_seat, flight_id=1):
    flight_id, seat = free_seat(flight_id)
    return client.get(
        f"/flights/{flight_id}/passenger?seat_id={seat['id']}").get_data(as_text=True)


def test_a_signed_in_visitor_gets_their_email_filled_in(client, register, free_seat):
    register(username="known", email="known@example.com")
    body = _form(client, free_seat)

    assert 'value="known@example.com"' in body
    assert "Filled in from your account" in body


def test_a_signed_out_visitor_gets_an_empty_form(client, free_seat):
    body = _form(client, free_seat)
    assert 'id="email" name="email" value=""' in body
    assert "Filled in from your account" not in body


def test_the_name_comes_from_the_last_trip_they_took(client, register, book,
                                                     free_seat):
    """An account holds a username and an email, never a passenger name — so
    the only place a returning traveller's name exists is their last booking."""
    register(username="returner", email="returner@example.com")
    book()                       # books as "Jimmy Ngo", phone +1 555 0142

    body = _form(client, free_seat, flight_id=2)
    assert 'value="Jimmy Ngo"' in body
    assert 'value="+1 555 0142"' in body
    assert 'value="returner@example.com"' in body      # the account, not the trip


def test_a_missing_phone_leaves_the_field_empty(client, conn, csrf, register,
                                                free_seat):
    """Phone is optional, so it is NULL on the passenger row. An `or` chain
    hands that back as None, which Jinja prints into the box as the word None
    for the visitor to delete before they can type."""
    register(username="nophone", email="nophone@example.com")

    flight_id, seat = free_seat(1)
    client.post("/bookings", data={
        "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
        "flight_id": flight_id, "seat_id": seat["id"],
        "full_name": "Jimmy Ngo", "email": "nophone@example.com", "phone": "",
    })

    body = _form(client, free_seat, flight_id=2)
    assert 'value="None"' not in body
    assert "None" not in body.split('id="phone"')[1].split(">")[0]
    assert 'value="Jimmy Ngo"' in body          # the rest still fills


def test_no_field_ever_renders_the_word_none(client, register, free_seat):
    register(username="cleanfields")
    body = _form(client, free_seat)
    assert 'value="None"' not in body


def test_a_first_booking_fills_only_what_is_known(client, register, free_seat):
    register(username="firsttimer", email="firsttimer@example.com")
    body = _form(client, free_seat)

    assert 'value="firsttimer@example.com"' in body
    assert 'id="full_name" name="full_name" maxlength="80"\n           value=""' in body \
        or 'value=""' in body                          # no name to offer yet


def test_an_interrupted_booking_still_wins_over_the_account(client, csrf, register,
                                                            free_seat):
    """What they typed a moment ago beats what the account remembers."""
    flight_id, seat = free_seat(1)
    client.post("/bookings", data={
        "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
        "flight_id": flight_id, "seat_id": seat["id"],
        "full_name": "Someone Else", "email": "typed@example.com",
        "phone": "+44 20 7946 0000",
    })
    register(username="overridden", email="account@example.com")

    body = client.get(
        f"/flights/{flight_id}/passenger?seat_id={seat['id']}").get_data(as_text=True)
    assert 'value="Someone Else"' in body
    assert 'value="typed@example.com"' in body
    assert "account@example.com" not in body


def test_the_fields_stay_editable_so_you_can_book_for_someone_else(client, conn,
                                                                   register, csrf,
                                                                   free_seat):
    register(username="booker", email="booker@example.com")
    flight_id, seat = free_seat(1)

    response = client.post("/bookings", data={
        "csrf_token": csrf(f"/flights/{flight_id}/passenger?seat_id={seat['id']}"),
        "flight_id": flight_id, "seat_id": seat["id"],
        "full_name": "Someone Else", "email": "guest@example.com", "phone": "",
    })
    assert response.status_code == 302

    reference = response.headers["Location"].rsplit("/", 1)[-1]
    row = conn.execute(
        """SELECT p.full_name, p.email FROM bookings b
           JOIN passengers p ON p.id = b.passenger_id WHERE b.reference = ?""",
        (reference,)).fetchone()
    assert row["full_name"] == "Someone Else"
    assert row["email"] == "guest@example.com"
