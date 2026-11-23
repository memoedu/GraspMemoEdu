import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [output, fixture, base = 'http://127.0.0.1:18891'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const [first, second] = JSON.parse(await readFile(path.join(fixture, 'browser-fixtures.json'), 'utf8'));
await mkdir(output, {recursive: true});
const engine = process.env.CLIPPER_BROWSER || 'chrome';
const mobile = process.env.CLIPPER_MOBILE === '1';
const fallback = process.env.CLIPPER_FALLBACK === '1';
const inPage = mobile || fallback;
const browser = engine === 'chrome' ? await launchAcceptanceChrome(require) : await require('playwright')[engine].launch();
const errors = [], checks = [];
const desktopSize = {width: 1280, height: 900}, mobileSize = {width: 390, height: 844};
const context = await browser.newContext({viewport: mobile ? mobileSize : desktopSize, locale: 'zh-CN',
  ...(mobile ? {hasTouch: true, isMobile: true} : {})});
context.setDefaultTimeout(14000);
if (fallback) await context.addInitScript(() => {
  const matches = Element.prototype.matches;
  const find = Document.prototype.querySelectorAll;
  const supports = CSS.supports.bind(CSS);
  const invalid = () => { throw new DOMException('Selector is not implemented', 'SyntaxError'); };
  Element.prototype.matches = function (selector) { return selector === ':popover-open' ? invalid() : matches.call(this, selector); };
  Document.prototype.querySelectorAll = function (selector) { return selector === 'dialog:modal' ? invalid() : find.call(this, selector); };
  CSS.supports = (...args) => args[0] === 'selector(dialog:modal)' ? false : supports(...args);
  Object.defineProperty(HTMLElement.prototype, 'showPopover', {value: undefined});
  Object.defineProperty(window, 'open', {value: () => null});
});
await context.addInitScript(() => {
  const sampleVoice = {name: 'Local fixture voice', localService: true, lang: 'en-US'};
  Object.defineProperty(window, 'SpeechSynthesisUtterance', {value: class {
    constructor(text) { this.text = text; }
  }});
  Object.defineProperty(window, 'speechSynthesis', {value: {
    getVoices: () => [sampleVoice],
    speak: utterance => { window.fixtureSpeech = {text: utterance.text, language: utterance.voice.lang}; },
    cancel: () => {},
  }});
});
const main = await context.newPage();
context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
main.on('pageerror', error => errors.push(error.message));
const toggle = main.locator('[data-question-tool="clipper"]');
const chooser = main.locator('.clipperActions');
const workspace = '.clipperWorkspace';
const route = base + '/#/subjects/math/topic/synthetic-course';
const phraseSelector = 'p:has-text("Capture the sequence")';
const formulaSelector = phraseSelector + ' [data-tex]';
const inlineSelector = 'p:has-text("Inline")';
let popup = null;

async function account(invite) {
  await main.locator('#userMenuButton').click();
  await main.locator('#identityButton').click();
  const login = main.locator('#identityDialog');
  await login.locator('input').fill(invite);
  await login.locator('form').evaluate(form => form.requestSubmit());
  await login.waitFor({state: 'hidden'});
  await toggle.waitFor();
}

async function select(css, element = false) {
  const target = main.locator(css);
  await target.scrollIntoViewIfNeeded();
  await target.evaluate((node, entire) => {
    const selection = getSelection(), range = document.createRange();
    if (entire) range.selectNode(node);
    else range.selectNodeContents(node);
    selection.removeAllRanges();
    selection.addRange(range);
  }, element);
  await chooser.waitFor();
}

async function open(label, css, element = false) {
  if (inPage && popup) await main.getByRole('button', {name: '最小化', exact: true}).click();
  await select(css, element);
  const event = popup || inPage ? null : main.waitForEvent('popup');
  await chooser.getByRole('button', {name: label, exact: true}).click();
  if (event) popup = await event;
  if (inPage) popup = main;
  await popup.locator(workspace).waitFor();
  return popup;
}

try {
  await main.goto(route);
  await main.locator(phraseSelector).waitFor();
  assert.equal(await toggle.isVisible(), false);
  await account(first);
  assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
  await toggle.click();
  assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
  assert.equal(await chooser.isVisible(), false);

  if (mobile) await main.locator(formulaSelector).tap();
  else {
    const phrase = await main.locator(phraseSelector).boundingBox();
    await main.mouse.move(phrase.x + 2, phrase.y + phrase.height / 2);
    await main.mouse.down();
    await main.mouse.move(phrase.x + 90, phrase.y + phrase.height / 2, {steps: 12});
    await main.mouse.up();
  }
  await chooser.waitFor();
  checks.push(mobile ? 'touch formula exposes actions' : 'native drag exposes actions');
  if (!mobile) {
    await main.evaluate(() => getSelection().removeAllRanges());
    await main.locator(formulaSelector).hover();
    await main.keyboard.press('Alt+Shift+s');
    await chooser.waitFor();
    await main.keyboard.press('Alt+Shift+c');
    await main.waitForFunction(() => document.activeElement.matches('.clipperActions button:first-child'), undefined, {timeout: 4000});
    checks.push('keyboard selects a formula and focuses actions');
  }

  await open('摘', formulaSelector, true);
  await popup.getByRole('button', {name: '保存摘录'}).click();
  await popup.getByText('已存入个人自由学习。', {exact: true}).waitFor();
  assert.match(await popup.locator('.clipperSource').innerHTML(), /x\^2/);
  if (!inPage) assert.equal(Math.round((await popup.locator(workspace).boundingBox()).y), 0);
  checks.push('formula-only excerpt uses original LaTeX');
  await popup.waitForFunction(() => [...document.querySelectorAll('link[data-clipper-styles]')]
    .filter(link => /\/clipper\.css\b/.test(link.href)).every(link => link.sheet));
  for (const width of [320, 375, 414, 768]) {
    await popup.setViewportSize({width, height: 660});
    const size = await popup.evaluate(() => new Promise(resolve => requestAnimationFrame(() =>
      requestAnimationFrame(() => resolve({
        viewport: innerWidth, root: document.documentElement.scrollWidth,
        body: document.body.scrollWidth, mode: document.compatMode,
        workspace: Math.round(document.querySelector('.clipperWorkspace').getBoundingClientRect().right),
      })))));
    assert.ok(size.root <= size.viewport, `horizontal overflow at ${width}: ${JSON.stringify(size)}`);
  }
  await popup.screenshot({path: path.join(output, 'clipper-excerpt.png')});
  if (inPage) await main.setViewportSize(mobile ? mobileSize : desktopSize);
  else await popup.getByRole('button', {name: '在当前页置顶', exact: true}).click({timeout: 8000}).catch(error => {
    if (!popup.isClosed()) throw error;
  });
  const dock = main.locator(fallback ? '.clipperDock' : '.clipperDock:popover-open');
  await dock.waitFor();
  if (mobile) {
    await main.touchscreen.tap(24, 250);
    await main.evaluate(() => window.scrollBy(0, 400));
  } else {
    await main.mouse.click(24, 250);
    await main.mouse.wheel(0, 400);
  }
  assert.ok(await dock.isVisible());
  if (!inPage && engine === 'chrome') {
    await dock.evaluate(element => Object.assign(element.style, {width: '465px', height: '385px'}));
    const available = await main.evaluate(() => ({width: document.body.getBoundingClientRect().width, height: innerHeight}));
    await dock.getByRole('button', {name: '铺满标签页', exact: true}).click();
    const expanded = await dock.boundingBox();
    assert.ok(expanded.width >= available.width - 1 && expanded.height >= available.height - 1);
    await dock.getByRole('button', {name: '还原', exact: true}).click();
    assert.equal(Math.round((await dock.boundingBox()).width), 465);
    await dock.getByRole('button', {name: '最小化', exact: true}).click();
    assert.ok((await dock.boundingBox()).height < 120);
    await dock.getByRole('button', {name: '恢复', exact: true}).click();
    assert.equal(Math.round((await dock.boundingBox()).height), 385);
    checks.push('dock fills and minimizes after resize and restores the chosen size');
  }
  await dock.getByRole('button', {name: '最小化', exact: true}).click();
  assert.equal(await dock.locator('.clipperPanel').isVisible(), false);
  await dock.getByRole('button', {name: '恢复', exact: true}).click();
  if (!inPage) {
    const reopened = main.waitForEvent('popup');
    await dock.getByRole('button', {name: '普通窗口', exact: true}).click();
    popup = await reopened;
  }
  await popup.getByText('已存入个人自由学习。', {exact: true}).waitFor();
  checks.push('dock survives page interaction and preserves the workspace on minimize and restore');

  for (const [selector, expected] of [
    ['p:has-text("Legacy SVG") mjx-container', '\\frac{1}{2}'],
    ['p:has-text("Native MathML") math', '{m}^{3}'],
  ]) {
    await open('摘', selector, true);
    await popup.getByRole('button', {name: '保存摘录'}).click();
    await popup.getByText('已存入个人自由学习。', {exact: true}).waitFor();
    await popup.waitForFunction(tex => [...document.querySelectorAll('.clipperSource [data-math-source]')]
      .some(formula => formula.dataset.mathSource.includes(tex)), expected, {timeout: 9000});
  }
  checks.push('legacy SVG and native MathML remain selectable without stored LaTeX');

  await open('卡', inlineSelector);
  await popup.getByRole('button', {name: '选区加入正面'}).click();
  assert.match(await popup.getByLabel('正面', {exact: true}).inputValue(), /\\frac\{a\}\{b\}/);
  await popup.getByLabel('背面', {exact: true}).fill('Fixture back for review');
  await popup.getByRole('button', {name: '保存卡片'}).click();
  await popup.getByText('已存入个人自由学习。', {exact: true}).waitFor();
  await popup.getByLabel('提问', {exact: true}).fill('Why does this work?');
  await popup.getByRole('button', {name: '发送', exact: true}).click();
  await popup.getByText('Fixture response: Why does this work?').waitFor();
  await popup.getByRole('button', {name: '整合为卡片'}).click();
  await popup.getByText('Fixture generated front').waitFor();
  checks.push('manual card, routed chat, multi-card candidate response');

  await open('问', phraseSelector);
  await popup.getByText('Fixture response: 请解释所选内容。').waitFor();
  checks.push('quick question invoked once');

  await open('读', phraseSelector);
  await popup.getByRole('button', {name: '查询词义'}).click();
  await popup.getByText('Fixture meaning: sequence').waitFor();
  await popup.getByRole('button', {name: '朗读选区'}).click();
  const spoken = await main.evaluate(() => window.fixtureSpeech);
  assert.equal(spoken.language, 'en-US');
  assert.match(spoken.text, /Capture the sequence/);
  checks.push('meaning lookup and local speech synthesis handoff');
  if (inPage) await main.getByRole('button', {name: '最小化', exact: true}).click();
  await main.goto(base + '/#/free-study');
  await main.getByRole('button', {name: '翻看背面'}).click();
  await main.getByText('Fixture back for review').waitFor();
  await main.getByRole('button', {name: '良好', exact: true}).click();
  await main.getByText('目前没有到期的个人卡片。').waitFor();
  await main.getByRole('button', {name: '摘录', exact: true}).click();
  await main.locator('.clipperLibraryItem').first().waitFor();
  for (const label of ['导出今天', '导出全部']) {
    const download = main.waitForEvent('download');
    await main.getByRole('button', {name: label}).click();
    const file = await download;
    const markdown = await readFile(await file.path(), 'utf8');
    assert.match(markdown, /\$x\^2\$/);
    assert.match(markdown, /\$\\frac\{1\}\{2\}\$/);
  }
  await main.screenshot({path: path.join(output, 'free-study-clips.png')});
  checks.push('site FSRS review and both RemNote markdown downloads');

  const closed = inPage ? null : popup.waitForEvent('close');
  await account(second);
  if (closed) await closed;
  else await main.locator(workspace).waitFor({state: 'detached'});
  assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
  await main.getByRole('button', {name: '摘录', exact: true}).click();
  await main.getByText('这里还没有内容。').waitFor();
  checks.push('account switch closes personal workspace and isolates items');
  assert.deepEqual(errors, []);
  console.log('PASS', checks.length, 'browser checks');
} finally {
  await writeFile(path.join(output, 'clipper-browser.json'), JSON.stringify({engine, mobile, fallback, checks, errors}, null, 2));
  await browser.close();
}
