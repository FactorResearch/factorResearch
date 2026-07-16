import fs from 'node:fs/promises';

const webdriverUrl = process.env.WEBDRIVER_URL || 'http://127.0.0.1:4444';
const appUrl = process.env.A11Y_APP_URL || 'http://127.0.0.1:8051/';
const outputPath = process.env.A11Y_OUTPUT || 'artifacts/production-proof/10-accessibility/accessibility-audit-results.json';
const axeSource = await fs.readFile(new URL('../node_modules/axe-core/axe.min.js', import.meta.url), 'utf8');

async function request(method, path, body) {
  const response = await fetch(`${webdriverUrl}${path}`, {
    method,
    headers: {'content-type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || payload.value?.error) {
    throw new Error(payload.value?.message || `${method} ${path} failed`);
  }
  return payload.value;
}

const session = await request('POST', '/session', {
  capabilities: {
    alwaysMatch: {
      browserName: 'firefox',
      'moz:firefoxOptions': {args: ['-headless']},
    },
  },
});
const sessionId = session.sessionId;
const base = `/session/${sessionId}`;

async function execute(script, args = []) {
  return request('POST', `${base}/execute/sync`, {script, args});
}

async function executeAsync(script, args = []) {
  return request('POST', `${base}/execute/async`, {script, args});
}

const viewports = [
  {name: 'iphone-sized', width: 320, height: 568},
  {name: 'android-sized', width: 412, height: 915},
  {name: 'tablet', width: 820, height: 1180},
  {name: 'laptop', width: 1366, height: 768},
  {name: 'wide-desktop', width: 1920, height: 1080},
];
const tabs = [
  {name: 'screener', selector: '#tab-screener-btn'},
  {name: 'analyze', selector: '#tab-analyze-btn'},
  {name: 'portfolio', selector: '#tab-portfolio-btn'},
  {name: 'factor-lab', selector: '#tab-factorlab-btn'},
  {name: 'pricing', selector: '#tab-pricing-btn'},
];
const standalonePages = [
  {name: 'landing', path: 'landing/post-a'},
  {name: 'terms', path: 'terms'},
  {name: 'privacy', path: 'privacy'},
  {name: 'error-state', path: 'landing/not-a-real-variant'},
];
const themes = ['light', 'dark'];
const audits = [];

try {
  await request('POST', `${base}/url`, {url: appUrl});
  await new Promise((resolve) => setTimeout(resolve, 2500));
  await execute(axeSource);

  for (const viewport of viewports) {
    await request('POST', `${base}/window/rect`, viewport);
    for (const theme of themes) {
      await execute(`
        document.documentElement.classList.toggle('light', ${theme === 'light'});
        document.body.classList.toggle('light', ${theme === 'light'});
        document.documentElement.dataset.theme = ${JSON.stringify(theme)};
      `);
      for (const tab of tabs) {
        await execute(`document.querySelector(${JSON.stringify(tab.selector)}).click()`);
        await new Promise((resolve) => setTimeout(resolve, 350));
        const result = await executeAsync(`
          const done = arguments[arguments.length - 1];
          const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
          axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa']}
          }).then((axeResult) => done({...axeResult, overflow})).catch((error) => done({error: error.message}));
        `);
        if (result.error) throw new Error(result.error);
        audits.push({viewport: viewport.name, theme, tab: tab.name, overflow: result.overflow, violations: result.violations});
      }
    }
  }

  for (const viewport of viewports.filter((item) => ['iphone-sized', 'laptop'].includes(item.name))) {
    await request('POST', `${base}/window/rect`, viewport);
    for (const page of standalonePages) {
      await request('POST', `${base}/url`, {url: new URL(page.path, appUrl).href});
      await new Promise((resolve) => setTimeout(resolve, 350));
      await execute(axeSource);
      const result = await executeAsync(`
        const done = arguments[arguments.length - 1];
        const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
        axe.run(document, {
          runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa']}
        }).then((axeResult) => done({...axeResult, overflow})).catch((error) => done({error: error.message}));
      `);
      if (result.error) throw new Error(result.error);
      audits.push({viewport: viewport.name, theme: 'system', tab: page.name, overflow: result.overflow, violations: result.violations});
    }
  }

  // Browser zoom halves the available CSS-pixel viewport; use that equivalent
  // without relying on browser-specific zoom controls.
  await request('POST', `${base}/url`, {url: appUrl});
  await new Promise((resolve) => setTimeout(resolve, 350));
  await execute(`document.querySelector('#tab-portfolio-btn').click()`);
  const keyboardContract = await executeAsync(`
    const done = arguments[arguments.length - 1];
    const firstTab = document.querySelector('#tab-screener-btn');
    const secondTab = document.querySelector('#tab-analyze-btn');
    firstTab.focus();
    firstTab.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
    const arrowNavigation = document.activeElement === secondTab;
    setTimeout(() => {
      const legalTrigger = document.querySelector('a[href="#legal-terms"]');
      legalTrigger.focus();
      legalTrigger.click();
      setTimeout(() => {
        const modal = document.querySelector('#legal-terms');
        const dialogFocus = modal.contains(document.activeElement);
        document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
        setTimeout(() => done({
          arrowNavigation,
          dialogFocus,
          focusRestored: document.activeElement === legalTrigger,
          restoredElement: document.activeElement?.outerHTML?.slice(0, 240) || 'none',
          triggerConnected: legalTrigger.isConnected,
        }), 120);
      }, 80);
    }, 250);
  `);
  await request('POST', `${base}/window/rect`, {width: 195, height: 422});
  const constrained = await execute(`return {
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    reducedMotionRules: [...document.styleSheets].some((sheet) => {
      try { return [...sheet.cssRules].some((rule) => rule.conditionText?.includes('prefers-reduced-motion')); }
      catch (_) { return false; }
    }),
    skipLink: Boolean(document.querySelector('.skip-link[href^="#"]')),
    scopedHeaders: [...document.querySelectorAll('thead th')].every((cell) => cell.getAttribute('scope') === 'col'),
    namedIconButtons: [...document.querySelectorAll('button')].every((button) => (button.getAttribute('aria-label') || button.textContent).trim().length > 0),
    chartEquivalents: [...document.querySelectorAll('.js-plotly-plot')].every((chart) => chart.nextElementSibling?.classList.contains('ds-chart-data')),
  }`);
  const contractViolations = Object.entries({
    'skip-link': constrained.skipLink,
    'table-header-scope': constrained.scopedHeaders,
    'button-name': constrained.namedIconButtons,
    'chart-equivalent': constrained.chartEquivalents,
    'keyboard-tab-navigation': keyboardContract.arrowNavigation,
    'dialog-focus-entry': keyboardContract.dialogFocus,
    'dialog-focus-restoration': keyboardContract.focusRestored,
  }).filter(([, passing]) => !passing).map(([id]) => ({id, nodes: [{html: id}]}));
  audits.push({viewport: 'mobile-200-percent', theme: 'dark', tab: 'portfolio', ...constrained, keyboardContract, violations: contractViolations});
} finally {
  await request('DELETE', base).catch(() => undefined);
}

await fs.mkdir(new URL('../artifacts/production-proof/10-accessibility/', import.meta.url), {recursive: true});
await fs.writeFile(outputPath, JSON.stringify(audits, null, 2));
const failures = audits.filter((audit) => audit.violations.length || audit.overflow > 1 || audit.reducedMotionRules === false);
for (const audit of audits) {
  const nodes = audit.violations.reduce((total, violation) => total + violation.nodes.length, 0);
  console.log(`${audit.viewport}/${audit.theme}/${audit.tab}: ${audit.violations.length} violations, ${nodes} nodes, overflow ${audit.overflow}px`);
}
if (failures.length) process.exitCode = 1;
