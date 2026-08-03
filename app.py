"""Skyway Airways - Flask application factory and routes.

Routes read through db.py and write through bookings.py; no SQL lives here.
"""

import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import (Flask, abort, current_app, flash, g, jsonify, make_response,
                   redirect, render_template, request, send_from_directory,
                   session, url_for)

import accounts
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
    register_csrf(app)
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
    """The hall clock and the signed-in user are on every page."""

    @app.context_processor
    def shared_context():
        if not request.endpoint or request.endpoint == "static":
            return {}
        return {
            "clock": _clock_seed(DEFAULT_CLOCK_OFFSET),
            "clock_airports": db.get_airports(get_db()),
            "current_user": current_user(),
            "csrf_token": csrf_token(),
        }


# --- accounts and sessions ---------------------------------------------------

def current_user():
    """The signed-in account for this request, or None. Cached per request."""
    if "user" not in g:
        user_id = session.get("user_id")
        g.user = accounts.get_by_id(get_db(), user_id) if user_id else None
    return g.user


def sign_in(user):
    """Start a fresh session for this account.

    The old session id is dropped first so a token fixed before login cannot be
    reused afterwards. The half-finished booking survives that: it is the
    visitor's own typing, and losing it is what sent them back to an empty
    form after registering.
    """
    draft = session.get(PASSENGER_DRAFT_KEY)
    session.clear()
    if draft:
        session[PASSENGER_DRAFT_KEY] = draft
    session["user_id"] = user["id"]


