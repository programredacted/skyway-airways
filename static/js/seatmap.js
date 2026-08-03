/* Interactive seat map.
 *
 * Enhances the grid Flask already rendered rather than rebuilding it: the
 * markup has one author (Jinja), and this file only owns selection state and
 * keeping availability fresh. Without JavaScript every seat is still a submit
 * button, so the page keeps working.
 */

(function () {
  "use strict";

  var grid = document.getElementById("seat-grid");
  if (!grid) return;

  var form = document.getElementById("seat-form");
  var chosenInput = document.getElementById("chosen-seat-id");
  var summary = document.getElementById("seat-summary");
  var chosenBox = document.getElementById("summary-chosen");
  var emptyNote = document.getElementById("summary-empty");
  var continueBtn = document.getElementById("continue-btn");
  var refreshBtn = document.getElementById("refresh-seats");
  var stamp = document.getElementById("refresh-stamp");
  var liveRegion = document.getElementById("seat-live");
  var hoverNote = document.getElementById("summary-hover");
  var seatsFree = document.getElementById("seats-free");

  var flightId = grid.dataset.flightId;
  var baseFare = Number(grid.dataset.baseFare);
  var selected = null;
  var REFRESH_MS = 30000;

  function seats() {
    return Array.prototype.slice.call(grid.querySelectorAll(".seat"));
  }

  function money(cents) {
    return "$" + Math.round(cents / 100).toLocaleString("en-US");
  }

  function isSold(seat) {
    return seat.getAttribute("aria-disabled") === "true";
  }

  function announce(message) {
    liveRegion.textContent = message;
  }

  // --- selection -------------------------------------------------------------

  function select(seat) {
    if (isSold(seat)) {
      announce("Seat " + seat.dataset.label + " is already sold.");
      return;
    }
    if (selected === seat) {
      clearSelection();
      announce("Seat " + seat.dataset.label + " deselected.");
      return;
    }

    if (selected) {
      selected.classList.remove("seat--selected");
      selected.setAttribute("aria-pressed", "false");
    }

    selected = seat;
    seat.classList.add("seat--selected");
    seat.setAttribute("aria-pressed", "true");
    chosenInput.value = seat.dataset.seatId;

    renderSummary(seat);
    announce(
      "Seat " + seat.dataset.label + " selected. " + seat.dataset.cabinLabel +
      ", " + money(Number(seat.dataset.price)) + "."
    );
  }

  function clearSelection() {
    if (selected) {
      selected.classList.remove("seat--selected");
      selected.setAttribute("aria-pressed", "false");
    }
    selected = null;
    chosenInput.value = "";
    chosenBox.hidden = true;
    emptyNote.hidden = false;
    continueBtn.disabled = true;
  }

  function renderSummary(seat) {
    var price = Number(seat.dataset.price);
    var multiplier = price / baseFare;

    document.getElementById("summary-seat").textContent = seat.dataset.label;
    document.getElementById("summary-cabin").textContent = seat.dataset.cabinLabel;
    document.getElementById("summary-base").textContent = money(baseFare);
    document.getElementById("summary-multiplier").textContent = "x " + multiplier.toFixed(1);
    document.getElementById("summary-total").textContent = money(price);

    emptyNote.hidden = true;
    chosenBox.hidden = false;
    continueBtn.disabled = false;
  }

  // --- keyboard --------------------------------------------------------------

  var ARROWS = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -1, ArrowDown: 1 };

  function moveFocus(current, key) {
    var row = current.closest(".seat-row");
    var inRow = Array.prototype.slice.call(row.querySelectorAll(".seat"));
    var column = inRow.indexOf(current);

    if (key === "ArrowLeft" || key === "ArrowRight") {
      var next = inRow[column + ARROWS[key]];
      if (next) next.focus();
      return;
    }

    // Up/down keep the same column and step to the neighbouring row.
    var rows = Array.prototype.slice.call(grid.querySelectorAll(".seat-row"));
    var target = rows[rows.indexOf(row) + ARROWS[key]];
    if (!target) return;
    var targetSeats = target.querySelectorAll(".seat");
    (targetSeats[Math.min(column, targetSeats.length - 1)] || targetSeats[0]).focus();
  }

  // --- live availability -----------------------------------------------------

  function applyState(seat, available) {
    if (available === undefined) return;
    var wasSold = isSold(seat);

    seat.setAttribute("aria-disabled", available ? "false" : "true");
    seat.classList.toggle("seat--taken", !available);

    var label = seat.dataset.label + ", " + seat.dataset.cabinLabel + ", " +
                money(Number(seat.dataset.price));
    seat.setAttribute("aria-label", "Seat " + label + (available ? "" : ", sold"));
    seat.title = seat.dataset.label + " · " + seat.dataset.cabinLabel + " · " +
                 money(Number(seat.dataset.price)) + (available ? "" : " · Sold");

    if (!available && !wasSold) seat.classList.add("seat--just-sold");
  }

  function refresh() {
    return fetch("/api/flights/" + flightId + "/seats", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    })
      .then(function (response) {
        if (!response.ok) throw new Error("availability request failed");
        return response.json();
      })
      .then(function (data) {
        var stateById = {};
        data.rows.forEach(function (row) {
          row.seats.forEach(function (seat) {
            stateById[seat.id] = seat.available;
          });
        });

        seats().forEach(function (seat) {
          applyState(seat, stateById[seat.dataset.seatId]);
        });

        seatsFree.textContent = data.seats_available;
        stamp.textContent = "updated " + new Date().toLocaleTimeString("en-US", {
          hour: "2-digit", minute: "2-digit"
        });

        // The seat they picked may have gone while they were filling in details.
        if (selected && stateById[selected.dataset.seatId] === false) {
          var lost = selected.dataset.label;
          clearSelection();
          announce("Seat " + lost + " was just booked by someone else. Please choose another.");
          stamp.textContent = "Seat " + lost + " was just taken";
        }
      })
      .catch(function () {
        stamp.textContent = "could not refresh";
      });
  }

  // --- wiring ----------------------------------------------------------------

  function enhance() {
    seats().forEach(function (seat) {
      // JS owns the click now, so seats stop being submit buttons. Sold seats
      // stay focusable (aria-disabled, not disabled) so they can be read aloud.
      seat.type = "button";
      seat.removeAttribute("name");
      if (seat.disabled) {
        seat.disabled = false;
        seat.setAttribute("aria-disabled", "true");
      }
    });

    grid.addEventListener("click", function (event) {
      var seat = event.target.closest(".seat");
      if (seat) select(seat);
    });

    grid.addEventListener("keydown", function (event) {
      if (!ARROWS[event.key]) return;
      var seat = event.target.closest(".seat");
      if (!seat) return;
      event.preventDefault();
      moveFocus(seat, event.key);
    });

    grid.addEventListener("mouseover", function (event) {
      var seat = event.target.closest(".seat");
      if (!seat) return;
      hoverNote.textContent = seat.dataset.label + " · " +
        seat.dataset.cabinLabel + " · " + money(Number(seat.dataset.price)) +
        (isSold(seat) ? " · sold" : "");
    });

    grid.addEventListener("mouseleave", function () {
      hoverNote.textContent = "";
    });

    refreshBtn.addEventListener("click", function () {
      stamp.textContent = "checking...";
      refresh();
    });

    summary.hidden = false;
    refreshBtn.hidden = false;
    document.getElementById("nojs-hint").hidden = true;

    // Re-check when the tab comes back, and slowly while it is visible.
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") refresh();
    });
    setInterval(function () {
      if (document.visibilityState === "visible") refresh();
    }, REFRESH_MS);
  }

  enhance();
})();
