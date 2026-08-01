/* Route map interactivity.
 *
 * The SVG is already drawn and already clickable — every arc and airport is a
 * real link. This only adds the readout panel and the highlighting that shows
 * which routes touch the city under the pointer.
 */

(function () {
  "use strict";

  var map = document.querySelector(".routemap");
  if (!map) return;

  var svg = map.querySelector(".routemap__svg");
  var hint = document.getElementById("map-hint");
  var detail = document.getElementById("map-detail");

  var fields = {
    number: document.getElementById("map-number"),
    route: document.getElementById("map-route"),
    departs: document.getElementById("map-departs"),
    duration: document.getElementById("map-duration"),
    aircraft: document.getElementById("map-aircraft"),
    seats: document.getElementById("map-seats"),
    fare: document.getElementById("map-fare")
  };

  function arcs() {
    return Array.prototype.slice.call(svg.querySelectorAll(".arc"));
  }

  function ports() {
    return Array.prototype.slice.call(svg.querySelectorAll(".port"));
  }

  function clearEmphasis() {
    svg.classList.remove("is-focused");
    arcs().forEach(function (arc) {
      arc.classList.remove("is-active", "is-dimmed");
    });
    ports().forEach(function (port) {
      port.classList.remove("is-active", "is-dimmed");
    });
  }

  function showRoute(arc, raise) {
    // SVG has no z-index, so the highlighted arc is redrawn last to sit on top
    // of its neighbours. Skipped for keyboard focus, where moving the focused
    // element in the DOM would drop the focus.
    if (raise && arc.parentNode.lastElementChild !== arc) {
      arc.parentNode.appendChild(arc);
    }

    fields.number.textContent = arc.dataset.flightNumber;
    fields.route.textContent = arc.dataset.route + "  (" + arc.dataset.codes + ")";
    fields.departs.textContent = arc.dataset.departs;
    fields.duration.textContent = arc.dataset.duration;
    fields.aircraft.textContent = arc.dataset.aircraft;
    fields.seats.textContent = arc.dataset.seats;
    fields.fare.textContent = arc.dataset.fare;
    hint.hidden = true;
    detail.hidden = false;

    svg.classList.add("is-focused");
    arcs().forEach(function (other) {
      other.classList.toggle("is-active", other === arc);
      other.classList.toggle("is-dimmed", other !== arc);
    });
    ports().forEach(function (port) {
      var touches = port.dataset.code === arc.dataset.origin
                 || port.dataset.code === arc.dataset.dest;
      port.classList.toggle("is-active", touches);
      port.classList.toggle("is-dimmed", !touches);
    });
  }

  /* Hovering a city lights up every route that touches it. */
  function showPort(port) {
    var code = port.dataset.code;
    fields.number.textContent = code;
    fields.route.textContent = port.dataset.city;
    fields.departs.textContent = port.dataset.departures + " departures";
    fields.duration.textContent = "--";
    fields.aircraft.textContent = "--";
    fields.seats.textContent = "--";
    fields.fare.textContent = "--";
    hint.hidden = true;
    detail.hidden = false;

    svg.classList.add("is-focused");
    arcs().forEach(function (arc) {
      var touches = arc.dataset.origin === code || arc.dataset.dest === code;
      arc.classList.toggle("is-active", touches);
      arc.classList.toggle("is-dimmed", !touches);
    });
    ports().forEach(function (other) {
      other.classList.toggle("is-active", other === port);
      other.classList.toggle("is-dimmed", other !== port);
    });
  }

  function reset() {
    clearEmphasis();
    detail.hidden = true;
    hint.hidden = false;
  }

  function handle(event) {
    var arc = event.target.closest(".arc");
    if (arc) return showRoute(arc, event.type === "mouseover");
    var port = event.target.closest(".port");
    if (port) return showPort(port);
  }

  svg.addEventListener("mouseover", handle);
  svg.addEventListener("focusin", handle);
  svg.addEventListener("mouseleave", reset);
  svg.addEventListener("focusout", function (event) {
    // Only reset when focus leaves the map entirely, not on every hop.
    if (!svg.contains(event.relatedTarget)) reset();
  });

  // --- the departure board drives the map too --------------------------------

  /* Reading a row in the timetable and finding it on the map should not mean
     hunting for the right arc: hovering the row lights it up. */
  var board = document.getElementById("board");
  if (!board) return;

  function arcForRow(row) {
    return svg.querySelector('.arc[data-flight-id="' + row.dataset.flightId + '"]');
  }

  function linkRow(event) {
    var row = event.target.closest(".board__row");
    if (!row) return;
    var arc = arcForRow(row);
    if (!arc) return;
    row.classList.add("is-linked");
    showRoute(arc, event.type === "mouseover");
  }

  function unlinkRows() {
    board.querySelectorAll(".board__row.is-linked")
         .forEach(function (row) { row.classList.remove("is-linked"); });
    reset();
  }

  board.addEventListener("mouseover", linkRow);
  board.addEventListener("focusin", linkRow);
  board.addEventListener("mouseleave", unlinkRows);
  board.addEventListener("focusout", function (event) {
    if (!board.contains(event.relatedTarget)) unlinkRows();
  });
})();
