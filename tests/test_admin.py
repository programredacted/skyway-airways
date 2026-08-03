"""Staff accounts: who can reach the panel, and what deleting an account does
to the bookings it made."""

import accounts
import db as database

ADMIN = ("admin", "Concorde001!")


def _user(conn, username):
    return conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)
    ).fetchone()


def test_the_seed_creates_exactly_one_admin(conn):
    admins = conn.execute("SELECT username FROM users WHERE is_admin = 1").fetchall()
    assert [row["username"] for row in admins] == ["admin"]


def test_new_accounts_are_never_admins(conn, register):
    register(username="ordinary")
    assert _user(conn, "ordinary")["is_admin"] == 0


def test_the_admin_username_cannot_be_registered(client, conn, register):
    """If a visitor claimed it first, the seed would find the name taken and
    the database would end up with no administrator at all."""
    response = register(username="admin", email="me@example.com")
    assert response.status_code == 400
    assert "reserved" in response.get_data(as_text=True)

    # and the seeded staff account is untouched
    assert _user(conn, "admin")["is_admin"] == 1


def test_reserved_names_are_refused_whatever_the_casing(register):
    for name in ("Admin", "ROOT", "sTaFf", "crew", "administrator", "skyway"):
        response = register(username=name, email=f"{name}@example.com")
        assert response.status_code == 400, name
        assert "reserved" in response.get_data(as_text=True), name


def test_a_reserved_name_does_not_block_an_ordinary_one(conn, register):
    """The list is exact, not a prefix match — "adminium" is a fine username."""
    assert register(username="adminium").status_code == 302
    assert _user(conn, "adminium")["is_admin"] == 0


def test_the_seed_leaves_a_claimed_admin_name_alone(conn):
    """Belt and braces for a database that predates the reserved list: if the
    name is already taken by an ordinary account, the seed must not promote
    it. Better no admin than a stranger holding the keys."""
    import seed

    conn.execute("UPDATE users SET is_admin = 0")
    conn.execute("DELETE FROM users WHERE LOWER(username) = 'admin'")
    conn.execute(
        """
        INSERT INTO users (username, email, password_hash, created_at, is_admin)
        VALUES ('admin', 'squatter@example.com', 'x', '2026-01-01T00:00:00', 0)
        """
    )
    conn.commit()

    assert seed._ensure_an_admin_exists(conn) is False
    assert _user(conn, "admin")["is_admin"] == 0
    assert conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0] == 0


def test_the_panel_turns_away_visitors_who_are_not_signed_in(client):
    response = client.get("/admin")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_the_panel_turns_away_signed_in_non_admins(client, register):
    register(username="nosy")
    assert client.get("/admin").status_code == 403


def test_an_admin_sees_every_account(client, login, register, csrf):
    register(username="listed")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    body = client.get("/admin").get_data(as_text=True)
    assert "listed" in body
    assert "demo" in body and "captain" in body


def test_an_admin_can_delete_an_account(client, conn, csrf, login, register):
    register(username="doomed")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "doomed")["id"]
    response = client.post(f"/admin/users/{user_id}/delete",
                           data={"csrf_token": csrf("/admin")})
    assert response.status_code == 302
    assert _user(conn, "doomed") is None


def test_deleting_an_account_leaves_its_bookings_confirmed(
        client, conn, csrf, login, register, book):
    """The seat was paid for. Removing the person should not put it back on
    sale behind the airline's back."""
    register(username="departed")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "departed")["id"]
    client.post(f"/admin/users/{user_id}/delete", data={"csrf_token": csrf("/admin")})

    booking = database.get_booking_by_reference(conn, reference)
    assert booking is not None
    assert booking["status"] == "CONFIRMED"
    assert booking["user_id"] is None          # unowned, not gone
    assert client.get(f"/bookings/{reference}").status_code == 200


def test_an_admin_cannot_delete_their_own_account(client, conn, csrf, login):
    login(*ADMIN)
    admin_id = _user(conn, "admin")["id"]

    response = client.post(f"/admin/users/{admin_id}/delete",
                           data={"csrf_token": csrf("/admin")})
    assert response.status_code == 302
    assert _user(conn, "admin") is not None


def test_a_non_admin_cannot_delete_by_posting_directly(client, conn, csrf, register, login):
    """The panel being hidden is not the protection; the route is."""
    register(username="victim")
    client.post("/logout", data={"csrf_token": csrf()})
    register(username="attacker")

    victim_id = _user(conn, "victim")["id"]
    response = client.post(f"/admin/users/{victim_id}/delete",
                           data={"csrf_token": csrf()})
    assert response.status_code == 403
    assert _user(conn, "victim") is not None


def test_deleting_an_account_is_csrf_protected(client, conn, login, register, csrf):
    register(username="shielded")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "shielded")["id"]
    assert client.post(f"/admin/users/{user_id}/delete").status_code == 400
    assert _user(conn, "shielded") is not None


