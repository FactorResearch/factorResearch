(function () {
  'use strict';

  const previousFocus = new WeakMap();
  const focusableSelector = [
    'a[href]:not([tabindex="-1"])',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(',');

  function visibleOverlay() {
    return document.querySelector(
      '[data-ds-overlay="modal"].is-open:not([hidden]),' +
      '[data-ds-overlay="drawer"].is-open:not([hidden]),' +
      '[data-ds-overlay="modal"]:target'
    );
  }

  function visibleDismissible() {
    return visibleOverlay() || document.querySelector('[data-ds-overlay="popup"]:not(.is-hidden)');
  }

  function syncOverlay() {
    const overlay = visibleOverlay();
    const dismissible = visibleDismissible();
    document.documentElement.classList.toggle('ds-overlay-lock', Boolean(overlay));
    document.body.classList.toggle('ds-overlay-lock', Boolean(overlay));
    document.querySelectorAll('[data-ds-overlay]').forEach(function (candidate) {
      if (candidate === dismissible || !previousFocus.has(candidate)) return;
      const target = previousFocus.get(candidate);
      previousFocus.delete(candidate);
      if (target && target.isConnected) {
        window.requestAnimationFrame(function () {
          if (target.isConnected) target.focus();
        });
      }
    });
    if (!dismissible) return;
    if (!previousFocus.has(dismissible)) previousFocus.set(dismissible, document.activeElement);
    if (!dismissible.contains(document.activeElement)) {
      const target = dismissible.querySelector(focusableSelector);
      if (target) target.focus();
    }
  }

  function closeHashOverlay(overlay) {
    if (!overlay || overlay.dataset.dsOverlay !== 'modal' || !window.location.hash) return false;
    const restoreTarget = previousFocus.get(overlay);
    previousFocus.delete(overlay);
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    window.requestAnimationFrame(function () {
      syncOverlay();
      if (restoreTarget && restoreTarget.isConnected) restoreTarget.focus();
    });
    return true;
  }

  document.addEventListener('click', function (event) {
    const trigger = event.target.closest && event.target.closest('a[href^="#"]:not([href="#"])');
    if (trigger) {
      const target = document.querySelector(trigger.getAttribute('href'));
      if (target?.matches('[data-ds-overlay]')) previousFocus.set(target, trigger);
    }
    const close = event.target.closest && event.target.closest('[data-ds-close="true"][href="#"]');
    if (!close) return;
    const overlay = close.closest('[data-ds-overlay="modal"]');
    if (closeHashOverlay(overlay)) event.preventDefault();
  });

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

  window.addEventListener('hashchange', function () {
    syncOverlay();
    syncSectionNavigation();
  });
  window.addEventListener('popstate', function () {
    restoreDisclosures(document);
    syncSectionNavigation();
  });
  window.addEventListener('pageshow', function () {
    restoreDisclosures(document);
    syncSectionNavigation();
  });

  document.addEventListener('keydown', function (event) {
    const overlay = visibleDismissible();
    if (!overlay) {
      const tab = event.target.closest && event.target.closest('[role="tab"]');
      if (tab && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
        const tabs = Array.from(tab.closest('[role="tablist"]').querySelectorAll('[role="tab"]'));
        const current = tabs.indexOf(tab);
        const next = event.key === 'Home' ? tabs[0]
          : event.key === 'End' ? tabs[tabs.length - 1]
          : tabs[(current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
        event.preventDefault();
        next.focus();
        next.click();
        return;
      }
      const target = event.target.closest && event.target.closest('[role="button"][tabindex]');
      if (target && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        target.click();
      }
      return;
    }
    if (event.key === 'Escape') {
      const close = overlay.querySelector('[data-ds-close="true"]');
      const controller = document.getElementById(overlay.dataset.dsCloseController || '');
      if (close || controller) {
        event.preventDefault();
        if (!closeHashOverlay(overlay)) (close || controller).click();
      }
      return;
    }
    if (overlay.dataset.dsOverlay === 'popup') return;
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

  function textOnly(value) {
    const node = document.createElement('span');
    node.innerHTML = String(value || '');
    return (node.textContent || '').trim();
  }

  function syncApplicationSemantics() {
    const tabs = document.querySelectorAll('.topbar-nav [role="tab"]');
    let activePanel = null;
    tabs.forEach(function (tab) {
      const panel = document.getElementById(tab.getAttribute('aria-controls'));
      const selected = tab.classList.contains('active') && Boolean(panel);
      tab.setAttribute('aria-selected', String(Boolean(selected)));
      tab.setAttribute('tabindex', selected ? '0' : '-1');
      if (panel) {
        panel.setAttribute('aria-hidden', String(!selected));
        if (selected) activePanel = panel;
      }
    });
    const skip = document.getElementById('skip-to-content');
    if (skip && activePanel) skip.setAttribute('href', '#' + activePanel.id);

    const profileButton = document.getElementById('profile-menu-btn');
    const profilePanel = document.getElementById('profile-quick-panel');
    if (profileButton && profilePanel) {
      profileButton.setAttribute('aria-expanded', String(!profilePanel.classList.contains('is-hidden')));
    }
  }

  function enhanceTables(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('table').forEach(function (table) {
      table.querySelectorAll('thead th').forEach(function (cell) { cell.setAttribute('scope', 'col'); });
      if (!table.querySelector('caption')) {
        const region = table.closest('[role="region"][aria-label]');
        const heading = table.closest('.scorecard, section')?.querySelector('h2, h3, .scorecard-header');
        const caption = document.createElement('caption');
        caption.className = 'sr-only';
        caption.textContent = region?.getAttribute('aria-label') || heading?.textContent?.trim() || 'Financial data table';
        table.prepend(caption);
      }
    });
  }

  function enhanceForms(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('.ds-field').forEach(function (field) {
      const control = field.querySelector('input, select, textarea, [role="combobox"]');
      const message = field.querySelector('.ds-field__message');
      if (!control || !message?.id) return;
      control.setAttribute('aria-describedby', message.id);
      if (field.classList.contains('is-error')) control.setAttribute('aria-invalid', 'true');
      else control.removeAttribute('aria-invalid');
      if (field.dataset.required === 'true') {
        control.setAttribute('aria-required', 'true');
        if ('required' in control) control.required = true;
      }
    });
  }

  function enhanceSliders(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('.ds-slider[id]').forEach(function (slider) {
      const label = document.querySelector(`label[for="${CSS.escape(slider.id)}"]`);
      const name = label?.textContent?.trim() || slider.id.replaceAll('-', ' ');
      slider.setAttribute('aria-label', `${name} numeric value`);
    });
  }

  function enhanceCharts(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('.js-plotly-plot').forEach(function (chart) {
      if (chart.dataset.a11yEnhanced === 'true') return;
      const traces = chart.data || [];
      const title = textOnly(chart.layout?.title?.text) || 'Financial chart';
      chart.dataset.a11yEnhanced = 'true';
      chart.setAttribute('role', 'img');
      chart.setAttribute('aria-label', `${title}. ${traces.length} data ${traces.length === 1 ? 'series' : 'series'}. A text data table follows.`);

      const details = document.createElement('details');
      details.className = 'ds-chart-data';
      const summary = document.createElement('summary');
      summary.textContent = `View ${title} as a data table`;
      const table = document.createElement('table');
      const caption = document.createElement('caption');
      caption.textContent = `${title} underlying values`;
      const head = document.createElement('thead');
      head.innerHTML = '<tr><th scope="col">Series</th><th scope="col">Period</th><th scope="col">Value</th></tr>';
      const body = document.createElement('tbody');
      traces.forEach(function (trace, traceIndex) {
        const xs = Array.from(trace.x || []);
        const ys = Array.from(trace.y || []);
        ys.forEach(function (value, index) {
          const row = document.createElement('tr');
          [trace.name || `Series ${traceIndex + 1}`, xs[index] ?? index + 1, value ?? 'Not available'].forEach(function (cellValue) {
            const cell = document.createElement('td');
            cell.textContent = String(cellValue);
            row.appendChild(cell);
          });
          body.appendChild(row);
        });
      });
      table.append(caption, head, body);
      details.append(summary, table);
      chart.insertAdjacentElement('afterend', details);
    });
  }

  new MutationObserver(function () {
    syncOverlay();
    syncApplicationSemantics();
    enhanceTables(document);
    enhanceForms(document);
    enhanceSliders(document);
    enhanceCharts(document);
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
      syncApplicationSemantics();
      enhanceTables(document);
      enhanceForms(document);
      enhanceSliders(document);
      enhanceCharts(document);
      restoreDisclosures(document);
      syncSectionNavigation();
    });
  } else {
    syncOverlay();
    syncApplicationSemantics();
    enhanceTables(document);
    enhanceForms(document);
    enhanceSliders(document);
    enhanceCharts(document);
    restoreDisclosures(document);
    syncSectionNavigation();
  }
})();
