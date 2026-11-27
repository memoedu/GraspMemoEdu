/** Read-only submission lookup over the existing, host-key-checked SSH connection. */
import {execFile} from 'node:child_process';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

const maxResponse = 16 * 1024 * 1024;

export async function readSubmission(route, {get, expectedUserId}) {
  if (typeof route !== 'string') throw Error('Unsupported background lookup');
  const list = /^\/submissions\?step=[1-9]\d*&page_size=100&order=desc(?:&page=[1-9]\d{0,2})?$/.test(route);
  const single = /^\/submissions\/[1-9]\d*$/.test(route);
  if (!list && !single) throw Error('Unsupported background lookup');
  const profile = await get('/profiles/current');
  if (!Number.isSafeInteger(expectedUserId) || profile.profiles?.[0]?.id !== expectedUserId)
    throw Error('Background Hyperskill account mismatch');
  const result = await get(list ? `${route}&user=${expectedUserId}` : route);
  if (!Array.isArray(result.submissions)) throw Error('Missing Hyperskill submissions');
  const visible = result.submissions.filter(row => row.user_id === expectedUserId);
  return {submissions: visible.map(({id, attempt, step, user_id, status, time, reply, feedback}) =>
    ({id, attempt, step, user_id, status, time, reply, feedback})), meta: {has_next: result.meta?.has_next === true}};
}

/** Start network IO outside the bridge's journal updates. Only a completed read enters the queue. */
export function deferredSubmissionReader(read, ready) {
  const pending = new Map();
  const results = new Map();
  return (method, route) => {
    if (method !== 'GET') throw Error('Background worker only reads receipts');
    const now = Date.now();
    for (const [key, item] of results) if (item.until <= now) results.delete(key);
    if (results.has(route)) return results.get(route).data;
    if (!pending.has(route) && pending.size < 4) {
      const request = Promise.resolve().then(() => read(method, route));
      pending.set(route, request);
      request.then(data => {
        pending.delete(route);
        if (results.size >= 128) results.delete(results.keys().next().value);
        results.set(route, {data, until: Date.now()+15000});
        ready();
      }, () => pending.delete(route));
    }
    throw Error('Background lookup is pending');
  };
}

export function sshSubmissionReader({host, node, script, config}, expectedUserId) {
  if (typeof host !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9.-]*$/.test(host)) throw Error('Invalid background SSH alias');
  for (const value of [node, script, config]) {
    if (typeof value !== 'string' || !/^\/[A-Za-z0-9_./-]+$/.test(value) || value.split('/').includes('..'))
      throw Error('Invalid background worker path');
  }
  return (method, route) => new Promise((resolve, reject) => {
    if (method !== 'GET') return reject(Error('Background worker only reads receipts'));
    const child = execFile('ssh', ['-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
      '-o', 'ConnectTimeout=8', '--', host, `${node} ${script} ${config}`],
    {encoding: 'utf8', maxBuffer: maxResponse, timeout: 60000, windowsHide: true}, (error, stdout) => {
      if (error) return reject(Error('Mac Hyperskill background lookup unavailable'));
      try {
        const result = JSON.parse(stdout);
        if (result.user !== expectedUserId || !Array.isArray(result.data?.submissions)) throw Error();
        resolve(result.data);
      } catch { reject(Error('Invalid Mac Hyperskill background receipt')); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify({route}));
  });
}

export async function runReader(get, expectedUserId) {
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk;
    if (input.length > 1024) throw Error('Oversized background request');
  }
  const {route} = JSON.parse(input);
  const data = await readSubmission(route, {get, expectedUserId});
  process.stdout.write(JSON.stringify({user: expectedUserId, data}));
}

async function main() {
  const config = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
  const {LiveCookieSnapshot} = await import(pathToFileURL(config.cookieModule));
  const auth = new LiveCookieSnapshot({workflowRoot: config.cookieWorkflowRoot, dataRoot: config.cookieDataRoot});
  auth.refresh();
  await runReader(async route => {
    const url = 'https://hyperskill.org/api' + route;
    const cookie = auth.headerForUrl(url);
    if (!cookie) throw Error('Mac Hyperskill login is required');
    const response = await fetch(url, {headers: {Cookie: cookie, Accept: 'application/json'}, redirect: 'error',
      signal: AbortSignal.timeout(25000)});
    if (!response.ok) throw Error('Hyperskill lookup rejected');
    return response.json();
  }, config.expectedUserId);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch(() => { console.error('Hyperskill background lookup failed'); process.exitCode = 1; });
}
