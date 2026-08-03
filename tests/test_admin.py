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


def _card(body, user_id):
    """The markup of one account's box, from its id to the next box."""
    start = body.index(f'id="user-{user_id}"')
    following = body.find('<article class="acct"', start + 1)
    return body[start:following if following != -1 else len(body)]


def test_a_booking_sits_inside_the_card_of_the_account_that_holds_it(
        client, conn, csrf, login, register, book):
    """The point of one box per account: the person, their trips, and the
    buttons for both, without hunting through a second table."""
    register(username="traveller")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    body = client.get("/admin").get_data(as_text=True)
    card = _card(body, _user(conn, "traveller")["id"])

    assert reference in card
    assert "Jimmy Ngo" in card                                  # the passenger
    assert f"/admin/bookings/{reference}/cancel" in card         # cancel it here
    assert "/delete" in card and "/lock" in card                 # act on the account


def test_an_account_with_no_trips_says_so(client, conn, csrf, login, register):
    register(username="idle")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    card = _card(client.get("/admin").get_data(as_text=True),
                 _user(conn, "idle")["id"])
    assert "No bookings on this account" in card


def test_the_seeded_list_says_what_it_is_not_showing(client, conn, csrf, login):
    """A list that stops without saying so reads as though it covered
    everything. The seed alone pre-sells hundreds of seats."""
    login(*ADMIN)
    body = client.get("/admin").get_data(as_text=True)

    seeded = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE user_id IS NULL").fetchone()[0]
    assert seeded > accounts.SEEDED_SHOWN, "expected the seed to overflow the cap"
    assert "Showing the" in body and "most recent" in body
    assert str(seeded) in body


def test_real_bookings_are_never_capped(client, conn, csrf, login, register, book):
    """The seeded seats are capped; the ones people made are not, and a booking
    made now must appear however full the seeded history is."""
    register(username="latest")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    body = client.get("/admin").get_data(as_text=True)
    assert reference in body

    from_accounts = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE user_id IS NOT NULL").fetchone()[0]
    for row in conn.execute(
            "SELECT reference FROM bookings WHERE user_id IS NOT NULL"):
        assert row["reference"] in body, row["reference"]

    # collapsed: the template wraps the line between the count and the noun
    flat = " ".join(body.split())
    assert f"holding {from_accounts} booking" in flat


def test_seeded_data_is_kept_apart_from_real_activity(client, csrf, login,
                                                      register, book):
    register(username="genuine")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    body = client.get("/admin").get_data(as_text=True)

    # the demo logins live under their own heading, not with the real accounts
    people = body.index("Passenger accounts")
    fixtures = body.index("Seeded demo data")
    assert people < body.index("genuine") < fixtures, "real account in the wrong box"
    assert fixtures < body.index("demo@skyway.example"), "demo login in the wrong box"
    assert people < body.index(reference) < fixtures, "real booking in the wrong box"


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


def test_every_action_returns_you_to_what_you_acted_on(client, conn, csrf, login,
                                                       register, book):
    """A bare redirect lands at the top, which on a long page means finding
    your place again after every click."""
    register(username="anchored")
    reference = book().headers["Location"].rsplit("/", 1)[-1]
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "anchored")["id"]
    token = csrf("/admin")

    locked = client.post(f"/admin/users/{user_id}/lock", data={"csrf_token": token})
    assert locked.headers["Location"].endswith(f"#user-{user_id}")

    cancelled = client.post(f"/admin/bookings/{reference}/cancel",
                            data={"csrf_token": token})
    assert cancelled.headers["Location"].endswith(f"#booking-{reference}")

    # refusing to delete a locked account should not move you either
    refused = client.post(f"/admin/users/{user_id}/delete", data={"csrf_token": token})
    assert refused.headers["Location"].endswith(f"#user-{user_id}")

    # the row is gone after a real delete, so it anchors to the table instead
    client.post(f"/admin/users/{user_id}/lock", data={"csrf_token": token})
    deleted = client.post(f"/admin/users/{user_id}/delete", data={"csrf_token": token})
    assert deleted.headers["Location"].endswith("#accounts")


