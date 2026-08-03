/* Show/hide for password fields.
   The buttons are rendered hidden and revealed here, so a browser without
   JavaScript is never offered a control that would do nothing. */
(function () {
  "use strict";

  var buttons = document.querySelectorAll("[data-pw-toggle]");

  Array.prototype.forEach.call(buttons, function (button) {
    var input = document.getElementById(button.getAttribute("data-pw-toggle"));
    if (!input) return;

    function render(visible) {
      input.type = visible ? "text" : "password";
      button.textContent = visible ? "Hide" : "Show";
      button.setAttribute("aria-pressed", visible ? "true" : "false");
      button.setAttribute("aria-label", (visible ? "Hide" : "Show") + " password");
    }

    render(false);
    button.hidden = false;

    button.addEventListener("click", function () {
      var nowVisible = input.type === "password";
      render(nowVisible);
      // keep the caret where it was; switching type moves it to the end
      var end = input.value.length;
      input.focus();
      if (input.setSelectionRange) input.setSelectionRange(end, end);
    });
  });
}());
