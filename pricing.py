"""Cabin classes, their price multipliers, and fare formatting."""

# Economy is the baseline; a flight's base_fare_cents is its Economy price.
CLASS_MULTIPLIERS = {
    "FIRST": 4.0,
    "BUSINESS": 2.2,
    "ECONOMY": 1.0,
}

CLASS_LABELS = {
    "FIRST": "First Class",
    "BUSINESS": "Clipper Club",
    "ECONOMY": "Economy",
}

# Cabins in nose-to-tail order, which is also how the seat map renders them.
CABIN_ORDER = ("FIRST", "BUSINESS", "ECONOMY")


def fare_for_class(base_fare_cents, cabin_class):
    """Price of one seat in this cabin, rounded to a whole dollar."""
    exact_cents = base_fare_cents * CLASS_MULTIPLIERS[cabin_class]
    return round(exact_cents / 100) * 100


def format_fare(cents):
    """1234500 -> '$12,345'. Fares are always whole dollars."""
    return "${:,}".format(cents // 100)


def cabin_label(cabin_class):
    return CLASS_LABELS.get(cabin_class, cabin_class.title())