def test_locking_an_account_refuses_deletion(client, conn, csrf, login, register):
    register(username="precious")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "precious")["id"]
    client.post(f"/admin/users/{user_id}/lock", data={"csrf_token": csrf("/admin")})
    assert _user(conn, "precious")["is_locked"] == 1

    response = client.post(f"/admin/users/{user_id}/delete",
                           data={"csrf_token": csrf("/admin")},
                           follow_redirects=True)
    assert "is locked" in response.get_data(as_text=True)
    assert _user(conn, "precious") is not None


def test_the_lock_is_enforced_below_the_view(conn, register):
    """Hiding the button is a courtesy; this is the rule. A direct call has to
    be refused too."""
    import accounts as accounts_module

    register(username="guardedrow")
    user_id = _user(conn, "guardedrow")["id"]
    accounts_module.set_locked(conn, user_id, True)

    try:
        accounts_module.delete_account(conn, user_id)
    except accounts_module.AccountLocked:
        pass
    else:
        raise AssertionError("a locked account was deleted")

    assert _user(conn, "guardedrow") is not None


def test_unlocking_restores_deletion(client, conn, csrf, login, register):
    register(username="releasable")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "releasable")["id"]
    client.post(f"/admin/users/{user_id}/lock", data={"csrf_token": csrf("/admin")})
    client.post(f"/admin/users/{user_id}/lock", data={"csrf_token": csrf("/admin")})
    assert _user(conn, "releasable")["is_locked"] == 0

    client.post(f"/admin/users/{user_id}/delete", data={"csrf_token": csrf("/admin")})
    assert _user(conn, "releasable") is None


def test_a_locked_row_offers_no_delete_button(client, conn, csrf, login, register):
    register(username="hidden")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "hidden")["id"]
    before = client.get("/admin").get_data(as_text=True)
    assert f"/admin/users/{user_id}/delete" in before

    client.post(f"/admin/users/{user_id}/lock", data={"csrf_token": csrf("/admin")})
    after = client.get("/admin").get_data(as_text=True)
    assert f"/admin/users/{user_id}/delete" not in after
    assert "Locked" in after


def test_every_account_row_offers_the_lock_toggle(client, conn, csrf, login, register):
    register(username="togglable")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    body = client.get("/admin").get_data(as_text=True)
    for row in conn.execute("SELECT id FROM users"):
        assert f"/admin/users/{row['id']}/lock" in body, row["id"]


def test_only_an_admin_can_lock(client, conn, csrf, register):
    register(username="target")
    client.post("/logout", data={"csrf_token": csrf()})
    register(username="meddler2")

    user_id = _user(conn, "target")["id"]
    assert client.post(f"/admin/users/{user_id}/lock",
                       data={"csrf_token": csrf()}).status_code == 403
    assert _user(conn, "target")["is_locked"] == 0


def test_locking_is_csrf_protected(client, conn, login, register, csrf):
    register(username="nocsrf")
    client.post("/logout", data={"csrf_token": csrf()})
    login(*ADMIN)

    user_id = _user(conn, "nocsrf")["id"]
    assert client.post(f"/admin/users/{user_id}/lock").status_code == 400
    assert _user(conn, "nocsrf")["is_locked"] == 0


def test_an_older_database_gains_both_added_columns(tmp_path):
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
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
    assert "is_admin" not in columns and "is_locked" not in columns

    database.init_db(connection)

    row = connection.execute("SELECT * FROM users WHERE username = 'legacy'").fetchone()
    assert row["is_admin"] == 0
    assert row["is_locked"] == 0
    connection.close()


def test_list_accounts_counts_only_confirmed_bookings(conn, register, book, client, csrf):
    register(username="counted")
    reference = book().headers["Location"].rsplit("/", 1)[-1]

    rows = {row["username"]: row["booking_count"] for row in accounts.list_accounts(conn)}
    assert rows["counted"] == 1

    client.post(f"/bookings/{reference}/cancel", data={"csrf_token": csrf()})
    rows = {row["username"]: row["booking_count"] for row in accounts.list_accounts(conn)}
    assert rows["counted"] == 0
