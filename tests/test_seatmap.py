"""Criterion 14: the cabin shell renders with a working seat grid."""

import db as database
import seatmap


def test_seat_map_page_renders_the_cabin_shell_and_a_seat_grid(client, conn):
    """Criterion 14."""
    page = client.get("/flights/1/seats")
    assert page.status_code == 200

    body = page.get_data(as_text=True)

    # the shell, nose to tail
    for part in ("cabin-shell", "cabin-shell__nose", "cabin-shell__tail",
                 "cabin-shell__divider"):
        assert part in body, part

    # and a real seat grid inside it
    seats = database.get_seats(conn, 1)
    assert body.count('class="seat cabin--') == len(seats)
    assert 'name="seat_id"' in body


def test_seats_are_buttons_so_they_stay_keyboard_reachable(client):
    body = client.get("/flights/1/seats").get_data(as_text=True)
    assert "<button type=\"submit\"" in body
    assert 'aria-pressed="false"' in body


def test_sold_seats_are_disabled_for_a_browser_without_javascript(client, conn):
    body = client.get("/flights/1/seats").get_data(as_text=True)
    sold = [s for s in database.get_seats(conn, 1) if not s["available"]]
    assert body.count("disabled") >= len(sold)


def test_every_cabin_flies_the_full_width_of_the_aircraft(conn):
    """No gaps in this layout: every row seats the aircraft's full letter set,
    so a seat position never renders as empty space a click could land on."""
    aircraft = database.get_aircraft_for_flight(conn, 1)
    width = len(aircraft["seat_letters"])
    for row in seatmap.build_rows(database.get_seats(conn, 1), aircraft):
        assert len(row["seats"]) == width, row["row_number"]
        assert all(cell.get("id") for cell in row["seats"]), row["row_number"]


def test_rows_are_grouped_nose_to_tail_by_cabin(conn):
    aircraft = database.get_aircraft_for_flight(conn, 1)
    rows = seatmap.build_rows(database.get_seats(conn, 1), aircraft)

    assert [row["row_number"] for row in rows] == sorted(r["row_number"] for r in rows)
    seen = []
    for row in rows:
        if row["cabin_class"] not in seen:
            seen.append(row["cabin_class"])
    assert seen == ["FIRST", "BUSINESS", "ECONOMY"]


def test_an_aisle_is_flagged_after_the_right_letters(conn):
    aircraft = database.get_aircraft_for_flight(conn, 1)
    expected = set(aircraft["aisle_after"].split(","))
    row = seatmap.build_rows(database.get_seats(conn, 1), aircraft)[0]
    flagged = {cell["letter"] for cell in row["seats"] if cell["aisle_after"]}
    assert flagged == expected


def test_the_json_seat_api_matches_the_page(client, conn):
    payload = client.get("/api/flights/1/seats").get_json()
    assert payload["total_seats"] == len(database.get_seats(conn, 1))
    for row in payload["rows"]:
        for seat in row["seats"]:
            assert "id" in seat and "price_cents" in seat


def test_seat_map_renders_for_every_aircraft_in_the_fleet(client, conn):
    for flight in database.get_flights(conn):
        response = client.get(f"/flights/{flight['id']}/seats")
        assert response.status_code == 200, flight["flight_number"]
