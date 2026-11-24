/** Build a compact reverse lookup from the MathJax font used by archived HTML. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';

const runtime = process.env.MATH_TOPIC_PDF_RUNTIME || 'D:/Caches/MathTopicPdf/node_modules';
const require = createRequire(path.join(runtime, '_entry.cjs'));
const root = path.dirname(require.resolve('mathjax-full/package.json'));
const {version} = require('mathjax-full/package.json');
assert.equal(version, '3.2.2');
const {TeXFont} = require('mathjax-full/js/output/svg/fonts/tex.js');
const font = new TeXFont();
const aliases = new Map([[0x02b9, 0x2032], [0x00b7, 0x22c5]]);
const outlines = new Map();

for (const variant of Object.values(font.variant)) {
  for (const [code, metrics] of Object.entries(variant.chars)) {
    const outline = metrics[3]?.p;
    if (!outline) continue;
    const point = aliases.get(Number(code)) ?? Number(code);
    if (/[\p{Cc}\p{Co}]/u.test(String.fromCodePoint(point))) continue;
    const svgPath = 'M' + outline + 'Z';
    if (!outlines.has(svgPath)) outlines.set(svgPath, new Set());
    outlines.get(svgPath).add(point);
  }
}

const hashes = new Map();
for (const [outline, values] of outlines) {
  // A single outline can encode different operations. Leave those ambiguous.
  const meanings = new Set([...values].map(point => String.fromCodePoint(point).normalize('NFKC')));
  if (meanings.size !== 1) continue;
  const key = createHash('sha256').update(outline).digest('hex').slice(0, 24);
  assert.ok(!hashes.has(key), 'Duplicate SVG outline digest');
  hashes.set(key, values.values().next().value);
}

const output = new URL('../web/vendor/mathjax-svg-glyphs/', import.meta.url);
const assets = {
  'index.mjs': '// Generated from MathJax ' + version + ' SVG TeX font data by scripts/build_mathjax_svg_glyphs.mjs.\n'
    + 'export const glyphs = ' + JSON.stringify(Object.fromEntries([...hashes].sort()), null, 2) + ';\n',
  'LICENSE': await readFile(path.join(root, 'LICENSE'), 'utf8'),
};
if (process.argv.includes('--check')) {
  for (const [name, content] of Object.entries(assets))
    assert.equal(await readFile(new URL(name, output), 'utf8'), content, name);
} else {
  await mkdir(output, {recursive: true});
  for (const [name, content] of Object.entries(assets)) await writeFile(new URL(name, output), content);
}
console.log('PASS MathJax ' + version + ' outline lookup · ' + hashes.size + ' glyphs');
