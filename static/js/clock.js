/* Split-flap clock for the departure hall.
 *
 * Shows the local time at any airport we serve, in 24-hour time, with UTC
 * always beside it as a fixed reference. Offsets are whole hours and ignore
 * daylight saving, matching how the timetable stores its times.
 */

(function () {
  "use strict";

  var clock = document.getElementById("clock");
  if (!clock || !window.SplitFlap) return;

  var face = document.getElementById("clock-face");
  var picker = document.getElementById("clock-zone");
  var cityLabel = document.getElementById("clock-city");
  var offsetLabel = document.getElementById("clock-offset");
  var utcLabel = document.getElementById("clock-utc");
  var STORAGE_KEY = "skyway.clock.zone";

  function pad(value) {
    return (value < 10 ? "0" : "") + value;
  }

  /* Wall-clock time at a fixed offset from UTC, as HH:MM:SS. */
  function timeAtOffset(offsetHours) {
    var now = new Date();
    var utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
    var there = new Date(utcMs + offsetHours * 3600000);
    return pad(there.getHours()) + ":" + pad(there.getMinutes()) + ":" + pad(there.getSeconds());
  }

  function offsetLabelFor(hours) {
    if (hours === 0) return "UTC";
    return "UTC" + (hours > 0 ? "+" : "−") + Math.abs(hours);
  }

  function selectedOption() {
    return picker.options[picker.selectedIndex];
  }

  function tick() {
    var option = selectedOption();
    var offset = Number(option.dataset.offset);

    // One decoy character, not three: seconds flip every tick, and a clock has
    // to stay readable while it does.
    window.SplitFlap.setText(face, timeAtOffset(offset), { steps: 1 });
    utcLabel.textContent = timeAtOffset(0);
    cityLabel.textContent = option.dataset.city;
    offsetLabel.textContent = offsetLabelFor(offset);
  }

  function start() {
    var saved = null;
    try {
      saved = window.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      saved = null;                       // private browsing; not worth failing over
    }
    if (saved) {
      for (var i = 0; i < picker.options.length; i++) {
        if (picker.options[i].value === saved) picker.selectedIndex = i;
      }
    }

    // Reveal before measuring: a hidden element has no width to lock in.
    clock.hidden = false;

    // Render the tiles once at a fixed width, then only changed digits flip.
    face.style.minWidth = face.getBoundingClientRect().width + "px";
    window.SplitFlap.render(face, timeAtOffset(Number(selectedOption().dataset.offset)));
    tick();

    picker.addEventListener("change", function () {
      try {
        window.localStorage.setItem(STORAGE_KEY, picker.value);
      } catch (error) { /* ignore */ }
      tick();
    });

    window.setInterval(tick, 1000);
  }

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(start);
  } else {
    start();
  }
})();
