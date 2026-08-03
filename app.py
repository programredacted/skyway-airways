"""Skyway Airways — Flask application factory and routes.

Routes read through db.py and write through bookings.py; no SQL lives here.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import (Flask, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, url_for)

import bookings
import db
import destinations
import routemap
import seatmap
import seed
from pricing import cabin_label, format_fare

PROJECT_ROOT = Path(__file__).parent

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_PATTERN = re.compile(r"^[0-9+()\-. ]{7,20}$")

# The hall clock opens on New York; the picker offers every airport we serve.
DEFAULT_CLOCK_CODE = "JFK"
DEFAULT_CLOCK_OFFSET = -5


def create_app():
    """Build the configured Flask app. Used by run.py, gunicorn, and flask run."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-secret-change-in-production"),
        DATABASE_PATH=os.environ.get("DATABASE_PATH", str(PROJECT_ROOT / "flights.db")),
        AIRLINE_NAME="Skyway Airways",
    )

    prepare_database(app)
    register_teardown(app)
    register_filters(app)
    register_context(app)
    register_routes(app)
    return app


# --- database plumbing -------------------------------------------------------

def prepare_database(app):
    """Create the schema and seed it if empty.

    Runs at startup because Render's free disk is ephemeral: every deploy starts
    with no database file, and the public URL has to come up already populated.
    """
    connection = db.connect(app.config["DATABASE_PATH"])
    try:
        db.init_db(connection)
        seed.seed_if_empty(connection)
    finally:
        connection.close()


def get_db():
    """One connection per request, closed by the teardown handler."""
    if "db" not in g:
        g.db = db.connect(current_app.config["DATABASE_PATH"])
    return g.db


def register_teardown(app):
    @app.teardown_appcontext
    def close_db(exception):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()


# --- template filters --------------------------------------------------------

def register_filters(app):
    @app.template_filter("clock")
    def clock(iso_timestamp):
        """'2026-08-01T19:30' -> '19:30'"""
        return iso_timestamp[11:16]

    @app.template_filter("daystamp")
    def daystamp(iso_timestamp):
        """'2026-08-01T19:30' -> 'Sat 01 Aug'"""
        return datetime.fromisoformat(iso_timestamp).strftime("%a %d %b")

    @app.template_filter("duration")
    def duration(minutes):
        return f"{minutes // 60}h {minutes % 60:02d}m"

    @app.template_filter("fare")
    def fare(cents):
        return format_fare(cents or 0)

    app.jinja_env.globals["cabin_label"] = cabin_label


def register_context(app):
    """The hall clock hangs on every page, so every template gets its data."""

    @app.context_processor
    def clock_context():
        if not request.endpoint or request.endpoint == "static":
            return {}
        return {
            "clock": _clock_seed(DEFAULT_CLOCK_OFFSET),
            "clock_airports": db.get_airports(get_db()),
        }


# --- input validation --------------------------------------------------------

def validate_passenger(form):
    """Return (cleaned values, errors). Server-side, always — the form's
    HTML5 attributes are a convenience, not a guarantee."""
    values = {
        "full_name": form.get("full_name", "").strip(),
        "email": form.get("email", "").strip(),
        "phone": form.get("phone", "").strip(),
    }
    errors = {}

    if len(values["full_name"]) < 2:
        errors["full_name"] = "Please give the passenger's full name."
    elif len(values["full_name"]) > 80:
        errors["full_name"] = "That name is too long for a boarding pass."

    if not values["email"]:
        errors["email"] = "We need an email for the itinerary."
    elif not EMAIL_PATTERN.match(values["email"]):
        errors["email"] = "That doesn't look like an email address."

    if values["phone"] and not PHONE_PATTERN.match(values["phone"]):
        errors["phone"] = "Use digits, spaces, and + ( ) - only."

    return values, errors


# --- routes ------------------------------------------------------------------

