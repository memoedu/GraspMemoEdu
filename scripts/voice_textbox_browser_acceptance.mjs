/** Exercise spoken self-correction through the real streaming service in an isolated website. */
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';

const [fixture, clips, output, base = 'http://127.0.0.1:18978'] = process.argv.slice(2);
assert.ok(['localhost','127.0.0.1'].includes(new URL(base).hostname));
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const browser = await chromium.launch({headless: true, channel:'chrome', args:['--autoplay-policy=no-user-gesture-required']});
const page = await browser.newPage({locale:'zh-CN'});
const errors = [], results = [];
page.on('pageerror', e => errors.push(String(e)));
await page.addInitScript(() => {
  // Compare the capture clock to painted frames, including the device's input latency.
  const fetchRequest = window.fetch;
  window.fetch = function(resource, options) {
    if (String(resource).includes('/api/voice-input/stream') && options?.body && window.liveEvidence) {
      const packet = JSON.parse(options.body);
      if (packet.pcm) {
        const bytes = Uint8Array.from(atob(packet.pcm), c => c.charCodeAt(0));
        if (new Int16Array(bytes.buffer).some(sample => Math.abs(sample)>40)) {
          window.liveEvidence.voicedFrames.push(performance.now());
        }
      }
    }
    return fetchRequest.apply(this, arguments);
  };
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value:async () => {
    const clock = new AudioContext({sampleRate:16000, latencyHint:'interactive', sinkId:{type:'none'}});
    await clock.resume();
    const sink = clock.createMediaStreamDestination();
    window.syntheticMic = {clock, sink};
    return sink.stream;
  }});
});
const button = name => page.getByRole('button',{name, exact:true});
const mic = button('录音输入'), stop = button('结束录音');
async function play(field, first, correction, waitAfterSpeech) {
  const audio = await Promise.all([first, correction].map(name => readFile(path.join(clips,name+'.wav')).then(b => b.toString('base64'))));
  await field.focus();
  await mic.click();
  await stop.waitFor();
  return field.evaluate(async (input, {audio, waitAfterSpeech}) => {
    const {clock,sink} = window.syntheticMic;
    const chunks = [];
    for (const encoded of audio) {
      const raw = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
      const buffer = await clock.decodeAudioData(raw.buffer);
      const data = buffer.getChannelData(0);
      let from = 0, to = data.length;
      while (from<to && Math.abs(data[from])*32768<=40) from++;
      while (to>from && Math.abs(data[to-1])*32768<=40) to--;
      chunks.push({buffer,from:from/buffer.sampleRate,duration:(to-from)/buffer.sampleRate});
    }
    const start = clock.currentTime+.08, startMs = performance.now()+80;
    const correctionStart = start+chunks[0].duration+1.35;
    const t = window.liveEvidence = {firstStart:startMs, firstEnd:startMs+chunks[0].duration*1000,
      correctionStart:startMs+(correctionStart-start)*1000, end:startMs+(correctionStart-start+chunks[1].duration)*1000,
      initial:input.value, changes:[], voicedFrames:[]};
    t.scheduledEnd = t.end;
    input.addEventListener('input', () => { t.committed=performance.now(); }, {once:true});
    let shown = input.value;
    function frame() {
      if (input.value !== shown) { shown=input.value; t.changes.push({at:performance.now(),value:shown}); }
      if (t.committed) { requestAnimationFrame(() => {t.painted=performance.now(); t.final=input.value;}); return; }
      if (performance.now()-startMs<25000) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    chunks.forEach(({buffer,from,duration},i) => {
      const when=i===0?start:correctionStart;
      // Stamp actual audio-graph boundaries. A device's audio clock can drift from wall time,
      // particularly while booting or changing devices. Keep the extrapolated time separately.
      const marker=clock.createConstantSource(); marker.offset.value=0; marker.connect(sink);
      marker.onended=()=>{t[i===0?'firstStart':'correctionStart']=performance.now();};
      marker.start(when); marker.stop(when+1/clock.sampleRate);
      const source = clock.createBufferSource(); source.buffer=buffer; source.connect(sink);
      source.onended=()=>{
        t[i===0?'firstEnd':'end']=performance.now();
        if (i===1) setTimeout(()=>{
          t.stopped=performance.now();
          [...document.querySelectorAll('button')].find(b=>b.textContent==='结束录音' && b.offsetWidth)?.click();
        },waitAfterSpeech);
      };
      source.start(when,from,duration);
    });
  },{audio,waitAfterSpeech});
}
try {
  await page.goto(base+'/#/subjects/math/topic/calculator-fixture');
  await button('下一页').last().waitFor();
  await page.locator('#userMenuButton').click();
  await page.locator('#identityButton').click();
  await page.locator('#invitationCode').fill((await readFile(path.join(fixture,'fixture-invitation.txt'),'utf8')).trim());
  await page.locator('#identitySubmitButton').click();
  await page.locator('#identitySubmitButton').waitFor({state:'hidden'});
  for (const kind of ['calculator','prose']) {
    let input, wanted, replacement, prefix, suffix, clip;
    if (kind==='calculator') {
      await button('下一页').last().click();
      await page.getByRole('toolbar',{name:'题目工具'}).locator('[data-question-tool=expression]').click();
      input = page.locator('.calculatorExpression'); prefix='2*('; suffix=')'; wanted='12+36'; replacement='12+38'; clip='calc';
    } else {
      await page.goto(base+'/#/settings');
      input=page.locator('#profileDisplayName'); prefix='【'; suffix='】'; wanted='周三'; replacement='周五'; clip='prose';
    }
    for (const waitAfterSpeech of [800,32]) {
      await input.fill(prefix+'旧'+suffix);
      await input.evaluate((e,p)=>e.setSelectionRange(p.length,p.length+1),prefix);
      await play(input,clip+'-first',clip+'-repair',waitAfterSpeech);
      await page.waitForFunction(()=>window.liveEvidence?.painted,{},{timeout:28000}).catch(async error=>{
        console.error(JSON.stringify(await page.evaluate(()=>({draft:window.liveEvidence,status:document.querySelector('.voiceToolPanel [role=status]')?.textContent}))));
        throw error;
      });
      const r=await page.evaluate(()=>window.liveEvidence);
      const first=r.changes.find(x=>x.at<r.firstEnd);
      const paused=r.changes.find(x=>x.at<r.correctionStart && x.value.includes(wanted));
      const corrected=r.changes.find(x=>x.at>=r.correctionStart && x.value.includes(replacement) && !x.value.includes(wanted) && !x.value.includes('不对'));
      const row={kind,stop_delay_ms:waitAfterSpeech,first_ms:first && Math.round(first.at-r.firstStart),
        pause_ms:paused && Math.round(Math.max(0,paused.at-r.firstEnd)),
        repair_ms:corrected && Math.round(Math.max(0,corrected.at-r.end)),
        stop_to_paint_ms:Math.round(r.painted-r.stopped),end_to_paint_ms:Math.round(r.painted-r.end),text:r.final,
        capture_first_ms:Math.round(r.voicedFrames[0]-r.firstStart),
        capture_tail_ms:Math.round(r.voicedFrames.at(-1)-r.end),
        audio_clock_drift_ms:Math.round(r.end-r.scheduledEnd),
        updates:r.changes.map(x=>({ms:Math.round(x.at-r.firstStart),text:x.value}))};
      results.push(row);
      console.log(JSON.stringify(row));
      assert.ok(first && paused && corrected && r.final.startsWith(prefix) && r.final.endsWith(suffix),kind);
      assert.ok(r.final.includes(replacement) && !r.final.includes(wanted) && !r.final.includes('不对'));
      if (kind==='prose') assert.ok(r.final.includes('讨论安排在'));
      assert.ok(row.first_ms<1000 && row.pause_ms<1000 && row.repair_ms<1000);
      if (waitAfterSpeech===800) assert.ok(corrected.at<r.stopped);
      else assert.ok(row.end_to_paint_ms<1000 && row.stop_to_paint_ms<1000);
    }
  }
  assert.deepEqual(errors,[]);
} finally {
  await writeFile(output,JSON.stringify(results,null,2));
  await browser.close();
}
