# LOOPLOG.md

One line per iteration of `/loop` against GOAL.md. Every result below comes from
an executed `pytest -q` run, never from reading code.

| # | Criterion | Result | Files touched |
|---|---|---|---|
| 0 | Build the suite and fixtures | 33 tests written, 28 passed / 5 failed on first run | `tests/conftest.py`, `tests/test_flights.py`, `tests/test_booking.py`, `tests/test_auth.py`, `tests/test_seatmap.py`, `requirements-dev.txt` |
| 1 | 8 — generic login error | FAIL then PASS. `POST /login` returned 302 instead of 400 when already signed in: the route redirected before its own CSRF check ran. Moved enforcement into a `before_request` hook so no route can skip it. | `app.py`, `templates/lookup.html` |
| 2 | 9 — duplicate registration rejected | FAIL then PASS. Test error, not app: registering signs you in, and `/register` then redirects, so the CSRF fixture found no form to read a token from. Fixture now reads from `/lookup`, which renders a form either way. | `tests/conftest.py`, `tests/test_auth.py` |
| 3 | 3 — sold seat rejected server-side | FAIL then PASS. Test error: `from tests.conftest import ...` fails because `tests/` is not a package. Replaced with a second registration, which is what the scenario actually needs. | `tests/test_booking.py` |
| 4 | 5 — no duplicate on resubmit | FAIL then PASS. Test error: after the seat sold, the passenger page redirects, so the token lookup threw. Same fixture fix as iteration 2. | `tests/conftest.py` |
| 5 | 10 — anonymous booking resumes | FAIL then PASS. Test error: asserted `seat_id=1` against a percent-encoded `next=` parameter (`seat_id%3D1`). Assertion now unquotes the location first. | `tests/test_booking.py` |
| 6 | Full suite | **33 passed, 0 failed, 0 blocked.** All 14 criteria checked in GOAL.md with their proving test named. | `GOAL.md`, `LOOPLOG.md` |

## Scoreboard

```
33 passed in 14.20s
criteria passed : 14 / 14
criteria blocked: 0
```

## Notes for manual attention

- One real defect surfaced: CSRF was checked per route, so `/login` skipped it
  whenever a signed-in visitor posted to it. It now runs in `before_request`,
  which also means every future POST route is covered by default.
- Four of the five failures were faults in the tests themselves, not the app.
  They are recorded above rather than quietly fixed, because "the test was
  wrong" is a different signal from "the code was wrong".
- No test was weakened or deleted to make the suite pass.
