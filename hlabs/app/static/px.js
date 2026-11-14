/* Page analytics: counts pointer and key activity and reports it twice,
   once a few seconds after load and once when the page is left. */
(function () {
  "use strict";
  var mouse = 0;
  var keys = 0;
  var sentOnLeave = false;

  function bump() { mouse += 1; }
  document.addEventListener("mousemove", bump, { passive: true });
  document.addEventListener("pointerdown", bump, { passive: true });
  document.addEventListener("touchstart", bump, { passive: true });
  document.addEventListener("wheel", bump, { passive: true });
  document.addEventListener("keydown", function () { keys += 1; });

  function report() {
    var body = JSON.stringify({ js: 1, mouse: mouse, keys: keys });
    try {
      if (navigator.sendBeacon && navigator.sendBeacon("/_hl/px", new Blob([body], { type: "application/json" }))) {
        return;
      }
    } catch (err) { /* fall through to fetch */ }
    if (window.fetch) {
      fetch("/_hl/px", {
        method: "POST",
        body: body,
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        keepalive: true
      }).catch(function () {});
    }
  }

  function leave() {
    if (sentOnLeave) { return; }
    sentOnLeave = true;
    report();
  }

  window.setTimeout(report, 4000);
  window.addEventListener("pagehide", leave);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") { leave(); }
  });
})();
