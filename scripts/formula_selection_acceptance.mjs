import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [output, fixture, base = 'http://127.0.0.1:18891'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const [invite] = JSON.parse(await readFile(path.join(fixture, 'browser-fixtures.json'), 'utf8'));
const browser = await launchAcceptanceChrome(require);
const checks = [], errors = [];
const route = '#/subjects/math/topic/synthetic-course';
const original = '#clip-fragment [data-math-source]';
const compact = text => text.replace(/\s+/g, '');

async function dragMath(page, selector) {
  const formula = page.locator(selector);
  await formula.scrollIntoViewIfNeeded();
  const [start, end] = await formula.evaluate(node => {
    const tokens = [...node.querySelectorAll('.katex-html .mord')];
    return ['a', 'b'].map(letter => {
      const token = tokens.find(item => item.textContent === letter && !item.childElementCount);
      const r = token.getBoundingClientRect();
      return {left: r.left, right: r.right, y: r.y + r.height / 2};
    });
  });
  await page.mouse.move(start.left + .5, start.y);
  await page.mouse.down();
  await page.mouse.move(end.right - .5, end.y, {steps: 16});
  await page.mouse.up();
  assert.equal(compact(await page.evaluate(() => getSelection().toString())), 'a+b');
}

try {
  await mkdir(output, {recursive: true});
  const context = await browser.newContext({viewport: {width: 1100, height: 860}, locale: 'zh-CN'});
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: base});
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/' + route);
  await page.locator(original + ' .katex-html').waitFor();
  await page.evaluate(() => document.fonts.ready);
  const legacy = page.locator('p:has-text("Legacy SVG") mjx-container[jax="HTML"]');
  await legacy.locator('.katex-html .mfrac').waitFor();
  assert.match(await legacy.locator('.katex-html').innerText(), /1/);
  const native = page.locator('p:has-text("Native MathML") math');
  assert.equal(await native.locator('mi').textContent(), 'm');
  assert.equal(await page.locator('.formulaSelectionTools, .formulaSelectionPanel, .formulaSelectionTrigger').count(), 0);
  assert.equal(await page.locator('[data-question-tool="clipper"]').isVisible(), false);

  await dragMath(page, original);
  await page.keyboard.press('Control+c');
  assert.equal(compact(await page.evaluate(() => navigator.clipboard.readText())), 'a+b');
  checks.push('Guest drags across visible formula characters and copies only the selected fragment');

  const archive = page.locator('#clip-archived [data-tex]');
  await archive.locator('mjx-container[jax="HTML"] .katex-html').waitFor();
  await dragMath(page, '#clip-archived [data-tex]');
  checks.push('Stored TeX and unsourced historical SVG render as native selectable HTML');

  await page.locator('#userMenuButton').click();
  await page.locator('#identityButton').click();
  const login = page.locator('#identityDialog');
  await login.locator('input').fill(invite);
  await login.locator('form').evaluate(form => form.requestSubmit());
  await login.waitFor({state: 'hidden'});
  const clipper = page.locator('[data-question-tool="clipper"]');
  if (await clipper.getAttribute('aria-pressed') !== 'true') await clipper.click();
  await page.locator(original + ' .katex-html').waitFor();
  await dragMath(page, original);
  const options = page.locator('.clipperActions');
  await options.getByRole('button', {name: '摘', exact: true}).click();
  const shared = page.frameLocator('.clipperPanel:not([hidden]) .clipperFeatureFrame');
  await shared.locator('#content > *').first().waitFor({state: 'attached', timeout: 75000});
  const frame = await (await page.locator('.clipperPanel:not([hidden]) .clipperFeatureFrame').elementHandle()).contentFrame();
  const saved = await frame.waitForFunction(async () => {
    const view = JSON.parse(await DotNet.invokeMethodAsync('KnowledgeClipper.Browser', 'View'));
    return view.shared.receipt && view.shared.text;
  }, undefined, {timeout: 45000});
  assert.equal(compact(await saved.jsonValue()), 'a+b');
  checks.push('Enabling the clipper preserves the same browser Range and saves only its fragment');

  for (const entry of ['pwa-free-study/', 'pwa-math-courses/']) {
    await page.goto(base + '/' + entry + route);
    await page.evaluate(() => {
      const paragraph = document.createElement('p');
      const formula = document.createElement('span');
      formula.dataset.tex = 'a+b+c';
      const math = document.createElement('mjx-container');
      math.setAttribute('jax', 'SVG');
      formula.append(math);
      paragraph.id = 'pwa-late-formula';
      paragraph.append(formula);
      document.body.append(paragraph);
    });
    await page.locator('#pwa-late-formula .katex-html').waitFor();
  }
  checks.push('Both PWA entrypoints normalize dynamically mounted formulas without a trigger');

  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'formula-selection.json'), JSON.stringify({checks, errors}, null, 2));
  console.log('PASS ' + checks.length + ' native formula selection checks');
} finally {
  await browser.close();
}
