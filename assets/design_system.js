(function () {
  'use strict';

  const previousFocus = new WeakMap();
  const focusableSelector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(',');

  function visibleOverlay() {
    return document.querySelector('[data-ds-overlay].is-open:not([hidden])');
  }

  function syncOverlay() {
    const overlay = visibleOverlay();
    document.documentElement.classList.toggle('ds-overlay-lock', Boolean(overlay));
    document.body.classList.toggle('ds-overlay-lock', Boolean(overlay));
    if (!overlay || previousFocus.has(overlay)) return;
    previousFocus.set(overlay, document.activeElement);
    const target = overlay.querySelector(focusableSelector);
    if (target) target.focus();
  }

  const disclosureStorageKey = 'fr:analysis-disclosures:v1';

  function readDisclosureState() {
    try {
      return JSON.parse(window.sessionStorage.getItem(disclosureStorageKey) || '{}');
    } catch (_error) {
      return {};
    }
  }

  function restoreDisclosures(root) {
    const state = readDisclosureState();
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('details[data-persist-disclosure="true"]').forEach(function (details) {
      const key = details.dataset.disclosureKey;
      if (key && Object.prototype.hasOwnProperty.call(state, key)) {
        details.open = Boolean(state[key]);
      }
    });
  }

  function syncSectionNavigation() {
    const activeId = window.location.hash.slice(1);
    document.querySelectorAll('.analysis-jump-link').forEach(function (link) {
      if (link.getAttribute('href') === '#' + activeId) {
        link.setAttribute('aria-current', 'location');
      } else {
        link.removeAttribute('aria-current');
      }
    });
  }

  document.addEventListener('toggle', function (event) {
    const details = event.target.closest && event.target.closest('details[data-persist-disclosure="true"]');
    if (!details) return;
    const key = details.dataset.disclosureKey;
    if (!key) return;
    const state = readDisclosureState();
    state[key] = details.open;
    try {
      window.sessionStorage.setItem(disclosureStorageKey, JSON.stringify(state));
    } catch (_error) {
      // Storage can be disabled; native disclosure behavior remains available.
    }
  }, true);

  window.addEventListener('hashchange', syncSectionNavigation);
  window.addEventListener('popstate', function () {
    restoreDisclosures(document);
    syncSectionNavigation();
  });
  window.addEventListener('pageshow', function () {
    restoreDisclosures(document);
    syncSectionNavigation();
  });

  document.addEventListener('keydown', function (event) {
    const overlay = visibleOverlay();
    if (!overlay) return;
    if (event.key === 'Escape') {
      const close = overlay.querySelector('[data-ds-close="true"]');
      if (close) {
        event.preventDefault();
        close.click();
      }
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(overlay.querySelectorAll(focusableSelector));
    if (!focusable.length) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  new MutationObserver(function () {
    const active = visibleOverlay();
    document.querySelectorAll('[data-ds-overlay]').forEach(function (overlay) {
      if (overlay === active || !previousFocus.has(overlay)) return;
      const target = previousFocus.get(overlay);
      previousFocus.delete(overlay);
      if (target && target.isConnected) target.focus();
    });
    syncOverlay();
    restoreDisclosures(document);
    syncSectionNavigation();
  }).observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['class', 'hidden'],
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      syncOverlay();
      restoreDisclosures(document);
      syncSectionNavigation();
    });
  } else {
    syncOverlay();
    restoreDisclosures(document);
    syncSectionNavigation();
  }
})();
