(function () {
  'use strict';

  const announceTimers = new WeakMap();
  const busyStates = new WeakMap();

  function syncBusyState(root) {
    const nodes = root.querySelectorAll ? root.querySelectorAll('[data-dash-is-loading]') : [];
    nodes.forEach(function (node) {
      const busy = node.getAttribute('data-dash-is-loading') === 'true';
      node.setAttribute('aria-busy', busy ? 'true' : 'false');
      if (!node.id) return;
      const region = document.querySelector(`[data-loading-for="${CSS.escape(node.id)}"]`);
      if (!region) return;
      clearTimeout(announceTimers.get(region));
      if (!busy) {
        if (busyStates.get(node) === true) {
          region.textContent = region.dataset.completeLabel || 'Update complete';
          const timer = setTimeout(function () { region.textContent = ''; }, 1500);
          announceTimers.set(region, timer);
        }
        busyStates.set(node, false);
        return;
      }
      busyStates.set(node, true);
      const timer = setTimeout(function () {
        if (node.getAttribute('data-dash-is-loading') === 'true') {
          region.textContent = region.dataset.loadingLabel || 'Updating section';
        }
      }, 250);
      announceTimers.set(region, timer);
    });

    const hiddenDropdownTargets = root.querySelectorAll
      ? root.querySelectorAll('.dash-dropdown-focus-target[aria-hidden="true"]')
      : [];
    hiddenDropdownTargets.forEach(function (target) {
      target.setAttribute('tabindex', '-1');
    });
  }

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      const target = mutation.target.nodeType === Node.ELEMENT_NODE ? mutation.target : mutation.target.parentElement;
      if (target) syncBusyState(target.closest('[data-adaptive-loading]') || document);
    });
  });

  function start() {
    syncBusyState(document);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['data-dash-is-loading'],
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