def register_routes(app):

    @app.route("/")
    def index():
        return render_template("index.html", airports=db.get_airports(get_db()))

    @app.route("/flights")
    def flight_list():
        """The departure board, optionally filtered by the search form."""
        connection = get_db()
        criteria = _search_criteria()
        return render_template(
            "flights.html",
            flights=db.get_flights(connection, **criteria),
            airports=db.get_airports(connection),
            criteria=criteria,
            # The whole network is drawn above the board, not just the filtered
            # rows: it is there to navigate by, so it should show what exists.
            map=routemap.build(db.get_routes(connection)),
        )

    @app.route("/destinations")
    def destination_list():
        return render_template("destinations.html",
                               destinations=destinations.all_destinations())

    @app.route("/destinations/<code>/panel")
    def destination_panel(code):
        """HTML fragment for the panel the map opens beneath itself."""
        guide = destinations.get(code)
        if guide is None:
            abort(404)
        return render_template("_destination_panel.html",
                               destination=dict(guide, code=code.upper()))

    @app.route("/destinations/<code>")
    def destination_detail(code):
        guide = destinations.get(code)
        if guide is None:
            abort(404)
        arrivals = [flight for flight in db.get_flights(get_db())
                    if flight["dest_code"] == code.upper()]
        return render_template("destination.html",
                               destination=dict(guide, code=code.upper()),
                               flights=arrivals)

    @app.route("/map")
    def route_map():
        """Every flight drawn as an arc; a way to pick a departure by looking."""
        connection = get_db()
        return render_template(
            "map.html",
            map=routemap.build(db.get_routes(connection)),
            airports=db.get_airports(connection),
        )

    @app.route("/api/flights")
    def flight_availability():
        """The handful of values that go stale on the departure board.

        Only what changes: seats, fare and status. Times and routes are fixed,
        so the board patches these cells instead of reloading the page.
        """
        connection = get_db()
        criteria = _search_criteria()
        payload = {
            "updated_at": datetime.now().strftime("%H:%M:%S"),
            "flights": [
                {
                    "id": flight["id"],
                    "seats_available": flight["seats_available"],
                    "total_seats": flight["total_seats"],
                    "from_price_cents": flight["from_price_cents"],
                    "status": flight["status"],
                }
                for flight in db.get_flights(connection, **criteria)
            ],
        }
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/flights/<int:flight_id>")
    def flight_detail(flight_id):
        connection = get_db()
        flight = db.get_flight(connection, flight_id)
        if flight is None:
            abort(404)
        return render_template(
            "flight.html",
            flight=flight,
            cabins=seatmap.build_cabins(db.get_cabin_summary(connection, flight_id)),
        )

    @app.route("/flights/<int:flight_id>/seats")
    def seat_selection(flight_id):
        """Seat map. This step renders a working no-JS grid; the next step
        layers live availability and a selection panel on top of it."""
        connection = get_db()
        flight = db.get_flight(connection, flight_id)
        if flight is None:
            abort(404)

        aircraft = db.get_aircraft_for_flight(connection, flight_id)
        return render_template(
            "seats.html",
            flight=flight,
            aircraft=aircraft,
            airline=app.config["AIRLINE_NAME"],
            rows=seatmap.build_rows(db.get_seats(connection, flight_id), aircraft),
            exit_rows=seatmap.exit_rows(aircraft),
            cabins=seatmap.build_cabins(db.get_cabin_summary(connection, flight_id)),
        )

    @app.route("/api/flights/<int:flight_id>/seats")
    def seat_availability(flight_id):
        """Live seat state for the map. A view of the truth, never the authority:
        every booking is re-checked against the database before it commits."""
        connection = get_db()
        flight = db.get_flight(connection, flight_id)
        if flight is None:
            abort(404)

        aircraft = db.get_aircraft_for_flight(connection, flight_id)
        payload = seatmap.seat_payload(
            flight, aircraft,
            db.get_seats(connection, flight_id),
            db.get_cabin_summary(connection, flight_id),
        )
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"  # availability must never be cached
        return response

    @app.route("/flights/<int:flight_id>/passenger")
    def passenger_form(flight_id):
        """Details form for a chosen seat, refusing a seat that is already gone."""
        connection = get_db()
        seat = _usable_seat(connection, flight_id, request.args.get("seat_id"))
        if seat is None:
            return redirect(url_for("seat_selection", flight_id=flight_id))

        return render_template(
            "passenger.html",
            flight=db.get_flight(connection, flight_id),
            seat=seat,
            values={"full_name": "", "email": "", "phone": ""},
            errors={},
        )

    @app.route("/bookings", methods=["POST"])
    def confirm_booking():
        """Create passenger + booking in one transaction, then redirect.

        Post/Redirect/Get: the confirmation page is a GET, so refreshing it
        re-reads the booking instead of re-submitting the form.
        """
        connection = get_db()
        flight_id = request.form.get("flight_id", type=int)
        seat = _seat_on_flight(connection, flight_id, request.form.get("seat_id"))
        if seat is None:
            return redirect(url_for("seat_selection", flight_id=flight_id))

        # Already sold? It may be this passenger submitting twice, so ask
        # _handle_lost_seat rather than assuming a stranger beat them to it.
        if not seat["available"]:
            return _handle_lost_seat(connection, seat, request.form.get("email", ""), flight_id)

        values, errors = validate_passenger(request.form)
        if errors:
            return render_template(
                "passenger.html",
                flight=db.get_flight(connection, flight_id),
                seat=seat,
                values=values,
                errors=errors,
            ), 400

        try:
            reference = bookings.create_booking(
                connection, seat["id"], values["full_name"], values["email"], values["phone"]
            )
        except bookings.SeatUnavailable:
            return _handle_lost_seat(connection, seat, values["email"], flight_id)

        return redirect(url_for("boarding_pass", reference=reference))

    @app.route("/bookings/<reference>")
    def boarding_pass(reference):
        booking = db.get_booking_by_reference(get_db(), reference)
        if booking is None:
            abort(404)
        return render_template("confirmation.html", booking=booking)

    @app.route("/bookings/<reference>/cancel", methods=["POST"])
    def cancel(reference):
        if bookings.cancel_booking(get_db(), reference):
            flash("Booking cancelled. The seat is back on sale.", "success")
        else:
            flash("That booking was already cancelled.", "error")
        return redirect(url_for("boarding_pass", reference=reference.upper()))

    @app.route("/lookup", methods=["GET", "POST"])
    def lookup():
        if request.method == "POST":
            reference = request.form.get("reference", "").strip()
            if db.get_booking_by_reference(get_db(), reference):
                return redirect(url_for("boarding_pass", reference=reference.upper()))
            flash(f"No booking found for '{reference}'.", "error")
        return render_template("lookup.html")

    @app.route("/healthz")
    def healthz():
        """Render polls this to decide the service is up."""
        return {"status": "ok"}

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="No such gate."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", code=500, message="Turbulence. Try again."), 500


