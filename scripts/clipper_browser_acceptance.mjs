import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';

const [output, fixture, base = 'http://127.0.0.1:18891'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const [first, second] = JSON.parse(await readFile(path.join(fixture, 'browser-fixtures.json'), 'utf8'));
await mkdir(output, {recursive: true});
const browser = await chromium.launch({headless: true, channel: 'chrome'});
const errors = [], checks = [];
const context = await browser.newContext({viewport: {width: 1280, height: 900}, locale: 'zh-CN'});
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
  await main.locator(css).evaluate((node, entire) => {
    const selection = getSelection(), range = document.createRange();
    if (entire) range.selectNode(node);
    else range.selectNodeContents(node);
    selection.removeAllRanges();
    selection.addRange(range);
  }, element);
  await chooser.waitFor();
}

async function open(label, css, element = false) {
  await select(css, element);
  const event = popup ? null : main.waitForEvent('popup');
  await chooser.getByRole('button', {name: label, exact: true}).click();
  if (event) popup = await event;
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

  const phrase = await main.locator(phraseSelector).boundingBox();
  await main.mouse.move(phrase.x + 2, phrase.y + phrase.height / 2);
  await main.mouse.down();
  await main.mouse.move(phrase.x + 90, phrase.y + phrase.height / 2, {steps: 12});
  await main.mouse.up();
  await chooser.waitFor();
  checks.push('native drag exposes actions');
  await main.evaluate(() => getSelection().removeAllRanges());
  await main.locator(formulaSelector).hover();
  await main.keyboard.press('Alt+Shift+s');
  await chooser.waitFor();
  await main.keyboard.press('Alt+Shift+c');
  assert.equal(await main.evaluate(() => document.activeElement.textContent), '卡');
  checks.push('keyboard selects a formula and focuses actions');

  await open('摘', formulaSelector, true);
  await popup.getByRole('button', {name: '保存摘录'}).click();
  await popup.getByText('已存入个人自由学习。', {exact: true}).waitFor();
  assert.match(await popup.locator('.clipperSource').innerHTML(), /x\^2/);
  assert.equal(Math.round((await popup.locator(workspace).boundingBox()).y), 0);
  checks.push('formula-only excerpt uses original LaTeX');
  for (const width of [320, 375, 414, 768]) {
    await popup.setViewportSize({width, height: 660});
    assert.ok(await popup.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'horizontal overflow at ' + width);
  }
  await popup.screenshot({path: path.join(output, 'clipper-excerpt.png')});
  await popup.getByRole('button', {name: '在当前页置顶', exact: true}).click({timeout: 8000}).catch(error => {
    if (!popup.isClosed()) throw error;
  });
  const dock = main.locator('.clipperDock:popover-open');
  await dock.waitFor();
  await main.mouse.click(24, 250);
  await main.mouse.wheel(0, 400);
  assert.ok(await dock.isVisible());
  await dock.getByRole('button', {name: '最小化', exact: true}).click();
  assert.equal(await dock.locator('.clipperPanel').isVisible(), false);
  await dock.getByRole('button', {name: '恢复', exact: true}).click();
  const reopened = main.waitForEvent('popup');
  await dock.getByRole('button', {name: '普通窗口', exact: true}).click();
  popup = await reopened;
  await popup.getByText('已存入个人自由学习。', {exact: true}).waitFor();
  checks.push('topmost dock survives page interaction and preserves content on minimize and popout');

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
  await main.goto(base + '/#/free-study');
  await main.getByRole('button', {name: '翻看背面'}).click();
  await main.getByText('Fixture back for review').waitFor();
  await main.getByRole('button', {name: '良好', exact: true}).click();
  await main.getByText('目前没有到期的个人卡片。').waitFor();
  await main.getByRole('button', {name: '摘录', exact: true}).click();
  await main.locator('.clipperLibraryItem').waitFor();
  for (const label of ['导出今天', '导出全部']) {
    const download = main.waitForEvent('download');
    await main.getByRole('button', {name: label}).click();
    const file = await download;
    const markdown = await readFile(await file.path(), 'utf8');
    assert.match(markdown, /\$x\^2\$/);
  }
  await main.screenshot({path: path.join(output, 'free-study-clips.png')});
  checks.push('site FSRS review and both RemNote markdown downloads');

  const closed = popup.waitForEvent('close');
  await account(second);
  await closed;
  assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
  await main.getByRole('button', {name: '摘录', exact: true}).click();
  await main.getByText('这里还没有内容。').waitFor();
  checks.push('account switch closes personal workspace and isolates items');
  assert.deepEqual(errors, []);
  console.log('PASS', checks.length, 'browser checks');
} finally {
  await writeFile(path.join(output, 'clipper-browser.json'), JSON.stringify({checks, errors}, null, 2));
  await browser.close();
}
