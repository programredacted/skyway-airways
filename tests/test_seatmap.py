"""Criterion 14: the plane-shaped cabin renders with a working seat grid."""

import db as database
import seatmap


def test_seat_map_page_renders_the_airframe_and_a_seat_grid(client, conn):
    """Criterion 14."""
    page = client.get("/flights/1/seats")
    assert page.status_code == 200

    body = page.get_data(as_text=True)

    # the airframe: nose, fuselage, wings, tail
    for part in ("airframe__nose", "airframe__body", "airframe__wings", "airframe__tail"):
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


def test_premium_cabins_fly_a_narrower_arrangement(conn):
    """First 1-1, Business 2-2, Economy the full width."""
    aircraft = database.get_aircraft_for_flight(conn, 1)
    rows = seatmap.build_rows(database.get_seats(conn, 1), aircraft)

    def seats_in(cabin):
        row = next(r for r in rows if r["cabin_class"] == cabin)
        return sum(1 for cell in row["seats"] if not cell["gap"])

    assert seats_in("FIRST") == len(aircraft["first_letters"])
    assert seats_in("BUSINESS") == len(aircraft["business_letters"])
    assert seats_in("ECONOMY") == len(aircraft["seat_letters"])
    assert seats_in("FIRST") < seats_in("BUSINESS") < seats_in("ECONOMY")


def test_every_row_is_emitted_at_full_width_so_the_cabin_keeps_its_shape(conn):
    aircraft = database.get_aircraft_for_flight(conn, 1)
    width = len(aircraft["seat_letters"])
    for row in seatmap.build_rows(database.get_seats(conn, 1), aircraft):
        assert len(row["seats"]) == width, row["row_number"]


def test_exit_rows_sit_at_the_wings(conn):
    aircraft = database.get_aircraft_for_flight(conn, 1)
    rows = seatmap.exit_rows(aircraft)
    assert len(rows) == 2
    assert rows[1] == rows[0] + 1
    assert aircraft["business_last_row"] < rows[0] <= aircraft["total_rows"]


def test_the_json_seat_api_omits_the_gaps(client, conn):
    payload = client.get("/api/flights/1/seats").get_json()
    assert payload["total_seats"] == len(database.get_seats(conn, 1))
    for row in payload["rows"]:
        for seat in row["seats"]:
            assert "id" in seat and "price_cents" in seat


def test_seat_map_renders_for_every_aircraft_in_the_fleet(client, conn):
    for flight in database.get_flights(conn):
        response = client.get(f"/flights/{flight['id']}/seats")
        assert response.status_code == 200, flight["flight_number"]
