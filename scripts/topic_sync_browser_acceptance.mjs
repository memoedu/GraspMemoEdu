import assert from 'node:assert/strict';
import {randomBytes, randomUUID} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [fixture, navigatorCheckout, origin = 'http://127.0.0.1:18948'] = process.argv.slice(2);
const {SiteNavigation} = await import(pathToFileURL(path.join(navigatorCheckout, 'src/site-navigation.mjs')));
const {invitations, topic_id: topic} = JSON.parse(await readFile(path.join(fixture, 'topic-sync-browser.json'), 'utf8'));
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const browser = await launchAcceptanceChrome(require);
const liveNative = process.argv.includes('--live-remnote');
const {withRemNoteBody} = await import(pathToFileURL(path.join(navigatorCheckout, 'src/remnote-body.mjs')));
const {BodySync, checkpoints} = await import(pathToFileURL(path.join(navigatorCheckout, 'src/body-sync.mjs')));
const nativeIds = {};
let kb = 'acceptance-' + randomUUID(), rem = 'acceptance-document';
if (liveNative) await withRemNoteBody(async call => {
  const state = await call('remnote_status');
  assert(state.connected && state.acceptWriteOperations);
  kb = state.knowledgeBaseId;
  const create = async (name, fields) => {
    const result = await call('remnote_create_note', fields);
    assert.equal(result.remIds.length, 1);
    nativeIds[name] = result.remIds[0];
    await writeFile(path.join(fixture, 'native-document.json'), JSON.stringify(nativeIds, null, 2));
    return nativeIds[name];
  };
  rem = await create('document', {title: 'GraspMemoEdu 正文同步隔离验收 ' + randomUUID().slice(0, 8), asDocument: true});
  const parent = await create('parent', {title: '本机大纲', parentId: rem});
  await create('child', {title: 'INTRODUCTION_ONLY 本机初稿', parentId: parent});
});
let device;
const opened = [], browserErrors = [];
const navigator = new SiteNavigation({
  devices: {read: async () => device, ensure: async () => (device ??= {id: randomUUID(), secret: randomBytes(32).toString('base64url')})},
  state: async () => ({kbId: kb}),
  launch: async target => {
    opened.push(target);
    return {verified: true, documentRemId: target.remId};
  },
  apiOrigin: origin,
});

