import assert from 'node:assert/strict';
import test from 'node:test';
import {calculate} from '../web/calculator-engine.js';
import {expandScientificNotation} from '../web/calculator-panel.js';
import {calculatorWorksheets, expressionCompletions, permitsModule, tools} from '../web/calculator-policy.js';
import {formulaTemplates, matchesCompletion, nativeFormulaSample} from '../web/formula-catalog.js';
import previews from '../web/vendor/formula/previews.mjs';

test('plain decimal display preserves the digits and sign of a scientific result', () => {
  for (const [scientific, decimal] of [
    ['1.2e+24', '12' + '0'.repeat(23)],
    ['-2.5e-9', '-0.0000000025'],
    ['1.234e+1', '12.34'],
    ['-7.3E+308', '-73' + '0'.repeat(307)],
    ['5e-324', '0.' + '0'.repeat(323) + '5'],
  ]) assert.equal(expandScientificNotation(scientific), decimal);
  for (const result of ['256', '1e+309', '1e-325', '1e10000', '2e+8 + 1i', '2e+8 m²', '[1e+25]']) {
    assert.equal(expandScientificNotation(result), null);
  }
});

test('formula and calculator suggestions match insertions and each math choice has a built preview', () => {
  const native = expressionCompletions({level: 'cas'}, {equation: true});
  for (const item of native) assert.ok(previews[nativeFormulaSample(item.value)], item.value);
  for (const item of formulaTemplates) assert.ok(previews[item.sample], item.label);
  for (const entries of [native, formulaTemplates]) {
    const factorial = entries.find(item => (item.latex || item.value) === '!');
    assert.equal(factorial.label, '!');
    assert.ok(matchesCompletion(factorial, '!'));
    for (const query of ['F', 'f', 'X', 'x', 'digit', '5000']) {
      assert.equal(matchesCompletion(factorial, query), false);
      assert.equal(entries.some(item => item.label === 'factorial' && matchesCompletion(item, query)), false);
    }
    assert.ok(entries.some(item => item.label === 'floor' && matchesCompletion(item, 'f')));
    assert.ok(entries.some(item => item.label === 'factorial' && matchesCompletion(item, 'fact')));
  }
});

const modules = tools.map(([id]) => id);
const cas = {level: 'cas', enable_modules: modules};
const basic = {level: 'basic'};
const run = (module, operation, input, config = cas, options = {}) =>
  calculate({config, module, operation, input, ...options});
const evaluate = (expression, config = basic, options) => run('expression', 'evaluate', {expression}, config, options);
const approx = (a, b, tolerance = 1e-10) => assert.ok(Math.abs(a - b) < tolerance, `${a} != ${b}`);

test('toolbar lists available worksheets without duplicating scientific constants', () => {
  const ids = config => calculatorWorksheets(config).map(([id]) => id);
  assert.deepEqual(ids(undefined), []);
  assert.deepEqual(ids({level: 'none'}), []);
  assert.deepEqual(ids(basic), ['expression']);
  assert.deepEqual(ids({level: 'scientific', enable_modules: ['graph']}), ['expression', 'graph']);
  assert.deepEqual(ids({level: 'scientific', disable_keys: ['evaluate']}), []);
  assert.deepEqual(ids({level: 'advanced', enable_modules: ['modular'], disable_modules: ['matrix'],
    disable_keys: ['describe', 'linear_regression']}), ['expression', 'graph', 'integral', 'probability', 'modular']);
  assert.equal(ids(cas).includes('symbolic'), true);
});

