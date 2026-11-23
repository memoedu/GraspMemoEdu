import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createRequire} from 'node:module';
import {homedir} from 'node:os';

const [assetRoot, site] = process.argv.slice(2);
const editor = 'https://rowan-memoedu.github.io/AnnotationCapture/whiteboard/v1/';
const requireRuntime = createRequire(join(homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = requireRuntime('playwright');
const chrome = await chromium.launch({channel: 'chrome', headless: true});
try {
  const browser = await chrome.newContext({viewport: {width: 1440, height: 880}, locale: 'zh-CN'});
  await browser.addInitScript(() => {
    // The test writes real files using Chrome's isolated filesystem.
    // Only the native directory chooser and its permission prompt are simulated.
    if (globalThis.FileSystemHandle && navigator.storage) {
      Object.defineProperty(FileSystemHandle.prototype, 'queryPermission', {value: async () => 'granted'});
      window.showDirectoryPicker = () => navigator.storage.getDirectory();
    }
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const diagnostics = [];
  page.on('console', message => { if (message.type() === 'error') diagnostics.push(message.text()); });
  page.on('requestfailed', request => diagnostics.push(request.url() + ' ' + request.failure()?.errorText));
  await page.route(editor + '**', async route => {
    const path = new URL(route.request().url()).pathname.slice(new URL(editor).pathname.length);
    const contentType = path.endsWith('.js') ? 'text/javascript' : path.endsWith('.css') ? 'text/css' : 'text/html';
    await route.fulfill({status: 200, contentType, body: await readFile(join(assetRoot, path))});
  });
  let calls = 0;
  await page.route('**/api/whiteboard/recognize**', async route => {
    const payload = route.request().postDataJSON();
    assert.match(payload.image, /^iVBORw0KGgo/);
    assert.ok(payload.question.length > 5);
    assert.doesNotMatch(payload.question, /REFERENCE_ONLY/);
    calls++;
    await route.fulfill({json: calls === 1 ? {status: 'insufficient', feedback: '还缺第三、第四个空。'} :
      {status: 'ready', answer: 'correct'}});
  });
  await page.goto(site + '/#/subjects/math/topic/calculator-fixture');
  const next = page.getByRole('button', {name: '下一页', exact: true}).last();
  const mastered = page.locator('#stepCard .choiceActions .primaryButton:enabled', {hasText: '已掌握'});
  const answerForm = page.locator('#stepCard #answerForm');
  await next.or(mastered).or(answerForm).first().waitFor();
  if (!(await mastered.count()) && !(await answerForm.count())) await next.click();
  await mastered.or(answerForm).first().waitFor();
  if (!(await answerForm.count())) await mastered.click();
  await answerForm.waitFor();
  const launcher = page.locator('[data-question-tool=whiteboard]');
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
  await page.mouse.move(board.x + 35, board.y + 45);
  await page.mouse.down();
  await page.mouse.move(board.x + 160, board.y + 96, {steps: 8});
  await page.mouse.up();
  await frame.getByRole('button', {name: '撤销', exact: true}).click();
  await frame.getByRole('button', {name: '重做', exact: true}).click();

  const expression = panel.getByRole('textbox', {name: '白板表达式或语音草稿'});
  const name = panel.getByRole('textbox', {name: '变量名'});
  await expression.fill('2+3');
  await name.fill('A');
  await panel.getByRole('button', {name: '储存／换元'}).click();
  await panel.getByText('A = 5', {exact: true}).waitFor();
  await frame.getByRole('button', {name: '清屏'}).click();
  await expression.fill('A+2');
  await panel.getByRole('button', {name: '计算', exact: true}).click();
  await expression.evaluate(input => input.dispatchEvent(new CustomEvent('whiteboard-dictation', {detail: '2x + 3 = 7'})));
  const send = panel.getByRole('button', {name: '提交', exact: true});
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
  assert.deepEqual(saved.registers, [['A', {value: 5, text: '5'}]]);
  assert.ok(saved.texts.includes('A+2 = 7'));
  assert.ok(saved.texts.includes('2x + 3 = 7'));
  await send.click();
  await page.locator('.feedback.correct').waitFor();
  assert.equal(calls, 2);
  await panel.getByRole('button', {name: '收起'}).click();
  await launcher.click();
  await panel.getByText('A = 5', {exact: true}).waitFor();
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 850});
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    assert.equal(overflow, false, 'viewport ' + width);
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({passed: true, checks: ['split', 'swap', 'undo-redo', 'register survives clearing',
    'voice insertion event', 'archive and reopen', 'insufficient without submission', 'shared judge', 'small viewports']}));
} finally {
  await chrome.close();
}
