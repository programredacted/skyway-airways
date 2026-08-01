/* Keep the departure board current.
 *
 * Refetches the volatile cells — seats, fare, status — once a minute and on
 * demand, patching them in place rather than reloading the page. Only cells
 * whose value actually changed are touched, so a board nobody has booked
 * against sits perfectly still.
 */

(function () {
  "use strict";

  var board = document.getElementById("board");
  if (!board) return;

  var button = document.getElementById("board-refresh");
  var status = document.getElementById("board-status");
  var pulse = document.getElementById("board-pulse");
  var INTERVAL_MS = 60000;

  var timer = null;
  var busy = false;

  function money(cents) {
    return "$" + Math.round(cents / 100).toLocaleString("en-US");
  }

  function seatsMarkup(flight) {
    if (flight.seats_available === 0) {
      return '<span class="tag tag--full">Sold out</span>';
    }
    if (flight.seats_available < 25) {
      return '<span class="tag tag--low">' + flight.seats_available + " left</span>";
    }
    return flight.seats_available + " left";
  }

  function highlight(cell) {
    cell.classList.remove("cell--changed");
    void cell.offsetWidth;                 // restart the animation
    cell.classList.add("cell--changed");
  }

  function applyFlight(flight) {
    var row = board.querySelector('[data-flight-id="' + flight.id + '"]');
    if (!row) return false;
    var changed = false;

    var seats = row.querySelector("[data-cell-seats]");
    var markup = seatsMarkup(flight);
    if (seats && seats.innerHTML.trim() !== markup) {
      seats.innerHTML = markup;
      highlight(seats);
      changed = true;
    }

    var fare = row.querySelector("[data-cell-fare]");
    var fareText = flight.from_price_cents ? money(flight.from_price_cents) : "--";
    if (fare && fare.textContent.trim() !== fareText) {
      fare.textContent = fareText;
      highlight(fare);
      changed = true;
    }

    var state = row.querySelector("[data-cell-status]");
    if (state && state.textContent.trim().toUpperCase() !== flight.status.toUpperCase()) {
      state.className = "tag tag--" + flight.status.toLowerCase();
      state.textContent = flight.status.charAt(0) + flight.status.slice(1).toLowerCase();
      highlight(state.parentElement);
      changed = true;
    }

    return changed;
  }

  function announce(message, tone) {
    status.textContent = message;
    status.dataset.tone = tone || "";
  }

  function refresh(manual) {
    if (busy) return;
    busy = true;
    pulse.classList.add("is-checking");
    if (manual) announce("Checking...");

    fetch("/api/flights" + window.location.search, {
      headers: { Accept: "application/json" },
      cache: "no-store"
    })
      .then(function (response) {
        if (!response.ok) throw new Error("board refresh failed");
        return response.json();
      })
      .then(function (data) {
        var changes = data.flights.reduce(function (count, flight) {
          return count + (applyFlight(flight) ? 1 : 0);
        }, 0);

        announce(
          changes
            ? "Updated " + data.updated_at + " · " + changes +
              (changes === 1 ? " flight changed" : " flights changed")
            : "Updated " + data.updated_at,
          changes ? "changed" : ""
        );
        restart();
      })
      .catch(function () {
        announce("Could not refresh — showing the last known board", "error");
        restart();
      })
      .then(function () {
        busy = false;
        pulse.classList.remove("is-checking");
      });
  }

  /* Restart the countdown ring so it always tracks the real next refresh. */
  function restart() {
    window.clearTimeout(timer);
    pulse.classList.remove("is-counting");
    void pulse.offsetWidth;
    pulse.classList.add("is-counting");
    timer = window.setTimeout(function () {
      refresh(false);
    }, INTERVAL_MS);
  }

  button.addEventListener("click", function () {
    refresh(true);
  });

  // Coming back to a sleeping tab should show fresh numbers immediately.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") refresh(false);
  });

  button.hidden = false;
  status.hidden = false;
  pulse.hidden = false;
  restart();
})();
