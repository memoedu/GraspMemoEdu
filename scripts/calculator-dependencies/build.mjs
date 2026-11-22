import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {mkdir, readdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const cache = path.resolve(process.argv[2]);
const root = path.resolve(directory, '../..');
const destination = path.join(root, 'web', 'vendor', 'calculator');
const require = createRequire(path.join(cache, 'package.json'));
const {build} = require('esbuild');
const packages = new Set();
const files = {};
const cleanNotice = text => text.replace(/\r\n/g, '\n').replace(/[ \t]+$/gm, '').trimEnd() + '\n';
await mkdir(destination, {recursive: true});

for (const name of ['core', 'advanced', 'symbolic', 'applied', 'completion']) {
  const output = await build({
    absWorkingDir: directory,
    entryPoints: [name + '.mjs'],
    outfile: path.join(destination, name + '.mjs'),
    nodePaths: [path.join(cache, 'node_modules')],
    bundle: true, minify: true, legalComments: 'linked', format: 'esm',
    platform: 'browser', target: 'es2022', write: false, metafile: true,
  });
  for (const input of Object.keys(output.metafile.inputs)) {
    const parts = path.resolve(directory, input).split(/[/\\]/);
    const index = parts.lastIndexOf('node_modules') + 1;
    if (!index) continue;
    packages.add(parts.slice(0, index + (parts[index].startsWith('@') ? 2 : 1)).join(path.sep));
  }
  for (const file of output.outputFiles) {
    const bytes = file.path.endsWith('.txt') ? cleanNotice(file.text) : file.contents;
    await writeFile(file.path, bytes);
    files['vendor/calculator/' + path.basename(file.path)] = createHash('sha256').update(bytes).digest('hex');
  }
}

const notices = new Map();
for (const dir of [...packages].sort()) {
  const spec = JSON.parse(await readFile(path.join(dir, 'package.json'), 'utf8'));
  const licenseFiles = (await readdir(dir)).filter(name => /^(?:licen[cs]e|notice|unlicense|copying)(?:\.|$)/i.test(name)).sort();
  const contents = await Promise.all(licenseFiles.map(name => readFile(path.join(dir, name), 'utf8')));
  if (!contents.length && !spec.license) throw new Error('Missing license for ' + spec.name);
  const contentsKey = contents.length ? contents.map(cleanNotice).join('\n') : 'License declaration in the upstream package.json.';
  const matching = notices.get(contentsKey) || [];
  matching.push(spec.name + '@' + spec.version + ' · ' + (spec.license || ''));
  notices.set(contentsKey, matching);
}
const uiLicense = 'Calc UI adaptations · Develifture/scientific-calculator f79fbd8a2 · MIT\n\n'
  + cleanNotice(await readFile(path.join(directory, 'Calc-LICENSE'), 'utf8'));
const notice = cleanNotice([uiLicense, ...[...notices].map(([license, names]) => names.join('\n') + '\n\n' + license)]
  .join('\n\n---------------------------\n\n'));
await writeFile(path.join(destination, 'LICENSES.txt'), notice);
files['vendor/calculator/LICENSES.txt'] = createHash('sha256').update(notice).digest('hex');
await writeFile(path.join(root, 'scripts', 'calculator-assets.json'), JSON.stringify({files}, null, 2) + '\n');
console.log('Built', Object.keys(files).length, 'calculator assets from', packages.size, 'packages');
