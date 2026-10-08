"""The departure board marks flights the signed-in visitor already holds seats on."""

import db as database


def _row(body, flight_number):
    """The board row for one flight, as rendered HTML."""
    marker = f"<span data-flap>{flight_number}</span>"
    start = body.rindex('<tr class="board__row"', 0, body.index(marker))
    return body[start:body.index("</tr>", start)]


def test_a_booked_flight_is_marked_on_the_board(client, conn, login, book):
    login()
    assert book(flight_id=1).status_code == 302

    body = client.get("/flights").get_data(as_text=True)
    number = database.get_flight(conn, 1)["flight_number"]
    assert "1 seat booked" in _row(body, number)
    assert body.count("tag--yours") == 1


def test_two_seats_on_one_flight_read_as_two(client, conn, login, book):
    login()
    book(flight_id=1)
    book(flight_id=1)

    body = client.get("/flights").get_data(as_text=True)
    number = database.get_flight(conn, 1)["flight_number"]
    assert "2 seats booked" in _row(body, number)


def test_nobody_else_sees_your_mark(client, login, book, csrf):
    login()
    book(flight_id=1)
    client.post("/logout", data={"csrf_token": csrf()})

    assert "tag--yours" not in client.get("/flights").get_data(as_text=True)


def test_a_cancelled_booking_is_not_marked(client, login, book, csrf):
    login()
    reference = book(flight_id=1).headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})

    assert "tag--yours" not in client.get("/flights").get_data(as_text=True)


def test_the_board_still_has_one_row_per_flight_when_signed_in(client, conn, login, book):
    login()
    book(flight_id=1)
    body = client.get("/flights").get_data(as_text=True)
    assert body.count('class="board__row"') == database.count_rows(conn, "flights")
