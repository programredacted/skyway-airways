"""The pre-sold list is capped by default, and the cap can be lifted.

A cap that cannot be lifted hides rows while looking complete, so what matters
is that ?seeded=all really returns every one -- counted against the database,
not against a number the page prints about itself.
"""

import re

import accounts

ADMIN = ("admin", "Concorde001!")


def _panel(client, csrf, login, query=""):
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)
    return client.get("/admin" + query).get_data(as_text=True)


def _seeded_rows(body):
    """Booking rows below the pre-sold heading, so account and ghost rows
    higher up the page are not counted with them."""
    tail = body.split('id="pre-sold"', 1)[-1]
    return re.findall(r'id="booking-\w+"', tail)


def test_the_list_is_capped_by_default(client, csrf, login):
    rows = _seeded_rows(_panel(client, csrf, login))
    assert len(rows) == accounts.SEEDED_SHOWN


def test_asking_for_all_returns_every_pre_sold_seat(client, csrf, login, conn):
    expected = conn.execute(
        """SELECT COUNT(*) FROM bookings
           WHERE user_id IS NULL AND former_username IS NULL"""
    ).fetchone()[0]
    assert expected > accounts.SEEDED_SHOWN, "seed no longer exceeds the cap"

    rows = _seeded_rows(_panel(client, csrf, login, "?seeded=all"))
    assert len(rows) == expected


def test_each_view_offers_the_other(client, csrf, login):
    capped = _panel(client, csrf, login)
    assert "seeded=all" in capped, "no way to see the rest"

    every = _panel(client, csrf, login, "?seeded=all")
    assert "Showing every one" in every
    assert 'href="/admin#pre-sold"' in every, "no way back to the short list"


def test_an_unknown_value_leaves_the_cap_alone(client, csrf, login):
    """Only 'all' lifts it -- a stray query string should not change the page."""
    rows = _seeded_rows(_panel(client, csrf, login, "?seeded=yes"))
    assert len(rows) == accounts.SEEDED_SHOWN
