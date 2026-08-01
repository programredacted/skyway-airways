/* Solari split-flap animation for the departure board.
 *
 * No layout shift: we wait for the webfonts to settle, lock each cell to the
 * width it already occupies, and only then swap the text for fixed-width tiles.
 * Skipped entirely for anyone who asked for reduced motion.
 */

(function () {
  "use strict";

  var GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  var FLIP_STEPS = 3;        // decoy characters before a tile settles
  var STEP_MS = 50;
  var ROW_STAGGER_MS = 65;   // each board row starts shortly after the one above
  var CHAR_STAGGER_MS = 18;  // and ripples left to right within a row

  var targets = document.querySelectorAll("[data-flap]");
  if (!targets.length) return;

  var stillWants = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function tileUp(element) {
    var text = element.textContent;
    var fragment = document.createDocumentFragment();

    for (var i = 0; i < text.length; i++) {
      var tile = document.createElement("span");
      var character = text.charAt(i);
      tile.className = character === " " ? "flap-char flap-char--blank" : "flap-char";
      tile.textContent = character;
      fragment.appendChild(tile);
    }

    element.textContent = "";
    element.className += " flap-text";
    element.appendChild(fragment);
    return Array.prototype.slice.call(element.children);
  }

  function flip(tile, delay) {
    var settled = tile.textContent;
    if (settled === " ") return;

    tile.style.animationDelay = delay + "ms";
    tile.className += " flap-flip";

    for (var step = 0; step < FLIP_STEPS; step++) {
      window.setTimeout(function (node) {
        node.textContent = GLYPHS.charAt(Math.floor(Math.random() * GLYPHS.length));
      }, delay + step * STEP_MS, tile);
    }
    window.setTimeout(function (node, character) {
      node.textContent = character;
    }, delay + FLIP_STEPS * STEP_MS, tile, settled);
  }

  function run() {
    // Delay is driven by the board row, not by a running tile count: with ~19
    // characters per row a global counter would take eight seconds to finish.
    var rowOrder = new Map();

    Array.prototype.forEach.call(targets, function (element) {
      // Freeze the box before touching the contents, so nothing can reflow.
      element.style.display = "inline-flex";
      element.style.minWidth = element.getBoundingClientRect().width + "px";

      var tiles = tileUp(element);
      if (!stillWants) return;

      var row = element.closest("tr") || element;
      if (!rowOrder.has(row)) rowOrder.set(row, rowOrder.size);
      var rowDelay = rowOrder.get(row) * ROW_STAGGER_MS;

      tiles.forEach(function (tile, index) {
        flip(tile, rowDelay + index * CHAR_STAGGER_MS);
      });
    });
  }

  // Fonts first: measuring before they load would lock in the wrong width.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(run);
  } else {
    run();
  }
})();
