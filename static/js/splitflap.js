/* Solari split-flap tiles.
 *
 * Exposes window.SplitFlap so the departure board and the clock share one
 * implementation, then animates the board on load.
 *
 * No layout shift: we wait for the webfonts to settle, lock each cell to the
 * width it already occupies, and only then swap the text for fixed-width tiles.
 */

(function () {
  "use strict";

  var GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  var FLIP_STEPS = 3;        // decoy characters before a tile settles
  var STEP_MS = 50;
  var ROW_STAGGER_MS = 65;   // each board row starts shortly after the one above
  var CHAR_STAGGER_MS = 18;  // and ripples left to right within a row

  function prefersStillness() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  // Separators get no flap card of their own: a real board's colons and spaces
  // are painted on the housing, not on a flap.
  var SEPARATORS = " :-/";

  /* Replace an element's text with one fixed-width tile per character. */
  function render(element, text) {
    var content = text === undefined ? element.textContent : text;
    var fragment = document.createDocumentFragment();

    for (var i = 0; i < content.length; i++) {
      var character = content.charAt(i);
      var tile = document.createElement("span");
      tile.className = SEPARATORS.indexOf(character) === -1
        ? "flap-char"
        : "flap-char flap-char--blank";
      tile.textContent = character;
      fragment.appendChild(tile);
    }

    element.textContent = "";
    if (element.className.indexOf("flap-text") === -1) {
      element.className += " flap-text";
    }
    element.appendChild(fragment);
    return Array.prototype.slice.call(element.children);
  }

  /* Flip one tile to `settled`, cycling through decoys on the way.
     `steps` controls how many decoys: the board can afford three, the clock
     wants one so the seconds stay readable at a glance. */
  function flip(tile, settled, delay, steps) {
    if (SEPARATORS.indexOf(settled) !== -1) {
      tile.textContent = settled;
      return;
    }
    if (steps === undefined) steps = FLIP_STEPS;

    tile.classList.remove("flap-flip");
    void tile.offsetWidth;            // restart the animation
    tile.style.animationDelay = delay + "ms";
    tile.classList.add("flap-flip");

    for (var step = 0; step < steps; step++) {
      window.setTimeout(function (node) {
        node.textContent = GLYPHS.charAt(Math.floor(Math.random() * GLYPHS.length));
      }, delay + step * STEP_MS, tile);
    }
    window.setTimeout(function (node, character) {
      node.textContent = character;
    }, delay + steps * STEP_MS, tile, settled);
  }

  /* Update an already-rendered element, flipping only the characters that
     changed. The clock relies on this: seconds flip every tick, hours rarely. */
  function setText(element, text, options) {
    var tiles = element.querySelectorAll(".flap-char");
    if (tiles.length !== text.length) {
      return render(element, text);
    }

    var steps = options && options.steps;
    var still = prefersStillness();
    for (var i = 0; i < tiles.length; i++) {
      var character = text.charAt(i);
      if (tiles[i].textContent === character) continue;
      if (still) {
        tiles[i].textContent = character;
      } else {
        flip(tiles[i], character, 0, steps);
      }
    }
    return Array.prototype.slice.call(tiles);
  }

  window.SplitFlap = { render: render, setText: setText, flip: flip };

  // --- the departure board -------------------------------------------------

  function runBoard() {
    var targets = document.querySelectorAll("[data-flap]");
    if (!targets.length) return;

    var animate = !prefersStillness();
    var rowOrder = new Map();

    Array.prototype.forEach.call(targets, function (element) {
      // Freeze the box before touching the contents, so nothing can reflow.
      element.style.display = "inline-flex";
      element.style.minWidth = element.getBoundingClientRect().width + "px";

      var settled = element.textContent;
      var tiles = render(element);
      if (!animate) return;

      // Delay is driven by the board row, not by a running tile count: with ~19
      // characters per row a global counter would take eight seconds to finish.
      var row = element.closest("tr") || element;
      if (!rowOrder.has(row)) rowOrder.set(row, rowOrder.size);
      var rowDelay = rowOrder.get(row) * ROW_STAGGER_MS;

      tiles.forEach(function (tile, index) {
        flip(tile, settled.charAt(index), rowDelay + index * CHAR_STAGGER_MS);
      });
    });
  }

  // Fonts first: measuring before they load would lock in the wrong width.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(runBoard);
  } else {
    runBoard();
  }
})();
