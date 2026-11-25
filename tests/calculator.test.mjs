import assert from 'node:assert/strict';
import test from 'node:test';
import {calculate, calculateImmediate, calculateSelectedFormula} from '../web/calculator-engine.js';

test('selected vector and matrix arithmetic preserves orientation and restrictions', async () => {
  for (const [expression, array] of [
    ['[[1],[-2],[3]]-[[4],[5],[6]]', [[-3],[-7],[-3]]],
    ['[[1,2]]+[[3,4]]', [[4,6]]],
    ['[[1,2],[3,4]]*[[5],[6]]', [[17],[39]]],
    ['-[[1],[-2]]', [[-1],[2]]],
    ['2*[[1],[-2]]', [[2],[-4]]],
    ['[[3],[1/2]]/2', [[1.5],[0.25]]],
      ['[[-2],[0]]+0.95*[[0.3],[0.1]]', [[-1.715],[0.095]]],
      ['-(1/20)*[[1],[3]]*2*(-2)', [[0.2],[0.6]]],
      ['[[-2],[0]]+0.95*[[0.3],[0.1]]-(1/20)*[[1],[3]]*2*(-2)', [[-1.515],[0.695]]],
  ]) {
      const actual = (await calculateSelectedFormula({expression, config:{level:'advanced'}, cas:false})).array;
      assert.deepEqual(actual.map(row => row.map(value => Number(value.toPrecision(12)))), array);
  }
  for (const expression of ['[[1],[2]]-[[1,2]]', '[[1],[2]]+[[1]]', '[[1],[2]]-1', '[[1,2]]*[[3,4]]']) {
    await assert.rejects(calculateSelectedFormula({expression}), {code:'matrix_dimensions'});
  }
  for (const config of [{level:'scientific'}, {level:'cas', disable_modules:['matrix']}, {level:'cas', disable_keys:['subtract']}]) {
    await assert.rejects(calculateSelectedFormula({expression:'[[1],[2]]-[[3],[4]]', config}), {code:'restricted'});
  }
});

test('selected symbolic vector and matrix calculations simplify each entry and retain denominators', async () => {
  const selection = '[[2*x],[3*x^2-2*x]]-y*[[5*x/y],[6*x]]';
  assert.deepEqual(await calculateSelectedFormula({expression:selection}), {
    text:'[[-3*x], [-x*(6*y-3*x+2)]]', nonZero:['y'],
  });
  for (const [expression, text] of [
    ['[[1,2],[3,4]]*[[x],[y]]', '[[x+2*y], [3*x+4*y]]'],
    ['[x,2]*[2,x]', '4*x'],
    ['-[[x,-y]]', '[[-x, y]]'],
    ['[[x,y]]-[[x,y]]', '[[0, 0]]'],
  ]) {
    assert.deepEqual(await calculateSelectedFormula({expression}), {text});
  }
  assert.deepEqual(await calculateSelectedFormula({expression:'[[x*y],[x*y]]/y'}), {
    text:'[[x], [x]]', nonZero:['y'],
  });
  await assert.rejects(calculateSelectedFormula({expression:'[[x],[1/(2-2)]]'}), {code:'domain'});
  await assert.rejects(calculateSelectedFormula({expression:'[[x],[y]]-[[x,y]]'}), {code:'matrix_dimensions'});
  await assert.rejects(calculateSelectedFormula({expression:selection, cas:false}), {code:'unassigned'});
  for (const config of [{level:'advanced'}, {level:'cas', disable_modules:['matrix']}, {level:'cas', disable_keys:['subtract']}]) {
    await assert.rejects(calculateSelectedFormula({expression:selection, config}));
  }
});
import {expandScientificNotation} from '../web/calculator-panel.js';
import {calculatorWorksheets, expressionCompletions, expressionExtensions, permitsModule, scientificCategories, tools} from '../web/calculator-policy.js';
import {formulaTemplates, matchesCompletion, nativeFormulaSample, nativeFunctionCompletions} from '../web/formula-catalog.js';
import previews from '../web/vendor/formula/previews.mjs';

