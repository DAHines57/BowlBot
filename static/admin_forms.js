/* Shared admin form behaviour: dismissible flashes, and posting forms marked
   data-ajax without navigating away so typed values survive a failure. */
(function () {
  "use strict";

  function flashEl(kind) {
    return document.getElementById(kind === "ok" ? "flash-ok" : "flash-err");
  }

  function showFlash(kind, message) {
    var el = flashEl(kind);
    if (!el) {
      if (kind !== "ok") window.alert(message);
      return;
    }
    var text = el.querySelector("[data-flash-text]");
    if (text) text.textContent = message || "";
    el.hidden = !message;
    var other = flashEl(kind === "ok" ? "err" : "ok");
    if (other) other.hidden = true;
    if (message) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  window.adminShowFlash = showFlash;

  /* A hidden input named "action" shadows form.action in the DOM, so read the
   * attribute (or the page URL when it is missing) instead of the property. */
  function formPostUrl(form) {
    var attr = form.getAttribute("action");
    if (attr) return attr;
    return form.baseURI || window.location.href;
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-dismiss]");
    if (!btn) return;
    var box = btn.closest(".flash, .notice");
    if (box) box.hidden = true;
  });

  // A success message arriving as a query param is shown once, then stripped so
  // a refresh does not repeat it.
  (function stripQueryFlashes() {
    if (!window.history || !window.history.replaceState) return;
    var url = new URL(window.location.href);
    var touched = false;
    ["success", "error", "saved", "msg"].forEach(function (key) {
      if (url.searchParams.has(key)) {
        url.searchParams.delete(key);
        touched = true;
      }
    });
    if (touched) window.history.replaceState({}, "", url.pathname + url.search);
  })();

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.hasAttribute("data-ajax")) return;
    if (!form.reportValidity()) return;

    e.preventDefault();
    var buttons = Array.prototype.slice.call(form.querySelectorAll("button"));
    buttons.forEach(function (b) { b.disabled = true; });

    fetch(formPostUrl(form), {
      method: (form.method || "post").toUpperCase(),
      body: new FormData(form),
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    })
      .then(function (res) {
        return res.json().then(
          function (body) { return { ok: res.ok, body: body }; },
          function () { return { ok: false, body: { error: "Unexpected server response." } }; }
        );
      })
      .then(function (result) {
        if (!result.ok || result.body.error) {
          showFlash("err", result.body.error || "Save failed.");
          return;
        }
        showFlash("ok", result.body.message || "Saved.");
        if (form.hasAttribute("data-reload-on-success")) {
          window.setTimeout(function () { window.location.reload(); }, 600);
        }
      })
      .catch(function () {
        showFlash("err", "Network error. Nothing was saved.");
      })
      .finally(function () {
        buttons.forEach(function (b) { b.disabled = false; });
      });
  });
})();
