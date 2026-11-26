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

async function dragMath(page, selector, reverse = false) {
  const formula = page.locator(selector);
  await formula.evaluate(node => node.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'}));
  await page.evaluate(() => getSelection().removeAllRanges());
  const [start, end] = await formula.evaluate(node => {
    const tokens = [...node.querySelectorAll('.katex-html .mord')];
    return ['a', 'b'].map((letter, offset) => {
      const text = tokens.find(item => item.textContent === letter && !item.childElementCount).firstChild;
      const range = document.createRange();
      range.selectNodeContents(text);
      const box = range.getBoundingClientRect();
      for (const fraction of [.22, .12, .35, 0, -.10]) {
        const x = Math.round(box.left + box.width * (offset ? 1 - fraction : fraction));
        const y = Math.round(box.top + box.height / 2);
        const hit = document.caretRangeFromPoint(x, y);
        if (hit?.startContainer === text && hit.startOffset === offset) return {x, y};
      }
      throw new Error('Browser cannot place a caret at the selected glyph boundary');
    });
  });
  const [from, to] = reverse ? [end, start] : [start, end];
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, {steps: 16});
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
  const fullFormula = await page.locator(original).evaluate(async node => {
    const {captureSelection} = await import(document.querySelector('script[src*="app.js"]').src.replace('app.js', 'clipper-selection.js'));
    const range = document.createRange();
    range.selectNode(node);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    return captureSelection(range, document.querySelector('#lessonContent')).text;
  });
  await page.keyboard.press('Control+c');
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), fullFormula);
  assert.match(fullFormula, /\\frac\{x\+1\}\{y-2\}/);
  await page.evaluate(() => navigator.clipboard.writeText('before visible formula copy'));
  await page.locator(original + ' .katex-html').evaluate(visible => {
    // KaTeX uses these characters for geometry in archived display formulas.
    visible.prepend(document.createTextNode('\u200b'));
    visible.append(document.createTextNode('\u200b'));
    const walker = document.createTreeWalker(visible, NodeFilter.SHOW_TEXT);
    const glyphs = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      for (const match of node.data.matchAll(/[^\s\p{Cf}]/gu)) {
        glyphs.push({node, start: match.index, end: match.index + match[0].length});
      }
    }
    const first = glyphs[0], last = glyphs.at(-1), range = document.createRange();
    range.setStart(first.node, first.start);
    range.setEnd(last.node, last.end);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
  });
  await page.keyboard.press('Control+c');
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), fullFormula);
  checks.push('Selecting every visible glyph produces LaTeX even when KaTeX inserts invisible edge characters');

  const [prose, glyph] = await page.locator('#clip-fragment').evaluate(node => {
    node.scrollIntoView({block: 'center', behavior: 'instant'});
    const token = [...node.querySelectorAll('.katex-html .mord')].find(item => item.textContent === 'a' && !item.childElementCount);
    const caret = (text, offset) => {
      const range = document.createRange();
      range.setStart(text, Math.max(0, offset - 1));
      range.setEnd(text, Math.max(1, offset));
      const box = range.getBoundingClientRect(), y = box.top + box.height / 2;
      const edge = offset ? box.right : box.left;
      for (const delta of [0, -.5, .5, -1, 1, -2, 2]) {
        const hit = document.caretRangeFromPoint(edge + delta, y);
        if (hit?.startContainer === text && hit.startOffset === offset) return [edge + delta, y];
      }
      throw new Error('Could not locate the selection boundary');
    };
    return [caret(node.firstChild, 0), caret(token.firstChild, 1)];
  });
  for (const [from, to] of [[prose, glyph], [glyph, prose]]) {
    await page.mouse.move(...from);
    await page.mouse.down();
    await page.mouse.move(...to, {steps: 16});
    await page.mouse.up();
    assert.match(await page.evaluate(() => getSelection().toString()), /Formula fragment/);
    await page.keyboard.press('Control+c');
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), 'Formula fragment ' + fullFormula);
  }
  checks.push('A drag from prose into a formula preserves the LaTeX in either selection direction');

  await page.evaluate(() => {
    window.competingCopyWrites = 0;
    window.competingCopy = event => {
      window.competingCopyWrites++;
      event.clipboardData.setData('text/plain', 'Rendered text\na\nb');
      event.preventDefault();
    };
    document.addEventListener('copy', window.competingCopy);
  });
  try {
    await page.keyboard.press('Control+a');
    await page.keyboard.press('Control+c');
    const all = await page.evaluate(() => navigator.clipboard.readText());
    assert(all.includes(fullFormula));
    assert.doesNotMatch(all, /\n{3,}|PRIVATE_HIDDEN_FIXTURE|Rendered text/);
    assert.equal(await page.evaluate(() => window.competingCopyWrites), 0);
  } finally {
    await page.evaluate(() => document.removeEventListener('copy', window.competingCopy));
  }
  checks.push('Whole formulas and Select All copy structured LaTeX as plain text using the excerpt serializer');
  checks.push('A later document copy handler cannot overwrite the LaTeX written for learning content');

  const archive = page.locator('#clip-archived [data-tex]');
  await archive.locator('mjx-container[jax="HTML"] .katex-html').waitFor();
  await dragMath(page, '#clip-archived [data-tex]');
  checks.push('Stored TeX and unsourced MathJax 3 SVG render as native selectable HTML');

  for (const [selector, display] of [['#clip-v2-inline .mjpage', false], ['#clip-v2-display .mjpage', true]]) {
    const math = page.locator(selector);
    await math.locator('.katex-html .mfrac').waitFor();
    assert.equal(await math.locator('.katex-display').count(), Number(display));
    if (display) {
      assert.equal(await math.locator('.katex-html [style*="border-color: lightgray"]').count(), 1);
      assert.match(await math.locator('.katex-html').innerText(), /#1/);
    }
    await dragMath(page, selector, display);
    await page.keyboard.press('Control+c');
    assert.equal(compact(await page.evaluate(() => navigator.clipboard.readText())), 'a+b');
  }
  assert.equal(await page.locator('#clip-non-formula path').count(), 1);
  checks.push('Inline and display MathJax 2 archives support native partial copy in both directions');
  const sharedSource = page.locator('#clip-shared-math-source .katex-html');
  await sharedSource.nth(1).waitFor();
  assert.deepEqual((await sharedSource.allTextContents()).map(compact), ['a', '+b']);
  checks.push('Separate formulas keep their own source when sharing a wrapper');

  const outline = page.locator('#clip-outline-only mjx-container[jax=HTML]');
  await outline.locator('.katex-html .mfrac').waitFor();
  assert.match(compact(await outline.locator('.katex-html').innerText()), /^a\+b\+c\+/);
  await dragMath(page, '#clip-outline-only');
  await page.keyboard.press('Control+c');
  assert.equal(compact(await page.evaluate(() => navigator.clipboard.readText())), 'a+b');
  assert.equal(await page.locator('#clip-unknown-outline mjx-container[jax=SVG] path').count(), 2);
  checks.push('Known path-only math preserves glyphs and supports partial copy; unknown glyphs keep their SVG');

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
  let saved;
  const deadline = Date.now() + 45000;
  while (!saved && Date.now() < deadline) {
    saved = await frame.evaluate(async () => {
      const view = JSON.parse(await DotNet.invokeMethodAsync('KnowledgeClipper.Browser', 'View'));
      return view.shared.receipt && view.shared.text;
    });
    if (!saved) await new Promise(resolve => setTimeout(resolve, 200));
  }
  assert.equal(typeof saved, 'string', 'Expected a saved text excerpt');
  assert.equal(compact(saved), 'a+b');
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
