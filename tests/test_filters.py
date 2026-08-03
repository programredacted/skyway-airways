"""The From/To filters, and the Clear control that has to accompany them."""

import re


def test_clear_is_always_rendered_so_the_script_can_reveal_it(client):
    """Built conditionally, it was absent from the page exactly when picking a
    route had just set a filter there was no way to undo."""
    body = client.get("/flights").get_data(as_text=True)
    assert 'id="clear-filters"' in body
    assert re.search(r'id="clear-filters"[^>]*\shidden', body), "should start hidden"


def test_clear_is_showing_when_the_board_arrives_filtered(client):
    body = client.get("/flights?origin=JFK").get_data(as_text=True)
    assert 'id="clear-filters"' in body
    assert not re.search(r'id="clear-filters"[^>]*\shidden', body)


def test_clear_is_a_plain_link_so_it_works_without_javascript(client):
    body = client.get("/flights?origin=JFK").get_data(as_text=True)
    assert re.search(r'<a[^>]*id="clear-filters"[^>]*href="/flights"', body)


def test_a_board_row_carries_both_ends_of_its_route(client):
    """The script reads these to fill the dropdowns."""
    body = client.get("/flights").get_data(as_text=True)
    rows = re.findall(r'<tr class="board__row"[^>]*>', body)
    assert rows
    for row in rows:
        assert "data-origin-code=" in row
        assert "data-dest-code=" in row


def test_every_code_the_rows_offer_is_a_real_dropdown_option(client):
    """setField refuses a code the <select> does not have, so a mismatch would
    silently do nothing rather than fail loudly."""
    body = client.get("/flights").get_data(as_text=True)

    options = set(re.findall(r'<option value="([A-Z]{3})"', body))
    codes = set(re.findall(r'data-origin-code="([^"]+)"', body))
    codes |= set(re.findall(r'data-dest-code="([^"]+)"', body))

    assert codes, "no routes on the board"
    assert codes <= options, codes - options


def test_the_arcs_carry_the_same_pair(client):
    """`class="arc"` exactly — .arc__hit is the wide invisible hit target and
    carries no data of its own; the route lives on the group around it."""
    body = client.get("/flights").get_data(as_text=True)
    arcs = re.findall(r'<a class="arc [^"]*"[^>]*>', body, re.S)
    assert arcs, "no route links found"
    for arc in arcs:
        assert "data-origin=" in arc and "data-dest=" in arc, arc


def test_clearing_by_link_returns_the_unfiltered_board(client, conn):
    import db as database

    filtered = client.get("/flights?origin=JFK").get_data(as_text=True)
    everything = client.get("/flights").get_data(as_text=True)

    assert filtered.count('class="board__row"') < everything.count('class="board__row"')
    assert everything.count('class="board__row"') == len(database.get_flights(conn))
