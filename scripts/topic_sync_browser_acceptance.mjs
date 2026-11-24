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
const kb = 'acceptance-' + randomUUID(), rem = 'acceptance-document';
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
  async function login(invite) {
    await page.locator('#userMenuButton').click();
    await page.locator('#identityButton').click();
    const login = page.locator('#identityDialog');
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
    console.error('Topic sync status', await page.locator('#lessonContent .lessonToolbar [role="status"]').allTextContents());
    throw error;
  }
  await navigator.request('device-binding', {device, body: {topic_id: topic, kb_id: kb, rem_id: rem}});
  await open.click();
  await page.getByText('已在 RemNote 中打开。', {exact: true}).waitFor();
  assert.deepEqual(opened, [{kbId: kb, remId: rem}]);
  const reverse = new URL((await navigator.source({kbId: kb, remId: rem})).url).hash;
  await page.goto(origin + '/' + reverse);
  await page.waitForURL(url => url.hash === new URL(route).hash);
  await open.waitFor();

  await login(invitations[1]);
  await page.goto(route);
  await open.click();
  await page.getByText('当前账号与本机绑定不一致。请切换到原绑定的网站账号。', {exact: true}).waitFor();
  assert.equal(await open.isDisabled(), true);
  await page.goto(origin + '/' + reverse);
  await page.getByText('当前账号与本机绑定不一致。请切换到原绑定的网站账号。', {exact: true}).waitFor();
  assert.equal(await open.isVisible(), false);
  assert.equal(opened.length, 1);
  assert.deepEqual(browserErrors, []);
  await writeFile(path.join(fixture, 'browser-acceptance.json'), JSON.stringify({
    paired: true, openedWebToDocument: true, openedDocumentToTopic: true, mismatchBlockedBothWays: true,
    companion: 'real local site client', remnote: 'synthetic SDK',
  }, null, 2));
  console.log('PASS real website and companion HTTP pairing, navigation and account mismatch');
} finally {
  await browser.close();
}
