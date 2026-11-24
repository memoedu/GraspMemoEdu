import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {after, before, test} from 'node:test';
import {launchAcceptanceChrome} from '../scripts/launch_acceptance_chrome.mjs';

const require = createRequire(path.join(process.env.PLAYWRIGHT_NODE_MODULES || path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'), '_entry.cjs'));
const {chromium} = require('playwright');
const publicPage = process.env.GRASPMEMOEDU_FOCUS_TEST_URL;
const base = new URL(publicPage || 'http://focus-mode.test/');
const web = new URL('../web/', import.meta.url);
let browser;

before(async () => {
  browser = process.env.CHROME_EXECUTABLE
    ? await chromium.launch({headless: true, executablePath: process.env.CHROME_EXECUTABLE})
    : await launchAcceptanceChrome(require);
});
after(async () => { await browser?.close(); });

async function fixture(t, {hierarchy = false, bank = false, width = 1440, context, standalone = false,
  entry = '',
  hash = '#/subjects/math/' + (bank ? 'banks/fixture?root=chapter' : 'courses/fixture?root=chapter'),
  learnerId = 'fixture', unavailable = 0, tools = false, help = false, long = false, denyFullscreen = false} = {}) {
  const page = context ? await context.newPage() : await browser.newPage({serviceWorkers: 'block', viewport: {width, height: 900}});
  if (standalone) await page.addInitScript(() => {
    const nativeMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = query => query === '(display-mode: standalone)' ? {matches: true} : nativeMatchMedia(query);
  });
  if (denyFullscreen) await page.addInitScript(() => {
    Element.prototype.requestFullscreen = () => Promise.reject(new DOMException('Denied', 'NotAllowedError'));
  });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => { await page.close(); assert.deepEqual(errors, []); });
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin === 'https://external.test' && url.pathname === '/outside') {
      return route.fulfill({contentType: 'text/html', body: '<h1>Outside GraspMemoEdu</h1>'});
    }
    if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) return route.abort();
    const relative = url.pathname.slice(base.pathname.length);
    const name = !relative || relative.endsWith('/') ? relative + 'index.html' : relative;
    if (name === 'app.js' || name === 'pwa.js') return route.abort();
    if (publicPage) return route.continue();
    await route.fulfill({path: fileURLToPath(new URL(name, web)),
      contentType: /\.m?js$/.test(name) ? 'text/javascript' : undefined});
  });
  if (tools) await page.route('https://rowan-memoedu.github.io/AnnotationCapture/whiteboard/*/whiteboard.html*',
    route => route.fulfill({contentType: 'text/html', body: '<!doctype html><title>Isolated whiteboard layout fixture</title>'}));
  const url = new URL(entry, base);
  url.hash = hash;
  await page.goto(url.href, {waitUntil: 'domcontentloaded'});
  await page.evaluate(async ({hierarchy, learnerId, unavailable, tools, help, long}) => {
    const moduleHref = name => document.querySelector('link[rel="modulepreload"][href*="/' + name + '.js"]').href;
    const {initPortal} = await import(moduleHref('portal'));
    const {setQuestionTools} = await import(moduleHref('question-tools'));
    const {reportableContent, placeContentActions} = await import(moduleHref('content-report'));
    const outline = [{id: 'chapter', title: 'Chapter', parent_id: null, topic_ids: []},
      {id: 'first', title: 'First', parent_id: 'chapter', topic_ids: ['current', 'locked', 'following']},
      {id: 'second', title: 'Second', parent_id: 'chapter', topic_ids: ['other']}];
    const course = {id: 'fixture', title: 'Fixture', root_id: 'chapter', outline};
    const access = {learner_id: learnerId, role: 'account', features: ['learn', 'review_history', 'course_hierarchy']};
    if (help) access.features.push('request_help');
    let verified = false;
    const lessons = ['current', 'locked', 'following', 'other'].map(id => ({
      id, topic_id: id, title: id, type: 'Lesson', status: 'not_started', dependency_ready: id !== 'locked',
    }));
    const due = {id: 'due', topic_id: 'due', title: 'Due', type: 'Review', status: 'not_started',
      start_href: '#/review/due/module?session=due-session'};
    const groups = [{id: 'chapter', title: 'Chapter', question_count: 0}, ...['read', 'locked', 'next', 'final'].map(id => ({
      id, title: id, parent_id: 'chapter', question_count: 0, introduction_count: 1, dependency_ready: id !== 'locked',
    }))];
    const responses = {subjects: {subjects: [{id: 'math', available: true, title: '数学'}]},
      'free-study': {subjects: []},
      profile: {timezone: 'Asia/Shanghai'}, catalog: {courses: [course], selected_course_id: course.id}};
    window.focusFixture = {reads: [], showReview: false, followingDone: false};
    const info = window.focusFixture;
    const element = id => document.getElementById(id);
    const portal = initPortal({
      getAccess: () => verified ? access : null, getIdentityProblem: () => null, refreshAccess: async () => {},
      ensureIdentity: async () => { verified = true; }, getApiOrigin: () => location.origin,
      request: async (name, options) => {
        verified = true;
        const [endpoint, query] = name.split('?');
        const params = new URLSearchParams(query);
        info.reads.push({endpoint, root: params.get('root_id'), fresh: options?.fresh === true});
        if (endpoint === 'dashboard') return {course, course_hierarchy_enabled: hierarchy,
          tasks: [...lessons.filter(item => !(info.followingDone && item.id === 'following')), ...(info.showReview ? [due] : [])],
          units: outline.slice(1), pending_hierarchy: outline.slice(1), history: []};
        if (endpoint === 'state') {
          if (unavailable) throw Object.assign(new Error('Unavailable fixture'), {status: unavailable});
          return {};
        }
        if (endpoint === 'training/bank') return {id: 'fixture', groups};
        if (endpoint === 'training/group') return {bank_id: 'fixture', id: params.get('group_id'), title: params.get('group_id'),
          questions: [], introductions: [{id: 'intro', title: 'Guidance', html: '<p>Read this guidance.</p>'}],
          content_order: [{type: 'introduction', id: 'intro'}]};
        return responses[endpoint];
      },
      leaveTopic: () => { element('appLayout').hidden = true; },
      openTopic: async id => {
        element('appLayout').hidden = false;
        element('appLayout').classList.toggle('historyCollapsed', matchMedia('(max-width: 1000px)').matches);
        document.body.classList.add('topicPage');
        element('loadingState').hidden = true;
        element('courseShell').hidden = false;
        const content = document.createElement('p'); content.className = 'courseContent';
        content.textContent = 'Learning content of ' + id;
        const finish = document.createElement('a'); finish.href = '#/subjects/math/courses/fixture?root=chapter';
        finish.textContent = 'Return to course';
        element('stepCard').replaceChildren(content);
        if (help) {
          const actions = document.createElement('div'); actions.className = 'questionActions';
          const heading = document.createElement('div'); heading.className = 'stepHeader'; heading.append(actions);
          reportableContent(content, {topic_id: id}, 'question:fixture', 'fixture');
          placeContentActions(content, actions);
          element('stepCard').prepend(heading);
        }
        if (long) for (let i = 0; i < 55; i++) element('stepCard').append(content.cloneNode(true));
        element('stepCard').append(portal.completionAction(finish));
        if (tools) setQuestionTools(element('stepCard'), {calculate: {level: 'scientific'}}, {key: id, editable: true});
      },
    });
    await portal.start();
  }, {hierarchy, learnerId, unavailable, tools, help, long});
  return page;
}

