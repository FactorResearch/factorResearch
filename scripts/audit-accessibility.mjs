import fs from 'node:fs/promises';

const webdriverUrl = process.env.WEBDRIVER_URL || 'http://127.0.0.1:4444';
const appUrl = process.env.A11Y_APP_URL || 'http://127.0.0.1:8051/';
const outputPath = process.env.A11Y_OUTPUT || 'artifacts/production-proof/10-accessibility/axe-results.json';
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
  {name: 'desktop', width: 1440, height: 1000},
  {name: 'tablet', width: 820, height: 1180},
  {name: 'mobile', width: 390, height: 844},
];
const tabs = [
  {name: 'screener', selector: '#tab-screener-btn'},
  {name: 'analyze', selector: '#tab-analyze-btn'},
  {name: 'portfolio', selector: '#tab-portfolio-btn'},
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
      await execute(`document.querySelector('#theme-${theme}').click()`);
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

  // Browser zoom halves the available CSS-pixel viewport; use that equivalent
  // without relying on browser-specific zoom controls.
  await request('POST', `${base}/window/rect`, {width: 195, height: 422});
  const constrained = await execute(`return {
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    reducedMotionRules: [...document.styleSheets].some((sheet) => {
      try { return [...sheet.cssRules].some((rule) => rule.conditionText?.includes('prefers-reduced-motion')); }
      catch (_) { return false; }
    })
  }`);
  audits.push({viewport: 'mobile-200-percent', theme: 'dark', tab: 'portfolio', ...constrained, violations: []});
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
