import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';

const [output, base = 'http://127.0.0.1:18894'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
await mkdir(output, {recursive: true});
const browser = await chromium.launch({headless: true, channel: 'chrome'});
const context = await browser.newContext({locale: 'zh-CN', viewport: {width: 1280, height: 900},
  permissions: ['clipboard-read', 'clipboard-write']});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.setDefaultTimeout(10000);

try {
  await page.goto(`${base}/#/subjects/math/banks/isolated-bank/group-a?question=essay`);
  const answer = page.locator('.answerForm textarea[name=answer]');
  const surface = page.locator('.answerForm .formulaInput .ProseMirror');
  const menu = page.locator('.inputCompletions');
  const option = label => menu.getByRole('option', {name: label, exact: true});
  await answer.fill('f');
  await option('f').locator('.katex').waitFor();
  await option('floor').locator('.katex').waitFor();
  await answer.press('Tab');
  const math = surface.locator('math-field');
  await math.waitFor();
  assert.equal(await math.evaluate(element => element === document.activeElement), true);
  await page.keyboard.press('x');
  await page.waitForFunction(() => document.querySelector('.answerForm [name=answer]').value.includes('x'));
  assert.match(await answer.inputValue(), /^\\\(f(?:\\left)?\(x(?:\\right)?\)\\\)$/);
  await answer.evaluate(element => element.addEventListener('keydown', event => {
    if (event.ctrlKey && event.key === 'Enter') {
      event.preventDefault(); event.stopImmediatePropagation(); element.dataset.submitShortcut = 'forwarded';
    }
  }, {capture: true, once: true}));
  await page.keyboard.press('Control+Enter');
  assert.equal(await answer.getAttribute('data-submit-shortcut'), 'forwarded');
  await page.screenshot({path: path.join(output, 'function-template.png')});
  await page.keyboard.press('Escape');
  await surface.locator('.is-formula-selected').waitFor();
  await page.keyboard.press('Control+c');
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), await answer.inputValue());
  await page.keyboard.press('Backspace');
  assert.equal(await answer.inputValue(), '');
  await page.keyboard.press('Control+z');
  assert.match(await answer.inputValue(), /f.*x/);
  console.log('PASS first-letter preview, template cursor, clipboard, delete and undo');

  await page.goto(`${base}/#/settings`);
  await page.locator('#userMenuButton').click();
  await page.locator('#supportButton').click();
  const feedback = page.locator('#feedbackMessage');
  await feedback.pressSequentially('Use $\\frac{1}{2}$');
  const form = page.locator('#feedbackMessage').locator('..');
  const composer = form.locator('.formulaInput .ProseMirror:visible');
  await composer.locator('math-field').waitFor();
  assert.equal(await feedback.inputValue(), 'Use $\\frac{1}{2}$');
  await composer.press('Control+End');
  await page.keyboard.type(' a/b');
  for (let i = 0; i < 3; i++) await page.keyboard.press('Shift+ArrowLeft');
  await option('改为分式').locator('.katex').waitFor();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  assert.equal(await feedback.inputValue(), 'Use $\\frac{1}{2}$ \\(\\frac{a}{b}\\)');
  assert.equal(await composer.locator('math-field').count(), 2);
  await page.screenshot({path: path.join(output, 'formula-replacement.png')});
  assert.deepEqual(errors, []);
  console.log('PASS typed LaTeX and range replacement through the shared dropdown');

  await page.locator('dialog[open]').getByRole('button', {name: '取消', exact: true}).click();
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#userMenuButton').click();
  await page.locator('#supportButton').click();
  await page.locator('dialog[open]').getByRole('button', {name: '插入公式', exact: true}).click();
  await composer.locator('math-field').waitFor();
  await page.keyboard.press('x');
  await page.waitForFunction(() => document.querySelector('#feedbackMessage').value === '\\(x\\)');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({path: path.join(output, 'mobile-formula.png')});
  await page.locator('dialog[open]').getByRole('button', {name: '取消', exact: true}).click();
  await page.setViewportSize({width: 1280, height: 900});
  await page.evaluate(async () => {
    const formulaUrl = document.querySelector('link[rel=modulepreload][href*="formula-input.js"]').href;
    const version = new URL(formulaUrl).search;
    const {attachFormulaEditing} = await import(formulaUrl);
    const {attachChatEditor} = await import(`./vendor/chat/chat.js${version}`);
    const input = document.createElement('textarea');
    input.id = 'formula-help-fixture'; input.maxLength = 4000;
    document.body.prepend(input);
    attachChatEditor(input, {editor: '测试答疑编辑器', math: '公式', preview: '预览'}, {attachFormula: attachFormulaEditing});
  });
  await page.locator('.chatEditor .cm-content').click();
  await page.locator('.chatEditor .cm-content').pressSequentially('f');
  await option('f').locator('.katex').waitFor();
  await page.keyboard.press('Tab');
  await page.locator('.chatEditor math-field').waitFor();
  await page.keyboard.press('x');
  await page.waitForFunction(() => /f.*x/.test(document.querySelector('#formula-help-fixture').value));
  await page.locator('.chatEditor').getByRole('button', {name: '预览'}).click();
  await page.locator('.chatEditor .chatPreview .katex').waitFor();
  assert.deepEqual(errors, []);
  console.log('PASS help composer: CodeMirror completion, formula editing and existing Markdown preview');
} catch (error) {
  await page.screenshot({path: path.join(output, 'failure.png')}).catch(() => {});
  console.error(errors);
  throw error;
} finally {
  await browser.close();
}