test('selected OCR formulas reuse numeric, remainder and optional CAS calculation', async () => {
  for (const [expression, result] of [['3+7', '10'], ['mod(17,5)', '2'], ['2+17 mod 5', '4'], ['sin(pi/2)', '1']]) {
    assert.equal((await calculateSelectedFormula({expression, cas: false})).text, result);
  }
  assert.equal((await calculateSelectedFormula({expression: 'x+x'})).text, '2*x');
  await assert.rejects(calculateSelectedFormula({expression: 'x+x', cas: false}), {code: 'unassigned'});
  await assert.rejects(calculateSelectedFormula({expression: 'x+x', config: {level: 'scientific'}}), {code: 'unassigned'});
  await assert.rejects(calculateSelectedFormula({expression: '3+7=10'}), {code: 'expression_required'});
  await assert.rejects(calculateSelectedFormula({expression: 'mod(17,0)'}), {code: 'domain'});
  await assert.rejects(calculateSelectedFormula({expression: '17 mod 0'}), {code: 'domain'});
});

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

test('calculator completes only trailing round parentheses and still checks syntax and permissions', async () => {
  for (const [expression, numeric] of [['2×（3+4)', 14], ['2*(3+4', 14], ['2×（3+(4', 14]]) {
    assert.equal(calculateImmediate(expression, basic).numeric, numeric);
    assert.equal((await evaluate(expression)).numeric, numeric);
  }
  for (const [expression, numeric] of [
    ['sqrt（(3+1', 2], ['round（1.234，2', 1.23], ['log_{1+2}（27', 3], ['determinant（[[1,2],[3,4]]', -2],
  ]) approx((await evaluate(expression, cas)).numeric, numeric);
  assert.equal((await evaluate('A＝（2+3')).register, 'A');
  assert.equal((await run('symbolic', 'simplify', {expression: '2*(x+x'})).text, '4*x');
  assert.equal((await run('modular', 'modular_power', {expression: '2^(3+1', modulus: '7'})).numeric, 2);

  for (const expression of ['2*(3+', 'sqrt（', 'round(1.234,', '2+3) + (4', 'determinant([(1,2]', 'sigmoid([1,2']) {
    await assert.rejects(evaluate(expression, cas), SyntaxError);
  }
  await assert.rejects(run('symbolic', 'solve', {expression: '(x+2=3'}), SyntaxError);
  for (const key of ['open', 'close', 'add']) {
    const config = {...cas, disable_keys: [key]};
    assert.throws(() => calculateImmediate('（2+3', config), {code: 'restricted'});
    await assert.rejects(evaluate('sqrt（2+3', config), {code: 'restricted'});
  }
  await assert.rejects(evaluate('('.repeat(40) + '1', cas), {code: 'limit'});
});

