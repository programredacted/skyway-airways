"""Shape raw seat rows into the grid the seat map renders.

Both the server-rendered grid and (next step) the JSON API use this, so the two
can never disagree about where the aisles are.
"""

from pricing import CABIN_ORDER, CLASS_MULTIPLIERS, cabin_label


def build_rows(seats, aircraft):
    """Group seats into cabin-ordered rows, flagging where an aisle follows.

    Every row is emitted at the aircraft's full width. First and Business fly
    fewer seats across, so their missing positions come back as gaps rather than
    being dropped — without them the premium rows would centre themselves and
    the cabin would lose its shape.
    """
    aisle_letters = set(aircraft["aisle_after"].split(","))
    width = list(aircraft["seat_letters"])
    rows = []

    for row_number in range(1, aircraft["total_rows"] + 1):
        in_row = {seat["seat_letter"]: seat for seat in seats
                  if seat["row_number"] == row_number}
        if not in_row:
            continue

        cells = []
        for letter in width:
            seat = in_row.get(letter)
            cells.append(_seat_cell(seat, aisle_letters) if seat
                         else {"gap": True, "letter": letter,
                               "aisle_after": letter in aisle_letters})

        rows.append({
            "row_number": row_number,
            "cabin_class": next(iter(in_row.values()))["cabin_class"],
            "seats": cells,
        })
    return rows


def _seat_cell(seat, aisle_letters):
    return {
        "gap": False,
        "id": seat["id"],
        "label": f"{seat['row_number']}{seat['seat_letter']}",
        "letter": seat["seat_letter"],
        "cabin_class": seat["cabin_class"],
        "price_cents": seat["price_cents"],
        "available": bool(seat["available"]),
        "aisle_after": seat["seat_letter"] in aisle_letters,
    }


def exit_rows(aircraft):
    """The two over-wing rows, where the wings meet the fuselage.

    Placed just behind the Business cabin, which is where the wing box sits on
    most of this fleet.
    """
    first_exit = min(aircraft["business_last_row"] + 2, aircraft["total_rows"] - 1)
    return [first_exit, first_exit + 1]


def build_cabins(summary_rows):
    """Legend data: one entry per cabin, in nose-to-tail order."""
    by_class = {row["cabin_class"]: row for row in summary_rows}
    cabins = []
    for cabin_class in CABIN_ORDER:
        row = by_class.get(cabin_class)
        if row is None:
            continue
        cabins.append({
            "cabin_class": cabin_class,
            "label": cabin_label(cabin_class),
            "multiplier": CLASS_MULTIPLIERS[cabin_class],
            "total": row["total"],
            "available": row["available"],
            "price_cents": row["price_cents"],
        })
    return cabins


def seat_payload(flight, aircraft, seats, summary_rows):
    """The JSON the browser polls for live availability."""
    rows = build_rows(seats, aircraft)
    return {
        "flight": {
            "id": flight["id"],
            "number": flight["flight_number"],
            "aircraft": aircraft["model"],
            "base_fare_cents": flight["base_fare_cents"],
        },
        "cabins": build_cabins(summary_rows),
        "rows": [
            {**row, "seats": [cell for cell in row["seats"] if not cell["gap"]]}
            for row in rows
        ],
        "total_seats": sum(1 for row in rows for cell in row["seats"] if not cell["gap"]),
        "seats_available": sum(
            1 for row in rows for cell in row["seats"]
            if not cell["gap"] and cell["available"]
        ),
    }
