"""Smoke tests. Standard library only: `py -m unittest discover tests`

Each test class builds a throwaway database, so nothing here touches the
flights.db used for the demo.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bookings  # noqa: E402
import db  # noqa: E402
import routemap  # noqa: E402
import seed  # noqa: E402


def fresh_database():
    """A seeded database in a brand-new file, as a fresh deploy would build."""
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    os.remove(path)  # let sqlite create it, so we exercise the real first-run path

    os.environ["DATABASE_PATH"] = path
    connection = db.connect(path)
    db.init_db(connection)
    seed.seed_if_empty(connection)
    return connection, path


def remove_database(path):
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)


class SeedTests(unittest.TestCase):

    def setUp(self):
        self.connection, self.path = fresh_database()

    def tearDown(self):
        self.connection.close()
        remove_database(self.path)

    def test_seeds_more_than_twelve_flights(self):
        self.assertGreaterEqual(db.count_rows(self.connection, "flights"), 12)

    def test_every_flight_has_seats_in_all_three_cabins(self):
        for flight in db.get_flights(self.connection):
            cabins = {row["cabin_class"] for row in db.get_cabin_summary(self.connection, flight["id"])}
            self.assertEqual(cabins, {"FIRST", "BUSINESS", "ECONOMY"}, flight["flight_number"])

    def test_seeding_twice_changes_nothing(self):
        before = [db.count_rows(self.connection, t) for t in ("flights", "seats", "bookings")]
        self.assertFalse(seed.seed_if_empty(self.connection))
        after = [db.count_rows(self.connection, t) for t in ("flights", "seats", "bookings")]
        self.assertEqual(before, after)

    def test_cabin_prices_follow_the_class_multipliers(self):
        from pricing import CLASS_MULTIPLIERS

        flight = db.get_flight(self.connection, 1)
        for cabin in db.get_cabin_summary(self.connection, 1):
            expected = round(flight["base_fare_cents"] * CLASS_MULTIPLIERS[cabin["cabin_class"]] / 100) * 100
            self.assertEqual(cabin["price_cents"], expected, cabin["cabin_class"])

    def test_some_seats_are_pre_sold_so_the_map_looks_used(self):
        self.assertGreater(db.count_rows(self.connection, "bookings"), 0)
        busiest = min(db.get_flights(self.connection), key=lambda f: f["seats_available"])
        self.assertLess(busiest["seats_available"], busiest["total_seats"] * 0.3)


class RouteMapTests(unittest.TestCase):
    """The map is projected server-side, so its geometry is testable."""

    def setUp(self):
        self.connection, self.path = fresh_database()
        self.built = routemap.build(db.get_routes(self.connection))

    def tearDown(self):
        self.connection.close()
        remove_database(self.path)

    def test_every_airport_has_coordinates(self):
        for airport in db.get_airports(self.connection):
            self.assertTrue(-90 <= airport["latitude"] <= 90, airport["code"])
            self.assertTrue(-180 <= airport["longitude"] <= 180, airport["code"])

    def test_projection_places_the_origin_at_the_centre(self):
        self.assertEqual(routemap.project(0, 0),
                         (routemap.MAP_WIDTH / 2, routemap.MAP_HEIGHT / 2))

    def test_pacific_routes_are_split_at_the_antimeridian(self):
        # LAX to Sydney spans 269 degrees; drawn naively it would stripe backwards.
        self.assertEqual(len(routemap.arc_paths(33.94, -118.41, -33.94, 151.18)), 2)
        self.assertEqual(len(routemap.arc_paths(40.64, -73.78, 51.47, -0.45)), 1)

    def test_outbound_and_return_do_not_share_a_path(self):
        out = routemap.arc_paths(40.64, -73.78, 51.47, -0.45)
        back = routemap.arc_paths(51.47, -0.45, 40.64, -73.78)
        self.assertNotEqual(out[0], back[0])

    def test_labels_never_collide(self):
        boxes = [routemap._label_box(a["label_x"], a["label_y"], a["label_anchor"],
                                     len(a["code"])) for a in self.built["airports"]]
        for first in range(len(boxes)):
            for second in range(first + 1, len(boxes)):
                self.assertFalse(routemap._overlaps(boxes[first], boxes[second]))

    def test_every_flight_is_drawn(self):
        self.assertEqual(len(self.built["arcs"]),
                         db.count_rows(self.connection, "flights"))


class BookingTests(unittest.TestCase):

    def setUp(self):
        self.connection, self.path = fresh_database()
        self.seat = next(s for s in db.get_seats(self.connection, 1) if s["available"])

    def tearDown(self):
        self.connection.close()
        remove_database(self.path)

    def test_booking_persists_and_can_be_retrieved(self):
        reference = bookings.create_booking(self.connection, self.seat["id"],
                                            "Jimmy Ngo", "jimmy@example.com")
        booking = db.get_booking_by_reference(self.connection, reference)
        self.assertEqual(booking["full_name"], "Jimmy Ngo")
        self.assertEqual(booking["price_paid_cents"], self.seat["price_cents"])

    def test_reference_lookup_is_case_insensitive(self):
        reference = bookings.create_booking(self.connection, self.seat["id"], "A B", "a@b.co")
        self.assertIsNotNone(db.get_booking_by_reference(self.connection, reference.lower()))

    def test_booked_seat_becomes_unavailable(self):
        bookings.create_booking(self.connection, self.seat["id"], "A B", "a@b.co")
        self.assertFalse(db.get_seat(self.connection, self.seat["id"])["available"])

    def test_second_booking_of_the_same_seat_is_refused(self):
        bookings.create_booking(self.connection, self.seat["id"], "First", "first@example.com")
        with self.assertRaises(bookings.SeatUnavailable):
            bookings.create_booking(self.connection, self.seat["id"], "Second", "second@example.com")

    def test_refused_booking_leaves_no_orphan_passenger(self):
        bookings.create_booking(self.connection, self.seat["id"], "First", "first@example.com")
        before = db.count_rows(self.connection, "passengers")
        with self.assertRaises(bookings.SeatUnavailable):
            bookings.create_booking(self.connection, self.seat["id"], "Second", "second@example.com")
        self.assertEqual(db.count_rows(self.connection, "passengers"), before)

    def test_cancelling_releases_the_seat_but_keeps_history(self):
        reference = bookings.create_booking(self.connection, self.seat["id"], "A B", "a@b.co")
        self.assertTrue(bookings.cancel_booking(self.connection, reference))
        self.assertTrue(db.get_seat(self.connection, self.seat["id"])["available"])
        self.assertEqual(db.get_booking_by_reference(self.connection, reference)["status"], "CANCELLED")
        bookings.create_booking(self.connection, self.seat["id"], "C D", "c@d.co")  # resold


class RouteTests(unittest.TestCase):
    """Every page a demo touches must return 200 on a freshly seeded database."""

    def setUp(self):
        self.connection, self.path = fresh_database()
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.connection.close()
        remove_database(self.path)

    def test_pages_render(self):
        for path in ["/", "/flights", "/flights?origin=JFK", "/flights/1",
                     "/flights/1/seats", "/api/flights/1/seats", "/map",
                     "/api/flights", "/lookup", "/healthz"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_board_refresh_endpoint_matches_the_page(self):
        payload = self.client.get("/api/flights").get_json()
        self.assertEqual(len(payload["flights"]),
                         db.count_rows(self.connection, "flights"))
        self.assertRegex(payload["updated_at"], r"^\d{2}:\d{2}:\d{2}$")

    def test_board_refresh_honours_filters(self):
        filtered = self.client.get("/api/flights?origin=JFK").get_json()
        self.assertEqual(len(filtered["flights"]),
                         len(db.get_flights(self.connection, origin="JFK")))

    def test_board_refresh_reflects_a_new_booking(self):
        before = self.client.get("/api/flights").get_json()["flights"][0]
        seat = next(s for s in db.get_seats(self.connection, before["id"]) if s["available"])
        bookings.create_booking(self.connection, seat["id"], "A B", "a@b.co")
        after = self.client.get("/api/flights").get_json()["flights"][0]
        self.assertEqual(before["seats_available"] - after["seats_available"], 1)

    def test_destination_pages_render(self):
        import destinations

        self.assertEqual(self.client.get("/destinations").status_code, 200)
        for code in destinations.DESTINATIONS:
            with self.subTest(code=code):
                self.assertEqual(self.client.get(f"/destinations/{code}").status_code, 200)
        self.assertEqual(self.client.get("/destinations/ZZZ").status_code, 404)

    def test_every_destination_has_a_poster_and_a_plan(self):
        import destinations

        posters = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "templates", "posters")
        for code, guide in destinations.DESTINATIONS.items():
            with self.subTest(code=code):
                # Each city draws its own landmark, not a shared shape.
                self.assertTrue(os.path.exists(os.path.join(posters, f"{code.lower()}.html")),
                                f"no poster artwork for {code}")
                self.assertEqual(len(guide["palette"]), 3)
                self.assertGreaterEqual(len(guide["things"]), 3)

    def test_destination_panel_fragment_renders(self):
        import destinations

        for code in destinations.DESTINATIONS:
            with self.subTest(code=code):
                response = self.client.get(f"/destinations/{code}/panel")
                self.assertEqual(response.status_code, 200)
                self.assertIn("itinerary__item", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/destinations/ZZZ/panel").status_code, 404)

    def test_every_airport_we_fly_to_has_a_guide(self):
        import destinations

        for airport in db.get_airports(self.connection):
            with self.subTest(code=airport["code"]):
                self.assertIsNotNone(destinations.get(airport["code"]))

    def test_map_page_draws_every_route(self):
        page = self.client.get("/map").get_data(as_text=True)
        self.assertEqual(page.count('class="arc '),
                         db.count_rows(self.connection, "flights"))

    def test_unknown_flight_and_booking_are_404(self):
        self.assertEqual(self.client.get("/flights/9999").status_code, 404)
        self.assertEqual(self.client.get("/bookings/NOSUCH").status_code, 404)

    def test_seat_api_reports_live_availability(self):
        payload = self.client.get("/api/flights/1/seats").get_json()
        self.assertGreater(payload["total_seats"], 0)
        self.assertEqual(
            payload["seats_available"],
            sum(1 for row in payload["rows"] for seat in row["seats"] if seat["available"]),
        )

    def test_full_booking_flow_through_the_app(self):
        seat = next(s for s in db.get_seats(self.connection, 1) if s["available"])
        response = self.client.post("/bookings", data={
            "flight_id": 1, "seat_id": seat["id"],
            "full_name": "Jimmy Ngo", "email": "jimmy@example.com",
        })
        self.assertEqual(response.status_code, 302)
        reference = response.headers["Location"].rsplit("/", 1)[-1]
        self.assertIn(reference, self.client.get(f"/bookings/{reference}").get_data(as_text=True))

    def test_invalid_details_are_rejected_without_writing(self):
        seat = next(s for s in db.get_seats(self.connection, 1) if s["available"])
        before = db.count_rows(self.connection, "bookings")
        response = self.client.post("/bookings", data={
            "flight_id": 1, "seat_id": seat["id"], "full_name": "", "email": "nope",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(db.count_rows(self.connection, "bookings"), before)

    def test_resubmitting_does_not_create_a_second_booking(self):
        seat = next(s for s in db.get_seats(self.connection, 1) if s["available"])
        form = {"flight_id": 1, "seat_id": seat["id"],
                "full_name": "Jimmy Ngo", "email": "jimmy@example.com"}
        before = db.count_rows(self.connection, "bookings")
        first = self.client.post("/bookings", data=form)
        second = self.client.post("/bookings", data=form)
        self.assertEqual(first.headers["Location"], second.headers["Location"])
        self.assertEqual(db.count_rows(self.connection, "bookings") - before, 1)


class FreshDeployTests(unittest.TestCase):
    """Render's disk is ephemeral: every deploy starts with no database file."""

    def test_create_app_builds_and_seeds_from_nothing(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.remove(path)
        self.assertFalse(os.path.exists(path))

        os.environ["DATABASE_PATH"] = path
        try:
            from app import create_app

            client = create_app().test_client()
            self.assertTrue(os.path.exists(path))
            self.assertEqual(client.get("/healthz").status_code, 200)

            board = client.get("/flights").get_data(as_text=True)
            self.assertIn("SK 001", board)

            connection = db.connect(path)
            self.assertGreaterEqual(db.count_rows(connection, "flights"), 12)
            connection.close()

            # A restart against the populated file must not seed a second time.
            create_app()
            connection = db.connect(path)
            self.assertGreaterEqual(db.count_rows(connection, "flights"), 12)
            self.assertEqual(db.count_rows(connection, "flights"), len(db.get_flights(connection)))
            connection.close()
        finally:
            remove_database(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
