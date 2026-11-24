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
const checks = [];
const expected = String.raw`a+b+c+\frac{x+1}{y-2}`;
const errors = [];

try {
  await mkdir(output, {recursive: true});
  for (const mobile of [false, true]) {
    const context = await browser.newContext({locale: 'zh-CN',
      viewport: mobile ? {width: 390, height: 844} : {width: 1100, height: 860},
      hasTouch: mobile, isMobile: mobile,
    });
    try {
      await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: base});
      const page = await context.newPage();
      page.setDefaultTimeout(12000);
      page.on('pageerror', error => errors.push(error.message));
      const trigger = page.getByRole('button', {name: '选取公式片段', exact: true});
      const panel = page.locator('.formulaSelectionPanel');
      const formula = page.locator('#clip-fragment [data-math-source]');
      const editor = panel.locator('math-field');
      const copy = panel.getByRole('button', {name: '复制 LaTeX', exact: true});
      const clipboard = () => page.evaluate(() => navigator.clipboard.readText());
      await page.goto(base + '/#/subjects/math/topic/synthetic-course');
      await formula.waitFor();
      await page.evaluate(() => document.fonts.ready);
      await formula.scrollIntoViewIfNeeded();
      const hit = await formula.evaluate(node => [...node.getClientRects()]
        .filter(rect => rect.width && rect.height && rect.bottom > 0 && rect.top < innerHeight)
        .sort((a, b) => b.width - a.width)[0].toJSON());
      if (mobile) await page.touchscreen.tap(hit.x + hit.width / 2, hit.y + hit.height / 2);
      else await page.mouse.move(hit.x + hit.width / 2, hit.y + hit.height / 2);
      await trigger.click();
      await editor.waitFor();
      assert.equal(await editor.evaluate(node => node.readOnly), true);
      await copy.click();
      await panel.getByRole('status').getByText('已复制').waitFor();
      assert.equal(await clipboard(), expected);
      checks.push(mobile ? 'Mobile tap opens a selectable formula and copies full LaTeX' :
        'Whole-formula LaTeX copy works before login');

      if (mobile) {
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await page.screenshot({path: path.join(output, 'mobile-formula-selection.png')});
        continue;
      }

      async function dragB() {
        await page.evaluate(() => document.fonts.ready);
        assert.equal(await editor.evaluate(node => node.value), expected);
        await page.waitForFunction(() => [...(document.querySelector('.formulaSelectionPanel math-field')?.shadowRoot
          ?.querySelectorAll('span') || [])].some(child => !child.children.length &&
          child.textContent === 'b' && child.getClientRects().length));
        const rect = await editor.evaluate(node => {
          const glyph = [...node.shadowRoot.querySelectorAll('span')]
            .find(child => !child.children.length && child.textContent === 'b' && child.getClientRects().length);
          const {left, right, top, height} = glyph.getBoundingClientRect();
          return {left, right, y: top + height / 2};
        });
        await page.mouse.move(rect.left + 1, rect.y);
        await page.mouse.down();
        await page.mouse.move(rect.right - 1, rect.y, {steps: 10});
        await page.mouse.up();
        assert.equal(await editor.evaluate(node => node.getValue(node.selection, 'latex')), 'b');
      }

      await dragB();
      await page.keyboard.press('Control+c');
      await page.waitForFunction(async () => await navigator.clipboard.readText() === 'b');
      await page.keyboard.press('Escape');
      await panel.waitFor({state: 'hidden'});
      await trigger.focus();
      await page.keyboard.press('Enter');
      await editor.waitFor();
      await page.keyboard.press('Shift+ArrowRight');
      await page.keyboard.press('Shift+ArrowRight');
      await copy.click();
      await page.waitForFunction(async () => await navigator.clipboard.readText() === 'a+');
      checks.push('Mouse drag and Shift+arrow copy only the selected MathLive subexpression');

      await page.keyboard.press('Escape');
      for (const [selector, pattern] of [
        ['p:has-text("Legacy SVG") mjx-container', /\\frac\{1\}\{2\}/],
        ['p:has-text("Native MathML") math', /\{m\}\^\{3\}/],
      ]) {
        await page.locator(selector).dblclick();
        await editor.waitFor();
        await copy.click();
        await panel.getByRole('status').getByText('已复制').waitFor();
        assert.match(await clipboard(), pattern);
        await page.keyboard.press('Escape');
      }
      checks.push('Legacy SVG and native MathML use the same formula selector');

      await page.locator('#userMenuButton').click();
      await page.locator('#identityButton').click();
      const login = page.locator('#identityDialog');
      await login.locator('input').fill(invite);
      await login.locator('form').evaluate(form => form.requestSubmit());
      await login.waitFor({state: 'hidden'});
      const clipper = page.locator('[data-question-tool="clipper"]');
      if (await clipper.getAttribute('aria-pressed') !== 'true') await clipper.click();
      await page.waitForResponse(response => response.url().endsWith('/api/clipper/settings'), {timeout: 7000}).catch(() => {});
      await formula.scrollIntoViewIfNeeded();
      const original = await formula.boundingBox();
      await page.mouse.dblclick(original.x + original.width / 2, original.y + original.height / 2);
      await editor.waitFor();
      await dragB();
      await panel.getByRole('button', {name: '摘录', exact: true}).click();
      const frameHandle = await page.locator('.clipperPanel:not([hidden]) .clipperFeatureFrame').elementHandle();
      const frame = await frameHandle.contentFrame();
      await frame.locator('#content > *').first().waitFor({state: 'attached', timeout: 75000});
      const source = await frame.waitForFunction(async () => {
        const view = JSON.parse(await DotNet.invokeMethodAsync('KnowledgeClipper.Browser', 'View'));
        return view.shared.receipt && view.shared.text;
      }, undefined, {timeout: 45000});
      assert.equal(await source.jsonValue(), String.raw`\(b\)`);
      const article = frame.locator('article').first();
      await frame.locator('.formulaSelectionTools').waitFor({state: 'attached'});
      await article.locator('.katex').first().hover();
      await frame.getByRole('button', {name: '选取公式片段', exact: true}).click();
      await frame.locator('.formulaSelectionPanel math-field').waitFor();
      await frame.getByRole('button', {name: '关闭', exact: true}).click();
      await page.locator('.clipperDock').getByRole('button', {name: '关闭', exact: true}).click();
      checks.push('Shared clipper saves only the selected formula fragment and reuses the selector inside its frame');
    } finally {
      await context.close();
    }
  }
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'formula-selection.json'), JSON.stringify({checks, errors}, null, 2));
  console.log(`PASS ${checks.length} formula selection checks`);
} finally {
  await browser.close();
}
