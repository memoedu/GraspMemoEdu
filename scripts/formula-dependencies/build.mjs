import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {mkdir, readFile, readdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {formulaTemplates, nativeFormulaSample} from '../../web/formula-catalog.js';
import {expressionCompletions} from '../../web/calculator-policy.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const cache = path.resolve(process.argv[2]);
const dest = path.join(root, 'web/vendor/formula');
const require = createRequire(path.join(cache, 'package.json'));
const {build} = require('esbuild');
const katex = require('katex');
const lock = JSON.parse(await readFile(path.join(here, 'package-lock.json'), 'utf8'));
const files = {};
const packages = new Set();

for (const [name, info] of Object.entries(lock.packages)) {
  if (!name || info.optional) continue;
  const installed = JSON.parse(await readFile(path.join(cache, name, 'package.json'), 'utf8'));
  if (installed.version !== info.version) throw new Error('Formula dependency drift: ' + name);
}
await mkdir(path.join(dest, 'fonts'), {recursive: true});
async function publish(name, bytes) {
  await writeFile(path.join(dest, name), bytes);
  files['vendor/formula/' + name] = createHash('sha256').update(bytes).digest('hex');
}
const runtime = await build({
  absWorkingDir: here, entryPoints: ['editor.mjs'], outfile: path.join(dest, 'editor.mjs'),
  nodePaths: [path.join(cache, 'node_modules')], bundle: true, minify: true, legalComments: 'linked',
  platform: 'browser', format: 'esm', target: 'es2022', metafile: true, write: false,
});
for (const input of Object.keys(runtime.metafile.inputs)) {
  const parts = path.resolve(here, input).split(/[/\\]/);
  const index = parts.lastIndexOf('node_modules') + 1;
  if (index) packages.add(parts.slice(0, index + (parts[index].startsWith('@') ? 2 : 1)).join(path.sep));
}
for (const file of runtime.outputFiles) await publish(path.basename(file.path), file.contents);

const mathlive = path.join(cache, 'node_modules/mathlive');
for (const name of await readdir(path.join(mathlive, 'fonts'))) {
  if (name.endsWith('.woff2')) await publish('fonts/' + name, await readFile(path.join(mathlive, 'fonts', name)));
}
const normalize = text => text.replace(/\r\n/g, '\n').replace(/[ \t]+$/gm, '').trimEnd();
const licenses = new Map();
for (const dir of [...packages].sort()) {
  const spec = JSON.parse(await readFile(path.join(dir, 'package.json'), 'utf8'));
  const matching = (await readdir(dir)).filter(name => /^(license|licence|copying|notice)(\.|$)/i.test(name));
  const body = (await Promise.all(matching.map(name => readFile(path.join(dir, name), 'utf8')))).map(normalize).join('\n\n');
  if (!body && !spec.license) throw new Error('Missing license for ' + spec.name);
  const grouped = licenses.get(body) || [];
  grouped.push(spec.name + '@' + spec.version + ' · ' + (spec.license || ''));
  licenses.set(body, grouped);
}
await publish('LICENSES.txt', [...licenses].map(([body, names]) => names.join('\n') + '\n\n' + body)
  .join('\n\n---------------------------\n\n').trimEnd() + '\n');

const samples = new Set([...formulaTemplates.map(item => item.sample),
  ...expressionCompletions({level: 'cas'}, {equation: true}).map(item => nativeFormulaSample(item.value)),
  ...'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789']);
const previews = Object.fromEntries([...samples].filter(Boolean).map(sample => [sample, katex.renderToString(sample, {
  trust: false, throwOnError: true, maxExpand: 100, maxSize: 10, strict: 'ignore', output: 'html',
})]));
await publish('previews.mjs', 'export default ' + JSON.stringify(previews) + ';\n');
await writeFile(path.join(root, 'scripts/formula-assets.json'), JSON.stringify({files}, null, 2) + '\n');
console.log('Built ' + Object.keys(files).length + ' formula assets.');