for (const hierarchy of [false, true]) {
  test(`Focus Mode uses the live ${hierarchy ? 'chapter' : 'flat'} course order`, async t => {
    const page = await fixture(t, {hierarchy, width: hierarchy ? 390 : 1440});
    const focus = page.locator('#focusToggle');
    const next = page.getByRole('link', {name: '下一个 Topic'});
    assert.equal(await focus.isVisible(), false);
    const pending = page.locator('.incompleteTasks');
    const lesson = pending.locator('[data-task-id="current"]');
    if (hierarchy) await page.getByRole('button', {name: '一键展开'}).click();
    await lesson.locator('.taskToggle').click();
    await lesson.locator('.portalStart').click();
    await focus.waitFor();
    assert.equal(await page.locator('.topRibbon').isVisible(), true);
    assert.equal(await next.isVisible(), false);
    const normal = await page.locator('.pageShell').boundingBox();
    await page.evaluate(() => { window.focusFixture.showReview = true; });
    await focus.click();
    await next.waitFor();
    await page.waitForFunction(() => document.fullscreenElement === document.documentElement);
    const focused = await page.locator('.pageShell').boundingBox();
    if (hierarchy) assert.ok(focused.width > normal.width);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    for (const selector of ['.topRibbon', '.historySidebar', '.lessonHeading', '.historyDrawerToggle']) {
      assert.equal(await page.locator(selector).isVisible(), false, selector);
    }
    assert.match(await next.getAttribute('href'), /\/review\/due\/module\?session=due-session&course=fixture&root=chapter&focus=1$/);
    await page.evaluate(() => { window.focusFixture.showReview = false; });
    await focus.click();
    await page.waitForFunction(() => !document.fullscreenElement);
    assert.equal(await next.isVisible(), false);
    assert.equal(await page.locator('.topRibbon').isVisible(), true);
    await focus.click();
    await next.waitFor();
    assert.match(await next.getAttribute('href'), /\/topic\/following\?course=fixture&root=chapter&focus=1$/);
    await page.evaluate(() => { window.focusFixture.followingDone = true; });
    await next.click();
    await page.getByText('Learning content of following', {exact: true}).waitFor();
    assert.equal(await page.evaluate(() => document.fullscreenElement === document.documentElement), true);
    assert.equal(await focus.getAttribute('aria-pressed'), 'true');
    assert.match(await next.getAttribute('href'), /\/topic\/current\?/);
    assert.ok(await page.evaluate(() => window.focusFixture.reads.some(req =>
      req.endpoint === 'dashboard' && req.root === 'chapter' && req.fresh)));
    const evidence = process.env.GRASPMEMOEDU_FOCUS_SCREENSHOTS;
    if (evidence) await page.screenshot({path: path.join(evidence, hierarchy ? 'course-mobile.png' : 'course-desktop.png')});
  });
}

