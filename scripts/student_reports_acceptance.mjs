import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';

const [base, artifactRoot, publicBase] = process.argv.slice(2);
assert.equal(new URL(base).hostname, '127.0.0.1');
const auth = JSON.parse(await fs.readFile(path.join(artifactRoot, 'auth.private.json'), 'utf8'));
const publicApi = publicBase ? JSON.parse(await fs.readFile(path.join(artifactRoot, 'pages/deployment.json'), 'utf8')).api_origin : null;
const fixtureSession = publicBase ? await (await fetch(base + '/api/session', {headers: {Origin: base}})).json() : null;
if (publicBase) assert.ok(fixtureSession.session_token);
const out = path.join(artifactRoot, publicBase ? 'published-browser' : 'browser'); await fs.mkdir(out, {recursive: true});
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const browser = await chromium.launch({headless: true, executablePath: path.join(os.homedir(), 'AppData/Local/Google/Chrome/Application/chrome.exe')});
const errors = [], checks = [];
const pass = name => { checks.push(name); console.log('PASS ' + name); };
const snapshot = async () => (await (await fetch(base + '/qa/snapshot')).json()).hash;
let active;
async function pageFor(role, mobile = false) {
  const context = await browser.newContext({viewport: mobile ? {width: 390, height: 844} : {width: 1440, height: 1000}, locale: 'zh-CN', isMobile: mobile, hasTouch: mobile});
  await context.addInitScript(({base, token, role}) => {
    localStorage.setItem('graspmemoedu:identity:' + base, token);
    localStorage.setItem('graspmemoedu:identity-role:' + base, role);
  }, {base, token: auth[role].identity_token, role: auth[role].access.role});
  const page = await context.newPage(); page.setDefaultTimeout(15000); page.on('pageerror', error => errors.push(error.message));
  if (publicBase) {
    // Published static UI is exercised against isolated records, never production learners.
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url());
      const headers = {...request.headers()}; delete headers.host; delete headers.referer;
      headers.origin = base; headers['x-learning-session'] = fixtureSession.session_token;
      if (headers['x-learning-identity']) headers['x-learning-identity'] = auth[role].identity_token;
      else if (!url.pathname.endsWith('/session')) headers['x-learning-identity'] = auth[role].identity_token;
      const response = await fetch(base + url.pathname + url.search, {method: request.method(), headers,
        body: ['GET', 'HEAD'].includes(request.method()) ? undefined : request.postData()});
      await route.fulfill({status: response.status, contentType: response.headers.get('content-type') || 'application/json',
        headers: {'Access-Control-Allow-Origin': new URL(publicBase).origin, 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, X-Learning-Identity'}, body: Buffer.from(await response.arrayBuffer())});
    });
    await context.addInitScript(({origin, token, role}) => {
      localStorage.setItem('graspmemoedu:identity:' + origin, token); localStorage.setItem('graspmemoedu:identity-role:' + origin, role);
    }, {origin: publicApi, token: auth[role].identity_token, role: auth[role].access.role});
  }
  return page;
}
const url = learner => (publicBase || base + '/') + '#/admin/students?learner=' + encodeURIComponent(learner);
try {
  const before = await snapshot();
  const page = active = await pageFor('admin');
  await page.goto(url(auth.target)); await page.locator('.studentDashboard').waitFor();
  await page.getByRole('tab', {name: '概览', exact: true}).waitFor();
  assert.equal(await page.getByRole('tab').count(), 5);
  assert.equal(await page.locator('.studentHeatCell').count(), 30);
  assert.equal(await page.locator('.studentMetric').count(), 8);
  await page.locator('.studentHeatCell').last().click();
  assert.match(await page.locator('.studentCharts').textContent(), /作答.*次/);
  await page.locator('.studentCalendarDay.hasReviews').first().click();
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({path: path.join(out, 'overview-desktop.png'), fullPage: true});
  pass('Overview metrics, activity heatmap, accuracy trend and date-specific review calendar');

  await page.getByRole('tab', {name: '全部 Topic', exact: true}).click();
  assert.equal(await page.locator('.studentTopic').count(), 2);
  const topic = page.locator('.studentTopic[data-topic-id=synthetic-course]');
  await topic.locator(':scope > summary').click();
  assert.match(await topic.innerText(), /1\s*\/\s*2/);
  assert.match(await topic.innerText(), /尚未学习/);
  await topic.locator('summary').filter({hasText: '题目与作答记录'}).click();
  await topic.locator('.studentQuestionRow').first().waitFor();
  assert.equal(await topic.locator('.studentQuestionRow').count(), 30);
  await topic.getByRole('button', {name: '加载更多', exact: true}).click();
  await page.waitForFunction(() => document.querySelectorAll('[data-topic-id=synthetic-course] .studentQuestionRow').length === 32);
  await page.screenshot({path: path.join(out, 'topics-desktop.png'), fullPage: true});
  pass('Complete Topic tree, unstarted modules, spare Practice questions and paginated drilldown');

  await page.getByRole('tab', {name: '题库', exact: true}).click();
  await page.locator('.studentBank > summary').click();
  for (const summary of await page.locator('.studentBank .courseUnitGroup > summary').all()) {
    if (!(await summary.evaluate(node => node.parentElement.open))) await summary.click();
  }
  await page.locator('.studentBankGroup > summary').filter({hasText: '第一题组'}).click();
  const exact = page.locator('.studentBank .studentQuestionRow').filter({has: page.getByRole('heading', {name: '隔离习题 exact', exact: true})});
  await exact.waitFor(); await exact.locator('.studentAnswerHistory > summary').click();
  await exact.locator('.studentAnswerCard').first().waitFor();
  assert.equal(await exact.locator('.studentAnswerCard').count(), 3);
  assert.match(await exact.innerText(), /系统判错 2 次/);
  assert.match(await exact.innerText(), /学员提交的答案/);
  assert.match(await exact.innerText(), /一加一等于二/);
  await page.screenshot({path: path.join(out, 'bank-history-desktop.png'), fullPage: true});
  pass('Bank hierarchy and original answers, verdicts, explanations and error counts');

  await page.getByRole('tab', {name: '错题本', exact: true}).click();
  const notebook = page.getByRole('tabpanel', {name: '错题本', exact: true});
  await notebook.locator('.studentQuestionRow').first().waitFor();
  await notebook.getByLabel('题目状态筛选', {exact: true}).selectOption('unanswered');
  await notebook.getByText('共 1 道题', {exact: true}).waitFor();
  assert.match(await notebook.innerText(), /隔离习题 blank/);
  await notebook.getByLabel('题目状态筛选', {exact: true}).selectOption('all');
  await notebook.getByText('共 4 道题', {exact: true}).waitFor();
  const essay = notebook.locator('.studentQuestionRow').filter({has: page.getByRole('heading', {name: '隔离习题 essay', exact: true})});
  await essay.locator('.studentAnswerHistory > summary').click();
  await essay.getByText('自主评分：2', {exact: true}).waitFor();
  pass('Notebook includes manually enrolled untrained questions and separate self-assessment records');

  await page.getByRole('tab', {name: '全部复习排程', exact: true}).click();
  await page.locator('.studentSchedule .courseChoice').first().waitFor();
  assert.equal(await page.locator('.studentAtomicCard').count(), 7);
  await page.getByLabel('复习排程筛选', {exact: true}).selectOption('future');
  assert.ok(await page.locator('.studentSchedule .courseChoice').count() >= 1);
  await page.getByRole('tab', {name: '全部复习排程', exact: true}).press('Home');
  assert.equal(await page.getByRole('tab', {name: '概览', exact: true}).getAttribute('aria-selected'), 'true');
  await page.getByLabel('统计时间范围', {exact: true}).selectOption('7');
  await page.waitForFunction(() => document.querySelectorAll('.studentHeatCell').length === 7);
  pass('Existing schedules and atomic variants retained; tabs support keyboard; activity range refreshes');

  const mobile = active = await pageFor('admin', true); await mobile.goto(url(auth.target));
  await mobile.locator('.studentDashboard').waitFor();
  assert.ok(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await mobile.screenshot({path: path.join(out, 'overview-mobile.png'), fullPage: true});
  await mobile.getByRole('tab', {name: '错题本', exact: true}).click();
  const mobileNotebook = mobile.getByRole('tabpanel', {name: '错题本', exact: true});
  await mobileNotebook.locator('.studentQuestionRow').first().waitFor();
  await mobileNotebook.locator('.studentAnswerHistory > summary').first().click();
  await mobileNotebook.locator('.studentAnswerCard').first().waitFor();
  assert.ok(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await mobile.screenshot({path: path.join(out, 'notebook-mobile.png'), fullPage: true});
  pass('Mobile report and submitted-answer display fit 390px without page overflow');

  const ordinary = active = await pageFor('ordinary'); await ordinary.goto(url(auth.target));
  await ordinary.getByText('此页面仅供管理员使用。', {exact: true}).waitFor();
  assert.equal(await ordinary.locator('.studentDashboard').count(), 0);
  await page.goto(url(auth.empty_target)); await page.locator('.studentDashboard').waitFor();
  assert.match(await page.locator('.studentMetrics').first().innerText(), /0\s*\/\s*2/);
  assert.match(await page.locator('.studentCharts').innerText(), /暂无系统判题/);
  assert.equal(await snapshot(), before); assert.deepEqual(errors, []);
  pass('Disabled/unstarted student, ordinary-user denial, zero browser errors and unchanged learner database');

  const ownBefore = await snapshot();
  const personalUrl = (publicBase || base + '/') + '#/progress';
  active = ordinary;
  await ordinary.locator('#userMenuButton').click();
  await ordinary.getByRole('link', {name: '个人学习情况', exact: true}).click();
  await ordinary.locator('.studentDashboard').waitFor();
  assert.equal(await ordinary.getByRole('tab').count(), 5);
  await ordinary.getByRole('tab', {name: '错题本', exact: true}).click();
  const ordinaryNotebook = ordinary.getByRole('tabpanel', {name: '错题本', exact: true});
  await ordinaryNotebook.locator('.studentAnswerHistory > summary').first().click();
  await ordinaryNotebook.locator('.studentAnswerCard .studentQuestion').first().waitFor();
  pass('Non-student learner opens the shared report from the account menu and reads a recorded answer');

  const student = active = await pageFor('student');
  await student.goto(personalUrl); await student.locator('.studentDashboard').waitFor();
  await student.getByRole('heading', {name: 'Learner nickname', exact: true}).waitFor();
  assert.equal(await student.getByRole('tab').count(), 5);
  assert.ok(!(await student.locator('.studentOverview').innerText()).includes('Private roster name'));
  await student.locator('#userMenuButton').click();
  await student.getByRole('link', {name: '个人学习情况', exact: true}).waitFor();
  assert.equal(await student.locator('#studentsLink').isVisible(), false);
  await student.locator('#userMenuButton').press('Escape');
  await student.getByRole('tab', {name: '全部 Topic', exact: true}).click();
  assert.equal(await student.locator('.studentTopic').count(), 2);
  assert.equal(await student.getByRole('tabpanel', {name: '全部 Topic', exact: true}).locator('[data-unit-id="math"]').count(), 0);
  assert.equal(await student.getByRole('tabpanel', {name: '全部 Topic', exact: true}).locator('[data-unit-id="chapter"]').count(), 1);
  await page.goto(url(auth.target)); await page.locator('.studentDashboard').waitFor();
  await page.getByRole('heading', {name: 'Private roster name', exact: true}).waitFor();
  await page.getByRole('tab', {name: '全部 Topic', exact: true}).click();
  assert.equal(await page.getByRole('tabpanel', {name: '全部 Topic', exact: true}).locator('[data-unit-id="math"]').count(), 0);
  assert.equal(await page.getByRole('tabpanel', {name: '全部 Topic', exact: true}).locator('[data-unit-id="chapter"]').count(), 1);
  await student.screenshot({path: path.join(out, 'personal-topic-tree.png'), fullPage: true});
  const atomicTopic = student.locator('.studentTopic[data-topic-id=atoms]');
  await atomicTopic.locator(':scope > summary').click();
  await atomicTopic.locator('summary').filter({hasText: '题目与作答记录'}).click();
  await atomicTopic.locator('.studentAnswerHistory > summary').first().click();
  await atomicTopic.locator('.studentAnswerCard .studentQuestion').first().waitFor();
  await student.getByRole('tab', {name: '题库', exact: true}).click();
  await student.locator('.studentBank > summary').click();
  assert.match(await student.locator('.studentBank').innerText(), /3\s*\/\s*6/);
  await student.getByRole('tab', {name: '错题本', exact: true}).click();
  const personalNotebook = student.getByRole('tabpanel', {name: '错题本', exact: true});
  await personalNotebook.locator('.studentQuestionRow').first().waitFor();
  await personalNotebook.locator('.studentAnswerHistory > summary').first().click();
  await personalNotebook.locator('.studentAnswerCard').first().waitFor();
  await student.screenshot({path: path.join(out, 'personal-history.png'), fullPage: true});
  const personalMobile = active = await pageFor('student', true);
  await personalMobile.goto(personalUrl); await personalMobile.locator('.studentDashboard').waitFor();
  assert.ok(await personalMobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await personalMobile.screenshot({path: path.join(out, 'personal-mobile.png'), fullPage: true});
  assert.equal(await snapshot(), ownBefore); assert.deepEqual(errors, []);
  pass('Student menu opens the shared personal dashboard, private roster names stay admin-only, and both trees omit the storage root');

  active = page;
  await page.goto(url(auth.target)); await page.locator('.studentQualifications').waitFor();
  const qualifications = page.locator('.studentQualifications');
  const studentFlag = qualifications.getByRole('checkbox', {name: '学员', exact: true});
  assert.ok(await studentFlag.isChecked());
  await studentFlag.uncheck();
  await qualifications.getByRole('button', {name: '保存资格', exact: true}).click();
  await qualifications.getByText('账号资格已保存。', {exact: true}).waitFor();
  await page.reload(); await qualifications.waitFor();
  assert.equal(await studentFlag.isChecked(), false);
  await studentFlag.check();
  await qualifications.getByRole('button', {name: '保存资格', exact: true}).click();
  await qualifications.getByText('账号资格已保存。', {exact: true}).waitFor();
  pass('A managing administrator can demote, reload and restore a student while the account remains managed');

  if (!publicBase) {
    active = ordinary;
    await ordinary.goto(base + '/#/settings');
    const mode = ordinary.getByRole('checkbox', {name: '入门模式', exact: true});
    await mode.waitFor(); assert.ok(await mode.isChecked());
    await mode.uncheck(); await ordinary.locator('.profileForm button[type=submit]').click();
    await ordinary.waitForFunction(() => document.querySelector('.profileStatus')?.textContent.includes('已保存'));
    await ordinary.reload(); await mode.waitFor();
    assert.equal(await mode.isChecked(), false);
    await mode.check(); await ordinary.locator('.profileForm button[type=submit]').click();
    await ordinary.waitForFunction(() => document.querySelector('.profileStatus')?.textContent.includes('已保存'));
    pass('Beginner mode starts enabled and persists the account’s toggle across reloads');

    const lessonUrl = base + '/#/subjects/math/topic/synthetic-course';
    const advance = ordinary.locator('#stepCard .continueRow .primaryButton:not(#submitButton)');
    const answer = async () => {
      await ordinary.locator('#answerInput').fill('wrong');
      await ordinary.locator('#submitButton').click();
      await advance.waitFor();
    };
    await ordinary.goto(lessonUrl); await answer();
    const hint = ordinary.locator('.beginnerHint');
    await ordinary.waitForFunction(() => document.querySelector('.beginnerHint')?.textContent.includes('队列中已添加一道题'));
    assert.equal(await hint.evaluate(el => getComputedStyle(el).pointerEvents), 'none');
    await advance.click(); await answer();
    await ordinary.waitForFunction(() => document.querySelector('.beginnerHint')?.textContent.includes('队列中已添加两道题'));
    assert.equal(await hint.getAttribute('data-tone'), 'incorrect');
    assert.equal(await hint.locator('.beginnerHintIcon').textContent(), '×');
    assert.equal(await hint.locator('.beginnerHintIcon').getAttribute('aria-hidden'), 'true');
    for (const width of [320, 375, 414, 768]) {
      await ordinary.setViewportSize({width, height: 844});
      assert.ok(await hint.evaluate(el => {
        const rect = el.getBoundingClientRect(); return rect.left >= 0 && rect.right <= innerWidth;
      }));
    }
    await ordinary.screenshot({path: path.join(out, 'beginner-hint.png')});
    await ordinary.waitForFunction(() => !document.querySelector('.beginnerHint')?.textContent);
    await ordinary.goto(base + '/#/settings'); await mode.waitFor(); await mode.uncheck();
    await ordinary.locator('.profileForm button[type=submit]').click();
    await ordinary.waitForFunction(() => document.querySelector('.profileStatus')?.textContent.includes('已保存'));
    await ordinary.goto(lessonUrl);
    await advance.click(); await answer();
    assert.equal(await ordinary.locator('.beginnerHint:not(:empty)').count(), 0);
    pass('Actual wrong answers display the committed one- and two-question queue additions, then disappear or stay suppressed');
  }
  if (auth.beginner) {
    const site = publicBase || base + '/';
    const page = active = await pageFor('beginner');
    const hint = page.locator('.beginnerHint');
    async function expectHint(text, tone, icon) {
      await page.waitForFunction(text => document.querySelector('.beginnerHint')?.textContent.includes(text), text);
      assert.equal(await hint.getAttribute('data-tone'), tone);
      assert.equal(await hint.locator('.beginnerHintIcon').textContent(), icon);
    }
    async function answer(input, submit, text) {
      await page.locator(input).fill(text);
      await page.locator(submit).click();
    }
    const lesson = site + '#/subjects/math/topic/synthetic-course';
    const afterAnswer = page.locator('#stepCard .continueRow .primaryButton:not(#submitButton)');
    await page.goto(lesson);
    for (let i = 0; i < 2; i++) {
      await answer('#answerInput', '#submitButton', 'correct');
      await afterAnswer.click();
    }
    if (!publicBase) {
      // Deliver a real judged snapshot through the normal refresh path before
      // releasing the submit response. The tip must not depend on that response.
      let release, submitted;
      const held = new Promise(resolve => { release = resolve; });
      const sent = new Promise(resolve => { submitted = resolve; });
      await page.route('**/api/submit?**', async route => {
        const response = await route.fetch();
        submitted(); await held; await route.fulfill({response});
      }, {times: 1});
      await answer('#answerInput', '#submitButton', 'correct');
      try {
        await sent;
        await page.waitForFunction(async () => {
          window.dispatchEvent(new Event('online'));
          await new Promise(resolve => setTimeout(resolve, 200));
          return document.querySelector('.beginnerHint')?.textContent.includes('本轮练习已完成');
        }, undefined, {polling: 250, timeout: 15000});
      } finally { release(); }
    } else await answer('#answerInput', '#submitButton', 'correct');
    await expectHint('本轮练习已完成', 'success', '✓');
    await page.screenshot({path: path.join(out, 'hint-practice-complete.png')});
    await page.reload(); await afterAnswer.waitFor();
    assert.equal(await page.locator('.beginnerHint:not(:empty)').count(), 0);
    pass(publicBase ? 'Published practice completion does not replay from history' :
      'Practice completion appears even when a refreshed snapshot reaches Chrome before the submit response, and does not replay from history');

    await page.goto(site + '#/subjects/math/review/synthetic-course/module-2?session=' + encodeURIComponent(auth.beginner_review));
    await answer('#reviewAnswerInput', '#reviewSubmitButton', 'correct');
    await expectHint('本轮复习已完成', 'success', '✓');
    pass('A completed paradigm review displays its own green confirmation');

    await page.goto(site + '#/subjects/english/topic/atoms');
    await answer('#atomicAnswer', '#atomicAnswerForm button[type=submit]', '错误');
    await expectHint('本题答错', 'incorrect', '×');
    pass('A wrong atomic-card answer displays a red cross even without a schedule change');

    await page.goto(site + '#/subjects/math/banks/isolated-bank/group-a?question=choice');
    await page.locator('.choiceOption input[value="b"]').check();
    await page.locator('#trainingSubmit').click();
    await expectHint('本题已加入错题本', 'incorrect', '×');
    pass('A wrong question-bank answer explains the automatic error-notebook enrollment');

    await page.goto(site + '#/subjects/math/reviews/' + encodeURIComponent(auth.beginner_paper));
    await answer('#paperAnswer', '#paperSubmit', '2');
    await expectHint('本份复习已完成', 'success', '✓');
    pass('A settled review paper displays a green completion hint');

    await page.goto(lesson);
    await afterAnswer.click();
    await page.getByRole('button', {name: '已掌握，试着作答'}).click();
    await answer('#answerInput', '#submitButton', 'correct');
    await expectHint('例题答对，本模块已完成', 'success', '✓');
    await afterAnswer.click();
    await expectHint('本 Topic 已完成', 'success', '✓');
    pass('Correct direct-example feedback and final Topic completion each receive a green check');
  }
  assert.deepEqual(errors, []);
} catch (error) {
  if (active) await active.screenshot({path: path.join(out, 'failure.png'), fullPage: true}).catch(() => {});
  throw error;
} finally {
  await fs.writeFile(path.join(out, 'report.json'), JSON.stringify({checks, errors}, null, 2)); await browser.close();
}
