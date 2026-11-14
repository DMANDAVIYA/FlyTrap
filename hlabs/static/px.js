(function () {
  var m = 0, k = 0, sent = false;
  addEventListener("mousemove", function () { m++; }, { passive: true });
  addEventListener("keydown", function () { k++; });
  addEventListener("touchstart", function () { m++; }, { passive: true });
  function send() {
    if (sent) return; sent = true;
    try {
      fetch("/_hl/px", { method: "POST", keepalive: true, headers: { "content-type": "application/json" },
        body: JSON.stringify({ js: 1, mouse: m, keys: k }) });
    } catch (e) {}
  }
  setTimeout(send, 2500);
  addEventListener("pagehide", send);
})();
