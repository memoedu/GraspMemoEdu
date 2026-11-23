import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';

const [fixture, output, base = 'http://127.0.0.1:18886', mode = 'fallback'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const browser = await chromium.launch({headless: true, channel: 'chrome',
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']});
const context = await browser.newContext({viewport: {width: 414, height: 844}, locale: 'zh-CN', permissions: ['microphone']});
if (mode === 'fallback') await context.addInitScript(() => { globalThis.AudioWorkletNode = undefined; });
const page = await context.newPage();
page.setDefaultTimeout(12000);
const errors = [], requests = [];
let respond, transcript = '左二配右二';
let uploads = 0, silence = false;
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  if (request.method() === 'POST') requests.push(new URL(request.url()).pathname);
});
await page.route('**/api/voice-input/transcribe?*', route => {
  assert.equal(route.request().postDataJSON().profile, 'answer_commands');
  assert.equal(route.request().postDataJSON().segmented, true);
  uploads++;
  return route.fulfill({json: {text: silence ? '' : transcript}});
});
const phrase = page.locator('.answerConversion textarea:visible');
const answer = page.locator('#answerInput');
const mic = page.getByRole('button', {name: '录音输入'});
const setting = page.getByRole('checkbox', {name: '显示文字答题框'});
const topicUrl = base + '/#/subjects/math/topic/calculator-fixture';
const nextLesson = page.locator('#stepCard .continueRow .primaryButton:not(#submitButton):enabled');
const mastered = page.locator('#stepCard .choiceActions .primaryButton:enabled', {hasText: '已掌握'});
const submit = page.locator('#submitButton');
const status = page.locator('.answerConversion [role=status]', {hasText: '已填入答题控件'});
const convert = async text => {
  await phrase.fill(text);
  await phrase.press('Control+Enter');
  await status.waitFor();
};
const submitted = () => requests.filter(url => url === '/api/submit' || url === '/api/training/submit').length;
const launch = page.locator('[data-question-tool=expression]:visible');
const calculator = page.locator('.questionCalculator');
const expression = calculator.getByRole('textbox', {name: '表达式'});
const transfer = calculator.getByRole('button', {name: '转换', exact: true});
const record = calculator.getByRole('button', {name: '记录', exact: true});
const closeCalculator = () => calculator.getByRole('button', {name: '关闭计算器'}).click();
async function compute(value) {
  await expression.fill(value);
  assert.ok(await transfer.isDisabled());
  await expression.press('Enter');
  await calculator.locator('.calculatorResult[data-state=success]').getByText(value, {exact: true}).waitFor();
}

try {
  await page.goto(base + '/#/subjects/math/courses');
  await page.locator('#userMenuButton').waitFor();
  await page.locator('#userMenuButton').click();
  await page.locator('#identityButton').click();
  await page.locator('#invitationCode').fill((await readFile(path.join(fixture, 'fixture-invitation.txt'), 'utf8')).trim());
  await page.locator('#identitySubmitButton').click();
  await page.locator('#identitySubmitButton').waitFor({state: 'hidden'});
  assert.equal(await mic.count(), 0);
  await page.goto(topicUrl);
  await openCurrentAnswer();
  assert.equal(await page.locator('.answerConversion textarea').count(), 0);
  await recordMiddlePair();
  assert.equal(JSON.parse(await answer.inputValue())[1].right, 'r2');
  assert.equal(submitted(), 0);
  await setCommandInput(true);
  await page.goto(topicUrl);
  await mic.waitFor();
  await convert('左边第一个连右边第三个，左边第二个连右边第二个，左边第三个连右边第一个');
  const complete = JSON.parse(await answer.inputValue());
  assert.deepEqual(complete.map(pair => pair.right), ['r3', 'r2', 'r1']);
  await phrase.fill('左一配右一，左三配右三');
  await page.locator('.answerConversion').getByRole('button', {name: '转换', exact: true}).click();
  await status.waitFor();
  assert.deepEqual(JSON.parse(await answer.inputValue()).map(pair => pair.right), ['r1', 'r2', 'r3']);
  const middle = page.locator('.matchingSlot[data-side=right][data-row="1"]');
  await middle.click();
  assert.equal(JSON.parse(await answer.inputValue())[1].right, null);
  await recordMiddlePair();
  assert.equal(submitted(), 0);

  await convert('左一配右三，左三配右一');
  await submit.click();
  await nextLesson.click();
  await openCurrentAnswer();
  const blanks = page.locator('.inlineBlank[data-blank-id]');
  await page.locator('#stepCard h2:visible').first().click();
  transcript = '第二个空填 7，第三个空填负4。';
  await speak();
  await page.waitForFunction(() => document.querySelector('[data-blank-id=b3]').value === '-4');
  assert.deepEqual(await blanks.evaluateAll(nodes => nodes.map(el => el.value)), ['', '7', '-4', '', '']);
  await page.setViewportSize({width: 1366, height: 900});
  await launch.click();
  for (const [index, value] of ['11', '22', '33', '44', '55'].entries()) {
    await compute(value);
    await transfer.click();
    assert.equal(await blanks.nth(index).inputValue(), value);
  }
  assert.ok(await transfer.isDisabled());
  await closeCalculator();
  await blanks.nth(2).click();
  await launch.click();
  await compute('66');
  assert.ok(await blanks.nth(2).evaluate(el => getComputedStyle(el.closest('.calculatorSelectedBlank')).outlineStyle === 'solid'));
  await transfer.click();
  await compute('77');
  await transfer.click();
  assert.equal(await blanks.nth(2).inputValue(), '77');
  await blanks.nth(3).click();
  await compute('88');
  await transfer.click();
  assert.equal(await blanks.nth(3).inputValue(), '88');
  assert.equal(await blanks.nth(2).evaluate(el => Boolean(el.closest('.calculatorSelectedBlank'))), false);
  await closeCalculator();
  await page.locator('#stepCard h2:visible').first().click();
  transcript = '第三个空填 9，然后第二个空填 -6。';
  await speak();
  await page.waitForFunction(() => document.querySelector('[data-blank-id=b2]').value === '-6');
  assert.deepEqual(JSON.parse(await answer.inputValue()), {b1: '11', b2: '-6', b3: '9', b4: '88', b5: '55'});
  await convert('1，2，3，4，5');
  const blank = page.locator('.inlineBlank[data-blank-id=b3]');
  assert.equal(await blank.inputValue(), '3');
  await blank.fill('30');
  await convert('第四空填 40');
  assert.deepEqual(JSON.parse(await answer.inputValue()), {b1: '1', b2: '2', b3: '30', b4: '40', b5: '5'});
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 844});
    assert.equal(await phrase.evaluate(el => {
      const {left, right} = el.getBoundingClientRect();
      return left >= 0 && right <= innerWidth && document.documentElement.scrollWidth <= innerWidth;
    }), true, String(width));
  }
  await page.screenshot({path: path.join(output, 'five-blanks.png')});
  assert.equal(submitted(), 1);

  await page.goto(base + '/#/subjects/math/banks/isolated-bank/group-a?question=choice');
  await phrase.waitFor();
  await page.locator('h2:visible').first().click();
  assert.equal(await mic.count(), 0);
  await convert('3');
  assert.equal(await page.locator('.choiceOption input:checked').inputValue(), 'b');
  assert.equal(requests.filter(url => url === '/api/answer-conversion').length, 0);
  for (const [question, text, selected] of [['one-value', '3', 'a'], ['two-values', '3，5', 'b']]) {
    await page.goto(base + '/#/subjects/math/banks/isolated-bank/group-a?question=' + question);
    await convert(text);
    assert.equal(await page.locator('.choiceOption input:checked').inputValue(), selected);
  }
  assert.equal(requests.filter(url => url === '/api/answer-conversion').length, 2);

  const choiceUrl = base + '/#/subjects/math/banks/isolated-bank/group-a?question=one-value';
  await setCommandInput(false);
  await page.goto(choiceUrl);
  await page.locator('.choiceOption input[value=b]').check();
  assert.equal(await page.locator('.answerConversion textarea').count(), 0);
  await launch.click();
  await expression.fill('1+2');
  await expression.press('Enter');
  await calculator.locator('.calculatorResult').getByText('3', {exact: true}).waitFor();
  await transfer.click();
  await calculator.locator('.calculatorTransferStatus[data-state=success]').waitFor();
  await closeCalculator();
  assert.equal(await page.locator('.choiceOption input:checked').inputValue(), 'a');
  assert.equal(submitted(), 1);

  await page.goto(base + '/#/subjects/math/banks/isolated-bank/group-a?question=three-values');
  await launch.click();
  await compute('-2'); await record.click();
  await compute('8'); await record.click();
  await calculator.getByRole('button', {name: '撤回末值'}).click();
  await compute('0'); await record.click();
  await compute('7'); await transfer.click();
  await calculator.locator('.calculatorTransferStatus[data-state=error]').waitFor();
  assert.match(await calculator.locator('.calculatorRecorded').innerText(), /-2，0/);
  await compute('8'); await transfer.click();
  await calculator.locator('.calculatorTransferStatus[data-state=success]').waitFor();
  assert.equal(await page.locator('.choiceOption input:checked').inputValue(), 'a');
  assert.equal(await calculator.locator('.calculatorRecorded').textContent(), '');
  await closeCalculator();

  await setCommandInput(true);
  await page.goto(choiceUrl);
  await page.route('**/api/answer-conversion?*', async route => {
    await new Promise(resolve => { respond = resolve; });
    await route.fulfill({json: {commands: [1]}}).catch(() => {});
  });
  await phrase.fill('变量的数值是三');
  await phrase.press('Control+Enter');
  await page.getByRole('button', {name: '转换中…', exact: true}).waitFor();
  await page.locator('.choiceOption input[value=b]').check();
  await expectRequest();
  respond();
  await page.getByText('答题内容已修改，请重新转换。', {exact: true}).waitFor();
  assert.equal(await page.locator('.choiceOption input:checked').inputValue(), 'b');
  respond = null;
  await phrase.press('Control+Enter');
  await expectRequest();
  await page.evaluate(() => { location.hash = '#/subjects/math/banks/isolated-bank/group-a?question=choice'; });
  await phrase.waitFor();
  await page.locator('.choiceOption').filter({hasText: '2'}).waitFor();
  respond();
  assert.equal(await page.locator('.choiceOption input:checked').inputValue(), 'b');
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'browser.json'), JSON.stringify({
    matching: true, partialMatching: true, fiveBlanks: true, numericChoice: true,
    assignmentApi: true, syntheticMicrophone: true, sparseAndReversedSpeech: true,
    sequentialAndPinnedBlanks: true, recordedTriple: true, failedTransferKeepsRecords: true, calculator: true,
    commandInputDefaultOff: true, preferenceSurvivesReload: true, microphoneAndCalculatorWithBoxOff: true,
    widths: [320, 375, 414, 768], protectedDrafts: true, deliberateSubmissions: submitted(), errors,
  }, null, 2));
} catch (error) {
  await page.screenshot({path: path.join(output, 'browser-failure.png')}).catch(() => {});
  throw error;
} finally {
  await browser.close();
}

