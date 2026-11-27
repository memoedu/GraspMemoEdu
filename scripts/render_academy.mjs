import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {loadAssets} from './import_course.mjs';
import {renderSourceMarkdown} from './render_mathacademy.mjs';

const limit = 32 * 1024 * 1024;
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

async function freeze(task) {
  const assets = await loadAssets(task.source, task.markdown);
  return task.markdown.replace(/!\[([^\]\n]*)\]\(([^)\n]+)\)/g, (_m, alt, relative) =>
    `![${alt}](data:image/png;base64,${assets.get(relative).data.toString('base64')})`);
}

function remoteRenderer(config, payload) {
  const {host, node, script, modules} = config;
  if (typeof host !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9.-]*$/.test(host)) throw Error('Invalid Academy render SSH alias');
  for (const value of [node, script, modules]) {
    if (typeof value !== 'string' || !/^\/[a-zA-Z0-9_./-]+$/.test(value) || value.split('/').includes('..'))
      throw Error('Invalid Academy render SSH path');
  }
  const command = `env CODEX_NODE_MODULES=${modules} MATH_TOPIC_PDF_RUNTIME=${modules} GRASPMEMOEDU_NODE_MODULES=${modules} ${node} ${script} --frozen-stdin`;
  return new Promise((resolve,reject)=>{
    const child = execFile('ssh',['-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
      '-o','ConnectTimeout=8','--',host,command],{timeout:60000,maxBuffer:limit,windowsHide:true},
    (error, stdout) => {
      if (error && (error.code === 255 || error.killed)) return resolve(null);
      if (error) return reject(Error('Remote Academy renderer failed'));
      try { resolve(JSON.parse(stdout)); } catch { reject(Error('Unreadable Academy render receipt')); }
    });
    child.stdin.on('error',()=>{});
    child.stdin.end(payload);
  });
}

const [input, output, remote] = process.argv.slice(2);
if (input === '--frozen-stdin') {
  let chunks = [], size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > limit) throw Error('Oversized frozen Academy render input');
    chunks.push(chunk);
  }
  const payload = Buffer.concat(chunks);
  const tasks = JSON.parse(payload);
  if (!Array.isArray(tasks) || tasks.some(task=>typeof task !== 'string')) throw Error('Invalid frozen Academy render input');
  process.stdout.write(JSON.stringify({source_sha256:digest(payload),result:tasks.map(renderSourceMarkdown)}));
} else {
  const markdown = [];
  for (const task of JSON.parse(await fs.readFile(input, 'utf8'))) markdown.push(await freeze(task));
  const payload = Buffer.from(JSON.stringify(markdown));
  const source_sha256 = digest(payload);
  const receipt = remote && payload.length<=limit ? await remoteRenderer(JSON.parse(remote),payload) : null;
  if (receipt && (receipt.source_sha256 !== source_sha256 || !Array.isArray(receipt.result) ||
      receipt.result.length !== markdown.length || receipt.result.some(value=>typeof value?.html !== 'string' || typeof value?.css !== 'string')))
    throw Error('Remote Academy render receipt does not match its frozen input');
  const result = receipt ? receipt.result : markdown.map(renderSourceMarkdown);
  await fs.writeFile(output, JSON.stringify(result));
  if (remote) await fs.writeFile(output.replace(/\.json$/,'-receipt.json'),JSON.stringify({source_sha256,
    result_sha256:digest(Buffer.from(JSON.stringify(result))), tasks:result.length, renderer:receipt?'ssh':'local-fallback'}));
  console.log(`Rendered ${result.length} Academy tasks with the shared content renderer`);
}
