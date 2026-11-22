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
  const live = answer.locator('..').locator('.answerFormulaPreview:visible');
  async function typeAnswer(text) {
    await answer.fill('');
    await answer.pressSequentially(text);
  }
  async function checkInk(source, stored, expected) {
    await typeAnswer(source);
    await live.locator('.katex-html').waitFor();
    await page.waitForFunction(([selector, expression]) =>
      document.querySelector(selector)?.textContent === expression,
    ['.answerForm [name=answer] + .answerFormulaPreview annotation', expected]);
    assert.equal(await answer.inputValue(), stored);
  }
  for (const prefix of ['f', 'F']) {
    await typeAnswer(prefix);
    await option('f').waitFor();
    await option('floor').waitFor();
    assert.deepEqual(await menu.getByRole('option').evaluateAll(rows => rows.map(row =>
      [row.querySelector('.completionFormula').ariaLabel, row.querySelectorAll('.katex').length,
        row.innerText === row.querySelector('.katex-html').innerText])),
    [['f', 1, true], ['frac', 1, true], ['floor', 1, true]]);
  }
  for (const prefix of ['x', 'X', '5000']) {
    await typeAnswer(prefix);
    assert.equal(await menu.isVisible(), false);
    assert.equal(await answer.inputValue(), prefix);
  }
  await typeAnswer('x!');
  await option('!').waitFor();
  assert.equal(await option('!').innerText(), '!');
  await answer.press('Tab');
  await surface.locator('math-field').waitFor();
  assert.equal(await surface.locator('math-field').evaluate(math => math.value), 'x!');
  assert.equal(await answer.inputValue(), '\\(x!\\)');
  await surface.press('Control+a');
  await surface.press('Backspace');
  assert.equal(await answer.inputValue(), '');
  await page.reload();
  await answer.waitFor();
  await typeAnswer('f(');
  assert.equal(await answer.inputValue(), 'f()');
  assert.equal(await answer.evaluate(input => input.selectionEnd), 2);
  await answer.pressSequentially('x)');
  assert.equal(await answer.inputValue(), 'f(x)');
  assert.equal(await menu.isVisible(), false);
  await checkInk('sin(cos(x))', 'sin(cos(x))', '\\sin \\left(\\cos \\left(x\\right)\\right)');
  await checkInk('a_{10}', 'a_{10}', 'a_{10}');
  await checkInk('x^12', 'x^{12}', 'x^{12}');
  await checkInk('\\frac{1}{2}', '\\frac{1}{2}', '\\frac{1}{2}');
  await checkInk('3/7', '3/7', '\\frac{3}{7}');
  await page.screenshot({path: path.join(output, 'direct-answer-preview.png')});
  await answer.press('Tab');
  await surface.locator('math-field').waitFor();
  assert.equal(await surface.locator('math-field').evaluate(math => math.value), '\\frac{3}{7}');
  assert.equal(await answer.inputValue(), '3/7');
  console.log('PASS direct answer rendering, native pairs and scripts, truthful previews and saved spelling');
  await surface.press('Control+a');
  await surface.press('Backspace');
  assert.equal(await answer.inputValue(), '');
  await page.reload();
  await answer.waitFor();
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

  await page.reload();
  await page.goto(base + '/#/settings');
  await page.getByRole('checkbox', {name: '显示文字答题框'}).check();
  await page.locator('.profileForm button[type=submit]').click();
  await page.locator('.profileStatus').getByText('设置已保存。').waitFor();
  const bank = base + '/#/subjects/math/banks/isolated-bank/group-a?question=';
  await page.goto(bank + 'exact');
  const literal = page.locator('.answerForm textarea[name=answer]');
  await literal.fill('5000');
  await literal.locator('..').locator('.katex-html').waitFor();
  assert.equal(await literal.inputValue(), '5000');
  assert.equal(await menu.isVisible(), false);
  await literal.fill('');
  await literal.pressSequentially('x^12');
  assert.equal(await literal.inputValue(), 'x^12');
  await literal.locator('..').locator('.katex .msupsub').waitFor();
  await literal.fill('');
  await literal.pressSequentially('a_i+1');
  assert.equal(await literal.inputValue(), 'a_{i+1}');
  const command = page.locator('.answerConversion textarea:visible');
  await command.pressSequentially('f');
  await option('f').waitFor();
  await command.press('Tab');
  await command.pressSequentially('y)');
  assert.equal(await command.inputValue(), 'f(y)');
  await command.locator('..').locator('.katex-html').waitFor();
  assert.equal(await literal.inputValue(), 'a_{i+1}');
  await page.goto(bank + 'blank');
  const blank = page.locator('.passageBlankText:visible').first();
  await blank.pressSequentially('2/3');
  await blank.locator('..').locator('.katex .mfrac').waitFor();
  assert.equal(await blank.inputValue(), '2/3');
  assert.deepEqual(JSON.parse(await page.locator('.answerForm [name=answer]').inputValue()), {a: '2/3'});
  await blank.fill('example');
  assert.equal(await blank.locator('..').locator('.answerFormulaPreview').isVisible(), false);
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 844});
    await blank.fill('');
    await blank.pressSequentially('f');
    await option('floor').locator('.katex-html').waitFor();
    const bounds = await menu.boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  }
  assert.deepEqual(errors, []);
  console.log('PASS exact, command and passage inputs, original payloads and responsive rendered suggestions');
} catch (error) {
  await page.screenshot({path: path.join(output, 'failure.png')}).catch(() => {});
  console.error(errors);
  throw error;
} finally {
  await browser.close();
}
