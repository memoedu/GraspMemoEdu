import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [output, base = 'http://127.0.0.1:18894'] = process.argv.slice(2);
assert.equal(new URL(base).hostname, '127.0.0.1', 'Use the isolated question-bank fixture');
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
await mkdir(output, {recursive: true});
const browser = await launchAcceptanceChrome(require);
const context = await browser.newContext({locale: 'zh-CN', viewport: {width: 1280, height: 900},
  permissions: ['clipboard-read', 'clipboard-write']});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.setDefaultTimeout(10000);

try {
  const cold = await browser.newContext();
  try {
    await cold.route('**/vendor/formula/editor.mjs*', async route => {
      await new Promise(resolve => setTimeout(resolve, 200));
      await route.continue();
    });
    const tab = await cold.newPage();
    await tab.goto(base + '/#/subjects/math/banks/isolated-bank/group-a?question=essay');
    const field = tab.locator('.answerForm [name=answer]');
    await field.pressSequentially('\\frac{3}{7}');
    const formula = tab.locator('.answerForm math-field');
    await formula.waitFor();
    await tab.keyboard.type('+2');
    await tab.waitForFunction(() => document.querySelector('.answerForm [name=answer]').value === '\\frac{3}{7}+2');
    assert.equal(await formula.evaluate(m => m === document.activeElement), true);
    assert.match(await formula.evaluate(m => m.getValue('math-ml')), /<mo>\+<\/mo><mn>2<\/mn>/);
  } finally { await cold.close(); }
  console.log('PASS uninterrupted keyboard input through a cold formula editor mount');
  await page.goto(`${base}/#/subjects/math/banks/isolated-bank/group-a?question=essay`);
  const answer = page.locator('.answerForm textarea[name=answer]');
  const surface = page.locator('.answerForm .formulaInput .ProseMirror');
  const menu = page.locator('.inputCompletions');
  const option = label => menu.getByRole('option', {name: label, exact: true});
  const math = surface.locator('math-field');
  async function typeAnswer(text) {
    await answer.fill('');
    await answer.pressSequentially(text);
  }
  async function clearRich(root) {
    if (await root.evaluate(el => el.contains(document.activeElement) && document.activeElement.localName === 'math-field'))
      await page.keyboard.press('Escape');
    await root.focus();
    await page.keyboard.press('Control+a');
    await page.keyboard.press('Backspace');
    await root.locator('math-field').waitFor({state: 'detached'});
    await page.waitForFunction(el => !el.textContent.trim() && document.activeElement === el, await root.elementHandle());
  }
  async function checkRendered(field, root, source, expectedTag, stored) {
    if (await root.isVisible()) await clearRich(root);
    else { await field.fill(''); await field.focus(); }
    await page.keyboard.type(source);
    const formula = root.locator('math-field');
    await formula.waitFor();
    await page.waitForFunction(({id, tag, stored}) => {
      const input = document.querySelector(id);
      return input.value === stored && input.parentElement.querySelector('math-field')?.getValue('math-ml').includes('<' + tag + '>');
    }, {id: '.answerForm textarea[name=answer]', tag: expectedTag, stored});
    assert.equal(await field.isVisible(), false);
    assert.equal(await root.locator('.katex').count(), 0);
    assert.equal(await page.locator('.answerFormulaPreview').count(), 0);
    return formula;
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
  await clearRich(surface);
  assert.equal(await answer.inputValue(), '');
  await page.reload();
  await answer.waitFor();
  await typeAnswer('f(');
  await math.waitFor();
  await page.waitForFunction(() => document.activeElement.localName === 'math-field');
  await page.keyboard.type('x)');
  await page.waitForFunction(() => document.querySelector('.answerForm [name=answer]').value === 'f(x)');
  assert.equal(await menu.isVisible(), false);
  await checkRendered(answer, surface, 'sin(cos(x))', 'mrow', 'sin(cos(x))');
  await checkRendered(answer, surface, 'a_{10}', 'msub', 'a_{10}');
  await checkRendered(answer, surface, 'x^12', 'msup', 'x^{12}');
  await checkRendered(answer, surface, '\\frac{1}{2}', 'mfrac', '\\frac{1}{2}');
  await checkRendered(answer, surface, '3/7', 'mfrac', '3/7');
  const fraction = math.locator('.ML__mfrac');
  await fraction.waitFor();
  // Place the caret on each rendered digit and replace it from the keyboard.
  for (const [digit, replacement] of [['3', '5'], ['7', '9']]) {
    const point = await page.waitForFunction(([field, digit]) => {
      const glyph = [...field.shadowRoot.querySelectorAll('.ML__mfrac span')].find(el =>
        !el.childElementCount && el.textContent === digit && el.getBoundingClientRect().width);
      const rect = glyph?.getBoundingClientRect();
      return rect?.height && {x: rect.x + rect.width * .85, y: rect.y + rect.height / 2};
    }, [await math.elementHandle(), digit]);
    const {x, y} = await point.jsonValue();
    await page.mouse.click(x, y);
    await page.waitForFunction(field => document.activeElement === field, await math.elementHandle());
    await page.keyboard.press('Shift+ArrowLeft');
    await page.keyboard.type(replacement);
  }
  await page.waitForFunction(() => document.querySelector('.answerForm [name=answer]').value === '5/9');
  assert.equal(await math.evaluate(e => e.getValue('math-ml')), '<mfrac><mn>5</mn><mn>9</mn></mfrac>');
  assert.equal(await math.evaluate(e => e === document.activeElement), true);
  await page.screenshot({path: path.join(output, 'inline-answer.png')});
  console.log('PASS directly editing the rendered numerator and denominator in the single answer field');
  await clearRich(surface);
  assert.equal(await answer.inputValue(), '');
  await page.reload();
  await answer.waitFor();
  await answer.fill('f');
  await option('f').locator('.katex').waitFor();
  await option('floor').locator('.katex').waitFor();
  await answer.press('Tab');
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
  await clearRich(surface);
  const mixed = '已知 \\frac{\\text{distance}}{t}，求速度。';
  await page.evaluate(text => navigator.clipboard.writeText(text), mixed);
  await page.keyboard.press('Control+v');
  await math.locator('.ML__mfrac').waitFor();
  assert.equal(await answer.inputValue(), mixed);
  assert.equal(await answer.isVisible(), false);
  assert.equal(await surface.evaluate(el => el.innerText.includes('\\frac')), false);
  assert.match(await surface.innerText(), /已知[\s\S]*求速度/);
  await page.reload();
  await surface.locator('math-field .ML__mfrac').waitFor();
  assert.equal(await answer.inputValue(), mixed);
  console.log('PASS paste and restored mixed-prose draft render directly in the answer');

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
  await clearRich(composer);
  await page.evaluate(() => navigator.clipboard.writeText('\\sqrt{y}'));
  await page.keyboard.press('Control+v');
  await composer.locator('math-field').waitFor();
  assert.equal(await feedback.inputValue(), '\\(\\sqrt{y}\\)');

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
  assert.equal(await page.locator('.chatEditor .formulaInput').isVisible(), false);
  await page.locator('.chatEditor').getByRole('button', {name: '预览'}).click();
  assert.equal(await page.locator('.chatEditor math-field').isVisible(), true);
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
  assert.equal(await literal.inputValue(), '5000');
  assert.equal(await menu.isVisible(), false);
  const exactRoot = literal.locator('..').locator('.formulaInput .ProseMirror').first();
  await checkRendered(literal, exactRoot, 'x^12', 'msup', 'x^12');
  await checkRendered(literal, exactRoot, 'a_i+1', 'msub', 'a_{i+1}');
  const command = page.locator('.answerConversion textarea');
  await command.pressSequentially('f');
  await option('f').waitFor();
  await command.press('Tab');
  const commandMath = page.locator('.answerConversion math-field');
  await commandMath.waitFor();
  await page.keyboard.type('y)');
  await page.waitForFunction(() => document.querySelector('.answerConversion textarea').value === 'f(y)');
  assert.equal(await command.isVisible(), false);
  assert.equal(await literal.inputValue(), 'a_{i+1}');
  const [response] = await Promise.all([
    page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/submit')),
    page.locator('#trainingSubmit').click(),
  ]);
  assert.ok(response.ok(), String(response.status()));
  assert.equal(response.request().postDataJSON().answer, 'a_{i+1}');
  await page.goto(bank + 'blank');
  const blank = page.locator('.passageBlankText').first();
  await blank.pressSequentially('2/3');
  const blankRoot = blank.locator('..').locator('.formulaInput .ProseMirror');
  await blankRoot.locator('math-field .ML__mfrac').waitFor();
  await page.waitForFunction(() => document.querySelector('.passageBlankText').value === '2/3');
  assert.deepEqual(JSON.parse(await page.locator('.answerForm [name=answer]').inputValue()), {a: '2/3'});
  await clearRich(blankRoot);
  await page.keyboard.type('example');
  assert.equal(await blank.inputValue(), 'example');
  assert.equal(await blankRoot.locator('math-field').count(), 0);
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 844});
    await clearRich(blankRoot);
    await page.keyboard.type('f');
    await option('floor').locator('.katex-html').waitFor();
    const bounds = await menu.boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  }
  assert.deepEqual(errors, []);
  console.log('PASS exact, command and passage inputs, original payloads and responsive rendered suggestions');
} catch (error) {
  await page.screenshot({path: path.join(output, 'failure.png')}).catch(() => {});
  console.error(errors, await page.evaluate(() => ({focus: document.activeElement.localName, field: document.querySelector('.answerForm [name=answer]')?.value, math: [...document.querySelectorAll('math-field')].map(m => [m.value, m.getValue('math-ml'),m.position])})));
  throw error;
} finally {
  await browser.close();
}
