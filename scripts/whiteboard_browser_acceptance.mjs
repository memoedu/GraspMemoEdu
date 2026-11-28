import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createRequire} from 'node:module';
import {homedir} from 'node:os';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [, site, voiceFile, invitationFile] = process.argv.slice(2);
assert.equal(Boolean(voiceFile), Boolean(invitationFile), 'Provide both the microphone WAV and the fixture invitation file');
const editor = 'https://rowan-memoedu.github.io/AnnotationCapture/whiteboard/';
const requireRuntime = createRequire(join(homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const chrome = await launchAcceptanceChrome(requireRuntime, voiceFile ? [
  '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', `--use-file-for-fake-audio-capture=${voiceFile}`,
] : []);
try {
  const browser = await chrome.newContext({viewport: {width: 1440, height: 880}, locale: 'zh-CN'});
  await browser.addInitScript(() => {
    const srcdoc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'srcdoc');
    Object.defineProperty(HTMLIFrameElement.prototype, 'srcdoc', {...srcdoc, set(value) {
      srcdoc.set.call(this, window.blockWhiteboardEditor ? '<!doctype html>' : value);
    }});
    // The test writes real files using Chrome's isolated filesystem.
    // Only the native directory chooser and its permission prompt are simulated.
    if (globalThis.FileSystemHandle && navigator.storage) {
      window.archivePermission = 'granted';
      Object.defineProperty(FileSystemHandle.prototype, 'queryPermission', {value: async () => window.archivePermission});
      Object.defineProperty(FileSystemHandle.prototype, 'requestPermission', {value: async ({mode}) => {
        window.requestedArchiveMode = mode;
        return (window.archivePermission = 'granted');
      }});
      window.showDirectoryPicker = () => window.cancelArchivePicker
        ? Promise.reject(new DOMException('Cancelled', 'AbortError')) : navigator.storage.getDirectory();
      const closeFile = FileSystemWritableFileStream.prototype.close;
      FileSystemWritableFileStream.prototype.close = async function () {
        if (window.waitForArchiveWrite) {
          window.archiveWriteStarted = true;
          await window.waitForArchiveWrite;
        }
        return closeFile.call(this);
      };
    }
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const diagnostics = [];
  page.on('console', message => { if (message.type() === 'error') diagnostics.push(message.text()); });
  page.on('requestfailed', request => diagnostics.push(request.url() + ' ' + request.failure()?.errorText));
  const externalEditorRequests = [];
  page.on('request', request => { if (request.url().startsWith(editor)) externalEditorRequests.push(request.url()); });
  let calls = 0, selectionCalls = 0;
  let receiveFirstOcr, releaseFirstOcr;
  const firstOcrStarted = new Promise(resolve => { receiveFirstOcr = resolve; });
  const firstOcrRelease = new Promise(resolve => { releaseFirstOcr = resolve; });
  let receiveOldSelection, releaseOldSelection;
  const oldSelectionStarted = new Promise(resolve => { receiveOldSelection = resolve; });
  const oldSelectionRelease = new Promise(resolve => { releaseOldSelection = resolve; });
  await page.route('**/api/whiteboard/recognize**', async route => {
    const payload = route.request().postDataJSON();
    assert.match(payload.image, /^iVBORw0KGgo/);
    assert.equal(payload.language, 'zh');
    if (payload.purpose === 'expression') {
      assert.equal(payload.question, undefined, 'formula OCR must send only the selection');
      const crop = Buffer.from(payload.image, 'base64');
      assert.ok(crop.readUInt32BE(16) < 1280 && crop.readUInt32BE(20) < 1024);
      if (receiveOldSelection) {
        receiveOldSelection();
        receiveOldSelection = undefined;
        await oldSelectionRelease;
        await route.fulfill({json: {status: 'ready', answer: 'obsolete'}}).catch(() => {});
        return;
      }
      return route.fulfill({json: {status: 'ready', answer: ++selectionCalls === 1 ? '3+7' : '2+3=5'}});
    }
    assert.ok(payload.question.length > 5);
    assert.doesNotMatch(payload.question, /REFERENCE_ONLY/);
    calls++;
    if (calls === 1) {
      receiveFirstOcr();
      await firstOcrRelease;
      return route.fulfill({status: 502, json: {detail: {code: 'whiteboard_ocr_unavailable', message: '测试：识别暂不可用。'}}});
    }
    await route.fulfill({json: calls === 2 ? {status: 'insufficient', feedback: '还缺第三、第四个空。'} :
      {status: 'ready', answer: 'correct'}});
  });
  let releaseVoice, receivedVoice;
  let onTopicBody = false;
  const voiceStarted = new Promise(resolve => { receivedVoice = resolve; });
  const voiceRelease = new Promise(resolve => { releaseVoice = resolve; });
  if (voiceFile) {
    await page.route('**/api/voice-input/transcribe**', async route => {
      const {mime_type, data_base64, profile} = route.request().postDataJSON();
      const wav = Buffer.from(data_base64, 'base64');
      assert.equal(mime_type, 'audio/wav');
      assert.equal(profile, 'calculator');
      assert.equal(wav.toString('ascii', 0, 4), 'RIFF');
      assert.equal(wav.readUInt32LE(24), 16000);
      assert.ok(wav.length > 10000);
      if (onTopicBody) return route.fulfill({json: {text: '2+3'}});
      receivedVoice();
      await voiceRelease;
      return route.fulfill({json: {text: '2x + 3 = 7'}});
    });
    await page.goto(site + '/#/settings');
    await page.locator('#portalContent:not([inert]) h1').waitFor();
    await page.locator('#userMenuButton').click();
    await page.locator('#identityButton').click();
    await page.locator('#invitationCode').fill((await readFile(invitationFile, 'utf8')).trim());
    await page.locator('#identitySubmitButton').click();
    const loginError = page.locator('#identityError:visible');
    await Promise.race([page.locator('#identitySubmitButton').waitFor({state: 'hidden'}), loginError.waitFor()]);
    if (await loginError.isVisible()) throw Error(await loginError.textContent());
  }
  const readingSubmissions = [];
  await page.route(/\/api\/(?:[^?#]+\/)?(?:submit|submit-answer)(?:\?|$)/, route => {
    if (onTopicBody) {
      readingSubmissions.push(new URL(route.request().url()).pathname);
      return route.abort();
    }
    return route.continue();
  });
  await page.goto(site + '/#/');
  await page.locator('#subjectHomeTitle').waitFor();
  assert.equal(await page.locator('.calculatorLaunch').count(), 0);
  await page.locator('.subjectCard[data-subject-id=math]').click();
  await page.locator('.portalLogo[href="#/subjects/math/courses"]:visible').waitFor();
  await page.locator('#portalContent:not([inert])').waitFor();
  assert.equal(await page.locator('.calculatorLaunch').count(), 0);
  await page.goto(site + '/#/subjects/math/topic/calculator-reading-fixture');
  onTopicBody = true;
  const bodyTools = page.getByRole('toolbar', {name: '正文工具'});
  const bodyBoard = page.locator('.whiteboardPanel:visible');
  const bodyExpression = bodyBoard.locator('[data-whiteboard-expression]');
  const bodySubmit = bodyBoard.getByRole('button', {name: '提交', exact: true});
  const prepared = page.locator('.whiteboardPanel[hidden] [data-whiteboard-expression]:enabled');
  await prepared.waitFor({state: 'attached'});
  const preparedFrame = await page.locator('.whiteboardPanel[hidden] iframe').elementHandle();
  await bodyTools.getByRole('button', {name: '白板', exact: true}).click();
  assert.equal(await bodyBoard.locator('iframe').evaluate((frame, initial) => frame === initial, preparedFrame), true);
  assert.equal(await bodyBoard.locator('iframe').getAttribute('sandbox'), 'allow-scripts');
  await bodyExpression.and(bodyBoard.locator('input:enabled')).waitFor();
  assert.equal(await bodySubmit.isVisible(), true);
  assert.equal(await bodySubmit.isDisabled(), true);
  assert.equal(await bodySubmit.evaluate(button => getComputedStyle(button).backgroundColor), 'rgb(224, 224, 224)');
  async function recordTwoSeconds(field) {
    await field.focus();
    await page.getByRole('button', {name: '录音输入', exact: true}).click();
    const finish = page.getByRole('button', {name: '结束录音', exact: true});
    await finish.waitFor();
    await page.waitForFunction(() => {
      const [, minutes, seconds] = document.querySelector('.voiceDuration').textContent.match(/(\d+) 分钟: (\d+) 秒/) || [];
      return Number(minutes) * 60 + Number(seconds) >= 2;
    });
    await finish.click();
  }
  async function dictateIntoBodyTool(field) {
    await field.fill('');
    await recordTwoSeconds(field);
    await page.waitForFunction(input => input.value === '2+3', await field.elementHandle());
    await page.getByText('已插入转写文字。', {exact: true}).waitFor();
  }
  if (voiceFile) await dictateIntoBodyTool(bodyExpression);
  else {
    await bodyExpression.fill('2+3');
    await bodyBoard.getByRole('button', {name: '写入白板', exact: true}).click();
  }
  await bodyBoard.frameLocator('iframe').getByRole('button', {name: '撤销', exact: true}).and(
    bodyBoard.frameLocator('iframe').locator('button:enabled')).waitFor();
  await bodySubmit.evaluate(button => button.click());
  await bodyTools.getByRole('button', {name: '科学计算器', exact: true}).click();
  const bodyCalculator = page.locator('.questionCalculator');
  const calculatorExpression = bodyCalculator.getByRole('textbox', {name: '表达式'});
  if (voiceFile) await dictateIntoBodyTool(calculatorExpression);
  else await calculatorExpression.fill('2+3');
  await bodyCalculator.getByRole('button', {name: '计算结果', exact: true}).first().click();
  await bodyCalculator.locator('.calculatorResult').getByText('5', {exact: true}).waitFor();
  assert.equal(await bodyCalculator.locator('.calculatorTransfer').isVisible(), false);
  assert.deepEqual(readingSubmissions, []);
  assert.equal(calls, 0);
  await bodyCalculator.getByRole('button', {name: '关闭计算器'}).click();
  await bodyBoard.getByRole('button', {name: '收起', exact: true}).click();
  onTopicBody = false;
  await page.goto(site + '/#/subjects/math/topic/calculator-fixture');
  const next = page.locator('#appLayout:not([hidden]) #stepCard').getByRole('button', {name: '下一页', exact: true}).last();
  const mastered = page.locator('#stepCard .choiceActions .primaryButton:enabled', {hasText: '已掌握'});
  const answerForm = page.locator('#stepCard #answerForm');
  const launcher = page.locator('.questionToolRail [data-question-tool=whiteboard]');
  await next.or(mastered).or(answerForm).first().waitFor();
  if (!(await mastered.count()) && !(await answerForm.count())) await next.click();
  await mastered.or(answerForm).first().waitFor();
  if (!(await answerForm.count())) {
    await launcher.click();
    const preview = page.locator('.whiteboardPanel:visible');
    await preview.locator('[data-whiteboard-expression]:enabled').waitFor();
    assert.equal(await preview.getByRole('button', {name: '提交', exact: true}).isDisabled(), true);
    await preview.getByRole('button', {name: '收起', exact: true}).click();
    await mastered.click();
  }
  await answerForm.waitFor();
  try { await launcher.click({timeout: 8000}); }
  catch (error) {
    throw Error((await page.locator('body').innerText()).slice(0, 1500) + '\n' + errors.join('\n'), {cause: error});
  }
  const panel = page.locator('.whiteboardPanel:visible');
  const frame = page.frameLocator('.whiteboardPanel:visible iframe');
  const canvas = frame.locator('#board');
  try { await panel.getByRole('button', {name: '归档目录'}).click({timeout: 14000}); }
  catch (error) {
    throw Error(JSON.stringify({status: await panel.locator('.whiteboardStatus').textContent(), location: page.frames().map(frame => frame.url()),
      errors, diagnostics}), {cause: error});
  }
  const pane = await panel.boundingBox();
  const question = await page.locator('#stepCard').boundingBox();
  assert.ok(question.y - pane.y < 180, 'the question starts directly beneath its toolbar');
  const separator = page.getByRole('separator', {name: '调整题目与白板比例'});
  const handle = await separator.boundingBox();
  await page.mouse.move(handle.x + handle.width / 2, handle.y + 40);
  await page.mouse.down();
  await page.mouse.move(handle.x - 75, handle.y + 40, {steps: 10});
  await page.mouse.up();
  assert.ok((await panel.boundingBox()).width > pane.width);
  await panel.getByRole('button', {name: '交换位置'}).click();
  assert.ok((await panel.boundingBox()).x < (await page.locator('#stepCard').boundingBox()).x);
  await canvas.scrollIntoViewIfNeeded();
  const board = await canvas.boundingBox();
  assert.equal(await frame.getByRole('button', {name: '涂抹删除', exact: true}).getAttribute('aria-pressed'), 'true');
  const draw = async points => {
    for (const [i, [x, y]] of points.entries()) {
      await page.mouse.move(board.x + x, board.y + y, {steps: i ? 4 : 1});
      if (!i) await page.mouse.down();
    }
    await page.mouse.up();
  };
  await draw([[96, 48], [96, 86], [125, 86], [125, 48], [96, 48]]);
  await draw([[138, 48], [138, 86], [176, 86], [176, 48], [138, 48]]);
  const pixels = (x, y) => canvas.evaluate((element, [x, y]) => {
    const box = element.getBoundingClientRect();
    const [r, g] = element.getContext('2d').getImageData(
      Math.round(x * element.width / box.width), Math.round(y * element.height / box.height), 1, 1
    ).data;
    return r > g + 20;
  }, [x, y]);
  const waitForPixel = async (x, y, expected) => {
    for (let attempt = 0; attempt < 20; attempt++) {
      if (await pixels(x, y) === expected) return;
      await page.waitForTimeout(35);
    }
    assert.equal(await pixels(x, y), expected);
  };
  await waitForPixel(96, 70, true);
  await draw([[117, 59], [135, 62], [117, 65], [135, 68], [117, 71], [135, 74]]);
  await waitForPixel(96, 70, false);
  await waitForPixel(120, 59, false);
  assert.equal(await pixels(138, 70), true);
  await frame.getByRole('button', {name: '撤销', exact: true}).click();
  await waitForPixel(96, 70, true);
  await frame.getByRole('button', {name: '重做', exact: true}).click();
  await waitForPixel(96, 70, false);
  await frame.getByRole('button', {name: '清屏', exact: true}).click();
  await page.mouse.move(board.x + 35, board.y + 45);
  await page.mouse.down();
  await page.mouse.move(board.x + 160, board.y + 96, {steps: 8});
  await page.mouse.up();
  await frame.getByRole('button', {name: '撤销', exact: true}).click();
  await frame.getByRole('button', {name: '重做', exact: true}).click();
  const undo = frame.getByRole('button', {name: '撤销', exact: true});
  await page.evaluate(() => { window.cancelArchivePicker = true; });
  await panel.getByRole('button', {name: '归档目录'}).click();
  assert.ok(await undo.isEnabled(), 'canceling directory selection preserves undo history');
  await page.evaluate(() => { window.cancelArchivePicker = false; });
  await panel.getByRole('button', {name: '归档目录'}).click();
  await panel.getByText('归档目录已授权。', {exact: true}).waitFor();
  assert.ok(await undo.isEnabled(), 'reauthorizing a directory preserves undo history');
  const archiveEntries = await page.evaluate(async () => {
    const root = await navigator.storage.getDirectory();
    const names = [];
    for await (const name of root.keys()) names.push(name);
    return names;
  });
  assert.equal(archiveEntries.includes('GraspMemoEdu-Whiteboards'), false, 'choosing a folder does not create an empty archive');
  await panel.getByRole('button', {name: '收起'}).click();
  await launcher.click();
  await panel.getByRole('button', {name: '归档目录'}).waitFor();
  assert.ok(await undo.isEnabled(), 'reopening the same live board preserves undo history');
  await frame.getByRole('button', {name: '画笔', exact: true}).click();
  await canvas.scrollIntoViewIfNeeded();
  const lassoTarget = await canvas.boundingBox();
  await page.mouse.move(lassoTarget.x + 100, lassoTarget.y + 188);
  await page.mouse.down();
  await page.mouse.move(lassoTarget.x + 150, lassoTarget.y + 216, {steps: 8});
  await page.mouse.up();
  await frame.getByRole('button', {name: '套索', exact: true}).click();
  await canvas.scrollIntoViewIfNeeded();
  const selection = await canvas.boundingBox();
  await page.mouse.move(selection.x + 85, selection.y + 172);
  await page.mouse.down();
  for (const [x, y] of [[170, 172], [170, 238], [85, 238], [85, 172]]) {
    await page.mouse.move(selection.x + x, selection.y + y, {steps: 8});
  }
  await page.mouse.up();
  const identifySelection = panel.getByRole('button', {name: '识别圈选公式'});
  await identifySelection.waitFor();
  await identifySelection.click();
  await oldSelectionStarted;
  await canvas.scrollIntoViewIfNeeded();
  const beforeScale = await canvas.boundingBox();
  await page.mouse.move(beforeScale.x + 158, beforeScale.y + 224);
  await page.mouse.down();
  await page.mouse.move(beforeScale.x + 197, beforeScale.y + 252, {steps: 8});
  await page.mouse.up();
  await identifySelection.waitFor();
  await panel.getByRole('button', {name: '计算', exact: true}).click();
  try { await panel.getByText('3+7 = 10', {exact: true}).waitFor({timeout: 5000}); }
  catch (error) {
    throw Error(JSON.stringify({selectionCalls, text: await panel.innerText(), errors, diagnostics}), {cause: error});
  }
  releaseOldSelection();
  assert.equal(await panel.getByText('3+7 = 10', {exact: true}).count(), 1);
  const selectedFormula = panel.getByRole('textbox', {name: '圈选公式识别结果'});
  await identifySelection.click();
  await page.waitForFunction(() => document.querySelector('.whiteboardSelection input')?.value === '2+3=5');
  await selectedFormula.evaluate(input => input.setSelectionRange(0, 3));
  const selectedVariable = panel.getByRole('textbox', {name: '变量名'});
  await selectedVariable.evaluate(input => input.dispatchEvent(new CustomEvent('whiteboard-dictation', {detail: '用 B 换元'})));
  await selectedVariable.press('Enter');
  await panel.getByText('B = 5', {exact: true}).waitFor();
  await panel.getByText('已换元，可在画布撤销。', {exact: true}).waitFor();
  await undo.click();
  await frame.getByRole('button', {name: '形状', exact: true}).hover();
  await frame.getByRole('button', {name: '箭头', exact: true}).waitFor();
  await frame.getByRole('button', {name: '形状', exact: true}).press('Escape');
  await canvas.press('Control+a');
  await frame.getByRole('button', {name: '删除所选', exact: true}).click();
  await undo.click();

  const expression = panel.getByRole('textbox', {name: '白板表达式或语音草稿'});
  const selectionRequestsBeforeText = selectionCalls;
  await frame.getByRole('button', {name: '清屏', exact: true}).click();
  await expression.fill('7+9');
  await panel.getByRole('button', {name: '写入白板', exact: true}).click();
  await canvas.press('Control+a');
  await identifySelection.waitFor();
  await panel.getByRole('button', {name: '计算', exact: true}).click();
  await panel.getByText('7+9 = 16', {exact: true}).waitFor();
  assert.equal(selectionCalls, selectionRequestsBeforeText, 'text already on the board needs no image recognition');
  await frame.getByRole('button', {name: '清屏', exact: true}).click();
  await expression.fill('z=((7)/(sqrt(16+45+3-4-12)))');
  await panel.getByRole('button', {name: '写入白板', exact: true}).click();
  await canvas.press('Control+a');
  await identifySelection.waitFor();
  await panel.getByRole('button', {name: '计算', exact: true}).click();
  await panel.locator('.whiteboardSelection').getByText('z = (7/12)*3^(1/2)', {exact: true}).waitFor();
  assert.equal(selectionCalls, selectionRequestsBeforeText);
  await frame.getByRole('button', {name: '清屏', exact: true}).click();
  const name = panel.getByRole('textbox', {name: '变量名'});
  await expression.fill('2+3=5');
  await expression.evaluate(input => input.setSelectionRange(0, 3));
  await name.fill('A');
  await panel.getByRole('button', {name: '储存／换元'}).click();
  await panel.getByText('B = 5 · A = 5', {exact: true}).waitFor();
  await frame.getByRole('button', {name: '清屏'}).click();
  await expression.fill('A+2');
  await panel.getByRole('button', {name: '计算', exact: true}).click();
  const send = panel.getByRole('button', {name: '提交', exact: true});
  if (voiceFile) {
    await expression.fill('');
    await recordTwoSeconds(expression);
    await voiceStarted;
    await send.click();
    await panel.getByText('请先结束录音并等待转写完成。', {exact: true}).waitFor();
    assert.equal(calls, 0);
    releaseVoice();
    await page.waitForFunction(() => document.querySelector('[data-whiteboard-expression]')?.value === '2x + 3 = 7');
  } else {
    await expression.evaluate(input => input.dispatchEvent(new CustomEvent('whiteboard-dictation', {detail: '2x + 3 = 7'})));
  }
  await page.evaluate(() => { window.archivePermission = 'denied'; });
  await send.click();
  await panel.getByText('请先选择并授权本机归档目录。', {exact: true}).waitFor();
  assert.equal(calls, 0);
  await page.evaluate(() => { window.archivePermission = 'prompt'; });
  await send.click();
  await firstOcrStarted;
  assert.equal(await page.evaluate(() => window.requestedArchiveMode), 'readwrite');
  assert.ok(await send.isDisabled(), 'prevent duplicate submission while the OCR request is pending');
  assert.ok(await frame.getByRole('button', {name: '画笔', exact: true}).isDisabled());
  releaseFirstOcr();
  await panel.getByText('测试：识别暂不可用。', {exact: true}).waitFor();
  await frame.getByRole('button', {name: '画笔', exact: true}).and(frame.locator('button:enabled')).waitFor();
  assert.equal(await page.locator('.feedback.correct,.feedback.incorrect').count(), 0);
  await send.click();
  await panel.getByText('还缺第三、第四个空。', {exact: true}).waitFor();
  assert.equal(await page.locator('.feedback.correct,.feedback.incorrect').count(), 0);
  const saved = await page.evaluate(async () => {
    const root = await (await navigator.storage.getDirectory()).getDirectoryHandle('GraspMemoEdu-Whiteboards');
    for await (const folder of root.values()) {
      const data = JSON.parse(await (await (await folder.getFileHandle('latest.json')).getFile()).text());
      const png = await (await folder.getFileHandle(data.image)).getFile();
      return {registers: data.registers, texts: data.scene.items.filter(item => item.kind === 'text').map(item => item.text), imageSize: png.size};
    }
  });
  assert.ok(saved.imageSize > 1000);
  assert.deepEqual(saved.registers, [['B', {value: 5, text: '5'}], ['A', {value: 5, text: '5'}]]);
  assert.ok(saved.texts.includes('A+2 = 7'));
  assert.ok(saved.texts.includes('2x + 3 = 7'));
  await page.evaluate(() => {
    window.waitForArchiveWrite = new Promise(resolve => { window.releaseArchiveWrite = resolve; });
  });
  const finalOcr = page.waitForResponse(response => response.url().includes('/api/whiteboard/recognize'));
  await send.click();
  await finalOcr;
  await page.waitForFunction(() => window.archiveWriteStarted);
  assert.equal(await page.locator('.feedback.correct').count(), 0, 'grading waits for the archive even after OCR completes');
  await page.evaluate(() => window.releaseArchiveWrite());
  await page.locator('.feedback.correct').waitFor();
  assert.equal(calls, 3);
  await panel.getByRole('button', {name: '收起'}).click();
  await launcher.click();
  await panel.getByText('B = 5 · A = 5', {exact: true}).waitFor();
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 850});
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    assert.equal(overflow, false, 'viewport ' + width);
  }
  await page.evaluate(async () => {
    const {saveWhiteboard, restoreWhiteboard} = await import('/whiteboard-archive.js');
    const sandbox = await (await navigator.storage.getDirectory()).getDirectoryHandle('archive-recovery-test', {create: true});
    const scene = {version: 1, items: [{kind: 'text', text: 'archive recovery', color: '#000000', x: 4, y: 20}]};
    await saveWhiteboard(sandbox, 'recovery-example', {scene, png: new Blob(['test raster'])}, []);
    const archive = await sandbox.getDirectoryHandle('GraspMemoEdu-Whiteboards');
    for await (const entry of archive.values()) {
      const saved = JSON.parse(await (await (await entry.getFileHandle('latest.json')).getFile()).text());
      await entry.removeEntry(saved.image);
    }
    const recovered = await restoreWhiteboard(sandbox, 'recovery-example');
    if (!recovered?.imageMissing || recovered.scene.items[0]?.text !== 'archive recovery') {
      throw Error('Scene must survive a missing PNG');
    }
  });
  await page.evaluate(() => { window.blockWhiteboardEditor = true; });
  await page.evaluate(async () => {
    const toolsModule = document.querySelector('link[href*="/question-tools.js"]')?.href || '/question-tools.js';
    const {setQuestionTools} = await import(toolsModule);
    const section = document.createElement('section');
    section.id = 'whiteboard-editor-retry';
    const question = document.createElement('article');
    section.append(question);
    document.body.append(section);
    setQuestionTools(question, {id: 'editor-retry', calculate: {level: 'scientific'}},
      {key: 'editor-retry', editable: true, isCurrent: () => true});
  });
  const retryCase = page.locator('#whiteboard-editor-retry');
  const retryLauncher = retryCase.locator('[data-question-tool=whiteboard]');
  await retryLauncher.click();
  await retryCase.getByText('白板载入失败，收起后重试。', {exact: true}).waitFor();
  await retryCase.getByRole('button', {name: '收起', exact: true}).click();
  await page.evaluate(() => { window.blockWhiteboardEditor = false; });
  await retryLauncher.click();
  await retryCase.getByRole('button', {name: '归档目录', exact: true}).and(retryCase.locator('button:enabled')).waitFor();
  assert.equal(await retryCase.locator('.whiteboardStatus').textContent(), '');
  assert.deepEqual(errors, []);
  assert.deepEqual(externalEditorRequests, []);
  console.log(JSON.stringify({passed: true, checks: ['Topic reading tools, no answer submission, absent on home and subject landing', 'pre-answer whiteboard uses a disabled submit button',
    'split', 'swap', 'undo-redo', 'scribble erase and atomic undo', 'register survives clearing',
    voiceFile ? 'Chrome capture, transcription insertion and pending submit guard' : 'voice insertion event',
    'prepared editor is reused on first open', 'archive and reopen', 'directory cancellation and denied permission', 'live undo after reopen',
    'lasso deletion and undo', 'OCR freeze and recovery', 'insufficient without submission', 'shared judge', 'small viewports',
    'editable scene recovered after its PNG went missing', 'editor retries after load failure',
    'selection calculation', 'changing selection cancels slow OCR', 'typed selection computes without OCR',
    'OCR and archive run together with grading gated on the archive',
    'dictated variable and undoable substitution', 'hover shapes', 'select all']}));
} finally {
  await chrome.close();
}
