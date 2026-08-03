"""Criteria 2-5, 10 and 12: the booking flow, the seat race, and validation."""

import sqlite3
import threading

import bookings
import db as database
import pricing


def _booking(conn, reference):
    return conn.execute(
        "SELECT * FROM bookings WHERE reference = ?", (reference,)
    ).fetchone()


def _reference_from(response):
    return response.headers["Location"].rsplit("/", 1)[-1]


def test_register_login_pick_seat_confirm_writes_the_right_row(client, conn, register, book):
    """Criterion 2: the whole happy path, end to end."""
    register(username="newflyer")

    flight_id, seat = 1, next(s for s in database.get_seats(conn, 1) if s["available"])
    assert client.get(f"/flights/{flight_id}").status_code == 200
    assert client.get(f"/flights/{flight_id}/seats").status_code == 200

    response = book(flight_id=flight_id, seat=seat)
    assert response.status_code == 302

    row = _booking(conn, _reference_from(response))
    user = conn.execute("SELECT id FROM users WHERE username = 'newflyer'").fetchone()

    assert row["user_id"] == user["id"]
    assert row["flight_id"] == flight_id
    assert row["seat_id"] == seat["id"]
    assert row["status"] == "CONFIRMED"

    # price paid == base fare x the cabin's multiplier
    flight = database.get_flight(conn, flight_id)
    expected = round(flight["base_fare_cents"]
                     * pricing.CLASS_MULTIPLIERS[seat["cabin_class"]] / 100) * 100
    assert row["price_paid_cents"] == expected == seat["price_cents"]


def test_the_booking_appears_on_its_boarding_pass(client, register, book):
    register(username="passholder")
    reference = _reference_from(book())
    body = client.get(f"/bookings/{reference}").get_data(as_text=True)
    assert reference in body
    assert "Jimmy Ngo" in body


def test_a_sold_seat_cannot_be_booked_even_if_the_client_submits_it(
        client, conn, register, book, free_seat):
    """Criterion 3: the server refuses, not the browser."""
    register(username="firstbuyer")
    flight_id, seat = free_seat(1)
    book(flight_id=flight_id, seat=seat)

    holds = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE seat_id = ? AND status = 'CONFIRMED'",
        (seat["id"],),
    ).fetchone()[0]
    assert holds == 1

    # Someone else submits the same seat id directly.
    client.post("/logout", data={"csrf_token": _token(client)})
    register(username="secondbuyer", email="second@example.com")

    response = book(flight_id=flight_id, seat=seat, full_name="Seat Thief",
                    email="thief@example.com")
    assert response.status_code == 302

    holds_after = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE seat_id = ? AND status = 'CONFIRMED'",
        (seat["id"],),
    ).fetchone()[0]
    assert holds_after == 1


def _token(client, path="/lookup"):
    page = client.get(path).get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = page.index(marker) + len(marker)
    return page[start:page.index('"', start)]


def test_two_overlapping_attempts_on_one_seat_leave_exactly_one_booking(conn, db_path):
    """Criterion 4: the partial unique index decides the race, not the app."""
    seat = next(s for s in database.get_seats(conn, 1) if s["available"])

    start = threading.Barrier(8)
    outcomes = []
    lock = threading.Lock()

    def attempt(index):
        own = database.connect(db_path)
        start.wait()
        try:
            bookings.create_booking(own, seat["id"], f"Racer {index}",
                                    f"racer{index}@example.com")
            result = "booked"
        except bookings.SeatUnavailable:
            result = "refused"
        except sqlite3.OperationalError as error:
            result = f"locked: {error}"
        finally:
            own.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("booked") == 1, outcomes
    assert not [o for o in outcomes if o.startswith("locked")], outcomes

    confirmed = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE seat_id = ? AND status = 'CONFIRMED'",
        (seat["id"],),
    ).fetchone()[0]
    assert confirmed == 1