test('compound arithmetic, comparisons and assignment compose with the existing expression syntax', async () => {
  const arithmetic = [['+=', (a, b) => a + b], ['-=', (a, b) => a - b], ['*=', (a, b) => a * b],
    ['/=', (a, b) => a / b], ['^=', (a, b) => a ** b]];
  const relations = [['==', (a, b) => a === b], ['!=', (a, b) => a !== b], ['<', (a, b) => a < b],
    ['<=', (a, b) => a <= b], ['>', (a, b) => a > b], ['>=', (a, b) => a >= b]];
  const numbers = [-8, -2, -1, 0, 1, 2, 8];
  for (const A of numbers) for (const B of numbers) {
    const options = {memory: {A, B}};
    for (const [op, calculate] of arithmetic) {
      if (!Number.isFinite(calculate(A, B))) continue;
      const result = await evaluate('A ' + op + ' B', basic, options);
      assert.equal(result.register, 'A');
      assert.equal(result.numeric, calculate(A, B));
    }
    for (const [op, compare] of relations) {
      const expected = Number(compare(A, B));
      assert.deepEqual(await evaluate('A ' + op + ' B', basic, options), {text: String(expected), numeric: expected});
      assert.equal((await evaluate('C = （A ' + op + ' B） + 1', basic, options)).numeric, expected + 1);
    }
  }
  const scientific = {level: 'scientific'};
  for (const [expression, expected] of [
    ['1+2<4==4', 1], ['1<2>3', 0], ['1<2<=3', 1], ['3>=2!=1', 1], ['2≤3', 1], ['2≥3', 0], ['2≠3', 1],
    ['3! != 5', 1], ['2^3 == 4+4', 1], [String.raw`$\sinh（0）+\cosh\left(0\right)$`, 1],
    [String.raw`\(log_{1+2}（27）\)`, 3], ['$2×（3+4）$', 14],
  ]) assert.equal((await evaluate(expression, scientific)).text, String(expected), expression);
  await assert.rejects(evaluate('A += 1', basic), {code: 'storage_required'});
  await assert.rejects(evaluate('A /= 0', basic, {memory: {A: 1}}), {code: 'domain'});
  await assert.rejects(evaluate('A += 1', {...basic, disable_keys: ['add']}, {memory: {A: 1}}), {code: 'restricted'});
  await assert.rejects(evaluate('A -= 1', {...basic, disable_keys: ['memory_registers']}), {code: 'restricted'});
  await assert.rejects(evaluate('1<2<=3', {...basic, disable_keys: ['smaller_eq']}), {code: 'restricted'});
  await assert.rejects(evaluate('[1,2] == [1,2]', cas), {code: 'domain'});
  for (const source of ['A+=B=2', 'A=(B+=1)', '(A=2)+1']) await assert.rejects(evaluate(source), {code: 'restricted'});
  assert.deepEqual(await run('expression', 'assign_variables', {expression: 'X == Y'}, scientific), {variables: ['X', 'Y']});
});

test('function definitions infer ASCII order, bind explicit parameters and share register overwrite semantics', async () => {
  const scientific = {level: 'scientific'};
  const memory = {X: 7};
  const execute = async (expression, defineFunction, options) => {
    const result = await run('expression', 'evaluate', {expression, defineFunction}, scientific, {memory, ...options});
    if (result.register) memory[result.register] = result.definition ?? result.numeric;
    return result;
  };
  assert.equal((await execute('F = X + 1')).numeric, 8);
  assert.deepEqual((await execute('F = X + 1', true)).definition, {expression: 'X + 1', parameters: ['X']});
  assert.equal((await execute('F（3）')).numeric, 4);
  assert.deepEqual((await execute('G = 10*Y + X', true)).definition.parameters, ['X', 'Y']);
  assert.equal((await execute('G（3，4）')).numeric, 43);
  assert.equal((await execute('G(Y, X) = 10*Y + X')).text, 'G(Y, X) = 10*Y + X');
  assert.equal((await execute('G(3,4)')).numeric, 34);
  assert.equal((await execute('H = a + 10*Z + 100*Z', true)).text, 'H(Z, a) = a + 10*Z + 100*Z');
  assert.equal((await execute('H(2,3)')).numeric, 223);
  assert.equal((await execute('F(F(3)) + F(5)')).numeric, 11);
  assert.equal((await execute('J(X) = G(F(X), X) + X')).text, 'J(X) = G(F(X), X) + X');
  assert.equal((await execute('J(3)')).numeric, 46);
  assert.equal((await execute('J(X) = X + Ans + pi')).definition.parameters.length, 1);
  approx((await execute('J(1)', false, {answer: 2})).numeric, 3 + Math.PI);
  await execute('J(T) = X + T');
  await execute('X = 10');
  assert.equal((await execute('J(2)')).numeric, 12);
  await execute('K() = 42');
  assert.equal((await execute('K()')).numeric, 42);
  await execute('ρ₁（β，α）＝10*β+α');
  assert.equal((await execute('ρ_{1}(3,4)')).numeric, 34);
  await execute('L(α_1) = α₁*2');
  assert.equal((await execute('L(3)')).numeric, 6);
  await execute('F = X + 1');
  assert.equal((await execute('F')).numeric, 11);
  await assert.rejects(execute('F(3)'), {code: 'function_arguments'});
  await execute('F(X) = X > 0');
  assert.equal((await execute('F(1)+F(-2)')).numeric, 1);
  await assert.rejects(execute('F += 1'), {code: 'function_arguments'});
  await assert.rejects(execute('F'), {code: 'function_arguments'});
  assert.equal((await evaluate('G', scientific)).numeric, 6.67430e-11);
});