test('Focus Mode keeps the bank root and advances through read-only groups without reopening them', async t => {
  const page = await fixture(t, {bank: true, width: 390});
  const card = page.locator('.incompleteTasks [data-task-id="read"]');
  await card.locator('.taskToggle').click();
  await card.locator('.portalStart').click();
  await page.locator('#focusToggle').click();
  const next = page.getByRole('link', {name: '下一个 Topic'});
  await next.waitFor();
  assert.match(await next.getAttribute('href'), /\/banks\/fixture\/next\?root=chapter&focus=1$/);
  await next.click();
  await page.waitForURL(/\/banks\/fixture\/next\?.*focus=1/);
  await next.waitFor();
  assert.match(await next.getAttribute('href'), /\/banks\/fixture\/final\?root=chapter&focus=1$/);
  await next.click();
  await page.waitForURL(/\/banks\/fixture\/final\?.*focus=1/);
  await page.getByRole('link', {name: '返回题库', exact: true}).waitFor();
  assert.equal(await next.isVisible(), false);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
});

const readerHash = '#/subjects/math/topic/current?course=fixture&root=chapter';
const waitForFullscreen = page => page.waitForFunction(() => document.fullscreenElement === document.documentElement);
const geometry = page => page.evaluate(() => {
  const question = document.getElementById('stepCard').getBoundingClientRect();
  const shell = document.querySelector('.pageShell').getBoundingClientRect();
  const toolbar = document.getElementById('focusToolbar').getBoundingClientRect();
  const calculator = document.querySelector('.questionCalculator[open]')?.getBoundingClientRect();
  return {midX: question.x + question.width / 2, width: question.width, right: question.right,
    centerX: document.documentElement.clientWidth / 2, midY: shell.y + shell.height / 2,
    centerY: (innerHeight + toolbar.bottom) / 2, calculatorLeft: calculator?.left,
    overflows: document.documentElement.scrollWidth > innerWidth};
});

