/*
 * meteoalarm-embed.js - show the HTML written by meteoalarm_warning.py on any page.
 *
 *   <div data-meteoalarm-src="./meteoalarm-summary.html"></div>
 *   <div data-meteoalarm-src="./meteoalarm-details.html"></div>
 *   <script src="./meteoalarm-embed.js" defer></script>
 *
 * The fragments must be served from the same site as the page.
 * Language tabs in the details fragment are wired up here, because scripts
 * inside HTML inserted with innerHTML do not run.
 */
(function () {
  "use strict";

  function bindTabs() {
    if (window.meteoalarmTabsBound) { return; }
    window.meteoalarmTabsBound = true;
    document.addEventListener("click", function (evt) {
      var label = evt.target.closest ? evt.target.closest("label[data-meteoalarm-tab]") : null;
      if (!label) { return; }
      var box = label.closest(".meteoalarm-tab");
      box.querySelectorAll(".tabcontent").forEach(function (el) { el.style.display = "none"; });
      box.querySelectorAll("label[data-meteoalarm-tab]").forEach(function (el) { el.classList.remove("active"); });
      document.getElementById(label.getAttribute("data-meteoalarm-tab")).style.display = "block";
      label.classList.add("active");
    });
  }

  function load(el) {
    var src = el.getAttribute("data-meteoalarm-src");
    // add a cache-buster so browsers pick up the file the cron job rewrote
    var url = src + (src.indexOf("?") < 0 ? "?" : "&") + "t=" + Math.floor(Date.now() / 60000);
    fetch(url, { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) { throw new Error(r.status + " " + r.statusText); }
        return r.text();
      })
      .then(function (html) { el.innerHTML = html; })
      .catch(function (err) {
        el.textContent = "Weather warnings are unavailable right now.";
        if (window.console) { console.warn("meteoalarm: could not load " + src + ": " + err.message); }
      });
  }

  function init() {
    bindTabs();
    document.querySelectorAll("[data-meteoalarm-src]").forEach(load);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
