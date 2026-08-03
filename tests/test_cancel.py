"""Cancelling from My Trips, and who is allowed to."""

import db as database


def _reference(response):
    return response.headers["Location"].rsplit("/", 1)[-1]


def test_my_trips_offers_a_cancel_button_for_live_bookings(client, register, book):
    register(username="canceller")
    reference = _reference(book())

    body = client.get("/my-trips").get_data(as_text=True)
    assert f"/bookings/{reference}/cancel" in body
    assert "Cancel booking" in body


def test_cancelling_from_my_trips_returns_there(client, csrf, register, book):
    register(username="roundtrip")
    reference = _reference(book())

    response = client.post(f"/bookings/{reference}/cancel", data={
        "csrf_token": csrf("/my-trips"), "next": "/my-trips"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/my-trips")


def test_cancelling_releases_the_seat(client, conn, csrf, register, book, free_seat):
    register(username="releaser")
    flight_id, seat = free_seat(1)
    reference = _reference(book(flight_id=flight_id, seat=seat))

    booked = database.get_seats(conn, flight_id)
    assert not next(s for s in booked if s["id"] == seat["id"])["available"]

    client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})

    freed = database.get_seats(conn, flight_id)
    assert next(s for s in freed if s["id"] == seat["id"])["available"]


def test_a_cancelled_booking_shows_as_void_and_loses_its_button(
        client, csrf, register, book):
    register(username="voided")
    reference = _reference(book())
    client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})

    body = client.get("/my-trips").get_data(as_text=True)
    assert "Cancelled" in body
    assert f"/bookings/{reference}/cancel" not in body


def test_cancelling_twice_is_reported_not_repeated(client, csrf, register, book):
    register(username="twice")
    reference = _reference(book())

    first = client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})
    assert first.status_code == 302

    second = client.post(f"/bookings/{reference}/cancel",
                         data={"csrf_token": csrf()}, follow_redirects=True)
    assert "already cancelled" in second.get_data(as_text=True)


def test_you_cannot_cancel_someone_elses_booking(client, conn, csrf, register, book):
    """The reference is enough to look a booking up, but not to cancel a trip
    that belongs to another account."""
    register(username="owner")
    reference = _reference(book())
    client.post("/logout", data={"csrf_token": csrf()})

    register(username="stranger")
    response = client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})
    assert response.status_code == 403

    assert database.get_booking_by_reference(conn, reference)["status"] == "CONFIRMED"


def test_a_signed_out_visitor_cannot_cancel_an_account_booking(client, conn, csrf,
                                                               register, book):
    register(username="protected")
    reference = _reference(book())
    client.post("/logout", data={"csrf_token": csrf()})

    response = client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})
    assert response.status_code == 403
    assert database.get_booking_by_reference(conn, reference)["status"] == "CONFIRMED"


def test_cancel_is_csrf_protected(client, conn, register, book):
    register(username="forgery")
    reference = _reference(book())

    assert client.post(f"/bookings/{reference}/cancel").status_code == 400
    assert database.get_booking_by_reference(conn, reference)["status"] == "CONFIRMED"


def test_cancelling_an_unknown_reference_is_a_404(client, csrf, register):
    register(username="ghost")
    assert client.post("/bookings/NOPE01/cancel",
                       data={"csrf_token": csrf()}).status_code == 404


def test_the_next_target_cannot_be_sent_off_site(client, csrf, register, book):
    """safe_next only accepts same-site paths, so a cancel link cannot be used
    as an open redirect."""
    register(username="offsite")
    reference = _reference(book())

    response = client.post(f"/bookings/{reference}/cancel", data={
        "csrf_token": csrf(), "next": "https://example.com/evil"})
    assert "example.com" not in response.headers["Location"]
