import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import zlib from 'node:zlib';

const webdriverUrl = process.env.WEBDRIVER_URL || 'http://127.0.0.1:4444';
const workshopUrl = process.env.DESIGN_SYSTEM_URL || 'http://127.0.0.1:8056/';
const update = process.env.UPDATE_VISUALS === '1';
const baselineDir = 'artifacts/design-system/visuals';
const actualDir = '/tmp/factorresearch-design-system-visuals';
const axeSource = await fs.readFile(new URL('../node_modules/axe-core/axe.min.js', import.meta.url), 'utf8');

async function request(method, endpoint, body) {
  const response = await fetch(`${webdriverUrl}${endpoint}`, {
    method,
    headers: {'content-type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || payload.value?.error) throw new Error(payload.value?.message || `${method} ${endpoint} failed`);
  return payload.value;
}

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
  return pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
}

function decodePng(buffer) {
  const signature = buffer.subarray(0, 8).toString('hex');
  if (signature !== '89504e470d0a1a0a') throw new Error('Invalid PNG baseline');
  let offset = 8, width, height, colorType, bitDepth, idat = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.subarray(offset + 4, offset + 8).toString('ascii');
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4); bitDepth = data[8]; colorType = data[9];
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    offset += length + 12;
  }
  if (bitDepth !== 8 || ![2, 6].includes(colorType)) throw new Error(`Unsupported PNG type ${colorType}/${bitDepth}`);
  const channels = colorType === 6 ? 4 : 3;
  const stride = width * channels;
  const compressed = zlib.inflateSync(Buffer.concat(idat));
  const pixels = Buffer.alloc(height * stride);
  let input = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = compressed[input++];
    for (let x = 0; x < stride; x += 1) {
      const raw = compressed[input++];
      const left = x >= channels ? pixels[y * stride + x - channels] : 0;
      const up = y ? pixels[(y - 1) * stride + x] : 0;
      const upperLeft = y && x >= channels ? pixels[(y - 1) * stride + x - channels] : 0;
      const predictor = filter === 0 ? 0 : filter === 1 ? left : filter === 2 ? up : filter === 3 ? Math.floor((left + up) / 2) : paeth(left, up, upperLeft);
      pixels[y * stride + x] = (raw + predictor) & 255;
    }
  }
  return {width, height, channels, pixels};
}

function differenceRatio(expectedBuffer, actualBuffer) {
  const expected = decodePng(expectedBuffer), actual = decodePng(actualBuffer);
  if (expected.width !== actual.width || expected.height !== actual.height || expected.channels !== actual.channels) return 1;
  let changed = 0;
  for (let pixel = 0; pixel < expected.width * expected.height; pixel += 1) {
    let different = false;
    for (let channel = 0; channel < Math.min(3, expected.channels); channel += 1) {
      const index = pixel * expected.channels + channel;
      if (Math.abs(expected.pixels[index] - actual.pixels[index]) > 12) different = true;
    }
    if (different) changed += 1;
  }
  return changed / (expected.width * expected.height);
}

const contexts = [
  {theme: 'light', viewport: 'desktop', width: 1440, height: 1000},
  {theme: 'dark', viewport: 'desktop', width: 1440, height: 1000},
  {theme: 'light', viewport: 'mobile', width: 390, height: 844},
  {theme: 'dark', viewport: 'mobile', width: 390, height: 844},
];
await fs.mkdir(actualDir, {recursive: true});
await fs.mkdir(baselineDir, {recursive: true});
const session = await request('POST', '/session', {capabilities: {alwaysMatch: {browserName: 'firefox', 'moz:firefoxOptions': {args: ['-headless']}}}});
const base = `/session/${session.sessionId}`;
const failures = [];
try {
  for (const context of contexts) {
    await request('POST', `${base}/window/rect`, context);
    await request('POST', `${base}/url`, {url: workshopUrl});
    await new Promise((resolve) => setTimeout(resolve, 800));
    await request('POST', `${base}/execute/sync`, {script: `${axeSource};document.documentElement.classList.toggle('light', ${context.theme === 'light'});document.body.classList.toggle('light', ${context.theme === 'light'});document.querySelector('.ds-catalogue').dataset.theme='${context.theme}';`, args: []});
    await new Promise((resolve) => setTimeout(resolve, 250));
    const axe = await request('POST', `${base}/execute/async`, {script: `const done=arguments[arguments.length-1];axe.run(document.querySelector('.ds-catalogue'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}).then(done).catch((error)=>done({error:error.message}));`, args: []});
    if (process.env.DEBUG_VISUALS === '1') {
      const styles = await request('POST', `${base}/execute/sync`, {script: `return ['.ds-button--primary','.ds-button--primary span:last-child','.ds-button--secondary','.ds-input'].map((selector)=>{const style=getComputedStyle(document.querySelector(selector));return {selector,color:style.color,background:style.backgroundColor,fontSize:style.fontSize,fontWeight:style.fontWeight,opacity:style.opacity};});`, args: []});
      console.log(context.theme, styles);
    }
    if (axe.error || axe.violations.length) failures.push(`${context.theme}/${context.viewport}: ${axe.error || axe.violations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => `${node.target.join(' ')} [${node.failureSummary}]`).join(' | ')}`).join(', ')}`);
    const element = await request('POST', `${base}/element`, {using: 'css selector', value: '.ds-catalogue'});
    const elementId = typeof element === 'string' ? element : Object.values(element)[0];
    const encoded = await request('GET', `${base}/element/${elementId}/screenshot`);
    const actual = Buffer.from(encoded, 'base64');
    const filename = `${context.theme}-${context.viewport}.png`;
    await fs.writeFile(path.join(actualDir, filename), actual);
    const baselinePath = path.join(baselineDir, filename);
    if (update) await fs.writeFile(baselinePath, actual);
    else {
      try {
        const ratio = differenceRatio(await fs.readFile(baselinePath), actual);
        console.log(`${filename}: ${(ratio * 100).toFixed(3)}% pixels changed`);
        if (ratio > 0.01) failures.push(`${filename}: ${(ratio * 100).toFixed(2)}% exceeds 1% threshold`);
      } catch (error) { failures.push(`${filename}: ${error.message}`); }
    }
  }
} finally {
  await request('DELETE', base).catch(() => undefined);
}
if (failures.length) {
  console.error(failures.join('\n'));
  process.exitCode = 1;
}
