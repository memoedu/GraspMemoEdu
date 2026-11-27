import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [output, base = 'http://127.0.0.1:18885'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
await mkdir(output, {recursive: true});
const browser = await launchAcceptanceChrome(require);
const context = await browser.newContext({viewport: {width: 1440, height: 900}, locale: 'zh-CN'});
await context.addInitScript(() => {
  Object.defineProperty(navigator, 'clipboard', {value: {writeText: async value => {
    if (window.rejectCalculatorClipboard) throw new DOMException('Denied', 'NotAllowedError');
    window.copiedCalculatorText = value;
  }}});
});
const page = await context.newPage();
page.setDefaultTimeout(15000);
const errors = [], workerRequests = [], checks = [];
let workerStarts = 0;
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => {
  const asset = new URL(request.url()).pathname;
  if (asset.endsWith('/calculator-worker.js')) workerStarts++;
  if (/\/vendor\/calculator\/(core|advanced|applied|symbolic)\.mjs$/.test(asset)) workerRequests.push(asset.split('/').at(-1));
});
const toolbar = page.getByRole('toolbar', {name: '题目工具'});
const allWorksheets = ['expression', 'graph', 'symbolic', 'statistics', 'machine_learning'];
const tool = value => toolbar.locator(`[data-question-tool="${value}"]`);
const launch = tool('expression');
const dialog = page.locator('.questionCalculator');
const outputBox = dialog.locator('.calculatorResult');
const next = page.getByRole('button', {name: '下一页', exact: true}).last();
async function select(value) {
  await tool(value).click();
  await page.locator(`.questionCalculator[data-module="${value}"]`).waitFor();
}
const toolIds = () => toolbar.locator('.calculatorLaunch:not([data-question-tool=whiteboard])')
  .evaluateAll(buttons => buttons.map(button => button.dataset.questionTool));
const calculate = () => dialog.getByRole('button', {name: '计算结果'}).click();
const field = item => dialog.locator(`[name="${item}"]`);
const expressionInput = dialog.getByRole('textbox', {name: '表达式'});
const completions = page.locator('.inputCompletions');
const option = label => completions.getByRole('option', {name: label, exact: true});
const assign = dialog.getByRole('button', {name: '变量值', exact: true});
const variable = name => dialog.getByRole('textbox', {name: `变量 ${name}`, exact: true});
const copyResult = dialog.getByRole('button', {name: '复制结果', exact: true});
const storeResult = dialog.getByRole('button', {name: '储存', exact: true});
const defineFunction = dialog.getByRole('button', {name: '定义函数', exact: true});
const recall = dialog.getByRole('button', {name: '调用储值', exact: true});
const more = dialog.locator('.calculatorMore');
const categories = more.getByRole('combobox', {name: '类别'});
const extensionForm = more.locator('.calculatorExtensionForm form');
const calculateExtension = () => extensionForm.getByRole('button', {name: '计算结果'}).click();
async function category(id) {
  if (!await categories.isVisible()) await more.locator(':scope > summary').click();
  await categories.selectOption(id);
}
async function store(letter, result) {
  await copyResult.click();
  assert.equal(await page.evaluate(() => window.copiedCalculatorText), result);
  assert.equal(await dialog.locator('[data-calculator-key="digit_7"]').isVisible(), true);
  await storeResult.click();
  assert.equal(await dialog.locator('[data-calculator-key="digit_7"]').isVisible(), false);
  await dialog.getByRole('button', {name: `存入 ${letter}`, exact: true}).click();
  assert.equal(await dialog.locator('[data-calculator-key="digit_7"]').isVisible(), true);
}
async function enter(expression, result) {
  await expressionInput.fill(expression);
  await calculate();
  await text(result);
}
async function sidebarOrientation(cardSelector) {
  return toolbar.evaluate((element, selector) => {
    const card = document.querySelector(selector).getBoundingClientRect();
    const rail = element.closest('.questionToolRail').getBoundingClientRect();
    const history = document.querySelector('.appLayout:not([hidden]) .historySidebar');
    const previous = history?.getBoundingClientRect();
    const group = element.querySelector('.questionToolGroup');
    const scroller = element.querySelector('.questionToolGroups');
    return {
      rightOfCard: rail.left >= card.right && Math.abs(rail.top - card.top) <= 1,
      leftHistory: !previous || previous.right <= card.left,
      direction: getComputedStyle(group).flexDirection,
      fits: scroller.scrollWidth <= scroller.clientWidth && document.documentElement.scrollWidth <= innerWidth,
    };
  }, cardSelector);
}
async function text(value) {
  await outputBox.getByText(value, {exact: true}).waitFor();
}
function resultTypography() {
  return outputBox.evaluate(result => {
    const {fontFamily, fontSize, fontWeight, letterSpacing, lineHeight} = getComputedStyle(result);
    return {fontFamily, fontSize, fontWeight, letterSpacing, lineHeight};
  });
}
async function open() {
  await select('expression');
}