def test_resubmitting_the_confirm_step_creates_no_duplicate(client, conn, register, book, free_seat):
    """Criterion 5."""
    register(username="doubleclicker")
    flight_id, seat = free_seat(1)
    before = database.count_rows(conn, "bookings")

    first = book(flight_id=flight_id, seat=seat)
    second = book(flight_id=flight_id, seat=seat)

    assert first.headers["Location"] == second.headers["Location"]
    assert database.count_rows(conn, "bookings") - before == 1


def test_refreshing_the_boarding_pass_creates_nothing(client, conn, register, book):
    register(username="refresher")
    reference = _reference_from(book())
    before = database.count_rows(conn, "bookings")

    for _ in range(3):
        assert client.get(f"/bookings/{reference}").status_code == 200

    assert database.count_rows(conn, "bookings") == before


def test_anonymous_booking_redirects_to_login_and_resumes(client, conn, csrf, free_seat, register):
    """Criterion 10: sign in, then land back on the same flight and seat."""
    flight_id, seat = free_seat(1)
    resume = f"/flights/{flight_id}/passenger?seat_id={seat['id']}"
    before = database.count_rows(conn, "bookings")

    response = client.post("/bookings", data={
        "csrf_token": csrf(resume),
        "flight_id": flight_id, "seat_id": seat["id"],
        "full_name": "Jimmy Ngo", "email": "jimmy@example.com",
    })

    from urllib.parse import unquote

    assert response.status_code == 302
    location = unquote(response.headers["Location"])   # next= is percent-encoded
    assert "/login" in location
    assert f"seat_id={seat['id']}" in location
    assert f"/flights/{flight_id}/passenger" in location
    assert database.count_rows(conn, "bookings") == before

    # Registering from that link returns us to the in-progress booking.
    signed_up = client.post(f"/register?next={resume}", data={
        "csrf_token": csrf(), "username": "resumer", "email": "resumer@example.com",
        "password": "Jetage1965!", "confirm": "Jetage1965!",
    })
    assert signed_up.status_code == 302
    assert signed_up.headers["Location"].endswith(resume)

    page = client.get(resume)
    assert page.status_code == 200
    assert f"{seat['row_number']}{seat['seat_letter']}" in page.get_data(as_text=True)


def test_bad_passenger_input_returns_a_friendly_error_not_a_500(
        client, conn, register, csrf, free_seat):
    """Criterion 12."""
    register(username="fumbler")
    flight_id, seat = free_seat(1)
    before = database.count_rows(conn, "bookings")
    resume = f"/flights/{flight_id}/passenger?seat_id={seat['id']}"

    cases = [
        {"full_name": "", "email": ""},
        {"full_name": "J", "email": "j@example.com"},
        {"full_name": "Jimmy Ngo", "email": "not-an-email"},
        {"full_name": "Jimmy Ngo", "email": "j@example.com", "phone": "call me!!"},
        {"full_name": "x" * 200, "email": "j@example.com"},
    ]
    for case in cases:
        form = {"csrf_token": csrf(resume), "flight_id": flight_id, "seat_id": seat["id"]}
        form.update(case)
        response = client.post("/bookings", data=form)
        assert response.status_code == 400, case
        assert "form__error" in response.get_data(as_text=True), case

    assert database.count_rows(conn, "bookings") == before


def test_malformed_forms_never_500(client, register):
    register(username="garbage")
    for form in ({}, {"flight_id": "abc"}, {"flight_id": 1, "seat_id": "xyz"}):
        response = client.post("/bookings", data=form)
        assert response.status_code < 500, form


def test_cancelling_releases_the_seat_and_keeps_history(client, conn, register, book, csrf):
    register(username="canceller")
    reference = _reference_from(book())

    response = client.post(f"/bookings/{reference}/cancel",
                           data={"csrf_token": csrf(f"/bookings/{reference}")})
    assert response.status_code == 302

    row = _booking(conn, reference)
    assert row["status"] == "CANCELLED"
    assert database.get_seat(conn, row["seat_id"])["available"]