# --- route helpers -----------------------------------------------------------

def _clock_seed(offset_hours):
    """Times to paint the clock with on the server.

    Rendering it filled means the element occupies its final size in the very
    first frame, so revealing the live clock costs no layout shift -- and a
    visitor without JavaScript still sees the time the page was served.
    """
    now_utc = datetime.now(timezone.utc)
    return {
        "local": (now_utc + timedelta(hours=offset_hours)).strftime("%H:%M:%S"),
        "utc": now_utc.strftime("%H:%M:%S"),
    }


def _search_criteria():
    """The departure-board filters, shared by the page and its refresh endpoint."""
    return {
        "origin": request.args.get("origin", "").strip() or None,
        "dest": request.args.get("dest", "").strip() or None,
        "date": request.args.get("date", "").strip() or None,
    }


def _seat_on_flight(connection, flight_id, raw_seat_id):
    """The seat if it exists on this flight, sold or not. Flashes why if not."""
    if not raw_seat_id or not str(raw_seat_id).isdigit():
        flash("Please choose a seat.", "error")
        return None

    seat = db.get_seat(connection, int(raw_seat_id))
    if seat is None or seat["flight_id"] != flight_id:
        flash("That seat isn't on this flight.", "error")
        return None
    return seat


def _usable_seat(connection, flight_id, raw_seat_id):
    """The seat if it exists on this flight and is still free, else None."""
    seat = _seat_on_flight(connection, flight_id, raw_seat_id)
    if seat is None:
        return None
    if not seat["available"]:
        flash(f"Seat {seat['row_number']}{seat['seat_letter']} has just been taken.", "error")
        return None
    return seat


def _handle_lost_seat(connection, seat, email, flight_id):
    """Someone confirmed this seat first — unless it was this passenger.

    A double-submitted form (impatient click, or a resubmitted POST) lands here
    with the same email as the booking that already exists, so we show them
    their boarding pass instead of a scary error.
    """
    existing = db.get_active_booking_for_seat(connection, seat["id"])
    if existing and existing["email"].lower() == email.lower():
        return redirect(url_for("boarding_pass", reference=existing["reference"]))

    flash(f"Seat {seat['row_number']}{seat['seat_letter']} was taken a moment ago. "
          "Please pick another.", "error")
    return redirect(url_for("seat_selection", flight_id=flight_id))
