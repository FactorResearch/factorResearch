(function () {
  "use strict";

  var btn = document.getElementById("analytics-opt-out-toggle");
  var status = document.getElementById("analytics-opt-out-status");

  if (btn && status) {
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
  }

  function activeModal() {
    var hash = window.location.hash;
    return hash ? document.querySelector(hash + ".legal-modal-overlay") : null;
  }

  function syncModalState() {
    document.body.classList.toggle("legal-modal-open", Boolean(activeModal()));
  }

  function closeModal() {
    document.querySelectorAll(".legal-modal-card.is-fullscreen").forEach(function (card) {
      card.classList.remove("is-fullscreen");
      var button = card.querySelector("[data-legal-fullscreen=\"true\"]");
      if (button) {
        button.setAttribute("aria-pressed", "false");
        button.textContent = "Full screen";
      }
    });
    window.location.hash = "";
    syncModalState();
  }

  document.addEventListener("click", function (event) {
    var fullscreen = event.target.closest && event.target.closest("[data-legal-fullscreen=\"true\"]");
    if (fullscreen) {
      var card = fullscreen.closest(".legal-modal-card");
      if (card) {
        var expanded = card.classList.toggle("is-fullscreen");
        fullscreen.setAttribute("aria-pressed", String(expanded));
        fullscreen.textContent = expanded ? "Exit full screen" : "Full screen";
      }
      return;
    }

    var close = event.target.closest && event.target.closest("[data-legal-close=\"true\"]");
    if (close) {
      event.preventDefault();
      closeModal();
    }
  });

  window.addEventListener("hashchange", syncModalState);
  document.addEventListener("keydown", function (event) {
    var modal = activeModal();
    if (modal && event.key === "Escape") {
      event.preventDefault();
      closeModal();
    }
  });
  syncModalState();
})();