try {
  const fixtureId = 'calculator-fixture';
  await page.goto(`${base}/#/subjects/math/topic/${fixtureId}`);
  await next.waitFor();
  assert.equal(await toolbar.count(), 0);
  const readingTools = page.getByRole('toolbar', {name: '正文工具'});
  await readingTools.getByRole('button', {name: '白板', exact: true}).waitFor();
  await readingTools.getByRole('button', {name: '科学计算器', exact: true}).waitFor();
  assert.deepEqual(workerRequests, []);
  await next.click();
  assert.deepEqual(await toolIds(), allWorksheets);
  assert.equal(await launch.textContent(), '');
  assert.equal(await launch.getAttribute('aria-label'), '科学计算器');
  assert.equal(await page.locator('#stepCard .questionTools').count(), 0);
  for (const [width, direction] of [[1440, 'row'], [1120, 'column'], [768, 'column'], [414, 'column'],
                                    [375, 'column'], [320, 'column'], [1440, 'row']]) {
    await page.setViewportSize({width, height: 900});
    await page.waitForFunction(expanded => document.getElementById('historyButton')
      .getAttribute('aria-expanded') === expanded, String(width > 1000));
    assert.deepEqual(await sidebarOrientation('#stepCard'), {
      rightOfCard: true, leftHistory: true, direction, fits: true,
    }, String(width));
  }
  await page.setViewportSize({width: 1120, height: 900});
  await launch.focus();
  await launch.press('ArrowDown');
  assert.equal(await tool('graph').evaluate(button => button === document.activeElement), true);
  await page.locator('#historyButton').click();
  assert.equal((await sidebarOrientation('#stepCard')).direction, 'row');
  await page.locator('#historyButton').click();
  assert.equal((await sidebarOrientation('#stepCard')).direction, 'column');
  await page.setViewportSize({width: 1440, height: 900});
  await launch.focus();
  await launch.press('ArrowRight');
  assert.equal(await tool('graph').evaluate(button => button === document.activeElement), true);
  const backend = '**/api/**';
  const worker = /\/calculator-worker\.js\?v=/;
  const rejectBackend = route => route.abort('internetdisconnected');
  let releaseWorker;
  const workerReady = new Promise(resolve => { releaseWorker = resolve; });
  await context.route(backend, rejectBackend);
  await context.route(worker, async route => {
    await workerReady;
    await route.continue();
  });
  await tool('graph').press('Enter');
  await page.locator('.questionCalculator[data-module="graph"]').waitFor();
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  assert.equal(await tool('graph').evaluate(button => button === document.activeElement), true);
  assert.equal(await tool('graph').getAttribute('aria-expanded'), 'false');
  const {openFrameMs, opened} = await launch.evaluate(button => {
    const start = performance.now();
    button.click();
    const panel = document.querySelector('.questionCalculator[open]');
    return {openFrameMs: performance.now() - start, opened: !!panel && panel.contains(document.activeElement)};
  });
  assert.equal(opened, true);
  assert.ok(openFrameMs >= 0 && openFrameMs < 100, `Calculator took ${openFrameMs} ms to render`);
  assert.equal(workerStarts, 0);
  assert.deepEqual(workerRequests, []);
  assert.equal(await dialog.getByRole('button', {name: '关闭计算器', exact: true}).count(), 1);
  assert.equal(await dialog.locator('.calculatorLayoutToggle').count(), 0);
  assert.equal(await dialog.evaluate(panel => {
    const {left, right} = panel.getBoundingClientRect();
    return left >= document.querySelector('.questionToolRail').getBoundingClientRect().right
      && getComputedStyle(panel).right === '12px' && right <= innerWidth;
  }), true);
  assert.equal(await page.getByText('Calculator: Graphing', {exact: true}).count(), 0);
  assert.equal(await dialog.locator('.calculatorNavigation').count(), 0);
  assert.equal(await dialog.locator('[data-calculator-key="sin"]').isEnabled(), true);
  await expressionInput.fill('2+3*4-8/2');
  const immediate = await dialog.getByRole('button', {name: '计算结果'}).evaluate(control => {
    const start = performance.now();
    control.click();
    return {ms: performance.now() - start, result: document.querySelector('.calculatorResult').textContent};
  });
  assert.equal(immediate.result, '10');
  assert.ok(immediate.ms < 50, `Cold arithmetic took ${immediate.ms} ms`);
  assert.equal(workerStarts, 0);
  assert.deepEqual(workerRequests, []);
  await enter('2×（3+(4', '14');
  assert.equal(await expressionInput.inputValue(), '2×（3+(4');
  assert.equal(workerStarts, 0);
  await dialog.getByRole('textbox', {name: '表达式'}).fill('sin(0)');
  await context.unroute(backend, rejectBackend);
  await calculate(); await text('计算中…');
  releaseWorker();
  await text('0');
  checks.push('Panels accept input with the backend unavailable and before any Worker request. Evaluation waits for the Worker.');
  await dialog.getByRole('textbox', {name: '表达式'}).fill('2^8');
  await dialog.getByRole('textbox', {name: '表达式'}).press('Enter');
  await text('256');
  await page.screenshot({path: path.join(output, 'desktop-scientific.png')});
  const notation = dialog.getByRole('button', {name: '切换结果格式'});
  await notation.waitFor({state: 'hidden'});
  await expressionInput.fill('1.2*10^24');
  await expressionInput.press('Enter');
  await text('1.2e+24');
  const scientificTypography = await resultTypography();
  await notation.press('Space');
  await text('1200000000000000000000000');
  assert.deepEqual(await resultTypography(), scientificTypography);
  assert.equal(await notation.getAttribute('aria-pressed'), 'true');
  await page.screenshot({path: path.join(output, 'decimal-result.png'), animations: 'disabled'});
  await notation.click();
  await text('1.2e+24');
  assert.deepEqual(await resultTypography(), scientificTypography);
  assert.equal(await notation.getAttribute('aria-pressed'), 'false');
  await expressionInput.fill('-2.5*10^(-9)');
  await expressionInput.press('Enter');
  await text('-2.5e-9');
  await notation.click();
  await text('-0.0000000025');
  await page.setViewportSize({width: 320, height: 840});
  await expressionInput.fill('10^100');
  await expressionInput.press('Enter');
  await text('1e+100');
  const mobileTypography = await resultTypography();
  await notation.click();
  await text('1' + '0'.repeat(100));
  assert.deepEqual(await resultTypography(), mobileTypography);
  assert.equal(await outputBox.evaluate(result => result.scrollWidth <= result.clientWidth), true);
  await page.setViewportSize({width: 1440, height: 900});
  await expressionInput.fill('2+3');
  await expressionInput.press('Enter');
  await text('5');
  await notation.waitFor({state: 'hidden'});
  checks.push('FORMAT toggles large and small scalar results without recalculation or typography changes on desktop or mobile.');
  await store('A', '5');
  await enter('A += 1', '6');
  await enter('A -= 1', '5');
  await enter('A == 5', '1');
  await enter('A != 5', '0');
  await expressionInput.fill('');
  await recall.click();
  assert.equal(await dialog.getByRole('button', {name: '调用 B', exact: true}).isDisabled(), true);
  await page.screenshot({path: path.join(output, 'memory-recall.png')});
  await dialog.getByRole('button', {name: '调用 A', exact: true}).press('Enter');
  assert.equal(await expressionInput.inputValue(), 'A');
  await enter('A*2', '10');
  await store('A', '10');
  await page.evaluate(() => { window.rejectCalculatorClipboard = true; });
  await copyResult.click();
  await dialog.getByText('剪贴板不可用。', {exact: true}).waitFor({state: 'attached'});
  await storeResult.click();
  await dialog.getByRole('button', {name: '存入 B', exact: true}).click();
  await enter('B', '10');
  await page.evaluate(() => { window.rejectCalculatorClipboard = false; });
  await enter('θ=5', '5');
  await expressionInput.fill('θ+3');
  await storeResult.click();
  const storageName = dialog.getByRole('textbox', {name: '储存变量名'});
  assert.equal(await storageName.evaluate(input => input === document.activeElement), true);
  assert.equal(await dialog.locator('[data-calculator-key="digit_7"]').isVisible(), false);
  await dialog.getByRole('button', {name: '存入 C', exact: true}).waitFor();
  await storageName.fill('v^{2}');
  await page.screenshot({path: path.join(output, 'named-storage.png')});
  await storageName.press('Enter');
  await text('8');
  assert.equal(await dialog.locator('[data-calculator-key="digit_7"]').isVisible(), true);
  await enter('3+3', '6');
  await storeResult.click();
  await dialog.getByRole('button', {name: '存入 C', exact: true}).click();
  await enter('C', '6');
  await enter('ρ₁=2', '2');
  await enter('v²+ρ_1+θ', '15');
  await dialog.getByRole('button', {name: '储存', exact: true}).click();
  await storageName.fill('sₐ');
  await dialog.getByRole('button', {name: '保存', exact: true}).click();
  await enter('s_a+1', '16');
  await expressionInput.fill('A+x');
  await assign.click();
  await variable('x').fill('2');
  assert.equal(await variable('A').count(), 0);
  await calculate(); await text('12');
  await recall.click();
  await dialog.locator('#calculatorRegisterPad').press('Escape');
  assert.equal(await dialog.isVisible(), true);
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  await open();
  assert.equal(await recall.isDisabled(), false);
  await enter('A', '10');
  await expressionInput.fill('A+T');
  await assign.click();
  await variable('T').waitFor();
  assert.equal(await variable('A').count(), 0);
  checks.push('Store, overwrite, caret recall, separate clipboard copy, and same-question memory on reopen.');
  await more.locator(':scope > summary').click();
  assert.equal(await categories.inputValue(), 'common');
  assert.equal(await categories.locator('option:checked').textContent(), '一元函数');
  await more.getByRole('button', {name: 'sinh', exact: true}).waitFor();
  await categories.selectOption('multi');
  await more.getByRole('button', {name: 'nCr', exact: true}).waitFor();
  await categories.selectOption('common');
  await more.locator(':scope > summary').click();
  await expressionInput.fill('$\\sinh（0）+\\cosh（0）$');
  await expressionInput.press('Enter');
  await text('1');
  await enter('X = 8', '8');
  await enter('F = X + 1', '9');
  await defineFunction.click();
  assert.equal(await defineFunction.getAttribute('aria-pressed'), 'true');
  await expressionInput.fill('X + 1');
  await calculate();
  await text('请输入函数定义，例如 F = X + 1 或 F(X, Y) = X + Y。');
  assert.equal(await defineFunction.getAttribute('aria-pressed'), 'true');
  await enter('F = X + 1', 'F(X) = X + 1');
  assert.equal(await defineFunction.getAttribute('aria-pressed'), 'false');
  await enter('Ans', '9');
  await expressionInput.fill('F');
  await option('F').waitFor();
  await expressionInput.press('Tab');
  assert.equal(await expressionInput.inputValue(), 'F(');
  await expressionInput.pressSequentially('3)');
  await expressionInput.press('Enter');
  await text('4');
  await defineFunction.click();
  await enter('G = 10*Y + X', 'G(X, Y) = 10*Y + X');
  await enter('G（3，4）', '43');
  await enter('G（3，(2+3', '53');
  checks.push('Chinese and ASCII parentheses mix, and missing trailing closers work with local arithmetic and Worker functions.');
  await enter('G(Y, X) = 10*Y + X', 'G(Y, X) = 10*Y + X');
  await enter('G(3, 4)', '34');
  await enter('F = X + 1', '9');
  await enter('F(3)', '请检查函数名与括号中的参数个数。');
  await enter('F', '9');
  await expressionInput.fill('F(3)');
  await expressionInput.evaluate(input => input.setSelectionRange(1, 1));
  await expressionInput.evaluate(input => input.dispatchEvent(new Event('input', {bubbles: true})));
  assert.equal(await option('F').count(), 0);
  checks.push('Unary default, multivariable picker, symbolic definition mode, explicit parameters, native completion and overwrite.');
  await expressionInput.fill('f');
  await option('floor').waitFor();
  await expressionInput.press('Tab');
  assert.equal(await expressionInput.inputValue(), 'floor(');
  await expressionInput.pressSequentially('3.9)');
  await expressionInput.press('Enter'); await text('3');
  await expressionInput.fill('2*fl(3.9)+1');
  await expressionInput.evaluate(input => input.setSelectionRange(4, 4));
  await expressionInput.evaluate(input => input.dispatchEvent(new Event('input', {bubbles: true})));
  await expressionInput.press('ArrowDown');
  await expressionInput.press('Enter');
  assert.equal(await expressionInput.inputValue(), '2*floor(3.9)+1');
  await expressionInput.press('Enter'); await text('7');
  await expressionInput.fill('');
  await dialog.getByRole('button', {name: '指定底数的对数'}).click();
  assert.equal(await expressionInput.inputValue(), 'log_');
  await expressionInput.pressSequentially('2(8)');
  await expressionInput.press('Enter'); await text('3');
  await expressionInput.fill('answer^2');
  await expressionInput.press('Enter'); await text('9');
  await expressionInput.fill('si');
  await option('sinh').waitFor();
  await option('sin').waitFor();
  checks.push('Prefix, Tab, arrows, caret replacement, Enter calculation, based log key, answer alias, and unlocked completions.');
  await expressionInput.fill('x^2');
  await calculate();
  await text('请点击「变量值」，并填写原式中每个未储存变量的值。');
  await assign.click();
  await variable('x').waitFor();
  assert.equal(await dialog.locator('.calculatorAssignmentValue').count(), 1);
  await dialog.locator('[data-calculator-key="digit_3"]').click();
  assert.equal(await variable('x').inputValue(), '3');
  assert.equal(await expressionInput.inputValue(), 'x^2');
  await variable('x').press('Enter');
  await text('9');
  await expressionInput.fill('x*y+z');
  assert.equal(await dialog.locator('.calculatorAssignmentValue').count(), 0);
  await assign.click();
  await variable('z').waitFor();
  assert.equal(await dialog.locator('.calculatorAssignmentValue').count(), 3);
  assert.equal(await variable('x').inputValue(), '3');
  await variable('y').fill('1+1');
  await variable('z').fill('4');
  await calculate();
  await text('10');
  checks.push('Scientific calculation supports one or more assignments with the same keypad, keyboard, and numeric parser.');
  await expressionInput.focus();
  await dialog.getByRole('combobox', {name: '选择常数'}).selectOption('c');
  assert.match(await dialog.getByRole('textbox', {name: '表达式'}).inputValue(), /c/);
  await select('graph');
  await field('expression').fill('f');
  await option('floor').waitFor();
  await field('expression').press('Escape');
  await completions.waitFor({state: 'hidden'});
  assert.equal(await dialog.isVisible(), true);
  await field('expression').fill('x^2');
  await field('lower').fill('-3');
  await field('upper').fill('3');
  await calculate(); await dialog.locator('canvas').waitFor();
  await page.screenshot({path: path.join(output, 'desktop-side.png')});
  await open();
  assert.match(await dialog.getByRole('textbox', {name: '表达式'}).inputValue(), /c/);
  checks.push('Legacy Graphing questions now get every worksheet. Keyboard focus and drafts are preserved.');

  await next.click();
  await dialog.waitFor({state: 'detached'});
  assert.deepEqual(await toolIds(), allWorksheets);
  assert.deepEqual(await toolbar.locator('.questionToolGroup:has(.calculatorLaunch:not([data-question-tool=whiteboard]))').evaluateAll(groups => groups.map(group =>
    [...group.querySelectorAll('[data-question-tool]')].map(tool => tool.dataset.questionTool))), [
    ['expression', 'graph', 'symbolic'],
    ['statistics', 'machine_learning'],
  ]);
  assert.deepEqual(await sidebarOrientation('#stepCard'), {
    rightOfCard: true, leftHistory: true, direction: 'row', fits: true,
  });
  await page.screenshot({path: path.join(output, 'desktop-toolbar.png')});
  checks.push('Tools stay next to the card at 320–1440px, switch direction on resize, and organize related worksheets in groups.');
  await open();
  assert.equal(await categories.isVisible(), false);
  await category('matrix');
  assert.equal(await more.locator('[data-calculator-key="matrix_inverse"]').isEnabled(), true);
  await enter('determinant([[1,2],[3,4]])+4', '2');
  await more.getByText('表单输入', {exact: true}).click();
  await field('a').waitFor({state: 'attached'});
  assert.equal(await dialog.locator('option[value="matrix_inverse"]').evaluate(option => option.disabled), false);
  await dialog.getByRole('combobox', {name: '运算'}).selectOption('determinant');
  const matrix = dialog.getByRole('group', {name: '矩阵 A'});
  const cell = (row, column) => matrix.getByRole('textbox', {name: `矩阵 A ${row}, ${column}`, exact: true});
  await cell(1, 1).click();
  await dialog.getByText('屏幕键盘', {exact: true}).click();
  const digitRow = await dialog.locator('.calculatorToolKeyboard .calculatorKey').evaluateAll(keys =>
    keys.filter(key => key.offsetTop === keys[0].offsetTop).map(key => key.dataset.calculatorKey));
  assert.deepEqual(digitRow, ['digit_7', 'digit_8', 'digit_9', 'backspace']);
  await dialog.locator('.calculatorToolKeyboard [data-calculator-key="digit_3"]').click();
  assert.equal(await cell(1, 1).inputValue(), '3');
  await cell(1, 2).fill('1'); await cell(2, 1).fill('2'); await cell(2, 2).fill('4');
  await calculateExtension(); await text('10');
  await matrix.getByRole('button', {name: '文本输入'}).click();
  assert.equal(await field('a').inputValue(), '[[3,1],[2,4]]');
  await field('a').fill('[[1,2],[3,4]]'); await calculateExtension(); await text('-2');
  await matrix.getByRole('button', {name: '结构化输入'}).click();
  assert.equal(await cell(2, 1).inputValue(), '3');
  await page.screenshot({path: path.join(output, 'desktop-matrix.png')});
  checks.push('Matrix cells accept keypad clicks and typing. Raw editing and grids round-trip, with the same engine.');
  const mod = dialog.getByRole('button', {name: '精确模幂', exact: true});
  await expressionInput.fill('2^1000000000000000000000000000000000000000');
  await mod.click();
  await dialog.getByRole('textbox', {name: '正整数模数'}).fill('7');
  await dialog.getByRole('button', {name: '取模', exact: true}).click(); await text('2');
  await mod.click();
  await category('machine_learning');
  await expressionInput.fill('');
  await more.getByRole('button', {name: 'Softmax', exact: true}).click();
  assert.equal(await expressionInput.inputValue(), 'softmax([1000,1001,1002])');
  await expressionInput.press('Enter');
  await outputBox.getByText(/0\.665240/).waitFor();
  await enter('2*sigmoid(0) + cosine_similarity(Ans, Ans)', '2');
  await expressionInput.fill('cross_e');
  await option('cross_entropy').waitFor();
  await expressionInput.press('Escape');
  await page.screenshot({path: path.join(output, 'desktop-ml-functions.png')});
  await select('machine_learning');
  assert.deepEqual(await dialog.getByRole('combobox', {name: '运算'}).locator('option').evaluateAll(options =>
    options.map(option => option.value)), ['classification', 'pca']);
  checks.push('Exact modular powers and composable ML functions share the expression. PCA and classification stay separate.');

  await select('expression');
  await expressionInput.fill('x+y+z');
  await assign.click();
  await variable('z').waitFor();
  await variable('x').fill('1');
  await variable('y').fill('2');
  await variable('z').fill('4');
  await calculate();
  await text('7');
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({width, height: 840});
    await expressionInput.fill('x+y+z');
    await page.waitForFunction(() => {
      const panel = document.querySelector('.questionCalculator[open]').getBoundingClientRect();
      const tools = document.querySelector('.questionToolRow[data-calculator-open]').getBoundingClientRect();
      return panel.top >= tools.bottom;
    });
    const fit = await dialog.evaluate(element => ({
      body: document.documentElement.scrollWidth <= innerWidth,
      panel: element.scrollWidth <= element.clientWidth + 1,
      right: getComputedStyle(element).right === '8px' && element.getBoundingClientRect().right <= innerWidth,
      keys: [...element.querySelectorAll('.calculatorKey')].filter(key => key.getClientRects().length)
        .every(key => key.getBoundingClientRect().height >= 44 && key.getBoundingClientRect().width >= 44),
    }));
    assert.deepEqual(fit, {body: true, panel: true, right: true, keys: true}, String(width));
    const primaryActionsVisible = await dialog.evaluate(element => {
      const bottom = element.getBoundingClientRect().bottom;
      return ['digit_7', 'evaluate'].every(id =>
        element.querySelector(`[data-calculator-key="${id}"]`).getBoundingClientRect().bottom <= bottom);
    });
    assert.equal(primaryActionsVisible, true, String(width));
    assert.equal(await toolbar.getByRole('button').evaluateAll(buttons => buttons.every(button => {
      const bounds = button.getBoundingClientRect();
      return bounds.left >= 0 && bounds.right <= innerWidth && bounds.width >= 44 && bounds.height >= 44;
    })), true, String(width));
    if (width === 375) await page.screenshot({path: path.join(output, 'mobile-right.png')});
    await expressionInput.fill('f');
    await option('floor').waitFor();
    assert.equal(await completions.evaluate(menu => {
      const bounds = menu.getBoundingClientRect();
      return bounds.left >= 0 && bounds.right <= document.body.getBoundingClientRect().right
        && bounds.top >= 0 && bounds.bottom <= innerHeight;
    }), true, String(width));
    if (width === 375) await page.screenshot({path: path.join(output, 'mobile-completions.png')});
    await expressionInput.press('Escape');
    checks.push(`${width}px right calculator fits and keypad targets are at least 44px by 44px.`);
  }
  await enter('2+3', '5');
  await store('F', '5');
  await enter('F+1', '6');
  await page.setViewportSize({width: 375, height: 840});
  await launch.press('End');
  assert.equal(await tool('machine_learning').evaluate(button => button === document.activeElement), true);
  assert.ok(await toolbar.locator('.questionToolGroups').evaluate(list => list.scrollTop > 0));
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  assert.equal(await launch.evaluate(element => element === document.activeElement), true);
  await next.click(); await open();
  assert.deepEqual(await toolIds(), allWorksheets);
  assert.equal(await dialog.locator('[data-calculator-key="sin"]').isEnabled(), true);
  await enter('6*7', '42');
  await store('D', '42');
  await enter('D/2', '21');
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  await next.click();
  await launch.waitFor();
  assert.deepEqual(await toolIds(), allWorksheets);
  await next.click(); await open();
  await expressionInput.fill('2x');
  await assign.click();
  await variable('x').fill('6');
  await calculate();
  await text('12');
  await store('C', '12');
  await enter('C+1', '13');
  await expressionInput.fill('2*x+3*x+y-y');
  await dialog.getByRole('button', {name: '化简', exact: true}).click();
  await text('5*x');
  assert.equal(await expressionInput.inputValue(), '2*x+3*x+y-y');
  await copyResult.click();
  assert.equal(await page.evaluate(() => window.copiedCalculatorText), '5*x');
  assert.equal(await dialog.locator('[data-calculator-key="digit_7"]').isVisible(), true);
  await select('symbolic');
  await dialog.getByRole('combobox', {name: '运算'}).selectOption('antiderivative');
  await field('expression').fill('x^2');
  await field('variable').fill('x');
  await calculate(); await text('(1/3)*x^3 + C');
  checks.push('Question navigation closes the previous dialog. Basic and disabled material both receive the full tools.');
  await open();
  await category('optimization');
  await dialog.getByRole('button', {name: '填入示例'}).click();
  await dialog.getByRole('textbox', {name: 'capacity 界值'}).fill('120');
  await calculateExtension(); await outputBox.getByText('60', {exact: true}).waitFor();
  await dialog.getByRole('button', {name: '文本输入'}).click();
  const model = JSON.parse(await field('model').inputValue());
  assert.equal(model.constraints.capacity.max, 120);
  model.constraints.capacity.max = 80;
  await field('model').fill(JSON.stringify(model));
  await dialog.getByRole('button', {name: '结构化输入'}).click();
  assert.equal(await dialog.getByRole('textbox', {name: 'capacity 界值'}).inputValue(), '80');
  await calculateExtension(); await outputBox.getByText('40', {exact: true}).waitFor();
  await category('astronomy');
  assert.equal(await field('date').getAttribute('type'), 'date');
  assert.equal(await dialog.locator('.calculatorToolKeyboard').count(), 0);
  await field('date').fill('2026-02-28');
  await calculateExtension(); await outputBox.getByText('月相角 (°)', {exact: true}).waitFor();
  checks.push('Optimization coefficients and constraints round-trip to JSON. The native date field accepts typed dates.');
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto(`${base}/#/subjects/math/banks/isolated-bank/group-a?question=essay`);
  await toolbar.waitFor();
  assert.deepEqual(await toolIds(), allWorksheets);
  assert.equal(await page.locator('#trainingstepCard .questionTools').count(), 0);
  assert.deepEqual(await sidebarOrientation('#trainingstepCard'), {
    rightOfCard: true, leftHistory: true, direction: 'row', fits: true,
  });
  const bankAnswer = page.locator('form.answerForm textarea[name=answer]');
  await bankAnswer.fill('f');
  await option('floor').waitFor();
  await bankAnswer.press('Tab');
  await page.locator('form.answerForm .formulaInput math-field').waitFor();
  await page.keyboard.press('x');
  await page.waitForFunction(() => /f.*x/.test(document.querySelector('form.answerForm textarea[name=answer]').value));
  await page.keyboard.press('Escape');
  await page.keyboard.press('Backspace');
  assert.equal(await bankAnswer.inputValue(), '');
  await select('graph');
  await page.getByRole('button', {name: '隔离习题 exact', exact: true}).click();
  await page.getByRole('heading', {name: '习题 2', exact: true}).waitFor();
  await dialog.waitFor({state: 'detached'});
  assert.deepEqual(await toolIds(), allWorksheets);
  await open();
  await enter('determinant([[1,2],[3,4]])', '-2');
  checks.push('Standalone question banks allow the full calculator on questions without calculator metadata.');
  const pageTools = page.locator('#pageTools');
  for (const route of ['courses', 'banks', 'reviews']) {
    await page.setViewportSize({width: 320, height: 840});
    await page.goto(`${base}/#/subjects/math/${route}`);
    await pageTools.locator('[data-question-tool="expression"]').click();
    await enter('2+2', '4');
    assert.equal(await dialog.getByRole('button', {name: '转换', exact: true}).isVisible(), false);
    assert.ok(await pageTools.evaluate(node => node.scrollWidth <= node.clientWidth), route);
  }
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto(`${base}/#/settings`);
  await dialog.waitFor({state: 'detached'});
  assert.equal(await pageTools.locator('[data-question-tool="expression"]').count(), 0);
  await page.goto(`${base}/#/`);
  assert.equal(await pageTools.locator('[data-question-tool="expression"]').count(), 0);
  checks.push('Course, bank and review directories work at 320px; settings and the site home have no calculator.');
  await page.goto(`${base}/#/settings`);
  const settings = page.getByRole('group', {name: '自动补全'});
  const checkbox = name => settings.getByRole('checkbox', {name, exact: true});
  for (const name of ['计算器', '回答', '其他']) assert.equal(await checkbox(name).isChecked(), true);
  await page.screenshot({path: path.join(output, 'autocomplete-settings.png')});
  await checkbox('回答').uncheck();
  await page.reload();
  assert.equal(await checkbox('回答').isChecked(), false);
  assert.equal(await checkbox('计算器').isChecked(), true);
  const zone = page.locator('#profileTimezone');
  await zone.fill('Asia/Sh');
  await option('Asia/Shanghai').waitFor();
  await zone.press('Tab');
  assert.equal(await zone.inputValue(), 'Asia/Shanghai');
  await page.locator('#userMenuButton').click();
  await page.locator('#supportButton').click();
  const feedback = page.locator('#feedbackMessage');
  await feedback.fill('sq');
  await option('sqrt').click();
  await page.locator('dialog[open] .formulaInput math-field').waitFor();
  await page.keyboard.press('2');
  await page.waitForFunction(() => /\\sqrt\s*(?:\{2\}|2)/.test(document.querySelector('#feedbackMessage').value));
  await page.locator('dialog[open]').getByRole('button', {name: '取消', exact: true}).click();
  await page.goto(`${base}/#/subjects/math/banks/isolated-bank/group-a?question=essay`);
  await bankAnswer.fill('f');
  await completions.waitFor({state: 'hidden'});
  await open();
  await expressionInput.fill('f');
  await option('floor').waitFor();
  await dialog.getByRole('button', {name: '关闭计算器'}).click();
  await page.goto(`${base}/#/settings`);
  await checkbox('其他').uncheck();
  await checkbox('计算器').uncheck();
  await zone.fill('Asia/Sh');
  await completions.waitFor({state: 'hidden'});
  await page.goto(`${base}/#/subjects/math/banks/isolated-bank/group-a?question=essay`);
  await bankAnswer.fill('f');
  await completions.waitFor({state: 'hidden'});
  await open();
  await expressionInput.fill('f');
  await completions.waitFor({state: 'hidden'});
  checks.push('Three independent settings persist on reload. Timezones and modal feedback use the same list.');
  assert.deepEqual(errors, []);
  await writeFile(path.join(output, 'browser-result.json'), JSON.stringify({checks, openFrameMs, coldArithmeticMs: immediate.ms,
    workerRequests, errors}, null, 2) + '\n');
  console.log(JSON.stringify({checks, openFrameMs, coldArithmeticMs: immediate.ms, pageErrors: errors.length}));
} catch (error) {
  await page.screenshot({path: path.join(output, 'failure.png')}).catch(() => {});
  console.error(await dialog.evaluate(panel => ({
    expression: panel.querySelector('.calculatorExpression')?.value,
    result: panel.querySelector('.calculatorResult')?.textContent,
    focused: document.activeElement?.getAttribute('aria-label'),
  })).catch(() => null));
  throw error;
} finally {
  await browser.close();
}