test('function validation enforces permissions, arity, depth and the existing expression limits', async () => {
  const scientific = {level: 'scientific'};
  const define = (expression, config = scientific, memory) =>
    run('expression', 'evaluate', {expression, defineFunction: true}, config, {memory});
  const F = (await define('F=X+1')).definition;
  const memory = {F, H: (await define('H=F(X)', scientific, {F})).definition};
  for (const [source, code] of [
    ['X+1', 'function_definition'], ['F+=1', 'function_definition'], ['F(X,X)=X', 'function_definition'],
    ['F(X,)=X', 'function_definition'], ['F(X)=X+Y', 'function_definition'], ['sin(X)=X', 'restricted'],
    ['F(X)=Y=2', 'restricted'], ['F=H(X)', 'limit'], ['F(X)=(' + '('.repeat(40) + 'X' + ')'.repeat(41), 'limit'],
    ['F=A+B+C+D+E+X+Y+Z+a+b+d+f+g', 'limit'],
  ]) await assert.rejects(define(source, scientific, memory), {code});
  for (const key of ['memory_registers', 'define_function', 'evaluate', 'add']) {
    const config = {...scientific, disable_keys: [key]};
    await assert.rejects(define('F=X+1', config), {code: 'restricted'});
    await assert.rejects(evaluate('F(3)', config, {memory}), {code: 'restricted'});
  }
  await assert.rejects(define('F=X+1', basic), {code: 'restricted'});
  for (const source of ['F()', 'F(1,2)']) await assert.rejects(evaluate(source, scientific, {memory}), {code: 'function_arguments'});
  assert.deepEqual(await run('expression', 'assign_variables', {expression: 'F(Y) == Z'}, scientific, {memory}),
    {variables: ['Y', 'Z']});
  const repeated = Array(30).fill('X').join('+');
  const branch = 'F(X)=' + repeated;
  const heavy = (await define(branch)).definition;
  await assert.rejects(evaluate(Array(13).fill('F(1)').join('+'), scientific, {memory: {F: heavy}}), {code: 'limit'});
  assert.equal((await evaluate('A+1', scientific, {memory: {A: {expression: '2*3'}}})).numeric, 7);
});

test('answer and calculator completion share function templates and typed prefixes', () => {
  const generic = formulaTemplates.find(item => item.label === 'f');
  const empty = new Map();
  assert.equal(nativeFunctionCompletions('f', empty)[0], generic);
  assert.equal(nativeFunctionCompletions('F', empty)[0].value, 'F(');
  assert.deepEqual(nativeFunctionCompletions('F', new Map([['F', {value: 1}]])), []);
  const defined = nativeFunctionCompletions('Fu', new Map([['Func', {value: {parameters: ['X']}}]]));
  assert.equal(defined[0].value, 'Func(');
  assert.ok(matchesCompletion(defined[0], String.raw`\fu`));
});

