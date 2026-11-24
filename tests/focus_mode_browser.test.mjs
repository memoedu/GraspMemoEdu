import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {after, before, test} from 'node:test';

const require = createRequire(path.join(process.env.PLAYWRIGHT_NODE_MODULES || path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'), '_entry.cjs'));
const {chromium} = require('playwright');
const publicPage = process.env.GRASPMEMOEDU_FOCUS_TEST_URL;
const base = new URL(publicPage || 'http://focus-mode.test/');
const web = new URL('../web/', import.meta.url);
let browser;

before(async () => {
  browser = await chromium.launch({headless: true, ...(process.env.CHROME_EXECUTABLE
    ? {executablePath: process.env.CHROME_EXECUTABLE} : {channel: 'chrome'})});
});
after(async () => { await browser?.close(); });

async function fixture(t, {hierarchy = false, bank = false, width = 1440, context, standalone = false,
  hash = '#/subjects/math/' + (bank ? 'banks/fixture?root=chapter' : 'courses/fixture?root=chapter'),
  learnerId = 'fixture', unavailable = 0} = {}) {
  const page = context ? await context.newPage() : await browser.newPage({serviceWorkers: 'block', viewport: {width, height: 900}});
  if (standalone) await page.addInitScript(() => {
    const nativeMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = query => query === '(display-mode: standalone)' ? {matches: true} : nativeMatchMedia(query);
  });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => { await page.close(); assert.deepEqual(errors, []); });
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) return route.abort();
    const name = url.pathname.slice(base.pathname.length) || 'index.html';
    if (name === 'app.js' || name === 'pwa.js') return route.abort();
    if (publicPage) return route.continue();
    await route.fulfill({path: fileURLToPath(new URL(name, web)),
      contentType: /\.m?js$/.test(name) ? 'text/javascript' : undefined});
  });
  const url = new URL(base);
  url.hash = hash;
  await page.goto(url.href, {waitUntil: 'domcontentloaded'});
  await page.evaluate(async ({hierarchy, learnerId, unavailable}) => {
    const {initPortal} = await import(document.querySelector('link[rel="modulepreload"][href*="./portal.js"]').href);
    const outline = [{id: 'chapter', title: 'Chapter', parent_id: null, topic_ids: []},
      {id: 'first', title: 'First', parent_id: 'chapter', topic_ids: ['current', 'locked', 'following']},
      {id: 'second', title: 'Second', parent_id: 'chapter', topic_ids: ['other']}];
    const course = {id: 'fixture', title: 'Fixture', root_id: 'chapter', outline};
    const access = {learner_id: learnerId, role: 'account', features: ['learn', 'review_history', 'course_hierarchy']};
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
        element('stepCard').replaceChildren(content, portal.completionAction(finish));
      },
    });
    await portal.start();
  }, {hierarchy, learnerId, unavailable});
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
    const focused = await page.locator('.pageShell').boundingBox();
    assert.ok(focused.width > normal.width);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    for (const selector of ['.topRibbon', '.historySidebar', '.lessonHeading', '.historyDrawerToggle']) {
      assert.equal(await page.locator(selector).isVisible(), false, selector);
    }
    assert.match(await next.getAttribute('href'), /\/review\/due\/module\?session=due-session&course=fixture&root=chapter&focus=1$/);
    await page.evaluate(() => { window.focusFixture.showReview = false; });
    await focus.click();
    assert.equal(await next.isVisible(), false);
    assert.equal(await page.locator('.topRibbon').isVisible(), true);
    await focus.click();
    await next.waitFor();
    assert.match(await next.getAttribute('href'), /\/topic\/following\?course=fixture&root=chapter&focus=1$/);
    await page.evaluate(() => { window.focusFixture.followingDone = true; });
    await next.click();
    await page.getByText('Learning content of following', {exact: true}).waitFor();
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

test('A new standalone launch restores the last Topic for the verified learner', async t => {
  const context = await browser.newContext({serviceWorkers: 'block', viewport: {width: 390, height: 850}});
  try {
    const pwa = {context, standalone: true};
    const topic = '#/subjects/math/topic/current?course=fixture&root=chapter';
    const lastPage = topic + '&focus=1';
    const first = await fixture(t, pwa);
    const lesson = first.locator('.incompleteTasks [data-task-id="current"]');
    await lesson.locator('.taskToggle').click();
    await lesson.locator('.portalStart').click();
    await first.getByText('Learning content of current').waitFor();
    await first.locator('#focusToggle').click();
    assert.equal(new URL(first.url()).hash, lastPage);
    // Android Back can return to the workspace and homepage before exiting.
    await first.evaluate(() => { location.hash = '#/'; });
    await first.locator('.subjectCard').first().waitFor();
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
    const explicit = await fixture(t, {...pwa, hash: '#/'});
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