def csrf_token():
    """A per-session token, minted on first use."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def register_csrf(app):
    """Check the token on every state-changing request, before anything else.

    Enforced here rather than per-route: a route that returns early - /login
    redirecting an already-signed-in visitor, say - would otherwise skip its own
    check, and any new POST route would have to remember to call it.
    """

    @app.before_request
    def verify_csrf():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        submitted = request.form.get("csrf_token", "")
        expected = session.get("csrf", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400)
        return None


def safe_next(target):
    """Only ever redirect to a path on this site.

    An open redirect would let a login link bounce someone to another host.
    """
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return None
    return target


# What the visitor typed on the passenger form before being told to sign in.
# Held in the session — a signed cookie — so it never becomes a query string
# that could be shared, logged or bookmarked.
PASSENGER_DRAFT_KEY = "passenger_draft"


def remember_passenger(form):
    draft = {
        "full_name": (form.get("full_name") or "").strip()[:120],
        "email": (form.get("email") or "").strip()[:254],
        "phone": (form.get("phone") or "").strip()[:40],
    }
    if any(draft.values()):
        session[PASSENGER_DRAFT_KEY] = draft


def passenger_draft():
    """A peek, not a pop. Registering and then filling in the booking are two
    separate requests and both need this, so it is dropped only once the
    booking exists."""
    return session.get(PASSENGER_DRAFT_KEY) or {}


def forget_passenger():
    session.pop(PASSENGER_DRAFT_KEY, None)


# --- input validation --------------------------------------------------------

def validate_passenger(form):
    """Return (cleaned values, errors). Server-side, always - the form's
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
            rows=seatmap.build_rows(db.get_seats(connection, flight_id), aircraft),
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

        # Whatever they typed before being sent off to sign in comes back
        # with them, so registering does not cost them the form.
        draft = passenger_draft()
        return render_template(
            "passenger.html",
            flight=db.get_flight(connection, flight_id),
            seat=seat,
            values={
                "full_name": draft.get("full_name", ""),
                "email": draft.get("email", ""),
                "phone": draft.get("phone", ""),
            },
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

        # Browsing is open to everyone; confirming is not. Send an anonymous
        # visitor to sign in and bring them back to this exact seat.
        user = current_user()
        if user is None:
            # They typed an email one step ago and are about to be asked for
            # one again on the register form. Carry it across.
            remember_passenger(request.form)
            flash("Please sign in to confirm your booking.", "error")
            resume = url_for("passenger_form", flight_id=flight_id, seat_id=seat["id"])
            return redirect(url_for("login", next=resume))

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
                connection, seat["id"], values["full_name"], values["email"],
                values["phone"], user_id=user["id"]
            )
        except bookings.SeatUnavailable:
            return _handle_lost_seat(connection, seat, values["email"], flight_id)

        forget_passenger()      # the booking exists; the draft has done its job
        return redirect(url_for("boarding_pass", reference=reference))

    @app.route("/bookings/<reference>")
    def boarding_pass(reference):
        booking = db.get_booking_by_reference(get_db(), reference)
        if booking is None:
            abort(404)
        return render_template("confirmation.html", booking=booking)

    @app.route("/bookings/<reference>/cancel", methods=["POST"])
    def cancel(reference):
        booking = db.get_booking_by_reference(get_db(), reference)
        if booking is None:
            abort(404)

        # A booking made from an account belongs to that account. Knowing the
        # reference is enough to look a booking up, but not to cancel someone
        # else's trip.
        user = current_user()
        if booking["user_id"] is not None and (
            user is None or user["id"] != booking["user_id"]
        ):
            abort(403)

        if bookings.cancel_booking(get_db(), reference):
            flash("Booking cancelled. The seat is back on sale.", "success")
        else:
            flash("That booking was already cancelled.", "error")

        return redirect(safe_next(request.form.get("next"))
                        or url_for("boarding_pass", reference=reference.upper()))

    # --- accounts ------------------------------------------------------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user():
            return redirect(url_for("flight_list"))

        values = {"username": "", "email": "", "password": "", "confirm": ""}
        errors = {}
        target = safe_next(request.args.get("next"))

        if request.method == "GET":
            values["email"] = passenger_draft().get("email", "")

        if request.method == "POST":
            try:
                user = accounts.register(get_db(), request.form)
            except accounts.RegistrationError as rejected:
                # Everything they typed comes back, passwords included: a taken
                # username should not cost them the whole form.
                values = {
                    "username": request.form.get("username", "").strip(),
                    "email": request.form.get("email", "").strip(),
                    "password": request.form.get("password", ""),
                    "confirm": request.form.get("confirm", ""),
                }
                errors = rejected.errors
            else:
                sign_in(user)
                flash(f"Welcome aboard, {user['username']}.", "success")
                return redirect(target or url_for("flight_list"))

        page = render_template("register.html", values=values, errors=errors,
                               next=target)
        response = make_response(page, 400 if errors else 200)
        if errors:
            # that page now carries a password in its markup — keep it out of
            # the browser's disk cache and any proxy along the way
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user():
            return redirect(url_for("flight_list"))

        target = safe_next(request.args.get("next"))
        error = None
        username = ""

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            user = accounts.authenticate(get_db(), username, request.form.get("password", ""))
            if user is None:
                # One message for both cases: naming which was wrong would
                # confirm whether an account exists.
                error = "Invalid username or password."
            else:
                sign_in(user)
                flash(f"Welcome aboard, {user['username']}.", "success")
                return redirect(safe_next(request.form.get("next")) or target
                                or url_for("flight_list"))

        return render_template("login.html", error=error, username=username,
                               next=target), (400 if error else 200)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Signed out. Safe travels.", "success")
        return redirect(url_for("index"))

    @app.route("/my-trips")
    def my_trips():
        user = current_user()
        if user is None:
            return redirect(url_for("login", next=url_for("my_trips")))
        return render_template("my_trips.html",
                               trips=accounts.bookings_for(get_db(), user["id"]))

    @app.route("/account", methods=["GET", "POST"])
    def account():
        user = current_user()
        if user is None:
            return redirect(url_for("login", next=url_for("account")))

        errors = {}
        if request.method == "POST":
            try:
                accounts.change_password(get_db(), user["id"], request.form)
            except accounts.RegistrationError as rejected:
                errors = rejected.errors
            else:
                flash("Password changed.", "success")
                return redirect(url_for("account"))

        return render_template(
            "account.html",
            user=user,
            errors=errors,
            trips=accounts.bookings_for(get_db(), user["id"]),
        ), (400 if errors else 200)

    # --- staff ---------------------------------------------------------------

    def require_admin():
        """The signed-in admin, or a response to return instead."""
        user = current_user()
        if user is None:
            return None, redirect(url_for("login", next=url_for("admin")))
        if not user["is_admin"]:
            abort(403)
        return user, None

    @app.route("/admin")
    def admin():
        user, bounce = require_admin()
        if bounce:
            return bounce
        connection = get_db()

        # An account and the trips it holds belong together: acting on either
        # means finding the same person twice in two different tables.
        held = {}
        for trip in accounts.account_bookings(connection):
            held.setdefault(trip["user_id"], []).append(trip)

        def with_trips(rows):
            return [{**row, "trips": held.get(row["id"], [])} for row in rows]

        # Seeded demo data stays apart from real activity: mixed together, the
        # ~900 pre-sold seats bury the handful that people actually made.
        everyone = accounts.list_accounts(connection, seed.demo_usernames())
        seeded = [row for row in everyone if row["seeded"]]
        return render_template(
            "admin.html",
            admin=user,
            accounts=with_trips([row for row in everyone if not row["seeded"]]),
            # the seeded logins split again by what they can do: a staff
            # account and a passenger account are not the same thing to look at
            staff_accounts=with_trips([row for row in seeded if row["is_admin"]]),
            demo_accounts=with_trips([row for row in seeded if not row["is_admin"]]),
            seeded_bookings=accounts.seeded_bookings(connection),
            totals=accounts.booking_totals(connection),
        )

    @app.route("/admin/bookings/<reference>/cancel", methods=["POST"])
    def admin_cancel_booking(reference):
        """Staff can cancel anyone's booking.

        Separate from /bookings/<ref>/cancel rather than loosening it: that
        route deliberately refuses a booking belonging to another account, and
        widening it for admins would put the ownership check behind a role
        test on the same path.
        """
        _, bounce = require_admin()
        if bounce:
            return bounce

        booking = db.get_booking_by_reference(get_db(), reference)
        if booking is None:
            abort(404)

        if bookings.cancel_booking(get_db(), reference):
            flash(f"Cancelled {booking['reference']}. The seat is back on sale.",
                  "success")
        else:
            flash("That booking was already cancelled.", "error")
        # back to the booking, not the top of a long page
        return redirect(url_for("admin", _anchor=f"booking-{booking['reference']}"))

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    def admin_delete_user(user_id):
        user, bounce = require_admin()
        if bounce:
            return bounce

        if user_id == user["id"]:
            # Removing the account you are holding would lock the last admin
            # out of the panel with no way back in.
            flash("You can't delete the account you're signed in with.", "error")
            return redirect(url_for("admin"))

        doomed = accounts.get_by_id(get_db(), user_id)
        if doomed is None:
            abort(404)

        try:
            accounts.delete_account(get_db(), user_id)
        except accounts.AccountLocked:
            flash(f"'{doomed['username']}' is locked. Unlock it first.", "error")
            return redirect(url_for("admin", _anchor=f"user-{user_id}"))

        flash(f"Deleted the account '{doomed['username']}'. "
              "Any bookings it made are still confirmed.", "success")
        # The row is gone, so back to its table rather than to a dead anchor.
        return redirect(url_for("admin", _anchor="accounts"))

    @app.route("/admin/users/<int:user_id>/lock", methods=["POST"])
    def admin_lock_user(user_id):
        """Toggle the guard that stops an account being deleted by mis-click."""
        _, bounce = require_admin()
        if bounce:
            return bounce

        target = accounts.get_by_id(get_db(), user_id)
        if target is None:
            abort(404)

        locked = not target["is_locked"]
        accounts.set_locked(get_db(), user_id, locked)
        flash(f"'{target['username']}' is now "
              + ("locked and cannot be deleted." if locked else "unlocked."),
              "success")
        return redirect(url_for("admin", _anchor=f"user-{user_id}"))

    @app.route("/lookup", methods=["GET", "POST"])
    def lookup():
        if request.method == "POST":
            reference = request.form.get("reference", "").strip()
            if db.get_booking_by_reference(get_db(), reference):
                return redirect(url_for("boarding_pass", reference=reference.upper()))
            flash(f"No booking found for '{reference}'.", "error")
        return render_template("lookup.html")

    @app.route("/favicon.ico")
    def favicon():
        """Browsers and bookmark tools ask for this by convention, whatever the
        <link> tags say. Served from /static so there is only one copy."""
        return send_from_directory(app.static_folder, "favicon.ico",
                                   mimetype="image/vnd.microsoft.icon")

    @app.route("/healthz")
    def healthz():
        """Render polls this to decide the service is up."""
        return {"status": "ok"}

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403,
                               message="Crew only beyond this point."), 403

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
    """Someone confirmed this seat first - unless it was this passenger.

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


