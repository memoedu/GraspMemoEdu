/** Verify local capture, ordered submissions, retry and editing through the supported site UI. */
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {runInNewContext} from 'node:vm';

const [fixture, output, base = 'http://127.0.0.1:18993'] = process.argv.slice(2);
assert.ok(['localhost','127.0.0.1'].includes(new URL(base).hostname));
{
  let Processor;
  const output = [];
  class AudioWorkletProcessor {
    port = {postMessage(data) { output.push(data instanceof ArrayBuffer ? [...new Int16Array(data)] : data); }};
  }
  runInNewContext(await readFile(new URL('../web/voice-pcm.js', import.meta.url), 'utf8'), {
    AudioWorkletProcessor, Int16Array, ArrayBuffer, registerProcessor: (_, type) => { Processor = type; },
  });
  const pcm = new Processor();
  const samples = (...values) => pcm.process([[values.map(x => x/32768)]]);
  const event = data => pcm.port.onmessage({data});
  samples(1,2); event('cut'); samples(3); event('cut'); samples(4);
  event('pause'); samples(99); event('cut'); event('resume'); samples(5); event('finish');
  assert.deepEqual(output,[[1,2],'cut',[3],'cut',[4],'pause','cut','resume',[5],'finish']);
}
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const browser = await chromium.launch({headless: true, channel: 'chrome', args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
const context = await browser.newContext({locale: 'zh-CN', viewport: {width: 390,height: 844}, permissions: ['microphone'], serviceWorkers: 'block'});
const page = await context.newPage();
page.setDefaultTimeout(12000);
const errors = [], evidence = [], uploads = [], replies = [];
let totalMicPermissions = 0, streamingRequests = 0;
await page.addInitScript(() => {
  const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  window.opens = 0;
  navigator.mediaDevices.getUserMedia = opts => { window.opens++; return original(opts); };
});
page.on('pageerror', error => errors.push(error.message));
await page.route(/\/api\/voice-input\/stream(?:\?|$)/, route => { streamingRequests++; return route.abort(); });
await page.route(/\/api\/voice-input\/transcribe(?:\?|$)/, async route => {
  const body = route.request().postDataJSON(), wav = Buffer.from(body.data_base64, 'base64');
  assert.equal(body.segmented,true);
  assert.equal(body.mime_type,'audio/wav');
  assert.equal(wav.length,44+wav.readUInt32LE(40));
  assert.equal(wav.readUInt32LE(24),16000);
  uploads.push({wav, context: body.context});
  const result = await new Promise(resolve => replies.push(resolve));
  await route.fulfill({status: result.status ?? 200, json: result.json});
});
const button = name => page.getByRole('button', {name,exact:true});
const mic = button('录音输入'), cut = button('转写'), end = button('结束录音');
const field = page.locator('#profileDisplayName');
const wait = async (test, label) => {
  for (let n=0; n<100; n++) {
    if (await test()) return;
    await new Promise(resolve => setTimeout(resolve,40));
  }
  assert.fail(label);
};
const value = expected => wait(async () => await field.inputValue()===expected,'unexpected input value');
const upload = n => wait(() => replies.length >= n, 'segment upload');
const reply = (number,text) => replies[number-1]({json:{text}});
async function begin(text, selection) {
  await field.fill(text);
  await field.focus();
  await field.evaluate((el,range)=>el.setSelectionRange(...range),selection);
  await mic.click();
  await end.waitFor();
}
try {
  await page.goto(base+'/#/settings');
  await page.locator('#userMenuButton').click();
  await page.locator('#identityButton').click();
  await page.locator('#invitationCode').fill((await readFile(path.join(fixture,'fixture-invitation.txt'),'utf8')).trim());
  await page.locator('#identitySubmitButton').click();
  await page.locator('#identitySubmitButton').waitFor({state:'hidden'});
  await page.goto(base+'/#/settings');

  await begin('前旧后',[1,2]);
  await page.waitForTimeout(350);
  assert.equal(uploads.length,0);
  assert.equal(await field.inputValue(),'前旧后');
  await cut.click(); await upload(1);
  assert.deepEqual(uploads[0].context.textbox,{before:'前',selected:'旧',after:'后'});
  // Continue speaking while recognition of the first segment waits.
  await page.waitForTimeout(290); await cut.click();
  await page.waitForTimeout(200); await cut.click();
  assert.equal(uploads.length,1);
  await end.waitFor();
  reply(1,'甲'); await value('前甲后'); await upload(2);
  assert.equal(uploads[1].context.textbox.before,'前甲');
  assert.ok(uploads[1].wav.length > 3200);
  replies[1]({status:502,json:{error:{code:'transcription_failed',message:'合成识别失败'}}});
  const retry = button('重试转写'); await retry.waitFor();
  await end.waitFor();
  await retry.click(); await upload(3);
  assert.ok(uploads[2].wav.equals(uploads[1].wav));
  reply(3,'乙'); await upload(4); reply(4,'丙'); await value('前甲乙丙后');
  await page.waitForTimeout(200);
  await end.click(); await upload(5); reply(5,''); await value('前甲乙丙后');
  await retry.waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>window.opens),1);
  evidence.push('local capture, rapid cuts, ordered results, failed segment retry, silent tail');

  await begin('新旧末',[1,2]);
  await page.waitForTimeout(220); await cut.click(); await upload(6);
  await button('取消').click(); reply(6,'迟到结果'); await value('新旧末');
  evidence.push('cancellation and late result rejection');
  totalMicPermissions = await page.evaluate(()=>window.opens);
  assert.equal(streamingRequests,0);
  assert.deepEqual(errors,[]);
  await writeFile(output,JSON.stringify({checks:evidence,uploads:uploads.length,streamingRequests,devices:totalMicPermissions},null,2));
  console.log('PASS',evidence.join('; '));
} finally {
  await browser.close();
}
