"""Project flights onto the SVG route map.

An equirectangular projection: longitude maps straight to x, latitude to y.
The map is drawn server-side so it renders without JavaScript and cannot shift
the layout; the browser only adds hover and selection on top.
"""

import worldmap

MAP_WIDTH = 1000
MAP_HEIGHT = 500

# The frame keeps the full span of longitude, so its left and right edges are
# the date line itself. A route crossing the Pacific then leaves one edge and
# arrives at the other exactly where a world map says it should -- cropping the
# sides instead would strand it in open ocean. Latitude is trimmed: Skyway
# flies nowhere near either pole.
VIEW_LAT_NORTH = 78
VIEW_LAT_SOUTH = -52

# How far an arc bows towards the pole, as a fraction of its own length.
BOW = 0.16

# Outbound and return fly the same great circle, so their arcs would land on
# top of each other and the one drawn first could never be hovered. Eastbound
# and westbound are nudged to opposite sides by this many units.
DIRECTION_SPLIT = 9.0

# Routes leaving one airport for nearby cities (JFK to London, Paris, Frankfurt
# and Rome) also run almost on top of each other, so each hub's departures are
# fanned apart by this spacing. Every arc stays individually clickable.
FAN_SPACING = 10.0


def project(latitude, longitude):
    x = (longitude + 180.0) / 360.0 * MAP_WIDTH
    y = (90.0 - latitude) / 180.0 * MAP_HEIGHT
    return x, y


def graticule(step_degrees=30):
    """Meridians and parallels, as ready-to-draw line coordinates."""
    meridians = []
    for longitude in range(-180 + step_degrees, 180, step_degrees):
        x, _ = project(0, longitude)
        meridians.append({"x1": x, "y1": 0, "x2": x, "y2": MAP_HEIGHT, "label": longitude})

    parallels = []
    for latitude in range(-60, 90, step_degrees):
        _, y = project(latitude, 0)
        parallels.append({"x1": 0, "y1": y, "x2": MAP_WIDTH, "y2": y, "label": latitude})

    return {"meridians": meridians, "parallels": parallels}


# Where along each arc a direction arrow is stamped, as a fraction of the curve.
ARROW_AT = (0.34, 0.66)


def _curve(x1, y1, x2, y2, fan=0.0):
    """A quadratic bezier bowing towards the nearer pole, like a great circle.

    Eastbound and westbound legs of the same route are offset to either side of
    that curve, and `fan` separates routes sharing an origin, so no arc can end
    up hidden underneath another. Returns the path plus the little arrowheads
    that show which way the flight goes.
    """
    midpoint_x = (x1 + x2) / 2
    midpoint_y = (y1 + y2) / 2
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

    towards_pole = -1 if midpoint_y < MAP_HEIGHT / 2 else 1
    heading = 1 if x2 >= x1 else -1
    control_y = (midpoint_y + towards_pole * length * BOW
                 + heading * DIRECTION_SPLIT + fan)

    return {
        "d": f"M {x1:.1f} {y1:.1f} Q {midpoint_x:.1f} {control_y:.1f} {x2:.1f} {y2:.1f}",
        "arrows": _arrows(x1, y1, midpoint_x, control_y, x2, y2),
    }


def _arrows(x0, y0, cx, cy, x2, y2):
    """Points along the curve, each with the tangent angle to point down.

    A quadratic bezier is B(t) = (1-t)^2 P0 + 2(1-t)t C + t^2 P2, and its
    derivative gives the heading at that point.
    """
    from math import atan2, degrees

    marks = []
    for t in ARROW_AT:
        u = 1 - t
        x = u * u * x0 + 2 * u * t * cx + t * t * x2
        y = u * u * y0 + 2 * u * t * cy + t * t * y2
        dx = 2 * u * (cx - x0) + 2 * t * (x2 - cx)
        dy = 2 * u * (cy - y0) + 2 * t * (y2 - cy)
        marks.append({"x": round(x, 1), "y": round(y, 1),
                      "angle": round(degrees(atan2(dy, dx)), 1)})
    return marks


def arc_segments(origin_lat, origin_lon, dest_lat, dest_lon, fan=0.0):
    """One segment, or two when the route crosses the antimeridian.

    A Pacific route like LAX-SYD spans 269 degrees of longitude. Drawn naively
    it would stripe backwards across the whole map, so we redraw it the short
    way round and add a copy shifted by one map width. The viewBox clips each
    copy, and the route appears to leave one edge and arrive at the other.
    """
    x1, y1 = project(origin_lat, origin_lon)
    x2, y2 = project(dest_lat, dest_lon)

    span = dest_lon - origin_lon
    if abs(span) <= 180:
        return [_curve(x1, y1, x2, y2, fan)]

    # Wrap the destination to the short side, then mirror the curve across the seam.
    shift = -MAP_WIDTH if span > 0 else MAP_WIDTH
    return [
        _curve(x1, y1, x2 + shift, y2, fan),
        _curve(x1 - shift, y1, x2, y2, fan),
    ]


def fan_offsets(routes):
    """Spread each airport's departures either side of their shared line."""
    by_origin = {}
    for route in routes:
        by_origin.setdefault(route["origin_code"], []).append(route["id"])

    offsets = {}
    for departures in by_origin.values():
        middle = (len(departures) - 1) / 2
        for position, flight_id in enumerate(departures):
            offsets[flight_id] = (position - middle) * FAN_SPACING
    return offsets


PADDING = 46          # room around the network for labels and wrap-around arcs
LABEL_CHAR_WIDTH = 7.4
LABEL_HEIGHT = 12
DOT_RADIUS = 6

