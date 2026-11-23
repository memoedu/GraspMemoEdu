import assert from 'node:assert/strict';
import {literalMathSegments} from '../web/math-presentation.js';
import {mathSpans} from '../web/math-syntax.js';
import {renderSourceHtml, renderSourceMarkdown} from './render_mathacademy.mjs';

const expressions = [
  '位置为 x_A, y_A, θ；满足 x_B=x_A+l cosθ。',
  '能量 E_k=m v^2/2，且 u_0^2+v_0^2=c^2。',
  '参数 q=(r,φ)，其中 r_1≤r_2。',
];
for (const text of expressions) {
  const segments = literalMathSegments(text);
  assert.equal(segments.map(segment => segment.text).join(''), text, 'Typography must preserve all source characters');
  assert.ok(segments.some(segment => segment.tokens?.some(token => token.sub)));
}
const trig = literalMathSegments('x_B=x_A+l cosθ').find(segment => segment.tokens).tokens;
assert.ok(trig.some(token => token.kind === 'function' && token.value === 'cos'));
assert.ok(trig.some(token => token.sub === 'B'));
for (const text of ['A plain answer with words.', 'Release 2026-10-06', 'abc_def', 'https://example.org/a_b', 'file_name.txt']) {
  const segments = literalMathSegments(text);
  assert.equal(segments.map(segment => segment.text).join(''), text);
  assert.equal(segments.some(segment => segment.tokens), false, text);
}
console.log('PASS literal math preserves answers, scripts and functions; prose, dates, URLs and file names remain literal');

const matrix = String.raw`$\mathbf{x}_1=\begin{bmatrix}0.2\\-0.3\end{bmatrix}$`;
const mixed = String.raw`$x$，\(y^2\)，$$\begin{cases}x&x>0\\0&x\leq0\end{cases}$$，\[z=0\]`;
assert.deepEqual([...mathSpans(mixed)].map(span => span.display), [false, false, true, true]);
assert.deepEqual([...mathSpans('$x$$y$2')].map(span => span.latex), ['x', 'y']);
const currency = String.raw`\$5 and $10, then $x^2$.`;
assert.deepEqual([...mathSpans(currency)].map(span => span.latex), ['x^2']);
assert.deepEqual([...mathSpans(String.raw`$a+\$b$ \[x\\ \]`)].map(span => span.latex), [String.raw`a+\$b`, String.raw`x\\ `]);
assert.deepEqual([...mathSpans(String.raw`\(\frac{x\) followed by \(y\)`)].map(span => span.latex), ['y']);
for (const input of [matrix, 'Let ' + matrix + ' be the first update.',
  String.raw`$\begin{bmatrix}1\\2\end{bmatrix}$`,
  '$x+\n' + String.raw`\begin{bmatrix}1\\2\end{bmatrix}$`]) {
  const {html} = renderSourceMarkdown(input);
  assert.equal((html.match(/<mjx-container/g) || []).length, 1);
  assert.match(html, /<p>[^<]*<span class="mathInline" data-tex=/);
  assert.doesNotMatch(html.replace(/<[^>]+>/g, ''), /\$|\\mathbf/);
}
const protectedHtml = renderSourceHtml('<p>Vector ' + matrix + '</p><code>$x$</code><pre>\\(z\\)</pre>').html;
assert.equal((protectedHtml.match(/<mjx-container/g) || []).length, 1);
assert.match(protectedHtml, /<code>\$x\$<\/code><pre>\\\(z\\\)<\/pre>/);
assert.equal((renderSourceMarkdown(currency).html.match(/<mjx-container/g) || []).length, 1);
console.log('PASS explicit delimiters, matrix-valued options, escapes, currency and protected code');

const native = '[math]x=\\begin{bmatrix}1\\\\2\\end{bmatrix}^T[/math]';
for (const {html} of [renderSourceMarkdown(native), renderSourceHtml('<p>' + native + '</p>')]) {
  assert.equal((html.match(/<mjx-container/g) || []).length, 1);
  assert.match(html, /data-tex="x=\\begin\{bmatrix\}[^"]+\^T"/);
  assert.doesNotMatch(html, /\[\/?math\]/i);
}
assert.match(renderSourceMarkdown('`[math]x[/math]`').html, /<code>\[math\]x\[\/math\]<\/code>/);
