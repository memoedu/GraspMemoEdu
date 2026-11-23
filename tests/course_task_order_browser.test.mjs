import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {after, before, test} from 'node:test';

const require = createRequire(path.join(process.env.PLAYWRIGHT_NODE_MODULES || path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'), '_entry.cjs'));
const {chromium} = require('playwright');
const publicPage = process.env.GRASPMEMOEDU_REVIEW_TASK_TEST_URL;
const base = new URL(publicPage || 'http://course-task-order.test/');
const web = new URL('../web/', import.meta.url);
let browser;

before(async () => {
  browser = await chromium.launch({headless: true, ...(process.env.CHROME_EXECUTABLE
    ? {executablePath: process.env.CHROME_EXECUTABLE} : {channel: 'chrome'})});
});
after(async () => { await browser?.close(); });

const course = {id: 'fixture', title: '课程排序测试', progress: 50};
const outline = [{id: 'chapter', title: '第一章', parent_id: null, topic_ids: ['lesson', 'draft']},
  {id: 'unavailable', title: '暂不可学习章节', parent_id: null, topic_ids: ['locked', 'paused', 'cooldown', 'maintenance']}];
const task = (id, type) => ({
  id, type, topic_id: id, title: id, course_id: course.id, course_title: course.title,
  dependency_ready: true, status: 'not_started', progress: 0,
});
const tasks = [task('lesson', 'Lesson'), {...task('review', 'Review'),
  due_at: '2026-11-23T02:00:00Z', start_href: '#/review/fixture/module'},
  {...task('locked', 'Lesson'), dependency_ready: false},
  {...task('paused', 'Lesson'), status: 'paused', locked: true},
  {...task('cooldown', 'Lesson'), cooldown_until: '2099-01-01T00:00:00Z'},
  {...task('maintenance', 'Lesson'), maintenance: true}];
const topics = [{id: 'lesson', title: 'Lesson', status: 'not_started'},
  {id: 'draft', title: 'Draft', status: 'read_only'},
  ...tasks.slice(2).map(({id, title, status}) => ({id, title, status}))];
const history = [task('past-review', 'Review'), task('past-lesson', 'Lesson')].map(entry => ({
  ...entry, status: 'completed', result: 'completed', progress: 100, completed_at: '2026-11-23T01:00:00Z',
}));

for (const {hierarchy, hasReady} of [
  {hierarchy: false, hasReady: true}, {hierarchy: true, hasReady: true}, {hierarchy: true, hasReady: false},
]) {
  const view = hierarchy ? 'chapter' : 'flat';
  test(`filter unavailable Topics in the ${view} view${hasReady ? '' : ' when none can be learned'}`, async () => {
    const page = await browser.newPage({serviceWorkers: 'block', viewport: {width: hierarchy ? 1280 : 375, height: 900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) return route.abort();
        const name = url.pathname.slice(base.pathname.length) || 'index.html';
        // The fixture invokes the portal with a synthetic identity and never calls an API.
        if (name === 'app.js' || name === 'pwa.js') return route.abort();
        if (publicPage) return route.continue();
        const contentType = /\.m?js$/.test(name) ? 'text/javascript' : undefined;
        await route.fulfill({path: fileURLToPath(new URL(name, web)), contentType});
      });
      const url = new URL(base);
      url.hash = '#/subjects/math/courses/fixture';
      await page.goto(url.href, {waitUntil: 'domcontentloaded'});
      await page.evaluate(async ({course, outline, tasks, topics, history, hierarchy, hasReady}) => {
        const moduleUrl = document.querySelector('link[rel="modulepreload"][href*="./portal.js"]').href;
        const {initPortal} = await import(moduleUrl);
        const access = {learner_id: 'fixture', role: 'account',
          features: ['review_history', 'course_hierarchy', ...(hasReady ? ['learn'] : [])]};
        const responses = {
          subjects: {subjects: [{id: 'math', title: '数学', available: true}]},
          profile: {timezone: 'Asia/Shanghai', display_name: '排序测试'},
          catalog: {courses: [{...course, outline}]},
          dashboard: {course, tasks, topics, history, units: outline, pending_hierarchy: outline,
            course_hierarchy_enabled: hierarchy},
        };
        const portal = initPortal({
          request: async name => responses[name.split('?')[0]],
          getAccess: () => access, getIdentityProblem: () => null, leaveTopic: () => {},
        });
        await portal.start();
      }, {course, outline, tasks: hasReady ? tasks : tasks.filter(entry => entry.type !== 'Review'),
        topics, history, hierarchy, hasReady});
      const pending = page.locator('#dashboardTasks .incompleteTasks');
      if (hasReady) assert.equal(await pending.locator('.courseUnitGroup').count(), hierarchy ? 2 : 0);
      const visibleIds = () => pending.locator('.portalTask:visible').evaluateAll(cards => cards.map(card => card.dataset.taskId));
      const initial = await visibleIds();
      const unavailable = ['locked', 'paused', 'cooldown', 'maintenance'];
      for (const id of unavailable) assert.ok(initial.includes(id), id);
      assert.deepEqual(initial.filter(id => !unavailable.includes(id)),
        hasReady ? ['review', 'lesson', 'draft:draft'] : ['lesson', 'draft:draft']);
      const filter = page.getByRole('checkbox', {name: '隐藏暂不可学习的主题', exact: true});
      await filter.check();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      assert.deepEqual(await visibleIds(), hasReady ? ['review', 'lesson'] : []);
      if (hierarchy) assert.equal(await pending.locator('[data-unit-id="unavailable"]').isVisible(), false);
      assert.equal(await page.getByText('暂不可学习的主题已隐藏，可取消勾选查看。', {exact: true}).isVisible(), !hasReady);
      assert.equal(await page.evaluate(() => localStorage.getItem('graspmemoedu:hide-locked:fixture')), 'true');
      await filter.uncheck();
      assert.deepEqual(await visibleIds(), initial);
      assert.equal(await page.locator('#completedTasks .portalTask:visible').count(), history.length);
      const glyph = id => page.locator(`#completedTasks [data-task-id="${id}"] .taskIcon svg path`).getAttribute('d');
      assert.equal(await glyph('past-review'), await glyph('past-lesson'));
      assert.deepEqual(errors, []);
      const evidence = process.env.GRASPMEMOEDU_REVIEW_TASK_SCREENSHOTS;
      if (evidence && hierarchy) await page.screenshot({path: path.join(evidence, 'chapter-with-drafts.png'), fullPage: true});
    } finally {
      await page.close();
    }
  });
}
