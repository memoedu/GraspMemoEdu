import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';
const [base, output, accountPath] = process.argv.slice(2);
assert.equal(new URL(base).hostname, '127.0.0.1');
assert(!['8765', '18768'].includes(new URL(base).port));
await fs.mkdir(output, {recursive: true});
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const session = (await (await fetch(base + '/api/session', {headers: {Origin: base}})).json()).session_token;
const credentials = JSON.parse(await fs.readFile(accountPath, 'utf8'));
const headers = {Origin: base, 'X-Learning-Session': session, 'Content-Type': 'application/json'};
const guest = await (await fetch(base + '/api/access/guest', {method: 'POST', headers, body: '{}'})).json();
const login = await (await fetch(base + '/api/access/login', {method: 'POST', headers,
  body: JSON.stringify({invitation_code: credentials.invitation_code})})).json();
headers['X-Learning-Identity'] = login.identity_token;
await fetch(base + '/api/catalog/select?subject_id=math', {method: 'POST', headers, body: JSON.stringify({course_id: 'course-math'})});
const browser = await launchAcceptanceChrome(require);
const report = {latency_ms_per_api_request: 120, pages: [], requests: [], errors: [], checks: {}};
try {
  const context = await browser.newContext({viewport: {width: 1365, height: 960}, locale: 'zh-CN'});
  await context.addInitScript(({base, token, guestToken}) => {
    localStorage.setItem('graspmemoedu:identity:' + base, token);
    localStorage.setItem('graspmemoedu:identity-role:' + base, 'account');
    localStorage.setItem('graspmemoedu:guest-identity:' + base, guestToken);
  }, {base, token: login.identity_token, guestToken: guest.identity_token});
  // Delay genuine API traffic; do not mock responses or learning state.
  await context.route('**/api/**', async route => {
    await new Promise(resolve => setTimeout(resolve, 120));
    await route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => report.errors.push(error.message));
  const bodies = [];
  page.on('response', response => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/')) return;
    const row = {path: url.pathname, query: url.search, status: response.status()};
    report.requests.push(row);
    bodies.push(response.body().then(body => {row.bytes = body.length;}).catch(() => {}));
  });
  async function view(name, route, selector, reload = false) {
    const start = performance.now(), before = report.requests.length;
    if (reload) await page.reload({waitUntil: 'domcontentloaded'});
    else if (page.url().startsWith(base)) await page.evaluate(async hash => {
      location.hash = hash;
      await new Promise(requestAnimationFrame);
    }, '#/subjects/math/' + route);
    else await page.goto(base + '/#/subjects/math/' + route, {waitUntil: 'domcontentloaded'});
    await page.waitForFunction(selector => {
      const node = document.querySelector(selector);
      return node && node.getClientRects().length && !node.closest('[hidden], [inert]')
        && !document.querySelector('#portalContent[aria-busy="true"]');
    }, selector);
    report.pages.push({name, ms: Math.round(performance.now() - start), requests: report.requests.length - before});
  }
  await view('courses_cold', 'courses', '.courseGrid .courseChoice');
  report.checks.account_startup_reads_access_once = report.requests.filter(row => row.path === '/api/access').length === 1;
  await view('learn_cold', 'learn', '.dashboardLayout .portalTask');
  await view('courses_warm', 'courses', '.courseGrid .courseChoice');
  await view('learn_warm', 'learn', '.dashboardLayout .portalTask');
  await view('banks_cold', 'banks', '.courseGrid .courseChoice');
  await view('bank_cold', 'banks/bank-math', '.dashboardLayout .portalTask');
  await view('banks_warm', 'banks', '.courseGrid .courseChoice');
  await view('bank_warm', 'banks/bank-math', '.dashboardLayout .portalTask');
  await view('topic_cold', 'topic/lesson-math', '#courseShell:not([hidden])');
  await page.screenshot({path: path.join(output, 'lesson-desktop.png')});
  await view('learn_after_topic', 'learn', '.dashboardLayout .portalTask');
  await view('topic_warm', 'topic/lesson-math', '#courseShell:not([hidden])');
  await view('topic_reload', 'topic/lesson-math', '#courseShell:not([hidden])', true);
  await page.waitForTimeout(1100);
  const beforeForeground = report.requests.length;
  const stateRead = page.waitForResponse(response => new URL(response.url()).pathname === '/api/state');
  await page.evaluate(() => {
    window.dispatchEvent(new Event('focus'));
    document.dispatchEvent(new Event('visibilitychange'));
    window.dispatchEvent(new Event('focus'));
  });
  await stateRead;
  await page.waitForTimeout(250);
  report.checks.foreground_reads_topic_once = report.requests.slice(beforeForeground)
    .filter(row => row.path === '/api/state').length === 1;
  await page.waitForTimeout(5100);
  const foregroundRequests = report.requests.slice(beforeForeground);
  report.checks.periodic_topic_state_reuses_access = foregroundRequests.some(row => row.path === '/api/state')
    && !foregroundRequests.some(row => row.path === '/api/access');
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 900});
    report.checks['width_' + width] = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
  }
  await page.screenshot({path: path.join(output, 'lesson-mobile.png')});
  await Promise.all(bodies);
  report.checks.no_page_errors = report.errors.length === 0;
  assert.deepEqual(report.errors, []);
  assert(Object.values(report.checks).every(Boolean));
} finally {
  await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify({pages: report.pages, checks: report.checks}, null, 2));
