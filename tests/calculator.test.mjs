import assert from 'node:assert/strict';
import test from 'node:test';
import {calculate} from '../web/calculator-engine.js';
import {permitsModule, tools} from '../web/calculator-policy.js';

const modules = tools.map(([id]) => id);
const cas = {level: 'cas', enable_modules: modules};
const basic = {level: 'basic'};
const run = (module, operation, input, config = cas, options = {}) =>
  calculate({config, module, operation, input, ...options});
const evaluate = (expression, config = basic, options) => run('expression', 'evaluate', {expression}, config, options);
const approx = (a, b, tolerance = 1e-10) => assert.ok(Math.abs(a - b) < tolerance, `${a} != ${b}`);

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