test('Idle tools and the feedback icon get a rightward offset without clipping either panel', async t => {
  const page = await fixture(t, {hash: readerHash, tools: true, help: true});
  const evidence = process.env.GRASPMEMOEDU_FOCUS_SCREENSHOTS;
  const shot = name => evidence && page.screenshot({path: path.join(evidence, name + '.png')});
  await page.locator('#focusToggle').click();
  await waitForFullscreen(page);
  const center = await geometry(page);
  assert.ok(!center.overflows && center.midX - center.centerX > 40 && center.midX - center.centerX < 60, JSON.stringify(center));
  assert.ok(center.width <= 700, JSON.stringify(center));
  assert.ok(Math.abs(center.midY - center.centerY) < 12, JSON.stringify(center));
  const help = await page.locator('.contentReportToggle').boundingBox();
  const rail = await page.locator('.questionToolRail').boundingBox();
  assert.ok(help && rail && help.x + help.width <= center.right && rail.x > center.right);
  await shot('desktop-tools-idle');
  await page.locator('[data-question-tool="expression"]').click();
  await page.locator('.questionCalculator[open]').waitFor();
  const withCalculator = await geometry(page);
  assert.ok(withCalculator.right <= withCalculator.calculatorLeft, JSON.stringify(withCalculator));
  assert.ok(withCalculator.midX < center.midX - 100, JSON.stringify(withCalculator));
  await shot('desktop-calculator-open');
  await page.locator('.questionCalculator').getByRole('button', {name: '关闭'}).click();
  assert.ok(Math.abs((await geometry(page)).midX - center.midX) < 2);
  const whiteboard = page.locator('[data-question-tool="whiteboard"]');
  await whiteboard.click();
  const panel = await page.locator('.whiteboardPanel').boundingBox();
  assert.ok(panel && panel.x > (await geometry(page)).right, JSON.stringify(panel));
  await shot('desktop-whiteboard-open');
  await whiteboard.click();
  assert.ok(Math.abs((await geometry(page)).midX - center.midX) < 2);
  await page.evaluate(() => document.exitFullscreen());
  await page.locator('.topRibbon').waitFor();
  assert.ok(!new URL(page.url()).hash.includes('focus='));
});

test('A feedback icon alone offsets the idle question on desktop', async t => {
  const page = await fixture(t, {hash: readerHash, help: true, width: 1024});
  await page.locator('#focusToggle').click();
  await waitForFullscreen(page);
  const {midX, centerX, overflows} = await geometry(page);
  assert.ok(!overflows && midX - centerX >= 30 && midX - centerX <= 40);
  assert.equal(await page.locator('.contentReportToggle').isVisible(), true);
});

test('Escape closes fullscreen and Focus Mode while keeping the reader route', async t => {
  const page = await fixture(t, {hash: readerHash, tools: true});
  await page.locator('#focusToggle').click();
  await waitForFullscreen(page);
  await page.locator('[data-question-tool="expression"]').click();
  await page.keyboard.press('Escape');
  await page.locator('.questionCalculator[open]').waitFor({state: 'hidden'});
  assert.equal(await page.evaluate(() => document.fullscreenElement === document.documentElement), true);
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.fullscreenElement, null, {timeout: 5000});
  await page.locator('.topRibbon').waitFor();
  assert.equal(new URL(page.url()).hash, readerHash);
  assert.equal(await page.locator('#focusToggle').getAttribute('aria-pressed'), 'false');
});

