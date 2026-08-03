"""Criteria 1 and 13: the timetable comes from the database, and seeding is safe
to repeat."""

import db as database
import seed


def test_departures_list_at_least_twelve_seeded_flights(client, conn):
    """Criterion 1."""
    assert database.count_rows(conn, "flights") >= 12

    page = client.get("/flights")
    assert page.status_code == 200

    body = page.get_data(as_text=True)
    rows = body.count('class="board__row"')
    assert rows == database.count_rows(conn, "flights")
    assert rows >= 12


def test_landing_page_and_board_come_from_the_database(client, conn):
    numbers = [row["flight_number"] for row in database.get_flights(conn)]
    body = client.get("/flights").get_data(as_text=True)
    for number in numbers:
        assert number in body


def test_seeding_twice_adds_no_duplicate_flights(conn):
    """Criterion 13."""
    before = [database.count_rows(conn, table)
              for table in ("flights", "seats", "bookings", "airports", "users")]

    assert seed.seed_if_empty(conn) is False

    after = [database.count_rows(conn, table)
             for table in ("flights", "seats", "bookings", "airports", "users")]
    assert before == after

    numbers = [row["flight_number"] for row in database.get_flights(conn)]
    assert len(numbers) == len(set(numbers))


def test_every_flight_has_all_three_cabins(conn):
    for flight in database.get_flights(conn):
        cabins = {row["cabin_class"] for row in database.get_cabin_summary(conn, flight["id"])}
        assert cabins == {"FIRST", "BUSINESS", "ECONOMY"}, flight["flight_number"]


def test_board_filters_by_origin(client, conn):
    from_jfk = database.get_flights(conn, origin="JFK")
    body = client.get("/flights?origin=JFK").get_data(as_text=True)
    assert body.count('class="board__row"') == len(from_jfk)
