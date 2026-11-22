import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';

const [output, base = 'http://127.0.0.1:18885'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
await mkdir(output, {recursive: true});
const browser = await chromium.launch({headless: true, channel: 'chrome'});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, locale: 'zh-CN'});
const page = await context.newPage();
page.setDefaultTimeout(15000);
const errors = [], workerRequests = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  if (request.url().includes('/vendor/calculator/')) workerRequests.push(request.url().split('/').at(-1));
});
const launch = page.getByRole('button', {name: '计算器', exact: true});
const dialog = page.locator('.questionCalculator');
const outputBox = dialog.getByRole('status');
const tool = dialog.getByRole('combobox', {name: '其他计算工具'});
const next = page.getByRole('button', {name: '下一页', exact: true}).last();
async function select(value) {
  const tab = dialog.locator(`button[data-module="${value}"]`);
  if (await tab.count()) await tab.click();
  else await tool.selectOption(value);
}
const calculate = () => dialog.getByRole('button', {name: '计算结果'}).click();
const field = item => dialog.locator(`[name="${item}"]`);
async function text(value) {
  await outputBox.getByText(value, {exact: true}).waitFor();
}
async function open() {
  await launch.click();
  await dialog.waitFor();
}

try {
  const fixtureId = 'calculator-fixture';
  await page.goto(`${base}/#/subjects/math/topic/${fixtureId}`);
  await next.waitFor();
  assert.equal(await launch.count(), 0);
  assert.deepEqual(workerRequests, []);
  await next.click();
  await open();
  assert.equal(await dialog.getAttribute('data-layout'), 'side');
  assert.equal(await page.getByText('Calculator: Graphing', {exact: true}).count(), 0);
  assert.equal(await tool.count(), 0);
  assert.deepEqual(await dialog.locator('button[data-module]').evaluateAll(tabs => tabs.map(tab => tab.dataset.module)), ['expression', 'graph']);
  assert.equal(await dialog.locator('[data-calculator-key="sin"]').isDisabled(), true);
  await dialog.getByRole('textbox', {name: '表达式'}).fill('sin(30)');
  await calculate(); await text('当前题目未开放此运算。');
  await dialog.getByRole('textbox', {name: '表达式'}).fill('2^8');
  await dialog.getByRole('textbox', {name: '表达式'}).press('Enter');
  await text('256');
  await dialog.getByRole('combobox', {name: '选择常数'}).selectOption('c');
  assert.match(await dialog.getByRole('textbox', {name: '表达式'}).inputValue(), /c/);
  await select('graph');
  await field('expression').fill('x^2');
  await field('lower').fill('-3');
  await field('upper').fill('3');
  await calculate(); await dialog.locator('canvas').waitFor();
  await page.screenshot({path: path.join(output, 'desktop-side.png')});
  checks.push('Legacy Graphing shows scientific functions and graph only. Inherited key applies to typing.');

  await next.click();
  await dialog.waitFor({state: 'detached'});
  await open();
  assert.equal(await tool.locator('option[value="expression"], option[value="graph"]').count(), 0);
  assert.equal(await tool.locator('option[value="probability"]').count(), 0);
  assert.equal(await tool.locator('option[value="symbolic"]').count(), 0);
  await select('matrix');
  assert.equal(await field('a').count(), 1);
  assert.equal(await dialog.locator('option[value="matrix_inverse"]').evaluate(option => option.disabled), true);
  await dialog.getByRole('combobox', {name: '运算'}).selectOption('determinant');
  const matrix = dialog.getByRole('group', {name: '矩阵 A'});
  const cell = (row, column) => matrix.getByRole('textbox', {name: `矩阵 A ${row}, ${column}`, exact: true});
  await cell(1, 1).click();
  await dialog.getByText('屏幕键盘', {exact: true}).click();
  await dialog.locator('.calculatorToolKeyboard [data-calculator-key="digit_3"]').click();
  assert.equal(await cell(1, 1).inputValue(), '3');
  await cell(1, 2).fill('1'); await cell(2, 1).fill('2'); await cell(2, 2).fill('4');
  await calculate(); await text('10');
  await matrix.getByRole('button', {name: '文本输入'}).click();
  assert.equal(await field('a').inputValue(), '[[3,1],[2,4]]');
  await field('a').fill('[[1,2],[3,4]]'); await calculate(); await text('-2');
  await matrix.getByRole('button', {name: '结构化输入'}).click();
  assert.equal(await cell(2, 1).inputValue(), '3');
  await page.screenshot({path: path.join(output, 'desktop-matrix.png')});
  checks.push('Matrix cells accept keypad clicks and typing. Raw editing and grids round-trip, with the same engine.');
  await select('modular');
  await field('expression').fill('2^1000000000000000000000000000000000000000');
  await field('modulus').fill('7');
  await calculate(); await text('2');
  await select('machine_learning');
  await dialog.getByRole('combobox', {name: '运算'}).selectOption('softmax');
  await dialog.getByRole('button', {name: '文本输入'}).click();
  await field('x').fill('1000,1001,1002');
  await calculate();
  await outputBox.getByText(/0\.665240/).waitFor();
  checks.push('The per-question grant opens modular exponentiation and ML. Probability and inverse remain unavailable.');

  await select('expression');
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 840});
    await page.waitForFunction(() => document.querySelector('.questionCalculator')?.dataset.layout === 'center');
    const fit = await dialog.evaluate(element => ({
      body: document.documentElement.scrollWidth <= innerWidth,
      panel: element.scrollWidth <= element.clientWidth + 1,
      keys: [...element.querySelectorAll('.calculatorKey')].filter(key => key.getClientRects().length)
        .every(key => key.getBoundingClientRect().height >= 44),
    }));
    assert.deepEqual(fit, {body: true, panel: true, keys: true}, String(width));
    checks.push(`${width}px calculator fits and keypad targets are at least 44px tall.`);
  }
  await page.setViewportSize({width: 375, height: 840});
  await page.screenshot({path: path.join(output, 'mobile-center.png')});
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  assert.equal(await launch.evaluate(element => element === document.activeElement), true);
  await next.click(); await open();
  assert.equal(await dialog.locator('.calculatorNavigation').count(), 0);
  assert.equal(await dialog.locator('[data-calculator-key="sin"]').count(), 0);
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  await next.click();
  assert.equal(await launch.count(), 0);
  await next.click(); await open();
  await select('symbolic');
  await dialog.getByRole('combobox', {name: '运算'}).selectOption('antiderivative');
  await field('expression').fill('x^2');
  await field('variable').fill('x');
  await calculate(); await text('(1/3)*x^3 + C');
  checks.push('Question navigation revokes the previous dialog and reaches basic, disabled and CAS fixtures.');
  await select('optimization');
  await dialog.getByRole('button', {name: '填入示例'}).click();
  await dialog.getByRole('textbox', {name: 'capacity 界值'}).fill('120');
  await calculate(); await outputBox.getByText('60', {exact: true}).waitFor();
  await dialog.getByRole('button', {name: '文本输入'}).click();
  const model = JSON.parse(await field('model').inputValue());
  assert.equal(model.constraints.capacity.max, 120);
  model.constraints.capacity.max = 80;
  await field('model').fill(JSON.stringify(model));
  await dialog.getByRole('button', {name: '结构化输入'}).click();
  assert.equal(await dialog.getByRole('textbox', {name: 'capacity 界值'}).inputValue(), '80');
  await calculate(); await outputBox.getByText('40', {exact: true}).waitFor();
  await select('astronomy');
  assert.equal(await field('date').getAttribute('type'), 'date');
  assert.equal(await dialog.locator('.calculatorToolKeyboard').count(), 0);
  await field('date').fill('2026-02-28');
  await calculate(); await outputBox.getByText('月相角 (°)', {exact: true}).waitFor();
  checks.push('Optimization coefficients and constraints round-trip to JSON. The native date field accepts typed dates.');
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'browser-result.json'), JSON.stringify({checks, workerRequests, errors}, null, 2) + '\n');
  console.log(JSON.stringify({checks, pageErrors: errors.length}));
} catch (error) {
  await page.screenshot({path: path.join(output, 'failure.png')}).catch(() => {});
  throw error;
} finally {
  await browser.close();
}
