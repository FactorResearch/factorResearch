import fs from 'node:fs/promises';

const webdriverUrl = process.env.WEBDRIVER_URL || 'http://127.0.0.1:4444';
const appUrl = process.env.A11Y_APP_URL || 'http://127.0.0.1:8051/';
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
const audits = [];

try {
  await request('POST', `${base}/url`, {url: appUrl});
  await new Promise((resolve) => setTimeout(resolve, 2500));
  await execute(axeSource);

  for (const viewport of viewports) {
    await request('POST', `${base}/window/rect`, viewport);
    for (const tab of tabs) {
      await execute(`document.querySelector(${JSON.stringify(tab.selector)}).click()`);
      await new Promise((resolve) => setTimeout(resolve, 350));
      const result = await executeAsync(`
        const done = arguments[arguments.length - 1];
        axe.run(document, {
          runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}
        }).then(done).catch((error) => done({error: error.message}));
      `);
      if (result.error) throw new Error(result.error);
      audits.push({viewport: viewport.name, tab: tab.name, violations: result.violations});
    }
  }
} finally {
  await request('DELETE', base).catch(() => undefined);
}

await fs.writeFile('axe-results.json', JSON.stringify(audits, null, 2));
const failures = audits.filter((audit) => audit.violations.length);
for (const audit of audits) {
  const nodes = audit.violations.reduce((total, violation) => total + violation.nodes.length, 0);
  console.log(`${audit.viewport}/${audit.tab}: ${audit.violations.length} violations, ${nodes} nodes`);
}
if (failures.length) process.exitCode = 1;