async function expectRequest() {
  for (let attempt = 0; attempt < 80 && !respond; attempt++) await new Promise(resolve => setTimeout(resolve, 50));
  assert.equal(typeof respond, 'function');
}

async function openCurrentAnswer() {
  const editorOrChoice = submit.or(mastered);
  await editorOrChoice.or(nextLesson).first().waitFor();
  if (!(await editorOrChoice.count())) {
    await nextLesson.click();
    await editorOrChoice.first().waitFor();
  }
  if (!(await submit.isVisible())) await mastered.click();
  await submit.waitFor();
}

async function setCommandInput(enabled) {
  await page.goto(base + '/#/settings');
  await setting.waitFor();
  assert.equal(await setting.isChecked(), !enabled);
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 844});
    assert.ok(await setting.evaluate(el => {
      const bounds = el.closest('label').getBoundingClientRect();
      return bounds.left >= 0 && bounds.right <= innerWidth && el.getBoundingClientRect().width > 0;
    }), 'Settings label fits at ' + width);
  }
  await setting.setChecked(enabled);
  await page.locator('.profileForm button[type=submit]').click();
  await page.locator('.profileStatus').getByText('设置已保存。').waitFor();
  await page.reload();
  await setting.waitFor();
  assert.equal(await setting.isChecked(), enabled);
}

async function speak() {
  const initial = await answer.inputValue(), conversions = requests.filter(p => p === '/api/answer-conversion').length;
  const initialUploads = uploads;
  silence = false;
  await mic.click();
  const stop = page.getByRole('button', {name: '结束录音', exact: true});
  await stop.waitFor();
  await page.waitForTimeout(350);
  assert.equal(uploads, initialUploads);
  await page.getByRole('button', {name: '转写', exact: true}).click();
  for (let n = 0; n < 50 && uploads === initialUploads; n++) await page.waitForTimeout(50);
  assert.equal(uploads, initialUploads + 1);
  assert.equal(await answer.inputValue(), initial);
  assert.equal(requests.filter(p => p === '/api/answer-conversion').length, conversions);
  assert.ok(!requests.includes('/api/voice-input/stream'));
  silence = true;
  await stop.click();
}
async function recordMiddlePair() {
  await speak();
  await page.locator('.matchingSlot[data-side=right][data-row="1"]', {hasText: 'R2'}).waitFor();
}