# Where a code may sit relative to its dot, best first. Every option stays
# within about 20 units of the dot: a label parked far away to avoid a clash
# is no longer obviously attached to its own city.
LABEL_POSITIONS = [
    (0, -11, "middle"),   # above
    (0, 18, "middle"),    # below
    (15, 4, "start"),     # right
    (-15, 4, "end"),      # left
    (15, -8, "start"),    # above right
    (-15, -8, "end"),     # above left
    (15, 16, "start"),    # below right
    (-15, 16, "end"),     # below left
    (0, -24, "middle"),   # two lines above
    (0, 31, "middle"),    # two lines below
]


def _box(x0, x1, y0, y1):
    return (x0, x1, y0, y1)


def _label_box(x, y, anchor, characters):
    width = characters * LABEL_CHAR_WIDTH
    if anchor == "middle":
        left = x - width / 2
    elif anchor == "start":
        left = x
    else:
        left = x - width
    return _box(left, left + width, y - LABEL_HEIGHT * 0.85, y + LABEL_HEIGHT * 0.25)


def _overlaps(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def _place_labels(airports):
    """Position each airport code in the nearest spot that collides with nothing.

    London, Paris, Frankfurt and Rome sit within a few pixels of one another at
    this scale, so their codes have to move; they move around their own dot
    rather than away from it.
    """
    dots = {
        airport["code"]: _box(airport["x"] - DOT_RADIUS, airport["x"] + DOT_RADIUS,
                              airport["y"] - DOT_RADIUS, airport["y"] + DOT_RADIUS)
        for airport in airports
    }
    taken = []

    for airport in sorted(airports, key=lambda a: (a["x"], a["y"])):
        others = [box for code, box in dots.items() if code != airport["code"]]
        chosen = None

        for offset_x, offset_y, anchor in LABEL_POSITIONS:
            candidate = _label_box(airport["x"] + offset_x, airport["y"] + offset_y,
                                   anchor, len(airport["code"]))
            if not any(_overlaps(candidate, box) for box in others + taken):
                chosen = (offset_x, offset_y, anchor, candidate)
                break

        # Every position was blocked: take the first and accept the overlap.
        if chosen is None:
            offset_x, offset_y, anchor = LABEL_POSITIONS[0]
            chosen = (offset_x, offset_y, anchor,
                      _label_box(airport["x"] + offset_x, airport["y"] + offset_y,
                                 anchor, len(airport["code"])))

        airport["label_x"] = airport["x"] + chosen[0]
        airport["label_y"] = airport["y"] + chosen[1]
        airport["label_anchor"] = chosen[2]
        taken.append(chosen[3])


def _viewbox():
    """Full width, trimmed height. See VIEW_LAT_* above for why."""
    _, top = project(VIEW_LAT_NORTH, 0)
    _, bottom = project(VIEW_LAT_SOUTH, 0)
    return {"x": 0, "y": top, "width": MAP_WIDTH, "height": bottom - top}


def _viewbox_tight(airports):
    """The strip above the departure board, cropped to the network itself.

    Sitting on top of the timetable, the map has to earn its height: trimming to
    the airports makes it a wide band instead of a square, which keeps the first
    departures on the same screen.
    """
    edges = [airport["y"] for airport in airports] + \
            [airport["label_y"] for airport in airports]
    top = min(edges) - 14
    return {"x": 0, "y": top, "width": MAP_WIDTH, "height": max(edges) + 16 - top}


def coastlines():
    """Every landmass as an SVG path, projected the same way as the routes."""
    paths = []
    for name, ring in worldmap.LANDMASSES.items():
        points = []
        for latitude, longitude in ring:
            x, y = project(latitude, longitude)
            points.append(f"{x:.1f} {y:.1f}")
        paths.append({"name": name, "d": "M " + " L ".join(points) + " Z"})
    return paths


def build(routes):
    """Everything the map template needs: airports, arcs and the grid."""
    airports = {}
    arcs = []
    offsets = fan_offsets(routes)

    for route in routes:
        for code, city, latitude, longitude in (
            (route["origin_code"], route["origin_city"], route["origin_lat"], route["origin_lon"]),
            (route["dest_code"], route["dest_city"], route["dest_lat"], route["dest_lon"]),
        ):
            if code not in airports:
                x, y = project(latitude, longitude)
                airports[code] = {"code": code, "city": city, "x": x, "y": y,
                                  "departures": 0, "arrivals": 0}

        airports[route["origin_code"]]["departures"] += 1
        airports[route["dest_code"]]["arrivals"] += 1

        arcs.append({
            "flight": route,
            "segments": arc_segments(route["origin_lat"], route["origin_lon"],
                                     route["dest_lat"], route["dest_lon"],
                                     offsets[route["id"]]),
            "fullness": _fullness(route),
        })

    plotted = sorted(airports.values(), key=lambda a: a["code"])
    _place_labels(plotted)

    return {
        "airports": plotted,
        "arcs": arcs,
        "land": coastlines(),
        "grid": graticule(),
        "view": _viewbox(),
        "view_tight": _viewbox_tight(plotted),
        "width": MAP_WIDTH,
        "height": MAP_HEIGHT,
    }


def _fullness(route):
    """'open', 'filling' or 'full' — drives how heavily the arc is drawn."""
    if not route["total_seats"] or route["seats_available"] == 0:
        return "full"
    share = route["seats_available"] / route["total_seats"]
    if share < 0.2:
        return "full"
    if share < 0.5:
        return "filling"
    return "open"