test('A restored focus URL offers one-click fullscreen and a non-reader route relinquishes it', async t => {
  const page = await fixture(t, {hash: readerHash + '&focus=1', width: 390, tools: true});
  const fullscreen = page.getByRole('button', {name: '进入全屏', exact: true});
  await fullscreen.waitFor();
  assert.equal(await page.evaluate(() => document.fullscreenElement), null);
  await fullscreen.click();
  await waitForFullscreen(page);
  const center = await geometry(page);
  assert.ok(!center.overflows && Math.abs(center.midX - center.centerX) < 2, JSON.stringify(center));
  assert.ok(Math.abs(center.midY - center.centerY) < 12, JSON.stringify(center));
  const evidence = process.env.GRASPMEMOEDU_FOCUS_SCREENSHOTS;
  if (evidence) await page.screenshot({path: path.join(evidence, 'mobile-tools-idle.png')});
  await page.locator('[data-question-tool="expression"]').click();
  await page.locator('.questionCalculator[open]').waitFor();
  const dock = await page.locator('.questionCalculator').boundingBox();
  const question = await page.locator('#stepCard').boundingBox();
  assert.ok(question.y + question.height <= dock.y, JSON.stringify({dock, question}));
  await page.locator('.questionCalculator').getByRole('button', {name: '关闭计算器', exact: true}).click();
  assert.ok(Math.abs((await geometry(page)).midY - center.midY) < 2);
  await page.evaluate(() => { location.hash = '#/'; });
  await page.waitForFunction(() => !document.fullscreenElement);
  await page.locator('.topRibbon').waitFor();
  assert.equal(await page.locator('#focusToolbar').isVisible(), false);
});

test('A denied fullscreen request leaves the centered layout and a retry action', async t => {
  const page = await fixture(t, {hash: readerHash, denyFullscreen: true});
  await page.locator('#focusToggle').click();
  await page.getByText('未能进入全屏，可再次点击进入。').waitFor();
  assert.equal(await page.evaluate(() => document.fullscreenElement), null);
  assert.equal(await page.locator('#focusFullscreen').isEnabled(), true);
  assert.equal(await page.locator('.topRibbon').isVisible(), false);
  await page.locator('#focusToggle').click();
  assert.equal(await page.locator('.topRibbon').isVisible(), true);
});

