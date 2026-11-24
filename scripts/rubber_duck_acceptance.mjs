import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [base, invitationFile, audioDirectory, output, mode] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const browser = await launchAcceptanceChrome(require, ['--autoplay-policy=no-user-gesture-required']);
const desktop = await browser.newContext({locale: 'zh-CN', viewport: {width: 1366, height: 900}});
const mobile = await browser.newContext({locale: 'zh-CN', viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});

const cases = {
  wrong: '极差是最大值和最小值相加。',
  shallow: '平均数就是把所有数据加起来，然后除以数据的个数。',
  branches: '极差等于最大值减最小值。极端值一般会明显影响平均数，但是对中位数的影响较小。',
  rest: '例如，二、四、六的平均数是四。中位数要先把数据从小到大排列，奇数个数取中间的一个，偶数个数取中间两个的平均数。众数是出现次数最多的数，并列时可以有多个众数。',
  triangle: '直角三角形的两条直角边的平方和等于斜边的平方。比如直角边是三和四，三的平方加四的平方是二十五，斜边就是五。',
  linear: '纵截距是横坐标等于零时的函数值，也就是直线和纵轴交点的纵坐标。',
};
const audio = Object.fromEntries(await Promise.all(Object.keys(cases).map(async key =>
  [key, (await readFile(path.join(audioDirectory, key + '.wav'))).toString('base64')])));
const invitation = (await readFile(invitationFile, 'utf8')).trim();
const code = invitation.startsWith('{') ? JSON.parse(invitation).advanced : invitation;
const evidence = [], errors = [];
const home = new URL('rubber-duck-test.html', base).href;

try {
  for (const context of [desktop, mobile]) {
    await context.addInitScript(() => {
      Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {value: async () => {
        const clock = new AudioContext({sampleRate: 16000, sinkId: {type: 'none'}});
        await clock.resume();
        const sink = clock.createMediaStreamDestination();
        window.testMicrophone = {clock, sink};
        return sink.stream;
      }});
    });
  }
  const run = async (context, isMobile) => {
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    let clip;
    const operations = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.endsWith('/voice-input/stream') && request.method() === 'POST') {
        operations.push(request.postDataJSON().op);
      }
    });
    if (mode === 'fixture-asr') {
      let offset = 0;
      await context.route('**/api/voice-input/stream**', async route => {
        const body = route.request().postDataJSON();
        if (body.op === 'open') { offset = 0; assert.equal(body.live, true); }
        else offset += Buffer.from(body.pcm || '', 'base64').length;
        await route.fulfill({json: {offset, ...(body.op === 'audio' && {preview: cases[clip]}),
          ...(body.op === 'finish' && {text: cases[clip]})}});
      });
    }
    page.setDefaultTimeout(35000);
    await Promise.all([
      page.waitForResponse(response => new URL(response.url()).pathname === '/api/profile' && response.ok()),
      page.goto(base),
    ]);
    await page.locator('#userMenuButton').click();
    await page.locator('#identityButton').click();
    await page.locator('#invitationCode').fill(code);
    await page.locator('#identitySubmitButton').click();
    await page.locator('#identitySubmitButton').waitFor({state: 'hidden'});
    await page.goto(home);
    const panel = page.locator('.duckExercise');
    await panel.waitFor();
    const shown = () => panel.locator('[data-kind=point]').evaluateAll(nodes => nodes.map(n => n.dataset.nodeId));
    const progress = () => panel.locator('.duckProgress').innerText();
    const waitProgress = async text => page.waitForFunction(value => document.querySelector('.duckProgress')?.textContent === value, text);
    const say = async (key, expected, pause = false) => {
      clip = key;
      await panel.getByRole('button', {name: /开始录音|继续录音/}).click();
      await panel.getByRole('button', {name: '暂停录音'}).waitFor();
      if (pause) {
        await panel.getByRole('button', {name: '暂停录音'}).click();
        assert.equal(await panel.locator('.duckStatus').innerText(), '录音已暂停');
        await panel.getByRole('button', {name: '继续录音'}).click();
      }
      const playback = page.evaluate(async encoded => {
        const {clock, sink} = window.testMicrophone;
        const data = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
        const source = clock.createBufferSource();
        source.buffer = await clock.decodeAudioData(data.buffer);
        source.connect(sink);
        await new Promise(resolve => { source.onended = resolve; source.start(); });
      }, audio[key]);
      await page.waitForFunction(() => document.querySelector('.duckSpoken')?.textContent.trim());
      assert.ok(await panel.locator('.duckSpoken').isVisible(), 'live transcript is visible before Convert');
      await playback;
      try {
        await panel.getByRole('button', {name: '转换', exact: true}).click();
      } catch (error) {
        console.error(key, await progress(), await panel.locator('.duckStatus').textContent(), operations.slice(-6));
        throw error;
      }
      assert.match(await panel.locator('.duckStatus').innerText(), /录音已暂停|要点/);
      await waitProgress(expected);
      await page.waitForFunction(() => !document.querySelector('.duckStatus')?.textContent.includes('正在'));
      evidence.push({clip: key, progress: await progress(), visible: await shown()});
      console.log(key, await progress(), (await shown()).join(','));
    };
    if (isMobile) {
      await page.goto(new URL('./#/subjects/math/banks/rubber-duck-qa/outline?question=linear', base).href);
      await panel.waitFor();
      await say('linear', '已展开 1 / 3');
      assert.deepEqual(await shown(), ['axis']);
      await page.screenshot({path: path.join(output, 'mobile.png'), fullPage: true});
    } else {
      assert.deepEqual(await shown(), []);
      assert.equal(await panel.locator('[data-kind=heading]').count(), 6);
      assert.equal(await panel.locator('input, textarea, [contenteditable]').count(), 0);
      await say('wrong', '已展开 0 / 7', true);
      await say('shallow', '已展开 1 / 7');
      assert.deepEqual(await shown(), ['mean-rule']);
      await say('branches', '已展开 3 / 7');
      assert.deepEqual(await shown(), ['mean-rule', 'range-rule', 'outlier-effect']);
      await page.reload();
      await waitProgress('已展开 3 / 7');
      await say('rest', '已展开 7 / 7');
      await panel.getByText('已讲清全部要点。', {exact: true}).waitFor();
      assert.equal(await panel.getByRole('button', {name: '转换', exact: true}).isVisible(), false);
      await page.screenshot({path: path.join(output, 'desktop.png'), fullPage: true});
      await page.goto(new URL('./#/subjects/math/banks/rubber-duck-qa/outline?question=right-triangle', base).href);
      await waitProgress('已展开 0 / 3');
      await say('triangle', '已展开 2 / 3');
      assert.deepEqual(await shown(), ['forward', 'example']);
      assert.ok(operations.includes('pause') && operations.includes('finish'));
    }
    await page.close();
  };
  await run(desktop, false);
  await run(mobile, true);
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'browser-results.json'), JSON.stringify({mode: mode || 'real-asr', evidence, errors}, null, 2));
} finally {
  await browser.close();
}
