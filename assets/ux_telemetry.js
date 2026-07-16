(function () {
  'use strict';

  const vitals = {LCP: null, INP: null, CLS: 0};
  let enabled = false;
  let sent = false;

  function routeGroup() {
    const path = window.location.pathname;
    if (/^\/[A-Za-z]{1,6}\/analyze\/\d{8}$/.test(path)) return '/company/analyze/date';
    if (/^\/analyze\/[A-Za-z]{1,6}/.test(path)) return '/analyze/company';
    return path.slice(0, 80) || '/';
  }

  function deviceClass() {
    if (window.innerWidth < 768) return 'mobile';
    if (window.innerWidth <= 1024) return 'tablet';
    return 'desktop';
  }

  function navigationType() {
    return performance.getEntriesByType('navigation')[0]?.type || 'navigate';
  }

  function post(path, payload) {
    if (!enabled) return;
    fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(payload),
    }).catch(function () {});
  }

  function sendVitals() {
    if (sent || !enabled) return;
    sent = true;
    Object.entries(vitals).forEach(function ([name, value]) {
      if (value === null) return;
      post('/analytics/vitals', {
        name,
        value,
        route: routeGroup(),
        device: deviceClass(),
        navigation_type: navigationType(),
      });
    });
  }

  function observe(type, callback) {
    try {
      new PerformanceObserver(function (list) { callback(list.getEntries()); })
        .observe({type, buffered: true});
    } catch (_error) {}
  }

  function startVitals() {
    observe('largest-contentful-paint', function (entries) {
      const last = entries[entries.length - 1];
      if (last) vitals.LCP = Math.round(last.startTime);
    });
    observe('layout-shift', function (entries) {
      entries.forEach(function (entry) {
        if (!entry.hadRecentInput) vitals.CLS += entry.value;
      });
      vitals.CLS = Math.round(vitals.CLS * 10000) / 10000;
    });
    observe('event', function (entries) {
      entries.forEach(function (entry) {
        if (entry.interactionId && (vitals.INP === null || entry.duration > vitals.INP)) {
          vitals.INP = Math.round(entry.duration);
        }
      });
    });
  }

  document.addEventListener('toggle', function (event) {
    if (!enabled || !event.target.open) return;
    if (event.target.matches('.analysis-disclosure')) {
      post('/analytics/ux-events', {event: 'model_detail_expanded', metadata: {section: event.target.closest('[data-analytics-id]')?.dataset.analyticsId || 'analysis'}});
    } else if (event.target.matches('.ds-methodology')) {
      post('/analytics/ux-events', {event: 'methodology_opened', metadata: {surface: 'inline'}});
    }
  }, true);

  document.addEventListener('click', function (event) {
    if (!enabled) return;
    if (event.target.closest('.portfolio-observation--critical a')) {
      post('/analytics/ux-events', {event: 'weak_link_inspected', metadata: {surface: 'portfolio'}});
    }
    if (event.target.closest('[id$="-retry"], [id*="retry"]')) {
      post('/analytics/ux-events', {event: 'recovery_retry_started', metadata: {surface: 'workflow'}});
    }
  });

  document.addEventListener('invalid', function (event) {
    post('/analytics/ux-events', {event: 'form_validation_failure', metadata: {control_type: event.target.type || event.target.tagName}});
  }, true);

  fetch('/privacy/analytics', {credentials: 'same-origin'})
    .then(function (response) { return response.json(); })
    .then(function (context) {
      enabled = !context.analytics_opt_out;
      if (enabled) startVitals();
    })
    .catch(function () {});

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') sendVitals();
  });
  window.addEventListener('pagehide', sendVitals);
})();