test('scientific and higher calculators discover variables and evaluate with numeric bindings', async () => {
  const scientific = {level: 'scientific'};
  const discover = (expression, config = scientific) => run('expression', 'assign_variables', {expression}, config);
  assert.deepEqual(await discover('2x+x+y+z^2+sin(t)+pi'), {variables: ['x', 'y', 'z', 't']});
  assert.deepEqual(await discover('sin(pi)'), {variables: []});
  assert.deepEqual(await discover('xy+x*y'), {variables: ['xy', 'x', 'y']});
  for (const level of ['scientific', 'advanced', 'cas']) {
    const config = {level};
    assert.equal((await run('expression', 'evaluate', {
      expression: '2x+y+z^2', assignments: {x: 'sqrt(9)', y: '1+1', z: '4'},
    }, config)).numeric, 24);
    await assert.rejects(run('expression', 'evaluate', {expression: 'x+x'}, config), {code: 'unassigned'});
  }
  await assert.rejects(discover('x', basic), {code: 'restricted'});
  const banned = {level: 'scientific', disable_keys: ['assign_variables']};
  await assert.rejects(discover('x', banned), {code: 'restricted'});
  await assert.rejects(run('expression', 'evaluate', {expression: 'x', assignments: {x: '2'}}, banned), {code: 'restricted'});
  await assert.rejects(discover('x=1'), {code: 'restricted'});
  await assert.rejects(discover('x+y', {level: 'scientific', disable_keys: ['add']}), {code: 'restricted'});
  await assert.rejects(run('expression', 'evaluate', {expression: 'x', assignments: {x: 'sin(2)'}},
    {level: 'scientific', disable_keys: ['sin']}), {code: 'restricted'});
  await assert.rejects(run('expression', 'evaluate', {expression: 'x', assignments: {x: '1/0'}}, scientific), {code: 'domain'});
  await assert.rejects(discover('a+b+c+d+f+g+j+k+l+m+n+o+p+q'), {code: 'limit'});
});

test('all displayed example inputs run through their actual vendored component', async t => {
  for (const [module, , , operations] of tools) {
    for (const [operation, , , fields] of operations) {
      await t.test(operation, async () => {
        const input = Object.fromEntries(fields.map(([name, , , example]) => [name, example]));
        const result = await run(module, operation, input);
        assert.ok(result.text || result.plot?.some(point => Number.isFinite(point[1])) || result.entries?.length);
      });
    }
  }
});

test('four tiers, graphing legacy allowance and a positive grant for specialist modules', async () => {
  assert.equal((await evaluate('3 × (4 + 5) + log10(100)')).text, '29');
  await assert.rejects(evaluate('sin(0.5)'), {code: 'restricted'});
  approx((await evaluate('sin(30)', {level: 'scientific'}, {degrees: true})).numeric, .5);
  const graphing = {level: 'scientific', enable_modules: ['graph']};
  assert.deepEqual(modules.filter(module => permitsModule(graphing, module)), ['graph']);
  const graph = await run('graph', 'plot', {expression: 'x^2', lower: '-2', upper: '2'}, graphing);
  assert.deepEqual(graph.plot[240], [0, 0]);
  await assert.rejects(run('symbolic', 'solve', {expression: 'x^2=2'}, {level: 'advanced'}), {code: 'restricted'});
  await assert.rejects(run('modular', 'modular_power', {}, {level: 'cas'}), {code: 'restricted'});
});

test('base subscripts, existing logarithms and answer aliases share calculator permissions', async () => {
  for (const expression of ['log_2(8)', 'log₂(8)', 'log(8, 2)', 'log_{1+1}(8)', 'log_2(log_2(256))']) {
    assert.equal((await evaluate(expression)).numeric, 3);
    await assert.rejects(evaluate(expression, {...basic, disable_keys: ['log_base']}), {code: 'restricted'});
  }
  assert.equal((await evaluate('log_0.5(0.125)')).numeric, 3);
  approx((await evaluate('log(8)+ln(8)')).numeric, 2 * Math.log(8));
  for (const expression of ['log_1(8)', 'log_0(8)', 'log_{-2}(8)'])
    await assert.rejects(evaluate(expression), {code: 'domain'});
  await assert.rejects(evaluate('log₂(8)', {...basic, disable_keys: ['digit_2']}), {code: 'restricted'});
  assert.equal((await evaluate('log_2(8)', {...basic, disable_keys: ['comma']})).numeric, 3);
  assert.equal((await evaluate('answer+ans', basic, {answer: 4})).numeric, 8);
  await assert.rejects(evaluate('answer', {...basic, disable_keys: ['ans']}, {answer: 4}), {code: 'restricted'});
  const integral = await run('integral', 'definite_integral', {expression: 'log_2(8)', lower: '0', upper: '1'});
  assert.equal(integral.text, '3');
  assert.equal((await run('symbolic', 'simplify', {expression: 'log_2(8)'})).text, '3');
  const completions = expressionCompletions({...cas, disable_keys: ['sin', 'log_base', 'power']});
  assert.ok(completions.some(item => item.value === 'floor('));
  for (const disabled of ['sin(', 'log_', '^'])
    assert.ok(completions.every(item => item.value !== disabled));
});

