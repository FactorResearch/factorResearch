(function () {
  var btn = document.getElementById("analytics-opt-out-toggle");
  var status = document.getElementById("analytics-opt-out-status");
  if (!btn || !status) return;

  function render(optedOut) {
    status.textContent = optedOut ? "opted out" : "tracking enabled";
    btn.textContent = optedOut
      ? "Enable analytics for this session"
      : "Disable analytics for this session";
  }

  btn.addEventListener("click", function () {
    var nextOptOut = status.textContent !== "opted out";
    fetch("/privacy/analytics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ opt_out: nextOptOut })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        render(!!data.analytics_opt_out);
        if (window.factorResearchSyncAnalyticsContext) {
          window.factorResearchSyncAnalyticsContext(data);
        }
      })
      .catch(function () {});
  });
})();