test('letter registers work at every tier and take precedence over expression assignments', async () => {
  for (const level of ['basic', 'scientific', 'advanced', 'cas']) {
    const config = {level};
    assert.equal((await evaluate('2*A+B', config, {memory: {A: 8, B: 0}})).numeric, 16);
    assert.equal((await evaluate('A*3', config, {memory: {A: 1 / 3}})).numeric, 1);
  }
  const scientific = {level: 'scientific'};
  const options = {memory: {A: 8}};
  assert.deepEqual(await run('expression', 'assign_variables', {expression: 'A+x+B'}, scientific, options),
    {variables: ['x', 'B']});
  assert.equal((await run('expression', 'evaluate', {expression: 'A+x', assignments: {A: '999', x: 'A/2'}},
    scientific, options)).numeric, 12);
  await assert.rejects(evaluate('A+x', scientific, options), {code: 'unassigned'});
  await assert.rejects(evaluate('A', scientific), {code: 'unassigned'});
  await assert.rejects(evaluate('A', {...scientific, disable_keys: ['memory_registers']}, options), {code: 'unassigned'});
  assert.equal((await evaluate('A', {...scientific, disable_keys: ['assign_variables']}, options)).numeric, 8);
  assert.deepEqual(await evaluate('A=A+1', scientific, options), {text: '9', numeric: 9, register: 'A'});
  const complex = (await evaluate('2+3*i', scientific)).complex;
  assert.deepEqual((await evaluate('2*A', scientific, {memory: {A: complex}})).complex, {re: 4, im: 6});
  await assert.rejects(evaluate('A', basic, {memory: {A: complex}}), {code: 'restricted'});
});

test('named storage accepts common letters and scripts without confusing superscripts with powers', async () => {
  for (const level of ['basic', 'scientific', 'advanced', 'cas']) {
    const config = {level};
    assert.deepEqual(await evaluate('θ=5', config), {text: '5', numeric: 5, register: 'θ'});
    assert.deepEqual(await evaluate('ρ₁=2', config), {text: '2', numeric: 2, register: 'ρ_1'});
    assert.equal((await evaluate('ρ_{1}+θ', config, {memory: {'ρ_1': 2, θ: 5}})).numeric, 7);
    assert.equal((await evaluate('变量+Ж', config, {memory: {变量: 4, Ж: 3}})).numeric, 7);
    assert.deepEqual(await evaluate('u^{2}=7', config), {text: '7', numeric: 7, register: 'u²'});
    assert.equal((await evaluate('u²+u^2', config, {memory: {'u²': 7, u: 2}})).numeric, 11);
  }
  await assert.rejects(evaluate('pi=3'), {code: 'restricted'});
  await assert.rejects(evaluate('Ans=3'), {code: 'restricted'});
  await assert.rejects(evaluate('x=2=4'), {code: 'restricted'});
  await assert.rejects(evaluate('x=3', {...basic, disable_keys: ['memory_registers']}), {code: 'restricted'});
});

test('local arithmetic preserves operation precedence, formatting and calculator permissions', () => {
  assert.deepEqual(calculateImmediate('(2+3)*4-9/3', basic), {text: '17', numeric: 17});
  assert.deepEqual(calculateImmediate('2×(-4)+1', basic), {text: '-7', numeric: -7});
  assert.equal(calculateImmediate('1/3', basic).text, '0.33333333333333');
  assert.equal(calculateImmediate('2.64935064935065+0', basic).text, '2.6493506493507');
  assert.equal(calculateImmediate('1/10000', basic).text, '1e-4');
  assert.equal(calculateImmediate('1000*1000', basic).text, '1e+6');
  assert.equal(calculateImmediate('α+3', basic, {α: 4}).numeric, 7);
  assert.equal(calculateImmediate('sin(2)', basic), null);
  assert.equal(calculateImmediate('-2^2+2^3^2', basic).numeric, 508);
  assert.equal(calculateImmediate('(-4)^0.5', basic), null);
  assert.equal(calculateImmediate('Ans+2', basic, {}, 5).numeric, 7);
  assert.throws(() => calculateImmediate('2+3', {...basic, disable_keys: ['add']}), {code: 'restricted'});
  assert.throws(() => calculateImmediate('2+3', {...basic, disable_keys: ['digit_3']}), {code: 'restricted'});
  assert.throws(() => calculateImmediate('1/0', basic), {code: 'domain'});
});

