/* Route map interactivity.
 *
 * The SVG is already drawn and already clickable — every arc and airport is a
 * real link. This adds the readout, the highlighting, and the guide panel.
 *
 * Three things can emphasise routes, in order of precedence:
 *   1. a hover or keyboard focus  (momentary)
 *   2. a selection made by clicking  (sticks until dismissed)
 *   3. the From/To/Date filters      (the standing background state)
 * When a hover ends the map falls back to whichever of 2 or 3 is active.
 */

(function () {
  "use strict";

  var map = document.querySelector(".routemap");
  if (!map) return;

  var svg = map.querySelector(".routemap__svg");
  var hint = document.getElementById("map-hint");
  var detail = document.getElementById("map-detail");
  var board = document.getElementById("board");

  var fields = {
    number: document.getElementById("map-number"),
    route: document.getElementById("map-route"),
    departs: document.getElementById("map-departs"),
    duration: document.getElementById("map-duration"),
    aircraft: document.getElementById("map-aircraft"),
    seats: document.getElementById("map-seats"),
    fare: document.getElementById("map-fare")
  };

  var selection = null;   // {kind: "arc"|"port", element}
  var filtered = null;    // array of arcs matching the filter form

  function arcs() {
    return Array.prototype.slice.call(svg.querySelectorAll(".arc"));
  }

  function ports() {
    return Array.prototype.slice.call(svg.querySelectorAll(".port"));
  }

  // --- emphasis --------------------------------------------------------------

  function clearEmphasis() {
    svg.classList.remove("is-focused", "is-single");
    arcs().forEach(function (arc) { arc.classList.remove("is-active", "is-dimmed"); });
    ports().forEach(function (port) { port.classList.remove("is-active", "is-dimmed"); });
    if (board) {
      board.querySelectorAll(".board__row.is-linked")
           .forEach(function (row) { row.classList.remove("is-linked"); });
    }
  }

  /* Light up a set of routes and the airports they touch. */
  function emphasise(chosen) {
    var live = {};
    chosen.forEach(function (arc) {
      live[arc.dataset.origin] = true;
      live[arc.dataset.dest] = true;
    });

    svg.classList.add("is-focused");
    // One route chosen means "look here"; several means "these match a filter".
    // Only the first grows its aircraft — see retro.css.
    svg.classList.toggle("is-single", chosen.length === 1);

    arcs().forEach(function (arc) {
      var on = chosen.indexOf(arc) !== -1;
      arc.classList.toggle("is-active", on);
      arc.classList.toggle("is-dimmed", !on);
    });
    ports().forEach(function (port) {
      var on = !!live[port.dataset.code];
      port.classList.toggle("is-active", on);
      port.classList.toggle("is-dimmed", !on);
    });

    if (!board) return;
    board.querySelectorAll(".board__row").forEach(function (row) {
      var on = chosen.some(function (arc) { return arc.dataset.flightId === row.dataset.flightId; });
      row.classList.toggle("is-linked", on);
    });
  }

  function raise(arc) {
    // SVG has no z-index, so the highlighted arc is redrawn last to sit on top.
    if (arc.parentNode.lastElementChild !== arc) arc.parentNode.appendChild(arc);
  }

  function showRoute(arc, lift) {
    if (lift) raise(arc);
    fields.number.textContent = arc.dataset.flightNumber;
    fields.route.textContent = arc.dataset.route + "  (" + arc.dataset.codes + ")";
    fields.departs.textContent = arc.dataset.departs;
    fields.duration.textContent = arc.dataset.duration;
    fields.aircraft.textContent = arc.dataset.aircraft;
    fields.seats.textContent = arc.dataset.seats;
    fields.fare.textContent = arc.dataset.fare;
    hint.hidden = true;
    detail.hidden = false;
    emphasise([arc]);
  }

  /* Hovering a city lights up every route that touches it. */
  function showPort(port) {
    var code = port.dataset.code;
    var touching = arcs().filter(function (arc) {
      return arc.dataset.origin === code || arc.dataset.dest === code;
    });

    fields.number.textContent = code;
    fields.route.textContent = port.dataset.city;
    fields.departs.textContent = port.dataset.departures + " departures";
    fields.duration.textContent = "--";
    fields.aircraft.textContent = "--";
    fields.seats.textContent = "--";
    fields.fare.textContent = "--";
    hint.hidden = true;
    detail.hidden = false;

    emphasise(touching);
    port.classList.add("is-active");
    port.classList.remove("is-dimmed");
  }

  function showFiltered() {
    fields.number.textContent = filtered.length + (filtered.length === 1 ? " route" : " routes");
    fields.route.textContent = filterSummary();
    fields.departs.textContent = "--";
    fields.duration.textContent = "--";
    fields.aircraft.textContent = "--";
    fields.seats.textContent = "--";
    fields.fare.textContent = "--";
    hint.hidden = true;
    detail.hidden = false;
    emphasise(filtered);
  }

  /* Back to whatever should be showing when nothing is under the pointer. */
  function reset() {
    if (selection) {
      return selection.kind === "arc" ? showRoute(selection.element, false)
                                      : showPort(selection.element);
    }
    if (filtered) return showFiltered();
    clearEmphasis();
    detail.hidden = true;
    hint.hidden = false;
  }

  // --- the guide panel -------------------------------------------------------

  var panel = document.getElementById("dest-panel");
  var panelBody = document.getElementById("dest-body");
  var closeButton = document.getElementById("dest-close");
  var openCode = null;

  /* Load a city's poster and itinerary into the panel under the map, and keep
     that route selected on the map until the panel is dismissed. */
  function openGuide(code, action, pick) {
    if (!panel) return false;
    if (openCode === code) {
      closeGuide();
      return false;      // it toggled shut; the caller should not sync filters
    }

    openCode = code;
    selection = pick || null;
    reset();

    panel.hidden = false;
    panel.classList.add("is-loading");

    fetch("/destinations/" + code + "/panel", { headers: { Accept: "text/html" } })
      .then(function (response) {
        if (!response.ok) throw new Error("no guide for " + code);
        return response.text();
      })
      .then(function (html) {
        panelBody.innerHTML = html;
        panel.classList.remove("is-loading");
        if (action) {
          var actions = panelBody.querySelector("[data-panel-actions]");
          var link = document.createElement("a");
          link.className = "btn btn--small btn--primary";
          link.href = action.href;
          link.textContent = action.label;
          actions.insertBefore(link, actions.firstChild);
        }
      })
      .catch(function () {
        panel.classList.remove("is-loading");
        panelBody.innerHTML = '<p class="destpanel__error">That guide could not be loaded.</p>';
      });

    return true;
  }

  function closeGuide() {
    openCode = null;
    selection = null;
    panel.hidden = true;
    panelBody.innerHTML = "";
    // Deselecting undoes what selecting did. Only the filters we set go with
    // it — `is-synced` is what tells those apart from ones typed by hand.
    releaseSyncedFilters();
    reset();
  }

  if (closeButton) closeButton.addEventListener("click", closeGuide);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panel && !panel.hidden) closeGuide();
  });

  // --- map events ------------------------------------------------------------

  function hoverTarget(event) {
    var arc = event.target.closest(".arc");
    if (arc) return showRoute(arc, event.type === "mouseover");
    var port = event.target.closest(".port");
    if (port) return showPort(port);
  }

  svg.addEventListener("mouseover", hoverTarget);
  svg.addEventListener("focusin", hoverTarget);
  svg.addEventListener("mouseleave", reset);
  svg.addEventListener("focusout", function (event) {
    if (!svg.contains(event.relatedTarget)) reset();
  });

  /* Clicks on the map open the guide instead of navigating. Without the
     script these are ordinary links and still work as links. */
  svg.addEventListener("click", function (event) {
    var arc = event.target.closest(".arc");
    if (arc) {
      event.preventDefault();
      if (openGuide(arc.dataset.dest,
                    { href: arc.dataset.book, label: "Book " + arc.dataset.flightNumber },
                    { kind: "arc", element: arc })) {
        syncFilters(arc.dataset.origin, arc.dataset.dest);
      }
      return;
    }
    var port = event.target.closest(".port");
    if (port) {
      event.preventDefault();
      if (openGuide(port.dataset.code,
                    { href: port.getAttribute("href"),
                      label: "Departures from " + port.dataset.city },
                    { kind: "port", element: port })) {
        // an airport is a departure point, so it sets From and frees To
        syncFilters(port.dataset.code, "");
      }
    }
  });

  // --- the From / To / Date filters ------------------------------------------

  var originField = document.getElementById("origin");
  var destField = document.getElementById("dest");
  var dateField = document.getElementById("date");

  function filterSummary() {
    var parts = [];
    if (originField && originField.value) parts.push("from " + originField.value);
    if (destField && destField.value) parts.push("to " + destField.value);
    if (dateField && dateField.value) parts.push("on " + dateField.value);
    return parts.join(" ") || "all routes";
  }

  /* Selecting a filter previews it on the map straight away, before the form
     is submitted: pick an origin and everything leaving there lights up. */
  function applyFilters() {
    var origin = originField ? originField.value : "";
    var dest = destField ? destField.value : "";
    var date = dateField ? dateField.value : "";

    if (!origin && !dest && !date) {
      filtered = null;
      return reset();
    }

    filtered = arcs().filter(function (arc) {
      return (!origin || arc.dataset.origin === origin)
          && (!dest || arc.dataset.dest === dest)
          && (!date || arc.dataset.date === date);
    });
    reset();
  }

  var clearLink = document.getElementById("clear-filters");

  /* Offer Clear whenever a field holds anything, however it got there. */
  function showClear() {
    if (!clearLink) return;
    clearLink.hidden = ![originField, destField, dateField].some(function (field) {
      return field && field.value;
    });
  }

  /* Whether the board itself was filtered, as opposed to only this form. */
  function boardIsFiltered() {
    var params = new URLSearchParams(window.location.search);
    return ["origin", "dest", "date"].some(function (name) {
      return (params.get(name) || "") !== "";
    });
  }

  if (clearLink) {
    clearLink.addEventListener("click", function (event) {
      // A filtered board can only be undone by a fresh request, so let the
      // link do what it says. A preview we set ourselves should not cost one.
      if (boardIsFiltered()) return;

      event.preventDefault();
      if (searchForm) searchForm.classList.remove("is-synced");
      [originField, destField, dateField].forEach(function (field) {
        setField(field, "");
      });
      if (panel && !panel.hidden) closeGuide();
      applyFilters();
      showClear();
    });
  }

  [originField, destField, dateField].forEach(function (field) {
    if (!field) return;
    field.addEventListener("change", applyFilters);
    field.addEventListener("input", applyFilters);
  });

  /* Setting a <select> from script fires no event, so anything else listening
     for a change would never hear about it. Dispatching one keeps this the
     same code path as a person using the dropdown. */
  function setField(field, code) {
    var value = code || "";
    if (!field || field.value === value) return false;
    // ignore a code the dropdown does not offer rather than blanking the field
    if (value && !field.querySelector('option[value="' + value + '"]')) return false;

    field.value = value;
    field.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  var searchForm = document.querySelector(".search");

  /* Picking a route is a statement of intent, so the From/To fields follow it.
     Preview only, which is how these filters have always behaved: the board
     itself still changes when the form is submitted. */
  function syncFilters(origin, dest) {
    setField(originField, origin);
    setField(destField, dest);
    if (searchForm) searchForm.classList.add("is-synced");
    showClear();
  }

  /* Give back the From/To we filled in, if they are still ours. The date is
     never touched: picking a route says nothing about which day you wanted. */
  function releaseSyncedFilters() {
    if (!searchForm || !searchForm.classList.contains("is-synced")) return false;
    searchForm.classList.remove("is-synced");
    setField(originField, "");
    setField(destField, "");
    showClear();
    return true;
  }

  /* Any hand-driven change makes the fields the visitor's, not ours: the cue
     goes, and deselecting a route will no longer clear them. */
  [originField, destField, dateField].forEach(function (field) {
    if (!field) return;
    field.addEventListener("input", function () {
      if (searchForm) searchForm.classList.remove("is-synced");
      showClear();
    });
  });

  // --- the departure board drives the map too --------------------------------

  if (board) {
    /* Reading a row in the timetable and finding it on the map should not mean
       hunting for the right arc: hovering the row lights it up. */
    board.addEventListener("mouseover", function (event) {
      var row = event.target.closest(".board__row");
      if (!row) return;
      var arc = svg.querySelector('.arc[data-flight-id="' + row.dataset.flightId + '"]');
      if (arc) showRoute(arc, true);
    });

    board.addEventListener("focusin", function (event) {
      var row = event.target.closest(".board__row");
      if (!row) return;
      var arc = svg.querySelector('.arc[data-flight-id="' + row.dataset.flightId + '"]');
      if (arc) showRoute(arc, false);
    });

    board.addEventListener("mouseleave", reset);
    board.addEventListener("focusout", function (event) {
      if (!board.contains(event.relatedTarget)) reset();
    });

    /* Clicking a departure opens its guide and keeps it isolated on the map.
       Clicks on the row's own links are left alone. */
    board.addEventListener("click", function (event) {
      if (event.target.closest("a, button")) return;
      var row = event.target.closest(".board__row");
      if (!row || !row.dataset.destCode) return;
      var arc = svg.querySelector('.arc[data-flight-id="' + row.dataset.flightId + '"]');
      if (openGuide(row.dataset.destCode,
                    { href: "/flights/" + row.dataset.flightId, label: "Book this flight" },
                    arc ? { kind: "arc", element: arc } : null)) {
        syncFilters(row.dataset.originCode, row.dataset.destCode);
      }
    });
  }

  // A filtered page load should arrive with the map already showing the filter.
  applyFilters();
  showClear();
})();
