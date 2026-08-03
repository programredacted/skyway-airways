/* Lock, unlock, delete and cancel without reloading the page.
 *
 * The server redirects to an anchor, which works but costs a visible jump:
 * the browser paints the top of the page and then scrolls down to the row.
 * Submitting in the background and swapping in the new markup avoids the
 * navigation entirely, so nothing moves at all.
 *
 * Progressive enhancement. Without this file the forms submit normally and
 * the anchor does its job; nothing here is load-bearing.
 */
(function () {
  "use strict";

  var content = document.getElementById("admin-content");
  if (!content || !window.fetch || !window.DOMParser) return;

  var flashes = document.getElementById("flashes");

  function swapIn(html) {
    var fresh = new DOMParser().parseFromString(html, "text/html");

    var replacement = fresh.getElementById("admin-content");
    if (!replacement) return false;          // not the page we expected

    // The flash sits above <main>, so a message appearing pushes everything
    // down. Track where the content actually starts in the document and give
    // back whatever it moved by — offsetHeight misses the container's margin,
    // which is most of the shift when it goes from empty to occupied.
    var startedAt = documentTop();

    content.innerHTML = replacement.innerHTML;
    var message = fresh.getElementById("flashes");
    if (flashes && message) flashes.innerHTML = message.innerHTML;

    var movedTo = documentTop();
    if (movedTo !== startedAt) window.scrollBy(0, movedTo - startedAt);
    return true;
  }

  function documentTop() {
    return content.getBoundingClientRect().top + window.pageYOffset;
  }

  document.addEventListener("submit", function (event) {
    // confirm.js runs first and cancels the submit if the visitor backs out
    if (event.defaultPrevented) return;

    var form = event.target;
    if (!content.contains(form) || form.method.toLowerCase() !== "post") return;

    event.preventDefault();
    var buttons = form.querySelectorAll("button");
    Array.prototype.forEach.call(buttons, function (b) { b.disabled = true; });

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch" }
    })
      .then(function (response) {
        // fetch follows the redirect, so this is the refreshed admin page
        if (!response.ok) throw new Error("rejected");
        return response.text();
      })
      .then(function (html) {
        if (!swapIn(html)) throw new Error("unrecognised response");
      })
      .catch(function () {
        // Anything unexpected — a 403, a dropped connection — falls back to a
        // real submit so the visitor sees the server's actual answer rather
        // than a page that quietly did nothing.
        form.submit();
      });
  });
}());