test('standalone and integrated tools cover every authorized operation', () => {
  const ids = config => calculatorWorksheets(config).map(([id]) => id);
  assert.deepEqual(ids(undefined), []);
  assert.deepEqual(ids({level: 'none'}), []);
  assert.deepEqual(ids(basic), ['expression']);
  assert.deepEqual(ids({level: 'scientific', enable_modules: ['graph']}), ['expression', 'graph']);
  assert.deepEqual(ids({level: 'scientific', disable_keys: ['evaluate']}), []);
  assert.deepEqual(ids({level: 'advanced', enable_modules: ['modular'], disable_modules: ['matrix'],
    disable_keys: ['describe', 'linear_regression']}), ['expression', 'graph']);
  const standalone = calculatorWorksheets(cas);
  assert.deepEqual(standalone.map(([id]) => id), ['expression', 'graph', 'statistics', 'symbolic', 'machine_learning']);
  assert.deepEqual(standalone.find(([id]) => id === 'symbolic')[3].map(([key]) => key), ['antiderivative', 'solve', 'differentiate']);
  assert.deepEqual(standalone.find(([id]) => id === 'machine_learning')[3].map(([key]) => key), ['classification', 'pca']);
  const integrated = [...standalone, ...scientificCategories(cas)].flatMap(([, , , specs]) => specs?.map(([key]) => key) || []);
  assert.deepEqual([...integrated, 'simplify', 'modular_power'].sort(), tools.flatMap(([, , , specs]) => specs.map(([key]) => key)).sort());
  assert.deepEqual(ids({...cas, disable_keys: ['evaluate']}), modules);
});

test('every inline function uses the same calculation as its worksheet', async () => {
  for (const [operation, [module, fields]] of expressionExtensions) {
    const direct = await evaluate(operation + '(' + fields.map(([, example]) => example).join(', ') + ')', cas);
    const descriptors = tools.find(([id]) => id === module)[3].find(([id]) => id === operation)[3];
    const form = await run(module, operation, Object.fromEntries(descriptors.map(([field, , , example]) => [field, example])));
    if (form.entries) approx(direct.numeric, form.entries[0][1]);
    else assert.equal(direct.text, form.text, operation);
  }
  approx((await evaluate('2*sigmoid(-1)+cross_entropy(log_softmax([1000,1001,1002]),3)', cas)).numeric,
    2 / (1 + Math.E) + 0.40760596444438);
  const array = (await evaluate('softmax([1,2,3])', cas)).array;
  approx((await evaluate('cosine_similarity(Ans, A)', cas, {answer: array, memory: {A: array}})).numeric, 1);
  const restricted = {...cas, disable_keys: ['sigmoid', 'matrix_inverse']};
  await assert.rejects(evaluate('sigmoid(0)', restricted), {code: 'restricted'});
  await assert.rejects(evaluate('matrix_inverse([[1,0],[0,1]])', restricted), {code: 'restricted'});
  await assert.rejects(evaluate('relu(2)', {...cas, disable_modules: ['machine_learning']}), {code: 'restricted'});
  assert.ok(expressionCompletions(cas, {extensions: true}).some(({value}) => value === 'sigmoid('));
  assert.ok(expressionCompletions(restricted, {extensions: true}).every(({value}) => value !== 'sigmoid('));
  assert.equal((await run('symbolic', 'simplify', {expression: '2*x+3*x+y-y'})).text, '5*x');
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
  assert.deepEqual(await discover('x=y+1'), {variables: ['y']});
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
  for (const expression of ['1;2', 'a=4=5', 'unknown(2)', 'det([[1]])', 'mod(2,1)'])
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
