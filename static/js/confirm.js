/* One "are you sure?" before anything destructive.

   Progressive enhancement, deliberately: without JavaScript the button still
   submits and the server still does the work. This only adds a chance to back
   out, so nothing depends on it running. */
(function () {
  "use strict";

  document.addEventListener("submit", function (event) {
    var button = event.submitter || event.target.querySelector("[data-confirm]");
    if (!button || !button.hasAttribute("data-confirm")) return;
    if (!window.confirm(button.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });
}());
