# GOAL.md

**Goal:** Fully functional flight booking application, verified by an automated
pytest suite. "Done" means every criterion below passes as a real executed test,
not by inspection.

**Status: 14 / 14 criteria met. 33 tests, 0 failures, 0 blocked.**

Run the suite with:

```
.venv\Scripts\python -m pytest -q
```

## Booking core

- [x] 1. `GET /flights` lists >= 12 seeded flights read from the SQLite DB.
      → `test_flights.py::test_departures_list_at_least_twelve_seeded_flights`
      (asserts the rendered row count equals `COUNT(*) FROM flights` and is >= 12)
- [x] 2. Full happy path: register -> login -> pick flight -> select an available
      seat -> confirm -> a booking row exists with the correct `user_id`,
      `flight_id`, `seat_id` and price (base fare x class multiplier).
      → `test_booking.py::test_register_login_pick_seat_confirm_writes_the_right_row`
- [x] 3. A sold seat cannot be booked: the server rejects it even when the client
      submits that seat id directly.
      → `test_booking.py::test_a_sold_seat_cannot_be_booked_even_if_the_client_submits_it`
- [x] 4. Two overlapping attempts on the same seat leave exactly one booking
      (transaction / race test).
      → `test_booking.py::test_two_overlapping_attempts_on_one_seat_leave_exactly_one_booking`
      (8 threads on 8 connections released by a barrier: 1 booked, 7 refused, 0 lock errors)
- [x] 5. Refreshing or resubmitting the confirmation step never creates a
      duplicate booking.
      → `test_booking.py::test_resubmitting_the_confirm_step_creates_no_duplicate`
      and `::test_refreshing_the_boarding_pass_creates_nothing`

## Auth and persistence

- [x] 6. Registering creates a `users` row with a hashed password: the stored
      value is not the plaintext and `check_password_hash` verifies it.
      → `test_auth.py::test_registering_stores_a_hash_and_never_the_password`
- [x] 7. After logout, logging back in with the same credentials succeeds — and
      still succeeds from a **fresh app instance** pointed at the same DB file,
      proving persistence is in the database and not the session.
      → `test_auth.py::test_login_survives_logout_and_a_fresh_app_instance`
- [x] 8. A wrong password and an unknown username both fail with the same
      generic error.
      → `test_auth.py::test_wrong_password_and_unknown_user_give_the_same_generic_error`
- [x] 9. Duplicate username or email registration is rejected (case-insensitive).
      → `test_auth.py::test_duplicate_username_or_email_is_rejected`
- [x] 10. An anonymous booking attempt redirects to login, and after signing in
      the user lands back on their booking with flight and seat intact.
      → `test_booking.py::test_anonymous_booking_redirects_to_login_and_resumes`
- [x] 11. `/my-trips` requires login and shows exactly that user's bookings.
      → `test_auth.py::test_my_trips_requires_login_and_shows_only_your_own`

## Quality gates

- [x] 12. Validation: bad passenger input and malformed forms return friendly
      errors, never a 500.
      → `test_booking.py::test_bad_passenger_input_returns_a_friendly_error_not_a_500`
      and `::test_malformed_forms_never_500`
- [x] 13. The seed script is idempotent: running it twice yields no duplicate
      flights.
      → `test_flights.py::test_seeding_twice_adds_no_duplicate_flights`
- [x] 14. The seat map renders: the route returns 200 and contains the cabin
      shell, nose to tail, with a working seat grid inside it.
      → `test_seatmap.py::test_seat_map_page_renders_the_cabin_shell_and_a_seat_grid`
      (plus 6 more covering cabin order, aisles, the JSON API and every aircraft)

      The SVG airframe this criterion originally described was reverted on
      request: the outlined cabin shell reads better and does not shrink the
      seats to make room for wings.

## Test layout

| File | Tests | Covers |
|---|---|---|
| `tests/conftest.py` | — | fixtures: isolated temp SQLite DB per test, Flask test client, csrf/register/login/book helpers |
| `tests/test_flights.py` | 5 | 1, 13 |
| `tests/test_booking.py` | 10 | 2, 3, 4, 5, 10, 12 |
| `tests/test_auth.py` | 10 | 6, 7, 8, 9, 11 |
| `tests/test_seatmap.py` | 8 | 14 |

Each test gets its own database file, created and seeded from scratch, so no
test can see another's bookings and the seed path is exercised on every run.
