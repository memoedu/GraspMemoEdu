import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';

const [fixture, output, base = 'http://127.0.0.1:18885'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const browser = await chromium.launch({headless: true, channel: 'chrome',
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']});
const context = await browser.newContext({viewport: {width: 390, height: 844}, locale: 'zh-CN', permissions: ['microphone']});
const page = await context.newPage();
const errors = [], calls = [], submissions = [];
let release;
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/training/submit') submissions.push(request.postDataJSON());
});
await page.route('**/api/voice-input/transcribe?*', async route => {
  const body = route.request().postDataJSON(); calls.push(body.profile);
  assert.match(body.mime_type, /^audio\/(mp4|ogg|webm)$/);
  assert.ok(body.data_base64.length > 100);
  const result = await new Promise(resolve => { release = resolve; });
  release = null;
  await route.fulfill({status: result.status || 200, json: result.body});
});
const wait = async condition => {
  for (let i = 0; i < 160; i++) {
    if (await condition()) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.fail('Timed out waiting for condition');
};
const toolbar = page.getByRole('toolbar', {name: '题目工具'});
const mic = page.getByRole('button', {name: '录音输入', exact: true});
const stop = page.getByRole('button', {name: '结束录音', exact: true});
const next = page.getByRole('button', {name: '下一页', exact: true}).last();
const record = async field => {
  await field.focus();
  await mic.click();
  await stop.waitFor();
  await new Promise(resolve => setTimeout(resolve, 290));
};

try {
  await page.goto(base + '/#/subjects/math/topic/calculator-fixture');
  await next.waitFor();
  assert.equal(await mic.count(), 0);
  await page.locator('#userMenuButton').click();
  await page.locator('#identityButton').click();
  await page.locator('#invitationCode').fill((await readFile(path.join(fixture, 'fixture-invitation.txt'), 'utf8')).trim());
  await page.locator('#identitySubmitButton').click();
  await mic.waitFor();
  await next.click();
  await toolbar.getByRole('button', {name: '录音输入', exact: true}).waitFor();
  assert.equal(await mic.count(), 1);
  assert.equal(await page.locator('.topRibbon .voiceTool').count(), 0);
  assert.equal(await toolbar.locator('.toolbarMarker').isVisible(), true);
  await toolbar.locator('[data-question-tool=graph]').press('End');
  assert.equal(await mic.evaluate(button => button === document.activeElement), true);
  await mic.blur();
  await page.screenshot({path: path.join(output, 'question-tools-mobile.png')});
  await page.setViewportSize({width: 1440, height: 900});
  assert.equal(await mic.count(), 1);
  await page.screenshot({path: path.join(output, 'question-tools-desktop.png')});
  await page.setViewportSize({width: 390, height: 844});
  await toolbar.locator('[data-question-tool=expression]').click();
  const calculator = page.locator('.questionCalculator');
  const expression = calculator.getByRole('textbox', {name: '表达式'});
  await expression.fill('1+99');
  await expression.evaluate(field => field.setSelectionRange(2, 4));
  await record(expression);
  await toolbar.locator('[data-question-tool=graph]').click({trial: true});
  await page.getByRole('button', {name: '暂停录音', exact: true}).click();
  await page.getByRole('button', {name: '继续录音', exact: true}).click();
  assert.equal(await calculator.isVisible(), true);
  await stop.click();
  await wait(() => release);
  release({body: {text: '2*3'}});
  await wait(async () => await expression.inputValue() === '1+2*3');
  await page.screenshot({path: path.join(output, 'calculator-and-voice.png')});
  await calculator.getByRole('button', {name: '关闭计算器'}).click();

  await page.goto(base + '/#/subjects/math/banks/isolated-bank/group-a?question=essay');
  const answer = page.locator('#trainingAnswer');
  await answer.waitFor();
  await toolbar.getByRole('button', {name: '录音输入'}).waitFor();
  assert.equal(await mic.count(), 1);
  await page.setViewportSize({width: 320, height: 844});
  await record(answer);
  assert.equal(await toolbar.locator('.voiceToolPanel').evaluate(panel => {
    const {left, right} = panel.getBoundingClientRect();
    return left >= 0 && right <= document.documentElement.clientWidth;
  }), true, 'Question voice controls fit a 320px viewport');
  await page.setViewportSize({width: 390, height: 844});
  const submit = page.locator('#trainingSubmit');
  await submit.click();
  await wait(() => release);
  assert.equal(submissions.length, 0);
  await submit.click();
  release({status: 502, body: {detail: 'fixture transcription failure'}});
  await page.getByRole('button', {name: '重试转写并提交', exact: true}).click();
  await wait(() => release);
  assert.equal(submissions.length, 0);
  release({body: {text: '4'}});
  await wait(() => submissions.length === 1);
  assert.equal(submissions[0].answer, '4');
  await page.goto(base + '/#/settings');
  const displayName = page.locator('#profileDisplayName');
  await displayName.fill('原始');
  assert.equal(await page.locator('#pageTools .voiceTool').count(), 1);
  await record(displayName);
  await stop.click();
  await wait(() => release);
  await displayName.fill('录音后的编辑');
  release({body: {text: '补充'}});
  const insert = page.getByRole('button', {name: '插入转写文字'});
  await insert.waitFor();
  assert.equal(await displayName.inputValue(), '录音后的编辑');
  await displayName.focus();
  await displayName.evaluate(input => input.setSelectionRange(0, 0));
  await insert.click();
  assert.equal(await displayName.inputValue(), '补充录音后的编辑');
  await page.locator('#userMenuButton').click();
  await page.locator('#supportButton').click();
  const feedback = page.locator('.feedbackDialog');
  await feedback.getByRole('toolbar').getByRole('button', {name: '录音输入'}).waitFor();
  assert.equal(await page.locator('.voiceTool').count(), 1);
  await record(feedback.locator('#feedbackMessage'));
  await stop.click();
  await wait(() => release);
  release({body: {text: '反馈草稿'}});
  await wait(async () => await feedback.locator('#feedbackMessage').inputValue() === '反馈草稿');
  await feedback.locator('.dialogHeading button').click();
  await page.locator('#pageTools').getByRole('toolbar').getByRole('button', {name: '录音输入'}).waitFor();
  assert.equal(await page.locator('.voiceTool').count(), 1);
  assert.deepEqual(calls, ['calculator', 'answer', 'answer', 'general', 'general']);
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'voice-browser.json'), JSON.stringify({calls, graded: submissions.length, errors}, null, 2));
} catch (error) {
  await page.screenshot({path: path.join(output, 'voice-browser-failure.png')}).catch(() => {});
  throw error;
} finally {
  await browser.close();
}