try {
  const context = await browser.newContext({viewport: {width: 1140, height: 850}, locale: 'zh-CN'});
  await context.exposeBinding('acceptanceNavigator', async (_, message) => {
    try { return await navigator[message.action](message.ticket); }
    catch (error) { return {error: error.message, code: error.code}; }
  });
  await context.addInitScript(() => {
    const channel = 'graspmemoedu-remnote-v1';
    window.addEventListener('message', async event => {
      const {data} = event;
      if (event.origin !== location.origin || event.source !== window || data?.channel !== channel ||
          data.type !== 'request' || !['device', 'pair', 'open'].includes(data.action)) return;
      const result = await window.acceptanceNavigator(data);
      window.postMessage({channel, type: 'response', id: data.id, result}, location.origin);
    });
  });
  const page = await context.newPage();
  page.setDefaultTimeout(16000);
  page.on('pageerror', error => browserErrors.push(error.message));
  const requests = [];
  page.on('response', response => {
    const pathname = new URL(response.url()).pathname;
    if (pathname.startsWith('/api/topic-sync/')) requests.push([pathname, response.status()]);
  });
  const open = page.getByRole('button', {name: '在本地 RemNote 中打开', exact: true});
  const route = origin + '/#/subjects/math/topic/' + topic;
  async function login(invite, tab = page) {
    await tab.locator('#userMenuButton').click();
    await tab.locator('#identityButton').click();
    const login = tab.locator('#identityDialog');
    await login.locator('input').fill(invite);
    await login.locator('form').evaluate(form => form.requestSubmit());
    await login.waitFor({state: 'hidden'});
  }

  await page.goto(route);
  await page.locator('#lessonTitle').waitFor();
  assert.equal(await open.isVisible(), false);
  await login(invitations[0]);
  await page.goto(route);
  await open.click();
  try {
    await page.getByText(/此 (?:Topic|主题) 尚未绑定本地 RemNote Document。/).waitFor();
  } catch (error) {
    console.error('Topic sync requests', JSON.stringify(requests));
    console.error('Topic sync status', await page.locator('#topicSyncStatus').textContent());
    throw error;
  }
  await navigator.request('device-binding', {device, body: {topic_id: topic, kb_id: kb, rem_id: rem}});
  const sync = new BodySync(navigator, checkpoints(path.join(fixture, 'checkpoints')));
  if (liveNative) {
    await sync.sync({kbId: kb, remId: rem});
    await page.reload();
  }
  const edit = page.getByRole('button', {name: '开启编辑', exact: true});
  let editorTested = false;
  if (process.argv.includes('--editor')) {
    await edit.waitFor();
    const toolbar = page.locator('#lessonContent [role="toolbar"]').filter({has: open});
    assert.equal(await toolbar.count(), 1);
    assert.equal(await toolbar.getByRole('button', {name: '开启编辑', exact: true}).count(), 1);
    assert.equal(await toolbar.getByRole('button', {name: '零碎知识简藏', exact: true}).count(), 1);
    await edit.focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await open.evaluate(button => button === document.activeElement), true);
    await page.setViewportSize({width: 390, height: 844});
    await edit.scrollIntoViewIfNeeded();
    const first = await edit.boundingBox();
    const second = await open.boundingBox();
    assert(first && second && first.x >= 0 && second.x + second.width <= 390);
    await page.setViewportSize({width: 1100, height: 860});
    await edit.click();
    const finish = page.getByRole('button', {name: '关闭编辑', exact: true});
    await finish.waitFor();
    await page.evaluate(() => { location.hash = '#/subjects/math/courses'; });
    await open.waitFor({state: 'hidden'});
    await finish.waitFor({state: 'hidden'});
    await page.getByRole('button', {name: '零碎知识简藏', exact: true}).waitFor();
    await page.evaluate(id => { location.hash = '#/subjects/math/topic/' + id; }, topic);
    await finish.waitFor();
    const frame = page.frameLocator('iframe.topicBodyFrame');
    if (!liveNative) {
      const heading = frame.locator('.ls-block').filter({has: frame.locator('.block-content').getByText('Outline formula section', {exact: true})});
      await heading.locator('.block-content').getByText('Outline child', {exact: true}).waitFor();
      await frame.locator('.block-content').filter({hasText: 'Outline parent'}).locator('.katex').waitFor();
      await frame.locator('.katex-display .mfrac').waitFor();
      const inline = frame.locator('.block-content').filter({hasText: 'Preserve inline formatting in one row.'});
      await inline.locator('strong').waitFor();
      assert.equal(await inline.locator('strong').textContent(), 'inline formatting');
      assert.equal(await frame.getByText('SVG replica').count(), 0);
    }
    const content = frame.locator('.block-content').filter({hasText: 'INTRODUCTION_ONLY'}).first();
    await content.click({position: {x: 8, y: 8}});
    const field = frame.locator('textarea:visible').first();
    await field.fill('Changed in TINE $x^2$');
    await field.blur();
    await page.getByText('正文已保存。', {exact: true}).waitFor();
    const changed = await navigator.request('device-body?topic_id=' + topic, {device});
    const nested = changed.document.blocks.find(row => row.text === 'Changed in TINE $x^2$');
    assert(nested?.parent_id);
    if (liveNative) {
      assert.equal(nested.id, nativeIds.child);
      await sync.sync({kbId: kb, remId: rem});
      await withRemNoteBody(async call => {
        const result = await call('personalwebsite_richtext', {remId: nativeIds.child});
        assert.equal(result.parentRemId, nativeIds.parent);
        assert(result.content.some(run => run.type === 'math' && run.tex === 'x^2'));
        await call('personalwebsite_richtext', {remId: nativeIds.child, expectedContent: result.content,
          expectedParentRemId: nativeIds.parent, content: [{text: 'Updated from the companion '}, {type: 'math', tex: 'x^3', display: false}]});
      });
      await sync.sync({kbId: kb, remId: rem});
    }
    await page.getByRole('button', {name: '关闭编辑', exact: true}).click();
    await edit.waitFor();
    assert.equal(await page.locator('iframe.topicBodyFrame').count(), 0);
    if (!liveNative) {
      const fromLocal = structuredClone(changed.document);
      fromLocal.blocks.find(row => row.id === nested.id).text = 'Updated from the companion $x^3$';
      await navigator.request('device-body', {device, body: {topic_id: topic, revision: randomUUID(),
        expected_revision: changed.revision, document: fromLocal}});
    }
    await page.reload();
    await edit.waitFor();
    assert.equal(await page.locator('iframe.topicBodyFrame').count(), 0);
    await page.evaluate(() => { location.hash = '#/subjects/math/courses'; });
    await edit.waitFor({state: 'hidden'});
    await page.evaluate(id => { location.hash = '#/subjects/math/topic/' + id; }, topic);
    await edit.waitFor();
    assert.equal(await page.locator('iframe.topicBodyFrame').count(), 0);
    await edit.click();
    await frame.getByText(/Updated from the companion/).first().waitFor();
    await finish.click();
    await edit.waitFor();
    assert.equal(await page.locator('iframe.topicBodyFrame').count(), 0);
    if (!liveNative) {
      await edit.click();
      const original = frame.locator('.block-content').filter({hasText: 'Updated from the companion'}).first();
      await original.waitFor();
      const current = await navigator.request('device-body?topic_id=' + topic, {device});
      const newer = structuredClone(current.document);
      newer.blocks.find(row => row.id === nested.id).text = 'Newer companion revision';
      const revision = randomUUID();
      await navigator.request('device-body', {device, body: {topic_id: topic, revision,
        expected_revision: current.revision, document: newer}});
      await original.click({position: {x: 8, y: 8}});
      const field = frame.locator('textarea:visible').first();
      await field.fill('Conflicting website draft');
      await field.blur();
      await page.waitForResponse(response => new URL(response.url()).pathname === '/api/topic-sync/body' &&
        response.request().method() === 'POST' && response.status() === 409);
      for (let i = 0; i < 2; i++) {
        await finish.click();
        await edit.waitFor();
        assert.equal(await page.locator('iframe.topicBodyFrame').count(), 0);
        await edit.click();
        await frame.getByText('Conflicting website draft', {exact: true}).waitFor();
      }
      await finish.click();
      const final = await navigator.request('device-body?topic_id=' + topic, {device});
      assert.equal(final.revision, revision);
      assert.equal(final.document.blocks.find(row => row.id === nested.id).text, 'Newer companion revision');
    }
    editorTested = true;
  }
  await open.click();
  await page.getByText('已在 RemNote 中打开。', {exact: true}).waitFor();
  assert.deepEqual(opened, [{kbId: kb, remId: rem}]);
  const reverse = new URL((await navigator.source({kbId: kb, remId: rem})).url).hash;
  await page.goto(origin + '/' + reverse);
  await page.waitForURL(url => url.hash === new URL(route).hash);
  await open.waitFor();

  await login(invitations[1]);
  await page.goto(route);
  if (!editorTested) await open.click();
  await page.getByText('当前账号与本机绑定不一致。请切换到原绑定的网站账号。', {exact: true}).waitFor();
  assert.equal(await open.isDisabled(), true);
  await page.goto(origin + '/' + reverse);
  await page.getByText('当前账号与本机绑定不一致。请切换到原绑定的网站账号。', {exact: true}).waitFor();
  assert.equal(await open.isVisible(), false);
  assert.equal(opened.length, 1);
  const clean = await browser.newContext({acceptDownloads: true});
  try {
    const withoutExtension = await clean.newPage();
    await withoutExtension.goto(route);
    await withoutExtension.locator('#lessonTitle').waitFor();
    await login(invitations[0], withoutExtension);
    await withoutExtension.goto(route);
    await withoutExtension.getByRole('button', {name: '在本地 RemNote 中打开', exact: true}).click();
    await withoutExtension.waitForURL(url => url.pathname.endsWith('/remnote-install.html'));
    const returnLink = withoutExtension.getByRole('link', {name: '返回 GraspMemoEdu'});
    assert.equal(new URL(await returnLink.getAttribute('href'), withoutExtension.url()).hash, new URL(route).hash);
    if (process.argv.includes('--installer')) {
      const download = withoutExtension.waitForEvent('download');
      await withoutExtension.getByRole('button', {name: '下载 Windows 安装包'}).click();
      const delivered = await download;
      assert.equal(delivered.suggestedFilename(), 'GraspMemoEdu-RemNote-Windows-x64.zip');
      assert.equal(await delivered.failure(), null);
    }
    await returnLink.click();
    await withoutExtension.waitForURL(url => url.hash === new URL(route).hash);
  } finally {
    await clean.close();
  }
  assert.deepEqual(browserErrors, []);
  await writeFile(path.join(fixture, 'browser-acceptance.json'), JSON.stringify({
    paired: true, openedWebToDocument: true, openedDocumentToTopic: true, mismatchBlockedBothWays: true,
    companion: 'real local site client', nativeNavigation: 'synthetic SDK', nativeBody: liveNative,
    tineEditorAndBody: editorTested, topicControlsShareExistingToolbar: editorTested,
    missingExtensionReturnsFromInstaller: true, installerDownload: process.argv.includes('--installer'),
    github: 'isolated in-memory ciphertext store',
  }, null, 2));
  console.log('PASS real website and companion HTTP pairing, navigation and account mismatch');
} finally {
  await browser.close();
}