test('disabled operations are blocked for typed and pasted input, aliases and tool calls', async () => {
  for (const [input, key] of [['3^5', 'power'], ['2π', 'multiply'], ['2π', 'constant_pi'],
    ['factorial(4)', 'factorial'], ['4!', 'factorial'], ['nCr(4,2)', 'combinations'],
    ['combinations(4,2)', 'combinations'], ['62', 'digit_6'], ['1e7', 'exponent_notation'],
    ['sqrt(4)', 'sqrt'], ['ln(2)', 'ln'], ['log(2)', 'ln'], ['(2+2)', 'open']]) {
    await assert.rejects(evaluate(input, {...cas, disable_keys: [key]}), {code: 'restricted'});
  }
  for (const expression of ['1;2', 'a=4', 'unknown(2)', 'det([[1]])', 'mod(2,1)'])
    await assert.rejects(evaluate(expression, cas), {code: 'restricted'});
  await assert.rejects(run('probability', 'normal_cdf', {}, {...cas, disable_modules: ['probability']}), {code: 'restricted'});
  await assert.rejects(run('matrix', 'matrix_inverse', {}, {...cas, disable_keys: ['matrix_inverse']}), {code: 'restricted'});
  await assert.rejects(run('matrix', 'normal_cdf', {}, cas), {code: 'restricted'});
  await assert.rejects(run('graph', 'plot', {expression: 'sin(x)', lower: '0', upper: '1'},
    {...cas, disable_keys: ['sin']}), {code: 'restricted'});
});

test('sample numeric accuracy and pathological inputs', async () => {
  approx(Number((await run('integral', 'definite_integral', {expression: 'x^2', lower: '1', upper: '0'})).text), -1 / 3);
  await assert.rejects(run('integral', 'definite_integral', {expression: '1/x', lower: '-1', upper: '1'}), {code: 'domain'});
  assert.equal((await run('matrix', 'linear_system', {a: '[[1,2],[3,4]]', b: '[5,11]'})).text, '[1, 2]');
  await assert.rejects(run('matrix', 'matrix_inverse', {a: '[[1,1],[1,1]]'}));
  await assert.rejects(run('matrix', 'matrix_multiply', {a: '[[1],[2,3]]', b: '[[1]]'}));
  await assert.rejects(run('statistics', 'linear_regression', {x: '3,3', y: '4,7'}), {code: 'domain'});
  const x = '1000,1001,1002';
  const probabilities = JSON.parse((await run('machine_learning', 'softmax', {x})).text);
  approx(probabilities.reduce((sum, p) => sum + p), 1);
  approx(Number((await run('machine_learning', 'cross_entropy', {x, label: '3'})).text), .4076059644443804);
  await assert.rejects(run('machine_learning', 'cosine_similarity', {x: '0,0', y: '1,1'}), {code: 'domain'});
  await assert.rejects(evaluate('1/0'), {code: 'domain'});
  await assert.rejects(evaluate('('.repeat(40) + '1' + ')'.repeat(40)), {code: 'limit'});
});

function exactPower(base, exponent, modulus) {
  let product = 1n;
  for (let factor = base % modulus; exponent > 0n; exponent >>= 1n) {
    if (exponent & 1n) product = product * factor % modulus;
    factor = factor * factor % modulus;
  }
  return (product % modulus + modulus) % modulus;
}

test('exact residues across hundreds of large integer cases', async () => {
  const modular = (expression, modulus) => run('modular', 'modular_power', {expression, modulus: String(modulus)});
  for (let i = 0n; i < 300n; i++) {
    const a = -(17n ** 22n) - i, b = 123456789012345678901234567890n + i ** 3n;
    const m = i * 719n + 1n;
    assert.equal((await modular(`(${a})^${b}`, m)).text, String(exactPower(a, b, m)));
  }
  const exponent = 2n ** 16n;
  assert.equal((await modular('7^(2^16) + 3 * 2^1000', 13)).text,
    String((exactPower(7n, exponent, 13n) + 3n * exactPower(2n, 1000n, 13n)) % 13n));
  await assert.rejects(modular('2^9', 0), {code: 'domain'});
  await assert.rejects(modular('2^-1', 7), {code: 'domain'});
});
