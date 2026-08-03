"""Every flight named in the staff panel is a way through to that flight.

All three booking lists share one query and one macro, so a change that drops
flight_id breaks them together -- hence the seeded list is checked too, not
just the one booking a test can easily make.
"""

import re

ADMIN = ("admin", "Concorde001!")


def _admin_panel(client, csrf, login):
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)
    return client.get("/admin").get_data(as_text=True)


def test_a_booking_links_to_its_own_flight(client, csrf, login, book, free_seat):
    login()
    flight_id, seat = free_seat(1)
    reference = book(flight_id, seat).headers["Location"].rsplit("/", 1)[-1]

    body = _admin_panel(client, csrf, login)

    row = re.search(rf'id="booking-{reference}".*?</tr>', body, re.S)
    assert row, "the booking is not on the panel"

    link = re.search(r'href="/flights/(\d+)"', row.group(0))
    assert link, "no flight link in the booking row"
    assert int(link.group(1)) == flight_id


def test_the_link_actually_opens_that_flight(client, csrf, login, book, free_seat):
    login()
    flight_id, seat = free_seat(2)
    book(flight_id, seat)

    body = _admin_panel(client, csrf, login)
    target = re.search(r'href="(/flights/\d+)"', body).group(1)

    response = client.get(target)
    assert response.status_code == 200
    assert "Choose your seat" in response.get_data(as_text=True)


def test_every_seeded_booking_is_linked_too(client, csrf, login):
    """The seeded list holds hundreds of rows and no test books into it, so
    a missing flight_id would surface here first -- as a url_for failure."""
    body = _admin_panel(client, csrf, login)

    rows = re.findall(r'id="booking-\w+".*?</tr>', body, re.S)
    assert len(rows) > 10, "expected the seeded bookings to be listed"

    unlinked = [r for r in rows if not re.search(r'href="/flights/\d+"', r)]
    assert not unlinked, f"{len(unlinked)} booking rows have no flight link"
