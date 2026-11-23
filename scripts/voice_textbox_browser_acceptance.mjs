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
  output.length = 0;
  const fresh = new Processor();
  fresh.process([[new Float32Array(960).fill(0.5)]]);
  assert.deepEqual(output.map(frame => frame.length), [160,800]);
}
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
// Chromium's default fake microphone emits intermittent beeps. A continuous
// fixture makes time to the first non-silent frame independent of beep timing.
const rate = 16000, wav = Buffer.alloc(44 + 2 * rate);
wav.write('RIFF', 0); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(rate, 24); wav.writeUInt32LE(2 * rate, 28); wav.writeUInt16LE(2, 32);
wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(wav.length - 44, 40);
for (let n=0; n<rate; n++) {
  const t = n / rate;
  wav.writeInt16LE(Math.round(10000 * Math.sin(2 * Math.PI * (220 * t + 40 * t * t))), 44 + 2 * n);
}
const signal = path.resolve(path.dirname(output), 'voice-acceptance-signal.wav');
await writeFile(signal, wav);
const browser = await chromium.launch({headless: true, channel: 'chrome',
  args: ['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+signal]});
const context = await browser.newContext({locale: 'zh-CN', viewport: {width: 390,height: 844}, permissions: ['microphone'], serviceWorkers: 'block'});
const page = await context.newPage();
page.setDefaultTimeout(12000);
const errors = [], evidence = [], uploads = [], replies = [];
let totalMicPermissions = 0, streamingRequests = 0;
await page.addInitScript(() => {
  const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  window.opens = 0; window.audioSetups = 0; window.micMeasurements = [];
  navigator.mediaDevices.getUserMedia = async opts => {
    window.opens++;
    const media = await original(opts);
    window.micTrack = media.getAudioTracks()[0];
    return media;
  };
  const Context = AudioContext, Processor = AudioWorkletNode;
  window.AudioContext = class extends Context {
    constructor(...args) { super(...args); window.audioSetups++; }
  };
  window.AudioWorkletNode = class extends Processor {
    constructor(...args) {
      super(...args);
      const measurement = window.micMeasurements.at(-1);
      const first = ({data}) => {
        if (!(data instanceof ArrayBuffer) || !new Int16Array(data).some(value => value !== 0)) return;
        measurement.firstPcmMs = performance.now() - measurement.click;
        this.port.removeEventListener('message', first);
      };
      this.port.addEventListener('message', first);
    }
  };
  document.addEventListener('click', event => {
    if (event.target.closest('button[aria-label="录音输入"]')) window.micMeasurements.push({click: performance.now()});
  }, true);
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
  const edits = [];
  await page.exposeFunction('captureSegmentEdit', value => edits.push(value));
  await field.evaluate(node => node.addEventListener('input', () => window.captureSegmentEdit(node.value)));
  await page.waitForTimeout(1080);
  const timer = page.locator('.voiceDuration:visible');
  assert.match(await timer.innerText(), /01 秒/);
  assert.equal(uploads.length,0);
  assert.equal(await field.inputValue(),'前旧后');
  await cut.click(); await upload(1);
  assert.match(await timer.innerText(), /00 秒/);
  assert.deepEqual(uploads[0].context.textbox,{before:'前',selected:'旧',after:'后'});
  // Continue speaking while recognition of the first segment waits.
  await page.waitForTimeout(290); await cut.click();
  await page.waitForTimeout(200); await cut.click();
  assert.equal(uploads.length,1);
  await end.waitFor();
  reply(1,'甲'); await value('前甲后'); await upload(2);
  assert.deepEqual(edits,['前甲后'], 'first completed segment emitted a real input event');
  assert.equal(uploads[1].context.textbox.before,'前甲');
  assert.ok(uploads[1].wav.length > 3200);
  replies[1]({status:502,json:{error:{code:'transcription_failed',message:'合成识别失败'}}});
  const retry = button('重试转写'); await retry.waitFor();
  await end.waitFor();
  await retry.click(); await upload(3);
  assert.ok(uploads[2].wav.equals(uploads[1].wav));
  reply(3,'乙'); await upload(4); reply(4,'丙'); await value('前甲乙丙后');
  assert.deepEqual(edits,['前甲后','前甲乙后','前甲乙丙后']);
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
  assert.equal(totalMicPermissions,1);
  assert.equal(streamingRequests,2,'only the failed connection attempt occurred on each take');
  assert.deepEqual(await page.evaluate(()=>[window.micTrack.enabled,window.audioSetups]),[false,1]);

  async function changeHash(hash) {
    const state = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/api/state') &&
      new URL(response.url()).searchParams.get('topic_id') === 'calculator-fixture');
    await page.evaluate(value => { location.hash = value; }, hash);
    await state;
    await button('下一页').last().waitFor();
  }
  await changeHash('#/subjects/math/topic/calculator-fixture');
  await page.waitForFunction(() => window.micTrack.readyState === 'ended');
  await page.evaluate(() => {
    const field = document.createElement('textarea');
    field.id = 'segment-topic-acceptance';
    document.querySelector('#appLayout').append(field);
  });
  const topicField = page.locator('#segment-topic-acceptance');
  const micTrials = [];
  for (let take=0; take<6; take++) {
    if (take === 3) {
      await page.waitForTimeout(3400);
      await changeHash('#/subjects/math/topic/calculator-fixture?node=canary');
    }
    await topicField.focus();
    await mic.click();
    await page.waitForFunction(() => Number.isFinite(window.micMeasurements.at(-1).firstPcmMs));
    micTrials.push(await page.evaluate(() => window.micMeasurements.at(-1).firstPcmMs));
    await button('取消').click();
    await page.waitForFunction(() => window.micTrack.enabled === false);
  }
  assert.deepEqual(await page.evaluate(()=>[window.opens,window.audioSetups]),[2,2]);
  assert.ok(micTrials.slice(1).every(ms => ms < 100), JSON.stringify(micTrials));
  evidence.push('same Topic microphone reuse, release on navigation, click-to-first-PCM under 100 ms');
  assert.deepEqual(errors,[]);
  await writeFile(output,JSON.stringify({checks:evidence,uploads:uploads.length,streamingRequests,
    devices:await page.evaluate(()=>window.opens), topicClickToFirstPcmMs:micTrials},null,2));
  console.log('PASS',evidence.join('; '));
} finally {
  await browser.close();
}