def test_the_admin_link_only_appears_for_admins(client, csrf, login, register):
    register(username="plain")
    assert 'href="/admin"' not in client.get("/flights").get_data(as_text=True)

    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)
    assert 'href="/admin"' in client.get("/flights").get_data(as_text=True)


def test_the_panel_lists_every_booking_and_who_holds_it(client, csrf, login,
                                                        register, book):
    register(username="traveller")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    body = client.get("/admin").get_data(as_text=True)
    assert reference in body
    assert "traveller" in body
    assert "Jimmy Ngo" in body            # the passenger, not the account
    assert "no account" in body           # the seeded pre-sold seats


def test_the_booking_list_says_what_it_is_not_showing(client, conn, csrf, login):
    """A list that stops without saying so reads as though it covered
    everything. The seed alone pre-sells hundreds of seats."""
    login(*ADMIN)
    body = client.get("/admin").get_data(as_text=True)

    total = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    shown = body.count("/admin/bookings/")

    assert total > accounts.BOOKINGS_SHOWN, "expected the seed to overflow the cap"
    assert shown <= accounts.BOOKINGS_SHOWN
    assert "Showing the" in body and "most recent" in body
    assert str(total) in body


def test_the_newest_bookings_are_the_ones_that_survive_the_cap(client, csrf, login,
                                                               register, book):
    """A booking made now must appear, however full the seeded history is."""
    register(username="latest")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    assert reference in client.get("/admin").get_data(as_text=True)


def test_an_admin_can_cancel_someone_elses_booking(client, conn, csrf, login,
                                                   register, book, free_seat):
    import db as database

    register(username="stranded")
    flight_id, seat = free_seat(1)
    reference = book(flight_id=flight_id, seat=seat).headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    response = client.post(f"/admin/bookings/{reference}/cancel",
                           data={"csrf_token": csrf("/admin")})
    assert response.status_code == 302
    assert database.get_booking_by_reference(conn, reference)["status"] == "CANCELLED"

    # and the seat is genuinely back on sale
    freed = database.get_seats(conn, flight_id)
    assert next(s for s in freed if s["id"] == seat["id"])["available"]


def test_a_non_admin_cannot_cancel_through_the_staff_route(client, conn, csrf,
                                                           register, book):
    import db as database

    register(username="mine")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    register(username="meddler")

    response = client.post(f"/admin/bookings/{reference}/cancel",
                           data={"csrf_token": csrf()})
    assert response.status_code == 403
    assert database.get_booking_by_reference(conn, reference)["status"] == "CONFIRMED"


def test_staff_cancelling_is_csrf_protected(client, conn, csrf, login, register, book):
    import db as database

    register(username="shieldedtrip")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    assert client.post(f"/admin/bookings/{reference}/cancel").status_code == 400
    assert database.get_booking_by_reference(conn, reference)["status"] == "CONFIRMED"


def test_staff_cancelling_an_unknown_reference_is_a_404(client, csrf, login):
    login(*ADMIN)
    assert client.post("/admin/bookings/NOPE01/cancel",
                       data={"csrf_token": csrf("/admin")}).status_code == 404


def test_a_cancelled_booking_loses_its_cancel_button(client, csrf, login,
                                                     register, book):
    register(username="doneandgone")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    client.post(f"/admin/bookings/{reference}/cancel",
                data={"csrf_token": csrf("/admin")})

    body = client.get("/admin").get_data(as_text=True)
    assert reference in body                                   # still listed
    assert f"/admin/bookings/{reference}/cancel" not in body    # but not actionable


def test_an_older_database_gains_the_admin_column(tmp_path):
    """CREATE TABLE IF NOT EXISTS will not add a column to a table that already
    exists, so db.init_db backfills it rather than requiring a reseed."""
    path = tmp_path / "old.db"
    connection = database.connect(str(path))
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL, email TEXT NOT NULL,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO users (username, email, password_hash, created_at)
        VALUES ('legacy', 'legacy@example.com', 'x', '2026-01-01T00:00:00');
        """
    )
    assert "is_admin" not in {
        row["name"] for row in connection.execute("PRAGMA table_info(users)")}

    database.init_db(connection)

    row = connection.execute("SELECT * FROM users WHERE username = 'legacy'").fetchone()
    assert row["is_admin"] == 0
    connection.close()


def test_list_accounts_counts_only_confirmed_bookings(conn, register, book, client, csrf):
    register(username="counted")
    reference = book().headers["Location"].rsplit("/", 1)[-1]

    rows = {row["username"]: row["booking_count"] for row in accounts.list_accounts(conn)}
    assert rows["counted"] == 1

    client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})
    rows = {row["username"]: row["booking_count"] for row in accounts.list_accounts(conn)}
    assert rows["counted"] == 0