test('Long reading starts below the bar and retains document scrolling in fullscreen', async t => {
  const page = await fixture(t, {hash: readerHash, long: true, tools: true});
  await page.locator('#focusToggle').click();
  await waitForFullscreen(page);
  const toolbar = await page.locator('#focusToolbar').boundingBox();
  const first = await page.locator('#stepCard p').first().boundingBox();
  assert.ok(first.y >= toolbar.y + toolbar.height && first.y < 165, JSON.stringify({first, toolbar}));
  await page.getByRole('link', {name: '下一个 Topic'}).scrollIntoViewIfNeeded();
  assert.ok(await page.evaluate(() => scrollY > 500));
  assert.equal(await page.locator('#focusToggle').isVisible(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
});

test('A new standalone launch restores the last Topic for the verified learner', async t => {
  const context = await browser.newContext({serviceWorkers: 'block', viewport: {width: 390, height: 850}});
  try {
    const pwa = {context, standalone: true, denyFullscreen: true};
    const topic = '#/subjects/math/topic/current?course=fixture&root=chapter';
    const lastPage = topic + '&focus=1';
    const first = await fixture(t, pwa);
    const lesson = first.locator('.incompleteTasks [data-task-id="current"]');
    await lesson.locator('.taskToggle').click();
    await lesson.locator('.portalStart').click();
    await first.getByText('Learning content of current').waitFor();
    await first.locator('#focusToggle').click();
    assert.equal(new URL(first.url()).hash, lastPage);
    await first.close();

    const browserPage = await fixture(t, {context, hash: ''});
    assert.equal(new URL(browserPage.url()).hash, '');
    const differentLearner = await fixture(t, {...pwa, hash: '', learnerId: 'other'});
    await differentLearner.locator('.subjectCard').first().waitFor();
    assert.equal(new URL(differentLearner.url()).hash, '');

    const restored = await fixture(t, {...pwa, hash: ''});
    await restored.getByText('Learning content of current').waitFor();
    assert.equal(new URL(restored.url()).hash, lastPage);
    assert.equal(await restored.locator('#focusToggle').getAttribute('aria-pressed'), 'true');
    const explicit = await fixture(t, {...pwa, hash: '#/', learnerId: 'explicit'});
    await explicit.locator('.subjectCard').first().waitFor();
    assert.equal(new URL(explicit.url()).hash, '#/');

    const temporaryFailure = await fixture(t, {...pwa, hash: '', unavailable: 503});
    assert.equal(new URL(temporaryFailure.url()).hash, lastPage);
    await temporaryFailure.getByRole('heading', {name: '服务暂不可用'}).waitFor();
    const inaccessible = await fixture(t, {...pwa, hash: '', unavailable: 403});
    await inaccessible.locator('.subjectCard').first().waitFor();
    assert.equal(new URL(inaccessible.url()).hash, '#/');
    const cleared = await fixture(t, {...pwa, hash: ''});
    assert.equal(new URL(cleared.url()).hash, '');
  } finally {
    await context.close();
  }
});

test('Scoped installations restore independently and fall back after a scope departure', async t => {
  const context = await browser.newContext({serviceWorkers: 'block', viewport: {width: 390, height: 850}});
  t.after(() => context.close());
  const pwa = {context, standalone: true};
  const free = 'pwa-free-study/';
  const math = 'pwa-math-courses/';
  const courseHome = '#/subjects/math/courses';
  const course = courseHome + '/fixture?root=chapter';
  const freeRoute = '#/free-study?view=fixture';
  const firstFree = await fixture(t, {...pwa, entry: free, hash: freeRoute});
  await firstFree.locator('.freeStudyLayout').waitFor();
  assert.equal(new URL(await firstFree.locator('#pwaInstallLink').getAttribute('href')).pathname,
    new URL(free + 'install.html', base).pathname);
  const firstMath = await fixture(t, {...pwa, entry: math, hash: course});
  await firstMath.locator('#dashboardTasks').waitFor();
  assert.equal(new URL(await firstMath.locator('#pwaInstallLink').getAttribute('href')).pathname,
    new URL(math + 'install.html', base).pathname);

  const relaunchedFree = await fixture(t, {...pwa, entry: free, hash: ''});
  const relaunchedMath = await fixture(t, {...pwa, entry: math, hash: ''});
  assert.equal(new URL(relaunchedFree.url()).hash, freeRoute);
  assert.equal(new URL(relaunchedMath.url()).hash, course);

  await relaunchedMath.evaluate(() => { location.hash = '#/free-study'; });
  await relaunchedMath.locator('.freeStudyLayout').waitFor();
  const fallbackMath = await fixture(t, {...pwa, entry: math, hash: ''});
  assert.equal(new URL(fallbackMath.url()).hash, courseHome);
  // Android can resume an existing window when its launcher icon is tapped.
  await relaunchedMath.bringToFront();
  await relaunchedMath.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await relaunchedMath.waitForURL(url => url.hash === courseHome);
  const stillFree = await fixture(t, {...pwa, entry: free, hash: ''});
  assert.equal(new URL(stillFree.url()).hash, freeRoute);

  const savedMath = await fixture(t, {...pwa, entry: math, hash: course});
  await savedMath.locator('#dashboardTasks').waitFor();
  await savedMath.close();
  const explicitMath = await fixture(t, {...pwa, entry: math, hash: '#/free-study'});
  await explicitMath.locator('.freeStudyLayout').waitFor();
  const afterExplicitMath = await fixture(t, {...pwa, entry: math, hash: ''});
  assert.equal(new URL(afterExplicitMath.url()).hash, courseHome);

  const rootPwa = await fixture(t, {...pwa, hash: course});
  await rootPwa.locator('#dashboardTasks').waitFor();
  await rootPwa.evaluate(() => {
    const link = document.createElement('a');
    link.href = 'https://external.test/outside';
    link.textContent = 'Leave GraspMemoEdu';
    document.body.prepend(link);
  });
  await rootPwa.getByRole('link', {name: 'Leave GraspMemoEdu'}).click();
  await rootPwa.getByRole('heading', {name: 'Outside GraspMemoEdu'}).waitFor();
  const rootFallback = await fixture(t, {...pwa, hash: ''});
  assert.equal(new URL(rootFallback.url()).hash, '');
  const freshFree = await fixture(t, {entry: free, hash: ''});
  assert.equal(new URL(freshFree.url()).hash, '#/free-study');
});
